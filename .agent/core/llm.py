#!/usr/bin/env python3
"""
Antigravity LLM Integration - Real AI execution for agents.

Supports all major LLM providers with Tool Use (function calling):
- Claude API (Anthropic) - Full tool use support
- OpenAI API (GPT-4o, etc) - Full tool use support
- Google Gemini API - Full tool use support
- Ollama (local models) - Tool use via OpenAI-compatible API
- OpenRouter - 300+ models via one API key (has free models)
- Kilo AI Gateway - 300+ models via kilo.ai
- GitHub Models - Free GPT-4o, Llama, Mistral with your GitHub login
- Free (g4f) - Free access to ChatGPT, Claude, Gemini without API keys
- Mock client for testing

All providers use a unified format: tools are defined once in Anthropic's
{name, description, input_schema} format and automatically converted to
each provider's native format by the client layer.

Usage:
    from .llm import LLMClient, LLMConfig, LLMProvider

    # Auto-detect provider from env vars
    client = LLMClient()

    # Explicit provider
    client = LLMClient(LLMConfig(provider="anthropic"))
    client = LLMClient(LLMConfig(provider="openai", model="gpt-4o"))
    client = LLMClient(LLMConfig(provider="gemini", model="gemini-2.0-flash"))
    client = LLMClient(LLMConfig(provider="ollama", model="llama3.1"))
    client = LLMClient(LLMConfig(provider="openrouter", model="qwen/qwen3-coder-480b:free"))
    client = LLMClient(LLMConfig(provider="kilocode", model="anthropic/claude-sonnet-4.5"))
    client = LLMClient(LLMConfig(provider="github", model="gpt-4o"))
    client = LLMClient(LLMConfig(provider="free", model="gpt-4o-mini"))

    response = await client.generate("Hello!", tools=[...])
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("antigravity.llm")

# Late imports to avoid circular dependencies
# Clients are imported in _create_client() method when needed


# =============================================================================
# CONFIGURATION
# =============================================================================


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    KILOCODE = "kilocode"
    GITHUB = "github"  # GitHub Models - free with GITHUB_TOKEN
    FREE = "free"
    MOCK = "mock"  # For testing


class LLMConfig(BaseModel):
    """Configuration for LLM client.

    Lee parametros desde env vars con prefijo ANTIGRAVITY_ cuando no se
    proporcionan explicitamente:
    - ANTIGRAVITY_LLM_MODEL: modelo a usar
    - ANTIGRAVITY_LLM_MAX_TOKENS: limite de tokens de salida
    - ANTIGRAVITY_LLM_THINKING: nivel de thinking (off/low/medium/high)
    - ANTIGRAVITY_PERSONA: modo de persona (gentleman/neutral/concise)
    """

    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    retry_attempts: int = 3
    retry_delay: float = 1.0
    thinking_level: str = "off"
    persona: str = ""

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._apply_env_overrides()
        self._resolve_api_key()
        self._resolve_base_url()

    def _apply_env_overrides(self) -> None:
        """Aplica overrides desde env vars sobre los valores por defecto.

        Solo pisa el valor cuando el campo sigue en su default, para no
        sobreescribir parametros pasados explicitamente al constructor.
        """
        env_model = os.getenv("ANTIGRAVITY_LLM_MODEL")
        if env_model and self.model == "claude-sonnet-4-20250514":
            self.model = env_model
        env_max_tokens = os.getenv("ANTIGRAVITY_LLM_MAX_TOKENS")
        if env_max_tokens and self.max_tokens == 4096:
            try:
                self.max_tokens = int(env_max_tokens)
            except ValueError:
                pass
        env_thinking = os.getenv("ANTIGRAVITY_LLM_THINKING")
        if env_thinking and self.thinking_level == "off":
            self.thinking_level = env_thinking
        env_persona = os.getenv("ANTIGRAVITY_PERSONA")
        if env_persona and not self.persona:
            self.persona = env_persona

    def _resolve_api_key(self) -> None:
        """Resuelve la API key desde env segun el provider activo.

        No hace nada si ya se proporciono una key explicita.
        """
        if self.api_key:
            return
        env_keys: dict[LLMProvider, str | None] = {
            LLMProvider.ANTHROPIC: os.getenv("ANTHROPIC_API_KEY"),
            LLMProvider.OPENAI: os.getenv("OPENAI_API_KEY"),
            LLMProvider.GEMINI: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            LLMProvider.OPENROUTER: os.getenv("OPENROUTER_API_KEY"),
            LLMProvider.KILOCODE: os.getenv("KILO_API_KEY"),
            LLMProvider.GITHUB: os.getenv("GITHUB_TOKEN"),
        }
        resolved = env_keys.get(self.provider)
        if resolved:
            self.api_key = resolved

    def _resolve_base_url(self) -> None:
        """Resuelve la base_url para providers OpenAI-compatible (Z.ai, etc)."""
        if not self.base_url and self.provider == LLMProvider.OPENAI:
            self.base_url = os.getenv("OPENAI_BASE_URL")


# =============================================================================
# COST TRACKING
# =============================================================================

# Pricing per 1M tokens (as of 2026)
PRICING = {
    # Anthropic
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    # OpenAI
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    # Gemini
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-pro": {"input": 1.25, "output": 10.0},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # Z.ai (GLM)
    "glm-5": {"input": 1.0, "output": 3.2},
    "glm-4.5": {"input": 0.50, "output": 1.50},
    # OpenRouter (popular models - prices vary, these are approximations)
    "openrouter/free": {"input": 0.0, "output": 0.0},
    "qwen/qwen3-coder-480b:free": {"input": 0.0, "output": 0.0},
    "deepseek/deepseek-r1:free": {"input": 0.0, "output": 0.0},
    "google/gemini-2.0-flash-exp:free": {"input": 0.0, "output": 0.0},
    "meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
    # GitHub Models (free with GITHUB_TOKEN, rate-limited)
    "github/gpt-4o": {"input": 0.0, "output": 0.0},
    "github/gpt-4o-mini": {"input": 0.0, "output": 0.0},
    "github/*": {"input": 0.0, "output": 0.0},
    # Free / g4f (always free)
    "g4f/*": {"input": 0.0, "output": 0.0},
    # Local (free)
    "ollama/*": {"input": 0.0, "output": 0.0},
}


@dataclass
class UsageStats:
    """Token usage and cost statistics."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0
    latency_ms: float = 0.0
    model: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def calculate_cost(self, model: str) -> float:
        """Calculate cost based on model pricing."""
        pricing = PRICING.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        self.cost_usd = round(input_cost + output_cost, 6)
        return self.cost_usd

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "requests": self.requests,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "timestamp": self.timestamp,
        }


class CostTracker:
    """Track LLM costs across sessions."""

    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path
        self.session_stats = UsageStats()
        self.history: list[UsageStats] = []

    def record(self, stats: UsageStats) -> None:
        """Record usage statistics."""
        self.session_stats.input_tokens += stats.input_tokens
        self.session_stats.output_tokens += stats.output_tokens
        self.session_stats.total_tokens += stats.total_tokens
        self.session_stats.cost_usd += stats.cost_usd
        self.session_stats.requests += 1
        self.history.append(stats)

        if self.storage_path:
            self._persist()

    def _persist(self) -> None:
        """Persist stats to file."""
        try:
            data = {
                "session": self.session_stats.to_dict(),
                "history": [h.to_dict() for h in self.history[-100:]],  # Keep last 100
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:  # type: ignore[arg-type]  # Path accepted by open()
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist cost data: {e}")

    def get_summary(self) -> dict:
        """Get cost summary."""
        return {
            "session": self.session_stats.to_dict(),
            "total_requests": len(self.history),
            "avg_latency_ms": sum(h.latency_ms for h in self.history) / len(self.history)
            if self.history
            else 0,
        }


# Global cost tracker
_cost_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker."""
    return _cost_tracker


# =============================================================================
# LLM RESPONSE
# =============================================================================


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    usage: UsageStats
    finish_reason: str = "stop"
    tool_calls: list[dict] = field(default_factory=list)
    raw_response: Any | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# =============================================================================
# BASE LLM CLIENT
# =============================================================================


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.cost_tracker = get_cost_tracker()

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response from the LLM."""
        ...

    async def list_models(self) -> list[dict]:
        """List available models from this provider.

        Returns:
            Lista de dicts con al menos 'id' y opcionalmente 'name', 'context_length'.
        """
        return []


# =============================================================================
# UNIFIED CLIENT
# =============================================================================


class LLMClient:
    """
    Unified LLM client that supports multiple providers.

    Usage:
        client = LLMClient()  # Uses default (Anthropic)
        client = LLMClient(LLMConfig(provider="openai", model="gpt-4o"))

        response = await client.generate("Hello!")
        print(response.content)
        print(f"Cost: ${response.usage.cost_usd}")
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = self._create_client()

    def _create_client(self) -> BaseLLMClient:
        """Create the appropriate client based on config."""
        from .clients import (
            AnthropicClient,
            FreeClient,
            GeminiClient,
            GitHubModelsClient,
            KiloCodeClient,
            MockLLMClient,
            OllamaClient,
            OpenAIClient,
            OpenRouterClient,
        )

        if self.config.provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(self.config)
        elif self.config.provider == LLMProvider.OPENAI:
            return OpenAIClient(self.config)
        elif self.config.provider == LLMProvider.OLLAMA:
            return OllamaClient(self.config)
        elif self.config.provider == LLMProvider.GEMINI:
            return GeminiClient(self.config)
        elif self.config.provider == LLMProvider.OPENROUTER:
            return OpenRouterClient(self.config)
        elif self.config.provider == LLMProvider.KILOCODE:
            return KiloCodeClient(self.config)
        elif self.config.provider == LLMProvider.GITHUB:
            return GitHubModelsClient(self.config)
        elif self.config.provider == LLMProvider.FREE:
            return FreeClient(self.config)
        elif self.config.provider == LLMProvider.MOCK:
            return MockLLMClient(self.config)
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response."""
        return await self._client.generate(
            prompt=prompt, system=system, messages=messages, tools=tools, **kwargs
        )

    async def stream(self, prompt: str, system: str | None = None, **kwargs) -> AsyncIterator[str]:
        """Stream a response."""
        async for chunk in self._client.stream(prompt, system, **kwargs):
            yield chunk

    def get_cost_summary(self) -> dict:
        """Get cost summary for this session."""
        return self._client.cost_tracker.get_summary()

    async def list_models(self) -> list[dict]:
        """List available models from the configured provider."""
        return await self._client.list_models()


# =============================================================================
# AGENT EXECUTOR
# =============================================================================


class AgentExecutor:
    """
    Execute agent tasks with real LLM calls.

    This is the "brain" that makes agents actually think.
    """

    # Modificadores de persona para inyectar en el system prompt
    _PERSONA_MODIFIERS: dict[str, str] = {
        "gentleman": (
            "\n\n[Communication Style: Gentleman — Teach, explain and guide with detail. "
            "Be thorough in your explanations, provide context and reasoning. "
            "Use a warm, educational tone. When presenting options, explain trade-offs.]"
        ),
        "concise": (
            "\n\n[Communication Style: Concise — Minimal answers, no elaboration. "
            "Skip preamble, context, and explanations unless explicitly asked. "
            "Use bullet points over paragraphs. One sentence when one sentence suffices.]"
        ),
    }

    def __init__(
        self, llm_client: LLMClient | None = None, max_iterations: int = 10, verbose: bool = False
    ):
        self.llm = llm_client or LLMClient()
        self.max_iterations = max_iterations
        self.verbose = verbose

    def _apply_persona(self, system_prompt: str) -> str:
        """Aplica el modificador de persona al system prompt.

        Args:
            system_prompt: Prompt original.

        Returns:
            Prompt con modificador de persona si aplica.
        """
        persona = (self.llm.config.persona or "").lower()
        if not persona or persona == "neutral":
            return system_prompt
        if persona == "jpkken":
            import os

            custom = os.getenv("ANTIGRAVITY_PERSONA_CUSTOM", "")
            if custom:
                return system_prompt + f"\n\n[Communication Style: Jpkken — {custom}]"
            return system_prompt
        modifier = self._PERSONA_MODIFIERS.get(persona)
        return system_prompt + modifier if modifier else system_prompt

    async def execute(
        self,
        task: str,
        agent_prompt: str,
        tools: list[dict] | None = None,
        context: str | None = None,
    ) -> dict:
        """
        Execute a task using an agent's system prompt.

        Args:
            task: The task to accomplish
            agent_prompt: The agent's system prompt (identity, skills, etc.)
            tools: Optional tools the agent can use
            context: Optional additional context

        Returns:
            Execution result with response, tokens used, cost
        """
        full_prompt = task
        if context:
            full_prompt = f"Context:\n{context}\n\nTask:\n{task}"

        # Aplicar modificador de persona si esta configurado
        effective_prompt = self._apply_persona(agent_prompt)

        logger.info(f"Executing task: {task[:50]}...")

        # Single-shot execution (can be extended to multi-turn)
        response = await self.llm.generate(prompt=full_prompt, system=effective_prompt, tools=tools)

        if self.verbose:
            logger.info(f"\n{'=' * 60}")
            logger.info("Agent Response:")
            logger.info(f"{'=' * 60}")
            logger.info(response.content[:500])
            logger.info(
                f"\nTokens: {response.usage.total_tokens} | Cost: ${response.usage.cost_usd}"
            )

        return {
            "success": True,
            "output": response.content,
            "tool_calls": response.tool_calls,
            "usage": response.usage.to_dict(),
            "model": response.model,
        }

    async def execute_with_tools(
        self,
        task: str,
        agent_prompt: str,
        tools: list[dict],
        tool_executor: Callable[[str, dict], Any],
    ) -> dict:
        """
        Execute a task with tool use in a loop.

        Args:
            task: The task to accomplish
            agent_prompt: The agent's system prompt
            tools: List of tool definitions
            tool_executor: Function to execute tools

        Returns:
            Final result after tool execution
        """
        effective_prompt = self._apply_persona(agent_prompt)
        messages = [{"role": "user", "content": task}]
        iterations = 0
        total_tokens = 0
        total_cost = 0.0

        while iterations < self.max_iterations:
            response = await self.llm.generate(
                prompt="", system=effective_prompt, messages=messages, tools=tools
            )

            total_tokens += response.usage.total_tokens
            total_cost += response.usage.cost_usd

            if not response.has_tool_calls:
                # No more tool calls, we're done
                return {
                    "success": True,
                    "output": response.content,
                    "iterations": iterations + 1,
                    "total_tokens": total_tokens,
                    "total_cost": total_cost,
                }

            # Execute tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": response.tool_calls,  # type: ignore[dict-item]  # dynamic API response structure
                }
            )

            for tool_call in response.tool_calls:
                result = tool_executor(tool_call["name"], tool_call["input"])
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call["id"], "content": str(result)}
                )

            iterations += 1

        return {
            "success": False,
            "output": "Max iterations reached",
            "iterations": iterations,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }


# =============================================================================
# RE-EXPORTS — Client classes accesibles como atributos de módulo
# Colocados después de que BaseLLMClient y demás clases base estén definidas,
# lo que evita el problema de import circular con los subpaquetes en clients/.
# =============================================================================

try:
    from .clients import (  # noqa: E402
        AnthropicClient,  # noqa: F401
        FreeClient,  # noqa: F401
        GeminiClient,  # noqa: F401
        GitHubModelsClient,  # noqa: F401
        KiloCodeClient,  # noqa: F401
        MockLLMClient,  # noqa: F401
        OllamaClient,  # noqa: F401
        OpenAIClient,  # noqa: F401
        OpenRouterClient,  # noqa: F401
    )
except ImportError:
    # En entornos donde los clientes individuales no están disponibles
    # los tests que los requieran serán saltados por el fixture
    pass


# =============================================================================
# CLI
# =============================================================================


async def main():
    """Test LLM integration."""
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity LLM Client")
    parser.add_argument("prompt", nargs="?", default="Hello! What can you do?")
    parser.add_argument(
        "--provider",
        "-p",
        choices=[
            "anthropic",
            "openai",
            "ollama",
            "gemini",
            "openrouter",
            "kilocode",
            "github",
            "free",
            "mock",
        ],
        default="mock",
    )
    parser.add_argument("--model", "-m", default=None)
    parser.add_argument("--stream", "-s", action="store_true")
    parser.add_argument("--list-models", "-l", action="store_true", help="List available models")
    parser.add_argument("--setup", action="store_true", help="Interactive provider setup")

    args = parser.parse_args()

    # Interactive setup wizard
    if args.setup:
        subprocess.run([sys.executable, ".agent/scripts/setup_llm.py"], check=True)
        return

    config = LLMConfig(
        provider=LLMProvider(args.provider),
        model=args.model
        or {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash",
            "ollama": "llama3.1",
            "openrouter": "openrouter/free",
            "kilocode": "anthropic/claude-sonnet-4.5",
            "github": "gpt-4o",
            "free": "gpt-4o-mini",
            "mock": "mock",
        }.get(args.provider, "gpt-4o"),
    )

    client = LLMClient(config)

    # List models mode
    if args.list_models:
        print(f"\nProvider: {config.provider.value}")
        print("Fetching available models...\n")
        models = await client.list_models()
        if models:
            for m in models:
                mid = m.get("id", "?")
                owner = m.get("owned_by", "")
                print(f"  {mid}" + (f"  ({owner})" if owner else ""))
            print(f"\nTotal: {len(models)} models")
        else:
            print("No models found or provider doesn't support listing.")
        return

    print(f"\nProvider: {config.provider.value}")
    print(f"Model: {config.model}")
    print(f"Prompt: {args.prompt}\n")
    print("-" * 50)

    if args.stream:
        print("Response (streaming): ", end="", flush=True)
        async for chunk in client.stream(args.prompt):
            print(chunk, end="", flush=True)
        print()
    else:
        response = await client.generate(args.prompt)
        print(f"Response: {response.content}")
        print(f"\nTokens: {response.usage.total_tokens}")
        print(f"Cost: ${response.usage.cost_usd:.6f}")

    print("-" * 50)
    print("\nSession Summary:")
    summary = client.get_cost_summary()
    print(f"  Total requests: {summary['total_requests']}")
    print(f"  Total cost: ${summary['session']['cost_usd']:.6f}")


if __name__ == "__main__":
    asyncio.run(main())
