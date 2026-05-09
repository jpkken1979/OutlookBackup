"""
Meta-Orchestrator - Evaluación de calidad post-ejecución.

Capa 3 del pipeline de orquestación (post-ejecución):
- Evalúa la calidad de ejecución
- Sugiere mejoras basadas en patrones
- Alimenta el learning loop para optimización futura

Jerarquía de orquestación (3 módulos):
    IntelligentOrchestrator.analyze()  → análisis y estrategia
    Orchestrator.execute()             → ejecución con fallback 3-tier
    MetaOrchestrator.evaluate()        → calidad post-ejecución (este módulo)

Version: 1.0.0
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Quality levels for execution assessment."""

    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 75-89%
    ACCEPTABLE = "acceptable"  # 60-74%
    POOR = "poor"  # 40-59%
    FAILED = "failed"  # <40%


class ImprovementType(Enum):
    """Types of improvement suggestions."""

    AGENT_SELECTION = "agent_selection"
    EXECUTION_ORDER = "execution_order"
    PARALLELIZATION = "parallelization"
    TIMEOUT_ADJUSTMENT = "timeout_adjustment"
    ERROR_HANDLING = "error_handling"
    RESOURCE_ALLOCATION = "resource_allocation"
    STRATEGY_CHANGE = "strategy_change"


@dataclass
class ExecutionPlan:
    """An execution plan to evaluate."""

    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    strategy: str = ""  # sequential, parallel, debate, etc.
    agents: list = field(default_factory=list)
    phases: list = field(default_factory=list)
    estimated_duration: int = 0  # seconds
    risk_level: str = "medium"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "task": self.task,
            "strategy": self.strategy,
            "agents": self.agents,
            "phases": self.phases,
            "estimated_duration": self.estimated_duration,
            "risk_level": self.risk_level,
            "metadata": self.metadata,
        }


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent: str
    success: bool
    output: dict = field(default_factory=dict)
    duration_ms: int = 0
    error: str | None = None
    quality_score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "success": self.success,
            "output": self.output,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
        }


@dataclass
class QualityAssessment:
    """Assessment of execution quality."""

    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    overall_score: float = 0.0
    agent_scores: dict = field(default_factory=dict)
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    bottlenecks: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "assessment_id": self.assessment_id,
            "plan_id": self.plan_id,
            "quality_level": self.quality_level.value,
            "overall_score": self.overall_score,
            "agent_scores": self.agent_scores,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "bottlenecks": self.bottlenecks,
            "suggestions": self.suggestions,
            "metrics": self.metrics,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Improvement:
    """An improvement suggestion."""

    improvement_type: ImprovementType
    description: str
    expected_impact: str
    implementation: str
    priority: int = 1  # 1-5, higher = more important
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "improvement_type": self.improvement_type.value,
            "description": self.description,
            "expected_impact": self.expected_impact,
            "implementation": self.implementation,
            "priority": self.priority,
            "confidence": self.confidence,
        }


class MetaOrchestrator:
    """
    Oversees and improves orchestration quality.

    Evaluates execution quality, suggests improvements,
    and can adapt strategies mid-execution.
    """

    def __init__(self, history_path: Path | None = None):
        self.history_path = history_path or Path(".agent/data/meta")
        self.history_path.mkdir(parents=True, exist_ok=True)
        self.assessments: list[QualityAssessment] = []
        self.patterns: dict[str, dict] = {}  # Learned patterns
        self._load_history()

    def _load_history(self):
        """Load historical assessments."""
        history_file = self.history_path / "assessments.json"
        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    data = json.load(f)
                    # Could deserialize assessments here
                    logger.info(f"Loaded {len(data.get('assessments', []))} historical assessments")
            except Exception as e:
                logger.error(f"Error loading history: {e}")

    def _save_history(self):
        """Save assessments to disk."""
        history_file = self.history_path / "assessments.json"
        try:
            data = {
                "assessments": [a.to_dict() for a in self.assessments[-100:]],
                "patterns": self.patterns,
                "last_saved": datetime.now().isoformat(),
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    async def evaluate_execution(
        self, plan: ExecutionPlan, results: list[AgentResult]
    ) -> QualityAssessment:
        """
        Evaluate how well an execution went.

        Args:
            plan: The execution plan used
            results: Results from each agent

        Returns:
            QualityAssessment with detailed analysis
        """
        # Calculate metrics
        total_agents = len(results)
        successful = sum(1 for r in results if r.success)
        total_duration = sum(r.duration_ms for r in results)

        # Calculate scores
        success_rate = successful / total_agents if total_agents > 0 else 0
        avg_quality = (
            sum(r.quality_score for r in results) / total_agents if total_agents > 0 else 0
        )

        # Duration efficiency (compared to estimate)
        duration_efficiency = 1.0
        if plan.estimated_duration > 0:
            actual_seconds = total_duration / 1000
            duration_efficiency = min(1.0, plan.estimated_duration / max(actual_seconds, 1))

        # Overall score (weighted)
        overall_score = success_rate * 0.4 + avg_quality * 0.3 + duration_efficiency * 0.3

        # Determine quality level
        if overall_score >= 0.9:
            quality_level = QualityLevel.EXCELLENT
        elif overall_score >= 0.75:
            quality_level = QualityLevel.GOOD
        elif overall_score >= 0.6:
            quality_level = QualityLevel.ACCEPTABLE
        elif overall_score >= 0.4:
            quality_level = QualityLevel.POOR
        else:
            quality_level = QualityLevel.FAILED

        # Analyze strengths
        strengths = []
        if success_rate >= 0.9:
            strengths.append("High agent success rate")
        if duration_efficiency >= 0.8:
            strengths.append("Efficient execution time")
        if avg_quality >= 0.8:
            strengths.append("High quality outputs")

        # Analyze weaknesses
        weaknesses = []
        failed_agents = [r.agent for r in results if not r.success]
        if failed_agents:
            weaknesses.append(f"Agent failures: {', '.join(failed_agents)}")
        if duration_efficiency < 0.5:
            weaknesses.append("Execution took longer than expected")

        # Find bottlenecks (slowest agents)
        sorted_by_duration = sorted(results, key=lambda r: r.duration_ms, reverse=True)
        bottlenecks = [
            f"{r.agent} ({r.duration_ms}ms)"
            for r in sorted_by_duration[:3]
            if r.duration_ms > total_duration / total_agents * 2  # More than 2x average
        ]

        # Agent scores
        agent_scores = {r.agent: r.quality_score for r in results}

        assessment = QualityAssessment(
            plan_id=plan.plan_id,
            quality_level=quality_level,
            overall_score=overall_score,
            agent_scores=agent_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            bottlenecks=bottlenecks,
            metrics={
                "success_rate": success_rate,
                "avg_quality": avg_quality,
                "duration_efficiency": duration_efficiency,
                "total_duration_ms": total_duration,
                "agents_used": total_agents,
            },
        )

        self.assessments.append(assessment)
        self._save_history()

        logger.info(f"Execution evaluated: {quality_level.value} ({overall_score:.2f})")
        return assessment

    async def suggest_improvements(self, assessment: QualityAssessment) -> list[Improvement]:
        """
        Suggest improvements based on assessment.

        Args:
            assessment: Quality assessment to analyze

        Returns:
            List of improvement suggestions
        """
        improvements = []

        # Check for agent failures
        if assessment.weaknesses:
            for weakness in assessment.weaknesses:
                if "failure" in weakness.lower():
                    improvements.append(
                        Improvement(
                            improvement_type=ImprovementType.ERROR_HANDLING,
                            description="Add retry logic for failing agents",
                            expected_impact="Reduce failure rate by 50%",
                            implementation="Wrap agent calls in retry with exponential backoff",
                            priority=5,
                            confidence=0.8,
                        )
                    )
                    break

        # Check for bottlenecks
        if assessment.bottlenecks:
            improvements.append(
                Improvement(
                    improvement_type=ImprovementType.PARALLELIZATION,
                    description="Parallelize independent agent calls",
                    expected_impact="Reduce total execution time",
                    implementation="Use asyncio.gather for independent agents",
                    priority=4,
                    confidence=0.7,
                )
            )

        # Check duration efficiency
        if assessment.metrics.get("duration_efficiency", 1.0) < 0.5:
            improvements.append(
                Improvement(
                    improvement_type=ImprovementType.TIMEOUT_ADJUSTMENT,
                    description="Adjust timeout settings",
                    expected_impact="Better resource utilization",
                    implementation="Increase timeouts or add early termination",
                    priority=3,
                    confidence=0.6,
                )
            )

        # Check quality scores
        low_quality_agents = [
            agent for agent, score in assessment.agent_scores.items() if score < 0.5
        ]
        if low_quality_agents:
            improvements.append(
                Improvement(
                    improvement_type=ImprovementType.AGENT_SELECTION,
                    description=f"Review agent selection: {', '.join(low_quality_agents)}",
                    expected_impact="Improve output quality",
                    implementation="Consider alternative agents or provide more context",
                    priority=4,
                    confidence=0.65,
                )
            )

        # Sort by priority
        improvements.sort(key=lambda i: i.priority, reverse=True)
        return improvements

    async def adapt_strategy(
        self,
        task: str,
        current_strategy: str,
        historical_assessments: list[QualityAssessment] | None = None,
    ) -> dict:
        """
        Adapt strategy based on historical feedback.

        Args:
            task: Task description
            current_strategy: Current strategy being used
            historical_assessments: Past assessments to learn from

        Returns:
            Adapted strategy configuration
        """
        assessments = historical_assessments or self.assessments[-10:]

        # Analyze historical performance by strategy
        strategy_scores: dict[str, list[float]] = {}
        for a in assessments:
            strategy = a.metrics.get("strategy", "sequential")
            if strategy not in strategy_scores:
                strategy_scores[strategy] = []
            strategy_scores[strategy].append(a.overall_score)

        # Calculate averages
        strategy_averages = {
            s: sum(scores) / len(scores) for s, scores in strategy_scores.items() if scores
        }

        # Find best strategy
        if strategy_averages:
            best_strategy = max(strategy_averages, key=strategy_averages.get)  # type: ignore[arg-type]  # dict.get is valid key func
        else:
            best_strategy = current_strategy

        # Build adapted configuration
        adapted = {
            "strategy": best_strategy,
            "adaptations": [],  # type: ignore[var-annotated]  # dict with mixed value types
            "confidence": 0.5,
        }

        # Add specific adaptations based on patterns
        if current_strategy != best_strategy:
            adapted["adaptations"].append(
                {  # type: ignore[attr-defined]  # list value in dict
                    "type": "strategy_change",
                    "from": current_strategy,
                    "to": best_strategy,
                    "reason": f"Historical score: {strategy_averages.get(best_strategy, 0):.2f}",
                }
            )
            adapted["confidence"] = 0.7

        # Check for task-specific patterns
        task_lower = task.lower()
        if "bug" in task_lower or "fix" in task_lower:
            adapted["adaptations"].append(
                {  # type: ignore[attr-defined]  # list value in dict
                    "type": "priority_agent",
                    "agent": "debugger",
                    "reason": "Task involves bug fixing",
                }
            )
        elif "security" in task_lower:
            adapted["adaptations"].append(
                {  # type: ignore[attr-defined]  # list value in dict
                    "type": "mandatory_agent",
                    "agent": "security-auditor",
                    "reason": "Security-related task",
                }
            )

        return adapted

    async def replan_if_needed(
        self,
        current_plan: ExecutionPlan,
        partial_results: list[AgentResult],
        threshold: float = 0.5,
    ) -> ExecutionPlan | None:
        """
        Replan mid-execution if things are going wrong.

        Args:
            current_plan: Current execution plan
            partial_results: Results so far
            threshold: Quality threshold to trigger replan

        Returns:
            New plan if replanning needed, None otherwise
        """
        if not partial_results:
            return None

        # Calculate current success rate
        successful = sum(1 for r in partial_results if r.success)
        success_rate = successful / len(partial_results)

        # Check if replanning is needed
        if success_rate >= threshold:
            return None

        logger.warning(f"Triggering replan: success rate {success_rate:.2f} < {threshold}")

        # Identify failed agents
        failed_agents = [r.agent for r in partial_results if not r.success]
        remaining_agents = [
            a for a in current_plan.agents if a not in [r.agent for r in partial_results]
        ]

        # Create new plan
        new_plan = ExecutionPlan(
            task=current_plan.task,
            strategy="sequential",  # Fall back to sequential for stability
            agents=remaining_agents,
            phases=[
                {
                    "name": "recovery",
                    "agents": remaining_agents,
                    "description": f"Continuing after {len(failed_agents)} failures",
                }
            ],
            metadata={
                "original_plan": current_plan.plan_id,
                "failed_agents": failed_agents,
                "replan_reason": f"Success rate {success_rate:.2f} below threshold",
            },
        )

        return new_plan

    async def should_terminate(
        self, plan: ExecutionPlan, results: list[AgentResult], time_elapsed_ms: int
    ) -> tuple[bool, str]:
        """
        Decide if execution should be terminated.

        Args:
            plan: Current plan
            results: Results so far
            time_elapsed_ms: Time elapsed

        Returns:
            (should_terminate, reason)
        """
        # Check timeout
        max_duration_ms = plan.estimated_duration * 1000 * 2  # 2x estimate
        if time_elapsed_ms > max_duration_ms:
            return True, "Execution exceeded maximum duration"

        # Check failure rate
        if len(results) >= 3:
            failures = sum(1 for r in results if not r.success)
            if failures / len(results) > 0.7:
                return True, "Too many agent failures"

        # Check for critical errors
        for result in results:
            if result.error and "critical" in result.error.lower():
                return True, f"Critical error in {result.agent}"

        return False, ""

    def get_stats(self) -> dict:
        """Get meta-orchestrator statistics."""
        if not self.assessments:
            return {"total_assessments": 0}

        scores = [a.overall_score for a in self.assessments]
        levels = [a.quality_level.value for a in self.assessments]

        return {
            "total_assessments": len(self.assessments),
            "avg_score": sum(scores) / len(scores),
            "best_score": max(scores),
            "worst_score": min(scores),
            "quality_distribution": {level: levels.count(level) for level in set(levels)},
        }


# Singleton instance
_meta_instance: MetaOrchestrator | None = None


def get_meta_orchestrator() -> MetaOrchestrator:
    """Get the global MetaOrchestrator instance."""
    global _meta_instance
    if _meta_instance is None:
        _meta_instance = MetaOrchestrator()
    return _meta_instance


# Example usage
if __name__ == "__main__":

    async def demo():
        meta = get_meta_orchestrator()

        # Create a plan
        plan = ExecutionPlan(
            task="Implement user authentication",
            strategy="parallel",
            agents=["architect", "backend-specialist", "security-auditor"],
            estimated_duration=60,
        )

        # Simulate results
        results = [
            AgentResult(agent="architect", success=True, duration_ms=5000, quality_score=0.9),
            AgentResult(
                agent="backend-specialist", success=True, duration_ms=15000, quality_score=0.8
            ),
            AgentResult(agent="security-auditor", success=False, duration_ms=8000, error="Timeout"),
        ]

        # Evaluate
        assessment = await meta.evaluate_execution(plan, results)
        print(f"Assessment: {assessment.to_dict()}")

        # Get improvements
        improvements = await meta.suggest_improvements(assessment)
        print(f"Improvements: {[i.to_dict() for i in improvements]}")

        # Check stats
        print(f"Stats: {meta.get_stats()}")

    asyncio.run(demo())
