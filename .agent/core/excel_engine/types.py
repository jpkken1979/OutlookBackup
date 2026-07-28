"""Excel Engine — types and schemas.

Single source of truth for dataclasses and enums shared across the engine,
backends, MCP server, and HTTP endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

SessionId = str


class Backend(str, Enum):
    """Backends supported by the engine."""

    OPENPYXL = "openpyxl"
    XLWINGS = "xlwings"
    SUPER_AGENT = "super-agent"


class NumberFmt(str, Enum):
    """Common number formats used in UNS workflows."""

    JPY = "¥#,##0"
    JPY_DEC = "¥#,##0.00"
    USD = "$#,##0.00"
    EUR = "€#,##0.00"
    PCT = "0.00%"
    ISO_DATE = "yyyy-mm-dd"
    ISO_DATETIME = "yyyy-mm-dd hh:mm:ss"


@dataclass
class CellFormat:
    """Cell formatting options applied via set_format."""

    bold: bool = False
    italic: bool = False
    font_color: str | None = None
    bg_color: str | None = None
    number_format: str | None = None
    font_size: int | None = None
    align: Literal["left", "center", "right"] | None = None


@dataclass
class SessionState:
    """Internal lifecycle state of a session."""

    session_id: SessionId
    path: str
    mode: Literal["read", "write", "live"]
    opened_with: Backend
    state: Literal["idle", "busy", "dead"] = "idle"
    opened_at: float = 0.0
    last_used_at: float = 0.0
    n_ops: int = 0
    error_count: int = 0


@dataclass
class SessionInfo:
    """Public-facing snapshot of a session."""

    session_id: SessionId
    path: str
    mode: str
    backend: Backend
    opened_at: float
    last_used_at: float
    n_ops: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "session_id": self.session_id,
            "path": self.path,
            "mode": self.mode,
            "backend": self.backend.value,
            "opened_at": self.opened_at,
            "last_used_at": self.last_used_at,
            "n_ops": self.n_ops,
        }


@dataclass
class ErrorInfo:
    """Structured error returned in OpResult.error."""

    category: Literal["transient", "recoverable", "user", "fatal"]
    code: str
    message: str
    backend_message: str | None
    suggested_next_actions: list[str]
    retryable: bool
    retry_after_ms: int | None
    brain_hint_used: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "category": self.category,
            "code": self.code,
            "message": self.message,
            "backend_message": self.backend_message,
            "suggested_next_actions": list(self.suggested_next_actions),
            "retryable": self.retryable,
            "retry_after_ms": self.retry_after_ms,
            "brain_hint_used": self.brain_hint_used,
        }


@dataclass
class OpResult:
    """Uniform result of any engine operation."""

    status: Literal["ok", "error"]
    request_id: str
    duration_ms: int
    backend_used: Backend | None
    data: dict[str, Any] | None = None
    error: ErrorInfo | None = None
    recovery_applied: dict[str, Any] | None = None
    brain_hints_applied: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "status": self.status,
            "request_id": self.request_id,
            "duration_ms": self.duration_ms,
            "backend_used": self.backend_used.value if self.backend_used else None,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "recovery_applied": self.recovery_applied,
            "brain_hints_applied": list(self.brain_hints_applied),
        }
