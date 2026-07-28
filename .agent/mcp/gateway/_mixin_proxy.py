"""Gateway mixin — proxy de hot-swap del backend IA de Claude Code.

Claude Code apunta fijo a /claudeproxy/v1/messages. Este handler lee el backend
activo (proxy_state), sanea el payload (message_sanitizer), resuelve destino
(provider_router) y hace passthrough del streaming SSE Anthropic.

Seguridad: el path va en `public_paths` del gateway porque Claude Code no envia
la API key del gateway (envia el auth del provider). El gateway bindea a 127.0.0.1.
"""

from __future__ import annotations

from collections import defaultdict
import asyncio
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web

# core vive en .agent/core; este archivo en .agent/mcp/gateway/ -> parents[2] = .agent
_agent_dir = Path(__file__).resolve().parents[2]
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from core import (  # noqa: E402
    message_sanitizer,
    openai_translator,
    provider_cascade,
    provider_errors,
    provider_router,
    provider_switch,
    proxy_state,
    routing_authority,
)

_log = logging.getLogger("antigravity-gateway.claudeproxy")

_DEFAULT_PROXY_TIMEOUT_MS = 3_000_000
_MIN_PROXY_TIMEOUT_MS = 120_000
_COMPACT_HINT = (
    "El provider llego al limite. Ejecuta /compact o cambia de provider antes de reintentar."
)
_AUTO_FALLBACK_ENV = "ANTIGRAVITY_PROXY_AUTO_FALLBACK"
_AUTO_COMPACT_ENV = "ANTIGRAVITY_PROXY_AUTO_COMPACT"
_AUTO_COMPACT_MAX_MESSAGES_ENV = "ANTIGRAVITY_PROXY_AUTO_COMPACT_MAX_MESSAGES"
_AUTO_RECOVERY_MAX_RETRIES_ENV = "ANTIGRAVITY_PROXY_AUTO_RECOVERY_MAX_RETRIES"
_FALLBACK_STICKY_ENV = "ANTIGRAVITY_PROXY_FALLBACK_STICKY"
# Pre-compactacion PREVENTIVA para backends alternativos (minimax/zai/glm):
# recorta el historial ANTES de mandarlo al upstream cuando supera el umbral,
# en vez de esperar el 400 reactivo. Reduce los fallbacks por context-limit.
# Solo aplica a alternativos (nunca a Claude). Umbral generoso por defecto para
# tocar unicamente historiales extremos; configurable y desactivable.
_ALT_PRECOMPACT_ENV = "ANTIGRAVITY_PROXY_ALT_PRECOMPACT"
_ALT_PRECOMPACT_MAX_MESSAGES_ENV = "ANTIGRAVITY_PROXY_ALT_MAX_MESSAGES"
_FALLBACK_STATUSES = frozenset({400, 413, 422})
_SERVER_ERROR_FALLBACK_STATUSES = frozenset({500, 502, 503, 504})
_COUNT_TOKENS_FALLBACK_STATUSES = frozenset({400, 404, 405, 422, 500, 501, 502, 503, 504})
_DEFAULT_AUTO_COMPACT_MAX_MESSAGES = 12
_DEFAULT_ALT_PRECOMPACT_MAX_MESSAGES = 40
_DEFAULT_AUTO_RECOVERY_MAX_RETRIES = 2
# Markers de LIMITE DE CONTEXTO / TAMANO del payload: errores recuperables
# reenviando a Claude o compactando el contexto.
#
# Deliberadamente NO incluye markers genericos de error de request
# ("invalid_request_error", "invalid params", "unsupported", "content length"):
# esos suelen indicar un error de CONFIGURACION del provider alternativo (modelo
# mal escrito, parametro no soportado) y deben devolverse al usuario como el 400
# real, en vez de tragarse silenciosamente hacia Claude y enmascarar el problema.
_CONTEXT_LIMIT_MARKERS = (
    "context window",
    "context length",
    "context_length_exceeded",
    "model_context_window_exceeded",
    "maximum context",
    "maximum tokens",
    "prompt is too long",
    "input is too long",
    "too many tokens",
    "token limit",
    "payload too large",
    "request entity too large",
    "entity too large",
    "body too large",
    "too large",
)
_UPSTREAM_RATE_LIMIT_TOTAL: dict[str, int] = defaultdict(int)
_AUTO_RECOVERY_METRICS: dict[str, int] = defaultdict(int)
_AUTO_RECOVERY_BY_PROVIDER: dict[str, int] = defaultdict(int)
_CLASS_ROUTE_TOTAL: dict[str, int] = defaultdict(int)

# ── Shadow mode (A/B testing pasivo) ──────────────────────────────────────────
#
# Con shadow ON (proxy_state.get_shadow), los turnos servidos por Claude se
# duplican en paralelo al provider alternativo y AMBAS respuestas se registran
# en shadow_log.jsonl. El turno del usuario nunca se bloquea: el shadow corre
# fire-and-forget y sus errores solo quedan en el log. ON/OFF en caliente via
# `provider_switch.py shadow on|off` (el estado se relee en cada request).
_SHADOW_LOG_ENV = "ANTIGRAVITY_PROXY_SHADOW_LOG"
_SHADOW_LOG_MAX_MB_ENV = "ANTIGRAVITY_PROXY_SHADOW_LOG_MAX_MB"
_DEFAULT_SHADOW_LOG_MAX_MB = 10.0
_SHADOW_MAX_BODY_BYTES = 1_000_000  # payloads enormes no se sombrean (costo)
_SHADOW_TEXT_LIMIT = 4_000  # truncado de cada respuesta en el log
_SHADOW_PROMPT_LIMIT = 500
_SHADOW_TOTAL: dict[str, int] = defaultdict(int)

# Auto-disable: si la sombra encadena N fallos consecutivos, el shadow se apaga
# solo (set_shadow(False)) para dejar de gastar tokens y registrar errores contra
# un alternativo caido. Cada shadow_error no-vacio suma al streak del provider; un
# shadow exitoso (error vacio) lo resetea. Reactivar shadow manualmente (flanco
# off->on) tambien resetea el streak. Igual que el resto del shadow, jamas bloquea
# ni afecta el turno real: corre en el finalize fire-and-forget.
_SHADOW_MAX_FAILURES_ENV = "ANTIGRAVITY_PROXY_SHADOW_MAX_FAILURES"
_DEFAULT_SHADOW_MAX_FAILURES = 3
_SHADOW_FAILURE_STREAK: dict[str, int] = defaultdict(int)
# Providers con shadow visto habilitado en el ultimo plan: detecta el flanco
# off->on (reactivacion manual o tras auto-disable) para resetear el streak.
_SHADOW_ENABLED_SEEN: set[str] = set()

# Registro de referencias fuertes a las shadow tasks para evitar que el GC las
# recolecte antes de que terminen (Python 3.12+ garbage-collect tasks sin referencia).
_SHADOW_TASKS: set[asyncio.Task] = set()  # type: ignore[type-arg]


def _on_shadow_done(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Descarta la shadow task del registro y loggea cualquier excepcion no consumida.

    Args:
        task: La tarea shadow que acaba de completar o cancelar.
    """
    _SHADOW_TASKS.discard(task)
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        _log.warning("shadow finalize fallo: %s", exc)


def _shadow_log_path() -> Path:
    """Path del log JSONL de comparaciones shadow (override por env)."""
    override = os.environ.get(_SHADOW_LOG_ENV)
    if override:
        return Path(override)
    return Path.home() / ".antigravity" / "proxy" / "shadow_log.jsonl"


def _shadow_log_max_bytes() -> int:
    """Tope de tamano del shadow log antes de rotar (env en MB, clamp 0.001-500)."""
    raw = os.environ.get(_SHADOW_LOG_MAX_MB_ENV, str(_DEFAULT_SHADOW_LOG_MAX_MB))
    try:
        parsed = float(raw)
    except ValueError:
        parsed = _DEFAULT_SHADOW_LOG_MAX_MB
    return int(max(0.001, min(parsed, 500.0)) * 1024 * 1024)


def _rotate_shadow_log_if_needed(path: Path) -> None:
    """Rota el shadow log a ``<nombre>.1`` cuando supera el tope (una generacion).

    El log es diagnostico, no auditoria: una generacion de backup alcanza para
    inspeccionar comparaciones recientes sin crecer sin limite. Best-effort —
    cualquier ``OSError`` solo deja warning, el shadow jamas afecta el turno real.
    """
    try:
        if path.stat().st_size < _shadow_log_max_bytes():
            return
    except OSError:
        return  # no existe todavia o no se puede stat-ear: nada que rotar
    rotated = path.with_name(path.name + ".1")
    try:
        os.replace(path, rotated)
        _SHADOW_TOTAL["log_rotated"] += 1
        _log.info("shadow log rotado a %s (tope %d bytes)", rotated, _shadow_log_max_bytes())
    except OSError as exc:  # pragma: no cover - IO best-effort
        _log.warning("no se pudo rotar el shadow log: %s", exc)


def _extract_text_from_sse(raw: bytes) -> str:
    """Extrae el texto concatenado de un stream SSE Anthropic (text_delta)."""
    parts: list[str] = []
    for line in raw.split(b"\n"):
        if not line.startswith(b"data: "):
            continue
        try:
            event = json.loads(line[6:])
        except Exception:  # noqa: BLE001 — SSE puede traer [DONE]/no-JSON
            continue
        if not isinstance(event, dict) or event.get("type") != "content_block_delta":
            continue
        delta = event.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            parts.append(str(delta.get("text", "")))
    return "".join(parts)


def _extract_text_from_json_response(raw: bytes) -> str:
    """Extrae el texto de una respuesta Anthropic no-streaming (content blocks)."""
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001 — boundary HTTP
        return ""
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _last_user_prompt(payload: dict) -> str:
    """Devuelve (truncado) el ultimo mensaje user del payload, para contexto del log."""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content[:_SHADOW_PROMPT_LIMIT]
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return str(block.get("text", ""))[:_SHADOW_PROMPT_LIMIT]
    return ""


def _plan_shadow(provider: str, raw_body: bytes) -> dict | None:
    """Decide si este turno se sombrea y arma el plan (None = no sombrear).

    Condiciones: shadow ON, el turno lo sirve Claude (la comparacion es
    alternativo-vs-Claude), payload parseable y no gigante, clase no-haiku
    (las tareas internas son ruido), shadow provider proxy-compatible y con
    circuito cerrado (no sombrear contra un backend caido).
    """
    shadow = proxy_state.get_shadow()
    if not shadow["enabled"]:
        # Shadow OFF (manual o por auto-disable): olvidar los flancos vistos para
        # que la proxima reactivacion (off->on) resetee el streak desde cero.
        _SHADOW_ENABLED_SEEN.clear()
        return None
    _track_shadow_reenable(shadow["provider"])
    if provider != "claude":
        return None
    if len(raw_body) > _SHADOW_MAX_BODY_BYTES:
        _SHADOW_TOTAL["skipped_body_too_large"] += 1
        return None
    sh_provider = shadow["provider"]
    if sh_provider not in provider_switch.PROXY_COMPATIBLE or sh_provider == "claude":
        return None
    if _circuit_open(sh_provider):
        _SHADOW_TOTAL["skipped_circuit_open"] += 1
        return None
    try:
        payload = json.loads(raw_body)
    except Exception:  # noqa: BLE001 — boundary HTTP
        return None
    if not isinstance(payload, dict):
        return None
    requested = payload.get("model")
    if proxy_state.detect_model_class(requested if isinstance(requested, str) else None) == "haiku":
        _SHADOW_TOTAL["skipped_haiku"] += 1
        return None
    # Muestreo probabilistico por turno: con sample_rate < 100 solo se sombrea
    # esa fraccion de los turnos elegibles, para bajar el costo de tokens dobles.
    # 100 = comportamiento historico (sombrear todos). random.random() in [0,1).
    sample_rate = shadow.get("sample_rate", proxy_state.SHADOW_DEFAULT_SAMPLE_RATE)
    if sample_rate < 100 and random.random() * 100 >= sample_rate:
        _SHADOW_TOTAL["skipped_sampled_out"] += 1
        return None
    sh_model = shadow["model"] or provider_switch.resolve_provider_model(sh_provider)
    return {
        "provider": sh_provider,
        "model": sh_model,
        "payload": payload,
        "claude_model": str(requested or ""),
    }


async def _run_shadow(incoming_headers: dict, plan: dict) -> dict:
    """Ejecuta el request shadow (no-streaming) contra el provider alternativo."""
    start = time.monotonic()
    sanitized = message_sanitizer.sanitize_anthropic_payload(
        plan["payload"], plan["provider"], plan["model"]
    )
    sanitized["stream"] = False
    target = provider_router.resolve_target(plan["provider"], incoming_headers)
    async with ClientSession(timeout=_proxy_client_timeout()) as session:
        async with session.post(
            target["url"], headers=target["headers"], json=sanitized
        ) as upstream:
            body = await upstream.read()
            latency_ms = round((time.monotonic() - start) * 1000)
            text = _extract_text_from_json_response(body) if upstream.status == 200 else ""
            return {
                "status": upstream.status,
                "latency_ms": latency_ms,
                "text": text[:_SHADOW_TEXT_LIMIT],
                "error": "" if upstream.status == 200 else body.decode("utf-8", "ignore")[:500],
            }


async def _finalize_shadow(
    shadow_task: asyncio.Task[dict],
    tee_chunks: list[bytes],
    plan: dict,
    claude_latency_ms: int | None,
) -> None:
    """Espera el shadow, arma el registro de comparacion y lo appendea al JSONL."""
    try:
        result = await shadow_task
        _SHADOW_TOTAL["ok" if result.get("status") == 200 else "upstream_error"] += 1
    except Exception as exc:  # noqa: BLE001 — el shadow jamas afecta el turno real
        _SHADOW_TOTAL["error"] += 1
        result = {"status": -1, "latency_ms": None, "text": "", "error": str(exc)[:500]}

    # Auto-disable: contabiliza el resultado (exito resetea, fallo acumula) y apaga
    # el shadow si la sombra encadena demasiados fallos. Nunca afecta el turno real.
    _record_shadow_result(plan["provider"], str(result.get("error") or ""))

    record = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claude_model": plan["claude_model"],
        "claude_latency_ms": claude_latency_ms,
        "claude_text": _extract_text_from_sse(b"".join(tee_chunks))[:_SHADOW_TEXT_LIMIT],
        "shadow_provider": plan["provider"],
        "shadow_model": plan["model"],
        "shadow_status": result.get("status"),
        "shadow_latency_ms": result.get("latency_ms"),
        "shadow_text": result.get("text", ""),
        "shadow_error": result.get("error", ""),
        "prompt_tail": _last_user_prompt(plan["payload"]),
    }
    try:
        path = _shadow_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_shadow_log_if_needed(path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - IO best-effort
        _log.warning("no se pudo escribir el shadow log: %s", exc)


def _shadow_max_failures() -> int:
    """Fallos consecutivos de la sombra que disparan el auto-disable (clamp 1-50)."""
    raw = os.environ.get(_SHADOW_MAX_FAILURES_ENV, str(_DEFAULT_SHADOW_MAX_FAILURES))
    try:
        parsed = int(raw)
    except ValueError:
        parsed = _DEFAULT_SHADOW_MAX_FAILURES
    return max(1, min(parsed, 50))


def _record_shadow_result(provider: str, error: str) -> None:
    """Acumula el resultado del shadow y auto-desactiva tras N fallos seguidos.

    Un ``error`` no vacio cuenta como fallo (incrementa el streak del provider);
    un ``error`` vacio (shadow 200 OK) lo resetea. Al alcanzar el umbral
    configurable (``ANTIGRAVITY_PROXY_SHADOW_MAX_FAILURES``, default 3) se persiste
    el shadow a ``enabled=false``, se loguea un WARNING grepeable y se cuenta en las
    metricas. Best-effort: corre dentro del finalize fire-and-forget, nunca rompe el
    turno real.

    Args:
        provider: Provider alternativo (sombra) que produjo el resultado.
        error: Mensaje de error del shadow request; vacio si fue exitoso.
    """
    if not provider:
        return
    if not error:
        _SHADOW_FAILURE_STREAK[provider] = 0
        return
    _SHADOW_FAILURE_STREAK[provider] += 1
    streak = _SHADOW_FAILURE_STREAK[provider]
    threshold = _shadow_max_failures()
    if streak < threshold:
        return
    _SHADOW_TOTAL["auto_disabled"] += 1
    _SHADOW_FAILURE_STREAK[provider] = 0
    _log.warning(
        "shadow auto-disabled: provider=%s fallos=%d (umbral=%d)",
        provider,
        streak,
        threshold,
    )
    try:
        proxy_state.set_shadow(False)
    except OSError as exc:  # pragma: no cover - IO best-effort
        _log.warning("no se pudo persistir el auto-disable del shadow: %s", exc)


def _track_shadow_reenable(provider: str) -> None:
    """Detecta el flanco off->on del shadow y resetea el streak al reactivar.

    Tras un auto-disable (o un OFF manual) el usuario puede volver a encender
    shadow; en ese caso el contador previo de fallos no debe arrastrarse.
    ``_plan_shadow`` llama esto cuando el shadow esta habilitado: la primera vez
    que ve un provider habilitado (tras estar off) resetea su streak, dejando el
    primer turno sombreado tras reactivar en cero.

    Args:
        provider: Provider alternativo (sombra) configurado y habilitado.
    """
    if provider and provider not in _SHADOW_ENABLED_SEEN:
        _SHADOW_ENABLED_SEEN.add(provider)
        _SHADOW_FAILURE_STREAK[provider] = 0


def get_shadow_metrics() -> dict[str, Any]:
    """Contadores del shadow mode para el health endpoint."""
    return dict(_SHADOW_TOTAL)


# ── Retry transitorio del passthrough Claude ─────────────────────────────────
#
# Un blip 5xx/529 de api.anthropic.com en el passthrough claude tumba de rebote
# el clasificador de seguridad de auto mode de Claude Code ("temporarily
# unavailable" -> Bash/Write/Edit bloqueados aunque el chat siga vivo). Antes de
# devolver ese error al cliente, UN reintento con backoff corto absorbe el blip.
# Solo statuses de sobrecarga/transporte (nunca 4xx ni 429: reintentar un
# rate-limit a 1s solo quema cuota). Kill switch: ANTIGRAVITY_PROXY_CLAUDE_RETRY=0.
_CLAUDE_TRANSIENT_RETRY_STATUSES = frozenset({500, 502, 503, 504, 529})
_CLAUDE_TRANSIENT_RETRY_DELAY_S = 1.0
_CLAUDE_TRANSIENT_RETRY_ENV = "ANTIGRAVITY_PROXY_CLAUDE_RETRY"


def _claude_transient_retry_enabled() -> bool:
    """True si el retry transitorio del passthrough claude esta habilitado."""
    raw = os.environ.get(_CLAUDE_TRANSIENT_RETRY_ENV, "1").strip().lower()
    return raw not in {"0", "off", "false", "no"}


# ── Circuit breaker por provider ──────────────────────────────────────────────
#
# Si un backend alternativo encadena fallos de SALUD (429/5xx/errores de
# conexion), el proxy abre el circuito: deja de pegarle al upstream caido y va
# directo al fallback a Claude, sin pagar el timeout completo en cada turno.
# Pasado el cooldown el circuito queda half-open: el proximo request pasa como
# probe — si responde 200 el circuito se cierra (streak en 0), si falla se
# reabre. Los 400/413/422 NO cuentan: son problemas del payload, no del backend.
_CIRCUIT_ENV = "ANTIGRAVITY_PROXY_CIRCUIT"
_CIRCUIT_THRESHOLD_ENV = "ANTIGRAVITY_PROXY_CIRCUIT_THRESHOLD"
_CIRCUIT_COOLDOWN_ENV = "ANTIGRAVITY_PROXY_CIRCUIT_COOLDOWN_S"
_DEFAULT_CIRCUIT_THRESHOLD = 3
_DEFAULT_CIRCUIT_COOLDOWN_S = 60.0
_CIRCUIT_FAILURE_STATUSES = _SERVER_ERROR_FALLBACK_STATUSES
_FAILOVER_STATUSES = frozenset({429}) | _CIRCUIT_FAILURE_STATUSES
# Estado en memoria (hot path). last-failure en EPOCH (time.time(), no monotonic)
# para poder persistirlo entre procesos: el snapshot vive en circuit_breaker.json
# (proxy_state.circuit_path) y se recarga lazy tras un restart del gateway.
_CIRCUIT_STREAK: dict[str, int] = defaultdict(int)
_CIRCUIT_LAST_FAILURE: dict[str, float] = {}
_CIRCUIT_LOADED = False
_CIRCUIT_PERSIST_TTL_S = 24 * 3600.0  # entradas mas viejas se descartan al cargar

# ── Auto-rotate proactivo por cuota (Fase 1, opt-in) ─────────────────────────
#
# La señal de cuota restante por provider vive en quota_state.json (la alimentan
# el usage_poller y la captura passiva de headers). Si el provider activo cae por
# debajo del umbral, el proxy rota ANTES de chocar el 429 — reusando la misma
# cascada que el failover por circuito. Opt-in puro: solo dispara con el
# auto-failover activo (provider_cascade.is_auto_failover_enabled).
_QUOTA_THRESHOLD_ENV = "ANTIGRAVITY_PROXY_QUOTA_THRESHOLD_PCT"
_QUOTA_COOLDOWN_ENV = "ANTIGRAVITY_PROXY_QUOTA_COOLDOWN_S"
_QUOTA_RECOVERY_ENV = "ANTIGRAVITY_PROXY_QUOTA_RECOVERY_PCT"
_QUOTA_AUTO_RETURN_ENV = "ANTIGRAVITY_PROXY_QUOTA_AUTO_RETURN"
_DEFAULT_QUOTA_THRESHOLD_PCT = 10.0
_DEFAULT_QUOTA_COOLDOWN_S = 300.0
_DEFAULT_QUOTA_RECOVERY_PCT = 20.0
# Anti-rebote: timestamp (epoch) de la última rotación por cuota por provider.
_LAST_QUOTA_ROTATION: dict[str, float] = {}


def _quota_threshold_pct() -> float:
    """Umbral de % restante por debajo del cual se rota (editable en caliente).

    Precedencia:
      1. env ``ANTIGRAVITY_PROXY_QUOTA_THRESHOLD_PCT`` (override back-compat / CI).
      2. ``quota_state.json::threshold_pct`` (lo que setea la UI de Nexus).
      3. default ``10.0``.

    El env es la rama explícita: si está presente pero no parsea, cae al default del
    módulo (comportamiento heredado; no rescata el JSON). Si el env está ausente, se
    lee el estado persistido; si ese también falta/corrupto, default.

    Returns:
        Umbral en ``[0, 100]``.
    """
    raw = os.environ.get(_QUOTA_THRESHOLD_ENV)
    if raw is not None:
        # Env var está presente (aunque sea vacío/whitespace).
        # Si parsea, úsalo; si no, cae al default (no al JSON).
        try:
            return max(0.0, min(float(raw), 100.0))
        except ValueError:
            # Env presente pero no parseable (vacío, whitespace, o non-numeric).
            return max(0.0, min(_DEFAULT_QUOTA_THRESHOLD_PCT, 100.0))
    try:
        from core import quota_state

        return quota_state.get_threshold_pct()
    except Exception:  # noqa: BLE001 -- señal opcional, nunca rompe el proxy
        return _DEFAULT_QUOTA_THRESHOLD_PCT


def _quota_cooldown_s() -> float:
    """Segundos mínimos entre dos rotaciones por cuota del mismo provider (override env)."""
    raw = os.environ.get(_QUOTA_COOLDOWN_ENV, str(_DEFAULT_QUOTA_COOLDOWN_S))
    try:
        parsed = float(raw)
    except ValueError:
        parsed = _DEFAULT_QUOTA_COOLDOWN_S
    return max(0.0, min(parsed, 86400.0))


def _quota_recovery_pct() -> float:
    """% mínimo de cuota restante para VOLVER a un provider de mayor prioridad (histéresis).

    Solo se usa cuando ``ANTIGRAVITY_PROXY_QUOTA_AUTO_RETURN`` está activo. Se clampa a
    ``max(_quota_threshold_pct() + 1, valor)`` para garantizar la histéresis: volver
    siempre exige más cuota que la que disparó la rotación (rota al <umbral, vuelve
    solo al >recovery), aunque se mal-configure el env por debajo del umbral.

    Returns:
        Umbral de recuperación en [0, 100], nunca menor que ``umbral + 1``.
    """
    raw = os.environ.get(_QUOTA_RECOVERY_ENV, str(_DEFAULT_QUOTA_RECOVERY_PCT))
    try:
        parsed = float(raw)
    except ValueError:
        parsed = _DEFAULT_QUOTA_RECOVERY_PCT
    parsed = max(0.0, min(parsed, 100.0))
    return max(_quota_threshold_pct() + 1.0, parsed)


def _quota_auto_return_enabled() -> bool:
    """True si el proxy puede volver automáticamente a un provider de mayor prioridad."""
    raw = os.environ.get(_QUOTA_AUTO_RETURN_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _quota_remaining(provider: str) -> float | None:
    """% de cuota restante de un provider, o ``None`` si se desconoce (best-effort).

    Lectura envuelta en try/except: jamás debe romper el flujo del proxy.
    """
    try:
        from core import quota_state

        return quota_state.get_remaining_percent(provider)
    except Exception:  # noqa: BLE001 — señal opcional, nunca rompe el proxy
        return None


def _quota_below_threshold(provider: str) -> bool:
    """True si la cuota restante del provider es conocida y está bajo el umbral.

    Cuota desconocida (``None``) → False: no se rota a ciegas.

    Args:
        provider: Provider activo a evaluar.

    Returns:
        True si ``remaining_percent`` es numérico y ``< umbral``.
    """
    remaining = _quota_remaining(provider)
    return remaining is not None and remaining < _quota_threshold_pct()


def _persisted_last_rotation(provider: str) -> float | None:
    """Epoch persistido de la última rotación por cuota del provider, o ``None`` (best-effort).

    Sobrevive a un restart del gateway (el dict in-process se resetea). Lectura
    envuelta en try/except: la señal es opcional y jamás debe romper el proxy.
    """
    try:
        from core import quota_state

        return quota_state.get_last_rotation(provider)
    except Exception:  # noqa: BLE001 — señal opcional, nunca rompe el proxy
        return None


def _quota_in_cooldown(provider: str) -> bool:
    """True si el provider rotó por cuota hace menos de ``_quota_cooldown_s`` (anti-rebote).

    Considera el MÁXIMO entre el timestamp in-process y el persistido en disco, de modo
    que un restart del gateway no resetee el cooldown y re-rote al toque.
    """
    last = _LAST_QUOTA_ROTATION.get(provider, 0.0)
    persisted = _persisted_last_rotation(provider)
    if persisted is not None:
        last = max(last, persisted)
    return (time.time() - last) < _quota_cooldown_s()


def _mark_quota_rotation(provider: str) -> None:
    """Registra el timestamp de la rotación por cuota del provider (anti-rebote).

    Escribe AMBOS: el dict in-process (hot path) y el persistido en disco (best-effort,
    para que el cooldown sobreviva a un restart del gateway).
    """
    now = time.time()
    _LAST_QUOTA_ROTATION[provider] = now
    try:
        from core import quota_state

        quota_state.set_last_rotation(provider, now)
    except Exception:  # noqa: BLE001 — persistencia best-effort, nunca rompe el proxy
        pass


def _quota_available_providers(failed: str) -> set[str]:
    """Providers proxy-routables candidatos a recibir la rotación por cuota.

    Excluye el que disparó la rotación y a cualquiera cuya cuota esté también bajo
    el umbral (no rotar a un provider igual de agotado). Los de cuota desconocida se
    consideran disponibles (no hay evidencia de que estén bajos); ollama (local)
    siempre reporta 100%, así que es la red de seguridad final.

    Args:
        failed: Provider que disparó la rotación (se excluye).

    Returns:
        Set de provider ids elegibles como destino.
    """
    failed = failed.strip().lower()
    avail: set[str] = set()
    for pid in provider_switch.PROXY_ROUTABLE:
        if pid == failed:
            continue
        if _quota_below_threshold(pid):
            continue
        avail.add(pid)
    return avail


def _quota_rotation_target(provider: str) -> str | None:
    """Elige el destino de una rotación proactiva por cuota, o ``None`` si no rota.

    Devuelve ``None`` (no rotar) si: la cuota del provider no está bajo el umbral,
    está en cooldown anti-rebote, o no hay ningún destino con cuota OK en la cascada
    (todos igual de agotados). Reusa ``provider_cascade.next_healthy_provider`` para
    respetar la cascada y los circuitos abiertos.

    Args:
        provider: Provider activo a evaluar.

    Returns:
        El provider destino, o ``None`` para no rotar.
    """
    if not _quota_below_threshold(provider):
        return None
    if _quota_in_cooldown(provider):
        return None
    available = _quota_available_providers(provider)
    if not available:
        return None
    target = provider_cascade.next_healthy_provider(provider, _open_circuits(), available=available)
    if not target or target == provider:
        return None
    return target


def _quota_return_target(active_provider: str) -> str | None:
    """Elige un provider de MAYOR prioridad ya recuperado al que volver, o ``None``.

    Es el "upgrade" complementario al downgrade de ``_quota_rotation_target``: si estás
    en un provider alternativo y uno de mayor prioridad en la cascada se recuperó, vuelve
    a él. Recorre ``provider_cascade.get_cascade()`` EN ORDEN; para cada provider que
    aparece ANTES que ``active_provider`` (mayor prioridad) devuelve el PRIMERO que cumpla
    la histéresis: cuota conocida y ``>= _quota_recovery_pct()``, circuito cerrado, y NO en
    cooldown anti-rebote. Cuota desconocida (``None``) no es candidato: no se vuelve a
    ciegas. Si ``active_provider`` no está en la cascada o ya es el de mayor prioridad →
    ``None``.

    Args:
        active_provider: Provider activo del que se podría volver.

    Returns:
        El provider de mayor prioridad recuperado, o ``None`` si no hay a cuál volver.
    """
    active = active_provider.strip().lower()
    cascade = provider_cascade.get_cascade()
    if active not in cascade:
        return None
    opens = _open_circuits()
    recovery = _quota_recovery_pct()
    for pid in cascade:
        if pid == active:
            return None  # se llegó al activo sin candidato de mayor prioridad
        remaining = _quota_remaining(pid)
        if remaining is None or remaining < recovery:
            continue
        if pid in opens:
            continue
        if _quota_in_cooldown(pid):
            continue
        return pid
    return None


def _capture_quota_headers(provider: str, headers: Any) -> None:
    """Captura passiva del % de cuota restante desde los headers de rate-limit.

    Anthropic expone el remaining/limit unificado del plan en
    ``anthropic-ratelimit-unified-remaining`` / ``-limit``. Cuando ambos vienen, se
    calcula el % restante y se persiste como señal real-time del provider activo.
    Best-effort total: cualquier error (header ausente, no numérico, I/O) se traga —
    esto corre en el hot path del proxy y jamás debe romperlo.

    Args:
        provider: Provider que sirvió la respuesta (al que se le atribuye la cuota).
        headers: Mapping de headers de la respuesta upstream.
    """
    try:
        remaining = headers.get("anthropic-ratelimit-unified-remaining")
        limit = headers.get("anthropic-ratelimit-unified-limit")
        if remaining is None or limit is None:
            return
        rem = float(remaining)
        lim = float(limit)
        if lim <= 0:
            return
        pct = max(0.0, min(100.0, rem / lim * 100.0))
        reset = headers.get("anthropic-ratelimit-unified-reset")
        from core import quota_state

        quota_state.write_provider_quota(
            provider, remaining_percent=pct, resets_at=reset, source="header"
        )
    except Exception:  # noqa: BLE001 — captura passiva best-effort, nunca rompe el proxy
        pass


def _ensure_circuit_loaded() -> None:
    """Recarga (una vez por proceso) el estado persistido del breaker.

    Permite que un restart del gateway no vuelva a pagar timeouts contra un
    backend que ya venia caido. Entradas con mas de ``_CIRCUIT_PERSIST_TTL_S``
    se descartan (stale: el estado del backend ya no es representativo).
    """
    global _CIRCUIT_LOADED
    if _CIRCUIT_LOADED:
        return
    _CIRCUIT_LOADED = True
    now = time.time()
    for provider, entry in proxy_state.get_circuit().items():
        epoch = float(entry.get("last_failure_epoch", 0.0))
        if (now - epoch) >= _CIRCUIT_PERSIST_TTL_S:
            continue
        _CIRCUIT_STREAK[provider] = int(entry.get("streak", 0))
        _CIRCUIT_LAST_FAILURE[provider] = epoch
    if _CIRCUIT_STREAK:
        _log.info(
            "circuit breaker: estado restaurado desde disco (%s)",
            dict(_CIRCUIT_STREAK),
        )


def _persist_circuit() -> None:
    """Persiste el estado en memoria del breaker (best-effort, nunca rompe el proxy)."""
    state = {
        provider: {
            "streak": streak,
            "last_failure_epoch": _CIRCUIT_LAST_FAILURE.get(provider, 0.0),
            "last_failure_at": datetime.fromtimestamp(
                _CIRCUIT_LAST_FAILURE.get(provider, 0.0), UTC
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for provider, streak in _CIRCUIT_STREAK.items()
        if streak > 0
    }
    try:
        proxy_state.save_circuit(state)
    except OSError as exc:  # pragma: no cover - IO best-effort
        _log.warning("no se pudo persistir el estado del circuit breaker: %s", exc)


def _circuit_enabled() -> bool:
    """Indica si el circuit breaker esta activo (default si; kill switch por env)."""
    raw = os.environ.get(_CIRCUIT_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _circuit_threshold() -> int:
    """Fallos consecutivos necesarios para abrir el circuito."""
    raw = os.environ.get(_CIRCUIT_THRESHOLD_ENV, str(_DEFAULT_CIRCUIT_THRESHOLD))
    try:
        parsed = int(raw)
    except ValueError:
        parsed = _DEFAULT_CIRCUIT_THRESHOLD
    return max(1, min(parsed, 20))


def _circuit_cooldown_s() -> float:
    """Segundos con el circuito abierto antes de permitir un probe (half-open)."""
    raw = os.environ.get(_CIRCUIT_COOLDOWN_ENV, str(_DEFAULT_CIRCUIT_COOLDOWN_S))
    try:
        parsed = float(raw)
    except ValueError:
        parsed = _DEFAULT_CIRCUIT_COOLDOWN_S
    return max(0.0, min(parsed, 3600.0))


def _record_provider_failure(provider: str, reason: str) -> None:
    """Acumula un fallo de salud del provider y deja rastro grepeable en el log."""
    if provider == "claude":
        return
    _ensure_circuit_loaded()
    _CIRCUIT_STREAK[provider] += 1
    _CIRCUIT_LAST_FAILURE[provider] = time.time()
    _persist_circuit()
    streak = _CIRCUIT_STREAK[provider]
    if streak == _circuit_threshold():
        _log.warning(
            "circuit breaker ABIERTO para %s (streak=%d, reason=%s, cooldown=%.0fs)",
            provider,
            streak,
            reason,
            _circuit_cooldown_s(),
        )
    else:
        _log.debug("circuit breaker: fallo de %s (streak=%d, %s)", provider, streak, reason)


def _record_provider_success(provider: str) -> None:
    """Cierra el circuito del provider tras una respuesta sana (streak en 0)."""
    _ensure_circuit_loaded()
    if _CIRCUIT_STREAK.get(provider):
        _log.info("circuit breaker CERRADO para %s (respuesta sana)", provider)
        _CIRCUIT_STREAK.pop(provider, None)
        _CIRCUIT_LAST_FAILURE.pop(provider, None)
        # Solo persiste cuando habia un streak que limpiar: cero I/O en el
        # camino feliz (la inmensa mayoria de los turnos).
        _persist_circuit()
        return
    _CIRCUIT_STREAK.pop(provider, None)
    _CIRCUIT_LAST_FAILURE.pop(provider, None)


def _routing_trace_id(request: web.Request) -> str:
    get_value = getattr(request, "get", None)
    stored = get_value("antigravity_trace_id") if callable(get_value) else None
    headers = getattr(request, "headers", {})
    return str(
        stored
        or headers.get("X-Request-Id")
        or headers.get("X-Antigravity-Trace-Id")
        or ""
    )


def _request_uses_routing_v2(request: web.Request) -> bool:
    get_value = getattr(request, "get", None)
    if callable(get_value) and bool(get_value("antigravity_routing_v2")):
        return True
    return bool(getattr(request, "headers", {}).get("X-Antigravity-Route"))


def _record_routing_outcome(
    request: web.Request,
    provider: str,
    *,
    status_code: int | None = None,
    error_kind: str | None = None,
    retry_after: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Best-effort SQLite telemetry; never changes a proxy response."""
    try:
        retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
        routing_authority.get_routing_authority().store.record_outcome(
            provider,
            account_id=f"{provider}:default",
            status_code=status_code,
            error_kind=error_kind,
            retry_after=retry_seconds,
            latency_ms=latency_ms,
            trace_id=_routing_trace_id(request),
        )
    except Exception as exc:  # noqa: BLE001 — observability must not break requests
        _log.debug("routing outcome persistence skipped: %s", exc)


def _circuit_open(provider: str) -> bool:
    """True si el circuito del provider esta abierto (saltear upstream).

    Half-open implicito: pasado el cooldown devuelve False y el proximo request
    actua de probe — exito cierra el circuito, fallo lo reabre.
    """
    if provider == "claude" or not _circuit_enabled():
        return False
    _ensure_circuit_loaded()
    if _CIRCUIT_STREAK.get(provider, 0) < _circuit_threshold():
        return False
    last = _CIRCUIT_LAST_FAILURE.get(provider, 0.0)
    return (time.time() - last) < _circuit_cooldown_s()


def reset_circuit_state() -> None:
    """Limpia el estado del breaker, en memoria y persistido (tests / reset explicito)."""
    global _CIRCUIT_LOADED
    _CIRCUIT_STREAK.clear()
    _CIRCUIT_LAST_FAILURE.clear()
    proxy_state.clear_circuit()
    # Estado conocido-vacio: no recargar del disco lo que acabamos de borrar.
    _CIRCUIT_LOADED = True


def get_circuit_snapshot() -> dict[str, Any]:
    """Snapshot JSON-safe del breaker para el health endpoint (semaforo de Nexus)."""
    _ensure_circuit_loaded()
    return {
        "enabled": _circuit_enabled(),
        "threshold": _circuit_threshold(),
        "cooldown_s": _circuit_cooldown_s(),
        "streaks": dict(_CIRCUIT_STREAK),
        "open": {p: _circuit_open(p) for p in _CIRCUIT_STREAK},
        "last_failure_at": {
            p: datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            for p, ts in _CIRCUIT_LAST_FAILURE.items()
        },
    }


def _extract_request_model(raw_body: bytes) -> str | None:
    """Extrae el campo ``model`` del body, tolerando JSON invalido (-> None)."""
    try:
        payload = json.loads(raw_body)
    except Exception:  # noqa: BLE001 — boundary HTTP
        return None
    if not isinstance(payload, dict):
        return None
    model = payload.get("model")
    return model if isinstance(model, str) and model else None


def _resolve_class_route(provider: str, model: str, raw_body: bytes) -> tuple[str, str]:
    """Aplica el routing por clase de modelo, si esta configurado.

    Claude Code manda opus/sonnet para el trabajo principal y haiku (small-fast)
    para tareas internas. Con routing activo (`/provider route haiku zai`), los
    requests de esa clase van al backend ruteado en vez del activo — p. ej. el
    trafico haiku a GLM (centavos) mientras opus sigue en Claude, o al reves:
    todo en GLM salvo `opus=claude`.

    Sin routing configurado es un no-op sin costo (no parsea el body). El body
    solo se parsea cuando hay rutas; JSON invalido o clase no ruteada degradan
    al backend activo sin error.

    Args:
        provider: Provider activo (default si no hay ruta).
        model: Modelo activo asociado.
        raw_body: Body crudo del request (para leer el modelo pedido).

    Returns:
        Tupla ``(provider, model)`` efectiva para este request.
    """
    routing = proxy_state.get_class_routing()
    if not routing:
        return provider, model

    requested = _extract_request_model(raw_body)
    cls = proxy_state.detect_model_class(requested)
    entry = routing.get(cls) if cls else None
    if not isinstance(entry, dict):
        return provider, model

    routed_provider = str(entry.get("provider") or "")
    if routed_provider not in provider_switch.PROXY_COMPATIBLE:
        _log.warning("class routing ignorado: provider no compatible %r", routed_provider)
        return provider, model
    if routed_provider == provider:
        # Misma ruta que el backend activo: respetar el modelo del routing si
        # lo pinneo el usuario (p. ej. haiku=zai:glm-4.5-air con zai activo).
        routed_model = entry.get("model")
        return provider, str(routed_model) if routed_model else model

    if routed_provider == "claude":
        # Passthrough: Claude usa el modelo que pidio Claude Code (no se pisa).
        routed_model = str(requested or proxy_state.DEFAULT_MODEL)
    else:
        routed_model = str(entry.get("model") or "") or provider_switch.resolve_provider_model(
            routed_provider
        )
    _CLASS_ROUTE_TOTAL[f"{cls}->{routed_provider}"] += 1
    _log.debug("class routing: %s (%s) -> %s/%s", cls, requested, routed_provider, routed_model)
    return routed_provider, routed_model


def _open_circuits() -> set[str]:
    """Devuelve el set de providers proxy-routables con el circuito abierto."""
    return {p for p in provider_switch.PROXY_ROUTABLE if _circuit_open(p)}


def _failover_reroute(provider: str, model: str, raw_body: bytes) -> tuple[str, str]:
    """Reruteo pre-flight al próximo provider sano si el failover automático está activo.

    Cierra el lazo observar→actuar: si el failover está habilitado (opt-in) y el circuito
    del provider activo está abierto, rerutea al próximo sano de la cascada ANTES de armar
    el request — en vez de pagar el timeout o rescatar siempre a Claude (inútil si el
    caído ES Claude). Compone con el resto del flujo: el destino elegido tiene el circuito
    cerrado, así que el guard de circuito posterior lo deja pasar normal.

    No-op (devuelve el par sin cambios) si: el failover está OFF, el circuito está cerrado,
    o no hay ningún provider sano en la cascada.

    Args:
        provider: Provider activo (tras class-routing).
        model: Modelo activo asociado.
        raw_body: Body crudo del request (para resolver el modelo del destino claude).

    Returns:
        Tupla ``(provider, model)`` efectiva — rerutada o intacta.
    """
    if not provider_cascade.is_auto_failover_enabled():
        return provider, model
    # Vuelta al provider preferido: opt-in explícito. Sin esto, una selección manual
    # en Nexus (zai/minimax) puede volver sola a Claude apenas Claude aparezca sano.
    if _quota_auto_return_enabled():
        try:
            return_target = _quota_return_target(provider)
            if return_target is not None:
                if return_target == "claude":
                    new_model = _extract_request_model(raw_body) or proxy_state.DEFAULT_MODEL
                else:
                    new_model = provider_switch.resolve_provider_model(return_target)
                _mark_quota_rotation(provider)
                # Persistir el switch (best-effort: una key faltante no rompe este turno).
                try:
                    provider_switch.set_hotswap(return_target, new_model)
                except Exception as exc:  # noqa: BLE001 — persistencia best-effort
                    _log.debug("quota-return: set_hotswap(%s) falló: %s", return_target, exc)
                # Reusa el MISMO evento que el downgrade (no crear uno nuevo, no tocar TS).
                _record_auto_recovery("auto_failover_quota_reroute", provider)
                _log.info(
                    "quota-return: %s sano, volviendo de %s a %s/%s",
                    return_target,
                    provider,
                    return_target,
                    new_model,
                )
                return return_target, new_model
        except Exception as exc:  # noqa: BLE001 — la cuota nunca rompe el proxy
            _log.debug("quota-return: evaluación falló, sigo con downgrade: %s", exc)
    # Rotación PROACTIVA por cuota (Fase 1): si la cuota restante del provider activo
    # cayó bajo el umbral, rotar ANTES de chocar el 429 — sin esperar a que el circuito
    # se abra. No-op si la cuota es desconocida, está en cooldown, o no hay destino con
    # cuota OK (todos igual de agotados → quedarse donde está). Toda la evaluación va
    # bajo try: ante cualquier error, se cae al failover por circuito de abajo.
    try:
        quota_target = _quota_rotation_target(provider)
        if quota_target is not None:
            if quota_target == "claude":
                new_model = _extract_request_model(raw_body) or proxy_state.DEFAULT_MODEL
            else:
                new_model = provider_switch.resolve_provider_model(quota_target)
            _mark_quota_rotation(provider)
            # Persistir el switch para que el próximo prompt arranque ya en el destino
            # (best-effort: una key faltante no debe romper el reruteo de este turno).
            try:
                provider_switch.set_hotswap(quota_target, new_model)
            except Exception as exc:  # noqa: BLE001 — persistencia best-effort
                _log.debug("quota-rotate: set_hotswap(%s) falló: %s", quota_target, exc)
            _record_auto_recovery("auto_failover_quota_reroute", provider)
            _log.info(
                "quota-rotate: %s %.1f%% < %.1f%% → %s/%s",
                provider,
                _quota_remaining(provider) or 0.0,
                _quota_threshold_pct(),
                quota_target,
                new_model,
            )
            return quota_target, new_model
    except Exception as exc:  # noqa: BLE001 — la cuota nunca rompe el proxy
        _log.debug("quota-rotate: evaluación falló, sigo con circuito: %s", exc)
    if not _circuit_open(provider):
        return provider, model
    target = provider_cascade.next_healthy_provider(
        provider, _open_circuits(), provider_cascade.configured_providers()
    )
    if not target or target == provider:
        return provider, model
    if target == "claude":
        # Passthrough: Claude usa el modelo pedido por Claude Code (no se pisa).
        new_model = _extract_request_model(raw_body) or proxy_state.DEFAULT_MODEL
    else:
        new_model = provider_switch.resolve_provider_model(target)
    _record_auto_recovery("auto_failover_reroute", provider)
    _log.info("auto-failover: %s (circuito abierto) -> %s/%s", provider, target, new_model)
    return target, new_model


def _messages_count_tokens_url(messages_url: str) -> str:
    """Convierte un endpoint Anthropic `/v1/messages` en `/v1/messages/count_tokens`."""
    base = messages_url.rstrip("/")
    if base.endswith("/v1/messages"):
        return f"{base}/count_tokens"
    return f"{base}/v1/messages/count_tokens"


def _proxy_max_body_bytes() -> int:
    """Tope de body para las rutas del proxy (override por env, en bytes).

    El gateway limita el REST general a 1MB (hardening), pero Claude Code
    manda TODO el contexto de la conversacion en cada turno de `/v1/messages`
    (sesiones largas ~1MB+, imagenes en base64 varios MB): con el tope de la
    app, aiohttp rebotaba con 413 antes de llegar a ningun provider. El
    default es 32MB, el limite duro documentado de la API de Anthropic.
    """
    raw = os.environ.get("ANTIGRAVITY_PROXY_MAX_BODY_BYTES", "")
    try:
        parsed = int(raw)
        if parsed > 0:
            return parsed
    except ValueError:
        pass
    return 32 * 1024 * 1024


def _proxy_client_timeout() -> ClientTimeout:
    """Construye timeout del proxy con override por env.

    Usa `ANTIGRAVITY_PROXY_TIMEOUT_MS` y fallback a `API_TIMEOUT_MS`.
    Se aplica tanto a `total` como a `sock_read` para evitar cortes tempranos
    de streams largos (p. ej. respuestas extensas de MiniMax/GLM).
    """
    raw = os.environ.get("ANTIGRAVITY_PROXY_TIMEOUT_MS") or os.environ.get("API_TIMEOUT_MS")
    timeout_ms = _DEFAULT_PROXY_TIMEOUT_MS
    if raw:
        try:
            timeout_ms = max(int(raw), _MIN_PROXY_TIMEOUT_MS)
        except ValueError:
            timeout_ms = _DEFAULT_PROXY_TIMEOUT_MS
    timeout_seconds = timeout_ms / 1000
    return ClientTimeout(total=timeout_seconds, sock_read=timeout_seconds)


def _increment_provider_rate_limit(provider: str) -> int:
    """Incrementa y devuelve el total de 429 upstream por provider."""
    _UPSTREAM_RATE_LIMIT_TOTAL[provider] += 1
    return _UPSTREAM_RATE_LIMIT_TOTAL[provider]


# Japan Standard Time: sin horario de verano, asi que UTC+9 fijo es siempre
# exacto y evita depender del paquete `tzdata` en Windows.
_JST = timezone(timedelta(hours=9))


def _humanize_rate_limit(
    reset_raw: str | None,
    retry_after: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """Construye el aviso corto de rate limit con hora de reset en JST.

    Prioriza el timestamp RFC 3339 de los headers ``anthropic-ratelimit-*-reset``
    (lo que manda Anthropic al agotarse la ventana de uso); si no esta, cae al
    ``Retry-After`` en segundos. Degrada con gracia a un mensaje sin hora cuando
    no hay ningun dato de reset parseable (p. ej. providers no-Anthropic o un 429
    sin headers de rate limit).

    Args:
        reset_raw: Valor crudo de un header de reset (timestamp RFC 3339) o None.
        retry_after: Valor del header ``Retry-After`` (segundos) o None.
        now: Momento de referencia (inyectable para tests); default UTC actual.

    Returns:
        Mensaje listo para mostrar al usuario, p. ej.
        ``"Limite alcanzado. Reintenta en ~47 min (18:30 JST)."``.
    """
    current = now or datetime.now(UTC)
    reset_dt: datetime | None = None
    if reset_raw:
        try:
            parsed = datetime.fromisoformat(reset_raw.strip().replace("Z", "+00:00"))
            reset_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            reset_dt = None
    if reset_dt is None and retry_after:
        try:
            reset_dt = current + timedelta(seconds=int(float(retry_after.strip())))
        except ValueError:
            reset_dt = None
    if reset_dt is None:
        return "Limite alcanzado. Espera unos minutos antes de reintentar."
    # Ceil division entera (sin importar math): redondea los segundos restantes
    # hacia arriba al minuto y nunca baja de 1.
    remaining_seconds = int((reset_dt - current).total_seconds())
    minutes = max(1, (remaining_seconds + 59) // 60)
    local = reset_dt.astimezone(_JST).strftime("%H:%M")
    return f"Limite alcanzado. Reintenta en ~{minutes} min ({local} JST)."


def _record_auto_recovery(event: str, provider: str | None = None) -> None:
    """Acumula métricas de recuperaciones automáticas del proxy y deja rastro en log.

    Centralizar el logging acá garantiza que TODO evento de recovery quede
    registrado con un prefijo uniforme y grepeable (`proxy auto-recovery:`),
    sin depender de que cada call-site recuerde loguear. Antes, eventos como
    `auto_recovery_limit_reached` solo bumpeaban el counter en memoria y no
    dejaban ninguna huella en los logs.
    """
    _AUTO_RECOVERY_METRICS[event] += 1
    if provider:
        _AUTO_RECOVERY_BY_PROVIDER[provider] += 1
    _log.warning(
        "proxy auto-recovery: event=%s provider=%s event_total=%d provider_total=%d",
        event,
        provider or "-",
        _AUTO_RECOVERY_METRICS[event],
        _AUTO_RECOVERY_BY_PROVIDER.get(provider, 0) if provider else 0,
    )
    # Ring persistente: el overview y Nexus muestran QUE decidio el proxy y
    # CUANDO, sobreviviendo restarts. Solo corre en eventos de recovery (raros),
    # asi que no agrega I/O al camino feliz; record_recovery_event jamas levanta.
    proxy_state.record_recovery_event(event, provider)


def _auto_recovery_max_retries() -> int:
    """Límite de rescates automáticos por request del proxy."""
    raw = os.environ.get(
        _AUTO_RECOVERY_MAX_RETRIES_ENV,
        str(_DEFAULT_AUTO_RECOVERY_MAX_RETRIES),
    )
    try:
        parsed = int(raw)
    except ValueError:
        parsed = _DEFAULT_AUTO_RECOVERY_MAX_RETRIES
    return max(0, min(parsed, 5))


def get_proxy_recovery_metrics() -> dict[str, Any]:
    """Snapshot JSON-safe para health endpoint."""
    return {
        "counters": dict(_AUTO_RECOVERY_METRICS),
        "by_provider": dict(_AUTO_RECOVERY_BY_PROVIDER),
        "class_routing": dict(_CLASS_ROUTE_TOTAL),
        "circuit": get_circuit_snapshot(),
        "shadow": get_shadow_metrics(),
        "recent_events": proxy_state.get_recovery_events(),
        "config": {
            "auto_fallback_enabled": _auto_fallback_enabled(),
            "auto_compact_enabled": _auto_compact_enabled(),
            "max_retries_per_request": _auto_recovery_max_retries(),
            "compact_max_messages": _auto_compact_max_messages(),
        },
    }


def _auto_fallback_enabled() -> bool:
    """Indica si el proxy puede rescatar errores de terceros via Claude."""
    raw = os.environ.get(_AUTO_FALLBACK_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


# Sentinel para detectar upstreams sintéticos sin atributo content_type (tests u
# objetos mock que no modelan aiohttp). Definido a nivel módulo para que haya una
# sola instancia por proceso y la comparación `is`/`is not` sea siempre correcta.
_SSE_GUARD_MISSING = object()


def _response_is_sse(content_type: str | None) -> bool:
    """Indica si el content-type del upstream corresponde a un stream SSE válido.

    Tanto el passthrough Anthropic como los backends OpenAI-compatible responden
    ``text/event-stream`` cuando streamean sano. Un 200 con ``text/html`` o
    ``application/json`` es un body de error de un provider sobrecargado.

    Args:
        content_type: Header content-type del upstream (puede venir vacío/None).

    Returns:
        True si el content-type contiene ``text/event-stream``.
    """
    return bool(content_type) and "text/event-stream" in content_type.lower()


def _fallback_sticky_enabled() -> bool:
    """Indica si el rescate automatico a Claude debe ser sticky.

    Default no-sticky (False): el fallback registra el rescate pero NO cambia el
    backend activo, de modo que el proximo prompt reintenta el provider elegido por
    el usuario. Con `ANTIGRAVITY_PROXY_FALLBACK_STICKY=1` se restaura el comportamiento
    historico (conmutar el backend a Claude tras el rescate).
    """
    raw = os.environ.get(_FALLBACK_STICKY_ENV, "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _auto_compact_enabled() -> bool:
    """Indica si se permite reintento automatico compactando contexto en Claude."""
    raw = os.environ.get(_AUTO_COMPACT_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _auto_compact_max_messages() -> int:
    """Cantidad maxima de mensajes a conservar al compactar contexto."""
    raw = os.environ.get(
        _AUTO_COMPACT_MAX_MESSAGES_ENV,
        str(_DEFAULT_AUTO_COMPACT_MAX_MESSAGES),
    )
    try:
        parsed = int(raw)
    except ValueError:
        parsed = _DEFAULT_AUTO_COMPACT_MAX_MESSAGES
    return max(4, min(parsed, 40))


def _chunk_has_context_limit_error(chunk: bytes) -> bool:
    """Detecta un evento SSE de error por limite de contexto en el primer chunk."""
    text = chunk.decode("utf-8", errors="ignore").lower()
    if "error" not in text:
        return False
    return any(marker in text for marker in _CONTEXT_LIMIT_MARKERS)


def _chunk_has_context_limit_stop_reason(chunk: bytes) -> bool:
    """Detecta respuestas JSON exitosas que reportan context window exceeded."""
    try:
        payload = json.loads(chunk.decode("utf-8", errors="ignore"))
    except Exception:  # noqa: BLE001 — boundary HTTP
        return False

    if not isinstance(payload, dict):
        return False

    stop_reason = str(payload.get("stop_reason", "")).lower()
    if not stop_reason:
        return False
    return "context_window_exceeded" in stop_reason or "context" in stop_reason


def _base_resp_signals_error(payload: object) -> bool:
    """True si el shape propietario ``base_resp`` de MiniMax delata un fallo.

    MiniMax (Anthropic-compat) NO usa el contrato Anthropic ``type:error`` /
    ``error:{}`` para sus fallos: los reporta como
    ``{"base_resp": {"status_code": <int>, "status_msg": "..."}}``. Un
    ``status_code`` no-cero es un error real — p.ej. ``2013`` con
    ``status_msg`` ``"tool result's tool id(...) not found"`` (historial con un
    ``tool_result`` huerfano tras hot-swap/compactacion). El camino feliz usa
    ``status_code == 0`` y NUNCA debe disparar.

    Args:
        payload: Objeto JSON ya parseado (frame ``data:`` o body completo).

    Returns:
        True si ``base_resp.status_code`` existe y es un entero no-cero.
    """
    if not isinstance(payload, dict):
        return False
    base_resp = payload.get("base_resp")
    if not isinstance(base_resp, dict):
        return False
    code = base_resp.get("status_code")
    return isinstance(code, int) and code != 0


def _json_has_top_level_error(chunk: bytes) -> bool:
    """Detecta respuestas JSON con error top-level (shape no-streaming de fallo).

    Algunos providers Anthropic-compat pueden devolver HTTP 200 + JSON de error
    (por ejemplo con campo ``error``) en lugar de SSE. En ese caso debemos
    rescatar via Claude para no filtrar un body no-SSE al cliente. Tambien cubre
    el shape propietario de MiniMax (``base_resp.status_code`` no-cero), que no
    usa la clave ``error``.
    """
    try:
        payload = json.loads(chunk.decode("utf-8", errors="ignore"))
    except Exception:  # noqa: BLE001 — boundary HTTP
        return False
    if not isinstance(payload, dict):
        return False
    return "error" in payload or _base_resp_signals_error(payload)


def _chunk_has_recoverable_sse_error(chunk: bytes) -> bool:
    """Detecta un primer evento SSE de error recuperable de un backend alternativo.

    Criterio (Fix A, spec 2026-06-24-provider-switch-robusto-cascade-design):
    se parsea el primer frame ``data:`` completo y se dispara fallback **solo si**
    el JSON de ese frame tiene ``"type":"error"`` o la clave ``"error"`` en el
    **nivel top-level** — mismo contrato que ``_json_has_top_level_error``. Se suma
    el shape propietario de MiniMax (``base_resp.status_code`` no-cero), que no usa
    la clave ``error`` ni la palabra "error" en su ``status_msg`` (p.ej. 2013
    ``"tool result's tool id(...) not found"``) — por eso la guarda barata tambien
    admite ``base_resp``.

    Esto evita el falso positivo de backends Anthropic-compat (p.ej. GLM-5.2) que
    abren su stream SANO con campos anidados o ``"error": null`` que el detector
    viejo (substring-based ``'"error":'``) confundía con un fallo, disparando
    fallback en cada turno.
    """
    text = chunk.decode("utf-8", errors="ignore")
    low = text.lower()
    # Exclusiones baratas antes de parsear: rate-limit/quota se dejan crudos.
    if "rate_limit" in low or "too many requests" in low or "quota" in low:
        return False
    # Sin una senal estructurada de error no parseamos: el contrato Anthropic
    # ("error") o el shape propietario de MiniMax ("base_resp"). Un chunk de texto
    # del camino feliz no tiene ninguno → se deja pasar barato.
    if "error" not in low and "base_resp" not in low:
        return False

    # Extraer el primer frame ``data:`` completo del chunk.
    payload = _first_sse_data_json(text)
    if payload is None:
        # No hay frame data parseable → no podemos afirmar que es un error; dejar crudo.
        return False
    # Contrato Anthropic: el frame es error si su ``type`` lo dice explícitamente,
    # o si hay una clave ``error`` con shape de error real (dict no vacío). Un
    # mero ``"error": "ok"`` / ``"error": null`` / ``"error": "none"`` es un flag
    # de status del camino feliz, no un fallo.
    if payload.get("type") == "error":
        return True
    err = payload.get("error")
    if isinstance(err, dict) and err:
        return True
    # MiniMax: fallo via ``base_resp.status_code`` no-cero (status_code 0 = exito).
    return _base_resp_signals_error(payload)


def _first_sse_data_json(text: str) -> dict | None:
    """Devuelve el JSON del primer frame ``data:`` del chunk, o None si no parsea.

    Un frame SSE es ``data: <json>\\n`` (eventualmente seguido de un ``\\n``).
    Algunos backends mandan varios eventos pegados; tomamos solo el primero porque
    es el que decide si el stream arrancó mal.
    """
    start = text.find("data:")
    if start == -1:
        return None
    rest = text[start + len("data:") :]
    end = rest.find("\n")
    raw = rest if end == -1 else rest[:end]
    raw = raw.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001 — boundary de stream externo
        return None
    return payload if isinstance(payload, dict) else None


def _anthropic_error_sse(detail: str, *, error_type: str = "api_error") -> bytes:
    """Construye un evento SSE Anthropic ``error`` bien formado.

    Claude Code entiende este contrato nativo y muestra un error legible en vez
    de un 200 malformado. Se usa para degradar con gracia cuando un backend
    alternativo falla a mitad del stream (post-commit del HTTP 200), donde ya no
    es posible un fallback transparente porque los headers + primeros chunks ya
    salieron al cliente.

    Args:
        detail: Mensaje legible para el usuario.
        error_type: Tipo de error Anthropic (``api_error``, ``overloaded_error``).

    Returns:
        Bytes del evento SSE ``event: error`` listo para escribir al cliente.
    """
    payload = {"type": "error", "error": {"type": error_type, "message": detail}}
    return f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _is_midstream_provider_error(
    chunk: bytes, provider: str | None, fallback_from: str | None
) -> bool:
    """Indica si un chunk POSTERIOR al primero delata un fallo recuperable del provider.

    Una vez que el HTTP 200 + headers se comprometieron (``response.prepare``), ya
    no se puede hacer fallback transparente. Pero si un backend alternativo emite
    un ``event: error`` (o un OpenAI ``{"error": {...}}``) a mitad del stream, hay
    que detectarlo para cerrar con un error legible en vez de filtrar basura cruda
    que Claude Code reporta como "error 200".

    Excluye el provider ``claude`` (sus errores nativos ya son legibles), los
    fallbacks en curso (evita recursión), los límites de contexto y rate-limit (se
    dejan crudos a propósito) y los ``"error": null`` que algunos backends emiten
    en cada chunk del camino feliz.

    Args:
        chunk: Chunk crudo del stream (posterior al primero).
        provider: Backend activo del turno.
        fallback_from: Provider del que ya se está rescatando (None si no aplica).

    Returns:
        True si el chunk debe tratarse como fallo mid-stream del provider.
    """
    if not provider or provider == "claude" or fallback_from:
        return False
    if not _auto_fallback_enabled():
        return False
    compact = chunk.decode("utf-8", errors="ignore").replace(" ", "").lower()
    if '"error":null' in compact or '"error":{}' in compact:
        return False
    if _chunk_has_context_limit_error(chunk):
        return False
    return _chunk_has_recoverable_sse_error(chunk)


def _alt_precompact_enabled() -> bool:
    """Indica si se pre-compacta el contexto de backends alternativos."""
    raw = os.environ.get(_ALT_PRECOMPACT_ENV, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _alt_precompact_max_messages() -> int:
    """Umbral de mensajes para la pre-compactacion de backends alternativos."""
    raw = os.environ.get(
        _ALT_PRECOMPACT_MAX_MESSAGES_ENV,
        str(_DEFAULT_ALT_PRECOMPACT_MAX_MESSAGES),
    )
    try:
        parsed = int(raw)
    except ValueError:
        parsed = _DEFAULT_ALT_PRECOMPACT_MAX_MESSAGES
    return max(8, min(parsed, 200))


def _compact_request_body(raw_body: bytes, max_messages: int | None = None) -> bytes | None:
    """Recorta mensajes antiguos del payload Anthropic para reintento automatico.

    Args:
        raw_body: Body crudo del request en formato Anthropic.
        max_messages: Cantidad maxima de mensajes a conservar. Si es ``None`` usa
            el umbral del auto-compact reactivo de Claude (``_auto_compact_max_messages``).

    Returns:
        El body recortado en bytes, o ``None`` si no hace falta recortar (payload
        invalido, sin lista de mensajes, o ya por debajo del umbral).
    """
    try:
        payload = json.loads(raw_body)
    except Exception:  # noqa: BLE001 — boundary HTTP
        return None

    if not isinstance(payload, dict):
        return None

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return None

    limit = _auto_compact_max_messages() if max_messages is None else max_messages
    if len(messages) <= limit:
        return None

    compacted_payload = dict(payload)
    compacted_payload["messages"] = messages[-limit:]
    compacted = json.dumps(compacted_payload, ensure_ascii=False).encode("utf-8")
    if compacted == raw_body:
        return None
    return compacted


def _should_auto_compact_retry(provider: str, status: int, text: str) -> bool:
    """Determina si conviene reintentar automaticamente compactando contexto."""
    if provider != "claude" or not _auto_compact_enabled():
        return False
    if status not in _FALLBACK_STATUSES:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _CONTEXT_LIMIT_MARKERS)


def _should_fallback_to_claude(provider: str, status: int, text: str) -> bool:
    """Decide si un error upstream es recuperable con passthrough Claude.

    MiniMax/ZAI pueden rechazar turnos que Claude Code arma para Anthropic nativo
    (contexto largo, tools, imagenes o parametros no soportados). En esos casos
    devolver el 400 crudo deja la conversacion sin salida, incluso para pedir
    `/provider claude`. Tambien pueden devolver 5xx genericos (por ejemplo
    MiniMax `unknown error, 999 (1000)`) ante turnos grandes; esos son fallos
    del backend alternativo, no configuracion local. El fallback conserva viva
    la sesion y evita el bucle.
    """
    if provider == "claude" or not _auto_fallback_enabled():
        return False
    if status in _SERVER_ERROR_FALLBACK_STATUSES:
        return True
    if status not in _FALLBACK_STATUSES:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _CONTEXT_LIMIT_MARKERS)


def _auto_recovery_limit_response(provider: str) -> web.Response:
    """Construye la respuesta 429 cuando se agotan los rescates automaticos.

    Centraliza el cuerpo del error `AUTO_RECOVERY_LIMIT` para no duplicarlo en
    cada call-site que detecta `auto_recovery_remaining <= 0`.

    Args:
        provider: Nombre del provider que agoto los reintentos.

    Returns:
        Una respuesta JSON con status 429 y el hint de compactacion.
    """
    return web.json_response(
        {
            "error": "limite de auto-recuperacion alcanzado",
            "code": "AUTO_RECOVERY_LIMIT",
            "provider": provider,
            "hint": _COMPACT_HINT,
        },
        status=429,
        # El proxy YA reintento/rescato por su cuenta: sin este header Claude
        # Code re-reintenta encima -> tormenta de double-retries.
        headers={"x-should-retry": "false"},
    )


_UPSTREAM_ERROR_LOG_ENV = "ANTIGRAVITY_PROXY_UPSTREAM_ERROR_LOG"
_UPSTREAM_ERROR_TEXT_LIMIT = 1000


def _upstream_error_log_path() -> Path:
    """Resuelve la ruta del log de errores 400 del upstream.

    Returns:
        Ruta a ``upstream_errors.jsonl``: el override de
        ``ANTIGRAVITY_PROXY_UPSTREAM_ERROR_LOG`` o el default bajo
        ``~/.antigravity/proxy/``.
    """
    override = os.environ.get(_UPSTREAM_ERROR_LOG_ENV)
    if override:
        return Path(override)
    return Path.home() / ".antigravity" / "proxy" / "upstream_errors.jsonl"


def _payload_summary(raw_body: bytes) -> dict[str, Any]:
    """Resume la forma del payload SIN exponer contenido ni secretos.

    Cuenta estructuras relevantes para diagnosticar por que un alternativo rechazo
    el historial. Nunca incluye texto de mensajes, system prompts ni API keys.

    Args:
        raw_body: Body crudo del request.

    Returns:
        Dict con conteos: ``n_messages, n_tool_use, n_tool_result, n_thinking,
        n_system, has_tools``. Ante un body no parseable devuelve ceros.
    """
    summary = {
        "n_messages": 0,
        "n_tool_use": 0,
        "n_tool_result": 0,
        "n_thinking": 0,
        "n_system": 0,
        "has_tools": False,
    }
    try:
        payload = json.loads(raw_body)
    except Exception:  # noqa: BLE001 — boundary HTTP; un body roto no debe romper el log
        return summary
    if not isinstance(payload, dict):
        return summary
    messages = payload.get("messages")
    if isinstance(messages, list):
        summary["n_messages"] = len(messages)
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "system":
                summary["n_system"] += 1
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "tool_use":
                    summary["n_tool_use"] += 1
                elif btype == "tool_result":
                    summary["n_tool_result"] += 1
                elif btype in ("thinking", "redacted_thinking"):
                    summary["n_thinking"] += 1
    if isinstance(payload.get("system"), (list, str)) and payload.get("system"):
        summary["n_system"] += 1
    summary["has_tools"] = bool(payload.get("tools"))
    return summary


def _payload_has_tool_history(raw_body: bytes) -> bool:
    """True si el historial tiene bloques tool_use/tool_result/thinking que purgar.

    Sirve de guard para el retry agresivo: solo tiene sentido purgar el historial
    de herramientas si efectivamente hay tool/thinking blocks. Un 400 sobre un
    historial sin esos bloques es un error de configuracion del provider, no del
    historial, y no debe enmascararse con un reintento.

    Args:
        raw_body: Body crudo del request.

    Returns:
        True si algun mensaje contiene un bloque tool_use/tool_result/thinking.
    """
    summary = _payload_summary(raw_body)
    return bool(summary["n_tool_use"] or summary["n_tool_result"] or summary["n_thinking"])


def _log_upstream_error(
    provider: str,
    model: str,
    status: int,
    upstream_error_text: str,
    raw_body: bytes,
) -> None:
    """Appendea una linea JSON al log de errores 400 del upstream.

    Observabilidad dedicada para diagnosticar los rechazos de los alternativos sin
    exponer secretos ni contenido completo de mensajes. Best-effort: cualquier fallo
    de IO solo se loguea, nunca rompe el turno.

    Args:
        provider: Backend alternativo que devolvio el error.
        model: Modelo activo del provider.
        status: Codigo HTTP del upstream.
        upstream_error_text: Cuerpo del error del upstream (se trunca a 1000 chars).
        raw_body: Body crudo del request (para el resumen estructural).
    """
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model,
        "status": status,
        "upstream_error_text": (upstream_error_text or "")[:_UPSTREAM_ERROR_TEXT_LIMIT],
        "payload_summary": _payload_summary(raw_body),
    }
    try:
        path = _upstream_error_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - IO best-effort
        _log.warning("no se pudo escribir el upstream error log: %s", exc)


def _turn_usage_log_path() -> Path:
    """Ruta del log de uso por turno (tokens por provider) para la telemetría de Nexus."""
    override = os.environ.get("ANTIGRAVITY_PROXY_TURN_USAGE_LOG")
    if override:
        return Path(override)
    return Path.home() / ".antigravity" / "proxy" / "turn_usage.jsonl"


_TURN_USAGE_MAX_BYTES = 5 * 1024 * 1024  # 5MB → rota a .1 (evita crecer sin tope)


def _extract_anthropic_usage(chunks: list[bytes]) -> tuple[int, int]:
    """Extrae ``(input_tokens, output_tokens)`` de chunks SSE Anthropic. Pura y tolerante.

    ``message_start`` trae ``message.usage.input_tokens``; ``message_delta`` trae
    ``usage.output_tokens``. Líneas no-``data:`` o JSON corrupto se ignoran.

    Args:
        chunks: Chunks crudos del stream (basta el primero + el último).

    Returns:
        Tupla ``(input_tokens, output_tokens)``; 0 si no se pudo determinar.
    """
    text = b"".join(chunks).decode("utf-8", errors="ignore")
    input_t = 0
    output_t = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            obj = json.loads(line[len("data:") :].strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        msg = obj.get("message")
        if isinstance(msg, dict):
            u = msg.get("usage")
            if isinstance(u, dict) and u.get("input_tokens"):
                input_t = int(u["input_tokens"])
        u = obj.get("usage")
        if isinstance(u, dict) and u.get("output_tokens"):
            output_t = int(u["output_tokens"])
    return input_t, output_t


def _log_turn_usage(provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Registra el uso de tokens de un turno (best-effort, nunca rompe el turno).

    Alimenta la telemetría de costo por sesión de Nexus. Skip si no hay provider o si
    ambos contadores son 0 (turno sin datos de uso). Rota el archivo a ``.1`` al superar
    el tope, para no crecer sin límite.

    Args:
        provider: Backend que sirvió el turno.
        model: Modelo activo.
        input_tokens: Tokens de entrada (prompt).
        output_tokens: Tokens de salida (generados).
    """
    if not provider or (input_tokens <= 0 and output_tokens <= 0):
        return
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model or "",
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
    }
    try:
        path = _turn_usage_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > _TURN_USAGE_MAX_BYTES:
            path.replace(path.with_suffix(".jsonl.1"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - IO best-effort
        _log.debug("no se pudo escribir turn_usage: %s", exc)


class _ProxyMixin:
    """Endpoint de proxy con hot-swap de backend IA."""

    async def _recover_stream_context_limit(
        self,
        request: web.Request,
        provider: str,
        raw_body: bytes,
        auto_recovery_remaining: int,
    ) -> web.StreamResponse | None:
        """Intenta rescatar un stream que abrio con un error de limite de contexto.

        Cuando el primer chunk SSE delata un context-window exceeded, decide la
        estrategia de recuperacion segun el provider: para terceros, fallback a
        Claude; para Claude, reintento compactando el contexto. Devuelve la
        respuesta final del rescate o ``None`` si no hay nada que recuperar y el
        caller debe continuar con el passthrough normal.

        Args:
            request: Request original de Claude Code (para headers/routing).
            provider: Provider activo que origino el stream.
            raw_body: Body crudo del request, necesario para reintentar.
            auto_recovery_remaining: Rescates automaticos disponibles.

        Returns:
            La ``web.StreamResponse`` del rescate, o ``None`` para seguir con el
            passthrough del stream original.
        """
        if provider != "claude":
            if auto_recovery_remaining <= 0:
                _record_auto_recovery("auto_recovery_limit_reached", provider)
                return _auto_recovery_limit_response(provider)
            _record_auto_recovery("fallback_stream_context_limit", provider)
            return await self._fallback_to_claude(
                request,
                None,
                raw_body,
                provider,
                "upstream-sse-context-limit",
            )

        compacted_body = _compact_request_body(raw_body)
        if not compacted_body:
            return None
        if auto_recovery_remaining <= 0:
            _record_auto_recovery("auto_recovery_limit_reached", provider)
            return _auto_recovery_limit_response(provider)
        _record_auto_recovery("compact_retry_stream_context_limit", provider)
        try:
            target = provider_router.resolve_target("claude", dict(request.headers))
        except provider_router.RouterError as exc:
            return web.json_response(
                {
                    "error": f"auto-compact retry no disponible: {exc}",
                    "hint": _COMPACT_HINT,
                },
                status=502,
            )

        async with ClientSession(timeout=_proxy_client_timeout()) as retry_session:
            async with retry_session.post(
                target["url"],
                headers=target["headers"],
                data=compacted_body,
            ) as retry_upstream:
                if retry_upstream.status != 200:
                    retry_text = await retry_upstream.text()
                    return web.json_response(
                        {
                            "error": ("auto-compact retry fallo tras error SSE de contexto"),
                            "status": retry_upstream.status,
                            "detail": retry_text[:1000],
                            "hint": _COMPACT_HINT,
                        },
                        status=retry_upstream.status,
                        # El proxy ya reintento (compactando): no re-reintentar encima.
                        headers={"x-should-retry": "false"},
                    )
                return await self._stream_upstream(
                    request,
                    retry_upstream,
                    auto_recovery_remaining=auto_recovery_remaining - 1,
                )

    @staticmethod
    async def _read_first_chunk(upstream: Any) -> bytes | None:
        """Consume el primer chunk no vacio del stream SSE upstream.

        Args:
            upstream: Respuesta aiohttp con `.content.iter_any()`.

        Returns:
            El primer chunk con datos, o ``None`` si el upstream termino sin enviar nada.
        """
        async for chunk in upstream.content.iter_any():
            if chunk:
                return chunk
        return None

    @staticmethod
    async def _finalize_stream_after_error(
        response: web.StreamResponse, prepared: bool
    ) -> web.StreamResponse | None:
        """Cierra el stream tras una excepcion durante la transmision SSE.

        Args:
            response: La respuesta en curso hacia el cliente.
            prepared: ``True`` si ``response.prepare()`` ya se ejecuto.

        Returns:
            La respuesta cerrada con EOF si ya estaba preparada, o ``None`` para
            indicarle al caller que debe re-propagar la excepcion original.
        """
        if prepared:
            try:
                await response.write_eof()
            except Exception:  # noqa: BLE001
                pass
            return response
        return None

    async def _check_first_chunk_recovery(
        self,
        request: web.Request,
        first_chunk: bytes,
        raw_body: bytes | None,
        provider: str | None,
        auto_recovery_remaining: int,
    ) -> web.StreamResponse | None:
        """Detecta un error de limite de contexto en el primer chunk y, si aplica, recupera.

        Args:
            request: Request entrante.
            first_chunk: Primer chunk con datos del stream SSE.
            raw_body: Body crudo original (necesario para recuperar).
            provider: Provider activo (necesario para recuperar).
            auto_recovery_remaining: Reintentos de auto-recuperacion disponibles.

        Returns:
            La respuesta de recuperacion si se detecto y rescato un error de
            limite de contexto; ``None`` para continuar con el streaming normal.
        """
        has_context_error = _chunk_has_context_limit_error(
            first_chunk
        ) or _chunk_has_context_limit_stop_reason(first_chunk)
        if provider and raw_body and has_context_error:
            return await self._recover_stream_context_limit(
                request,
                provider,
                raw_body,
                auto_recovery_remaining,
            )
        return None

    async def _rescue_provider_failure(
        self,
        request: web.Request,
        raw_body: bytes,
        provider: str,
        reason: str,
    ) -> web.StreamResponse:
        """Rescata un "200 malformado" del provider activo (usado por `_stream_upstream`).

        Punto único para las tres ramas de rescate de `_stream_upstream` (200-no-SSE,
        SSE-error-en-primer-chunk, JSON-error-top-level). Antes, las tres saltaban
        siempre a `_fallback_to_claude` (un solo salto) aunque el auto-failover en
        cascada estuviera activo: si el turno ya venía de rotar claude→zai y zai
        devolvía uno de estos 200 rotos, el rescate volvía derecho a Claude —que podía
        seguir en 429— en vez de seguir bajando la cascada a minimax/opencode/
        openrouter/ollama. Unifica con el camino de status-code no-200
        (`_handle_upstream_error`), que ya usaba la cascada completa.

        Args:
            request: Request entrante.
            raw_body: Body crudo original del turno.
            provider: Provider que acaba de devolver el 200 malformado.
            reason: Motivo legible (para logs/state).

        Returns:
            La respuesta del próximo provider sano de la cascada, o el rescate
            histórico de un solo salto a Claude si la cascada está OFF o agotada.
        """
        if (
            provider_cascade.is_auto_failover_enabled()
            or _request_uses_routing_v2(request)
        ):
            rotated = await self._failover_to_next_healthy(
                request, None, raw_body, provider, reason, {provider}
            )
            if rotated is not None:
                return rotated
        return await self._fallback_to_claude(request, None, raw_body, provider, reason)

    async def _stream_upstream(
        self,
        request: web.Request,
        upstream: Any,
        *,
        fallback_from: str | None = None,
        raw_body: bytes | None = None,
        provider: str | None = None,
        model: str | None = None,
        auto_recovery_remaining: int = 0,
        response: web.StreamResponse | None = None,
        tee_buffer: list[bytes] | None = None,
    ) -> web.StreamResponse:
        """Transmite un upstream SSE hacia Claude Code.

        Si ``tee_buffer`` viene (shadow mode), cada chunk transmitido tambien se
        acumula ahi para extraer el texto de la respuesta al finalizar.
        """
        # El upstream devolvió 200 pero el content-type no es SSE (HTML/JSON de
        # error, 200 hueco de un provider sobrecargado). Tratarlo como fallo del
        # provider y rescatar via Claude — igual que un 5xx — siempre que no
        # estemos ya sirviendo un fallback (evita recursión) y el auto-fallback
        # esté activo. Reusa el breaker + _fallback_to_claude existentes.
        #
        # Condiciones de activación:
        # - content_type presente en el upstream (aiohttp real siempre lo tiene;
        #   objetos sintéticos sin atributo → no podemos determinar → no rescatar).
        # - No es SSE: text/event-stream → es un stream válido, pasar.
        # - No es JSON: application/json puede ser legítimo (p.ej. stop_reason
        #   de contexto) y se evalúa luego del primer chunk para distinguir
        #   error top-level real vs caso válido.
        # Captura passiva de cuota: el provider activo expone su rate-limit unificado
        # en los headers de la respuesta 200. Señal real-time para el auto-rotate.
        # Gateada por opt-in: con la feature OFF, cero I/O extra en el hot path.
        if provider and provider_cascade.is_auto_failover_enabled():
            _capture_quota_headers(provider, getattr(upstream, "headers", {}))
        _upstream_ct = getattr(upstream, "content_type", _SSE_GUARD_MISSING)
        _is_json_ct = "application/json" in str(_upstream_ct).lower()
        if (
            not fallback_from
            and provider
            and provider != "claude"
            and raw_body is not None
            and _auto_fallback_enabled()
            and _upstream_ct is not _SSE_GUARD_MISSING
            and not _response_is_sse(_upstream_ct)
            and not _is_json_ct
        ):
            _record_provider_failure(provider, "status-200-no-sse")
            return await self._rescue_provider_failure(
                request, raw_body, provider, "upstream-200-no-sse"
            )

        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Antigravity-Trace-Id": _routing_trace_id(request),
        }
        if fallback_from:
            headers["X-Antigravity-Fallback-From"] = fallback_from

        response = response or web.StreamResponse(status=200, headers=headers)
        prepared = False
        try:
            first_chunk = await self._read_first_chunk(upstream)

            if first_chunk is None:
                _log.error("upstream SSE termino sin enviar chunks")
                # Mismo camino de rescate que los otros 200-malformados (no-SSE /
                # SSE-error / JSON-error): cascada o fallback a Claude. Antes era
                # el unico caso que moria en 502 seco hacia Claude Code.
                if (
                    not fallback_from
                    and provider
                    and provider != "claude"
                    and raw_body is not None
                    and _auto_fallback_enabled()
                ):
                    _record_provider_failure(provider, "status-200-empty-stream")
                    return await self._rescue_provider_failure(
                        request, raw_body, provider, "upstream-200-empty-stream"
                    )
                return web.json_response(
                    {
                        "error": "backend devolvio un stream vacio",
                        "detail": (
                            "El upstream respondio HTTP 200 pero no envio eventos SSE validos."
                        ),
                    },
                    status=502,
                )

            recovered = await self._check_first_chunk_recovery(
                request, first_chunk, raw_body, provider, auto_recovery_remaining
            )
            if recovered is not None:
                return recovered

            # Algunos backends alternativos devuelven HTTP 200 + SSE valido pero
            # arrancan con `event: error` (p.ej. provider sobrecargado). Claude
            # Code lo ve como respuesta 200 malformada; rescatar antes de pasar
            # ese stream conserva viva la sesion. Los rate limits se dejan crudos.
            if (
                not fallback_from
                and provider
                and provider != "claude"
                and raw_body is not None
                and _auto_fallback_enabled()
                and _response_is_sse(str(_upstream_ct))
                and _chunk_has_recoverable_sse_error(first_chunk)
                and not _chunk_has_context_limit_error(first_chunk)
            ):
                _record_provider_failure(provider, "status-200-sse-error")
                return await self._rescue_provider_failure(
                    request, raw_body, provider, "upstream-200-sse-error"
                )

            # Si el upstream es JSON no-SSE y trae error top-level (no context-limit),
            # tratarlo como fallo del provider y rescatar via Claude.
            if (
                not fallback_from
                and provider
                and provider != "claude"
                and raw_body is not None
                and _auto_fallback_enabled()
                and _is_json_ct
                and _json_has_top_level_error(first_chunk)
                and not _chunk_has_context_limit_error(first_chunk)
                and not _chunk_has_context_limit_stop_reason(first_chunk)
            ):
                _record_provider_failure(provider, "status-200-json-error")
                return await self._rescue_provider_failure(
                    request, raw_body, provider, "upstream-200-json-error"
                )

            await response.prepare(request)
            prepared = True

            # Backends OpenAI-compatible: el upstream responde Chat Completions SSE
            # (data: {choices:[{delta:{content}}]...}), que hay que traducir a eventos
            # Anthropic (message_start/content_block_delta/...) para Claude Code. Los
            # chunks se alimentan al traductor y este emite los SSE Anthropic ya
            # serializados; el tee_buffer (shadow mode) recoge la salida traducida.
            if provider and provider_router.is_openai_compatible(provider):
                translator = openai_translator.OpenAiStreamTranslator(model=model or "")
                # `feed()` es sincrono y devuelve list[bytes]; solo el upstream
                # (iter_any) es async. Por eso `for` sobre feed() y `async for`
                # sobre el stream.
                for translated in translator.feed(first_chunk):
                    if tee_buffer is not None:
                        tee_buffer.append(translated)
                    await response.write(translated)
                async for chunk in upstream.content.iter_any():
                    if not chunk:
                        continue
                    if _is_midstream_provider_error(chunk, provider, fallback_from):
                        await self._close_stream_with_provider_error(
                            request, response, provider, model, raw_body, chunk
                        )
                        return response
                    for translated in translator.feed(chunk):
                        if tee_buffer is not None:
                            tee_buffer.append(translated)
                        await response.write(translated)
                for translated in translator.flush():
                    if tee_buffer is not None:
                        tee_buffer.append(translated)
                    await response.write(translated)
                try:
                    _log_turn_usage(
                        provider or "",
                        model or "",
                        translator._input_tokens,
                        translator._output_tokens,
                    )
                except Exception:  # noqa: BLE001 — telemetría best-effort, nunca rompe
                    pass
                await response.write_eof()
                return response

            if tee_buffer is not None:
                tee_buffer.append(first_chunk)
            await response.write(first_chunk)
            last_chunk = first_chunk
            async for chunk in upstream.content.iter_any():
                if not chunk:
                    continue
                if _is_midstream_provider_error(chunk, provider, fallback_from):
                    await self._close_stream_with_provider_error(
                        request, response, provider, model, raw_body, chunk
                    )
                    return response
                if tee_buffer is not None:
                    tee_buffer.append(chunk)
                last_chunk = chunk
                await response.write(chunk)
            try:
                in_t, out_t = _extract_anthropic_usage([first_chunk, last_chunk])
                _log_turn_usage(provider or "", model or "", in_t, out_t)
            except Exception:  # noqa: BLE001 — telemetría best-effort, nunca rompe
                pass
            await response.write_eof()
            return response
        except ConnectionResetError as exc:
            # El cliente (Claude Code) corto la conexion antes de recibir la
            # respuesta — Esc, prompt nuevo encima o timeout del lado del cliente.
            # No es un fallo del proxy ni del backend: se loguea como WARNING sin
            # traceback para no ensuciar como ERROR un cancel benigno.
            _log.warning(
                "conexion reseteada durante stream SSE (provider=%s): %s "
                "— probable cancel del cliente",
                provider or "-",
                exc,
            )
            closed = await self._finalize_stream_after_error(response, prepared)
            if closed is not None:
                return closed
            raise
        except Exception:
            _log.exception("error transmitiendo stream SSE upstream")
            closed = await self._finalize_stream_after_error(response, prepared)
            if closed is not None:
                return closed
            raise

    async def _close_stream_with_provider_error(
        self,
        request: web.Request,
        response: web.StreamResponse,
        provider: str | None,
        model: str | None,
        raw_body: bytes | None,
        chunk: bytes,
    ) -> None:
        """Cierra un stream ya comprometido con un error Anthropic legible.

        Cuando un backend alternativo falla a mitad del stream (después de que el
        HTTP 200 + headers salieron), no se puede hacer fallback transparente. En
        vez de filtrar el chunk crudo —que Claude Code reporta como "error 200"—
        se emite un ``event: error`` bien formado, se registra el fallo para el
        circuit breaker y se deja rastro en el log de errores del upstream.

        Args:
            response: Respuesta ya preparada (headers enviados).
            provider: Backend que falló.
            model: Modelo activo del provider.
            raw_body: Body crudo del request (para el resumen estructural del log).
            chunk: Chunk que delató el error (para la observabilidad).
        """
        _record_provider_failure(provider or "", "status-200-midstream-error")
        _record_routing_outcome(
            request,
            provider or "",
            status_code=500,
        )
        _log_upstream_error(
            provider or "",
            model or "",
            200,
            chunk.decode("utf-8", errors="ignore"),
            raw_body or b"",
        )
        _log.warning(
            "fallo mid-stream del provider %s — cierre legible (no hay fallback "
            "transparente posible post-commit del 200)",
            provider or "-",
        )
        await response.write(
            _anthropic_error_sse(
                f"El proveedor '{provider}' falló a mitad de la respuesta. "
                "Reintentá el prompt o cambiá de provider con /provider.",
                error_type="overloaded_error",
            )
        )
        await response.write_eof()

    async def _fallback_to_claude(
        self,
        request: web.Request,
        session: ClientSession | None,
        raw_body: bytes,
        failed_provider: str,
        reason: str,
    ) -> web.StreamResponse:
        """Reenvia el turno a Claude y registra el rescate en el state.

        Por default es no-sticky: registra el fallback (`record_fallback`) sin cambiar
        el backend, de modo que el proximo prompt reintenta el provider del usuario. Con
        `ANTIGRAVITY_PROXY_FALLBACK_STICKY=1` ademas conmuta el backend a Claude (historico).
        """
        if session is None:
            async with ClientSession(timeout=_proxy_client_timeout()) as owned_session:
                return await self._fallback_to_claude(
                    request,
                    owned_session,
                    raw_body,
                    failed_provider,
                    reason,
                )

        try:
            target = provider_router.resolve_target("claude", dict(request.headers))
        except provider_router.RouterError as exc:
            return web.json_response(
                {
                    "error": f"fallback claude no disponible: {exc}",
                    "fallback_from": failed_provider,
                    "reason": reason,
                },
                status=502,
            )

        if _fallback_sticky_enabled():
            proxy_state.record_fallback(
                failed_provider,
                reason,
                switch_to=("claude", proxy_state.DEFAULT_MODEL),
            )
        else:
            proxy_state.record_fallback(failed_provider, reason)
        _log.warning(
            "fallback automatico a claude: failed_provider=%s reason=%s sticky=%s",
            failed_provider,
            reason,
            _fallback_sticky_enabled(),
        )

        async with session.post(
            target["url"], headers=target["headers"], data=raw_body
        ) as upstream:
            if upstream.status != 200:
                text = await upstream.text()
                _log.error(
                    "fallback claude fallo despues de %s status=%d: %r",
                    failed_provider,
                    upstream.status,
                    text[:1000],
                )
                return web.json_response(
                    {
                        "error": f"fallback claude respondio {upstream.status}",
                        "fallback_from": failed_provider,
                        "reason": reason,
                        "detail": text[:1000],
                    },
                    status=upstream.status,
                )
            return await self._stream_upstream(request, upstream, fallback_from=failed_provider)

    async def _failover_to_next_healthy(
        self,
        request: web.Request,
        session: ClientSession | None,
        raw_body: bytes,
        failed_provider: str,
        reason: str,
        tried: set[str],
    ) -> web.StreamResponse | None:
        """Rota en vivo al próximo provider sano de la cascada tras un fallo in-flight.

        Cuando el provider activo falla con un error de salud (429/5xx) y el auto-failover
        está activo, re-despacha el turno a OTRO alternativo (no solo a Claude) en el mismo
        turno. Recursivo y acotado: cada provider probado se agrega a ``tried`` (tope = la
        cascada), evitando loops. Si el próximo sano es Claude, delega al
        ``_fallback_to_claude`` especializado. Devuelve ``None`` solo si NINGÚN provider de
        la cascada está sano — ahí el caller aplica su manejo histórico.

        Args:
            request: Request entrante.
            session: Sesión aiohttp activa, o ``None`` para que este método abra la suya
                (mismo patrón que ``_fallback_to_claude`` — útil cuando el caller, como
                ``_stream_upstream``, no tiene una sesión en scope).
            raw_body: Body crudo original del turno.
            failed_provider: Provider que acaba de fallar.
            reason: Motivo legible (para logs/state).
            tried: Providers ya intentados en esta cadena (anti-loop).

        Returns:
            La respuesta del primer provider sano que sirva el turno, o ``None``.
        """
        if session is None:
            async with ClientSession(timeout=_proxy_client_timeout()) as owned_session:
                return await self._failover_to_next_healthy(
                    request, owned_session, raw_body, failed_provider, reason, tried
                )
        open_circuits = _open_circuits() | tried | {failed_provider}
        target = provider_cascade.next_healthy_provider(
            failed_provider, open_circuits, provider_cascade.configured_providers()
        )
        if target is None:
            return None
        if target == "claude":
            return await self._fallback_to_claude(
                request, session, raw_body, failed_provider, reason
            )

        model = provider_switch.resolve_provider_model(target)
        _record_auto_recovery("auto_failover_inflight", failed_provider)
        _log.warning(
            "auto-failover in-flight: %s (%s) → %s/%s", failed_provider, reason, target, model
        )
        built = await self._build_proxy_request(request, target, model, raw_body)
        if isinstance(built, web.StreamResponse):
            return built
        new_target, post_kwargs = built
        async with session.post(
            new_target["url"], headers=new_target["headers"], **post_kwargs
        ) as upstream:
            if upstream.status != 200:
                if upstream.status in _CIRCUIT_FAILURE_STATUSES:
                    _record_provider_failure(target, f"status-{upstream.status}")
                _record_routing_outcome(
                    request,
                    target,
                    status_code=upstream.status,
                    retry_after=getattr(upstream, "headers", {}).get("Retry-After"),
                )
                # Rotar al siguiente sano (recursión acotada por `tried`).
                return await self._failover_to_next_healthy(
                    request,
                    session,
                    raw_body,
                    target,
                    f"upstream-{upstream.status}",
                    tried | {target},
                )
            _record_provider_success(target)
            _record_routing_outcome(request, target, status_code=200)
            return await self._stream_upstream(
                request,
                upstream,
                fallback_from=failed_provider,
                raw_body=raw_body,
                provider=target,
                model=model,
            )

    async def _fallback_count_tokens_to_claude(
        self,
        request: web.Request,
        session: ClientSession,
        raw_body: bytes,
        failed_provider: str,
        reason: str,
    ) -> web.StreamResponse:
        """Cuenta tokens con Claude cuando el backend alternativo no soporta el endpoint."""
        try:
            target = provider_router.resolve_target("claude", dict(request.headers))
        except provider_router.RouterError as exc:
            return web.json_response(
                {
                    "error": f"count_tokens fallback claude no disponible: {exc}",
                    "fallback_from": failed_provider,
                    "reason": reason,
                },
                status=502,
            )

        count_url = _messages_count_tokens_url(target["url"])
        _log.warning(
            "count_tokens fallback a claude: failed_provider=%s reason=%s",
            failed_provider,
            reason,
        )
        async with session.post(
            count_url,
            headers=target["headers"],
            data=raw_body,
        ) as upstream:
            body = await upstream.read()
            if upstream.status != 200:
                text = body.decode("utf-8", errors="ignore")
                _log.error(
                    "count_tokens fallback claude fallo despues de %s status=%d: %r",
                    failed_provider,
                    upstream.status,
                    text[:1000],
                )
                return web.json_response(
                    {
                        "error": f"count_tokens fallback claude respondio {upstream.status}",
                        "fallback_from": failed_provider,
                        "reason": reason,
                        "detail": text[:1000],
                    },
                    status=upstream.status,
                )
            return web.Response(
                status=200,
                body=body,
                content_type=upstream.content_type or "application/json",
                headers={"X-Antigravity-Fallback-From": failed_provider},
            )

    async def _build_proxy_request(
        self,
        request: web.Request,
        provider: str,
        model: str,
        raw_body: bytes,
    ) -> tuple[dict[str, Any], dict[str, Any]] | web.StreamResponse:
        """Resuelve el destino upstream y los kwargs de POST para el backend activo.

        Para `claude` reenvia el body crudo; para backends compatibles parsea y
        sanea el JSON antes del passthrough. Maneja inline los caminos de error
        (RouterError, JSON invalido) devolviendo la respuesta HTTP correspondiente.

        Args:
            request: Request entrante de Claude Code.
            provider: Provider activo (`claude`, `glm`, `minimax`, ...).
            model: Modelo activo asociado al provider.
            raw_body: Body crudo del request.

        Returns:
            Una tupla ``(target, post_kwargs)`` lista para `session.post`, o una
            ``web.StreamResponse`` ya resuelta cuando hubo error o fallback.
        """
        if provider == "claude":
            try:
                target = provider_router.resolve_target(provider, dict(request.headers))
                return target, {"data": raw_body}
            except provider_router.RouterError as exc:
                return web.json_response({"error": f"proxy ({provider}): {exc}"}, status=502)

        try:
            payload = json.loads(raw_body)
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            if not _auto_fallback_enabled():
                _log.error(
                    "JSON invalido en body del request: %s | body_len=%d body_preview=%r",
                    exc,
                    len(raw_body),
                    raw_body[:200],
                )
                return web.json_response(
                    {"error": "JSON invalido en el body"},
                    status=400,
                )
            _log.warning(
                "JSON invalido para %s; fallback a claude: %s | body_len=%d body_preview=%r",
                provider,
                exc,
                len(raw_body),
                raw_body[:200],
            )
            async with ClientSession(timeout=_proxy_client_timeout()) as session:
                return await self._fallback_to_claude(
                    request,
                    session,
                    raw_body,
                    provider,
                    f"invalid-json: {exc}",
                )

        # Pre-compactacion PREVENTIVA: si el historial supera el umbral, recortarlo
        # antes de mandarlo al backend alternativo. Evita el 400 por context-limit
        # (MiniMax-M3 ~256k vs el contexto mayor de Claude) y el fallback reactivo.
        if _alt_precompact_enabled():
            messages = payload.get("messages")
            if isinstance(messages, list):
                limit = _alt_precompact_max_messages()
                if len(messages) > limit:
                    payload = dict(payload)
                    payload["messages"] = messages[-limit:]
                    _record_auto_recovery("precompact_alt_provider", provider)
                    _log.info(
                        "pre-compact %s: %d -> %d mensajes (umbral %d)",
                        provider,
                        len(messages),
                        limit,
                        limit,
                    )

        try:
            target = provider_router.resolve_target(provider, dict(request.headers))
        except provider_router.RouterError as exc:
            return web.json_response({"error": f"proxy ({provider}): {exc}"}, status=502)

        # Backends OpenAI-compatible (ollama, lmstudio): el sanitizer asume forma
        # Anthropic (messages con content blocks, tools con input_schema), asi que
        # se salta y se traduce el payload a Chat Completions. El stream de vuelta
        # tambien se traduce en _stream_upstream (ver `openai_stream` mas abajo).
        if provider_router.is_openai_compatible(provider):
            # Reconciliar pares tool_use/tool_result huerfanos ANTES de traducir: el
            # historial puede degenerar tras truncado/hot-swap y los providers OpenAI
            # estrictos (OpenCode Go / Kimi -> "tool_call_id is not found"; MiniMax ->
            # 2013) rechazan un role:tool sin su tool_call. La rama Anthropic ya lo hace
            # via sanitize_anthropic_payload; aca lo aplicamos a mano (el traductor es puro).
            messages = payload.get("messages")
            if isinstance(messages, list):
                payload = {
                    **payload,
                    "messages": message_sanitizer.reconcile_tool_blocks(messages),
                }
            try:
                oai = openai_translator.anthropic_to_openai(payload, model=model, provider=provider)
            except Exception as exc:  # noqa: BLE001 — boundary de traduccion
                _log.error(
                    "falla traducir payload Anthropic->OpenAI (%s): %s | payload_keys=%s",
                    provider,
                    exc,
                    list(payload.keys()),
                )
                return web.json_response(
                    {"error": f"proxy ({provider}): payload no traducible a OpenAI: {exc}"},
                    status=400,
                )
            return target, {"json": oai}

        try:
            sanitized = message_sanitizer.sanitize_anthropic_payload(payload, provider, model)
            return target, {"json": sanitized}
        except provider_router.RouterError as exc:
            return web.json_response({"error": f"proxy ({provider}): {exc}"}, status=502)

    @staticmethod
    def _auto_recovery_limit_response(provider: str) -> web.StreamResponse:
        """Construye la respuesta 429 cuando se agotaron los reintentos de auto-recuperacion.

        Args:
            provider: Provider que alcanzo el limite.

        Returns:
            Respuesta JSON HTTP 429 con el codigo ``AUTO_RECOVERY_LIMIT``.
        """
        _record_auto_recovery("auto_recovery_limit_reached", provider)
        return web.json_response(
            {
                "error": "limite de auto-recuperacion alcanzado",
                "code": "AUTO_RECOVERY_LIMIT",
                "provider": provider,
                "hint": _COMPACT_HINT,
            },
            status=429,
            # Ver _auto_recovery_limit_response module-level: el proxy ya agoto
            # sus rescates, que el cliente no re-reintente encima.
            headers={"x-should-retry": "false"},
        )

    async def _try_auto_compact_retry(
        self,
        request: web.Request,
        session: ClientSession,
        target: dict[str, Any],
        provider: str,
        raw_body: bytes,
        auto_recovery_remaining: int,
    ) -> web.StreamResponse | None:
        """Reintenta el turno con el body compactado tras un error de limite de contexto.

        Args:
            request: Request entrante.
            session: Sesion aiohttp activa.
            target: Destino upstream resuelto (`url`, `headers`).
            provider: Provider activo.
            raw_body: Body crudo original.
            auto_recovery_remaining: Reintentos de auto-recuperacion disponibles.

        Returns:
            La respuesta del reintento si el compactado fue exitoso, el 429 de
            limite si se agotaron reintentos, o ``None`` si no procede compactar.
        """
        compacted_body = _compact_request_body(raw_body)
        if not compacted_body:
            return None
        if auto_recovery_remaining <= 0:
            return self._auto_recovery_limit_response(provider)
        _record_auto_recovery("compact_retry_status_context_limit", provider)
        auto_recovery_remaining -= 1
        async with session.post(
            target["url"],
            headers=target["headers"],
            data=compacted_body,
        ) as retry_upstream:
            if retry_upstream.status == 200:
                return await self._stream_upstream(
                    request,
                    retry_upstream,
                    auto_recovery_remaining=auto_recovery_remaining,
                )
            retry_text = await retry_upstream.text()
            _log.error(
                "auto-compact retry fallo status=%d: %r",
                retry_upstream.status,
                retry_text[:1000],
            )
        return None

    @staticmethod
    def _build_upstream_error_response(
        provider: str,
        status: int,
        text: str,
        retry_after: str | None,
        reset_raw: str | None = None,
    ) -> web.StreamResponse:
        """Construye la respuesta de error final para un upstream con status != 200.

        Args:
            provider: Provider que respondio el error.
            status: Codigo HTTP devuelto por el upstream.
            text: Cuerpo de la respuesta del upstream (truncado en el payload).
            retry_after: Valor de la cabecera ``Retry-After`` si existe.
            reset_raw: Timestamp RFC 3339 de un header ``anthropic-ratelimit-*-reset``
                si existe; se usa para calcular la hora de reset del 429.

        Returns:
            Respuesta JSON con el detalle del error. Para 429 devuelve el formato
            de error NATIVO de Anthropic (``type``/``error.message``) para que
            Claude Code renderice un aviso corto y humanizado, conservando la
            metadata interna (``code``/``retryable``/``hint``) y ``Retry-After``.
        """
        if status == 429:
            provider_count = _increment_provider_rate_limit(provider)
            message = _humanize_rate_limit(reset_raw, retry_after)
            _log.warning(
                "provider rate limit: provider=%s count=%s retry_after=%s reset=%s",
                provider,
                provider_count,
                retry_after,
                reset_raw,
            )
            payload: dict[str, Any] = {
                # Formato de error nativo de Anthropic: Claude Code muestra
                # `error.message` como el aviso visible al usuario.
                "type": "error",
                "error": {"type": "rate_limit_error", "message": message},
                # Metadata interna: Claude Code la ignora, pero Nexus, los logs y
                # los tests del proxy dependen de estos campos.
                "code": "RATE_LIMIT",
                "hint": _COMPACT_HINT,
                "retryable": True,
                "provider_rate_limit_count": provider_count,
            }
            if retry_after:
                payload["retry_after"] = retry_after
            return web.json_response(
                payload,
                status=429,
                headers={
                    **({"Retry-After": retry_after} if retry_after else {}),
                },
            )
        return web.json_response(
            {
                "error": f"backend {provider} respondio {status}",
                "detail": text[:1000],
            },
            status=status,
        )

    async def _try_aggressive_retry(
        self,
        request: web.Request,
        session: ClientSession,
        provider: str,
        model: str,
        raw_body: bytes,
    ) -> web.StreamResponse | None:
        """Reintenta UNA vez con sanitizado agresivo tras un 400 inexplicado.

        Re-sanea el payload con ``aggressive=True`` (purga todo el historial de
        herramientas, deja solo texto) y lo reenvia al mismo backend. Si el retry
        responde 200 hace passthrough del stream; si vuelve a dar 400 -> fallback a
        Claude si esta disponible; si no, error legible al cliente.

        Tope estricto: este metodo se invoca UNA sola vez por request (guard en el
        caller). Sin loops.

        Args:
            request: Request entrante.
            session: Sesion aiohttp activa.
            provider: Provider alternativo que devolvio 400.
            model: Modelo activo del provider.
            raw_body: Body crudo original.

        Returns:
            La respuesta del retry/fallback, o ``None`` si el body no era parseable
            (el caller continua con el error final).
        """
        try:
            payload = json.loads(raw_body)
        except Exception:  # noqa: BLE001 — boundary HTTP
            return None
        if not isinstance(payload, dict):
            return None
        sanitized = message_sanitizer.sanitize_anthropic_payload(
            payload, provider, model, aggressive=True
        )
        try:
            target = provider_router.resolve_target(provider, dict(request.headers))
        except provider_router.RouterError:
            return None
        _record_auto_recovery("aggressive_retry_400", provider)
        _log.warning("retry agresivo (purga tool blocks) para %s tras 400", provider)
        async with session.post(
            target["url"], headers=target["headers"], json=sanitized
        ) as retry_upstream:
            if retry_upstream.status == 200:
                _record_provider_success(provider)
                return await self._stream_upstream(request, retry_upstream)
            retry_text = await retry_upstream.text()
            _log.error(
                "retry agresivo fallo %s status=%d: %r",
                provider,
                retry_upstream.status,
                retry_text[:1000],
            )
        # El retry agresivo tambien fallo: ultimo recurso -> fallback a Claude.
        if _auto_fallback_enabled():
            _record_auto_recovery("aggressive_retry_fallback_claude", provider)
            return await self._fallback_to_claude(
                request, session, raw_body, provider, "aggressive-retry-400"
            )
        message = (
            f"El proveedor {provider} rechazo el historial de la conversacion. "
            "Proba /clear o cambia de modelo."
        )
        return web.json_response(
            {
                # Formato de error nativo de Anthropic: Claude Code muestra
                # `error.message` como el aviso visible al usuario (mismo patron
                # que el 429 en `_build_error_response`).
                "type": "error",
                "error": {"type": "invalid_request_error", "message": message},
                # Metadata interna: Claude Code la ignora; Nexus, logs y tests del
                # proxy dependen de estos campos.
                "code": "HISTORY_REJECTED",
                "provider": provider,
            },
            status=400,
        )

    async def _retry_claude_transient(
        self,
        request: web.Request,
        session: ClientSession,
        target: dict[str, Any],
        raw_body: bytes,
        model: str,
        first_status: int,
    ) -> web.StreamResponse | None:
        """UN reintento del passthrough claude ante un 5xx/529 transitorio.

        El blip de sobrecarga de Anthropic que tumba el clasificador de auto
        mode suele durar menos que un turno: reintentar una sola vez con
        backoff corto lo absorbe sin que Claude Code llegue a ver el error.
        Nada se streameo aun al cliente (estamos en la rama status != 200),
        asi que el re-POST del body crudo es seguro.

        Args:
            request: Request entrante (para el relay del stream).
            session: Sesion aiohttp activa.
            target: Destino claude ya resuelto (`url`, `headers`).
            raw_body: Body crudo original (passthrough sin tocar).
            model: Modelo activo (para el relay del stream).
            first_status: Status del primer intento (solo para el log).

        Returns:
            La respuesta streameada si el reintento respondio 200, o ``None``
            para que el caller continue con el manejo del error original.
        """
        await asyncio.sleep(_CLAUDE_TRANSIENT_RETRY_DELAY_S)
        _log.warning("retry transitorio claude tras status=%d (1 reintento)", first_status)
        try:
            async with session.post(
                target["url"], headers=target["headers"], data=raw_body
            ) as upstream:
                if upstream.status != 200:
                    text = await upstream.text()
                    _log.error(
                        "retry transitorio claude fallo status=%d: %r",
                        upstream.status,
                        text[:500],
                    )
                    return None
                _record_provider_success("claude")
                _record_auto_recovery("claude_transient_retry_ok", "claude")
                return await self._stream_upstream(
                    request,
                    upstream,
                    raw_body=raw_body,
                    provider="claude",
                    model=model,
                    auto_recovery_remaining=0,
                )
        except (OSError, TimeoutError) as exc:
            _log.error("retry transitorio claude fallo por transporte: %s", exc)
            return None

    async def _try_context_overflow_retry(
        self,
        request: web.Request,
        session: ClientSession,
        provider: str,
        model: str,
        raw_body: bytes,
        status: int,
        text: str,
    ) -> web.StreamResponse | None:
        """Reintenta UNA vez contra el MISMO provider con ``max_tokens`` reducido.

        Ante un 400 de un alternativo clasificado como ``context_overflow``
        (``provider_errors.classify_upstream_error``), calcula cuanto
        ``max_tokens`` entra en la ventana restante (o lo reduce a la mitad si
        el error no trae numeros parseables — ver
        ``provider_errors.compute_reduced_max_tokens``) y reintenta UNA vez
        contra el mismo backend, ANTES de caer a la cascada/fallback existente.

        Nunca aplica a ``claude``: el passthrough OAuth ya tiene su propio
        auto-compact retry (``_try_auto_compact_retry``) — duplicarlo aca
        gastaria un reintento extra sin necesidad.

        Args:
            request: Request entrante (para resolver headers/target).
            session: Sesion aiohttp activa.
            provider: Provider alternativo que devolvio el 400.
            model: Modelo activo del provider.
            raw_body: Body crudo original (Anthropic) enviado al backend.
            status: Status HTTP del upstream que fallo.
            text: Cuerpo de la respuesta del upstream.

        Returns:
            La respuesta del retry si tuvo exito (200), o ``None`` si no aplica
            o si el retry tambien fallo — el caller continua con el flujo
            historico de cascada/fallback.
        """
        if provider == "claude":
            return None
        category = provider_errors.classify_upstream_error(status, text)
        if category is not provider_errors.ErrorCategory.CONTEXT_OVERFLOW:
            return None
        try:
            payload = json.loads(raw_body)
        except Exception:  # noqa: BLE001 — boundary HTTP
            return None
        if not isinstance(payload, dict):
            return None
        current_max_tokens = payload.get("max_tokens")
        if not isinstance(current_max_tokens, int) or current_max_tokens <= 0:
            return None
        new_max_tokens = provider_errors.compute_reduced_max_tokens(current_max_tokens, text)
        if new_max_tokens >= current_max_tokens:
            return None

        adjusted_body = json.dumps(
            {**payload, "max_tokens": new_max_tokens}, ensure_ascii=False
        ).encode("utf-8")
        built = await self._build_proxy_request(request, provider, model, adjusted_body)
        if isinstance(built, web.StreamResponse):
            return None
        target, post_kwargs = built

        _record_auto_recovery("context_overflow_max_tokens_retry", provider)
        _log.warning(
            "context-overflow retry %s: max_tokens %d -> %d",
            provider,
            current_max_tokens,
            new_max_tokens,
        )
        async with session.post(
            target["url"], headers=target["headers"], **post_kwargs
        ) as retry_upstream:
            if retry_upstream.status == 200:
                _record_provider_success(provider)
                return await self._stream_upstream(
                    request,
                    retry_upstream,
                    raw_body=adjusted_body,
                    provider=provider,
                    model=model,
                )
            retry_text = await retry_upstream.text()
            _log.error(
                "context-overflow retry fallo %s status=%d: %r",
                provider,
                retry_upstream.status,
                retry_text[:1000],
            )
        return None

    async def _handle_upstream_error(
        self,
        request: web.Request,
        session: ClientSession,
        target: dict[str, Any],
        provider: str,
        raw_body: bytes,
        upstream: Any,
        auto_recovery_remaining: int,
        model: str = "",
        aggressive_retry_remaining: int = 0,
    ) -> web.StreamResponse:
        """Gestiona una respuesta upstream con status != 200 (fallback / compact / error).

        Intenta fallback a Claude o reintento con body compactado segun la
        politica de auto-recuperacion; si nada aplica, devuelve el error final.

        Args:
            request: Request entrante.
            session: Sesion aiohttp activa.
            target: Destino upstream resuelto (`url`, `headers`).
            provider: Provider activo.
            raw_body: Body crudo original.
            upstream: Respuesta upstream con status != 200.
            auto_recovery_remaining: Reintentos de auto-recuperacion disponibles.
            model: Modelo activo del provider (para el retry agresivo y el log).
            aggressive_retry_remaining: Reintentos agresivos disponibles (tope 1).

        Returns:
            La respuesta resultante: fallback, reintento, limite alcanzado o error.
        """
        text = await upstream.text()
        # Captura passiva de cuota desde los headers del error (un 429 suele traer
        # remaining=0): alimenta el auto-rotate proactivo del próximo turno.
        # Gateada por opt-in: con la feature OFF no toca disco en el hot path.
        if provider_cascade.is_auto_failover_enabled():
            _capture_quota_headers(provider, upstream.headers)
        retry_after = upstream.headers.get("Retry-After")
        _record_routing_outcome(
            request,
            provider,
            status_code=upstream.status,
            retry_after=retry_after,
        )
        # Anthropic indica cuando se resetea la ventana de uso via headers RFC 3339;
        # `unified` cubre el limite combinado del plan de suscripcion (ventana 5h).
        reset_raw = (
            upstream.headers.get("anthropic-ratelimit-unified-reset")
            or upstream.headers.get("anthropic-ratelimit-tokens-reset")
            or upstream.headers.get("anthropic-ratelimit-requests-reset")
        )
        _log.error(
            "upstream %s (%s) status=%d: %r",
            provider,
            target["url"],
            upstream.status,
            text[:1000],
        )
        # Observabilidad dedicada del 400 de un alternativo: log estructural sin
        # secretos para diagnosticar por que rechazo el historial.
        if provider != "claude" and upstream.status == 400:
            _log_upstream_error(provider, model, upstream.status, text, raw_body)
        # Solo los fallos de SALUD (429/5xx) alimentan el breaker; los 4xx de
        # payload son por-request y no dicen nada del estado del backend.
        if upstream.status in _CIRCUIT_FAILURE_STATUSES:
            _record_provider_failure(provider, f"status-{upstream.status}")
        # Passthrough claude con blip de sobrecarga: UN reintento antes de
        # devolver el error (que tumba el clasificador de auto mode del cliente).
        if (
            provider == "claude"
            and upstream.status in _CLAUDE_TRANSIENT_RETRY_STATUSES
            and _claude_transient_retry_enabled()
        ):
            retried = await self._retry_claude_transient(
                request, session, target, raw_body, model, upstream.status
            )
            if retried is not None:
                return retried
        # Auto-failover in-flight (opt-in): ante un fallo de salud (429/5xx) del
        # alternativo, rotar al próximo sano de la cascada en este mismo turno —
        # antes de rebotar a Claude. Si la cascada no tiene sano, devuelve None y
        # sigue el manejo histórico.
        if (
            provider != "claude"
            and (
                provider_cascade.is_auto_failover_enabled()
                or _request_uses_routing_v2(request)
            )
            and upstream.status in _FAILOVER_STATUSES
        ):
            rotated = await self._failover_to_next_healthy(
                request, session, raw_body, provider, f"upstream-{upstream.status}", {provider}
            )
            if rotated is not None:
                return rotated
        # Context_overflow de un alternativo: probar PRIMERO el ajuste local de
        # max_tokens (UN retry contra el mismo backend) antes de rebotar a
        # Claude. Si no aplica o vuelve a fallar, sigue el flujo historico.
        if provider != "claude" and upstream.status == 400:
            context_retry = await self._try_context_overflow_retry(
                request, session, provider, model, raw_body, upstream.status, text
            )
            if context_retry is not None:
                return context_retry
        if _should_fallback_to_claude(provider, upstream.status, text):
            if auto_recovery_remaining <= 0:
                return self._auto_recovery_limit_response(provider)
            _record_auto_recovery("fallback_status_context_limit", provider)
            return await self._fallback_to_claude(
                request,
                session,
                raw_body,
                provider,
                f"upstream-{upstream.status}",
            )
        # Red de seguridad ante 400 inexplicado de un alternativo (sin marker de
        # contexto): UN retry agresivo purgando el historial de herramientas. Tope
        # estricto de 1 via aggressive_retry_remaining (guard explicito, sin loops).
        #
        # SOLO si el historial TIENE tool/thinking blocks que purgar: un 400 sobre
        # un payload sin tool blocks es un error de CONFIGURACION del provider
        # (modelo mal escrito, param no soportado), no del historial, y debe volver
        # crudo al usuario (preserva el contrato de _CONTEXT_LIMIT_MARKERS). Purgar
        # un historial sin tools no cambiaria nada -> reintentar seria inutil.
        if (
            provider != "claude"
            and upstream.status == 400
            and aggressive_retry_remaining > 0
            and _payload_has_tool_history(raw_body)
        ):
            aggressive = await self._try_aggressive_retry(
                request, session, provider, model, raw_body
            )
            if aggressive is not None:
                return aggressive
        if _should_auto_compact_retry(provider, upstream.status, text):
            retried = await self._try_auto_compact_retry(
                request,
                session,
                target,
                provider,
                raw_body,
                auto_recovery_remaining,
            )
            if retried is not None:
                return retried
        return self._build_upstream_error_response(
            provider, upstream.status, text, retry_after, reset_raw
        )

    async def handle_claude_proxy_count_tokens(self, request: web.Request) -> web.StreamResponse:
        """POST /claudeproxy/v1/messages/count_tokens — passthrough Anthropic token count.

        Claude Code llama este endpoint al calcular si el turno cabe antes de enviar
        `/messages`. Si falta, el cliente queda sin preflight al usar el proxy local y
        puede terminar chocando contra el limite duro de 32MB.
        """
        active = proxy_state.get_active()
        provider, model = active["provider"], active["model"]

        # Mismo tope ampliado que /messages: el preflight cuenta tokens del turno
        # completo, que puede superar el 1MB del client_max_size de la app.
        request = request.clone(client_max_size=_proxy_max_body_bytes())
        raw_body = await request.read()
        # Mismo routing por clase que /messages: el preflight debe contar tokens
        # contra el backend que efectivamente va a servir el turno.
        provider, model = _resolve_class_route(provider, model, raw_body)

        # Backends OpenAI-compatible no exponen /v1/messages/count_tokens (endpoint
        # puramente Anthropic). En vez de golpear un 404 y rebotar a Claude, se
        # estima el conteo localmente: Claude Code solo usa este preflight para
        # decidir si el turno cabe antes de enviarlo, asi que un aprox bytes/4
        # (heuristic) es suficiente y evita el roundtrip inutil.
        if provider != "claude" and provider_router.is_openai_compatible(provider):
            estimate = max(1, len(raw_body) // 4)
            return web.json_response({"input_tokens": estimate})

        # Circuito abierto: contar tokens directo contra Claude (mismo criterio
        # que /messages, sin gastar el timeout en el backend caido).
        if _circuit_open(provider) and _auto_fallback_enabled():
            _record_auto_recovery("circuit_open_skip_count_tokens", provider)
            async with ClientSession(timeout=_proxy_client_timeout()) as session:
                return await self._fallback_count_tokens_to_claude(
                    request, session, raw_body, provider, "circuit-open"
                )

        built = await self._build_proxy_request(request, provider, model, raw_body)
        if isinstance(built, web.StreamResponse):
            return built
        target, post_kwargs = built
        count_url = _messages_count_tokens_url(target["url"])

        timeout = _proxy_client_timeout()
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.post(
                    count_url, headers=target["headers"], **post_kwargs
                ) as upstream:
                    body = await upstream.read()
                    if upstream.status == 200:
                        return web.Response(
                            status=200,
                            body=body,
                            content_type=upstream.content_type or "application/json",
                        )

                    text = body.decode("utf-8", errors="ignore")
                    _log.error(
                        "count_tokens upstream %s (%s) status=%d: %r",
                        provider,
                        count_url,
                        upstream.status,
                        text[:1000],
                    )
                    if (
                        provider != "claude"
                        and _auto_fallback_enabled()
                        and upstream.status in _COUNT_TOKENS_FALLBACK_STATUSES
                    ):
                        return await self._fallback_count_tokens_to_claude(
                            request,
                            session,
                            raw_body,
                            provider,
                            f"count_tokens-upstream-{upstream.status}",
                        )
                    retry_after = upstream.headers.get("Retry-After")
                    return self._build_upstream_error_response(
                        provider, upstream.status, text, retry_after
                    )
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            _log.exception("error en count_tokens proxy hacia %s", provider)
            return web.json_response(
                {"error": f"count_tokens proxy ({provider}) fallo: {exc}"}, status=502
            )

    async def handle_claude_proxy(self, request: web.Request) -> web.StreamResponse:
        """POST /claudeproxy/v1/messages — proxy Anthropic con backend mutable.

        Lee el backend activo. Para Claude nativo reenvia el body crudo; para
        backends compatibles sanea JSON antes del passthrough SSE.
        """
        active = proxy_state.get_active()
        provider, model = active["provider"], active["model"]
        auto_recovery_remaining = _auto_recovery_max_retries()
        trace_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Antigravity-Trace-Id")
            or f"route-{uuid.uuid4().hex}"
        )

        # El client_max_size de la app (1MB, hardening REST) aplicaria en read();
        # las rutas del proxy necesitan el limite real de la API (32MB).
        request = request.clone(client_max_size=_proxy_max_body_bytes())
        request["antigravity_trace_id"] = trace_id
        request["antigravity_routing_v2"] = bool(
            request.headers.get("X-Antigravity-Route")
        )
        raw_body = await request.read()
        if routing_authority.routing_enabled():
            try:
                decision = routing_authority.get_routing_authority().resolve_request(
                    raw_body,
                    provider,
                    model,
                    trace_id=trace_id,
                    route_hint=request.headers.get("X-Antigravity-Route"),
                )
                if decision is not None:
                    request["antigravity_routing_v2"] = True
                    provider, model = decision.provider, decision.model
                    _log.info(
                        "routing v2: trace=%s route=%s -> %s/%s score=%.3f manual=%s",
                        trace_id,
                        decision.route,
                        provider,
                        model,
                        decision.score,
                        decision.manual,
                    )
                else:
                    provider, model = _resolve_class_route(provider, model, raw_body)
            except (RuntimeError, ValueError) as exc:
                _log.warning("routing v2 degradado a provider activo: %s", exc)
                provider, model = _resolve_class_route(provider, model, raw_body)
        else:
            provider, model = _resolve_class_route(provider, model, raw_body)

        # Auto-failover (opt-in): si el provider activo tiene el circuito abierto,
        # rerutear al proximo sano de la cascada en vez de rebotar siempre a Claude.
        provider, model = _failover_reroute(provider, model, raw_body)

        # Circuito abierto: no pagar el timeout contra un backend caido — rescate
        # directo a Claude (o 503 explicito si el auto-fallback esta apagado).
        if _circuit_open(provider):
            _record_auto_recovery("circuit_open_skip", provider)
            if _auto_fallback_enabled():
                return await self._fallback_to_claude(
                    request, None, raw_body, provider, "circuit-open"
                )
            return web.json_response(
                {
                    "error": f"backend {provider} con circuito abierto (fallos consecutivos)",
                    "code": "CIRCUIT_OPEN",
                    "provider": provider,
                    "hint": "Reintentar tras el cooldown o cambiar de provider.",
                },
                status=503,
            )

        built = await self._build_proxy_request(request, provider, model, raw_body)
        if isinstance(built, web.StreamResponse):
            return built
        target, post_kwargs = built

        # Shadow mode: duplicar el turno al alternativo en paralelo (nunca bloquea
        # ni afecta la respuesta real; el resultado va al shadow log).
        shadow_plan = _plan_shadow(provider, raw_body)
        shadow_task: asyncio.Task[dict] | None = None
        tee_buffer: list[bytes] | None = None
        turn_start = time.monotonic()
        if shadow_plan is not None:
            _SHADOW_TOTAL["started"] += 1
            shadow_task = asyncio.create_task(_run_shadow(dict(request.headers), shadow_plan))
            tee_buffer = []

        timeout = _proxy_client_timeout()
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.post(
                    target["url"], headers=target["headers"], **post_kwargs
                ) as upstream:
                    if upstream.status != 200:
                        return await self._handle_upstream_error(
                            request,
                            session,
                            target,
                            provider,
                            raw_body,
                            upstream,
                            auto_recovery_remaining,
                            model=model,
                            aggressive_retry_remaining=1,
                        )
                    _record_provider_success(provider)
                    _record_routing_outcome(
                        request,
                        provider,
                        status_code=200,
                        latency_ms=round((time.monotonic() - turn_start) * 1000),
                    )
                    return await self._stream_upstream(
                        request,
                        upstream,
                        raw_body=raw_body,
                        provider=provider,
                        model=model,
                        auto_recovery_remaining=auto_recovery_remaining,
                        tee_buffer=tee_buffer,
                    )
        except ConnectionResetError as exc:
            # Cancel del cliente propagado desde _stream_upstream antes de
            # preparar la respuesta. 499 (Client Closed Request) distingue este
            # caso del 502 real del backend y evita el ruido de un traceback.
            _log.warning("conexion reseteada por el cliente hacia %s: %s", provider, exc)
            return web.json_response(
                {"error": "cliente cerro la conexion", "code": "CLIENT_DISCONNECT"},
                status=499,
            )
        except Exception as exc:  # noqa: BLE001 — boundary HTTP
            _log.exception("error en proxy hacia %s", provider)
            # Errores de transporte (DNS, conexion rechazada, timeout) son fallos
            # de salud del backend: alimentan el breaker igual que un 5xx.
            _record_provider_failure(provider, f"transport-{type(exc).__name__}")
            _record_routing_outcome(
                request,
                provider,
                error_kind=("timeout" if isinstance(exc, TimeoutError) else "transport"),
                latency_ms=round((time.monotonic() - turn_start) * 1000),
            )
            if (
                provider_cascade.is_auto_failover_enabled()
                or _request_uses_routing_v2(request)
            ):
                rotated = await self._failover_to_next_healthy(
                    request,
                    None,
                    raw_body,
                    provider,
                    f"transport-{type(exc).__name__}",
                    {provider},
                )
                if rotated is not None:
                    return rotated
            return web.json_response(
                {
                    "error": f"proxy ({provider}) fallo antes del primer token",
                    "code": "PROVIDER_TRANSPORT_ERROR",
                    "retryable": True,
                    "trace_id": trace_id,
                },
                status=502,
            )
        finally:
            # El registro shadow se completa fire-and-forget en TODOS los caminos
            # de salida (stream OK, error, cancel): jamas bloquea la respuesta.
            if shadow_task is not None and shadow_plan is not None:
                claude_latency_ms = round((time.monotonic() - turn_start) * 1000)
                _t = asyncio.create_task(
                    _finalize_shadow(shadow_task, tee_buffer or [], shadow_plan, claude_latency_ms)
                )
                _SHADOW_TASKS.add(_t)
                _t.add_done_callback(_on_shadow_done)
