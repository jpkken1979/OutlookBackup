"""Excel Engine — core orchestration layer for Excel operations.

Single source of truth for all Excel parse/write/automate operations.
Exposed via MCP stdio server and Gateway HTTP endpoints.
"""

try:
    from excel_engine.engine import ExcelEngine
except ImportError:
    ExcelEngine = None  # type: ignore[assignment,misc]

from excel_engine.types import (
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
