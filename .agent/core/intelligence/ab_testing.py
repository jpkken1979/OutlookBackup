# mypy: ignore-errors
#!/usr/bin/env python3
"""
A/B Agent Testing - Compare agent performance with controlled experiments.

This module provides A/B testing capabilities that:
1. Run same task against multiple agents
2. Compare outputs objectively
3. Measure performance metrics
4. Generate statistical analysis
5. Identify best performer

Usage:
    from .agent.core.intelligence import ABTester, run_ab_test

    tester = ABTester()

    # Compare two agents
    result = await tester.compare(
        task="Design a REST API for user management",
        agents=["architect", "api-designer"],
        metrics=["quality", "speed", "completeness"]
    )

    print(f"Winner: {result.winner}")
    print(f"Confidence: {result.statistical_confidence:.0%}")
"""

import json
import logging
import os
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.ab_testing")


class MetricType(Enum):
    """Types of metrics to measure."""

    QUALITY = "quality"  # Output quality score
    SPEED = "speed"  # Execution time
    COMPLETENESS = "completeness"  # Task completion
    CORRECTNESS = "correctness"  # Technical accuracy
    CLARITY = "clarity"  # Output clarity
    EFFICIENCY = "efficiency"  # Resource efficiency
    CONSISTENCY = "consistency"  # Output consistency
    USER_PREFERENCE = "user_preference"  # User rating


class TestStatus(Enum):
    """Status of an A/B test."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentOutput:
    """Output from an agent in a test."""

    agent_name: str
    output: str
    execution_time_ms: int
    metrics: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "output_length": len(self.output),
            "execution_time_ms": self.execution_time_ms,
            "metrics": self.metrics,
            "error": self.error,
        }


@dataclass
class ComparisonResult:
    """Result of comparing two agent outputs."""

    metric: str
    agent_a: str
    agent_b: str
    score_a: float
    score_b: float
    winner: str
    difference: float
    significant: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "winner": self.winner,
            "difference": self.difference,
            "significant": self.significant,
        }


@dataclass
class ABTestResult:
    """Result of an A/B test."""

    test_id: str
    task: str
    agents: list[str]
    winner: str
    runner_up: str
    scores: dict[str, float]
    metrics_breakdown: dict[str, dict[str, float]]
    comparisons: list[ComparisonResult]
    statistical_confidence: float
    sample_size: int
    execution_time_ms: int
    insights: list[str]
    recommendations: list[str]
    outputs: list[AgentOutput]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "task": self.task,
            "agents": self.agents,
            "winner": self.winner,
            "runner_up": self.runner_up,
            "scores": self.scores,
            "metrics_breakdown": self.metrics_breakdown,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "statistical_confidence": self.statistical_confidence,
            "sample_size": self.sample_size,
            "execution_time_ms": self.execution_time_ms,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
        }


class MetricEvaluator:
    """Evaluates metrics for agent outputs."""

    def __init__(self):
        self.evaluators: dict[MetricType, Callable] = {
            MetricType.QUALITY: self._evaluate_quality,
            MetricType.SPEED: self._evaluate_speed,
            MetricType.COMPLETENESS: self._evaluate_completeness,
            MetricType.CORRECTNESS: self._evaluate_correctness,
            MetricType.CLARITY: self._evaluate_clarity,
            MetricType.EFFICIENCY: self._evaluate_efficiency,
            MetricType.CONSISTENCY: self._evaluate_consistency,
        }

    def evaluate(
        self,
        output: AgentOutput,
        task: str,
        metric: MetricType,
    ) -> float:
        """Evaluate a metric for an output."""
        evaluator = self.evaluators.get(metric, self._default_evaluator)
        return evaluator(output, task)

    def _evaluate_quality(self, output: AgentOutput, task: str) -> float:
        """Evaluate output quality (0-1)."""
        score = 0.5  # Base score

        text = output.output

        # Length bonus (but not too long)
        word_count = len(text.split())
        if 100 < word_count < 1000:
            score += 0.15
        elif 50 < word_count < 2000:
            score += 0.1

        # Structure bonus
        if "##" in text or "###" in text:
            score += 0.1
        if "```" in text:
            score += 0.1
        if "- " in text or "* " in text:
            score += 0.05

        # Task relevance
        task_words = set(task.lower().split())
        output_words = set(text.lower().split())
        relevance = len(task_words & output_words) / max(len(task_words), 1)
        score += relevance * 0.1

        return min(1.0, score)

    def _evaluate_speed(self, output: AgentOutput, task: str) -> float:
        """Evaluate speed (0-1, faster is better)."""
        time_ms = output.execution_time_ms

        # Normalize to 0-1 (assuming <1s is excellent, >30s is poor)
        if time_ms < 1000:
            return 1.0
        elif time_ms < 5000:
            return 0.9
        elif time_ms < 10000:
            return 0.7
        elif time_ms < 30000:
            return 0.5
        else:
            return max(0.1, 1.0 - time_ms / 60000)

    def _evaluate_completeness(self, output: AgentOutput, task: str) -> float:
        """Evaluate task completeness (0-1)."""
        text = output.output.lower()
        task_lower = task.lower()

        # Check for key task elements
        score = 0.5

        # Extract potential requirements from task
        requirement_indicators = ["must", "should", "need", "require", "include"]
        found_requirements = 0
        total_requirements = 0

        for indicator in requirement_indicators:
            if indicator in task_lower:
                total_requirements += 1
                # Check if addressed in output
                if any(word in text for word in task_lower.split()):
                    found_requirements += 1

        if total_requirements > 0:
            score += 0.3 * (found_requirements / total_requirements)

        # Check for conclusion/summary
        conclusion_indicators = ["conclusion", "summary", "in summary", "therefore", "thus"]
        if any(ind in text for ind in conclusion_indicators):
            score += 0.1

        # Check for error (incomplete)
        if output.error:
            score -= 0.3

        return max(0.0, min(1.0, score))

    def _evaluate_correctness(self, output: AgentOutput, task: str) -> float:
        """Evaluate technical correctness (0-1)."""
        text = output.output.lower()

        score = 0.7  # Assume mostly correct by default

        # Penalty for uncertainty language
        uncertainty_words = ["maybe", "perhaps", "might", "possibly", "i think", "not sure"]
        uncertainty_count = sum(1 for w in uncertainty_words if w in text)
        score -= uncertainty_count * 0.05

        # Penalty for contradictions
        if "but actually" in text or "however, that's wrong" in text:
            score -= 0.2

        # Bonus for citations/references
        if "according to" in text or "reference" in text or "documentation" in text:
            score += 0.1

        return max(0.0, min(1.0, score))

    def _evaluate_clarity(self, output: AgentOutput, task: str) -> float:
        """Evaluate output clarity (0-1)."""
        text = output.output

        score = 0.5

        # Average sentence length (shorter is clearer, to a point)
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        if sentences:
            avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
            if 10 < avg_len < 25:
                score += 0.2
            elif 5 < avg_len < 35:
                score += 0.1

        # Headers for organization
        if "##" in text:
            score += 0.15

        # Lists for enumeration
        if "- " in text or "1." in text:
            score += 0.1

        # Not too much jargon (simple heuristic)
        long_words = [w for w in text.split() if len(w) > 12]
        if len(long_words) / max(len(text.split()), 1) < 0.1:
            score += 0.05

        return min(1.0, score)

    def _evaluate_efficiency(self, output: AgentOutput, task: str) -> float:
        """Evaluate resource efficiency (0-1)."""
        # Combine speed and output quality per unit time
        speed_score = self._evaluate_speed(output, task)
        quality_score = self._evaluate_quality(output, task)

        # Efficiency is quality achieved per time unit
        return speed_score * 0.4 + quality_score * 0.6

    def _evaluate_consistency(self, output: AgentOutput, task: str) -> float:
        """Evaluate output consistency (0-1)."""
        text = output.output

        score = 0.7  # Base score

        # Check for consistent formatting
        lines = text.split("\n")
        if len(lines) > 3:
            # Check heading consistency
            heading_styles = set()
            for line in lines:
                if line.startswith("#"):
                    heading_styles.add(len(line) - len(line.lstrip("#")))

            if len(heading_styles) <= 3:
                score += 0.1

        # Check for consistent list style
        list_bullets = [line[0] for line in lines if line.strip() and line.strip()[0] in "-*•"]
        if list_bullets and len(set(list_bullets)) == 1:
            score += 0.1

        return min(1.0, score)

    def _default_evaluator(self, output: AgentOutput, task: str) -> float:
        """Default evaluator returns average."""
        return 0.5


class StatisticalAnalyzer:
    """Performs statistical analysis on test results."""

    def compare_scores(
        self,
        scores_a: list[float],
        scores_b: list[float],
        significance_level: float = 0.05,
    ) -> dict[str, Any]:
        """Compare two sets of scores statistically."""
        if not scores_a or not scores_b:
            return {"significant": False, "p_value": 1.0}

        mean_a = statistics.mean(scores_a)
        mean_b = statistics.mean(scores_b)

        # Simple significance check (would use proper t-test in production)
        diff = abs(mean_a - mean_b)

        # Estimate variance
        var_a = statistics.variance(scores_a) if len(scores_a) > 1 else 0.1

        var_b = statistics.variance(scores_b) if len(scores_b) > 1 else 0.1

        # Simplified significance check
        pooled_var = (var_a + var_b) / 2
        standard_error = (pooled_var / min(len(scores_a), len(scores_b))) ** 0.5

        # Rough z-score
        if standard_error > 0:
            z_score = diff / standard_error
            if significance_level <= 0.05:
                threshold = 1.96
            elif significance_level <= 0.10:
                threshold = 1.64
            else:
                threshold = 1.28
            significant = z_score > threshold
        else:
            significant = diff > 0.05

        return {
            "mean_a": mean_a,
            "mean_b": mean_b,
            "difference": mean_a - mean_b,
            "significant": significant,
            "confidence": min(0.99, 0.5 + abs(diff) * 2) if significant else 0.5,
        }

    def calculate_confidence(
        self,
        results: list[ComparisonResult],
    ) -> float:
        """Calculate overall confidence in the test result."""
        if not results:
            return 0.5

        significant_count = sum(1 for r in results if r.significant)
        total = len(results)

        # Base confidence from significant results
        base = significant_count / total

        # Bonus for consistency (all pointing same direction)
        winners = [r.winner for r in results]
        if len(set(winners)) == 1:
            base += 0.1

        return min(0.99, max(0.5, base))


class ABTester:
    """
    Performs A/B testing between agents.

    This class:
    1. Runs tasks against multiple agents
    2. Measures performance metrics
    3. Compares results statistically
    4. Identifies winners
    """

    def __init__(self, memory_dir: Path | None = None):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_AB_TESTING_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_AB_TESTING_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "ab_testing"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.evaluator = MetricEvaluator()
        self.analyzer = StatisticalAnalyzer()

        # Test history
        self.test_history: list[ABTestResult] = []

        # Mock execution function (would call actual agents)
        self._execute_agent: Callable | None = None

    def set_executor(self, executor: Callable) -> None:
        """Set the agent execution function."""
        self._execute_agent = executor

    async def _run_all_agents(
        self, agents: list[str], task: str, runs_per_agent: int, context: dict[str, Any]
    ) -> list[AgentOutput]:
        """Ejecuta cada agente `runs_per_agent` veces sobre la tarea.

        Returns:
            Lista plana de AgentOutput (en orden agente x corrida).
        """
        outputs: list[AgentOutput] = []
        for agent in agents:
            for _ in range(runs_per_agent):
                outputs.append(await self._run_agent(agent, task, context))
        return outputs

    def _evaluate_outputs(
        self,
        outputs: list[AgentOutput],
        metrics: list[str],
        agents: list[str],
        task: str,
    ) -> dict[str, dict[str, Any]]:
        """Evalúa cada métrica para cada output y acumula scores por agente.

        Returns:
            Breakdown agente -> métrica -> lista de scores (sin promediar aún).
        """
        valid_metrics = {m.value for m in MetricType}
        breakdown: dict[str, dict[str, Any]] = {agent: {} for agent in agents}
        for output in outputs:
            for metric_name in metrics:
                metric_type = (
                    MetricType(metric_name) if metric_name in valid_metrics else MetricType.QUALITY
                )
                score = self.evaluator.evaluate(output, task, metric_type)
                output.metrics[metric_name] = score
                breakdown[output.agent_name].setdefault(metric_name, []).append(score)
        return breakdown

    @staticmethod
    def _average_breakdown(
        breakdown: dict[str, dict[str, Any]], agents: list[str], metrics: list[str]
    ) -> None:
        """Reemplaza in-place las listas de scores por su media."""
        for agent in agents:
            for metric in metrics:
                if isinstance(breakdown[agent].get(metric), list):
                    scores = breakdown[agent][metric]
                    breakdown[agent][metric] = statistics.mean(scores) if scores else 0.0

    async def compare(
        self,
        task: str,
        agents: list[str],
        metrics: list[str] | None = None,
        runs_per_agent: int = 1,
        context: dict[str, Any] | None = None,
    ) -> ABTestResult:
        """
        Compare multiple agents on a task.

        Args:
            task: Task description
            agents: List of agent names to compare
            metrics: Metrics to evaluate
            runs_per_agent: Number of runs per agent
            context: Additional context

        Returns:
            ABTestResult with comparison data
        """
        import time

        start_time = time.time()

        metrics = metrics or ["quality", "speed", "completeness"]
        context = context or {}

        # Generate test ID
        test_id = f"ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting A/B test {test_id}: {len(agents)} agents, {len(metrics)} metrics")

        # Run agents
        outputs = await self._run_all_agents(agents, task, runs_per_agent, context)

        # Evaluate metrics para cada output y promediar
        metrics_breakdown = self._evaluate_outputs(outputs, metrics, agents, task)
        self._average_breakdown(metrics_breakdown, agents, metrics)

        # Calculate overall scores
        scores = {}
        for agent in agents:
            agent_scores = [metrics_breakdown[agent].get(m, 0) for m in metrics]
            scores[agent] = statistics.mean(agent_scores) if agent_scores else 0.0

        # Generate comparisons
        comparisons = self._generate_comparisons(agents, metrics_breakdown)

        # Determine winner
        sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_agents[0][0]
        runner_up = sorted_agents[1][0] if len(sorted_agents) > 1 else winner

        # Calculate statistical confidence
        statistical_confidence = self.analyzer.calculate_confidence(comparisons)

        # Generate insights
        insights = self._generate_insights(winner, runner_up, metrics_breakdown, comparisons)

        # Generate recommendations
        recommendations = self._generate_recommendations(winner, metrics_breakdown, comparisons)

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = ABTestResult(
            test_id=test_id,
            task=task,
            agents=agents,
            winner=winner,
            runner_up=runner_up,
            scores=scores,
            metrics_breakdown=metrics_breakdown,
            comparisons=comparisons,
            statistical_confidence=statistical_confidence,
            sample_size=len(outputs),
            execution_time_ms=elapsed_ms,
            insights=insights,
            recommendations=recommendations,
            outputs=outputs,
        )

        self.test_history.append(result)
        self._save_result(result)

        return result

    async def _run_agent(
        self,
        agent_name: str,
        task: str,
        context: dict[str, Any],
    ) -> AgentOutput:
        """Run an agent on a task."""
        import time

        start_time = time.time()

        try:
            if self._execute_agent:
                output = await self._execute_agent(agent_name, task, context)
            else:
                # Simulate agent output for testing
                output = self._simulate_agent_output(agent_name, task)

            elapsed_ms = int((time.time() - start_time) * 1000)

            return AgentOutput(
                agent_name=agent_name,
                output=output,
                execution_time_ms=elapsed_ms,
                metrics={},
            )

        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}")
            return AgentOutput(
                agent_name=agent_name,
                output="",
                execution_time_ms=int((time.time() - start_time) * 1000),
                metrics={},
                error=str(e),
            )

    def _simulate_agent_output(self, agent_name: str, task: str) -> str:
        """Simulate agent output for testing."""
        # Simple simulation based on agent type
        random.uniform(0.6, 0.9)

        output = f"# {agent_name.title()} Response\n\n"
        output += f"## Task Analysis\n\nAnalyzing: {task}\n\n"
        output += "## Approach\n\n- Step 1: Understand requirements\n- Step 2: Design solution\n- Step 3: Implement\n\n"
        output += "## Conclusion\n\nThis approach addresses the key requirements.\n"

        # Add some variation
        if "architect" in agent_name:
            output += "\n```\nArchitecture diagram here\n```\n"
        if "api" in agent_name:
            output += '\n```json\n{"endpoint": "/api/v1/resource"}\n```\n'

        return output

    def _generate_comparisons(
        self,
        agents: list[str],
        metrics_breakdown: dict[str, dict[str, float]],
    ) -> list[ComparisonResult]:
        """Generate pairwise comparisons."""
        comparisons = []

        for i, agent_a in enumerate(agents):
            for agent_b in agents[i + 1 :]:
                for metric, score_a in metrics_breakdown[agent_a].items():
                    score_b = metrics_breakdown[agent_b].get(metric, 0)

                    difference = score_a - score_b
                    winner = agent_a if difference > 0 else agent_b
                    significant = abs(difference) > 0.1

                    comparisons.append(
                        ComparisonResult(
                            metric=metric,
                            agent_a=agent_a,
                            agent_b=agent_b,
                            score_a=score_a,
                            score_b=score_b,
                            winner=winner,
                            difference=abs(difference),
                            significant=significant,
                        )
                    )

        return comparisons

    def _generate_insights(
        self,
        winner: str,
        runner_up: str,
        metrics: dict[str, dict[str, float]],
        comparisons: list[ComparisonResult],
    ) -> list[str]:
        """Generate insights from test results."""
        insights = []

        # Winner insight
        winner_score = sum(metrics[winner].values()) / len(metrics[winner])
        insights.append(f"{winner} performed best with average score {winner_score:.0%}")

        # Metric-specific insights
        for metric in metrics[winner]:
            winner_metric = metrics[winner][metric]
            runner_metric = metrics[runner_up].get(metric, 0)

            if winner_metric > runner_metric + 0.2:
                insights.append(f"{winner} significantly outperformed on {metric}")
            elif runner_metric > winner_metric + 0.1:
                insights.append(f"{runner_up} was stronger on {metric}")

        # Significant comparisons
        significant = [c for c in comparisons if c.significant]
        if significant:
            insights.append(f"{len(significant)} comparisons showed significant differences")

        return insights[:5]

    def _generate_recommendations(
        self,
        winner: str,
        metrics: dict[str, dict[str, float]],
        comparisons: list[ComparisonResult],
    ) -> list[str]:
        """Generate recommendations from results."""
        recommendations = []

        recommendations.append(f"Use {winner} for similar tasks")

        # Check for weak areas
        for metric, score in metrics[winner].items():
            if score < 0.6:
                recommendations.append(f"Improve {winner}'s {metric} (currently {score:.0%})")

        # Check if results are close
        scores = [sum(m.values()) / len(m) for m in metrics.values()]
        if max(scores) - min(scores) < 0.1:
            recommendations.append("Consider additional factors - agents performed similarly")

        return recommendations[:4]

    def _save_result(self, result: ABTestResult) -> None:
        """Save test result to disk."""
        filename = f"{result.test_id}.json"
        filepath = self.memory_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)

    def get_test_history(self, limit: int = 10) -> list[ABTestResult]:
        """Get recent test history."""
        return self.test_history[-limit:]

    def export_report(self) -> str:
        """Export testing report as markdown."""
        lines = [
            "# A/B Testing Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Total tests:** {len(self.test_history)}",
            "",
        ]

        for result in self.test_history[-5:]:
            lines.extend(
                [
                    f"## Test: {result.test_id}",
                    "",
                    f"**Task:** {result.task[:100]}...",
                    f"**Winner:** {result.winner}",
                    f"**Confidence:** {result.statistical_confidence:.0%}",
                    "",
                    "### Scores",
                    "",
                ]
            )

            for agent, score in result.scores.items():
                lines.append(f"- {agent}: {score:.0%}")

            lines.extend(["", "---", ""])

        return "\n".join(lines)


# Convenience function
async def run_ab_test(
    task: str,
    agents: list[str],
    metrics: list[str] | None = None,
) -> ABTestResult:
    """Quick function to run A/B test."""
    tester = ABTester()
    return await tester.compare(task, agents, metrics)
