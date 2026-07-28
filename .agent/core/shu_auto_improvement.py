"""Auto-improvement feedback loop for /shu skill.

Collects execution feedback and suggests template improvements based on
error rates, unclear questions, and performance metrics.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class ShuFeedbackRecord:
    """Single execution feedback record."""

    timestamp: str
    goal: str
    category: str
    responses: list[str]
    result: Literal["success", "error"]
    execution_time_ms: float
    user_id: str = "anonymous"
    session_id: str = ""


class ShuFeedbackCollector:
    """Records /shu execution feedback for analysis."""

    def __init__(self, feedback_dir: Path | None = None) -> None:
        """Initialize feedback collector.

        Args:
            feedback_dir: Directory for feedback storage. Defaults to
                ~/.antigravity/shu/
        """
        if feedback_dir is None:
            feedback_dir = Path.home() / ".antigravity" / "shu"

        self.feedback_dir = feedback_dir
        self.feedback_file = feedback_dir / "feedback.jsonl"

        # Ensure directory exists
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        goal: str,
        category: str,
        responses: list[str],
        result: Literal["success", "error"],
        execution_time_ms: float,
        user_id: str | None = None,
    ) -> None:
        """Record a single execution feedback.

        Args:
            goal: User's goal/question
            category: Detected category
            responses: List of user responses
            result: "success" or "error"
            execution_time_ms: Total execution time in milliseconds
            user_id: Optional user identifier. Falls back to env var
                ANTIGRAVITY_SESSION_ID, then "anonymous".
        """
        import os

        resolved_user_id = user_id or os.environ.get("ANTIGRAVITY_SESSION_ID") or "anonymous"
        session_id = os.environ.get("ANTIGRAVITY_SESSION_ID", "")

        record = ShuFeedbackRecord(
            timestamp=datetime.utcnow().isoformat(),
            goal=goal,
            category=category,
            responses=responses,
            result=result,
            execution_time_ms=execution_time_ms,
            user_id=resolved_user_id,
            session_id=session_id,
        )

        try:
            with open(self.feedback_file, "a", encoding="utf-8") as f:
                json.dump(asdict(record), f)
                f.write("\n")
            logger.debug(f"Shu feedback recorded: {category} ({result})")
        except Exception as e:
            logger.error(f"Failed to record Shu feedback: {e}")


class ShuImprovementEngine:
    """Analyzes feedback and suggests template improvements."""

    def __init__(self, feedback_file: Path | None = None) -> None:
        """Initialize improvement engine.

        Args:
            feedback_file: Path to feedback.jsonl. Defaults to
                ~/.antigravity/shu/feedback.jsonl
        """
        if feedback_file is None:
            feedback_file = Path.home() / ".antigravity" / "shu" / "feedback.jsonl"

        self.feedback_file = feedback_file

    def suggest_improvements(self) -> dict:
        """Analyze feedback and generate improvement suggestions.

        Returns:
            Dictionary with:
            - category_errors: dict mapping category -> error_rate (0-1)
            - unclear_questions: list of goals with "I don't know" responses
            - slow_categories: list of categories with avg time > 5000ms
            - recommendations: list of suggested improvements
        """
        if not self.feedback_file.exists():
            logger.warning("Feedback file not found, skipping analysis")
            return {
                "category_errors": {},
                "unclear_questions": [],
                "slow_categories": [],
                "recommendations": [],
            }

        records = self._load_feedback()
        if len(records) < 10:
            logger.info(f"Only {len(records)} feedback records, skipping analysis")
            return {
                "category_errors": {},
                "unclear_questions": [],
                "slow_categories": [],
                "recommendations": [],
            }

        return {
            "category_errors": self._calculate_error_rates(records),
            "unclear_questions": self._find_unclear_questions(records),
            "slow_categories": self._find_slow_categories(records),
            "recommendations": self._generate_recommendations(records),
        }

    def _load_feedback(self) -> list[dict]:
        """Load feedback records from JSONL file."""
        records = []
        try:
            with open(self.feedback_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to load feedback: {e}")

        return records

    def _calculate_error_rates(self, records: list[dict]) -> dict:
        """Calculate error rate by category.

        Args:
            records: List of feedback records

        Returns:
            Dict mapping category -> error_rate (0-1)
        """
        category_stats: dict[str, dict] = {}

        for record in records:
            category = record.get("category", "unknown")
            result = record.get("result", "error")

            if category not in category_stats:
                category_stats[category] = {"total": 0, "errors": 0}

            category_stats[category]["total"] += 1
            if result == "error":
                category_stats[category]["errors"] += 1

        error_rates = {}
        for category, stats in category_stats.items():
            if stats["total"] > 0:
                error_rates[category] = stats["errors"] / stats["total"]

        return error_rates

    def _find_unclear_questions(self, records: list[dict]) -> list[str]:
        """Find goals that resulted in "I don't know" responses.

        Args:
            records: List of feedback records

        Returns:
            List of unclear goal texts
        """
        unclear = []
        unclear_patterns = ["i don't know", "no sé", "unclear", "ambiguo"]

        for record in records:
            responses = record.get("responses", [])
            goal = record.get("goal", "")

            for response in responses:
                if any(pat in response.lower() for pat in unclear_patterns):
                    if goal not in unclear:
                        unclear.append(goal)
                    break

        return unclear

    def _find_slow_categories(self, records: list[dict]) -> list[tuple[str, float]]:
        """Find categories with average execution time > 5000ms.

        Args:
            records: List of feedback records

        Returns:
            List of (category, avg_time_ms) tuples
        """
        category_times: dict[str, list[float]] = {}

        for record in records:
            category = record.get("category", "unknown")
            exec_time = record.get("execution_time_ms", 0.0)

            if category not in category_times:
                category_times[category] = []
            category_times[category].append(exec_time)

        slow_categories = []
        for category, times in category_times.items():
            avg_time = sum(times) / len(times) if times else 0
            if avg_time > 5000:
                slow_categories.append((category, avg_time))

        return sorted(slow_categories, key=lambda x: x[1], reverse=True)

    def _generate_recommendations(self, records: list[dict]) -> list[str]:
        """Generate actionable improvement recommendations.

        Args:
            records: List of feedback records

        Returns:
            List of recommendation strings
        """
        recommendations = []
        error_rates = self._calculate_error_rates(records)
        unclear = self._find_unclear_questions(records)
        slow = self._find_slow_categories(records)

        for category, error_rate in error_rates.items():
            if error_rate >= 0.3:
                recommendations.append(
                    f"⚠️ Category '{category}' has {error_rate:.0%} error rate - "
                    f"consider clarifying the category prompt or template"
                )

        if unclear:
            recommendations.append(
                f"📝 {len(unclear)} distinct goals resulted in unclear responses - "
                f"review and improve question templates for better disambiguation"
            )

        for category, avg_time in slow:
            recommendations.append(
                f"⏱️ Category '{category}' averages {avg_time:.0f}ms - "
                f"consider breaking into smaller sub-steps or caching results"
            )

        return recommendations


def analyze_shu_feedback(feedback_dir: Path | None = None) -> dict:
    """Convenience function to analyze feedback and get suggestions.

    Args:
        feedback_dir: Directory containing feedback.jsonl

    Returns:
        Dictionary with analysis results
    """
    engine = ShuImprovementEngine(
        feedback_file=((feedback_dir / "feedback.jsonl") if feedback_dir else None)
    )
    return engine.suggest_improvements()
