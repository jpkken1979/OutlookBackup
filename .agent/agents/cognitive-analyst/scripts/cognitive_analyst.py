#!/usr/bin/env python3
"""
Cognitive Analyst Agent.

Uses Chain-of-Thought and deep analysis for complex problem understanding.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Setup
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("cognitive-analyst")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@dataclass
class ReasoningStep:
    """A single reasoning step."""

    step_number: int
    thought: str
    observation: str
    conclusion: str
    confidence: float


@dataclass
class Finding:
    """An analysis finding."""

    category: str
    severity: str  # info, low, medium, high, critical
    title: str
    description: str
    evidence: list[str]
    recommendations: list[str]


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    task: str
    summary: str
    reasoning_chain: list[ReasoningStep]
    findings: list[Finding]
    recommendations: list[str]
    confidence: float
    knowledge_gaps: list[str]
    duration_ms: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "summary": self.summary,
            "reasoning_chain": [
                {
                    "step": s.step_number,
                    "thought": s.thought,
                    "observation": s.observation,
                    "conclusion": s.conclusion,
                    "confidence": s.confidence,
                }
                for s in self.reasoning_chain
            ],
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "evidence": f.evidence,
                    "recommendations": f.recommendations,
                }
                for f in self.findings
            ],
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "knowledge_gaps": self.knowledge_gaps,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def export_report(self) -> str:
        """Export as markdown report."""
        lines = [
            "# Cognitive Analysis Report",
            "",
            f"**Task:** {self.task}",
            f"**Confidence:** {self.confidence:.0%}",
            f"**Duration:** {self.duration_ms:.0f}ms",
            "",
            "## Summary",
            "",
            self.summary,
            "",
            "## Reasoning Chain",
            "",
        ]

        for step in self.reasoning_chain:
            lines.extend(
                [
                    f"### Step {step.step_number}",
                    f"**Thought:** {step.thought}",
                    f"**Observation:** {step.observation}",
                    f"**Conclusion:** {step.conclusion}",
                    f"*Confidence: {step.confidence:.0%}*",
                    "",
                ]
            )

        lines.extend(["## Findings", ""])

        for finding in self.findings:
            severity_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
                "info": "🔵",
            }.get(finding.severity, "⚪")

            lines.extend(
                [
                    f"### {severity_icon} {finding.title}",
                    f"**Category:** {finding.category} | **Severity:** {finding.severity}",
                    "",
                    finding.description,
                    "",
                    "**Evidence:**",
                ]
            )
            for evidence in finding.evidence:
                lines.append(f"- {evidence}")
            lines.append("")

        if self.knowledge_gaps:
            lines.extend(["## Knowledge Gaps", ""])
            for gap in self.knowledge_gaps:
                lines.append(f"- {gap}")
            lines.append("")

        lines.extend(["## Recommendations", ""])
        for i, rec in enumerate(self.recommendations, 1):
            lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class CognitiveAnalyst:
    """
    Agent that uses deep cognitive analysis.

    Combines:
    - Chain-of-thought reasoning
    - Self-reflection
    - Metacognition
    - Knowledge graph building
    """

    def __init__(self):
        self.analysis_history: list[AnalysisResult] = []
        self._modules_loaded = False
        self._modules = {}

    async def _load_modules(self):
        """Lazy load intelligence modules."""
        if self._modules_loaded:
            return

        try:
            from core.intelligence import (
                ChainOfThought,
                Metacognition,
                SelfReflection,
                create_knowledge_graph,
            )

            self._modules["cot"] = ChainOfThought()
            self._modules["reflection"] = SelfReflection()
            self._modules["metacognition"] = Metacognition()
            self._modules["knowledge"] = create_knowledge_graph()
            self._modules_loaded = True
        except ImportError as e:
            logger.warning(f"Could not load intelligence modules: {e}")
            self._modules_loaded = True

    async def analyze(
        self, task: str, context: dict | None = None, depth: str = "deep"
    ) -> AnalysisResult:
        """
        Perform cognitive analysis.

        Args:
            task: What to analyze
            context: Additional context (files, focus areas, etc.)
            depth: Analysis depth (quick, moderate, deep)

        Returns:
            Complete analysis result
        """
        start_time = datetime.now()
        await self._load_modules()

        context = context or {}
        reasoning_chain: list[ReasoningStep] = []
        findings: list[Finding] = []
        knowledge_gaps: list[str] = []
        overall_confidence = 0.8

        # Step 1: Understand the task
        step1 = await self._reason_step(
            step_number=1,
            thought=f"Understanding the task: {task}",
            action="Parse task and identify scope",
        )
        reasoning_chain.append(step1)

        # Step 2: Gather context
        step2 = await self._reason_step(
            step_number=2,
            thought="Gathering relevant context and information",
            action="Analyze provided context and identify patterns",
        )
        reasoning_chain.append(step2)

        # Step 3: Identify focus areas
        focus_areas = context.get("focus_areas", self._detect_focus_areas(task))
        step3 = await self._reason_step(
            step_number=3,
            thought=f"Focusing analysis on: {', '.join(focus_areas)}",
            action="Prioritize analysis areas based on task",
        )
        reasoning_chain.append(step3)

        # Step 4: Deep analysis per focus area
        for area in focus_areas:
            area_findings = await self._analyze_area(task, area, context)
            findings.extend(area_findings)

            step = await self._reason_step(
                step_number=len(reasoning_chain) + 1,
                thought=f"Analyzing {area}",
                action=f"Found {len(area_findings)} findings in {area}",
            )
            reasoning_chain.append(step)

        # Step 5: Self-reflection
        reflection_step = await self._self_reflect(task, findings)
        reasoning_chain.append(reflection_step)

        # Adjust confidence based on reflection
        if reflection_step.confidence < 0.7:
            knowledge_gaps.append("Analysis may be incomplete - consider additional context")
            overall_confidence *= 0.9

        # Step 6: Identify knowledge gaps
        gaps = await self._identify_knowledge_gaps(task, context)
        knowledge_gaps.extend(gaps)

        # Generate recommendations
        recommendations = self._generate_recommendations(findings)

        # Generate summary
        summary = self._generate_summary(task, findings, recommendations)

        duration = (datetime.now() - start_time).total_seconds() * 1000

        result = AnalysisResult(
            task=task,
            summary=summary,
            reasoning_chain=reasoning_chain,
            findings=findings,
            recommendations=recommendations,
            confidence=overall_confidence,
            knowledge_gaps=knowledge_gaps,
            duration_ms=duration,
            metadata={
                "depth": depth,
                "focus_areas": focus_areas,
                "modules_used": list(self._modules.keys()),
            },
        )

        self.analysis_history.append(result)
        return result

    async def _reason_step(self, step_number: int, thought: str, action: str) -> ReasoningStep:
        """Create a reasoning step."""
        # Use chain-of-thought if available
        if "cot" in self._modules and self._modules["cot"]:
            try:
                result = await self._modules["cot"].think_step(thought)
                observation = str(result) if result else action
            except Exception:
                observation = action
        else:
            observation = action

        return ReasoningStep(
            step_number=step_number,
            thought=thought,
            observation=observation,
            conclusion=f"Completed: {action}",
            confidence=0.8,
        )

    def _detect_focus_areas(self, task: str) -> list[str]:
        """Detect focus areas from task."""
        task_lower = task.lower()
        areas = []

        area_keywords = {
            "security": ["security", "auth", "vulnerability", "injection", "xss"],
            "performance": ["performance", "speed", "optimize", "slow", "cache"],
            "architecture": ["architecture", "design", "structure", "pattern"],
            "code_quality": ["quality", "clean", "maintainable", "readable"],
            "testing": ["test", "coverage", "spec", "unit"],
            "functionality": ["function", "feature", "behavior", "bug"],
        }

        for area, keywords in area_keywords.items():
            if any(kw in task_lower for kw in keywords):
                areas.append(area)

        return areas if areas else ["general"]

    async def _analyze_area(self, task: str, area: str, context: dict) -> list[Finding]:
        """Analyze a specific area."""
        findings = []

        # Generate findings based on area
        if area == "security":
            findings.append(
                Finding(
                    category="security",
                    severity="medium",
                    title="Security Analysis Required",
                    description=f"Security-focused analysis of: {task}",
                    evidence=["Task mentions security-related concerns"],
                    recommendations=["Perform OWASP-based security audit"],
                )
            )
        elif area == "performance":
            findings.append(
                Finding(
                    category="performance",
                    severity="info",
                    title="Performance Analysis Required",
                    description=f"Performance-focused analysis of: {task}",
                    evidence=["Task mentions performance concerns"],
                    recommendations=["Profile critical paths", "Identify bottlenecks"],
                )
            )
        elif area == "architecture":
            findings.append(
                Finding(
                    category="architecture",
                    severity="info",
                    title="Architecture Analysis",
                    description=f"Architectural analysis of: {task}",
                    evidence=["Task requires understanding system design"],
                    recommendations=["Document component interactions", "Identify coupling"],
                )
            )
        else:
            findings.append(
                Finding(
                    category=area,
                    severity="info",
                    title=f"{area.title()} Analysis",
                    description=f"Analysis of {area} aspects for: {task}",
                    evidence=[f"Task involves {area}"],
                    recommendations=[f"Deep dive into {area} concerns"],
                )
            )

        return findings

    async def _self_reflect(self, task: str, findings: list[Finding]) -> ReasoningStep:
        """Self-reflect on analysis quality."""
        if "reflection" in self._modules and self._modules["reflection"]:
            try:
                reflection = await self._modules["reflection"].reflect(
                    output=json.dumps(
                        [f.to_dict() if hasattr(f, "to_dict") else str(f) for f in findings]
                    ),
                    task=task,
                )
                confidence = reflection.confidence if hasattr(reflection, "confidence") else 0.8
            except Exception:
                confidence = 0.75
        else:
            confidence = 0.75

        return ReasoningStep(
            step_number=999,  # Will be renumbered
            thought="Reflecting on analysis completeness and accuracy",
            observation=f"Found {len(findings)} findings across multiple areas",
            conclusion="Analysis appears comprehensive"
            if confidence > 0.7
            else "Analysis may need additional context",
            confidence=confidence,
        )

    async def _identify_knowledge_gaps(self, task: str, context: dict) -> list[str]:
        """Identify knowledge gaps using metacognition."""
        gaps = []

        if "metacognition" in self._modules and self._modules["metacognition"]:
            try:
                assessment = await self._modules["metacognition"].assess(task)
                if hasattr(assessment, "knowledge_gaps"):
                    gaps.extend(assessment.knowledge_gaps)
            except Exception:
                pass

        # Heuristic gaps
        if not context.get("files"):
            gaps.append("No specific files provided - analysis based on task description only")

        return gaps

    def _generate_recommendations(self, findings: list[Finding]) -> list[str]:
        """Generate recommendations from findings."""
        recommendations = []

        # Aggregate recommendations from findings
        for finding in findings:
            recommendations.extend(finding.recommendations)

        # Deduplicate and prioritize
        seen = set()
        unique_recs = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recs.append(rec)

        return unique_recs[:10]  # Top 10 recommendations

    def _generate_summary(
        self, task: str, findings: list[Finding], recommendations: list[str]
    ) -> str:
        """Generate analysis summary."""
        critical = sum(1 for f in findings if f.severity == "critical")
        high = sum(1 for f in findings if f.severity == "high")
        medium = sum(1 for f in findings if f.severity == "medium")

        severity_summary = []
        if critical > 0:
            severity_summary.append(f"{critical} critical")
        if high > 0:
            severity_summary.append(f"{high} high")
        if medium > 0:
            severity_summary.append(f"{medium} medium")

        severity_text = ", ".join(severity_summary) if severity_summary else "no significant issues"

        return (
            f"Cognitive analysis of '{task}' identified {len(findings)} findings "
            f"({severity_text}). Generated {len(recommendations)} recommendations "
            f"for improvement."
        )


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Cognitive Analyst Agent")
    parser.add_argument("task", nargs="?", help="Analysis task")
    parser.add_argument("--depth", choices=["quick", "moderate", "deep"], default="deep")
    parser.add_argument("--focus", nargs="+", help="Focus areas")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.task:
        parser.print_help()
        return

    analyst = CognitiveAnalyst()
    context = {}
    if args.focus:
        context["focus_areas"] = args.focus

    result = await analyst.analyze(args.task, context, args.depth)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.export_report())


if __name__ == "__main__":
    asyncio.run(main())
