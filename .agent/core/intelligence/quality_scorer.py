#!/usr/bin/env python3
"""
Quality Scorer Module - Meta-agent that evaluates agent outputs.

This module provides automated quality assessment:
- Evaluate outputs across multiple dimensions
- Score completeness, correctness, clarity, actionability
- Provide improvement suggestions
- Track quality over time for learning

Usage:
    from .agent.core.intelligence import QualityScorer

    scorer = QualityScorer()
    score = await scorer.score(
        agent_name="architect",
        task="Design authentication system",
        output="Here is the architecture..."
    )

    print(f"Quality: {score.overall_score:.0%}")
    print(f"Suggestions: {score.improvement_suggestions}")
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.quality_scorer")


class QualityDimension(Enum):
    """Dimensions for quality assessment."""

    COMPLETENESS = "completeness"  # Addresses all aspects of task
    CORRECTNESS = "correctness"  # Technically accurate
    CLARITY = "clarity"  # Clear and understandable
    ACTIONABILITY = "actionability"  # Can be used directly
    STRUCTURE = "structure"  # Well-organized
    DEPTH = "depth"  # Appropriate level of detail
    SAFETY = "safety"  # No dangerous suggestions
    CONSISTENCY = "consistency"  # Consistent with context/standards


class QualityGrade(Enum):
    """Quality grades."""

    EXCELLENT = "A"  # 90-100%
    GOOD = "B"  # 80-89%
    SATISFACTORY = "C"  # 70-79%
    NEEDS_WORK = "D"  # 60-69%
    POOR = "F"  # Below 60%


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    dimension: QualityDimension
    score: float  # 0.0 to 1.0
    weight: float  # Importance weight
    reasoning: str
    evidence: list[str]
    deductions: list[str]
    suggestions: list[str]


@dataclass
class QualityScore:
    """Complete quality assessment result."""

    agent_name: str
    task: str
    output_length: int
    dimension_scores: list[DimensionScore]
    overall_score: float
    grade: QualityGrade
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]
    critical_issues: list[str]
    pass_threshold: bool
    execution_time_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dimension_scores"] = [
            {**asdict(ds), "dimension": ds.dimension.value} for ds in self.dimension_scores
        ]
        d["grade"] = self.grade.value
        return d

    def to_report(self) -> str:
        """Generate human-readable quality report."""
        lines = [
            "# Quality Assessment Report",
            "",
            f"**Agent:** {self.agent_name}",
            f"**Task:** {self.task}",
            f"**Grade:** {self.grade.value} ({self.overall_score:.0%})",
            f"**Pass:** {'YES' if self.pass_threshold else 'NO'}",
            "",
            "## Dimension Scores",
            "",
        ]

        # Sort dimensions by score
        sorted_dims = sorted(self.dimension_scores, key=lambda x: x.score, reverse=True)

        for ds in sorted_dims:
            bar = "=" * int(ds.score * 10) + "-" * (10 - int(ds.score * 10))
            lines.append(f"- **{ds.dimension.value}**: [{bar}] {ds.score:.0%}")

        if self.strengths:
            lines.extend(["", "## Strengths"])
            for s in self.strengths:
                lines.append(f"- {s}")

        if self.weaknesses:
            lines.extend(["", "## Weaknesses"])
            for w in self.weaknesses:
                lines.append(f"- {w}")

        if self.critical_issues:
            lines.extend(["", "## CRITICAL ISSUES"])
            for issue in self.critical_issues:
                lines.append(f"- {issue}")

        if self.improvement_suggestions:
            lines.extend(["", "## Improvement Suggestions"])
            for i, suggestion in enumerate(self.improvement_suggestions, 1):
                lines.append(f"{i}. {suggestion}")

        return "\n".join(lines)


class QualityScorer:
    """
    Quality Scorer - Meta-agent that evaluates other agents' outputs.

    Provides automated, multi-dimensional quality assessment
    with actionable feedback for improvement.
    """

    # Dimension weights (sum to 1.0)
    DIMENSION_WEIGHTS = {
        QualityDimension.COMPLETENESS: 0.20,
        QualityDimension.CORRECTNESS: 0.25,
        QualityDimension.CLARITY: 0.15,
        QualityDimension.ACTIONABILITY: 0.15,
        QualityDimension.STRUCTURE: 0.10,
        QualityDimension.DEPTH: 0.05,
        QualityDimension.SAFETY: 0.05,
        QualityDimension.CONSISTENCY: 0.05,
    }

    # Pass threshold
    PASS_THRESHOLD = 0.70

    # Grade thresholds
    GRADE_THRESHOLDS = [
        (0.90, QualityGrade.EXCELLENT),
        (0.80, QualityGrade.GOOD),
        (0.70, QualityGrade.SATISFACTORY),
        (0.60, QualityGrade.NEEDS_WORK),
        (0.00, QualityGrade.POOR),
    ]

    def __init__(
        self,
        llm_evaluator: Callable | None = None,
        memory_dir: Path | None = None,
        custom_weights: dict[QualityDimension, float] | None = None,
    ):
        self.llm_evaluator = llm_evaluator
        self.memory_dir = memory_dir or Path(".agent/memory/quality")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.weights = custom_weights or self.DIMENSION_WEIGHTS.copy()
        self.score_history: list[QualityScore] = []
        logger.info("QualityScorer initialized")

    async def score(
        self,
        agent_name: str,
        task: str,
        output: str,
        context: dict[str, Any] | None = None,
        expected_elements: list[str] | None = None,
    ) -> QualityScore:
        """
        Score an agent's output.

        Args:
            agent_name: Name of the agent that produced output
            task: The original task/request
            output: The agent's output to evaluate
            context: Optional context for evaluation
            expected_elements: Optional list of elements that should be present

        Returns:
            QualityScore with detailed assessment
        """
        import time

        start_time = time.time()

        context = context or {}
        expected_elements = expected_elements or []

        logger.info(f"Scoring output from {agent_name} for task: {task[:50]}...")

        # Score each dimension
        dimension_scores = []
        for dimension, weight in self.weights.items():
            ds = await self._score_dimension(
                dimension=dimension,
                weight=weight,
                task=task,
                output=output,
                context=context,
                expected_elements=expected_elements,
            )
            dimension_scores.append(ds)

        # Calculate overall score
        overall = self._calculate_overall_score(dimension_scores)

        # Determine grade
        grade = self._determine_grade(overall)

        # Extract strengths and weaknesses
        strengths = self._extract_strengths(dimension_scores)
        weaknesses = self._extract_weaknesses(dimension_scores)

        # Compile suggestions
        suggestions = self._compile_suggestions(dimension_scores)

        # Identify critical issues
        critical = self._identify_critical_issues(dimension_scores, output)

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = QualityScore(
            agent_name=agent_name,
            task=task,
            output_length=len(output),
            dimension_scores=dimension_scores,
            overall_score=overall,
            grade=grade,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=suggestions,
            critical_issues=critical,
            pass_threshold=overall >= self.PASS_THRESHOLD,
            execution_time_ms=elapsed_ms,
        )

        self.score_history.append(result)
        await self._save_score(result)

        logger.info(f"Quality score: {overall:.0%} ({grade.value})")
        return result

    async def _score_dimension(
        self,
        dimension: QualityDimension,
        weight: float,
        task: str,
        output: str,
        context: dict[str, Any],
        expected_elements: list[str],
    ) -> DimensionScore:
        """Score a single quality dimension."""
        if self.llm_evaluator:
            return await self._llm_score_dimension(
                dimension, weight, task, output, context, expected_elements
            )

        return self._heuristic_score_dimension(
            dimension, weight, task, output, context, expected_elements
        )

    def _score_completeness(
        self,
        task_lower: str,
        output_lower: str,
        output: str,
        expected_elements: list[str],
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión COMPLETENESS.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        evidence: list[str] = []
        deductions: list[str] = []
        suggestions: list[str] = []

        task_keywords = set(task_lower.split()) - {"the", "a", "an", "is", "to", "for", "and", "or"}
        addressed = sum(1 for kw in task_keywords if kw in output_lower)
        coverage = addressed / max(len(task_keywords), 1)
        score = 0.5 + coverage * 0.5

        if expected_elements:
            found = sum(1 for elem in expected_elements if elem.lower() in output_lower)
            element_coverage = found / len(expected_elements)
            score = (score + element_coverage) / 2
            evidence.append(f"Expected elements found: {found}/{len(expected_elements)}")

        if len(output) < 100:
            score -= 0.2
            deductions.append("Output too short")
            suggestions.append("Provide more detail")

        reasoning = f"Keyword coverage: {coverage:.0%}"
        evidence.append(f"Addressed {addressed} of {len(task_keywords)} task keywords")
        return score, evidence, deductions, suggestions, reasoning

    def _score_correctness(
        self,
        output_lower: str,
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión CORRECTNESS.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        score = 0.7
        deductions: list[str] = []
        suggestions: list[str] = []

        uncertainty_phrases = [
            "i think",
            "maybe",
            "perhaps",
            "might",
            "possibly",
            "not sure",
            "could be",
            "i believe",
        ]
        uncertainty_count = sum(1 for p in uncertainty_phrases if p in output_lower)

        if uncertainty_count > 2:
            score -= 0.15
            deductions.append(f"High uncertainty ({uncertainty_count} markers)")

        if " but " in output_lower and " however " in output_lower:
            if output_lower.count(" but ") + output_lower.count(" however ") > 3:
                score -= 0.1
                deductions.append("Multiple contradicting statements")

        if "todo" in output_lower or "fixme" in output_lower or "tbd" in output_lower:
            score -= 0.15
            deductions.append("Contains TODO/FIXME markers")
            suggestions.append("Complete all sections before finalizing")

        return score, [], deductions, suggestions, f"Uncertainty markers: {uncertainty_count}"

    def _score_clarity(
        self,
        output: str,
        output_lower: str,
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión CLARITY.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        evidence: list[str] = []
        deductions: list[str] = []
        suggestions: list[str] = []

        has_headers = "##" in output or "**" in output
        has_lists = (
            "- " in output or "* " in output or bool(re.search(r"^\d+\.", output, re.MULTILINE))
        )
        has_code = "```" in output

        score = 0.5
        if has_headers:
            score += 0.2
            evidence.append("Has clear headers")
        if has_lists:
            score += 0.15
            evidence.append("Uses lists for organization")
        if has_code:
            score += 0.15
            evidence.append("Includes code examples")

        sentences = [s.strip() for s in output.split(".") if s.strip()]
        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_words > 35:
                score -= 0.1
                deductions.append("Very long sentences reduce readability")
                suggestions.append("Break up long sentences")

        if not has_headers and len(output) > 500:
            suggestions.append("Add headers to organize content")

        reasoning = f"Structure elements: headers={has_headers}, lists={has_lists}, code={has_code}"
        return score, evidence, deductions, suggestions, reasoning

    def _score_actionability(
        self,
        output: str,
        output_lower: str,
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión ACTIONABILITY.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        evidence: list[str] = []
        suggestions: list[str] = []

        action_verbs = [
            "implement",
            "create",
            "add",
            "run",
            "execute",
            "install",
            "configure",
            "update",
            "modify",
            "delete",
            "deploy",
            "test",
            "build",
            "use",
            "call",
            "invoke",
            "set",
        ]
        action_count = sum(1 for v in action_verbs if v in output_lower)
        has_code = "```" in output
        has_steps = (
            bool(re.search(r"^\s*\d+\.", output, re.MULTILINE))
            or "step" in output_lower
            or "first" in output_lower
        )

        score = 0.4
        if action_count > 0:
            score += min(action_count * 0.1, 0.3)
            evidence.append(f"Contains {action_count} action verbs")
        if has_code:
            score += 0.2
            evidence.append("Includes code examples")
        if has_steps:
            score += 0.1
            evidence.append("Has step-by-step structure")

        if not has_code and not has_steps:
            suggestions.append("Add code examples or step-by-step instructions")

        return (
            score,
            evidence,
            [],
            suggestions,
            f"Actions: {action_count}, Code: {has_code}, Steps: {has_steps}",
        )

    def _score_structure(
        self,
        output: str,
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión STRUCTURE.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        evidence: list[str] = []
        deductions: list[str] = []
        suggestions: list[str] = []

        lines = output.split("\n")
        section_markers = sum(
            1 for line in lines if line.strip().startswith("#") or line.strip().startswith("**")
        )
        paragraphs = [p for p in output.split("\n\n") if p.strip()]
        avg_para_length = sum(len(p) for p in paragraphs) / max(len(paragraphs), 1)

        score = 0.6
        if section_markers >= 2:
            score += 0.2
            evidence.append(f"Has {section_markers} section markers")
        if 100 < avg_para_length < 500:
            score += 0.1
            evidence.append("Good paragraph length")
        elif avg_para_length > 800:
            score -= 0.1
            deductions.append("Paragraphs too long")
            suggestions.append("Break up long paragraphs")

        return (
            score,
            evidence,
            deductions,
            suggestions,
            f"Sections: {section_markers}, Avg paragraph: {avg_para_length:.0f} chars",
        )

    def _score_depth(
        self,
        task_lower: str,
        output: str,
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión DEPTH.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        evidence: list[str] = []
        deductions: list[str] = []
        suggestions: list[str] = []
        score = 0.7

        word_count = len(output.split())
        needs_depth = any(
            kw in task_lower
            for kw in ["explain", "analyze", "design", "architect", "plan", "detail"]
        )

        if needs_depth:
            if word_count >= 300:
                score = 0.9
                evidence.append("Provides detailed explanation")
            elif word_count >= 150:
                score = 0.7
            else:
                score = 0.5
                suggestions.append("Task requires more detailed response")
        else:
            if 50 <= word_count <= 500:
                score = 0.85
                evidence.append("Appropriate length for task")
            elif word_count > 500:
                score = 0.7
                deductions.append("May be overly verbose")

        return (
            score,
            evidence,
            deductions,
            suggestions,
            f"Word count: {word_count}, Needs depth: {needs_depth}",
        )

    def _score_safety(
        self,
        output_lower: str,
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión SAFETY.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        danger_patterns = {
            "rm -rf /": "Dangerous file deletion command",
            "drop table": "Dangerous database operation",
            "delete from": "Potentially dangerous delete",
            "eval(": "Dangerous code evaluation",
            "exec(": "Dangerous code execution",
            "shell=true": "Potential command injection",
            "--no-verify": "Bypassing safety checks",
            "chmod 777": "Insecure permissions",
            "password=": "Hardcoded credential",
            "api_key=": "Exposed API key",
            "secret=": "Exposed secret",
        }

        found_dangers = [
            desc for pattern, desc in danger_patterns.items() if pattern in output_lower
        ]

        if found_dangers:
            score = max(0.3, 1.0 - len(found_dangers) * 0.2)
            suggestions = ["Review and address security concerns"]
            return (
                score,
                [],
                found_dangers,
                suggestions,
                f"Dangerous patterns found: {len(found_dangers)}",
            )

        return 0.95, ["No dangerous patterns detected"], [], [], "Dangerous patterns found: 0"

    def _score_consistency(
        self,
        context: dict[str, Any],
    ) -> tuple[float, list[str], list[str], list[str], str]:
        """Score la dimensión CONSISTENCY.

        Returns:
            Tupla (score, evidence, deductions, suggestions, reasoning).
        """
        score = 0.8
        if context.get("prior_decisions"):
            pass  # Would compare against prior decisions
        return score, ["Consistency check (basic)"], [], [], "Basic consistency evaluation"

    def _heuristic_score_dimension(
        self,
        dimension: QualityDimension,
        weight: float,
        task: str,
        output: str,
        context: dict[str, Any],
        expected_elements: list[str],
    ) -> DimensionScore:
        """Heuristic-based dimension scoring."""
        output_lower = output.lower()
        task_lower = task.lower()

        _scorers: dict[QualityDimension, Any] = {
            QualityDimension.COMPLETENESS: lambda: self._score_completeness(
                task_lower,
                output_lower,
                output,
                expected_elements,
            ),
            QualityDimension.CORRECTNESS: lambda: self._score_correctness(output_lower),
            QualityDimension.CLARITY: lambda: self._score_clarity(output, output_lower),
            QualityDimension.ACTIONABILITY: lambda: self._score_actionability(output, output_lower),
            QualityDimension.STRUCTURE: lambda: self._score_structure(output),
            QualityDimension.DEPTH: lambda: self._score_depth(task_lower, output),
            QualityDimension.SAFETY: lambda: self._score_safety(output_lower),
            QualityDimension.CONSISTENCY: lambda: self._score_consistency(context),
        }

        scorer = _scorers.get(dimension)
        if scorer:
            score, evidence, deductions, suggestions, reasoning = scorer()
        else:
            score, evidence, deductions, suggestions, reasoning = 0.7, [], [], [], ""

        return DimensionScore(
            dimension=dimension,
            score=max(0.0, min(1.0, score)),
            weight=weight,
            reasoning=reasoning,
            evidence=evidence,
            deductions=deductions,
            suggestions=suggestions,
        )

    async def _llm_score_dimension(
        self,
        dimension: QualityDimension,
        weight: float,
        task: str,
        output: str,
        context: dict[str, Any],
        expected_elements: list[str],
    ) -> DimensionScore:
        """Use LLM to score dimension."""
        prompt = f"""
Evaluate this output on {dimension.value}.

TASK: {task}

OUTPUT:
{output[:2000]}

Expected elements: {expected_elements if expected_elements else "None specified"}

Score the {dimension.value} from 0.0 to 1.0.
Respond in JSON:
{{
    "score": 0.0-1.0,
    "reasoning": "Brief explanation",
    "evidence": ["positive points"],
    "deductions": ["negative points"],
    "suggestions": ["improvements"]
}}
"""
        try:
            response = await self.llm_evaluator(prompt)  # type: ignore[misc]  # callable: Optional, checked at init
            data = json.loads(response)
            return DimensionScore(
                dimension=dimension,
                score=float(data.get("score", 0.7)),
                weight=weight,
                reasoning=data.get("reasoning", ""),
                evidence=data.get("evidence", []),
                deductions=data.get("deductions", []),
                suggestions=data.get("suggestions", []),
            )
        except Exception as e:
            logger.warning(f"LLM scoring failed: {e}, using heuristic")
            return self._heuristic_score_dimension(
                dimension, weight, task, output, context, expected_elements
            )

    def _calculate_overall_score(self, scores: list[DimensionScore]) -> float:
        """Calculate weighted overall score."""
        total_weight = sum(s.weight for s in scores)
        weighted_sum = sum(s.score * s.weight for s in scores)
        return weighted_sum / total_weight if total_weight > 0 else 0.5

    def _determine_grade(self, score: float) -> QualityGrade:
        """Determine letter grade from score."""
        for threshold, grade in self.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return QualityGrade.POOR

    def _extract_strengths(self, scores: list[DimensionScore]) -> list[str]:
        """Extract strengths from high-scoring dimensions."""
        strengths = []
        for s in sorted(scores, key=lambda x: x.score, reverse=True):
            if s.score >= 0.8:
                strengths.append(f"{s.dimension.value}: {s.reasoning}")
                strengths.extend(s.evidence[:1])
        return strengths[:5]

    def _extract_weaknesses(self, scores: list[DimensionScore]) -> list[str]:
        """Extract weaknesses from low-scoring dimensions."""
        weaknesses = []
        for s in sorted(scores, key=lambda x: x.score):
            if s.score < 0.7:
                weaknesses.append(f"{s.dimension.value}: {s.reasoning}")
                weaknesses.extend(s.deductions[:1])
        return weaknesses[:5]

    def _compile_suggestions(self, scores: list[DimensionScore]) -> list[str]:
        """Compile improvement suggestions."""
        suggestions = []
        # Prioritize suggestions from lowest-scoring dimensions
        for s in sorted(scores, key=lambda x: x.score):
            suggestions.extend(s.suggestions)
        return list(dict.fromkeys(suggestions))[:7]  # Deduplicate and limit

    def _identify_critical_issues(
        self,
        scores: list[DimensionScore],
        output: str,
    ) -> list[str]:
        """Identify critical issues that must be addressed."""
        critical = []

        # Check safety dimension
        safety_scores = [s for s in scores if s.dimension == QualityDimension.SAFETY]
        if safety_scores and safety_scores[0].score < 0.5:
            critical.extend(safety_scores[0].deductions)

        # Check for very low scores
        for s in scores:
            if s.score < 0.4:
                critical.append(f"Critical weakness in {s.dimension.value}")

        return critical[:5]

    async def _save_score(self, score: QualityScore) -> None:
        """Save score to disk."""
        try:
            filename = f"quality_{score.agent_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.memory_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(score.to_dict(), f, indent=2, ensure_ascii=False)

            # Save report
            report_path = self.memory_dir / filename.replace(".json", "_report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(score.to_report())
        except Exception as e:
            logger.warning(f"Failed to save quality score: {e}")

    def get_agent_statistics(self, agent_name: str) -> dict[str, Any]:
        """Get quality statistics for an agent."""
        agent_scores = [s for s in self.score_history if s.agent_name == agent_name]

        if not agent_scores:
            return {"agent": agent_name, "total_evaluations": 0}

        overall_scores = [s.overall_score for s in agent_scores]
        pass_rate = sum(1 for s in agent_scores if s.pass_threshold) / len(agent_scores)

        return {
            "agent": agent_name,
            "total_evaluations": len(agent_scores),
            "average_score": sum(overall_scores) / len(overall_scores),
            "best_score": max(overall_scores),
            "worst_score": min(overall_scores),
            "pass_rate": pass_rate,
            "most_common_grade": max(
                {s.grade for s in agent_scores},
                key=lambda g: sum(1 for s in agent_scores if s.grade == g),
            ).value,
        }


# Convenience function
async def quick_score(
    agent_name: str,
    task: str,
    output: str,
) -> QualityScore:
    """Quick quality scoring."""
    scorer = QualityScorer()
    return await scorer.score(agent_name, task, output)
