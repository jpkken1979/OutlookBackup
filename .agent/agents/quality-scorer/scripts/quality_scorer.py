#!/usr/bin/env python3
"""
Quality Scorer Agent - Evaluates other agents' outputs.

This meta-agent ensures quality standards are met across the ecosystem.

Usage:
    python quality_scorer.py --agent architect --task "Design auth" --output-file output.txt
    python quality_scorer.py --evaluate "output text here"
    python quality_scorer.py --stats architect
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from core.intelligence.quality_scorer import QualityScore, QualityScorer
except ImportError:
    # Fallback to local implementation
    from dataclasses import dataclass
    from enum import Enum

    class QualityDimension(Enum):
        COMPLETENESS = "completeness"
        CORRECTNESS = "correctness"
        CLARITY = "clarity"
        ACTIONABILITY = "actionability"
        STRUCTURE = "structure"
        DEPTH = "depth"
        SAFETY = "safety"
        CONSISTENCY = "consistency"

    class QualityGrade(Enum):
        EXCELLENT = "A"
        GOOD = "B"
        SATISFACTORY = "C"
        NEEDS_WORK = "D"
        POOR = "F"

    @dataclass
    class DimensionScore:
        dimension: str
        score: float
        notes: str

    @dataclass
    class QualityScore:
        agent_name: str
        task: str
        overall_score: float
        grade: str
        passed: bool
        dimension_scores: list[DimensionScore]
        strengths: list[str]
        weaknesses: list[str]
        suggestions: list[str]
        critical_issues: list[str]

    class QualityScorer:
        PASS_THRESHOLD = 0.70

        def __init__(self):
            self.history = []

        async def score(self, agent_name: str, task: str, output: str) -> QualityScore:
            """Score an agent's output."""
            scores = []
            output_lower = output.lower()

            # Completeness
            task_words = set(task.lower().split()) - {"the", "a", "an", "to", "for"}
            coverage = sum(1 for w in task_words if w in output_lower) / max(len(task_words), 1)
            completeness = 0.5 + coverage * 0.5
            scores.append(
                DimensionScore("completeness", completeness, f"{coverage:.0%} keyword coverage")
            )

            # Correctness
            uncertainty = sum(1 for p in ["maybe", "perhaps", "might"] if p in output_lower)
            correctness = max(0.5, 0.85 - uncertainty * 0.1)
            scores.append(
                DimensionScore("correctness", correctness, f"{uncertainty} uncertainty markers")
            )

            # Clarity
            has_structure = "##" in output or "- " in output
            clarity = 0.8 if has_structure else 0.6
            scores.append(
                DimensionScore(
                    "clarity", clarity, "Has structure" if has_structure else "Needs structure"
                )
            )

            # Actionability
            has_code = "```" in output
            actionability = 0.85 if has_code else 0.6
            scores.append(
                DimensionScore(
                    "actionability", actionability, "Has code" if has_code else "Needs examples"
                )
            )

            # Structure
            structure = 0.8 if has_structure else 0.5
            scores.append(
                DimensionScore(
                    "structure",
                    structure,
                    "Well organized" if has_structure else "Needs organization",
                )
            )

            # Depth
            word_count = len(output.split())
            depth = min(0.9, 0.5 + word_count / 1000)
            scores.append(DimensionScore("depth", depth, f"{word_count} words"))

            # Safety
            danger_patterns = ["rm -rf", "drop table", "password=", "eval("]
            dangers = sum(1 for p in danger_patterns if p in output_lower)
            safety = max(0.3, 1.0 - dangers * 0.2)
            scores.append(
                DimensionScore(
                    "safety", safety, f"{dangers} dangerous patterns" if dangers else "Safe"
                )
            )

            # Consistency
            consistency = 0.8
            scores.append(DimensionScore("consistency", consistency, "Basic check"))

            # Calculate overall
            weights = {
                "completeness": 0.20,
                "correctness": 0.25,
                "clarity": 0.15,
                "actionability": 0.15,
                "structure": 0.10,
                "depth": 0.05,
                "safety": 0.05,
                "consistency": 0.05,
            }

            overall = sum(s.score * weights.get(s.dimension, 0.1) for s in scores)

            # Grade
            if overall >= 0.9:
                grade = "A"
            elif overall >= 0.8:
                grade = "B"
            elif overall >= 0.7:
                grade = "C"
            elif overall >= 0.6:
                grade = "D"
            else:
                grade = "F"

            # Strengths and weaknesses
            sorted_scores = sorted(scores, key=lambda x: x.score, reverse=True)
            strengths = [f"{s.dimension}: {s.notes}" for s in sorted_scores[:3] if s.score >= 0.7]
            weaknesses = [f"{s.dimension}: {s.notes}" for s in sorted_scores[-3:] if s.score < 0.7]

            # Suggestions
            suggestions = []
            if not has_code:
                suggestions.append("Add code examples to improve actionability")
            if not has_structure:
                suggestions.append("Add headers and lists for better organization")
            if dangers > 0:
                suggestions.append("Review and address security concerns")

            # Critical issues
            critical = []
            if safety < 0.5:
                critical.append("Security vulnerabilities detected")

            return QualityScore(
                agent_name=agent_name,
                task=task,
                overall_score=overall,
                grade=grade,
                passed=overall >= self.PASS_THRESHOLD,
                dimension_scores=scores,
                strengths=strengths,
                weaknesses=weaknesses,
                suggestions=suggestions,
                critical_issues=critical,
            )


def format_report(score: QualityScore) -> str:
    """Format quality score as markdown report."""
    # Handle both attribute names
    passed = getattr(score, "pass_threshold", getattr(score, "passed", False))
    grade_val = score.grade if isinstance(score.grade, str) else score.grade.value

    lines = [
        "## Quality Assessment Report",
        "",
        f"**Agent:** {score.agent_name}",
        f"**Task:** {score.task}",
        f"**Grade:** {grade_val} ({score.overall_score:.0%})",
        f"**Pass:** {'YES' if passed else 'NO'}",
        "",
        "### Dimension Scores",
        "",
        "| Dimension | Score | Notes |",
        "|-----------|-------|-------|",
    ]

    for ds in score.dimension_scores:
        dim = ds.dimension if isinstance(ds.dimension, str) else ds.dimension.value
        # Handle both 'notes' and 'reasoning' attributes
        notes = getattr(ds, "notes", getattr(ds, "reasoning", ""))
        lines.append(f"| {dim} | {ds.score:.0%} | {notes} |")

    if score.strengths:
        lines.extend(["", "### Strengths", ""])
        for s in score.strengths:
            lines.append(f"- {s}")

    if score.weaknesses:
        lines.extend(["", "### Weaknesses", ""])
        for w in score.weaknesses:
            lines.append(f"- {w}")

    if score.critical_issues:
        lines.extend(["", "### Critical Issues", ""])
        for issue in score.critical_issues:
            lines.append(f"- **{issue}**")

    # Handle both attribute names
    suggestions = getattr(score, "suggestions", getattr(score, "improvement_suggestions", []))
    if suggestions:
        lines.extend(["", "### Improvement Suggestions", ""])
        for i, sug in enumerate(suggestions, 1):
            lines.append(f"{i}. {sug}")

    # Handle both attribute names
    passed = getattr(score, "pass_threshold", getattr(score, "passed", False))

    lines.extend(
        [
            "",
            "### Verdict",
            f"**{'PASS' if passed else 'FAIL'}**: ",
        ]
    )

    if passed:
        lines[-1] += "Output meets quality standards."
    else:
        lines[-1] += "Output requires improvement before approval."

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Quality Scorer - Evaluate agent outputs")
    parser.add_argument("--agent", type=str, default="unknown", help="Agent name")
    parser.add_argument("--task", type=str, default="Evaluate output", help="Task description")
    parser.add_argument("--output-file", type=str, help="File containing output to evaluate")
    parser.add_argument("--evaluate", type=str, help="Direct output text to evaluate")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    # Get output to evaluate
    output = ""
    if args.output_file:
        with open(args.output_file) as f:
            output = f.read()
    elif args.evaluate:
        output = args.evaluate
    else:
        # Read from stdin
        output = sys.stdin.read()

    if not output.strip():
        print("Error: No output to evaluate. Provide --output-file, --evaluate, or pipe to stdin.")
        sys.exit(1)

    # Score
    scorer = QualityScorer()
    score = await scorer.score(args.agent, args.task, output)

    # Output
    if args.json:
        grade_val = score.grade if isinstance(score.grade, str) else score.grade.value
        result = {
            "agent_name": score.agent_name,
            "task": score.task,
            "overall_score": score.overall_score,
            "grade": grade_val,
            "passed": getattr(score, "pass_threshold", getattr(score, "passed", False)),
            "dimension_scores": [
                {
                    "dimension": ds.dimension
                    if isinstance(ds.dimension, str)
                    else ds.dimension.value,
                    "score": ds.score,
                    "notes": getattr(ds, "notes", getattr(ds, "reasoning", "")),
                }
                for ds in score.dimension_scores
            ],
            "strengths": score.strengths,
            "weaknesses": score.weaknesses,
            "suggestions": getattr(
                score, "suggestions", getattr(score, "improvement_suggestions", [])
            ),
            "critical_issues": score.critical_issues,
        }
        print(json.dumps(result, indent=2))
    else:
        print(format_report(score))


if __name__ == "__main__":
    asyncio.run(main())
