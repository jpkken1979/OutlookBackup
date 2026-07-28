"""Resolucion dinamica del modelo "mejor" (mas nuevo) por provider IA.

Estrategia hibrida (decision 2026-06-01, K. Kaneshiro): cuando se conmuta a un
provider sin especificar modelo, en vez de clavar un default hardcodeado, se
resuelve el modelo a usar asi:

1. **Override explicito** — env var ``ANTIGRAVITY_<PROVIDER>_MODEL`` (p. ej.
   ``ANTIGRAVITY_MINIMAX_MODEL=MiniMax-M3``). Si esta seteada, gana siempre.
2. **Cache fresco** — ``~/.antigravity/providers/models_cache.json`` con TTL.
   Lo comparten las tres capas (CLI/MCP/gateway en Python y Nexus en Rust).
3. **Fetch best-effort** — ``GET {base_url}/v1/models`` del propio provider;
   se ordena por version (el mas nuevo gana) y se cachea.
4. **Fallback estatico** — la lista conocida ``known_models``; el mas nuevo por
   version. Degrada con gracia sin red (sandbox/CI) o si el provider no expone
   el listado.

Criterio de "mejor" = **mas nuevo por version** (M3 > M2.7, glm-6 > glm-5.1).
A igualdad de version, el flagship le gana a las variantes reducidas
(air/mini/nano/lite/flash).

El fetch usa solo stdlib (``urllib``) con timeout corto: no agrega dependencias
ni bloquea perceptiblemente el switch (normalmente sirve desde cache).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# TTL por defecto del cache de modelos (segundos). Override: ANTIGRAVITY_MODEL_CACHE_TTL.
_DEFAULT_TTL_SECONDS = 86_400  # 24h

# Timeout del fetch a /v1/models (segundos). Corto: si el provider no responde,
# caemos al fallback sin penalizar el switch.
_FETCH_TIMEOUT_SECONDS = 2.5

# Endpoints candidatos de discovery de modelos por provider. Se prueban EN ORDEN y
# gana el primero que devuelva una lista parseable. No asumimos que el host de
# /v1/messages (anthropic-compatible) tambien liste modelos: probamos tambien el host
# nativo del provider, que suele ser el unico que expone /v1/models o /paas/v4/models.
_DISCOVERY_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "minimax": (
        "https://api.minimax.io/anthropic/v1/models",
        "https://api.minimax.io/v1/models",
        "https://api.minimaxi.chat/v1/models",
    ),
    "zai": (
        "https://api.z.ai/api/anthropic/v1/models",
        "https://api.z.ai/api/paas/v4/models",
        "https://open.bigmodel.cn/api/paas/v4/models",
    ),
    "openrouter": ("https://openrouter.ai/api/v1/models",),
    "opencode": ("https://opencode.ai/zen/go/v1/models",),
    "nvidia": ("https://integrate.api.nvidia.com/v1/models",),
}

# Sufijos que marcan una variante "reducida" de un modelo (no flagship). A igualdad
# de version numerica, el modelo sin estos sufijos se considera superior.
_REDUCED_VARIANT_TOKENS = frozenset(
    {"air", "mini", "nano", "lite", "flash", "small", "tiny", "fast"}
)

# Regex de grupos numericos consecutivos dentro del id (version semantica laxa).
_VERSION_RE = re.compile(r"\d+")

# Timeout del probe de validacion de modelo (segundos) y tope de candidatos a
# probar antes de degradar al fallback estatico. Kill switch:
# ANTIGRAVITY_DISABLE_MODEL_VALIDATE=1.
_VALIDATE_TIMEOUT_SECONDS = 6.0
_VALIDATE_MAX_CANDIDATES = 3

# Una entrada de modelo descubierta: (id, created_epoch | None).
ModelEntry = tuple[str, "float | None"]


def _truthy(value: str | None) -> bool:
    """True si el string representa un booleano afirmativo de entorno."""
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def version_key(model_id: str, family: str = "") -> tuple[tuple[int, ...], int]:
    """Calcula la clave de ordenamiento por version de un id de modelo.

    Args:
        model_id: Identificador del modelo (p. ej. ``MiniMax-M2.7``, ``glm-4.5-air``).
        family: Prefijo de familia a recortar antes de parsear (p. ej. ``glm``);
            evita que numeros del prefijo contaminen la version.

    Returns:
        Tupla ``(version_tuple, variant_rank)`` comparable: mayor = mas nuevo.
        ``variant_rank`` es 1 para flagship y 0 para variantes reducidas, de modo
        que a igual version el flagship gana.
    """
    body = model_id
    if family and body.lower().startswith(family.lower()):
        body = body[len(family) :]
    nums = tuple(int(n) for n in _VERSION_RE.findall(body))
    tokens = {t.lower() for t in re.split(r"[-_.\s]+", model_id) if t}
    variant_rank = 0 if tokens & _REDUCED_VARIANT_TOKENS else 1
    return (nums, variant_rank)


def _normalize_entries(raw: Sequence[object]) -> list[ModelEntry]:
    """Normaliza una lista heterogenea a ``[(id, created_epoch|None)]``.

    Acepta strings sueltos, tuplas ``(id, created)`` o dicts ``{"id", "created"}``,
    asi el resolver tolera tanto la lista conocida (strings) como el fetch remoto.
    """
    out: list[ModelEntry] = []
    for item in raw:
        if isinstance(item, str):
            if item:
                out.append((item, None))
        elif isinstance(item, (tuple, list)) and item:
            mid = str(item[0])
            created = item[1] if len(item) > 1 else None
            if mid:
                out.append((mid, created if isinstance(created, (int, float)) else None))
        elif isinstance(item, dict):
            raw_id = item.get("id") or item.get("name") or item.get("model")
            if isinstance(raw_id, str) and raw_id:
                out.append((raw_id, _to_epoch(item.get("created") or item.get("created_at"))))
    return out


def _entry_sort_key(entry: ModelEntry, family: str) -> tuple[tuple[int, ...], int, float]:
    """Clave de orden de una entrada: version PRIMARIO, fecha como desempate.

    El criterio elegido es "mas nuevo por version" (M3 > M2.7), de modo que la
    version manda. La fecha de lanzamiento (``created``) solo desempata cuando la
    version es igual/ambigua o no se puede parsear (naming nuevo sin numeros).
    """
    mid, created = entry
    nums, variant_rank = version_key(mid, family)
    return (nums, variant_rank, created if created is not None else -1.0)


def best_entry(entries: Sequence[object], family: str = "") -> str | None:
    """Devuelve el id "mas nuevo" de una lista de entradas (str/tuple/dict).

    Args:
        entries: Modelos candidatos (ids sueltos o entradas con fecha).
        family: Prefijo de familia para filtrar/parsear (``MiniMax``, ``glm``).

    Returns:
        El id ganador, o ``None`` si no queda candidato tras filtrar por familia.
    """
    fam = family.lower()
    normalized = [e for e in _normalize_entries(entries) if not fam or e[0].lower().startswith(fam)]
    if not normalized:
        return None
    return max(normalized, key=lambda e: _entry_sort_key(e, family))[0]


def latest_model(models: list[str], family: str = "") -> str | None:
    """Atajo de ``best_entry`` para listas de ids sin fecha (lista conocida)."""
    return best_entry(list(models), family)


def _display_ids(entries: Sequence[object], family: str = "") -> list[str]:
    """Normaliza entradas a una lista de ids lista para mostrar.

    Filtra por familia (el ``/v1/models`` nativo de los providers mezcla otras
    lineas: speech, embeddings, cogview), deduplica preservando el primero y
    ordena del mas nuevo al mas viejo (mismo criterio que ``best_entry``).

    Args:
        entries: Modelos candidatos (ids sueltos o entradas con fecha).
        family: Prefijo de familia para filtrar (``MiniMax``, ``glm``).

    Returns:
        Ids unicos ordenados newest-first; vacia si nada pasa el filtro.
    """
    fam = family.lower()
    normalized = [e for e in _normalize_entries(entries) if not fam or e[0].lower().startswith(fam)]
    normalized.sort(key=lambda e: _entry_sort_key(e, family), reverse=True)
    seen: set[str] = set()
    out: list[str] = []
    for mid, _ in normalized:
        if mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


# ── Cache compartido ─────────────────────────────────────────────────────────


def cache_path() -> Path:
    """Path del cache de modelos (override por ``ANTIGRAVITY_MODEL_CACHE``)."""
    override = os.environ.get("ANTIGRAVITY_MODEL_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".antigravity" / "providers" / "models_cache.json"


def _read_cache() -> dict[str, object]:
    """Lee el cache tolerando ausencia/corrupcion (devuelve ``{}``)."""
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(cache: dict[str, object]) -> None:
    """Persiste el cache de modelos (crea el directorio padre si falta)."""
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover - IO best-effort
        logger.warning("No se pudo escribir el cache de modelos en %s: %s", path, exc)


def _ttl_seconds() -> int:
    """TTL configurable del cache (env ``ANTIGRAVITY_MODEL_CACHE_TTL``)."""
    raw = os.environ.get("ANTIGRAVITY_MODEL_CACHE_TTL")
    if raw and raw.isdigit():
        return int(raw)
    return _DEFAULT_TTL_SECONDS


def _cache_fresh(entry: object) -> bool:
    """True si la entrada de cache tiene un ``best`` y no expiro segun el TTL."""
    if not isinstance(entry, dict) or not entry.get("best"):
        return False
    ts = entry.get("ts")
    if not isinstance(ts, (int, float)):
        return False
    return (time.time() - ts) < _ttl_seconds()


# ── Fetch remoto best-effort ─────────────────────────────────────────────────


def _to_epoch(value: object) -> float | None:
    """Convierte un ``created`` (epoch int, epoch ms, o ISO-8601) a epoch segundos."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        secs = float(value)
        return secs / 1000.0 if secs > 1e12 else secs  # heuristica ms -> s
    if isinstance(value, str) and value.strip():
        txt = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(txt)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    return None


def _candidate_urls(provider_id: str, base_url: str) -> list[str]:
    """Lista ordenada y deduplicada de URLs de discovery a probar."""
    urls: list[str] = list(_DISCOVERY_ENDPOINTS.get(provider_id, ()))
    if base_url:
        base = base_url.rstrip("/")
        urls.append(f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models")
    seen: set[str] = set()
    ordered: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def _http_get_json(url: str, api_key: str, timeout: float) -> object | None:
    """GET autenticado que devuelve el JSON parseado, o ``None`` ante cualquier fallo."""
    req = urllib.request.Request(  # noqa: S310 - URLs fijas de providers, no input de usuario
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "x-api-key": api_key,
            "Accept": "application/json",
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.debug("Fetch de modelos fallo para %s: %s", url, exc)
        return None


def _parse_models(payload: object) -> list[ModelEntry]:
    """Extrae ``[(id, created)]`` de un payload de /models de cualquier shape comun.

    Soporta Anthropic/OpenAI (``{"data": [...]}``), bigmodel (``{"models": [...]}``),
    y lista cruda. Cada item puede ser dict (con ``id``/``created``) o string.
    """
    if isinstance(payload, dict):
        raw = payload.get("data") or payload.get("models") or payload.get("result")
    else:
        raw = payload
    if not isinstance(raw, list):
        return []
    return _normalize_entries(raw)


def probe_model_serves(
    base_url: str,
    api_key: str,
    model_id: str,
    timeout: float = _VALIDATE_TIMEOUT_SECONDS,
) -> bool | None:
    """Verifica que el endpoint de messages realmente SIRVA un modelo listado.

    Bug 2026-06-30/07-10 (minimax): ``/v1/models`` listaba ``MiniMax-M3`` pero
    ``/v1/messages`` lo rechazaba con ``400 "modelo mal escrito"`` (rollout a
    medias del lado del provider). Como el resolver elige "el mas nuevo por
    version", ese id envenenaba el cache compartido y rompia el eslabon de la
    cascada de failover. Listar un modelo NO garantiza poder servirlo: este
    probe minimo (1 mensaje, ``max_tokens=32``) lo confirma antes de cachear.

    Args:
        base_url: URL base anthropic-compatible del provider.
        api_key: API key para autenticar el probe.
        model_id: Id de modelo candidato a validar.
        timeout: Timeout del probe en segundos.

    Returns:
        ``True`` si el modelo responde 200; ``False`` si el endpoint lo rechaza
        con un 4xx de request invalido (400/422 = listado pero no servible);
        ``None`` si no se pudo determinar (red caida, 5xx, 401/403, endpoint
        inexistente) — el caller debe fail-open y aceptar el candidato.
    """
    if not base_url or not api_key or not model_id:
        return None
    base = base_url.rstrip("/")
    url = f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"
    body = json.dumps(
        {
            "model": model_id,
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "ping"}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 - URLs fijas de providers, no input de usuario
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):  # noqa: S310
            return True
    except urllib.error.HTTPError as exc:
        # Solo 400/422 delatan "modelo listado pero no servible". Un 404 puede
        # ser el endpoint (wire openai) y no el modelo; 401/403/5xx no dicen
        # nada del modelo -> indeterminado (fail-open).
        if exc.code in (400, 422):
            logger.warning(
                "Modelo %s listado pero rechazado por %s (HTTP %d)", model_id, url, exc.code
            )
            return False
        return None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _validated_best(
    remote: Sequence[object],
    family: str,
    base_url: str,
    api_key: str,
) -> str | None:
    """Elige el "mejor" id remoto que ADEMAS pase el probe de servicio.

    Recorre los candidatos newest-first (mismo orden que ``best_entry``) y
    devuelve el primero que el endpoint de messages acepte. Un probe
    indeterminado (``None``) acepta el candidato (fail-open: no castigar por
    problemas de red). Con la validacion deshabilitada
    (``ANTIGRAVITY_DISABLE_MODEL_VALIDATE=1``) equivale a ``best_entry``.

    Args:
        remote: Entradas descubiertas del provider.
        family: Prefijo de familia para filtrar/ordenar.
        base_url: URL base para el probe.
        api_key: API key para el probe.

    Returns:
        El id validado (o el mejor sin validar si el kill switch esta activo),
        ``None`` si ningun candidato pasa.
    """
    if _truthy(os.environ.get("ANTIGRAVITY_DISABLE_MODEL_VALIDATE")):
        return best_entry(remote, family)
    candidates = _display_ids(remote, family)[:_VALIDATE_MAX_CANDIDATES]
    for candidate in candidates:
        verdict = probe_model_serves(base_url, api_key, candidate)
        if verdict is None or verdict:
            return candidate
    return None


def fetch_remote_models(
    provider_id: str,
    base_url: str,
    api_key: str,
    timeout: float = _FETCH_TIMEOUT_SECONDS,
) -> list[ModelEntry]:
    """Descubre los modelos del provider probando varios endpoints candidatos.

    Best-effort: prueba en orden los hosts/paths de ``_DISCOVERY_ENDPOINTS`` (mas el
    ``{base_url}/v1/models``) y devuelve las entradas del PRIMERO que liste algo.
    Ante cualquier error devuelve ``[]`` para que el caller caiga al fallback.

    Args:
        provider_id: Id del provider (``minimax``, ``zai``, ...).
        base_url: URL base anthropic-compatible (se prueba tambien como ultimo recurso).
        api_key: API key para autenticar el listado.
        timeout: Timeout por request en segundos.

    Returns:
        Lista de ``(id, created_epoch|None)``, o ``[]`` si ningun endpoint respondio.
    """
    for url in _candidate_urls(provider_id.strip().lower(), base_url):
        payload = _http_get_json(url, api_key, timeout)
        if payload is None:
            continue
        entries = _parse_models(payload)
        if entries:
            logger.info("Modelos de %s descubiertos via %s (%d)", provider_id, url, len(entries))
            return entries
    return []


# ── API publica ──────────────────────────────────────────────────────────────


def resolve_default_model(
    provider_id: str,
    *,
    known_models: tuple[str, ...] | list[str],
    fallback: str,
    base_url: str = "",
    api_key: str | None = None,
    family: str = "",
) -> str:
    """Resuelve el modelo por defecto "mejor" (mas nuevo) de un provider.

    Aplica la cascada override -> cache -> fetch remoto -> fallback estatico.
    Nunca lanza: ante cualquier fallo devuelve un modelo valido del fallback.

    Args:
        provider_id: Id del provider (``minimax``, ``zai``, ...).
        known_models: Lista conocida (hint/fallback). El mas nuevo se usa si no
            hay cache ni red.
        fallback: Modelo de ultimo recurso si ``known_models`` esta vacia.
        base_url: URL base del provider para el fetch (vacio = sin fetch).
        api_key: API key para el fetch (None = sin fetch).
        family: Prefijo de familia para filtrar/ordenar (p. ej. ``MiniMax``, ``glm``).

    Returns:
        El id del modelo elegido.
    """
    pid = provider_id.strip().lower()

    # 1. Override explicito por env var (gana siempre, sin red).
    override = os.environ.get(f"ANTIGRAVITY_{pid.upper()}_MODEL")
    if override and override.strip():
        logger.info("Modelo de %s fijado por override: %s", pid, override.strip())
        return override.strip()

    # 2. Cache fresco.
    cache = _read_cache()
    entry = cache.get(pid)
    if isinstance(entry, dict) and _cache_fresh(entry):
        return str(entry["best"])

    # 3. Fetch remoto best-effort multi-endpoint (salvo offline o sin credenciales).
    offline = _truthy(os.environ.get("ANTIGRAVITY_DISABLE_MODEL_FETCH"))
    if not offline and api_key:
        remote = fetch_remote_models(pid, base_url, api_key)
        # Validar que el "mejor" listado se pueda SERVIR antes de cachearlo:
        # un id listado-pero-rechazado envenena el cache compartido y rompe
        # la cascada de failover (bug minimax MiniMax-M3 2026-06-30/07-10).
        best = _validated_best(remote, family, base_url, api_key)
        if best:
            cache[pid] = {
                "best": best,
                # Lista display-ready (filtrada por familia, newest-first): la
                # consumen `resolve_models` y la capa Rust de Nexus tal cual.
                "models": _display_ids(remote, family),
                "ts": time.time(),
            }
            _write_cache(cache)
            logger.info("Modelo de %s resuelto dinamicamente: %s", pid, best)
            return best

    # 4. Fallback estatico: el mas nuevo de la lista conocida.
    return latest_model(list(known_models), family) or fallback


def resolve_models(
    provider_id: str,
    *,
    known_models: tuple[str, ...] | list[str],
    base_url: str = "",
    api_key: str | None = None,
    family: str = "",
    allow_fetch: bool = True,
) -> list[str]:
    """Resuelve la lista de modelos de un provider (dinamica, no hardcodeada).

    Misma cascada que ``resolve_default_model`` pero para la LISTA completa:
    cache fresco -> fetch remoto (y cachea) -> lista conocida estatica. Nunca
    lanza: sin red/credenciales degrada a la lista conocida, asi las UIs
    (CLI ``models``, overview del gateway, dropdown de Nexus) siempre muestran
    algo y muestran lo REAL cuando el provider es alcanzable.

    Args:
        provider_id: Id del provider (``minimax``, ``zai``, ...).
        known_models: Lista conocida (fallback offline).
        base_url: URL base del provider para el fetch (vacio = sin fetch).
        api_key: API key para el fetch (None = sin fetch).
        family: Prefijo de familia para filtrar/ordenar.
        allow_fetch: ``False`` para contextos no bloqueantes (overview/UI):
            usa solo cache o estatica, jamas sale a la red.

    Returns:
        Ids ordenados newest-first; la lista conocida si no hay nada mejor.
    """
    pid = provider_id.strip().lower()

    # 1. Cache fresco compartido (lo escribe cualquiera de las dos cascadas).
    cache = _read_cache()
    entry = cache.get(pid)
    if isinstance(entry, dict) and _cache_fresh(entry):
        cached = entry.get("models")
        if isinstance(cached, list) and cached:
            ids = _display_ids(cached, family)
            if ids:
                return ids

    # 2. Fetch remoto best-effort (mismos kill-switches que el default).
    offline = _truthy(os.environ.get("ANTIGRAVITY_DISABLE_MODEL_FETCH"))
    if allow_fetch and not offline and api_key:
        remote = fetch_remote_models(pid, base_url, api_key)
        ids = _display_ids(remote, family)
        if ids:
            cache[pid] = {
                # El "best" cacheado lo consume la cascada de failover via
                # resolve_provider_model: validarlo aca tambien, o el id
                # envenenado reentra por el camino de la UI.
                "best": _validated_best(remote, family, base_url, api_key),
                "models": ids,
                "ts": time.time(),
            }
            _write_cache(cache)
            logger.info("Lista de modelos de %s resuelta dinamicamente (%d)", pid, len(ids))
            return ids

    # 3. Fallback estatico, mismo orden newest-first que el camino dinamico.
    return _display_ids(list(known_models), family) or list(known_models)


def write_provider_models_cache(provider_id: str, entries: list[tuple[str, bool]]) -> list[str]:
    """Persiste la lista enriquecida (id + flag free) de un provider en el cache.

    Escribe el shape ``{"best", "models": [{"id","free"}], "ts"}`` para ``provider_id``
    haciendo merge sobre el cache compartido (no pisa otros providers). ``best`` = primer
    modelo free, o el primer id si ninguno es free. Lo consume la capa Rust de Nexus para
    poblar el dropdown (free-primero) y el badge "free". El shape de ``models`` sigue
    siendo releible por ``resolve_models`` (``_normalize_entries`` tolera dicts con ``id``).

    Args:
        provider_id: Id del provider (``openrouter``, ``opencode``).
        entries: Lista ``(model_id, is_free)`` ya ordenada free-primero por el caller.

    Returns:
        Los ids escritos, en el orden recibido.
    """
    pid = provider_id.strip().lower()
    cache = _read_cache()
    ids = [mid for mid, _ in entries]
    free_ids = [mid for mid, free in entries if free]
    best = free_ids[0] if free_ids else (ids[0] if ids else "")
    cache[pid] = {
        "best": best,
        "models": [{"id": mid, "free": bool(free)} for mid, free in entries],
        "ts": time.time(),
    }
    _write_cache(cache)
    return ids
