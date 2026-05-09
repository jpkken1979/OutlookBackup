"""Google Gemini API client."""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from ..llm import BaseLLMClient, LLMConfig, LLMResponse, UsageStats

logger = logging.getLogger("antigravity.llm.clients.gemini")


# =============================================================================
# GEMINI CLIENT
# =============================================================================


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini API. Supports Tool Use natively."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta"

    def _convert_tools_to_gemini(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic-format tool definitions to Gemini format."""
        declarations = []
        for t in tools:
            schema = t.get("input_schema", t.get("parameters", {}))
            # Gemini uses 'parameters' not 'input_schema'
            declarations.append(
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": schema,
                }
            )
        return [{"function_declarations": declarations}]

    def _convert_messages_to_gemini(
        self, messages: list[dict], system: str | None
    ) -> tuple[list[dict], str | None]:
        """Convert OpenAI/Anthropic message format to Gemini contents format."""
        contents = []
        sys_instruction = system

        for msg in messages:
            role = msg.get("role", "user")

            if role == "system":
                sys_instruction = msg.get("content", "")
                continue

            # Map roles: user->user, assistant->model
            gemini_role = "model" if role == "assistant" else "user"

            content = msg.get("content", "")

            # Handle complex content (Anthropic tool_result format)
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append({"text": item["text"]})
                        elif item.get("type") == "tool_result":
                            parts.append(
                                {
                                    "function_response": {
                                        "name": item.get("name", "tool"),
                                        "response": {"content": item.get("content", "")},
                                    }
                                }
                            )
                        elif item.get("type") == "tool_use":
                            parts.append(
                                {
                                    "function_call": {
                                        "name": item["name"],
                                        "args": item.get("input", {}),
                                    }
                                }
                            )
                    else:
                        parts.append({"text": str(item)})
                if parts:
                    contents.append({"role": gemini_role, "parts": parts})
            elif content:
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        return contents, sys_instruction

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response using Gemini."""
        start_time = time.time()

        if messages is None:
            messages = [{"role": "user", "content": prompt}]

        contents, sys_instruction = self._convert_messages_to_gemini(messages, system)

        request_body: dict[str, Any] = {"contents": contents}

        if sys_instruction:
            request_body["system_instruction"] = {"parts": [{"text": sys_instruction}]}

        request_body["generation_config"] = {
            "max_output_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        if tools:
            request_body["tools"] = self._convert_tools_to_gemini(tools)

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx") from None

        url = (
            f"{self.base_url}/models/{self.config.model}:generateContent?key={self.config.api_key}"
        )

        last_error = None
        data = None
        for attempt in range(self.config.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    resp = await client.post(url, json=request_body)
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    import asyncio

                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        if data is None:
            raise last_error or Exception("Failed to get response from Gemini")

        latency_ms = (time.time() - start_time) * 1000

        # Extract content and tool calls
        content = ""
        tool_calls: list[dict] = []

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    content += part["text"]
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append(
                        {
                            "id": f"call_{len(tool_calls)}_{fc['name']}",
                            "name": fc["name"],
                            "input": fc.get("args", {}),
                        }
                    )

        # Usage from Gemini
        usage_meta = data.get("usageMetadata", {})
        usage = UsageStats(
            input_tokens=usage_meta.get("promptTokenCount", 0),
            output_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
            model=self.config.model,
            latency_ms=latency_ms,
        )
        usage.calculate_cost(self.config.model)
        self.cost_tracker.record(usage)

        finish_reason = "stop"
        if candidates:
            finish_reason = candidates[0].get("finishReason", "STOP").lower()

        return LLMResponse(
            content=content,
            model=self.config.model,
            usage=usage,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_response=data,
        )

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response using Gemini (streamGenerateContent)."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx") from None

        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        request_body: dict[str, Any] = {"contents": contents}
        if system:
            request_body["system_instruction"] = {"parts": [{"text": system}]}

        url = (
            f"{self.base_url}/models/{self.config.model}:streamGenerateContent"
            f"?key={self.config.api_key}&alt=sse"
        )

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=request_body) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = json.loads(line[6:])
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield part["text"]
