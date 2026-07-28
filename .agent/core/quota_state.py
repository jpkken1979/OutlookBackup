"""Estado persistido de cuota por provider IA (señal del auto-rotate por umbral).

El proxy del gateway necesita saber CUÁNTA cuota le queda a cada provider para
decidir si rotar proactivamente ANTES de chocar contra un 429. Esa señal vive acá,
en ``~/.antigravity/proxy/quota_state.json``, y la alimentan dos fuentes:

- **poll**: ``core.usage_poller`` consulta periódicamente los endpoints de uso de
  cada provider (Claude OAuth, z.ai, MiniMax) y escribe el % restante.
- **header**: el proxy captura en caliente los headers
  ``anthropic-ratelimit-unified-remaining`` / ``-limit`` de las respuestas del
  provider activo (señal real-time, sin polling).

El predicado de rotación (``_quota_below_threshold`` en ``_mixin_proxy``) lee este
estado. Escritura atómica (tmp + ``os.replace``) imitando ``proxy_state``. Tolera
archivo ausente/corrupto devolviendo estado vacío — la feature es opt-in y jamás
debe romper el flujo del proxy.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, UTC
from pathlib import Path


def quota_state_path() -> Path:
    """Path del archivo de estado de cuota (override por ``ANTIGRAVITY_PROXY_QUOTA_STATE``).

    Returns:
        Ruta al JSON con la cuota restante por provider.
    """
    override = os.environ.get("ANTIGRAVITY_PROXY_QUOTA_STATE")
    if override:
        return Path(override)
    return Path.home() / ".antigravity" / "proxy" / "quota_state.json"


def _utc_now_iso() -> str:
    """Timestamp UTC en formato ISO-8601 segundos (sufijo Z)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, payload: dict) -> None:
    """Escribe el payload JSON de forma atómica (tmp + ``os.replace``).

    Args:
        path: Destino del archivo de estado.
        payload: Diccionario serializable a persistir.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_quota_state() -> dict:
    """Lee el estado de cuota completo, tolerando ausencia/corrupción.

    Returns:
        Dict ``{"providers": {<id>: {...}}, "updated_at": str}``; estructura vacía
        (``{"providers": {}}``) si el archivo falta o está corrupto.
    """
    try:
        data = json.loads(quota_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"providers": {}}
    if not isinstance(data, dict):
        return {"providers": {}}
    providers = data.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    result: dict = {"providers": providers, "updated_at": str(data.get("updated_at", ""))}
    rotations = data.get("rotations")
    if isinstance(rotations, dict):
        result["rotations"] = rotations
    threshold_pct = data.get("threshold_pct")
    if isinstance(threshold_pct, (int, float)) and not isinstance(threshold_pct, bool):
        result["threshold_pct"] = float(threshold_pct)
    return result


def write_provider_quota(
    provider: str,
    remaining_percent: float | None,
    used_percent: float | None = None,
    resets_at: str | None = None,
    window: str | None = None,
    source: str = "poll",
    error: str | None = None,
) -> dict:
    """Persiste (merge) la cuota de UN provider de forma atómica.

    Hace merge contra el estado existente: actualizar un provider no borra a los
    demás. Si ``used_percent`` no se pasa pero sí ``remaining_percent``, se deriva
    como ``100 - remaining_percent`` (y viceversa).

    Args:
        provider: Id del provider (``claude`` | ``zai`` | ``minimax`` | ``ollama``).
        remaining_percent: % de cuota restante (0-100), o ``None`` si desconocido.
        used_percent: % usado (0-100); derivado de ``remaining_percent`` si falta.
        resets_at: Timestamp ISO de reseteo de la ventana, si se conoce.
        window: Nombre de la ventana (p. ej. ``five_hour`` / ``weekly``).
        source: Origen de la señal (``poll`` | ``header`` | ``local``).
        error: Mensaje de error si el fetch falló (cuota queda desconocida).

    Returns:
        El estado completo persistido.
    """
    pid = provider.strip().lower()
    remaining = _clamp_percent(remaining_percent)
    used = _clamp_percent(used_percent)
    if used is None and remaining is not None:
        used = round(100.0 - remaining, 4)
    if remaining is None and used is not None:
        remaining = round(100.0 - used, 4)

    state = read_quota_state()
    providers = dict(state.get("providers", {}))
    providers[pid] = {
        "remaining_percent": remaining,
        "used_percent": used,
        "resets_at": resets_at,
        "window": window,
        "source": str(source),
        "updated_at": _utc_now_iso(),
        "error": error,
    }
    payload: dict = {"providers": providers, "updated_at": _utc_now_iso()}
    rotations = state.get("rotations")
    if isinstance(rotations, dict):
        payload["rotations"] = rotations
    threshold_pct = state.get("threshold_pct")
    if isinstance(threshold_pct, (int, float)) and not isinstance(threshold_pct, bool):
        payload["threshold_pct"] = threshold_pct
    _atomic_write(quota_state_path(), payload)
    return payload


def get_last_rotation(provider: str) -> float | None:
    """Devuelve el epoch (float) de la última rotación por cuota del provider, o ``None``.

    El cooldown anti-rebote del proxy persiste acá el timestamp de la última rotación
    para que sobreviva a un restart del gateway (el dict in-process se resetea).

    Args:
        provider: Id del provider.

    Returns:
        Epoch en segundos (float), o ``None`` si no hay registro o no es numérico.
    """
    rotations = read_quota_state().get("rotations")
    if not isinstance(rotations, dict):
        return None
    ts = rotations.get(provider.strip().lower())
    try:
        return float(ts) if ts is not None else None
    except (TypeError, ValueError):
        return None


def set_last_rotation(provider: str, ts: float) -> dict:
    """Persiste (merge atómico) el epoch de la última rotación por cuota del provider.

    Hace merge top-level sobre ``rotations`` sin pisar el map ``providers`` ni las
    rotaciones de otros providers.

    Args:
        provider: Id del provider que rotó.
        ts: Epoch en segundos (``time.time()``).

    Returns:
        El estado completo persistido.
    """
    pid = provider.strip().lower()
    state = read_quota_state()
    providers = state.get("providers", {})
    existing = state.get("rotations")
    rotations = dict(existing) if isinstance(existing, dict) else {}
    rotations[pid] = float(ts)
    payload: dict = {
        "providers": providers,
        "rotations": rotations,
        "updated_at": _utc_now_iso(),
    }
    threshold_pct = state.get("threshold_pct")
    if isinstance(threshold_pct, (int, float)) and not isinstance(threshold_pct, bool):
        payload["threshold_pct"] = threshold_pct
    _atomic_write(quota_state_path(), payload)
    return payload


_DEFAULT_THRESHOLD_PCT = 10.0


def get_threshold_pct() -> float:
    """Umbral de rotación por cuota persistido, o el default si falta.

    Lee el campo top-level ``threshold_pct`` de ``quota_state.json`` (seteado por
    Nexus). Tolerante a archivo ausente/corrupto y valor no numérico: devuelve el
    default. Clampa a ``[0, 100]`` para defenderse de escrituras malformadas.

    Returns:
        Umbral en ``[0, 100]``; ``10.0`` si el archivo/campo falta o está corrupto.
    """
    try:
        data = json.loads(quota_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_THRESHOLD_PCT
    if not isinstance(data, dict):
        return _DEFAULT_THRESHOLD_PCT
    result = _clamp_percent(data.get("threshold_pct"))
    return result if result is not None else _DEFAULT_THRESHOLD_PCT


def set_threshold_pct(value: float) -> dict:
    """Persiste (merge atómico) el umbral de rotación por cuota.

    Hace merge top-level sobre ``quota_state.json`` sin pisar ``providers`` ni
    ``rotations``. Clampa el valor a ``[0, 100]``: la validación de rango
    "amigable" (rechazar fuera de ``[1, 90]``) vive en la capa Rust/Nexus, acá
    solo se normaliza.

    Args:
        value: Umbral deseado (se clampa a ``[0, 100]``).

    Returns:
        El estado completo persistido.
    """
    clamped = _clamp_percent(float(value))
    if clamped is None:
        clamped = _DEFAULT_THRESHOLD_PCT
    state = read_quota_state()
    providers = state.get("providers", {})
    existing_rotations = state.get("rotations")
    payload: dict = {
        "providers": providers,
        "threshold_pct": clamped,
        "updated_at": _utc_now_iso(),
    }
    if isinstance(existing_rotations, dict):
        payload["rotations"] = existing_rotations
    _atomic_write(quota_state_path(), payload)
    return payload


_DEFAULT_QUOTA_TTL_SECONDS = 1800.0


def _quota_ttl_seconds() -> float:
    """TTL de staleness de una lectura de cuota (override ``ANTIGRAVITY_PROXY_QUOTA_TTL_SECONDS``).

    Returns:
        Segundos tras los cuales una entrada se considera vieja y se degrada a
        "desconocida" en vez de alimentar una decisión de rotación. Default 1800s
        (30min): margen amplio respecto del intervalo típico del poller, sin dejar
        que un poller caído (o un provider sin uso por horas) alimente el auto-rotate
        con un número stale. ``0`` desactiva el chequeo (compat histórico).
    """
    raw = os.environ.get("ANTIGRAVITY_PROXY_QUOTA_TTL_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_QUOTA_TTL_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _DEFAULT_QUOTA_TTL_SECONDS


def _entry_is_stale(entry: dict) -> bool:
    """True si ``entry["updated_at"]`` es más vieja que el TTL de staleness.

    Sin ``updated_at`` (entrada legacy o corrupta) no se puede juzgar antigüedad:
    se considera NO stale para no romper compatibilidad hacia atrás.
    """
    ttl = _quota_ttl_seconds()
    if ttl <= 0:
        return False
    updated_at = entry.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        return False
    try:
        stamp = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return False
    return (datetime.now(UTC) - stamp).total_seconds() > ttl


def get_remaining_percent(provider: str) -> float | None:
    """Devuelve el % de cuota restante de un provider, o ``None`` si se desconoce.

    Args:
        provider: Id del provider.

    Returns:
        Float en [0, 100], o ``None`` si no hay señal confiable: provider ausente,
        ``remaining_percent`` no numérico, o la entrada superó el TTL de staleness
        (``_entry_is_stale``) — un poller caído no debe seguir alimentando decisiones
        de rotación con un número de horas de antigüedad.

        Nota sobre ``error``: NO se usa para invalidar un ``remaining_percent``
        numérico ya presente. Algunos callers (p. ej. ``usage_poller.fetch_ollama``
        ante un backend caído) persisten deliberadamente ``remaining_percent=0.0``
        junto con ``error`` para señalar "confirmado sin capacidad" — 0% ya excluye
        al provider del auto-rotate via el umbral, y tratarlo como desconocido
        revertiría esa exclusión (un provider caído volvería a verse "disponible").
    """
    entry = read_quota_state().get("providers", {}).get(provider.strip().lower())
    if not isinstance(entry, dict):
        return None
    if _entry_is_stale(entry):
        return None
    return _clamp_percent(entry.get("remaining_percent"))


def _clamp_percent(value: object) -> float | None:
    """Normaliza un porcentaje a float en [0, 100], o ``None`` si no es numérico."""
    if value is None:
        return None
    try:
        pct = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, pct))
