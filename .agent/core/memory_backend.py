"""
Memory Backend — Interfaz ABC para backends de observaciones del ecosistema.
Solo un backend activo a la vez (plugin slot exclusivo).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryBackend(ABC):
    """Interfaz base. Implementar store(), retrieve() y get_stats()."""

    @abstractmethod
    def store(
        self,
        session_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: str,
        metadata: dict[str, Any],
    ) -> str: ...

    @abstractmethod
    def retrieve(self, session_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_stats(self) -> dict[str, Any]: ...


class SQLiteMemoryBackend(MemoryBackend):
    """Backend SQLite. Zero-deps. Default del ecosistema."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS observations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_input TEXT NOT NULL DEFAULT '{}',
                tool_output TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL DEFAULT (julianday('now'))
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_session ON observations(session_id)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def store(
        self,
        session_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: str,
        metadata: dict[str, Any],
    ) -> str:
        obs_id = str(uuid.uuid4())
        with self._conn() as c:
            c.execute(
                "INSERT INTO observations(id,session_id,tool_name,tool_input,tool_output,metadata) VALUES(?,?,?,?,?,?)",
                (
                    obs_id,
                    session_id,
                    tool_name,
                    json.dumps(tool_input),
                    tool_output[:4096],
                    json.dumps(metadata),
                ),
            )
        return obs_id

    def retrieve(self, session_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            if session_id:
                rows = c.execute(
                    "SELECT * FROM observations WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM observations ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "tool_name": r["tool_name"],
                "tool_input": json.loads(r["tool_input"]),
                "tool_output": r["tool_output"],
                "metadata": json.loads(r["metadata"]),
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    def get_stats(self) -> dict[str, Any]:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            sessions = c.execute("SELECT COUNT(DISTINCT session_id) FROM observations").fetchone()[
                0
            ]
        return {
            "backend": "sqlite",
            "db_path": str(self._db_path),
            "total_observations": total,
            "unique_sessions": sessions,
        }


def get_backend_from_config(config: dict[str, Any] | None = None) -> MemoryBackend:
    """Factory. Lee config o usa SQLite en ~/.antigravity/observations.db."""
    import os

    cfg = (config or {}).get("memory", {})
    if cfg.get("backend", "sqlite") == "sqlite":
        default = Path.home() / ".antigravity" / "observations.db"
        return SQLiteMemoryBackend(
            Path(cfg.get("db_path", os.environ.get("ANTIGRAVITY_DB_PATH", str(default))))
        )
    raise ValueError(f"Backend desconocido: '{cfg['backend']}'. Soportados: ['sqlite']")
