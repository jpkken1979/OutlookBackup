"""Resuelve destino (URL + headers) del backend activo para el proxy."""

from __future__ import annotations

from pathlib import Path

from core import provider_switch

# Headers entrantes que se preservan en el passthrough (match case-insensitive).
_PRESERVE = ("anthropic-version", "anthropic-beta", "content-type", "accept")

# Para backends alternativos (MiniMax/ZAI) NO se reenvia `anthropic-beta`:
# Claude Code manda betas experimentales (interleaved-thinking, fine-grained-tool-
# streaming, etc.) que los endpoints Anthropic-compatible de terceros no conocen
# y suelen rechazar con 400. `anthropic-version` si se preserva.
_PRESERVE_ALT = ("anthropic-version", "content-type", "accept")

# Headers hop-by-hop / de transporte que NUNCA deben reenviarse al upstream: aiohttp
# recalcula Host y Content-Length, y heredarlos malforma la request (el Content-Length
# queda desfasado tras reescribir el modelo y el upstream cuelga esperando bytes).
_HOP_BY_HOP = frozenset(
    {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-connection",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "accept-encoding",
    }
)


def is_openai_compatible(provider: str) -> bool:
    """True si el backend habla OpenAI Chat Completions (requiere traduccion).

    Deriva del catalogo (`.antigravity/providers.json`): un provider es
    OpenAI-compatible si su `wire == "openai"` y es `routable`. Para estos el proxy
    traduce el payload y el stream via `core.openai_translator`. Los backends
    Anthropic-compatible (claude, minimax, zai) y los no-ruteables (nvidia) devuelven
    False y siguen el path de passthrough/sanitizacion Anthropic existente.

    Args:
        provider: Id del provider (ollama, lmstudio, openrouter, opencode, ...).

    Returns:
        True si requiere traduccion OpenAI<->Anthropic, False si es passthrough Anthropic.
    """
    cfg = provider_switch.PROVIDERS.get(provider)
    return bool(cfg and cfg.wire == "openai" and cfg.routable)


class RouterError(ValueError):
    """Backend desconocido o sin API key configurada."""


def _preserved(incoming: dict, allowed: tuple[str, ...] = _PRESERVE) -> dict:
    """Devuelve los headers entrantes que deben preservarse hacia el backend.

    Args:
        incoming: Headers del request entrante.
        allowed: Whitelist de headers a reenviar (default: passthrough completo;
            usar ``_PRESERVE_ALT`` para backends de terceros).

    Returns:
        Subconjunto de headers a reenviar, con Content-Type garantizado.
    """
    lower = {k.lower(): (k, v) for k, v in incoming.items()}
    out: dict[str, str] = {}
    for name in allowed:
        if name in lower:
            orig_key, val = lower[name]
            out[orig_key] = val
    out.setdefault("Content-Type", "application/json")
    return out


def resolve_target(provider: str, incoming_headers: dict, root: Path | None = None) -> dict:
    """Resuelve {url, headers} del backend activo.

    Args:
        provider: id del backend (claude | zai | ...).
        incoming_headers: headers del request entrante de Claude Code.
        root: raiz del proyecto para leer el .env (default: auto).

    Returns:
        Dict con keys 'url' (endpoint /v1/messages) y 'headers'.

    Raises:
        RouterError: provider desconocido o sin API key.
    """
    root = root or provider_switch.default_root()

    if provider == "claude":
        # Passthrough OAuth: preservamos el auth entrante de Claude Code
        # (authorization Bearer / x-api-key) y los headers anthropic-*, quitando
        # solo los hop-by-hop para que aiohttp recalcule Host y Content-Length.
        headers = {k: v for k, v in incoming_headers.items() if k.lower() not in _HOP_BY_HOP}
        headers.setdefault("Content-Type", "application/json")
        return {"url": "https://api.anthropic.com/v1/messages", "headers": headers}

    cfg = provider_switch.PROVIDERS.get(provider)
    if cfg is None:
        raise RouterError(f"Backend desconocido: {provider}")

    headers = _preserved(incoming_headers, allowed=_PRESERVE_ALT)
    if cfg.api_key_env:
        key = provider_switch.get_api_key_from_env(root, cfg.api_key_env)
        if not key:
            raise RouterError(f"{cfg.api_key_env} no encontrada en {root / '.env'}")
        headers["x-api-key"] = key
        headers["Authorization"] = f"Bearer {key}"

    base = cfg.base_url.rstrip("/")

    # Backends OpenAI-compatible (ollama, lmstudio): endpoint /v1/chat/completions.
    # El proxy traduce el payload y el stream via core.openai_translator. Los locales
    # (ollama en :11434, lmstudio en :1234/v1) no requieren API key; si el usuario
    # configuro una para un remoto (openrouter/kimi futuro), ya quedo en Authorization.
    if is_openai_compatible(provider):
        # LM Studio ya incluye /v1 en su base_url; Ollama no. Normalizamos para no
        # doblar el segmento: si la base ya termina en /v1 lo respetamos.
        if base.endswith("/v1"):
            return {"url": f"{base}/chat/completions", "headers": headers}
        return {"url": f"{base}/v1/chat/completions", "headers": headers}

    return {"url": f"{base}/v1/messages", "headers": headers}
