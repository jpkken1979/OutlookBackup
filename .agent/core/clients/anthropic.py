"""Anthropic Claude API client."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from ..llm import BaseLLMClient, LLMConfig, LLMResponse, UsageStats

logger = logging.getLogger("antigravity.llm.clients.anthropic")


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic's Claude API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Lazy load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self.config.api_key)  # type: ignore[assignment]  # anthropic: dep opcional
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Run: pip install anthropic"
                ) from None
        return self._client

    async def _create_with_retry(self, client: Any, request_kwargs: dict) -> Any:
        """Llama a messages.create con reintentos y backoff lineal.

        Args:
            client: Cliente Anthropic.
            request_kwargs: Argumentos de la request.

        Returns:
            La respuesta del API.

        Raises:
            El último error si se agotan los reintentos.
        """
        last_error = None
        for attempt in range(self.config.retry_attempts):
            try:
                return client.messages.create(**request_kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Anthropic API attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        raise last_error or Exception("Failed to get response from Anthropic")

    @staticmethod
    def _extract_content_and_tools(response: Any) -> tuple[str, list[dict]]:
        """Extrae texto y tool_calls de los bloques de contenido de la respuesta.

        Args:
            response: Respuesta del API Anthropic.

        Returns:
            Tupla (texto concatenado, lista de tool_calls).
        """
        content = ""
        tool_calls: list[dict] = []
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
            elif hasattr(block, "type") and block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})
        return content, tool_calls

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response using Claude."""
        client = self._get_client()
        start_time = time.time()

        # Build messages
        if messages is None:
            messages = [{"role": "user", "content": prompt}]

        # Build request
        request_kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }

        if system:
            request_kwargs["system"] = system

        if tools:
            request_kwargs["tools"] = tools

        # Make request with retry
        response = await self._create_with_retry(client, request_kwargs)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Extract content
        content, tool_calls = self._extract_content_and_tools(response)

        # Build usage stats
        usage = UsageStats(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            model=self.config.model,
            latency_ms=latency_ms,
        )
        usage.calculate_cost(self.config.model)

        # Track cost
        self.cost_tracker.record(usage)

        return LLMResponse(
            content=content,
            model=self.config.model,
            usage=usage,
            finish_reason=response.stop_reason or "stop",
            tool_calls=tool_calls,
            raw_response=response,
        )

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response using Claude."""
        client = self._get_client()

        messages = [{"role": "user", "content": prompt}]

        with client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            messages=messages,
            system=system or "",
        ) as stream:
            for text in stream.text_stream:
                yield text
