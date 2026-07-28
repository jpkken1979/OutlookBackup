# mypy: ignore-errors
"""CLI del motor autonomo: ``python -m core.autonomous_loop 'tarea'``.

Extraido del monolito ``autonomous_loop.py`` (refactor 2026-05-31). El
``_core_dir`` apunta a ``core/`` (un nivel arriba del paquete) para que los
imports bare (llm, agent_mesh, ...) sigan resolviendo.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .loop import run_autonomous
from .providers import get_available_providers


if __name__ == "__main__":
    import sys as _sys

    # Ensure core directory is on sys.path so bare imports (llm, agent_mesh, etc.) work
    _core_dir = str(Path(__file__).resolve().parent.parent)
    if _core_dir not in _sys.path:
        _sys.path.insert(0, _core_dir)

    import argparse

    parser = argparse.ArgumentParser(description="Antigravity Autonomous Agent Loop")
    parser.add_argument("task", nargs="?", help="Task for the agent")
    parser.add_argument("--agent", "-a", default="explorer", help="Agent name")
    parser.add_argument("--max-iter", "-m", type=int, default=10, help="Max iterations")
    parser.add_argument(
        "--provider",
        "-p",
        default=None,
        choices=["anthropic", "openai", "gemini", "ollama"],
        help="LLM provider (auto-detected if omitted)",
    )
    parser.add_argument("--model", default=None, help="Override model name")
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--list-providers", action="store_true", help="List available LLM providers and exit"
    )

    args = parser.parse_args()

    if args.list_providers:
        providers = get_available_providers()
        print("\nAvailable LLM Providers:")
        print("-" * 50)
        for p in providers:
            status = "[OK]" if p["available"] else "[--]"
            print(
                f"  {status} {p['provider']:12s}  model: {p['default_model']:25s}  ({p['reason']})"
            )
        print()
        exit(0)

    if not args.task:
        print("Usage: python autonomous_loop.py 'Your task here'")
        print("\nExamples:")
        print("  python autonomous_loop.py 'Find all security issues' -a security-auditor")
        print("  python autonomous_loop.py 'Explain the orchestrator module' -a explorer")
        print("  python autonomous_loop.py 'List all TODO comments' --max-iter 5")
        print("  python autonomous_loop.py 'Audit code' -p ollama --model llama3.1")
        print("  python autonomous_loop.py 'Audit code' -p gemini --model gemini-2.0-flash")
        print("\n  python autonomous_loop.py --list-providers  # See available providers")
        exit(0)

    result = asyncio.run(
        run_autonomous(
            task=args.task,
            agent_name=args.agent,
            max_iterations=args.max_iter,
            verbose=not args.quiet,
            provider=args.provider,
            model=args.model,
        )
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\nFinal Output:\n{result.final_output}")
