# mypy: ignore-errors
"""Auto-deteccion de proveedor LLM segun el entorno.

Extraido del monolito ``autonomous_loop.py`` (refactor 2026-05-31). Sin cambios
de comportamiento; los imports relativos a ``core`` pasaron de ``.`` a ``..``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("antigravity.autonomous")


# Default models per provider (models with good Tool Use support)
_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.1",
}

# Provider detection order: cloud APIs first, then local
_PROVIDER_ENV_KEYS = [
    ("anthropic", ["ANTHROPIC_API_KEY"]),
    ("openai", ["OPENAI_API_KEY"]),
    ("gemini", ["GEMINI_API_KEY", "GOOGLE_API_KEY"]),
    ("ollama", ["OLLAMA_BASE_URL"]),  # Ollama doesn't need an API key, just needs to be running
]


def detect_best_provider(
    provider_override: str | None = None,
    model_override: str | None = None,
) -> Any:
    """
    Auto-detect the best available LLM provider based on environment variables.

    Priority: explicit override > Anthropic > OpenAI > Gemini > Ollama > Mock

    Args:
        provider_override: Force a specific provider
        model_override: Override model name

    Returns:
        LLMConfig with the best available provider
    """
    try:
        from llm import LLMConfig, LLMProvider
    except ImportError:
        from ..llm import LLMConfig, LLMProvider

    # Explicit override
    if provider_override:
        provider = LLMProvider(provider_override)
        model = model_override or _DEFAULT_MODELS.get(provider_override, "")
        return LLMConfig(provider=provider, model=model)

    # Auto-detect from environment
    for provider_name, env_keys in _PROVIDER_ENV_KEYS:
        for key in env_keys:
            if os.environ.get(key):
                provider = LLMProvider(provider_name)
                model = model_override or _DEFAULT_MODELS[provider_name]
                return LLMConfig(provider=provider, model=model)

    # Check if Ollama is running locally (no env var needed)
    try:
        import httpx

        # Quick sync check - don't block long
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            # Pick first available model; fall back to hardcoded default
            if not model_override:
                installed = [m["name"] for m in resp.json().get("models", [])]
                model = installed[0] if installed else _DEFAULT_MODELS["ollama"]
            else:
                model = model_override
            return LLMConfig(provider=LLMProvider.OLLAMA, model=model)
    except Exception as _e:
        logger.debug("Modulo opcional no disponible: %s", _e)

    # Fallback to mock (for testing / no API available)
    logger.warning("No LLM provider detected. Using mock client.")
    return LLMConfig(provider=LLMProvider.MOCK, model="mock")


def get_available_providers() -> list[dict]:
    """
    Return a list of all providers that are currently available.

    Returns:
        List of {provider, available, reason} dicts
    """
    results = []

    for provider_name, env_keys in _PROVIDER_ENV_KEYS:
        found_key = None
        for key in env_keys:
            if os.environ.get(key):
                found_key = key
                break

        if provider_name == "ollama":
            # Ollama is special - check if running
            try:
                import httpx

                resp = httpx.get("http://localhost:11434/api/tags", timeout=2)
                available = resp.status_code == 200
                reason = "running" if available else "not running"
            except Exception as _e:
                available = bool(found_key)
                reason = f"env: {found_key}" if found_key else "not detected"
                logger.debug("Ollama health check failed: %s", _e)
        else:
            available = found_key is not None
            reason = f"env: {found_key}" if found_key else "no API key"

        results.append(
            {
                "provider": provider_name,
                "available": available,
                "reason": reason,
                "default_model": _DEFAULT_MODELS[provider_name],
            }
        )

    return results
