"""Fetchers de % de cuota restante por provider IA (alimentan ``quota_state``).

Portado de CodexBar (``win-codexbar/electron/providers/``): cada fetcher consulta el
endpoint de uso del provider, parsea el % usado de la ventana principal y escribe la
cuota restante (``100 - usado``) vía ``quota_state.write_provider_quota``. Todo I/O de
red es asíncrono (``aiohttp``, el gateway ya lo usa) con timeout corto. Un fetcher que
falla NO tumba a los demás (``asyncio.gather(return_exceptions=True)``) y deja la cuota
del provider como desconocida (``None`` + ``error``), que el predicado de rotación trata
como "no rotar a ciegas".

Endpoints (paridad CodexBar):
- claude: ``GET https://api.anthropic.com/api/oauth/usage`` (token OAuth de
  ``~/.claude/.credentials.json``), ventana ``five_hour`` como señal principal.
- zai: ``GET https://api.z.ai/api/monitor/usage/quota/limit`` (``ZAI_API_KEY``),
  filtra ``TOKENS_LIMIT``, ``percentage`` = usado.
- minimax: ``GET https://platform.minimax.io/v1/api/openplatform/coding_plan/remains``
  (``MINIMAX_API_KEY``), counts si hay total, si no ``remaining_percent``.
- ollama: local, sin cuota → siempre 100% (red de seguridad).

Opt-in: el loop de polling solo corre si el auto-failover está activo o
``ANTIGRAVITY_PROXY_QUOTA_POLL`` está prendido. Feature OFF = cero llamadas de red.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

# core vive junto a este archivo; quota_state es hermano.
try:
    from core import quota_state
except ImportError:  # pragma: no cover - fallback de boundary de import
    import quota_state  # type: ignore[no-redef]

_HTTP_TIMEOUT_S = 10.0
_DEFAULT_POLL_INTERVAL_MIN = 5

_CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_ZAI_USAGE_URLS = (
    "https://api.z.ai/api/monitor/usage/quota/limit",
    "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
)
_MINIMAX_USAGE_URL = "https://platform.minimax.io/v1/api/openplatform/coding_plan/remains"
_OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
_OLLAMA_VERSION_URL = "http://localhost:11434/api/version"


# ── Helpers de parseo (puros, testeables sin red) ────────────────────────────


def _as_finite(value: object) -> float | None:
    """Convierte un valor a float finito, o ``None`` si no es numérico."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _clamp(value: float) -> float:
    """Satura un porcentaje al rango [0, 100]."""
    return max(0.0, min(100.0, value))


_CLAUDE_FIVE_HOUR_KEYS = ("five_hour", "fiveHour")
_CLAUDE_SEVEN_DAY_KEYS = ("seven_day", "sevenDay", "weekly")


def _extract_window(payload: dict, keys: tuple[str, ...]) -> dict | None:
    """Busca una ventana de rate-limit por sus claves en las shapes conocidas.

    Args:
        payload: JSON de ``/api/oauth/usage``.
        keys: Claves candidatas de la ventana (root o anidadas en ``rate_limits``).

    Returns:
        El dict de la ventana, o ``None`` si no aparece en ninguna shape.
    """
    rate_limits = payload.get("rate_limits")
    nested: dict = rate_limits if isinstance(rate_limits, dict) else {}
    camel_rate_limits = payload.get("rateLimits")
    nested_camel: dict = camel_rate_limits if isinstance(camel_rate_limits, dict) else {}
    for key in keys:
        win = payload.get(key) or nested.get(key) or nested_camel.get(key)
        if isinstance(win, dict):
            return win
    return None


def _window_used_pct(window: dict) -> float | None:
    """% usado [0, 100] de una ventana de rate-limit (utilization/percentage o used/limit)."""
    for key in ("utilization", "percentage", "used_percent", "usedPercent"):
        val = _as_finite(window.get(key))
        if val is not None:
            return _clamp(val)
    used = _as_finite(window.get("used"))
    limit = _as_finite(window.get("limit") or window.get("max"))
    if used is not None and limit is not None and limit > 0:
        return _clamp(used / limit * 100.0)
    return None


def parse_claude_windows(payload: dict) -> tuple[float | None, float | None]:
    """Extrae el % usado de las ventanas de 5h y semanal de la respuesta OAuth de Claude.

    El plan ``max`` topea por DOS ventanas simultáneas: la de 5 horas y la de 7 días.
    La rotación por cuota debe mirar la MÁS agotada (la que ata), así que se devuelven
    ambas y el caller toma el máximo uso.

    Args:
        payload: JSON de ``/api/oauth/usage``.

    Returns:
        Tupla ``(five_hour_used_pct, seven_day_used_pct)``; cada elemento es el % usado
        [0, 100] de su ventana, o ``None`` si esa ventana no se pudo resolver.
    """
    if not isinstance(payload, dict):
        return None, None
    five = _extract_window(payload, _CLAUDE_FIVE_HOUR_KEYS)
    seven = _extract_window(payload, _CLAUDE_SEVEN_DAY_KEYS)
    five_pct = _window_used_pct(five) if isinstance(five, dict) else None
    seven_pct = _window_used_pct(seven) if isinstance(seven, dict) else None
    return five_pct, seven_pct


def parse_claude_used_percent(payload: dict) -> float | None:
    """Extrae el % usado de la ventana ``five_hour`` (back-compat; reusa ``parse_claude_windows``).

    Args:
        payload: JSON de ``/api/oauth/usage``.

    Returns:
        % usado [0, 100] de la ventana de 5h, o ``None`` si no se pudo resolver.
    """
    return parse_claude_windows(payload)[0]


def parse_zai_used_percent(payload: dict) -> float | None:
    """Extrae el % usado del límite de tokens (``TOKENS_LIMIT``) de la respuesta z.ai.

    Args:
        payload: JSON de ``/api/monitor/usage/quota/limit``.

    Returns:
        % usado [0, 100] del límite de tokens principal, o ``None`` si no aplica.
    """
    if not isinstance(payload, dict):
        return None
    limits = ((payload.get("data") or {}).get("limits")) or []
    if not isinstance(limits, list):
        return None
    token_limits = [
        lim for lim in limits if isinstance(lim, dict) and lim.get("type") == "TOKENS_LIMIT"
    ]
    if not token_limits:
        return None

    def _is_five_hour(lim: dict) -> bool:
        return _as_finite(lim.get("unit")) == 3 and _as_finite(lim.get("number")) == 5

    def _is_weekly(lim: dict) -> bool:
        return _as_finite(lim.get("unit")) == 6

    # z.ai topea por la ventana de 5h Y la semanal (unit=6): la que ata es la de mayor
    # % usado. Se consideran AMBAS y se toma el máximo (más usado = menos restante).
    binding: list[float] = []
    five = next((lim for lim in token_limits if _is_five_hour(lim)), None)
    weekly = next((lim for lim in token_limits if _is_weekly(lim)), None)
    for lim in (five, weekly):
        if lim is None:
            continue
        pct = _as_finite(lim.get("percentage"))
        if pct is not None:
            binding.append(_clamp(pct))
    if binding:
        return max(binding)
    # Ninguna ventana conocida: caer al primer token-limit no-semanal disponible.
    primary = next((lim for lim in token_limits if not _is_weekly(lim)), None) or token_limits[0]
    pct = _as_finite(primary.get("percentage"))
    # Si hay TOKENS_LIMIT pero sin `percentage` numerico, NO asumir 0% usado
    # (=100% restante): devolver None ("desconocido") para no rotar a z.ai a ciegas.
    return _clamp(pct) if pct is not None else None


def _minimax_record_used_pct(record: dict) -> float | None:
    """% usado [0, 100] de UN record de ``model_remains`` (counts si hay total, si no %).

    Replica ``minimax/index.ts::parseModel`` por record: prioriza los counts si hay un
    total real (``current_interval_total_count > 0``); si no, usa
    ``current_interval_remaining_percent``.

    Args:
        record: Dict de un modelo/ventana del plan de coding.

    Returns:
        % usado [0, 100], o ``None`` si el record no trae datos de uso.
    """
    if not isinstance(record, dict):
        return None
    total = _as_finite(record.get("current_interval_total_count"))
    used_count = _as_finite(record.get("current_interval_usage_count"))
    if total is not None and used_count is not None and total > 0:
        return _clamp((used_count / total) * 100.0)
    remaining_pct = _as_finite(record.get("current_interval_remaining_percent"))
    if remaining_pct is not None:
        return _clamp(100.0 - remaining_pct)
    return None


def parse_minimax_used_percent(payload: dict) -> float | None:
    """Extrae el % usado del plan de coding de MiniMax (la ventana MÁS restrictiva).

    Recorre TODOS los records de ``model_remains`` y devuelve el de MAYOR % usado: con
    varias ventanas/planes, la que ata es la más agotada (menos restante). Mantiene
    back-compat con la forma legacy (campos de uso en el root).

    Args:
        payload: JSON de ``/coding_plan/remains``.

    Returns:
        % usado [0, 100] de la ventana más restrictiva, o ``None`` si ninguna resuelve.
    """
    if not isinstance(payload, dict):
        return None
    models = payload.get("model_remains")
    if isinstance(models, list) and models:
        records = [m for m in models if isinstance(m, dict)]
    else:
        # Forma legacy: campos en el root.
        records = [payload]
    used_pcts = [pct for record in records if (pct := _minimax_record_used_pct(record)) is not None]
    return max(used_pcts) if used_pcts else None


# ── Credenciales / API keys ──────────────────────────────────────────────────


_CLAUDE_TOKEN_EXPIRY_SKEW_S = 60.0


def _read_claude_creds() -> dict | None:
    """Lee el dict crudo de credenciales OAuth de ``~/.claude/.credentials.json``.

    Returns:
        El dict de credenciales, o ``None`` si el archivo falta, está corrupto o no es dict.
    """
    cred_path = Path.home() / ".claude" / ".credentials.json"
    try:
        raw = json.loads(cred_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _read_claude_oauth_token() -> str | None:
    """Lee el access token OAuth de Claude desde ``~/.claude/.credentials.json``.

    Returns:
        El access token, o ``None`` si el archivo falta, está corrupto o sin token.
    """
    raw = _read_claude_creds()
    if raw is None:
        return None
    oauth = raw.get("claudeAiOauth")
    token = None
    if isinstance(oauth, dict):
        token = oauth.get("accessToken")
    token = token or raw.get("access_token")
    return str(token) if token else None


def _parse_epoch_seconds(value: object) -> float | None:
    """Normaliza un instante (epoch ms/s o ISO-8601) a epoch en SEGUNDOS, o ``None``.

    Heurística defensiva: un número ``>= 1e12`` se interpreta como MILISEGUNDOS (lo
    típico en las creds de Claude Code), uno menor como segundos. Un string numérico
    sigue la misma regla; un string no numérico se intenta parsear como ISO-8601.

    Args:
        value: Valor crudo de ``expiresAt`` (int/float epoch ms o s, o string ISO).

    Returns:
        Epoch en segundos (float), o ``None`` si no se pudo resolver.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num / 1000.0 if num >= 1e12 else num
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            num = float(text)
            return num / 1000.0 if num >= 1e12 else num
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _claude_token_is_expired(creds: dict) -> bool:
    """True si el token OAuth de Claude está expirado (con skew defensivo de ~60s).

    Lee ``claudeAiOauth.expiresAt`` (o ``expiresAt`` en root) y lo interpreta
    defensivamente vía ``_parse_epoch_seconds`` (ms / s / ISO). Si no se puede resolver
    un instante de expiración, devuelve ``False`` (no bloquear por una shape desconocida:
    la captura passiva de headers cubre igual el caso de uso activo).

    Args:
        creds: Dict de credenciales OAuth (``claudeAiOauth`` anidado).

    Returns:
        True si ``expiresAt`` es resoluble y ya pasó (descontando el skew).
    """
    oauth = creds.get("claudeAiOauth")
    raw = oauth.get("expiresAt") if isinstance(oauth, dict) else None
    if raw is None:
        raw = creds.get("expiresAt")
    expires_at = _parse_epoch_seconds(raw)
    if expires_at is None:
        return False
    return time.time() >= (expires_at - _CLAUDE_TOKEN_EXPIRY_SKEW_S)


def _read_api_key(key_name: str) -> str | None:
    """Resuelve una API key desde ``os.environ`` o el ``.env`` del repo.

    Args:
        key_name: Nombre de la env var (p. ej. ``ZAI_API_KEY``).

    Returns:
        El valor de la key, o ``None`` si no está en env ni en el ``.env``.
    """
    value = os.environ.get(key_name)
    if value and value.strip():
        return value.strip()
    root = os.environ.get("ANTIGRAVITY_ROOT")
    env_path = Path(root) / ".env" if root else Path(__file__).resolve().parents[2] / ".env"
    try:
        content = env_path.read_text(encoding="utf-8")
    except OSError:
        return None
    prefix = f"{key_name}="
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        return line[len(prefix) :].strip().strip('"').strip("'") or None
    return None


# ── Fetchers async (red) ─────────────────────────────────────────────────────


async def _get_json(session: aiohttp.ClientSession, url: str, headers: dict[str, str]) -> dict:
    """GET que devuelve JSON dict, levantando para status != 2xx."""
    async with session.get(url, headers=headers) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    return data if isinstance(data, dict) else {}


async def fetch_claude(session: aiohttp.ClientSession) -> None:
    """Consulta la cuota de Claude (OAuth) y la persiste en ``quota_state``."""
    token = _read_claude_oauth_token()
    if not token:
        quota_state.write_provider_quota(
            "claude",
            remaining_percent=None,
            source="poll",
            error="sin credenciales OAuth en ~/.claude/.credentials.json",
        )
        return
    # No pegarle a la red con un token expirado: Claude Code lo refresca al USARLO, no
    # acá. Marcar desconocido y salir (la captura passiva de headers cubre el uso activo).
    creds = _read_claude_creds()
    if creds is not None and _claude_token_is_expired(creds):
        quota_state.write_provider_quota(
            "claude",
            remaining_percent=None,
            source="poll",
            error="token OAuth expirado (Claude Code lo refresca al usarlo)",
        )
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "Antigravity/1.0",
    }
    try:
        payload = await _get_json(session, _CLAUDE_USAGE_URL, headers)
    except Exception as exc:  # noqa: BLE001 — boundary de red, degradar a desconocido
        quota_state.write_provider_quota(
            "claude", remaining_percent=None, source="poll", error=str(exc)[:200]
        )
        return
    used_five, used_seven = parse_claude_windows(payload)
    # La ventana que ata es la MÁS usada (menos restante). Si solo una está disponible,
    # se usa esa; si ninguna, la cuota queda desconocida.
    candidates = [
        (win, pct)
        for win, pct in (("five_hour", used_five), ("seven_day", used_seven))
        if pct is not None
    ]
    if candidates:
        window, used = max(candidates, key=lambda c: c[1])
        remaining: float | None = round(100.0 - used, 4)
        error: str | None = None
    else:
        window, used, remaining = "five_hour", None, None
        error = "respuesta sin ventana five_hour/seven_day"
    quota_state.write_provider_quota(
        "claude",
        remaining_percent=remaining,
        used_percent=used,
        window=window,
        source="poll",
        error=error,
    )


async def fetch_zai(session: aiohttp.ClientSession) -> None:
    """Consulta la cuota de z.ai (GLM) y la persiste en ``quota_state``."""
    api_key = _read_api_key("ZAI_API_KEY")
    if not api_key:
        quota_state.write_provider_quota(
            "zai", remaining_percent=None, source="poll", error="ZAI_API_KEY ausente"
        )
        return
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Antigravity/1.0",
    }
    last_error: str | None = None
    for url in _ZAI_USAGE_URLS:
        try:
            payload = await _get_json(session, url, headers)
        except Exception as exc:  # noqa: BLE001 — probar el siguiente endpoint
            last_error = str(exc)[:200]
            continue
        used = parse_zai_used_percent(payload)
        remaining = None if used is None else round(100.0 - used, 4)
        quota_state.write_provider_quota(
            "zai",
            remaining_percent=remaining,
            used_percent=used,
            window="five_hour",
            source="poll",
            error=None if used is not None else "respuesta sin TOKENS_LIMIT",
        )
        return
    quota_state.write_provider_quota(
        "zai", remaining_percent=None, source="poll", error=last_error or "fetch fallido"
    )


async def fetch_minimax(session: aiohttp.ClientSession) -> None:
    """Consulta la cuota de MiniMax y la persiste en ``quota_state``."""
    api_key = _read_api_key("MINIMAX_API_KEY")
    if not api_key:
        quota_state.write_provider_quota(
            "minimax",
            remaining_percent=None,
            source="poll",
            error="MINIMAX_API_KEY ausente",
        )
        return
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "Antigravity/1.0",
    }
    try:
        payload = await _get_json(session, _MINIMAX_USAGE_URL, headers)
    except Exception as exc:  # noqa: BLE001 — boundary de red
        quota_state.write_provider_quota(
            "minimax", remaining_percent=None, source="poll", error=str(exc)[:200]
        )
        return
    used = parse_minimax_used_percent(payload)
    remaining = None if used is None else round(100.0 - used, 4)
    quota_state.write_provider_quota(
        "minimax",
        remaining_percent=remaining,
        used_percent=used,
        window="five_hour",
        source="poll",
        error=None if used is not None else "respuesta sin datos de uso",
    )


def parse_openrouter_remaining_pct(payload: dict) -> float | None:
    """Extrae el % de creditos restantes de la respuesta de OpenRouter.

    OpenRouter expone ``GET /api/v1/credits`` → ``{"data": {"total_credits", "total_usage"}}``
    (probe en vivo, ver ``discovery_provider_quota_endpoints.md``). El % restante es
    ``(total_credits - total_usage) / total_credits * 100``.

    Args:
        payload: JSON de ``/api/v1/credits``.

    Returns:
        % restante [0, 100], o ``None`` si falta el dato o ``total_credits`` no es > 0
        (cuenta sin tope claro → no rotar a ciegas).
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    total = _as_finite(data.get("total_credits"))
    used = _as_finite(data.get("total_usage"))
    if total is None or used is None or total <= 0:
        return None
    return _clamp((total - used) / total * 100.0)


async def fetch_openrouter(session: aiohttp.ClientSession) -> None:
    """Consulta los creditos restantes de OpenRouter y los persiste en ``quota_state``.

    Unico provider proxy-ruteable con endpoint de balance por API key confirmado
    (ver ``discovery_provider_quota_endpoints.md``).
    """
    api_key = _read_api_key("OPENROUTER_API_KEY")
    if not api_key:
        quota_state.write_provider_quota(
            "openrouter",
            remaining_percent=None,
            source="poll",
            error="OPENROUTER_API_KEY ausente",
        )
        return
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "Antigravity/1.0",
    }
    try:
        payload = await _get_json(session, _OPENROUTER_CREDITS_URL, headers)
    except Exception as exc:  # noqa: BLE001 — boundary de red
        quota_state.write_provider_quota(
            "openrouter", remaining_percent=None, source="poll", error=str(exc)[:200]
        )
        return
    remaining = parse_openrouter_remaining_pct(payload)
    quota_state.write_provider_quota(
        "openrouter",
        remaining_percent=remaining,
        window="credits",
        source="poll",
        error=None if remaining is not None else "respuesta sin total_credits>0",
    )


async def fetch_ollama(session: aiohttp.ClientSession) -> None:
    """Reporta la cuota de Ollama (local): 100% si responde, 0% si está caído.

    Ollama no tiene límite de cuota, PERO si el server no responde no es un destino
    válido de rotación. Marcarlo 0% cuando el ping a ``/api/version`` falla lo excluye
    automáticamente del predicado de umbral (no rotar a un local caído). Si responde
    OK → 100% (red de seguridad final de la cascada).
    """
    error: str | None = None
    alive = True
    try:
        async with session.get(_OLLAMA_VERSION_URL) as resp:
            if resp.status >= 400:
                error = f"ollama status {resp.status}"
                alive = False
    except Exception as exc:  # noqa: BLE001 — local, best-effort
        error = f"ollama no responde: {str(exc)[:120]}"
        alive = False
    quota_state.write_provider_quota(
        "ollama",
        remaining_percent=100.0 if alive else 0.0,
        window="local",
        source="local",
        error=error,
    )


async def poll_all() -> None:
    """Corre todos los fetchers en paralelo; un fallo no tumba a los demás."""
    timeout = aiohttp.ClientTimeout(total=_HTTP_TIMEOUT_S)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        results = await asyncio.gather(
            fetch_claude(session),
            fetch_zai(session),
            fetch_minimax(session),
            fetch_openrouter(session),
            fetch_ollama(session),
            return_exceptions=True,
        )
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("usage_poller: un fetcher falló: %s", result)


# ── Loop de polling (gateway lo arranca en background) ───────────────────────


def _poll_interval_min() -> int:
    """Intervalo del loop en minutos (override por ``ANTIGRAVITY_PROXY_QUOTA_POLL_INTERVAL_MIN``)."""
    raw = os.environ.get(
        "ANTIGRAVITY_PROXY_QUOTA_POLL_INTERVAL_MIN", str(_DEFAULT_POLL_INTERVAL_MIN)
    )
    try:
        parsed = int(raw)
    except ValueError:
        parsed = _DEFAULT_POLL_INTERVAL_MIN
    return max(1, min(parsed, 1440))


def is_poll_enabled() -> bool:
    """Indica si el polling de cuota debe correr (opt-in).

    Habilitado si ``ANTIGRAVITY_PROXY_QUOTA_POLL`` está prendido, o si el auto-failover
    está activo (la cuota es su señal). Default OFF: feature apagada = cero red.

    Returns:
        True si el loop debe pollear en esta iteración.
    """
    raw = os.environ.get("ANTIGRAVITY_PROXY_QUOTA_POLL", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    try:
        from core import provider_cascade

        return provider_cascade.is_auto_failover_enabled()
    except Exception:  # noqa: BLE001 — boundary de import; sin señal, OFF
        return False


async def start_poll_loop(interval_min: int | None = None) -> None:
    """Loop que pollea la cuota cada ``interval_min`` minutos mientras esté habilitado.

    Re-evalúa ``is_poll_enabled()`` en cada iteración, de modo que prender el
    auto-failover en Nexus (en caliente) activa el polling sin reiniciar el gateway.
    Cuando está deshabilitado, solo duerme (cero red). Best-effort: cualquier error
    de un ciclo se loguea y el loop continúa.

    Args:
        interval_min: Intervalo en minutos; ``None`` lee el del entorno.
    """
    while True:
        try:
            if is_poll_enabled():
                await poll_all()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — un ciclo malo no debe matar el loop
            logger.warning("usage_poller: ciclo de polling falló: %s", exc)
        minutes = interval_min if interval_min is not None else _poll_interval_min()
        await asyncio.sleep(minutes * 60)
