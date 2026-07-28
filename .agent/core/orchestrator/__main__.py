"""CLI del orchestrator: ``python -m core.orchestrator "tarea"``.

Extraido del monolito ``orchestrator.py`` (refactor 2026-06-01).
"""

from __future__ import annotations

import asyncio

from .core import AntigravityOrchestrator
from .registry import AGENT_REGISTRY


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Antigravity Orchestrator v3.0 - Multi-Agent Task Execution"
    )
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Plan only")
    parser.add_argument("--max-agents", "-m", type=int, default=5, help="Max agents")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--list-agents", action="store_true", help="List all agents")

    args = parser.parse_args()

    if args.list_agents:
        print("\nAvailable Agents:")
        print("-" * 50)
        for name, config in AGENT_REGISTRY.items():
            print(f"  {name} (Tier {config.tier})")
            print(f"    Role: {config.role}")
            print(f"    Skills: {', '.join(config.skills[:5])}")
            print()
        return

    if not args.task:
        print("Error: Provide a task to execute")
        print('Usage: python orchestrator.py "Your task here"')
        return

    orchestrator = AntigravityOrchestrator(verbose=args.verbose)
    asyncio.run(orchestrator.execute(args.task, max_agents=args.max_agents, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
