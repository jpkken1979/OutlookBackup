"""ShuCrossPlatformHandler — Unified handler for cross-platform /shu invocations.

Normalizes responses from Slack, Discord, and GitHub into the standard /shu
6-question format and delegates execution to the webhook publisher.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import sys

logger = logging.getLogger(__name__)

# Add .agent to path for imports
_AGENT_DIR = Path(__file__).parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))


@dataclass
class ShuExecutionResult:
    """Result of a cross-platform /shu execution.

    Attributes:
        success: Whether execution completed without errors.
        platform: Source platform (slack, discord, github).
        goal: The user's stated goal.
        normalized_responses: Responses mapped to q1-q6 keys.
        execution_plan: Generated plan based on responses.
        next_steps: List of concrete next steps.
        broadcast_result: Result from webhook publisher.
        execution_time_ms: Total execution time in milliseconds.
        timestamp: ISO8601 timestamp of the execution.
    """

    success: bool
    platform: str
    goal: str
    normalized_responses: dict[str, str]
    execution_plan: str
    next_steps: list[str]
    broadcast_result: dict
    execution_time_ms: float
    timestamp: str


# Mapping from platform-specific keys to normalized q1-q6 keys
_SLACK_KEY_MAP: dict[str, str] = {
    "q1_context": "q1",
    "q2_scope": "q2",
    "q3_restrictions": "q3",
    "q4_validation": "q4",
    "q5_priority": "q5",
    "q6_historical": "q6",
}

_DISCORD_KEY_MAP: dict[str, str] = {
    "q1_context": "q1",
    "q2_scope": "q2",
    "q3_restrictions": "q3",
    "q4_validation": "q4",
    "q5_priority": "q5",
    "q6_historical": "q6",
}

# GitHub responses use uppercase keys Q1-Q6 (from markdown heading parsing)
_GITHUB_LABEL_MAP: dict[str, str] = {
    "Q1": "q1",
    "Q2": "q2",
    "Q3": "q3",
    "Q4": "q4",
    "Q5": "q5",
    "Q6": "q6",
}

_QUESTION_LABELS: dict[str, str] = {
    "q1": "Context (situacion real)",
    "q2": "Scope (que debe cambiar)",
    "q3": "Restrictions (restricciones)",
    "q4": "Validation (criterio de exito)",
    "q5": "Priority (urgencia + valor)",
    "q6": "Historical (decisiones previas similares)",
}


def _compute_responses_hash(responses: dict[str, str]) -> str:
    """Compute a short hash of the responses dict for log correlation.

    Args:
        responses: Normalized responses dict.

    Returns:
        8-character hex hash.
    """
    serialized = str(sorted(responses.items()))
    return hashlib.sha256(serialized.encode()).hexdigest()[:8]


class ShuCrossPlatformHandler:
    """Normalizes and executes /shu from any supported platform.

    Platforms supported: slack, discord, github.
    All responses are normalized to {q1, q2, q3, q4, q5, q6} before
    being processed and published via the webhook system.
    """

    def __init__(self, subscribers_dir: Path | None = None) -> None:
        """Initialize the handler with optional custom subscribers directory.

        Args:
            subscribers_dir: Directory for webhook subscriber storage.
                Defaults to ~/.antigravity/shu/.
        """
        try:
            from core.shu_webhook_publisher import ShuWebhookPublisher

            self._publisher = ShuWebhookPublisher(subscribers_dir=subscribers_dir)
            self._publisher_available = True
        except ImportError as exc:
            logger.warning("ShuWebhookPublisher not available: %s", exc)
            self._publisher = None  # type: ignore[assignment]
            self._publisher_available = False

    def _normalize_slack_responses(self, raw: dict[str, str]) -> dict[str, str]:
        """Map Slack modal field names to q1-q6.

        Args:
            raw: Dict with keys like q1_context, q2_scope, etc.

        Returns:
            Normalized dict with q1-q6 keys.
        """
        normalized: dict[str, str] = {}
        for platform_key, norm_key in _SLACK_KEY_MAP.items():
            normalized[norm_key] = raw.get(platform_key, "").strip()
        return normalized

    def _normalize_discord_responses(self, raw: dict[str, str]) -> dict[str, str]:
        """Map Discord field names to q1-q6.

        Args:
            raw: Dict with keys like q1_context, q2_scope, etc.

        Returns:
            Normalized dict with q1-q6 keys.
        """
        normalized: dict[str, str] = {}
        for platform_key, norm_key in _DISCORD_KEY_MAP.items():
            normalized[norm_key] = raw.get(platform_key, "").strip()
        return normalized

    def _normalize_github_responses(self, raw: dict[str, str]) -> dict[str, str]:
        """Map GitHub comment keys (Q1, Q2, ...) to q1-q6.

        GitHub responses are extracted from markdown like:
            **Q1 - Context:** some text

        Args:
            raw: Dict with uppercase keys Q1-Q6 extracted from comment.

        Returns:
            Normalized dict with q1-q6 keys.
        """
        normalized: dict[str, str] = {}
        for label, norm_key in _GITHUB_LABEL_MAP.items():
            # Try uppercase first (from markdown parsing), then lowercase fallback
            value = raw.get(label, raw.get(norm_key, "")).strip()
            normalized[norm_key] = value
        return normalized

    def _normalize_responses(self, platform: str, raw: dict[str, str]) -> dict[str, str]:
        """Dispatch normalization to the correct platform handler.

        Args:
            platform: Platform identifier (slack, discord, github).
            raw: Raw response dict from the platform.

        Returns:
            Normalized dict with q1-q6 keys.
        """
        if platform == "slack":
            return self._normalize_slack_responses(raw)
        elif platform == "discord":
            return self._normalize_discord_responses(raw)
        elif platform == "github":
            return self._normalize_github_responses(raw)
        else:
            # Generic fallback: try q1-q6 direct keys first
            normalized: dict[str, str] = {}
            for i in range(1, 7):
                qkey = f"q{i}"
                value = raw.get(qkey, raw.get(f"Q{i}", ""))
                normalized[qkey] = value.strip()
            return normalized

    def _build_execution_plan(
        self, goal: str, responses: dict[str, str], platform: str
    ) -> tuple[str, list[str]]:
        """Generate a concise execution plan from normalized responses.

        Args:
            goal: The user's stated goal.
            responses: Normalized q1-q6 responses.
            platform: Source platform.

        Returns:
            Tuple of (execution_plan_summary, next_steps_list).
        """
        lines = [
            f"[CONTEXTO SHU] -- Plataforma: {platform.upper()}",
            f"Objetivo: {goal}",
            "",
        ]
        for key, label in _QUESTION_LABELS.items():
            value = responses.get(key, "(sin respuesta)")
            lines.append(f"  {label}: {value}")

        plan = "\n".join(lines)

        next_steps: list[str] = []
        if responses.get("q2"):
            next_steps.append(f"Ejecutar cambio: {responses['q2'][:80]}")
        if responses.get("q4"):
            next_steps.append(f"Validar con: {responses['q4'][:80]}")
        if responses.get("q3"):
            next_steps.append(f"Respetar restricciones: {responses['q3'][:80]}")
        if not next_steps:
            next_steps.append("Definir scope concreto antes de ejecutar")

        return plan, next_steps

    def execute_from_platform(
        self,
        platform: str,
        goal: str,
        responses: dict[str, str],
    ) -> dict[str, Any]:
        """Normalize responses, build execution plan, and publish via webhook.

        Never raises to caller — all exceptions are caught and logged.

        Args:
            platform: Source platform (slack, discord, github).
            goal: The user's stated goal.
            responses: Raw response dict from the platform bridge.

        Returns:
            Dict with keys: success, platform, goal, normalized_responses,
            execution_plan, next_steps, broadcast_result, execution_time_ms,
            timestamp.
        """
        start_ts = time.monotonic()
        timestamp = datetime.now(UTC).isoformat()

        responses_hash = _compute_responses_hash(responses)
        logger.info(
            "shu_cross_platform: platform=%s goal=%r responses_hash=%s",
            platform,
            goal[:60],
            responses_hash,
        )

        try:
            normalized = self._normalize_responses(platform, responses)

            plan, next_steps = self._build_execution_plan(goal, normalized, platform)

            # Publish to webhook subscribers
            suggestions = [plan] + next_steps
            affected_templates = [f"shu-{platform}", goal[:50]]

            if self._publisher_available:
                broadcast_result = self._publisher.publish_improvement(
                    suggestions=suggestions,
                    affected_templates=affected_templates,
                )
            else:
                broadcast_result = {
                    "broadcast_count": 0,
                    "successful": 0,
                    "failed": 0,
                    "errors": ["Publisher not available"],
                }

            elapsed_ms = (time.monotonic() - start_ts) * 1000
            logger.info(
                "shu_cross_platform: completed platform=%s goal=%r elapsed_ms=%.1f "
                "broadcast_successful=%d",
                platform,
                goal[:60],
                elapsed_ms,
                broadcast_result.get("successful", 0),
            )

            return ShuExecutionResult(
                success=True,
                platform=platform,
                goal=goal,
                normalized_responses=normalized,
                execution_plan=plan,
                next_steps=next_steps,
                broadcast_result=broadcast_result,
                execution_time_ms=round(elapsed_ms, 1),
                timestamp=timestamp,
            ).__dict__

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start_ts) * 1000
            logger.error(
                "shu_cross_platform: error platform=%s goal=%r error=%s elapsed_ms=%.1f",
                platform,
                goal[:60],
                exc,
                elapsed_ms,
            )
            return {
                "success": False,
                "platform": platform,
                "goal": goal,
                "normalized_responses": {},
                "execution_plan": "",
                "next_steps": [],
                "broadcast_result": {
                    "broadcast_count": 0,
                    "successful": 0,
                    "failed": 0,
                    "errors": [str(exc)],
                },
                "execution_time_ms": round(elapsed_ms, 1),
                "timestamp": timestamp,
            }
