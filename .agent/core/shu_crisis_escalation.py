#!/usr/bin/env python3
"""Crisis escalation logic for /shu skill.

Auto-escalates to crisis-handler agent when conditions are met.
Integrates with autonomous_loop for real agent execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve repository root for execute_agent.py
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"


@dataclass
class EscalationContext:
    """Context data for escalation event."""

    goal: str
    category: str
    responses: list[str]
    error_message: str | None = None
    execution_time_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "goal": self.goal,
            "category": self.category,
            "responses": self.responses,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
        }


class ShuCrisisEscalator:
    """Auto-escalates task failures to crisis-handler agent.

    Features:
    - Detects escalation conditions (errors, timeouts, urgency keywords)
    - Invokes crisis-handler agent via execute_agent.py
    - Tracks escalation metrics
    """

    # Urgency keywords that trigger auto-escalation
    URGENCY_KEYWORDS = frozenset(
        [
            "critical",
            "urgente",
            "inmediato",
            "bloqueante",
            "emergencia",
            "fallo crítico",
            "error fatal",
        ]
    )

    # Timeout threshold in milliseconds
    TIMEOUT_THRESHOLD_MS = 30000

    def __init__(self, verbose: bool = False) -> None:
        """Initialize the escalator.

        Args:
            verbose: Enable debug logging.
        """
        self.verbose = verbose
        self.escalation_count = 0
        logger.info("[CRISIS_ESCALATION] Escalator initialized")

    def should_escalate(
        self, result: str, goal: str, execution_time_ms: float | None = None
    ) -> bool:
        """Determine if a task failure should be escalated.

        Escalates if any condition is true:
        1. result == "error"
        2. execution_time_ms > 30000 (timeout)
        3. goal contains urgency keywords

        Args:
            result: Task execution result ("error", "success", etc.)
            goal: Original goal/task description.
            execution_time_ms: Execution time in milliseconds (optional).

        Returns:
            True if escalation is warranted, False otherwise.
        """
        # Check explicit error condition
        if result == "error" or result.lower() in ("failed", "failure"):
            logger.warning("[CRISIS_ESCALATION] Escalation triggered: explicit error result")
            return True

        # Check timeout condition
        if execution_time_ms and execution_time_ms > self.TIMEOUT_THRESHOLD_MS:
            logger.warning(
                "[CRISIS_ESCALATION] Escalation triggered: timeout (%.0fms > %.0fms)",
                execution_time_ms,
                self.TIMEOUT_THRESHOLD_MS,
            )
            return True

        # Check urgency keywords
        goal_lower = goal.lower()
        for keyword in self.URGENCY_KEYWORDS:
            if keyword in goal_lower:
                logger.warning(
                    "[CRISIS_ESCALATION] Escalation triggered: urgency keyword '%s'",
                    keyword,
                )
                return True

        return False

    async def escalate_to_crisis_handler(self, context: EscalationContext) -> dict[str, Any]:
        """Invoke crisis-handler agent via execute_agent.py.

        Passes goal, context (responses), and error info to the agent.
        The agent determines root cause and recommends recovery action.

        Args:
            context: Escalation context with goal, responses, error details.

        Returns:
            Agent result dict with keys:
                - success: bool (agent execution succeeded)
                - action: str (recommended action)
                - reasoning: str (explanation)
                - recommendation: str (detailed recommendation)
                - trace: dict (agent execution trace)
        """
        self.escalation_count += 1

        # Prepare task for crisis handler
        task_description = self._build_crisis_task(context)

        logger.info(
            "[CRISIS_ESCALATION] Escalating to crisis-handler (attempt %d)",
            self.escalation_count,
        )
        logger.debug("[CRISIS_ESCALATION] Task: %s", task_description)

        try:
            # Execute agent synchronously via subprocess
            result = await self._execute_agent_subprocess(task_description)

            if result["success"]:
                logger.info(
                    "[CRISIS_ESCALATION] Crisis handler succeeded: %s",
                    result.get("action", "unknown"),
                )
            else:
                logger.error(
                    "[CRISIS_ESCALATION] Crisis handler failed: %s",
                    result.get("trace", {}).get("final_output", "no output"),
                )

            return self._parse_agent_response(result)

        except Exception as exc:
            logger.error(
                "[CRISIS_ESCALATION] Escalation execution failed: %s",
                str(exc),
                exc_info=True,
            )
            return {
                "success": False,
                "action": "manual_intervention_required",
                "reasoning": f"Crisis handler execution failed: {str(exc)}",
                "recommendation": "Check logs and manually assess the situation.",
                "error": str(exc),
            }

    async def _execute_agent_subprocess(self, task: str) -> dict[str, Any]:
        """Execute crisis-handler agent via execute_agent.py subprocess.

        Args:
            task: Task description for the agent.

        Returns:
            Parsed JSON response from execute_agent.py
        """
        script_path = SCRIPTS_DIR / "execute_agent.py"

        if not script_path.exists():
            raise FileNotFoundError(f"execute_agent.py not found at {script_path}")

        # Build command
        cmd = [
            sys.executable,
            str(script_path),
            "crisis-handler",
            task,
            "--max-iter",
            "5",
            "--json",
        ]

        if self.verbose:
            logger.debug("[CRISIS_ESCALATION] Running: %s", " ".join(cmd))

        # Run subprocess
        try:
            proc_result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout for agent execution
            )

            if proc_result.returncode != 0:
                logger.error(
                    "[CRISIS_ESCALATION] Agent subprocess failed with code %d",
                    proc_result.returncode,
                )
                logger.error("[CRISIS_ESCALATION] stderr: %s", proc_result.stderr)
                raise RuntimeError(f"Agent execution failed: {proc_result.stderr}")

            # Parse JSON output
            response = json.loads(proc_result.stdout)
            return response

        except subprocess.TimeoutExpired:
            logger.error("[CRISIS_ESCALATION] Agent execution timeout (60s)")
            raise RuntimeError("Crisis handler execution timeout")
        except json.JSONDecodeError as exc:
            logger.error(
                "[CRISIS_ESCALATION] Failed to parse agent output: %s",
                str(exc),
            )
            raise RuntimeError(f"Invalid agent output: {str(exc)}")

    def _build_crisis_task(self, context: EscalationContext) -> str:
        """Build task description for crisis handler agent.

        Args:
            context: Escalation context.

        Returns:
            Task description string.
        """
        task_parts = [
            f"Goal: {context.goal}",
            f"Category: {context.category}",
        ]

        if context.responses:
            task_parts.append(f"Responses received: {len(context.responses)}")
            task_parts.append("Response summary: " + "; ".join(context.responses[:3]))

        if context.error_message:
            task_parts.append(f"Error: {context.error_message}")

        if context.execution_time_ms:
            task_parts.append(f"Execution time: {context.execution_time_ms:.0f}ms")

        task_parts.append("Determine root cause and recommend recovery action.")

        return "\n".join(task_parts)

    def _parse_agent_response(self, agent_result: dict[str, Any]) -> dict[str, Any]:
        """Parse and normalize agent response.

        Args:
            agent_result: Raw response from execute_agent.py

        Returns:
            Normalized escalation result dict.
        """
        if not agent_result.get("success"):
            return {
                "success": False,
                "action": "escalation_failed",
                "reasoning": "Agent execution did not succeed",
                "recommendation": agent_result.get("result", "Unable to determine recommendation"),
                "trace": agent_result.get("trace", {}),
            }

        # Extract meaningful output from agent
        agent_output = agent_result.get("result", "")
        trace_data = agent_result.get("trace", {})

        # Try to parse structured action from output
        action = self._extract_action(agent_output)
        reasoning = agent_output[:500] if agent_output else "No reasoning provided"

        return {
            "success": True,
            "action": action,
            "reasoning": reasoning,
            "recommendation": self._build_recommendation(action, agent_output),
            "trace": trace_data,
        }

    def _extract_action(self, output: str) -> str:
        """Extract primary action from agent output.

        Args:
            output: Agent output text.

        Returns:
            Action name or "manual_intervention".
        """
        output_lower = output.lower()

        # Simple heuristics for common actions
        if "retry" in output_lower:
            return "retry_task"
        if "rollback" in output_lower or "revert" in output_lower:
            return "rollback_changes"
        if "escalate" in output_lower or "human" in output_lower:
            return "escalate_to_human"
        if "fix" in output_lower or "patch" in output_lower:
            return "apply_fix"

        return "manual_intervention_required"

    def _build_recommendation(self, action: str, output: str) -> str:
        """Build human-readable recommendation from agent analysis.

        Args:
            action: Extracted action.
            output: Agent output.

        Returns:
            Recommendation text.
        """
        recommendations = {
            "retry_task": "Attempt the task again. Previous failure may be transient.",
            "rollback_changes": "Revert recent changes and validate system state.",
            "escalate_to_human": "Escalate to human operator for manual assessment.",
            "apply_fix": "Apply recommended fix and retry task execution.",
            "manual_intervention_required": "Manual intervention required. Review logs carefully.",
        }

        base = recommendations.get(action, "Review agent output below.")
        if output:
            base += f"\n\nAgent analysis: {output[:300]}"
        return base


async def escalate_if_needed(
    result: str,
    goal: str,
    category: str,
    responses: list[str],
    error_message: str | None = None,
    execution_time_ms: float | None = None,
    verbose: bool = False,
) -> dict[str, Any] | None:
    """Convenience function: escalate if conditions warrant it.

    Args:
        result: Task result ("error", "success", etc.)
        goal: Task goal/description.
        category: Task category (for context).
        responses: List of responses/attempts.
        error_message: Error details if available.
        execution_time_ms: Execution time in milliseconds.
        verbose: Enable debug logging.

    Returns:
        Escalation result dict if escalated, None if no escalation needed.
    """
    escalator = ShuCrisisEscalator(verbose=verbose)

    if not escalator.should_escalate(result, goal, execution_time_ms):
        logger.debug("[CRISIS_ESCALATION] No escalation needed")
        return None

    context = EscalationContext(
        goal=goal,
        category=category,
        responses=responses,
        error_message=error_message,
        execution_time_ms=execution_time_ms,
    )

    return await escalator.escalate_to_crisis_handler(context)


if __name__ == "__main__":
    # Simple test
    async def test() -> None:
        """Test the escalator."""
        ctx = EscalationContext(
            goal="Critical system sync",
            category="system",
            responses=["timeout", "connection_failed"],
            error_message="Gateway unreachable",
            execution_time_ms=35000,
        )

        escalator = ShuCrisisEscalator(verbose=True)

        # Check if escalation is needed
        should_escalate = escalator.should_escalate(
            result="error",
            goal=ctx.goal,
            execution_time_ms=ctx.execution_time_ms,
        )
        print(f"Should escalate: {should_escalate}")

        if should_escalate:
            result = await escalator.escalate_to_crisis_handler(ctx)
            print(json.dumps(result, indent=2))

    asyncio.run(test())
