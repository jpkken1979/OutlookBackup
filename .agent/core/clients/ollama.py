"""Ollama local models client."""

import json
import logging
import os
import time
from collections.abc import AsyncIterator
from typing import Any

from ..llm import BaseLLMClient, LLMConfig, LLMResponse, UsageStats

logger = logging.getLogger("antigravity.llm.clients.ollama")


# =============================================================================
# OLLAMA CLIENT (local models with Tool Use)
# =============================================================================


class OllamaClient(BaseLLMClient):
    """Client for Ollama local models. Supports Tool Use via OpenAI-compatible API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response using Ollama (OpenAI-compatible /v1/chat/completions)."""
        start_time = time.time()

        # Build messages in OpenAI format
        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
        elif system:
            # Prepend system message if not already there
            if not messages or messages[0].get("role") != "system":
                messages = [{"role": "system", "content": system}] + messages

        request_body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        }

        # Ollama supports OpenAI-style function calling for supported models
        if tools:
            request_body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", t.get("parameters", {})),
                    },
                }
                for t in tools
            ]

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx") from None

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            url = f"{self.base_url}/v1/chat/completions"
            resp = await client.post(url, json=request_body)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.time() - start_time) * 1000

        # Extract content
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
        tool_calls: list[dict] = []

        if choice["message"].get("tool_calls"):
            for tc in choice["message"]["tool_calls"]:
                args = tc["function"].get("arguments", "{}")
                tool_calls.append(
                    {
                        "id": tc.get("id", f"call_{len(tool_calls)}"),
                        "name": tc["function"]["name"],
                        "input": json.loads(args) if isinstance(args, str) else args,
                    }
                )

        # Usage stats (Ollama may or may not provide these)
        usage_data = data.get("usage", {})
        usage = UsageStats(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            model=self.config.model,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Local models = free
        )

        self.cost_tracker.record(usage)

        return LLMResponse(
            content=content,
            model=self.config.model,
            usage=usage,
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=tool_calls,
            raw_response=data,
        )

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response using Ollama."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx") from None

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        request_body = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
        }

        async with (
            httpx.AsyncClient(timeout=self.config.timeout) as client,
            client.stream(
                "POST", f"{self.base_url}/v1/chat/completions", json=request_body
            ) as resp,
        ):
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]
