#!/usr/bin/env python3
"""Execute a real Antigravity agent and return structured JSON.

This script provides a stable bridge for external clients such as the
TypeScript chatbot. Instead of returning an agent prompt for another LLM to
execute, it runs the Python autonomous loop directly and returns the actual
result plus execution trace metadata.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / ".agent"
CORE_DIR = AGENT_DIR / "core"

for candidate in (str(REPO_ROOT), str(AGENT_DIR), str(CORE_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from core.autonomous_loop import run_autonomous  # noqa: E402


SUPPORTED_PROVIDERS = {
    "anthropic",
    "openai",
    "gemini",
    "ollama",
    "openrouter",
    "github",
    "free",
    "mock",
}

TS_PROVIDER_MAP = {
    "openrouter": "openrouter",
    "groq": None,
    "zhipu": None,
}


def resolve_provider(requested_provider: str | None) -> tuple[str | None, str | None]:
    """Map requested provider names to Python autonomous-loop providers."""
    if not requested_provider:
        return None, None

    normalized = requested_provider.strip().lower()
    if normalized in SUPPORTED_PROVIDERS:
        return normalized, None

    if normalized in TS_PROVIDER_MAP:
        resolved = TS_PROVIDER_MAP[normalized]
        if resolved is None:
            return (
                None,
                f"Provider '{normalized}' is not supported by the Python agent runtime; using auto-detect.",
            )
        return resolved, None

    return None, f"Unknown provider '{normalized}'; using auto-detect."


async def execute_agent(
    agent_name: str,
    task: str,
    provider: str | None,
    max_iterations: int,
) -> dict[str, Any]:
    """Run the requested agent through the autonomous loop."""
    runtime_provider, provider_note = resolve_provider(provider)
    result = await run_autonomous(
        task=task,
        agent_name=agent_name,
        max_iterations=max_iterations,
        verbose=False,
        provider=runtime_provider,
    )

    payload = {
        "success": result.succeeded,
        "agent": agent_name,
        "task": task,
        "execution_mode": "autonomous_loop",
        "provider_requested": provider,
        "provider_used": runtime_provider or "auto",
        "result": result.final_output,
        "trace": result.to_dict(),
    }
    if provider_note:
        payload["provider_note"] = provider_note
    return payload


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Execute one Antigravity agent")
    parser.add_argument("agent", help="Agent name to execute")
    parser.add_argument("task", help="Task to perform")
    parser.add_argument("--provider", help="Optional provider override")
    parser.add_argument(
        "--max-iter", type=int, default=8, help="Maximum autonomous loop iterations"
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    try:
        result = asyncio.run(
            execute_agent(
                agent_name=args.agent,
                task=args.task,
                provider=args.provider,
                max_iterations=args.max_iter,
            )
        )
    except Exception as exc:
        error_payload = {
            "success": False,
            "agent": args.agent,
            "task": args.task,
            "error": str(exc),
            "execution_mode": "autonomous_loop",
        }
        if args.json:
            print(json.dumps(error_payload, indent=2, ensure_ascii=False))
        else:
            print(error_payload["error"], file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["result"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
