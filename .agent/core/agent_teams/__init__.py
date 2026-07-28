#!/usr/bin/env python3
"""
Agent Teams - Peer-to-peer agent collaboration with message passing.

Enables agents to work as coordinated teams where members can:
1. Discover teammates and their capabilities
2. Send direct messages to specific teammates
3. Broadcast messages to the entire team
4. Delegate subtasks to specialized teammates
5. Build shared context through conversation threads
6. Reach consensus on decisions

Builds on existing infrastructure:
- DynamicTeamOrchestrator for team formation
- AgentMessenger for message routing
- AgentExecutor for actual execution

Usage:
    from core.agent_teams import TeamManager, spawn_team

    manager = TeamManager()
    team = await manager.spawn_team(
        task="Crear API REST con autenticacion OAuth",
        agents=["architect", "api-designer", "security-auditor", "coder"],
        lead="architect",
    )

Refactor 2026-05-31: el monolito ``agent_teams.py`` (1621 lineas) se dividio en
este paquete sin cambios de comportamiento. La API publica se preserva intacta:
``from core.agent_teams import TeamManager, TaskListManager, spawn_team, ...``
sigue funcionando identico.

- ``enums``    — enums P2P (TeamStatus, MemberRole, MessageType, MessagePriority)
- ``models``   — dataclasses P2P (TeamMessage, Teammate, ConsensusRequest, ...)
- ``teams``    — AgentTeam, TeamManager y funciones de conveniencia
- ``tasklist`` — Task List Teams (tareas compartidas con file locking)
"""

from __future__ import annotations

from .enums import MemberRole, MessagePriority, MessageType, TeamStatus
from .models import (
    ConsensusRequest,
    TeamExecutionResult,
    TeamMessage,
    Teammate,
)
from .tasklist import (
    TEAMS_ROOT,
    TaskListManager,
    TaskListTeam,
    TaskStatus,
    TeamEvent,
    TeamFileLock,
    TeamTask,
)
from .teams import (
    AGENTS_DIR,
    AgentTeam,
    TeamManager,
    auto_team,
    get_team_manager,
    spawn_team,
)

__all__ = [
    # Enums P2P
    "TeamStatus",
    "MemberRole",
    "MessageType",
    "MessagePriority",
    # Modelos P2P
    "TeamMessage",
    "Teammate",
    "ConsensusRequest",
    "TeamExecutionResult",
    # Teams P2P
    "AgentTeam",
    "TeamManager",
    "get_team_manager",
    "spawn_team",
    "auto_team",
    "AGENTS_DIR",
    # Task List Teams
    "TaskStatus",
    "TeamTask",
    "TeamFileLock",
    "TeamEvent",
    "TaskListTeam",
    "TaskListManager",
    "TEAMS_ROOT",
]
