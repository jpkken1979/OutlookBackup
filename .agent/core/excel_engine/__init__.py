"""Excel Engine — core orchestration layer for Excel operations.

Single source of truth for all Excel parse/write/automate operations.
Exposed via MCP stdio server and Gateway HTTP endpoints.
"""

from .engine import ExcelEngine
from .types import (
    Backend,
    CellFormat,
    ErrorInfo,
    NumberFmt,
    OpResult,
    SessionId,
    SessionInfo,
    SessionState,
)

__all__ = [
    "Backend",
    "CellFormat",
    "ErrorInfo",
    "ExcelEngine",
    "NumberFmt",
    "OpResult",
    "SessionId",
    "SessionInfo",
    "SessionState",
]
