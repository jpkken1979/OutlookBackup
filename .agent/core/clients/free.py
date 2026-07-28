"""Free LLM clients (g4f and mock)."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ..llm import BaseLLMClient, LLMConfig, LLMResponse, UsageStats

logger = logging.getLogger("antigravity.llm.clients.free")


# =============================================================================
# FREE CLIENT (g4f - ChatGPT, Claude, Gemini sin API keys)
# =============================================================================


class FreeClient(BaseLLMClient):
    """Client for free LLM access via g4f (GPT4Free).

    No API keys required. Provides access to ChatGPT, Claude, Gemini and more
    through community-maintained providers.

    Supports optional cookie-based auth for premium providers:
        - Set G4F_CHATGPT_COOKIES=path/to/cookies.json for ChatGPT Plus
        - Set G4F_PROVIDER to choose a specific provider (e.g. 'Bing', 'You')

    Note: Less reliable than paid APIs. Providers may change without notice.
    For production workloads, use paid providers (OpenAI, Anthropic, etc).
    Tool use is NOT supported in free mode.
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Lazy load g4f async client with optional cookie auth."""
        if self._client is None:
            try:
                from g4f.client import AsyncClient

                kwargs: dict[str, Any] = {}

                # Optional: load cookies for authenticated access (ChatGPT Plus, etc)
                cookies_path = os.getenv("G4F_CHATGPT_COOKIES")
                if cookies_path:
                    try:
                        import json as _json
                        from pathlib import Path

                        cookie_file = Path(cookies_path)
                        if cookie_file.exists():
                            cookies = _json.loads(cookie_file.read_text(encoding="utf-8"))
                            kwargs["cookies"] = cookies
                            logger.info("g4f: loaded cookies from %s", cookies_path)
                    except (OSError, json.JSONDecodeError, ValueError) as e:
                        logger.warning("g4f: failed to load cookies: %s", e)

                # Optional: specific provider
                provider_name = os.getenv("G4F_PROVIDER")
                if provider_name:
                    try:
                        import g4f.Provider as providers

                        provider = getattr(providers, provider_name, None)
                        if provider:
                            kwargs["provider"] = provider
                            logger.info("g4f: using provider %s", provider_name)
                    except Exception as e:
                        logger.warning("g4f: provider %s not found: %s", provider_name, e)

                self._client = AsyncClient(**kwargs)
            except ImportError:
                raise ImportError(
                    "g4f package not installed. Run: pip install -U g4f[openai]"
                ) from None
        return self._client

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response using free providers via g4f."""
        client = self._get_client()
        start_time = asyncio.get_event_loop().time()

        if tools:
            logger.warning("Tool use is not supported in free mode (g4f). Ignoring tools.")

        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

        model = self.config.model or "gpt-4o-mini"

        last_error = None
        response = None
        for attempt in range(self.config.retry_attempts):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                )
                break
            except Exception as e:
                last_error = e
                logger.warning(f"g4f attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        if response is None:
            raise last_error or Exception("Failed to get response from g4f free providers")

        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        content = response.choices[0].message.content or ""

        # g4f may not provide token counts, estimate from text
        est_input = sum(len(m.get("content", "").split()) for m in messages) * 2
        est_output = len(content.split()) * 2

        usage = UsageStats(
            input_tokens=est_input,
            output_tokens=est_output,
            total_tokens=est_input + est_output,
            model=model,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

        self.cost_tracker.record(usage)

        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            finish_reason="stop",
            raw_response=response,
        )

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response using free providers via g4f."""
        client = self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        model = self.config.model or "gpt-4o-mini"

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def list_models(self) -> list[dict]:
        """List popular models available via g4f."""
        try:
            import g4f.models as models

            result = []
            for name in dir(models):
                obj = getattr(models, name)
                if hasattr(obj, "name") and hasattr(obj, "base_provider"):
                    result.append(
                        {
                            "id": obj.name,
                            "owned_by": getattr(obj, "base_provider", "unknown"),
                        }
                    )
            return result
        except ImportError:
            return [
                {"id": "gpt-4o-mini", "owned_by": "openai"},
                {"id": "gpt-4o", "owned_by": "openai"},
                {"id": "claude-3.5-sonnet", "owned_by": "anthropic"},
                {"id": "gemini-pro", "owned_by": "google"},
            ]


# =============================================================================
# MOCK CLIENT (for testing)
# =============================================================================


class MockLLMClient(BaseLLMClient):
    """Mock client for testing without API calls."""

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a mock response."""
        await asyncio.sleep(0.1)  # Simulate latency

        content = f"[MOCK] Processed: {prompt[:100]}..."

        usage = UsageStats(
            input_tokens=len(prompt.split()) * 2,
            output_tokens=len(content.split()) * 2,
            total_tokens=0,
            model="mock",
            latency_ms=100,
        )
        usage.total_tokens = usage.input_tokens + usage.output_tokens

        return LLMResponse(content=content, model="mock", usage=usage)

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a mock response."""
        words = f"[MOCK] Processing your request about: {prompt[:50]}".split()
        for word in words:
            await asyncio.sleep(0.05)
            yield word + " "
