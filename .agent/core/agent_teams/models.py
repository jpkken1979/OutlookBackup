"""Modelos de datos del subsistema Agent Teams (P2P).

Extraido del monolito ``agent_teams.py`` (refactor 2026-05-31). Sin cambios de
comportamiento.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .enums import MemberRole, MessagePriority, MessageType


@dataclass
class TeamMessage:
    """Mensaje entre miembros del equipo."""

    id: str
    from_agent: str
    to_agent: str  # "*" para broadcast
    message_type: MessageType
    content: str
    priority: MessagePriority = MessagePriority.NORMAL
    thread_id: str | None = None
    reply_to: str | None = None
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Serializa el mensaje."""
        result = asdict(self)
        result["message_type"] = self.message_type.value
        result["priority"] = self.priority.value
        return result


@dataclass
class Teammate:
    """Un miembro del equipo con sus capacidades."""

    name: str
    role: MemberRole
    description: str = ""
    skills: list[str] = field(default_factory=list)
    status: str = "ready"  # ready, working, waiting, done, error
    has_executable: bool = False

    def to_dict(self) -> dict:
        """Serializa el teammate."""
        return {
            "name": self.name,
            "role": self.role.value,
            "description": self.description,
            "skills": self.skills,
            "status": self.status,
            "has_executable": self.has_executable,
        }


@dataclass
class ConsensusRequest:
    """Solicitud de consenso al equipo."""

    id: str
    topic: str
    options: list[str]
    initiator: str
    votes: dict = field(default_factory=dict)  # agent -> option
    reasoning: dict = field(default_factory=dict)  # agent -> reasoning
    deadline_seconds: int = 60
    result: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class TeamExecutionResult:
    """Resultado de la ejecución del equipo."""

    team_id: str
    task: str
    success: bool
    outputs: dict  # agent_name -> output
    messages_exchanged: int
    consensus_decisions: list[dict]
    execution_time_ms: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializa el resultado."""
        return asdict(self)
