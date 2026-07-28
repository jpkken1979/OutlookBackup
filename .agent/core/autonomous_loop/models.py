# mypy: ignore-errors
"""Modelos del motor autonomo: enums LoopStatus/StepType y dataclasses Loop*.

Extraido del monolito ``autonomous_loop.py`` (refactor 2026-05-31). Sin cambios
de comportamiento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LoopStatus(str, Enum):
    """Status of the autonomous loop."""

    RUNNING = "running"
    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    ERROR = "error"
    STOPPED_BY_AGENT = "stopped_by_agent"


class StepType(str, Enum):
    """Type of step in the loop."""

    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REFLECTION = "reflection"
    FINAL_ANSWER = "final_answer"


@dataclass
class LoopStep:
    """A single step in the autonomous loop."""

    step_num: int
    step_type: StepType
    content: str
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "step": self.step_num,
            "type": self.step_type.value,
            "content": self.content[:500],
            "tool": self.tool_name,
            "tokens": self.tokens_used,
            "cost": self.cost_usd,
            "duration_ms": self.duration_ms,
        }


@dataclass
class LoopResult:
    """Result of an autonomous loop execution."""

    status: LoopStatus
    final_output: str
    steps: list[LoopStep]
    total_iterations: int
    total_tokens: int
    total_cost_usd: float
    total_duration_ms: float
    tools_used: list[str]
    agent_name: str = ""
    task: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "final_output": self.final_output[:2000],
            "total_iterations": self.total_iterations,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_duration_ms": self.total_duration_ms,
            "tools_used": self.tools_used,
            "agent": self.agent_name,
            "steps": [s.to_dict() for s in self.steps],
        }

    @property
    def succeeded(self) -> bool:
        return self.status == LoopStatus.COMPLETED
