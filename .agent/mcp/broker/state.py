"""SQLite state for traces and write approvals.

Only hashes and redacted metadata are persisted. Connector arguments and
credentials never enter this database.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import ApprovalRecord, OperationClass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def arguments_digest(arguments: dict[str, Any]) -> str:
    """Return a stable digest without persisting the raw arguments."""

    serialized = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class BrokerState:
    """Small transactional store shared by MCP and Nexus REST handlers."""

    def __init__(self, database_path: Path):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database_path = database_path
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    operation_class TEXT NOT NULL,
                    arguments_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_approvals_status
                    ON approvals(status, created_at);

                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    target TEXT,
                    status TEXT NOT NULL,
                    retryable INTEGER NOT NULL DEFAULT 0,
                    duration_ms REAL,
                    error_code TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_traces_created
                    ON traces(created_at DESC);

                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def request_approval(
        self,
        connector_id: str,
        operation: str,
        operation_class: OperationClass,
        arguments: dict[str, Any],
    ) -> ApprovalRecord:
        digest = arguments_digest(arguments)
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM approvals
                WHERE connector_id = ? AND operation = ? AND arguments_digest = ?
                  AND status = 'pending'
                ORDER BY created_at DESC LIMIT 1
                """,
                (connector_id, operation, digest),
            ).fetchone()
            if existing:
                return ApprovalRecord.model_validate(dict(existing))

            approval = ApprovalRecord(
                approval_id=f"apr_{uuid.uuid4().hex}",
                connector_id=connector_id,
                operation=operation,
                operation_class=operation_class,
                arguments_digest=digest,
                status="pending",
                created_at=_utc_now(),
            )
            connection.execute(
                """
                INSERT INTO approvals (
                    approval_id, connector_id, operation, operation_class,
                    arguments_digest, status, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.connector_id,
                    approval.operation,
                    approval.operation_class.value,
                    approval.arguments_digest,
                    approval.status,
                    approval.created_at,
                    approval.resolved_at,
                ),
            )
            return approval

    def resolve_approval(self, approval_id: str, approved: bool) -> ApprovalRecord | None:
        status = "approved" if approved else "denied"
        resolved_at = _utc_now()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET status = ?, resolved_at = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (status, resolved_at, approval_id),
            )
            if cursor.rowcount == 0:
                return self.get_approval(approval_id, connection=connection)
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
            return ApprovalRecord.model_validate(dict(row)) if row else None

    def consume_approval(
        self,
        approval_id: str,
        connector_id: str,
        operation: str,
        arguments: dict[str, Any],
    ) -> bool:
        digest = arguments_digest(arguments)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET status = 'consumed', resolved_at = COALESCE(resolved_at, ?)
                WHERE approval_id = ? AND connector_id = ? AND operation = ?
                  AND arguments_digest = ? AND status = 'approved'
                """,
                (_utc_now(), approval_id, connector_id, operation, digest),
            )
            return cursor.rowcount == 1

    def get_approval(
        self,
        approval_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ApprovalRecord | None:
        owns_connection = connection is None
        current = connection or self._connect()
        try:
            row = current.execute(
                "SELECT * FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
            return ApprovalRecord.model_validate(dict(row)) if row else None
        finally:
            if owns_connection:
                current.close()

    def list_approvals(self, status: str = "pending", limit: int = 100) -> list[ApprovalRecord]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM approvals
                WHERE (? = 'all' OR status = ?)
                ORDER BY created_at DESC LIMIT ?
                """,
                (status, status, safe_limit),
            ).fetchall()
        return [ApprovalRecord.model_validate(dict(row)) for row in rows]

    def record_trace(
        self,
        *,
        trace_id: str,
        action: str,
        target: str | None,
        status: str,
        retryable: bool,
        duration_ms: float,
        error_code: str | None = None,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO traces (
                    trace_id, action, target, status, retryable,
                    duration_ms, error_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    action,
                    target,
                    status,
                    int(retryable),
                    round(duration_ms, 3),
                    error_code,
                    _utc_now(),
                ),
            )

    def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 500)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM traces ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_idempotency_key(self, key: str, operation: str) -> bool:
        """Atomically claim a redacted idempotency key.

        The key is already a random/hash identifier. Request bodies and report
        contents are intentionally never persisted.
        """

        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO idempotency_keys (
                    idempotency_key, operation, created_at
                ) VALUES (?, ?, ?)
                """,
                (key, operation, _utc_now()),
            )
            return cursor.rowcount == 1

    def release_idempotency_key(self, key: str) -> None:
        """Release a claim after a failed operation so the outbox may retry."""

        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM idempotency_keys WHERE idempotency_key = ?",
                (key,),
            )
