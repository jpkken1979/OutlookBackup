"""Modelos, enums y configuracion de paths del orchestrator.

Extraido del monolito ``orchestrator.py`` (refactor 2026-06-01). Sin cambios de
comportamiento; solo se ajusto la profundidad de ``__file__`` (AGENT_DIR) por el
paso a paquete.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


import os as _os  # for path resolution env var override

AGENT_DIR = Path(__file__).parent.parent.parent
AGENTS_DIR = AGENT_DIR / "agents"
SKILLS_DIR = AGENT_DIR / "skills"
# 3-tier resolution: env var > user home (NO repo path como default)
# Bugfix 2026-05-24: el default antiguo (.agent/memory) ensuciaba shared_memory.json
# cuando tests instanciaban AntigravityOrchestrator() sin override. Ver
# .claude/memory/bugfix_user_model_json_dirty_after_tests.md.
MEMORY_DIR = (
    Path(_os.environ["ANTIGRAVITY_ORCHESTRATOR_MEMORY"])
    if _os.environ.get("ANTIGRAVITY_ORCHESTRATOR_MEMORY")
    else Path.home() / ".antigravity" / "memory"
)
AGENT_CARDS_DIR = AGENT_DIR / "agent_cards"


class AgentTier(Enum):
    """Agent specialization tiers for execution ordering."""

    PLANNING = 1  # planner, product-manager, architect
    DEVELOPMENT = 2  # frontend, backend, database, mobile
    QUALITY = 3  # testing, security, performance
    OPERATIONS = 4  # devops, documentation, debugger
    SPECIALIZED = 5  # game-dev, seo, code-archaeologist
    UNS_BUSINESS = 6  # Japanese HR specialists


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


# =============================================================================
# DATA MODELS
# =============================================================================


class AgentConfig(BaseModel):
    """Configuration for an Antigravity agent."""

    name: str
    tier: int
    role: str
    goal: str = ""
    backstory: str = ""
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    allow_delegation: bool = True
    verbose: bool = False
    max_iter: int = 15
    max_rpm: int = 10


class TaskConfig(BaseModel):
    """Configuration for a task."""

    id: str
    description: str
    expected_output: str
    agent: str | None = None
    context: list[str] = Field(default_factory=list)
    async_execution: bool = False
    human_input: bool = False


class ExecutionPlan(BaseModel):
    """Plan for executing a complex task."""

    id: str
    original_task: str
    phases: list[dict[str, Any]] = Field(default_factory=list)
    total_agents: int = 0
    estimated_complexity: str = "medium"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ExecutionResult(BaseModel):
    """Result of task execution."""

    task_id: str
    status: str
    output: str
    agent: str
    duration_seconds: float
    tokens_used: int = 0
    completed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
