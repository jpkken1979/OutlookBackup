# mypy: ignore-errors
"""
Autonomous Agent Loop - ReAct-style execution with real LLM + Tool Use.

This is the missing piece that transforms Antigravity agents from "prompt skins"
into truly autonomous agents. It implements a ReAct (Reason + Act) loop:

    Observe -> Think -> Act -> Reflect -> (repeat until done)

Usage:
    from core.autonomous_loop import AutonomousLoop, run_autonomous

    # Quick usage
    result = await run_autonomous(
        task="Find all TODO comments and create a summary",
        agent_name="explorer",
        max_iterations=10,
    )

Refactor 2026-05-31: el monolito ``autonomous_loop.py`` (1840 lineas) se dividio
en este paquete sin cambios de comportamiento. La API publica se preserva: los
imports ``from core.autonomous_loop import AutonomousLoop, run_autonomous, ...``
siguen funcionando identico. Tres clases de ajuste fueron necesarias por el
cambio de profundidad del paquete (cubiertas por characterization tests):
imports relativos ``.`` -> ``..``, ``Path(__file__)`` un nivel mas, y el CLI.

- ``paths``     — helpers de WRITABLE_ROOTS
- ``models``    — LoopStatus, StepType, LoopStep, LoopResult
- ``tools``     — builders de definiciones de tools
- ``providers`` — auto-deteccion de proveedor LLM
- ``loop``      — AutonomousLoop + run_autonomous
- ``__main__``  — CLI (python -m core.autonomous_loop)
"""

from __future__ import annotations

from .loop import AutonomousLoop, run_autonomous
from .models import LoopResult, LoopStatus, LoopStep, StepType
from .paths import _get_writable_roots, _is_path_in_writable_roots
from .providers import detect_best_provider, get_available_providers
from .tools import (
    build_anthropic_tools,
    build_default_tools,
    build_tools_from_agent,
)

__all__ = [
    # Motor
    "AutonomousLoop",
    "run_autonomous",
    # Modelos
    "LoopStatus",
    "StepType",
    "LoopStep",
    "LoopResult",
    # Tools
    "build_tools_from_agent",
    "build_anthropic_tools",
    "build_default_tools",
    # Providers
    "detect_best_provider",
    "get_available_providers",
    # Path helpers (consumidos internamente / por tests)
    "_get_writable_roots",
    "_is_path_in_writable_roots",
]
