"""Modelos, enums y dataclasses del IntelligentOrchestrator.

Extraido del monolito intelligent_orchestrator.py (Plan 018 — paso 1).
Sin cambios de comportamiento ni de interfaz. La API publica sigue siendo
core.intelligent_orchestrator — estos simbolos se re-exportan desde ahi.

Simbolos exportados:
- TaskComplexity   (Enum)
- ExecutionStrategy (Enum)
- TaskAnalysis      (dataclass)
- ExecutionStep     (dataclass)
- ExecutionResult   (dataclass)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskComplexity(Enum):
    """Task complexity levels."""

    TRIVIAL = "trivial"  # Single action, no thinking needed
    SIMPLE = "simple"  # Few steps, minimal reasoning
    MODERATE = "moderate"  # Multiple steps, some reasoning
    COMPLEX = "complex"  # Many steps, significant reasoning
    EXPERT = "expert"  # Requires deep expertise
    RESEARCH = "research"  # Requires exploration and learning


class ExecutionStrategy(Enum):
    """Execution strategies."""

    DIRECT = "direct"  # Execute immediately
    THINK_FIRST = "think_first"  # Chain-of-thought then execute
    DEBATE = "debate"  # Multi-agent debate then execute
    REACT = "react"  # ReAct loop
    COMPOSED = "composed"  # Compose skills dynamically
    COLLABORATIVE = "collaborative"  # Multiple agents working together
    ADAPTIVE = "adaptive"  # Adapt strategy during execution


@dataclass
class TaskAnalysis:
    """Analysis of a task."""

    task: str
    complexity: TaskComplexity
    domains: list[str]
    required_capabilities: list[str]
    estimated_steps: int
    risk_level: float  # 0-1
    confidence: float  # 0-1
    recommended_strategy: ExecutionStrategy
    recommended_agents: list[str]
    recommended_modules: list[str]
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "complexity": self.complexity.value,
            "domains": self.domains,
            "required_capabilities": self.required_capabilities,
            "estimated_steps": self.estimated_steps,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "recommended_strategy": self.recommended_strategy.value,
            "recommended_agents": self.recommended_agents,
            "recommended_modules": self.recommended_modules,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


@dataclass
class ExecutionStep:
    """A single execution step."""

    step_number: int
    action: str
    agent: str | None
    module: str | None
    input_data: dict
    output_data: dict | None = None
    status: str = "pending"
    duration_ms: float = 0
    error: str | None = None
    reflection: str | None = None


@dataclass
class ExecutionResult:
    """Result of intelligent execution."""

    task: str
    success: bool
    output: Any
    analysis: TaskAnalysis
    steps: list[ExecutionStep]
    total_duration_ms: float
    tokens_used: int
    quality_score: float
    explanation: str
    learnings: list[str]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "success": self.success,
            "output": self.output,
            "analysis": self.analysis.to_dict(),
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "agent": s.agent,
                    "module": s.module,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                    "reflection": s.reflection,
                }
                for s in self.steps
            ],
            "total_duration_ms": self.total_duration_ms,
            "tokens_used": self.tokens_used,
            "quality_score": self.quality_score,
            "explanation": self.explanation,
            "learnings": self.learnings,
            "metadata": self.metadata,
        }

    def export_report(self) -> str:
        """Export as markdown report."""
        lines = [
            "# Intelligent Execution Report",
            "",
            f"**Task:** {self.task}",
            f"**Status:** {'Success' if self.success else 'Failed'}",
            f"**Quality Score:** {self.quality_score:.2f}/1.0",
            f"**Duration:** {self.total_duration_ms:.0f}ms",
            f"**Tokens Used:** {self.tokens_used}",
            "",
            "## Analysis",
            "",
            f"- **Complexity:** {self.analysis.complexity.value}",
            f"- **Strategy:** {self.analysis.recommended_strategy.value}",
            f"- **Domains:** {', '.join(self.analysis.domains)}",
            f"- **Agents Used:** {', '.join(self.analysis.recommended_agents)}",
            "",
            "## Execution Steps",
            "",
        ]

        for step in self.steps:
            status_icon = (
                "OK" if step.status == "completed" else "FAIL" if step.status == "failed" else "..."
            )
            lines.append(f"{step.step_number}. {status_icon} **{step.action}**")
            if step.agent:
                lines.append(f"   - Agent: {step.agent}")
            if step.module:
                lines.append(f"   - Module: {step.module}")
            if step.reflection:
                lines.append(f"   - Reflection: {step.reflection}")
            lines.append(f"   - Duration: {step.duration_ms:.0f}ms")
            lines.append("")

        lines.extend(["## Explanation", "", self.explanation, "", "## Learnings", ""])

        for learning in self.learnings:
            lines.append(f"- {learning}")

        return "\n".join(lines)
