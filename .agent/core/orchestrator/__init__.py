#!/usr/bin/env python3
"""
Antigravity Orchestrator v3.0 - CrewAI-based Multi-Agent Orchestration.

This is the brain of the Antigravity ecosystem. It coordinates all specialist
agents using CrewAI for real task execution with:
- Intelligent task decomposition
- Parallel execution within tiers
- Shared memory across agents
- A2A protocol for agent discovery
- OpenTelemetry observability

Refactor 2026-06-01: el monolito ``orchestrator.py`` (1768 lineas) se dividio en
este paquete sin cambios de comportamiento. La API publica se preserva: los
imports ``from core.orchestrator import AntigravityOrchestrator, AGENT_REGISTRY,
AgentConfig, ...`` siguen funcionando identico. Ajustes por el cambio de
profundidad del paquete (cubiertos por characterization tests): imports
relativos ``.`` -> ``..`` y ``Path(__file__)`` un nivel mas.

- ``models``    — enums, modelos pydantic y paths de configuracion
- ``discovery`` — auto-discovery de agentes desde IDENTITY.md
- ``registry``  — AGENT_REGISTRY (fallback hardcodeado + discovery)
- ``core``      — clase AntigravityOrchestrator
- ``__main__``  — CLI (python -m core.orchestrator)
"""

from __future__ import annotations

import logging

# Logging setup — debe correr ANTES de importar .registry (que loguea al hacer
# discovery de agentes), preservando el orden/format del monolito original.
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.orchestrator")

from .core import (  # noqa: E402
    HAS_AUTONOMOUS_LOOP,
    HAS_CREWAI,
    HAS_LANGGRAPH,
    AntigravityOrchestrator,
)
from .discovery import _discover_agents  # noqa: E402
from .models import (  # noqa: E402
    AGENT_CARDS_DIR,
    AGENT_DIR,
    AGENTS_DIR,
    MEMORY_DIR,
    SKILLS_DIR,
    AgentConfig,
    AgentTier,
    ExecutionPlan,
    ExecutionResult,
    TaskConfig,
    TaskStatus,
)
from .registry import AGENT_REGISTRY  # noqa: E402

__all__ = [
    "AntigravityOrchestrator",
    "AGENT_REGISTRY",
    # Modelos / enums
    "AgentTier",
    "TaskStatus",
    "AgentConfig",
    "TaskConfig",
    "ExecutionPlan",
    "ExecutionResult",
    # Paths de configuracion
    "AGENT_DIR",
    "AGENTS_DIR",
    "SKILLS_DIR",
    "MEMORY_DIR",
    "AGENT_CARDS_DIR",
    # Flags de capacidades
    "HAS_CREWAI",
    "HAS_LANGGRAPH",
    "HAS_AUTONOMOUS_LOOP",
    # Discovery
    "_discover_agents",
]
