"""Enriquecimiento opcional de metadata de modelos desde models.dev.

Trae metadata de display/decision (``context_window``, ``pricing``, ``capabilities``)
desde la API publica de models.dev y la cachea en disco con TTL. Es PURAMENTE
complementario: la base local (``provider_catalog`` / ``providers.json``) MANDA en routing
(base_url/wire/api_key_env); esto solo agrega metadata.

Diseno:
    - Lazy: nada se dispara en import time. El fetch ocurre solo al llamar a las funciones
      publicas y respeta el cache.
    - Sin red = no-op silencioso: timeout corto + try/except que degradan a ``{}`` sin
      crashear ni loguear ruido.
    - Cache propio: ``~/.antigravity/providers/models_dev_cache.json`` (NO se pisa el
      ``models_cache.json`` de ``model_resolver``, que tiene otro formato y otro uso).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# Endpoint publico de models.dev. Devuelve un JSON con metadata de modelos por provider.
MODELS_DEV_URL = "https://models.dev/api.json"

# TTL del cache en segundos (24h). Pasado el TTL se reintenta el fetch; si falla, se
# reutiliza el cache vencido como ultimo recurso (mejor metadata vieja que ninguna).
CACHE_TTL_SECONDS = 24 * 60 * 60

# Timeout corto del fetch: sin red, esto debe fallar rapido y degradar a {}.
_FETCH_TIMEOUT_SECONDS = 5


def cache_path() -> Path:
    """Path del cache propio de models.dev.

    Returns:
        ``~/.antigravity/providers/models_dev_cache.json`` (nombre propio para no
        colisionar con el ``models_cache.json`` de ``model_resolver``).
    """
    return Path.home() / ".antigravity" / "providers" / "models_dev_cache.json"


def _read_cache(path: Path) -> dict | None:
    """Lee el cache si existe y no esta vencido.

    Args:
        path: Path del archivo de cache.

    Returns:
        El payload cacheado (clave ``data``) si el cache es valido y fresco; ``None`` si
        falta, esta corrupto o vencido.
    """
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, dict):
        return None
    fetched_at = cached.get("fetched_at")
    data = cached.get("data")
    if not isinstance(fetched_at, int | float) or not isinstance(data, dict):
        return None
    if (time.time() - fetched_at) > CACHE_TTL_SECONDS:
        return None
    return data


def _read_cache_stale(path: Path) -> dict | None:
    """Lee el ``data`` del cache ignorando el TTL (ultimo recurso sin red).

    Args:
        path: Path del archivo de cache.

    Returns:
        El payload cacheado aunque este vencido, o ``None`` si falta/corrupto.
    """
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    data = cached.get("data") if isinstance(cached, dict) else None
    return data if isinstance(data, dict) else None


def _write_cache(path: Path, data: dict) -> None:
    """Persiste el payload de models.dev en el cache con timestamp.

    Args:
        path: Path del archivo de cache.
        data: Payload crudo de la API a cachear.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": time.time(), "data": data}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # best-effort: no poder cachear no es fatal
        logger.debug("No se pudo escribir el cache de models.dev: %s", exc)


def _fetch_remote() -> dict | None:
    """Fetch del JSON de models.dev con timeout corto.

    Returns:
        El payload crudo de la API, o ``None`` si no hay red / la respuesta no parsea.
    """
    try:
        # URL constante y publica; no es input del usuario.
        with urllib.request.urlopen(  # noqa: S310
            MODELS_DEV_URL, timeout=_FETCH_TIMEOUT_SECONDS
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — best-effort: cualquier fallo degrada a None
        return None
    return data if isinstance(data, dict) else None


def get_catalog(path: Path | None = None, *, force_refresh: bool = False) -> dict:
    """Devuelve el catalogo crudo de models.dev (cache-first, lazy).

    Resuelve en orden: cache fresco -> fetch remoto (y cachea) -> cache vencido ->
    ``{}``. Nunca crashea; sin red devuelve ``{}`` (o el cache vencido si existe).

    Args:
        path: Override del path del cache (tests).
        force_refresh: Si ``True``, ignora el cache fresco y reintenta el fetch.

    Returns:
        El payload crudo de models.dev, o ``{}`` si no hay datos disponibles.
    """
    cpath = path or cache_path()

    if not force_refresh:
        fresh = _read_cache(cpath)
        if fresh is not None:
            return fresh

    remote = _fetch_remote()
    if remote is not None:
        _write_cache(cpath, remote)
        return remote

    stale = _read_cache_stale(cpath)
    return stale if stale is not None else {}


def _find_model_entry(catalog: dict, provider: str, model_id: str) -> dict | None:
    """Busca la entrada de un modelo en el catalogo de models.dev.

    El formato de models.dev agrupa modelos por provider; aca buscamos por ``model_id``
    de forma tolerante: primero dentro del provider homonimo, luego en cualquier provider.
    El match es por id exacto (case-insensitive).

    Args:
        catalog: Payload crudo de models.dev.
        provider: Id del provider local (hint de busqueda).
        model_id: Id del modelo a enriquecer.

    Returns:
        El dict de la entrada del modelo, o ``None`` si no hay match.
    """
    if not isinstance(catalog, dict) or not model_id:
        return None
    target = model_id.strip().lower()

    def _scan(provider_block: object) -> dict | None:
        if not isinstance(provider_block, dict):
            return None
        models = provider_block.get("models")
        if isinstance(models, dict):
            for mid, entry in models.items():
                if isinstance(mid, str) and mid.lower() == target and isinstance(entry, dict):
                    return entry
        elif isinstance(models, list):
            for entry in models:
                if isinstance(entry, dict):
                    mid = entry.get("id")
                    if isinstance(mid, str) and mid.lower() == target:
                        return entry
        return None

    # 1) Provider homonimo (mas confiable).
    hit = _scan(catalog.get(provider))
    if hit is not None:
        return hit

    # 2) Cualquier provider (models.dev nombra distinto que nuestros ids locales).
    for block in catalog.values():
        hit = _scan(block)
        if hit is not None:
            return hit
    return None


def _is_zero(value: object) -> bool:
    """True si el valor numérico (int/float/str) representa cero."""
    try:
        return float(value) == 0.0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def model_is_free(model_id: str, entry: dict | None = None) -> bool:
    """Clasifica si un modelo es gratuito (cero costo).

    Orden de decisión (spec §4): marca explícita en el id manda; luego costo cero
    declarado en models.dev; si no hay ni marca ni costo, se asume PAGO (conservador,
    para no inducir un cobro creyendo que es gratis).

    Args:
        model_id: Id del modelo (p. ej. ``qwen/qwen3-coder:free``).
        entry: Entrada cruda de models.dev del modelo (con ``cost``/``pricing``), si está.

    Returns:
        ``True`` si el modelo es free; ``False`` si es pago o desconocido.
    """
    mid = (model_id or "").strip().lower()
    # 1. Marca explícita en el id (convención OpenRouter ':free' / OpenCode '*-free').
    if mid.endswith(":free") or mid.endswith("-free"):
        return True
    # 2. Costo cero declarado (tolera 'cost'|'pricing', input|prompt / output|completion).
    cost = None
    if isinstance(entry, dict):
        cost = entry.get("cost") or entry.get("pricing")
    if isinstance(cost, dict):
        inp = cost.get("input", cost.get("prompt"))
        out = cost.get("output", cost.get("completion"))
        if inp is not None and out is not None and _is_zero(inp) and _is_zero(out):
            return True
    # 3. Desconocido -> pago (conservador).
    return False


def list_provider_models(provider: str, *, path: Path | None = None) -> list[tuple[str, bool]]:
    """Lista los modelos de un provider desde models.dev, marcando los free.

    Lee el bloque ``<provider>.models`` del catálogo de models.dev y devuelve
    ``[(id, free)]`` ordenado free-primero (orden relativo estable). Degrada a ``[]``
    sin red/cache/match, igual que el resto del módulo.

    Args:
        provider: Id del provider local (``openrouter``, ``opencode``).
        path: Override del path del cache de models.dev (tests).

    Returns:
        Lista de ``(model_id, is_free)`` free-primero; ``[]`` si no hay datos.
    """
    catalog = get_catalog(path=path)
    block = catalog.get(provider.strip().lower()) if isinstance(catalog, dict) else None
    raw_models = block.get("models") if isinstance(block, dict) else None

    pairs: list[tuple[str, dict | None]] = []
    if isinstance(raw_models, dict):
        for mid, entry in raw_models.items():
            if isinstance(mid, str) and mid:
                pairs.append((mid, entry if isinstance(entry, dict) else None))
    elif isinstance(raw_models, list):
        for entry in raw_models:
            if isinstance(entry, dict):
                mid = entry.get("id")
                if isinstance(mid, str) and mid:
                    pairs.append((mid, entry))

    out = [(mid, model_is_free(mid, entry)) for mid, entry in pairs]
    # Free primero, orden relativo estable (sort estable de Python).
    out.sort(key=lambda t: 0 if t[1] else 1)
    return out


def enrich_model(provider: str, model_id: str, *, path: Path | None = None) -> dict:
    """Enriquece un modelo con metadata de models.dev.

    Lazy y degradante: si no hay red ni cache, o no hay match, devuelve ``{}`` sin
    crashear. La base local manda en routing; esto es solo metadata de display/decision.

    Args:
        provider: Id del provider local (claude, minimax, zai, ...).
        model_id: Id del modelo a enriquecer.
        path: Override del path del cache (tests).

    Returns:
        Dict con ``context_window``, ``pricing`` y ``capabilities`` si hubo match;
        ``{}`` si no hay red/cache/match.
    """
    catalog = get_catalog(path=path)
    entry = _find_model_entry(catalog, provider.strip().lower(), model_id)
    if entry is None:
        return {}

    return {
        "context_window": entry.get("context_window") or entry.get("limit"),
        "pricing": entry.get("pricing") or entry.get("cost"),
        "capabilities": entry.get("capabilities") or entry.get("modalities"),
    }
