"""OpenAI and OpenAI-compatible API clients."""

import json
import logging
import os
import time
from collections.abc import AsyncIterator
from typing import Any

from ..llm import BaseLLMClient, LLMConfig, LLMResponse, UsageStats

logger = logging.getLogger("antigravity.llm.clients.openai")


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Lazy load OpenAI client. Supports custom base_url for compatible APIs (Z.ai, etc)."""
        if self._client is None:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": self.config.api_key}
                if self.config.base_url:
                    kwargs["base_url"] = self.config.base_url
                self._client = OpenAI(**kwargs)  # type: ignore[assignment]  # openai: dep opcional
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai") from None
        return self._client

    def _convert_tools_to_openai(self, tools: list[dict]) -> list[dict]:
        """Convert unified tool format to OpenAI function calling format."""
        result = []
        for t in tools:
            func = {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", t.get("parameters", {})),
            }
            result.append({"type": "function", "function": func})
        return result

    def _convert_messages_to_openai(self, messages: list[dict], system: str | None) -> list[dict]:
        """Convert unified message format to OpenAI format.

        Handles Anthropic-style tool_result content blocks by converting them
        to OpenAI's tool role messages.
        """
        converted = []
        if system:
            converted.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle Anthropic-style complex content (tool results in user messages)
            if role == "user" and isinstance(content, list):
                converted.extend(self._convert_user_content_list(content))
                continue

            # Handle assistant messages with Anthropic-style tool_use blocks
            if role == "assistant" and isinstance(content, list):
                converted.append(self._convert_assistant_content_list(content))
                continue

            # Simple message passthrough
            converted.append({"role": role, "content": content})

        return converted

    @staticmethod
    def _convert_user_content_list(content: list) -> list[dict]:
        """Convierte bloques de contenido de un mensaje user al formato OpenAI.

        Args:
            content: Lista de bloques estilo Anthropic (tool_result, text, ...).

        Returns:
            Lista de mensajes OpenAI (rol tool o user) derivados de los bloques.
        """
        converted: list[dict] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": item.get("tool_use_id", ""),
                        "content": str(item.get("content", "")),
                    }
                )
            elif isinstance(item, dict) and item.get("type") == "text":
                converted.append({"role": "user", "content": item["text"]})
        return converted

    @staticmethod
    def _convert_assistant_content_list(content: list) -> dict:
        """Convierte bloques de un mensaje assistant al formato OpenAI.

        Args:
            content: Lista de bloques estilo Anthropic (text, tool_use, ...).

        Returns:
            Un unico mensaje OpenAI de rol assistant con content y tool_calls.
        """
        text_parts = []
        tool_calls_list = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item["text"])
                elif item.get("type") == "tool_use":
                    tool_calls_list.append(
                        {
                            "id": item["id"],
                            "type": "function",
                            "function": {
                                "name": item["name"],
                                "arguments": json.dumps(item.get("input", {})),
                            },
                        }
                    )

        oai_msg: dict[str, Any] = {"role": "assistant"}
        if text_parts:
            oai_msg["content"] = "\n".join(text_parts)
        else:
            oai_msg["content"] = None
        if tool_calls_list:
            oai_msg["tool_calls"] = tool_calls_list
        return oai_msg

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response using OpenAI."""
        client = self._get_client()
        start_time = time.time()

        # Build messages
        if messages is None:
            oai_messages = []
            if system:
                oai_messages.append({"role": "system", "content": system})
            oai_messages.append({"role": "user", "content": prompt})
        else:
            oai_messages = self._convert_messages_to_openai(messages, system)

        # Build request
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": oai_messages,
        }

        if tools:
            request_kwargs["tools"] = self._convert_tools_to_openai(tools)

        # Make request
        response = client.chat.completions.create(**request_kwargs)

        latency_ms = (time.time() - start_time) * 1000

        # Extract content
        content = response.choices[0].message.content or ""
        tool_calls = []

        if response.choices[0].message.tool_calls:
            for tc in response.choices[0].message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments),
                    }
                )

        # Build usage stats
        usage = UsageStats(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            model=self.config.model,
            latency_ms=latency_ms,
        )
        usage.calculate_cost(self.config.model)

        self.cost_tracker.record(usage)

        return LLMResponse(
            content=content,
            model=self.config.model,
            usage=usage,
            finish_reason=response.choices[0].finish_reason,
            tool_calls=tool_calls,
            raw_response=response,
        )

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response using OpenAI."""
        client = self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        stream = client.chat.completions.create(
            model=self.config.model, messages=messages, stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def list_models(self) -> list[dict]:
        """List available models from OpenAI-compatible API."""
        client = self._get_client()
        try:
            models = client.models.list()
            return [
                {
                    "id": m.id,
                    "owned_by": getattr(m, "owned_by", "unknown"),
                    "created": getattr(m, "created", None),
                }
                for m in models.data
            ]
        except Exception as e:
            logger.warning("Failed to list models: %s", e)
            return []


# =============================================================================
# OPENROUTER CLIENT (300+ models, free tier available)
# =============================================================================


class OpenRouterClient(OpenAIClient):
    """Client for OpenRouter API. Access 300+ models with one API key.

    Includes free models (model IDs ending in :free).
    Uses OpenAI-compatible API at https://openrouter.ai/api/v1
    """

    def _get_client(self):
        """Load OpenAI client configured for OpenRouter."""
        if self._client is None:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {
                    "api_key": self.config.api_key,
                    "base_url": "https://openrouter.ai/api/v1",
                    "default_headers": {
                        "HTTP-Referer": os.getenv(
                            "OPENROUTER_REFERER", "https://github.com/antigravity"
                        ),
                        "X-Title": "Antigravity Ecosystem",
                    },
                }
                self._client = OpenAI(**kwargs)  # type: ignore[assignment]  # openai: dep opcional
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai") from None
        return self._client


# =============================================================================
# KILO AI GATEWAY CLIENT (300+ models via kilo.ai)
# =============================================================================


class KiloCodeClient(OpenAIClient):
    """Client for Kilo AI Gateway. Access 300+ models via kilo.ai.

    Models use provider/model format (e.g. 'anthropic/claude-sonnet-4.5').
    Free models available. $20 free credits on signup.
    Uses OpenAI-compatible API at https://api.kilo.ai/api/gateway
    """

    def _get_client(self):
        """Load OpenAI client configured for Kilo AI Gateway."""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(  # type: ignore[assignment]  # openai: dep opcional
                    api_key=self.config.api_key,
                    base_url="https://api.kilo.ai/api/gateway",
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai") from None
        return self._client


# =============================================================================
# GITHUB MODELS CLIENT (free with GITHUB_TOKEN login)
# =============================================================================


class GitHubModelsClient(OpenAIClient):
    """Client for GitHub Models - free LLM access with your GitHub account.

    Uses your existing GITHUB_TOKEN for authentication. No separate API key needed.
    Access GPT-4o, GPT-4o-mini, Llama, Mistral, and more for free.
    Rate limits: 50-150 requests/day depending on model.

    Uses OpenAI-compatible API at https://models.inference.ai.azure.com
    """

    def _get_client(self):
        """Load OpenAI client configured for GitHub Models."""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(  # type: ignore[assignment]  # openai: dep opcional
                    api_key=self.config.api_key,
                    base_url="https://models.inference.ai.azure.com",
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai") from None
        return self._client
