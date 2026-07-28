"""Enums del subsistema Agent Teams (P2P).

Extraido del monolito ``agent_teams.py`` (refactor 2026-05-31). Sin cambios de
comportamiento.
"""

from __future__ import annotations

from enum import Enum


class TeamStatus(Enum):
    """Estado del equipo."""

    FORMING = "forming"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class MemberRole(Enum):
    """Roles dentro del equipo."""

    LEAD = "lead"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    SUPPORTER = "supporter"
    CRITIC = "critic"


class MessageType(Enum):
    """Tipos de mensaje entre agentes."""

    DIRECT = "direct"
    BROADCAST = "broadcast"
    DELEGATION = "delegation"
    RESULT = "result"
    CONSENSUS_REQUEST = "consensus_request"
    CONSENSUS_VOTE = "consensus_vote"
    STATUS_UPDATE = "status_update"
    HELP_REQUEST = "help_request"


class MessagePriority(Enum):
    """Prioridad de mensajes."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3
