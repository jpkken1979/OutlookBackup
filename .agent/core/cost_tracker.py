#!/usr/bin/env python3
"""
Cost Tracker - LLM token and API cost tracking module.

Tracks:
- Token usage per agent
- API calls by model
- Cost estimation
- Usage analytics

Usage:
    from cost_tracker import CostTracker, track_usage

    tracker = CostTracker()
    tracker.record_usage(
        agent="architect",
        model="claude-3-opus",
        input_tokens=1000,
        output_tokens=500
    )

    report = tracker.get_report()
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Single usage record."""

    timestamp: str
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    task_type: str | None = None
    session_id: str | None = None


@dataclass
class CostReport:
    """Cost analysis report."""

    period_start: str
    period_end: str
    total_tokens: int
    total_cost: float
    by_agent: dict[str, dict] = field(default_factory=dict)
    by_model: dict[str, dict] = field(default_factory=dict)
    by_task_type: dict[str, dict] = field(default_factory=dict)
    daily_breakdown: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class CostTracker:
    """
    LLM cost tracking and optimization.

    Tracks token usage and estimates costs for various LLM providers.
    """

    # Cost per 1K tokens (approximate, varies by model)
    COST_PER_1K_TOKENS = {
        # Claude models
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
        "claude-opus-4-5": {"input": 0.015, "output": 0.075},
        # OpenAI models
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        # Google models
        "gemini-pro": {"input": 0.00025, "output": 0.0005},
        "gemini-ultra": {"input": 0.00125, "output": 0.00375},
        # Default for unknown models
        "default": {"input": 0.01, "output": 0.03},
    }

    def __init__(self, storage_path: str | None = None):
        """
        Initialize cost tracker.

        Args:
            storage_path: Path to store usage data. Defaults to .agent/data/cost_tracking.json
        """
        self.storage_path = (
            Path(storage_path) if storage_path else Path(".agent/data/cost_tracking.json")
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[UsageRecord] = []
        self._lock = Lock()
        self._load_records()

    def _load_records(self):
        """Load existing records from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.records = [UsageRecord(**r) for r in data.get("records", [])]
                logger.debug(f"Loaded {len(self.records)} cost records")
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Could not load cost records: {e}")
                self.records = []

    def _save_records(self):
        """Save records to storage."""
        try:
            data = {"records": [asdict(r) for r in self.records[-10000:]]}  # Keep last 10k records
            self.storage_path.write_text(json.dumps(data, indent=2))
        except (OSError, TypeError) as e:
            logger.warning(f"Could not save cost records: {e}")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for token usage."""
        pricing = self.COST_PER_1K_TOKENS.get(model, self.COST_PER_1K_TOKENS["default"])
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def record_usage(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        task_type: str | None = None,
        session_id: str | None = None,
    ) -> UsageRecord:
        """
        Record token usage.

        Args:
            agent: Name of the agent that used the tokens
            model: LLM model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            task_type: Optional task type (feature, bug, refactor, etc.)
            session_id: Optional session identifier

        Returns:
            UsageRecord: The recorded usage
        """
        total_tokens = input_tokens + output_tokens
        estimated_cost = self._estimate_cost(model, input_tokens, output_tokens)

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            task_type=task_type,
            session_id=session_id,
        )

        with self._lock:
            self.records.append(record)
            self._save_records()

        logger.debug(f"Recorded usage: {agent} - {total_tokens} tokens - ${estimated_cost:.4f}")
        return record

    def get_report(
        self, period_days: int = 30, agent: str | None = None, model: str | None = None
    ) -> CostReport:
        """
        Generate cost report.

        Args:
            period_days: Number of days to include in report
            agent: Filter by specific agent
            model: Filter by specific model

        Returns:
            CostReport: Detailed cost analysis
        """
        cutoff = datetime.now() - timedelta(days=period_days)
        cutoff_str = cutoff.isoformat()

        # Filter records
        filtered = [r for r in self.records if r.timestamp >= cutoff_str]
        if agent:
            filtered = [r for r in filtered if r.agent == agent]
        if model:
            filtered = [r for r in filtered if r.model == model]

        # Calculate totals
        total_tokens = sum(r.total_tokens for r in filtered)
        total_cost = sum(r.estimated_cost for r in filtered)

        # Group by agent
        by_agent: dict[str, dict] = {}
        for r in filtered:
            if r.agent not in by_agent:
                by_agent[r.agent] = {"tokens": 0, "cost": 0, "calls": 0}
            by_agent[r.agent]["tokens"] += r.total_tokens
            by_agent[r.agent]["cost"] += r.estimated_cost
            by_agent[r.agent]["calls"] += 1

        # Group by model
        by_model: dict[str, dict] = {}
        for r in filtered:
            if r.model not in by_model:
                by_model[r.model] = {"tokens": 0, "cost": 0, "calls": 0}
            by_model[r.model]["tokens"] += r.total_tokens
            by_model[r.model]["cost"] += r.estimated_cost
            by_model[r.model]["calls"] += 1

        # Group by task type
        by_task_type: dict[str, dict] = {}
        for r in filtered:
            task = r.task_type or "unknown"
            if task not in by_task_type:
                by_task_type[task] = {"tokens": 0, "cost": 0, "calls": 0}
            by_task_type[task]["tokens"] += r.total_tokens
            by_task_type[task]["cost"] += r.estimated_cost
            by_task_type[task]["calls"] += 1

        # Daily breakdown
        daily: dict[str, dict] = {}
        for r in filtered:
            day = r.timestamp[:10]
            if day not in daily:
                daily[day] = {"tokens": 0, "cost": 0}
            daily[day]["tokens"] += r.total_tokens
            daily[day]["cost"] += r.estimated_cost

        daily_breakdown = [{"date": k, **v} for k, v in sorted(daily.items())]

        # Generate recommendations
        recommendations = []

        # Check for expensive models
        if by_model.get("gpt-4", {}).get("cost", 0) > total_cost * 0.5:
            recommendations.append("Consider using GPT-4-Turbo or Claude for cost savings")

        # Check for high-usage agents
        sorted_agents = sorted(by_agent.items(), key=lambda x: x[1]["cost"], reverse=True)
        if sorted_agents and sorted_agents[0][1]["cost"] > total_cost * 0.4:
            recommendations.append(
                f"Agent '{sorted_agents[0][0]}' accounts for {sorted_agents[0][1]['cost'] / total_cost * 100:.0f}% of costs"
            )

        # Check for optimization opportunities
        if total_cost > 100:
            recommendations.append("Consider implementing response caching for repeated queries")
        if len(filtered) > 1000:
            recommendations.append("High API call volume - consider batching requests")

        return CostReport(
            period_start=cutoff_str,
            period_end=datetime.now().isoformat(),
            total_tokens=total_tokens,
            total_cost=round(total_cost, 2),
            by_agent={
                k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
                for k, v in by_agent.items()
            },
            by_model={
                k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
                for k, v in by_model.items()
            },
            by_task_type={
                k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
                for k, v in by_task_type.items()
            },
            daily_breakdown=daily_breakdown,
            recommendations=recommendations,
        )

    def get_budget_status(self, monthly_budget: float) -> dict:
        """
        Check current spending against budget.

        Args:
            monthly_budget: Monthly budget in dollars

        Returns:
            Budget status with remaining amount and projections
        """
        report = self.get_report(period_days=30)
        daily_avg = report.total_cost / 30 if report.total_cost > 0 else 0
        projected_monthly = daily_avg * 30

        return {
            "spent": round(report.total_cost, 2),
            "budget": monthly_budget,
            "remaining": round(monthly_budget - report.total_cost, 2),
            "percentage_used": round((report.total_cost / monthly_budget) * 100, 1)
            if monthly_budget > 0
            else 0,
            "daily_average": round(daily_avg, 2),
            "projected_monthly": round(projected_monthly, 2),
            "on_track": projected_monthly <= monthly_budget,
            "days_remaining": 30 - (datetime.now().day),
        }

    def clear_old_records(self, days_to_keep: int = 90):
        """
        Clear records older than specified days.

        Args:
            days_to_keep: Number of days of records to keep
        """
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff.isoformat()

        with self._lock:
            original_count = len(self.records)
            self.records = [r for r in self.records if r.timestamp > cutoff_str]
            removed = original_count - len(self.records)
            self._save_records()

        logger.info(f"Cleared {removed} old cost records")


# Convenience decorator for tracking
def track_usage(agent: str, model: str = "default"):
    """
    Decorator to track function usage.

    Args:
        agent: Agent name
        model: Model name

    Usage:
        @track_usage("architect", "claude-3-opus")
        async def my_function():
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracker = CostTracker()
            start_tokens = kwargs.pop("_input_tokens", 1000)

            result = await func(*args, **kwargs)

            output_tokens = len(str(result)) // 4  # Rough estimate
            tracker.record_usage(agent, model, start_tokens, output_tokens)

            return result

        return wrapper

    return decorator


# Global instance
_global_tracker: CostTracker | None = None


def get_tracker() -> CostTracker:
    """Get global cost tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


if __name__ == "__main__":
    # Demo
    tracker = CostTracker()

    # Simulate some usage
    tracker.record_usage("architect", "claude-3-opus", 2000, 1000, "feature")
    tracker.record_usage("backend-specialist", "claude-3-sonnet", 1500, 800, "feature")
    tracker.record_usage("test-engineer", "claude-3-haiku", 500, 200, "testing")

    report = tracker.get_report(period_days=7)
    print(f"Total cost: ${report.total_cost}")
    print(f"Total tokens: {report.total_tokens}")
    print(f"By agent: {json.dumps(report.by_agent, indent=2)}")
