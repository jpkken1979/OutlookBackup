"""
Autonomous Execution — Brain-aware autonomous planning and execution.

Integrates with Brain Network to:
- Query relevant knowledge before planning (avoid repeating errors)
- Store outcomes and decisions after execution
- Provide context-aware autonomous loops

Phase 1: Brain-aware recall + plan awareness
Phase 2: Conditional workflows + loop checkpoints
Phase 3: Orchestration + audit trail
"""

from __future__ import annotations

from .planner import (
    BrainAwarePlanner,
    PlanContext,
    ExecutionOutcome,
    create_brain_aware_planner,
    # Phase 2
    AutonomousLoop,
    LoopCheckpoint,
    LoopConfig,
    # Phase 3
    BrainOrchestrator,
    OrchestratedPlan,
)

__all__ = [
    "BrainAwarePlanner",
    "PlanContext",
    "ExecutionOutcome",
    "create_brain_aware_planner",
    # Phase 2
    "AutonomousLoop",
    "LoopCheckpoint",
    "LoopConfig",
    # Phase 3
    "BrainOrchestrator",
    "OrchestratedPlan",
]
