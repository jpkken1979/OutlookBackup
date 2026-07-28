"""Estado mutable del backend IA activo del proxy de hot-swap.

El proxy del gateway relee este archivo en CADA request, de modo que cambiar
el backend no requiere reiniciar el gateway ni la sesion de Claude Code.

Ademas del backend activo (`provider`/`model`), el state puede llevar un bloque
`fallback` que registra el ultimo rescate automatico a Claude (cuando un provider
alternativo rechaza el turno). Ese bloque es informativo: lo escribe el gateway via
`record_fallback()` y lo lee el overview para avisarle al usuario. Un cambio de
backend deliberado (`set_active`) limpia el bloque.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path
from collections.abc import Generator

DEFAULT_PROVIDER = "claude"
DEFAULT_MODEL = "claude-sonnet-4-6"

# Clases de modelo que Claude Code usa: opus/sonnet/fable para el trabajo
# principal, haiku (small-fast) para tareas internas (titulos, resumenes,
# clasificaciones). Se matchea por substring del family name (sin version):
# "opus" cubre opus-4-8, opus-5, etc. — no hardcodear versiones aca.
VALID_MODEL_CLASSES = ("haiku", "sonnet", "opus", "fable")

# Env var de override del routing por clase. Acepta un spec
# ("haiku=zai:glm-4.5-air,sonnet=minimax") o "off" como kill switch.
CLASS_ROUTING_ENV = "ANTIGRAVITY_PROXY_CLASS_ROUTING"


def state_path() -> Path:
    """Path del archivo de estado (override por ANTIGRAVITY_PROXY_STATE).

    Returns:
        Ruta al JSON con el backend activo.
    """
    override = os.environ.get("ANTIGRAVITY_PROXY_STATE")
    if override:
        return Path(override)
    return Path.home() / ".antigravity" / "proxy" / "active_provider.json"


def _utc_now_iso() -> str:
    """Timestamp UTC en formato ISO-8601 segundos (sufijo Z)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── File lock cross-platform (sin fcntl/msvcrt) ──────────────────────────────
_LOCK_TIMEOUT_S = 2.0  # Tiempo maximo de espera para adquirir el lock.
_LOCK_STALE_S = 10.0  # Un lock mas viejo que esto se considera stale y se borra.
_LOCK_RETRY_SLEEP_S = 0.03  # 30ms entre reintentos (backoff fijo corto).


@contextmanager
def _state_lock() -> Generator[None, None, None]:
    """Adquiere un file lock exclusivo sobre ``active_provider.json``.

    Cross-platform (Windows + Linux) sin ``fcntl`` ni ``msvcrt``: usa
    ``O_CREAT | O_EXCL | O_WRONLY`` que es atomico en ambas plataformas.

    Recupera locks stale: si el ``.lock`` tiene mtime mas viejo que
    ``_LOCK_STALE_S``, lo borra y reintenta — evita deadlocks cuando un proceso
    murio mientras sostenia el lock.

    Raises:
        TimeoutError: Si no se pudo adquirir el lock en ``_LOCK_TIMEOUT_S`` s.
    """
    lock_path = Path(str(state_path()) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + _LOCK_TIMEOUT_S
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            # Lock adquirido: cerramos el fd de inmediato (solo necesitamos existencia).
            os.close(fd)
            fd = None
            break
        except OSError:
            # El archivo ya existe: verificar si es stale.
            try:
                mtime = lock_path.stat().st_mtime
                if time.time() - mtime > _LOCK_STALE_S:
                    try:
                        lock_path.unlink()
                    except OSError:
                        pass
                    continue
            except OSError:
                pass  # El lock desapareció entre el open y el stat, reintentar.
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"No se pudo adquirir el lock de proxy_state en {_LOCK_TIMEOUT_S}s: {lock_path}"
                )
            time.sleep(_LOCK_RETRY_SLEEP_S)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass  # Tolerante: ya no existe (poco probable pero no debe levantar).


def _read_raw() -> dict:
    """Lee el JSON crudo del state tolerando ausencia/corrupcion (devuelve {})."""
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _atomic_write(path: Path, payload: dict | list) -> None:
    """Escribe el payload JSON de forma atomica (tmp + os.replace).

    Args:
        path: Destino del archivo de estado.
        payload: Diccionario o lista serializable a persistir.
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


def get_active() -> dict:
    """Devuelve el backend activo.

    Returns:
        Dict {'provider': str, 'model': str}; default claude si falta o esta corrupto.
        No incluye el bloque `fallback` (usar `get_fallback()` para eso) para
        preservar compatibilidad con los consumidores del hot-path.
    """
    data = _read_raw()
    if not data:
        return {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL}
    provider = str(data.get("provider") or DEFAULT_PROVIDER)
    model = str(data.get("model") or DEFAULT_MODEL)
    return {"provider": provider, "model": model}


def set_active(provider: str, model: str) -> dict:
    """Escribe el backend activo de forma atomica (cambio deliberado).

    Sobreescribe el state completo, por lo que LIMPIA cualquier bloque `fallback`
    previo: un switch explicito de backend resetea el historial de rescates.

    Args:
        provider: id del backend (claude | zai | ...).
        model: modelo a usar con ese backend.

    Returns:
        El estado nuevo persistido.
    """
    with _state_lock():
        payload = {"provider": provider, "model": model}
        _atomic_write(state_path(), payload)
    return payload


def get_fallback() -> dict | None:
    """Devuelve el bloque del ultimo fallback automatico, o None si no hay.

    Returns:
        Dict {'from', 'reason', 'count', 'at'} con el ultimo rescate a Claude,
        o None si nunca hubo fallback o se limpio con un switch manual.
    """
    fb = _read_raw().get("fallback")
    return fb if isinstance(fb, dict) else None


def record_fallback(
    from_provider: str,
    reason: str,
    *,
    switch_to: tuple[str, str] | None = None,
) -> dict:
    """Registra un rescate automatico a Claude en el state.

    Por default NO cambia el backend activo (no-sticky): el proximo prompt reintenta
    el provider elegido por el usuario. Si `switch_to=(provider, model)`, ademas
    conmuta el backend (modo sticky opt-in, comportamiento historico).

    Incrementa el contador de fallbacks consecutivos cuando el `from_provider`
    coincide con el del bloque previo; si cambia, reinicia el contador en 1.

    Args:
        from_provider: Provider que rechazo el turno y motivo el rescate.
        reason: Razon legible del fallback (status, marker, etc.).
        switch_to: Si se pasa, (provider, model) al que conmutar el backend (sticky).

    Returns:
        El estado nuevo persistido (incluye el bloque 'fallback').
    """
    with _state_lock():
        current = _read_raw()
        provider = str(current.get("provider") or DEFAULT_PROVIDER)
        model = str(current.get("model") or DEFAULT_MODEL)

        prev = current.get("fallback")
        prev_count = 0
        if isinstance(prev, dict) and prev.get("from") == from_provider:
            try:
                prev_count = int(prev.get("count", 0))
            except (TypeError, ValueError):
                prev_count = 0

        if switch_to is not None:
            provider, model = switch_to[0], switch_to[1]

        payload = {
            "provider": provider,
            "model": model,
            "fallback": {
                "from": from_provider,
                "reason": reason,
                "count": prev_count + 1,
                "at": _utc_now_iso(),
            },
        }
        _atomic_write(state_path(), payload)
    return payload


# ── Routing por clase de modelo (haiku/sonnet/opus -> provider) ──────────────
#
# Claude Code manda DOS niveles de modelo: opus/sonnet para el trabajo principal
# y haiku (ANTHROPIC_SMALL_FAST_MODEL) para tareas internas baratas. El routing
# por clase permite partir el trafico: p. ej. haiku -> GLM (centavos) mientras
# opus sigue en Claude. Vive en un archivo SEPARADO del backend activo para que
# los hot-swaps (`set_active` sobreescribe el state completo) no lo pisen.


def routing_path() -> Path:
    """Path del archivo de routing por clase (junto al state del backend)."""
    return state_path().parent / "class_routing.json"


def detect_model_class(model_id: str | None) -> str | None:
    """Detecta la clase (haiku/sonnet/opus) de un id de modelo Anthropic.

    Args:
        model_id: Id de modelo pedido por Claude Code (p. ej. ``claude-haiku-4-5``).

    Returns:
        La clase detectada, o ``None`` si no es un modelo Claude clasificable.
    """
    if not model_id:
        return None
    lowered = model_id.lower()
    for cls in VALID_MODEL_CLASSES:
        if cls in lowered:
            return cls
    return None


def parse_routing_spec(spec: str) -> dict[str, dict]:
    """Parsea un spec de routing tipo ``haiku=zai:glm-4.5-air,sonnet=minimax``.

    Args:
        spec: Entradas ``clase=provider[:modelo]`` separadas por coma. Entradas
            malformadas o con clase desconocida se ignoran (tolerante).

    Returns:
        Dict ``{clase: {"provider": str, "model": str | None}}``.
    """
    routing: dict[str, dict] = {}
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        cls, _, target = chunk.partition("=")
        cls = cls.strip().lower()
        if cls not in VALID_MODEL_CLASSES or not target.strip():
            continue
        provider, _, model = target.strip().partition(":")
        if not provider.strip():
            continue
        routing[cls] = {
            "provider": provider.strip().lower(),
            "model": model.strip() or None,
        }
    return routing


def get_class_routing() -> dict[str, dict]:
    """Devuelve el routing por clase activo (el proxy lo relee en cada request).

    Precedencia: env ``ANTIGRAVITY_PROXY_CLASS_ROUTING`` (spec, u ``off`` como
    kill switch) -> archivo ``class_routing.json`` -> vacio (sin routing).

    Returns:
        Dict ``{clase: {"provider": str, "model": str | None}}``; vacio si no hay.
    """
    env_spec = os.environ.get(CLASS_ROUTING_ENV, "").strip()
    if env_spec:
        if env_spec.lower() in {"0", "off", "false", "no"}:
            return {}
        return parse_routing_spec(env_spec)

    try:
        data = json.loads(routing_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    routing: dict[str, dict] = {}
    for cls, entry in data.items():
        if cls in VALID_MODEL_CLASSES and isinstance(entry, dict) and entry.get("provider"):
            routing[cls] = {
                "provider": str(entry["provider"]).lower(),
                "model": str(entry["model"]) if entry.get("model") else None,
            }
    return routing


def set_class_route(model_class: str, provider: str, model: str | None = None) -> dict:
    """Setea (merge) una ruta de clase y la persiste de forma atomica.

    Args:
        model_class: Clase a rutear (``haiku`` | ``sonnet`` | ``opus``).
        provider: Backend destino (``claude`` | ``minimax`` | ``zai``).
        model: Modelo a usar en el destino; ``None`` = default del provider.

    Returns:
        El routing completo persistido.

    Raises:
        ValueError: clase desconocida.
    """
    cls = model_class.strip().lower()
    if cls not in VALID_MODEL_CLASSES:
        raise ValueError(f"Clase desconocida: {model_class} (validas: {VALID_MODEL_CLASSES})")
    # Merge contra el ARCHIVO (no contra get_class_routing): un override transitorio
    # por env no debe colarse en lo persistido.
    try:
        raw = json.loads(routing_path().read_text(encoding="utf-8"))
        routing = raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        routing = {}
    routing[cls] = {"provider": provider.strip().lower(), "model": model or None}
    _atomic_write(routing_path(), routing)
    return routing


# ── Shadow mode (A/B testing pasivo) ─────────────────────────────────────────
#
# Con shadow ON, los turnos servidos por Claude se duplican en paralelo hacia
# el provider alternativo configurado y ambas respuestas se registran en
# `shadow_log.jsonl` para comparar calidad con datos propios. ON/OFF simple:
# el proxy relee este estado en cada request, apagar vuelve al modo normal
# al instante (cero costo extra cuando esta off).
#
# `sample_rate` (0-100): fraccion de turnos elegibles a sombrear (muestreo
# probabilistico por turno en el proxy). 100 = comportamiento historico
# (sombrear el 100%); valores menores reducen el costo de tokens dobles.

SHADOW_DEFAULT_SAMPLE_RATE = 100


def _clamp_sample_rate(value: object) -> int:
    """Normaliza un sample_rate a entero en el rango [0, 100].

    Args:
        value: Valor crudo (int/float/str) leido del state o de un caller.

    Returns:
        Entero saturado a [0, 100]; ``SHADOW_DEFAULT_SAMPLE_RATE`` si no es
        numerico (tolerante a state corrupto o ausente).
    """
    try:
        if not isinstance(value, (str, bytes, bytearray, float, int)):
            return SHADOW_DEFAULT_SAMPLE_RATE
        rate = int(value)
    except (TypeError, ValueError):
        return SHADOW_DEFAULT_SAMPLE_RATE
    return max(0, min(100, rate))


def shadow_path() -> Path:
    """Path del estado del shadow mode (junto al state del backend)."""
    return state_path().parent / "shadow.json"


def get_shadow() -> dict:
    """Devuelve el estado del shadow mode.

    Returns:
        Dict ``{"enabled": bool, "provider": str, "model": str | None,
        "sample_rate": int}``; deshabilitado (con sample_rate default) si el
        archivo falta o esta corrupto.
    """
    try:
        data = json.loads(shadow_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "enabled": False,
            "provider": "",
            "model": None,
            "sample_rate": SHADOW_DEFAULT_SAMPLE_RATE,
        }
    if not isinstance(data, dict) or not data.get("enabled") or not data.get("provider"):
        return {
            "enabled": False,
            "provider": "",
            "model": None,
            "sample_rate": SHADOW_DEFAULT_SAMPLE_RATE,
        }
    return {
        "enabled": True,
        "provider": str(data["provider"]).lower(),
        "model": str(data["model"]) if data.get("model") else None,
        "sample_rate": _clamp_sample_rate(data.get("sample_rate", SHADOW_DEFAULT_SAMPLE_RATE)),
    }


def set_shadow(
    enabled: bool,
    provider: str = "",
    model: str | None = None,
    sample_rate: int | None = None,
) -> dict:
    """Activa o desactiva el shadow mode de forma atomica.

    Args:
        enabled: ``True`` para activar, ``False`` para volver al modo normal.
        provider: Backend alternativo a sombrear (requerido si ``enabled``).
        model: Modelo en el shadow; ``None`` = default del provider.
        sample_rate: Fraccion (0-100) de turnos elegibles a sombrear. ``None``
            preserva el sample_rate persistido (o el default si no habia).

    Returns:
        El estado persistido.
    """
    if sample_rate is None:
        # Preserva el rate actual; si no hay state previo cae al default.
        prev = get_shadow()
        rate = _clamp_sample_rate(prev.get("sample_rate", SHADOW_DEFAULT_SAMPLE_RATE))
    else:
        rate = _clamp_sample_rate(sample_rate)
    payload = {
        "enabled": bool(enabled),
        "provider": provider.strip().lower() if enabled else "",
        "model": model or None,
        "sample_rate": rate,
        "at": _utc_now_iso(),
    }
    _atomic_write(shadow_path(), payload)
    return payload


def failover_path() -> Path:
    """Path del estado del auto-failover en cascada (junto al state del backend)."""
    return state_path().parent / "failover.json"


def get_failover() -> dict:
    """Devuelve el estado persistido del auto-failover automático.

    Returns:
        Dict ``{"enabled": bool}``; deshabilitado si el archivo falta o esta corrupto.
    """
    try:
        data = json.loads(failover_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"enabled": False}
    if not isinstance(data, dict):
        return {"enabled": False}
    return {"enabled": bool(data.get("enabled"))}


def set_failover(enabled: bool) -> dict:
    """Activa o desactiva el auto-failover de forma atomica (Nexus lo prende en caliente).

    Args:
        enabled: ``True`` para activar la rotacion automatica en cascada.

    Returns:
        El estado persistido.
    """
    payload = {"enabled": bool(enabled), "at": _utc_now_iso()}
    _atomic_write(failover_path(), payload)
    return payload


# ── Circuit breaker (persistencia) ───────────────────────────────────────────
#
# El breaker del proxy vive en memoria del gateway (hot path), pero su estado se
# persiste aca para (a) sobrevivir restarts del gateway sin volver a pagar
# timeouts contra un backend caido, y (b) que Nexus / `provider_switch status`
# puedan mostrarle al usuario POR QUE sus turnos estan yendo a Claude.
# Formato: {provider: {"streak": int, "last_failure_epoch": float,
#                      "last_failure_at": iso}}.


def circuit_path() -> Path:
    """Path del estado persistido del circuit breaker (junto al state del backend)."""
    return state_path().parent / "circuit_breaker.json"


def get_circuit() -> dict[str, dict]:
    """Devuelve el estado persistido del breaker, tolerando ausencia/corrupcion.

    Returns:
        Dict ``{provider: {"streak", "last_failure_epoch", "last_failure_at"}}``;
        vacio si el archivo falta, esta corrupto o no tiene entradas validas.
    """
    try:
        data = json.loads(circuit_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    state: dict[str, dict] = {}
    for provider, entry in data.items():
        if not isinstance(entry, dict):
            continue
        try:
            streak = int(entry.get("streak", 0))
            epoch = float(entry.get("last_failure_epoch", 0.0))
        except (TypeError, ValueError):
            continue
        if streak <= 0:
            continue
        state[str(provider)] = {
            "streak": streak,
            "last_failure_epoch": epoch,
            "last_failure_at": str(entry.get("last_failure_at", "")),
        }
    return state


def save_circuit(state: dict[str, dict]) -> None:
    """Persiste el estado del breaker de forma atomica.

    Args:
        state: Estado completo a persistir (mismo formato que ``get_circuit``).
    """
    _atomic_write(circuit_path(), state)


def clear_circuit() -> None:
    """Borra el estado persistido del breaker (reset explicito / tests)."""
    try:
        circuit_path().unlink()
    except OSError:
        pass


# ── Eventos de auto-recovery (ring persistente) ──────────────────────────────
#
# El proxy toma decisiones autonomas (pre-compactar historial, fallback a
# Claude, abrir circuito) que antes solo dejaban contadores en memoria del
# gateway. Este ring persiste los ultimos N eventos para que el overview y
# Nexus puedan mostrar QUE hizo el proxy y CUANDO, sobreviviendo restarts.

RECOVERY_EVENTS_MAX = 20


def events_path() -> Path:
    """Path del ring de eventos de recovery (junto al state del backend)."""
    return state_path().parent / "recovery_events.json"


def record_recovery_event(event: str, provider: str | None = None, detail: str = "") -> None:
    """Appendea un evento de recovery al ring persistente (best-effort).

    Conserva solo los ultimos ``RECOVERY_EVENTS_MAX`` eventos. Jamas levanta:
    cualquier error de I/O se ignora — esto corre en el camino de error del
    proxy y no debe agregar fallos propios.

    Args:
        event: Nombre del evento (p. ej. ``precompact_alt_provider``).
        provider: Provider involucrado, si aplica.
        detail: Detalle corto legible (opcional).
    """
    try:
        try:
            raw = json.loads(events_path().read_text(encoding="utf-8"))
            events = raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError):
            events = []
        events.append(
            {
                "event": str(event),
                "provider": str(provider or ""),
                "detail": str(detail)[:200],
                "at": _utc_now_iso(),
            }
        )
        _atomic_write(events_path(), events[-RECOVERY_EVENTS_MAX:])
    except OSError:
        pass


def get_recovery_events(limit: int = RECOVERY_EVENTS_MAX) -> list[dict]:
    """Devuelve los ultimos eventos de recovery (mas reciente al final).

    Args:
        limit: Cantidad maxima de eventos a devolver.

    Returns:
        Lista de eventos ``{"event", "provider", "detail", "at"}``; vacia si
        el archivo falta o esta corrupto.
    """
    try:
        raw = json.loads(events_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    events = [e for e in raw if isinstance(e, dict) and e.get("event")]
    return events[-max(1, limit) :]


def clear_recovery_events() -> None:
    """Borra el ring de eventos (tests / mantenimiento)."""
    try:
        events_path().unlink()
    except OSError:
        pass


def clear_class_routes(model_class: str | None = None) -> dict:
    """Borra una ruta de clase (o todas) y persiste.

    Args:
        model_class: Clase puntual a borrar; ``None`` borra todo el routing.

    Returns:
        El routing restante persistido.
    """
    if model_class is None:
        _atomic_write(routing_path(), {})
        return {}
    try:
        raw = json.loads(routing_path().read_text(encoding="utf-8"))
        routing = raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        routing = {}
    routing.pop(model_class.strip().lower(), None)
    _atomic_write(routing_path(), routing)
    return routing
