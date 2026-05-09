#!/usr/bin/env python3
"""
Self-Reflection Module - Agents that evaluate their own outputs.

This module enables agents to:
- Evaluate the quality of their outputs before returning
- Identify weaknesses and areas of uncertainty
- Retry with different approaches when confidence is low
- Learn from self-assessment over time

Usage:
    from .agent.core.intelligence import SelfReflection

    reflection = SelfReflection()
    result = await reflection.reflect(
        task="Design API for user management",
        output="Here is the API design...",
        agent_name="api-designer"
    )

    if result.should_retry:
        # Try a different approach
        ...
"""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.self_reflection")


class ReflectionDimension(Enum):
    """Dimensions for self-reflection evaluation."""

    COMPLETENESS = "completeness"  # Did I address all aspects?
    CORRECTNESS = "correctness"  # Is this technically correct?
    CLARITY = "clarity"  # Is this clear and understandable?
    ACTIONABILITY = "actionability"  # Can this be used directly?
    SAFETY = "safety"  # Are there security/safety concerns?
    CONSISTENCY = "consistency"  # Does this match prior decisions?


@dataclass
class DimensionScore:
    """Score for a single reflection dimension."""

    dimension: ReflectionDimension
    score: float  # 0.0 to 1.0
    reasoning: str
    concerns: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ReflectionResult:
    """Result of self-reflection analysis."""

    task: str
    agent_name: str
    overall_confidence: float  # 0.0 to 1.0
    dimension_scores: list[DimensionScore]
    should_retry: bool
    retry_suggestions: list[str]
    blind_spots: list[str]  # What might I be missing?
    assumptions: list[str]  # What am I assuming?
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dimension_scores"] = [
            {**asdict(ds), "dimension": ds.dimension.value} for ds in self.dimension_scores
        ]
        return d

    @property
    def weakest_dimension(self) -> DimensionScore | None:
        if not self.dimension_scores:
            return None
        return min(self.dimension_scores, key=lambda x: x.score)

    @property
    def summary(self) -> str:
        status = (
            "HIGH"
            if self.overall_confidence >= 0.8
            else "MEDIUM"
            if self.overall_confidence >= 0.6
            else "LOW"
        )
        weakest = self.weakest_dimension
        weak_area = weakest.dimension.value if weakest else "none"
        return f"Confidence: {status} ({self.overall_confidence:.2f}), Weakest: {weak_area}"


class SelfReflection:
    """
    Self-Reflection engine for autonomous agents.

    Enables agents to critically evaluate their own outputs,
    identify uncertainties, and improve through iteration.
    """

    # Reflection prompts for each dimension
    DIMENSION_PROMPTS = {
        ReflectionDimension.COMPLETENESS: [
            "Did I address ALL aspects of the task?",
            "Are there edge cases I didn't consider?",
            "Did I answer what was actually asked?",
        ],
        ReflectionDimension.CORRECTNESS: [
            "Is this technically accurate?",
            "Are my assumptions valid?",
            "Would an expert agree with this?",
        ],
        ReflectionDimension.CLARITY: [
            "Would someone unfamiliar understand this?",
            "Is the structure logical?",
            "Are there ambiguous statements?",
        ],
        ReflectionDimension.ACTIONABILITY: [
            "Can this be implemented directly?",
            "Are next steps clear?",
            "Is anything missing to take action?",
        ],
        ReflectionDimension.SAFETY: [
            "Are there security implications?",
            "Could this cause harm if wrong?",
            "Should I escalate for human review?",
        ],
        ReflectionDimension.CONSISTENCY: [
            "Does this align with prior decisions?",
            "Am I contradicting earlier context?",
            "Is this consistent with project patterns?",
        ],
    }

    # Confidence thresholds
    RETRY_THRESHOLD = 0.6
    ESCALATE_THRESHOLD = 0.4

    def __init__(
        self,
        memory_dir: Path | None = None,
        llm_evaluator: Callable | None = None,
    ):
        self.memory_dir = memory_dir or Path(".agent/memory/reflections")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.llm_evaluator = llm_evaluator
        self.reflection_history: list[ReflectionResult] = []
        logger.info("SelfReflection engine initialized")

    async def reflect(
        self,
        task: str,
        output: str,
        agent_name: str,
        context: dict[str, Any] | None = None,
        dimensions: list[ReflectionDimension] | None = None,
    ) -> ReflectionResult:
        """
        Perform self-reflection on an agent's output.

        Args:
            task: The original task/question
            output: The agent's output to reflect on
            agent_name: Name of the agent that produced the output
            context: Optional additional context
            dimensions: Specific dimensions to evaluate (default: all)

        Returns:
            ReflectionResult with confidence scores and recommendations
        """
        dimensions = dimensions or list(ReflectionDimension)
        context = context or {}

        logger.info(f"Reflecting on output from {agent_name} for task: {task[:50]}...")

        # Evaluate each dimension
        dimension_scores = []
        for dimension in dimensions:
            score = await self._evaluate_dimension(
                dimension=dimension,
                task=task,
                output=output,
                context=context,
            )
            dimension_scores.append(score)

        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(dimension_scores)

        # Determine if retry is needed
        should_retry = overall_confidence < self.RETRY_THRESHOLD

        # Generate retry suggestions if needed
        retry_suggestions = []
        if should_retry:
            retry_suggestions = self._generate_retry_suggestions(dimension_scores)

        # Identify blind spots and assumptions
        blind_spots = self._identify_blind_spots(task, output, dimension_scores)
        assumptions = self._identify_assumptions(task, output)

        result = ReflectionResult(
            task=task,
            agent_name=agent_name,
            overall_confidence=overall_confidence,
            dimension_scores=dimension_scores,
            should_retry=should_retry,
            retry_suggestions=retry_suggestions,
            blind_spots=blind_spots,
            assumptions=assumptions,
        )

        # Save to history
        self.reflection_history.append(result)
        await self._save_reflection(result)

        logger.info(f"Reflection complete: {result.summary}")
        return result

    async def _evaluate_dimension(
        self,
        dimension: ReflectionDimension,
        task: str,
        output: str,
        context: dict[str, Any],
    ) -> DimensionScore:
        """Evaluate a single reflection dimension."""
        prompts = self.DIMENSION_PROMPTS[dimension]

        # If we have an LLM evaluator, use it
        if self.llm_evaluator:
            return await self._llm_evaluate_dimension(dimension, task, output, prompts, context)

        # Otherwise, use heuristic evaluation
        return self._heuristic_evaluate_dimension(dimension, task, output, prompts)

    async def _llm_evaluate_dimension(
        self,
        dimension: ReflectionDimension,
        task: str,
        output: str,
        prompts: list[str],
        context: dict[str, Any],
    ) -> DimensionScore:
        """Use LLM to evaluate a dimension."""
        evaluation_prompt = f"""
You are a critical evaluator. Assess this output on {dimension.value}.

TASK: {task}

OUTPUT TO EVALUATE:
{output}

EVALUATION QUESTIONS:
{chr(10).join(f"- {p}" for p in prompts)}

Respond in JSON format:
{{
    "score": 0.0-1.0,
    "reasoning": "Brief explanation",
    "concerns": ["list of concerns"],
    "suggestions": ["list of improvements"]
}}
"""
        try:
            response = await self.llm_evaluator(evaluation_prompt)  # type: ignore[misc]  # callable: Optional, checked at init
            data = json.loads(response)
            return DimensionScore(
                dimension=dimension,
                score=float(data.get("score", 0.5)),
                reasoning=data.get("reasoning", ""),
                concerns=data.get("concerns", []),
                suggestions=data.get("suggestions", []),
            )
        except Exception as e:
            logger.warning(f"LLM evaluation failed: {e}, using heuristic")
            return self._heuristic_evaluate_dimension(dimension, task, output, prompts)

    def _heuristic_evaluate_dimension(
        self,
        dimension: ReflectionDimension,
        task: str,
        output: str,
        prompts: list[str],
    ) -> DimensionScore:
        """Heuristic-based dimension evaluation."""
        score = 0.7  # Default moderate confidence
        concerns = []
        suggestions = []
        reasoning = ""

        output_lower = output.lower()
        task_lower = task.lower()

        if dimension == ReflectionDimension.COMPLETENESS:
            # Check if output length is reasonable
            if len(output) < 100:
                score -= 0.2
                concerns.append("Output seems too short for task complexity")

            # Check for keywords from task
            task_keywords = set(task_lower.split()) - {"the", "a", "an", "is", "are", "to", "for"}
            addressed = sum(1 for kw in task_keywords if kw in output_lower)
            coverage = addressed / max(len(task_keywords), 1)
            score = min(score, 0.5 + coverage * 0.5)

            if coverage < 0.5:
                concerns.append("May not address all aspects of the task")
                suggestions.append("Review task requirements and ensure all are covered")

            reasoning = f"Keyword coverage: {coverage:.0%}"

        elif dimension == ReflectionDimension.CORRECTNESS:
            # Check for uncertainty markers
            uncertainty_markers = ["maybe", "perhaps", "i think", "might", "possibly", "not sure"]
            uncertainty_count = sum(1 for m in uncertainty_markers if m in output_lower)
            if uncertainty_count > 2:
                score -= 0.2
                concerns.append("High uncertainty expressed in output")

            # Check for TODO/FIXME
            if "todo" in output_lower or "fixme" in output_lower:
                score -= 0.1
                concerns.append("Contains incomplete sections")

            reasoning = f"Uncertainty markers: {uncertainty_count}"

        elif dimension == ReflectionDimension.CLARITY:
            # Check for structure
            has_structure = any(marker in output for marker in ["##", "- ", "1.", "```"])
            if has_structure:
                score += 0.1
            else:
                suggestions.append("Consider adding structure (headers, lists)")

            # Check sentence length (very long sentences reduce clarity)
            sentences = output.split(".")
            avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
            if avg_sentence_len > 30:
                score -= 0.1
                concerns.append("Some sentences may be too long")

            reasoning = (
                f"Has structure: {has_structure}, Avg sentence length: {avg_sentence_len:.0f}"
            )

        elif dimension == ReflectionDimension.ACTIONABILITY:
            # Check for action words
            action_words = ["implement", "create", "add", "run", "execute", "install", "configure"]
            has_actions = any(word in output_lower for word in action_words)

            # Check for code examples
            has_code = "```" in output

            if has_actions:
                score += 0.1
            if has_code:
                score += 0.1

            if not has_actions and not has_code:
                suggestions.append("Add concrete action steps or code examples")

            reasoning = f"Has actions: {has_actions}, Has code: {has_code}"

        elif dimension == ReflectionDimension.SAFETY:
            # Check for dangerous patterns
            danger_patterns = [
                "rm -rf",
                "drop table",
                "delete from",
                "eval(",
                "exec(",
                "shell=true",
                "--no-verify",
                "password=",
                "api_key=",
                "secret=",
            ]
            dangers_found = [p for p in danger_patterns if p in output_lower]
            if dangers_found:
                score -= 0.3
                concerns.extend([f"Potentially dangerous pattern: {d}" for d in dangers_found])
                suggestions.append("Review security implications")

            reasoning = f"Danger patterns found: {len(dangers_found)}"

        elif dimension == ReflectionDimension.CONSISTENCY:
            # This would ideally check against memory/prior decisions
            # For now, we give moderate confidence
            reasoning = "Consistency check requires memory context"
            suggestions.append("Verify alignment with prior decisions")

        return DimensionScore(
            dimension=dimension,
            score=max(0.0, min(1.0, score)),
            reasoning=reasoning,
            concerns=concerns,
            suggestions=suggestions,
        )

    def _calculate_overall_confidence(self, scores: list[DimensionScore]) -> float:
        """Calculate overall confidence from dimension scores."""
        if not scores:
            return 0.5

        # Weighted average with safety having higher weight
        weights = {
            ReflectionDimension.SAFETY: 1.5,
            ReflectionDimension.CORRECTNESS: 1.3,
            ReflectionDimension.COMPLETENESS: 1.0,
            ReflectionDimension.CLARITY: 0.8,
            ReflectionDimension.ACTIONABILITY: 0.9,
            ReflectionDimension.CONSISTENCY: 1.0,
        }

        total_weight = sum(weights.get(s.dimension, 1.0) for s in scores)
        weighted_sum = sum(s.score * weights.get(s.dimension, 1.0) for s in scores)

        return weighted_sum / total_weight

    def _generate_retry_suggestions(self, scores: list[DimensionScore]) -> list[str]:
        """Generate suggestions for retry based on low-scoring dimensions."""
        suggestions = []

        # Sort by score to prioritize lowest
        sorted_scores = sorted(scores, key=lambda x: x.score)

        for score in sorted_scores[:3]:  # Focus on 3 worst dimensions
            if score.score < self.RETRY_THRESHOLD:
                suggestions.append(f"Improve {score.dimension.value}: {score.reasoning}")
                suggestions.extend(score.suggestions)

        return suggestions

    def _identify_blind_spots(
        self,
        task: str,
        output: str,
        scores: list[DimensionScore],
    ) -> list[str]:
        """Identify potential blind spots in the output."""
        blind_spots = []

        # Common blind spots
        checks = [
            (
                "error handling" not in output.lower() and "exception" not in output.lower(),
                "Error handling may not be addressed",
            ),
            ("edge case" not in output.lower(), "Edge cases may not be considered"),
            (
                "performance" not in output.lower() and "scale" not in output.lower(),
                "Performance implications may not be addressed",
            ),
            (
                "security" not in output.lower() and "auth" not in output.lower(),
                "Security considerations may be missing",
            ),
            ("test" not in output.lower(), "Testing strategy may not be addressed"),
        ]

        for condition, message in checks:
            if condition:
                blind_spots.append(message)

        # Add concerns from dimension evaluations
        for score in scores:
            if score.score < 0.6:
                blind_spots.extend(score.concerns)

        return blind_spots[:5]  # Limit to top 5

    def _identify_assumptions(self, task: str, output: str) -> list[str]:
        """Identify assumptions made in the output."""
        assumptions = []

        # Look for assumption indicators
        assumption_markers = [
            ("assuming", "Explicit assumption made"),
            ("if we", "Conditional assumption"),
            ("should be", "Expected state assumption"),
            ("will have", "Future state assumption"),
            ("already", "Pre-existing state assumption"),
        ]

        output_lower = output.lower()
        for marker, description in assumption_markers:
            if marker in output_lower:
                # Extract context around the marker
                idx = output_lower.find(marker)
                context = output[max(0, idx - 20) : min(len(output), idx + 50)]
                assumptions.append(f"{description}: ...{context}...")

        return assumptions[:5]  # Limit to top 5

    async def _save_reflection(self, result: ReflectionResult) -> None:
        """Save reflection result to disk."""
        try:
            filename = (
                f"reflection_{result.agent_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            filepath = self.memory_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save reflection: {e}")

    def get_reflection_stats(self) -> dict[str, Any]:
        """Get statistics from reflection history."""
        if not self.reflection_history:
            return {"total_reflections": 0}

        confidences = [r.overall_confidence for r in self.reflection_history]
        retry_rate = sum(1 for r in self.reflection_history if r.should_retry) / len(
            self.reflection_history
        )

        return {
            "total_reflections": len(self.reflection_history),
            "average_confidence": sum(confidences) / len(confidences),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "retry_rate": retry_rate,
        }


# Convenience function for quick reflection
async def quick_reflect(
    task: str,
    output: str,
    agent_name: str = "unknown",
) -> ReflectionResult:
    """Quick reflection without persistent state."""
    reflector = SelfReflection()
    return await reflector.reflect(task, output, agent_name)
