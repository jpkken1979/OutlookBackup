"""Analyst agent — Pre-planning requirements analysis."""

from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Requirement:
    """A single requirement identified during analysis."""
    description: str
    category: str  # functional, non_functional, constraint, assumption
    priority: str  # must_have, should_have, could_have
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Risk:
    """A potential risk or blocker identified."""
    description: str
    likelihood: str  # high, medium, low
    impact: str  # high, medium, low
    mitigation: str | None = None


@dataclass
class AnalysisReport:
    """Complete requirements analysis report."""
    problem_statement: str
    requirements: list[Requirement]
    risks: list[Risk]
    alternatives: list[str]
    suggested_phases: list[str]

    def format_markdown(self) -> str:
        """Format the report in OMC-inspired markdown."""
        lines = [
            "# Analysis Report",
            "",
            f"**Problem**: {self.problem_statement}",
            "",
            "## Requirements",
        ]
        for req in self.requirements:
            lines.append(f"- [{req.priority.upper()}] {req.category}: {req.description}")

        lines.extend(["", "## Risks"])
        for risk in self.risks:
            mitigation = f" → {risk.mitigation}" if risk.mitigation else ""
            lines.append(f"- [{risk.likelihood.upper()}/{risk.impact.upper()}] {risk.description}{mitigation}")

        lines.extend(["", "## Alternatives"])
        for i, alt in enumerate(self.alternatives, 1):
            lines.append(f"{i}. {alt}")

        lines.extend(["", "## Suggested Phases"])
        for phase in self.suggested_phases:
            lines.append(f"- {phase}")

        return "\n".join(lines)


class AnalystAgent:
    """Pre-planning agent that analyzes requirements and identifies gaps."""

    def analyze(
        self,
        task_description: str,
        context: str | None = None
    ) -> AnalysisReport:
        """Perform requirements analysis on a task.

        Args:
            task_description: What the user wants to accomplish.
            context: Additional context about the project or constraints.

        Returns:
            AnalysisReport with requirements, risks, and alternatives.
        """
        logger.info(f"Analyzing task: {task_description[:50]}...")

        # Simple analysis — in production this would use more sophisticated prompting
        requirements = [
            Requirement(
                description="Understand the full scope of the task",
                category="functional",
                priority="must_have"
            ),
            Requirement(
                description="Identify technical constraints and dependencies",
                category="constraint",
                priority="must_have"
            ),
        ]

        risks = [
            Risk(
                description="Requirements may be incomplete or change mid-flight",
                likelihood="medium",
                impact="medium",
                mitigation="Iterate in small batches"
            )
        ]

        alternatives = [
            "Approach A: Direct implementation with minimal planning",
            "Approach B: Full analysis then implementation (recommended)",
            "Approach C: Incremental delivery with continuous feedback",
        ]

        suggested_phases = [
            "Phase 1: Requirements validation",
            "Phase 2: Architecture and design",
            "Phase 3: Implementation",
            "Phase 4: Verification",
        ]

        return AnalysisReport(
            problem_statement=task_description,
            requirements=requirements,
            risks=risks,
            alternatives=alternatives,
            suggested_phases=suggested_phases
        )


def main() -> AnalysisReport:
    """CLI entry point for analyst agent."""
    import sys

    task = sys.argv[1] if len(sys.argv) > 1 else "Analyze requirements"
    agent = AnalystAgent()
    return agent.analyze(task)


if __name__ == "__main__":
    report = main()
    print(report.format_markdown())
