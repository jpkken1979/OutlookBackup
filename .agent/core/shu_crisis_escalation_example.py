#!/usr/bin/env python3
"""Example usage of ShuCrisisEscalator for /shu skill.

This shows how to integrate crisis escalation into task execution.
"""

import asyncio
import sys
from pathlib import Path

# Add .agent to path
AGENT_DIR = Path(__file__).parent.parent / ".agent"
sys.path.insert(0, str(AGENT_DIR))

from core.shu_crisis_escalation import (
    ShuCrisisEscalator,
    EscalationContext,
    escalate_if_needed,
)


async def example_task_with_escalation() -> None:
    """Example: Execute a task and escalate if needed."""

    # Simulate task execution
    task_goal = "Critical system backup"
    task_result = "error"
    execution_time_ms = 45000
    responses = ["connection timeout", "retry failed"]
    error_msg = "Gateway unreachable after 3 attempts"

    print(f"Task: {task_goal}")
    print(f"Result: {task_result}")
    print(f"Time: {execution_time_ms}ms")
    print()

    # Check if escalation is needed
    escalation_result = await escalate_if_needed(
        result=task_result,
        goal=task_goal,
        category="system",
        responses=responses,
        error_message=error_msg,
        execution_time_ms=execution_time_ms,
        verbose=True,
    )

    if escalation_result:
        print("Escalation triggered!")
        print(f"  Action: {escalation_result.get('action')}")
        print(f"  Reasoning: {escalation_result.get('reasoning')}")
        print(f"  Recommendation: {escalation_result.get('recommendation')}")
    else:
        print("No escalation needed.")


async def example_manual_escalation() -> None:
    """Example: Manual escalation with full control."""

    escalator = ShuCrisisEscalator(verbose=True)

    # Check if conditions warrant escalation
    should_escalate = escalator.should_escalate(
        result="error",
        goal="Urgent: Fix critical database corruption",
        execution_time_ms=35000,
    )

    if should_escalate:
        print("Escalating to crisis handler...")
        context = EscalationContext(
            goal="Fix critical database corruption",
            category="database",
            responses=["query timeout", "connection lost"],
            error_message="Corruption detected in transaction log",
            execution_time_ms=35000,
        )

        result = await escalator.escalate_to_crisis_handler(context)
        print(f"Crisis handler result: {result}")


if __name__ == "__main__":
    print("=== Example 1: Automatic escalation ===")
    asyncio.run(example_task_with_escalation())

    print("\n=== Example 2: Manual escalation ===")
    asyncio.run(example_manual_escalation())
