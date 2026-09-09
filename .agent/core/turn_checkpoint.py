"""Durable, redacted checkpoints for provider-routed LLM turns.

The proxy may retry a request before the first token, rotate providers after a
quota/circuit failure, or stop after a partial stream. This module records those
facts without persisting prompts, responses, credentials, or raw idempotency
keys.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import tempfile
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

STATE_PREPARED: Final = "prepared"
STATE_SENT: Final = "sent"
STATE_STREAMING: Final = "streaming"
STATE_COMPLETED: Final = "completed"
STATE_FAILED: Final = "failed"
TURN_STATES: Final = frozenset(
    {STATE_PREPARED, STATE_SENT, STATE_STREAMING, STATE_COMPLETED, STATE_FAILED}
)

CONTINUITY_INITIAL: Final = "initial"
CONTINUITY_NEXT_TURN: Final = "next_turn_rotation"
CONTINUITY_FULL_RETRY: Final = "full_retry"
CONTINUITY_RESUMED: Final = "resumed"
CONTINUITY_INTERRUPTED: Final = "interrupted"
CONTINUITY_MODES: Final = frozenset(
    {
        CONTINUITY_INITIAL,
        CONTINUITY_NEXT_TURN,
        CONTINUITY_FULL_RETRY,
        CONTINUITY_RESUMED,
        CONTINUITY_INTERRUPTED,
    }
)

_SAFE_TRACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._:/ -]+")
_DEFAULT_RECENT_LIMIT = 100
_MAX_RECENT_LIMIT = 500
_MAX_RETAINED_TURNS = 2_000


class TurnCheckpointConflict(ValueError):
    """A trace id was reused for a different request payload."""


@dataclass(frozen=True, slots=True)
class TurnAttempt:
    """Opaque metadata required to dispatch one upstream attempt."""

    trace_id: str
    attempt: int
    provider: str
    model: str
    idempotency_key: str
    continuity: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_label(value: str, *, fallback: str = "unknown", limit: int = 160) -> str:
    cleaned = _SAFE_LABEL_RE.sub("_", str(value).strip())[:limit]
    return cleaned or fallback


def normalize_trace_id(value: str | None) -> str:
    """Return a safe opaque trace id, replacing untrusted header values."""

    candidate = (value or "").strip()
    if _SAFE_TRACE_RE.fullmatch(candidate):
        return candidate
    return f"route-{secrets.token_hex(16)}"


def _request_metadata(payload: bytes) -> dict[str, Any]:
    """Extract non-content request shape; never return prompt/tool text."""

    metadata: dict[str, Any] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "messages": 0,
        "tools": 0,
        "stream": None,
    }
    try:
        body = json.loads(payload)
    except (TypeError, ValueError):
        return metadata
    if not isinstance(body, dict):
        return metadata
    messages = body.get("messages")
    tools = body.get("tools")
    metadata["messages"] = len(messages) if isinstance(messages, list) else 0
    metadata["tools"] = len(tools) if isinstance(tools, list) else 0
    metadata["stream"] = bool(body.get("stream", True))
    return metadata


def _default_db_path() -> Path:
    override = os.environ.get("ANTIGRAVITY_TURN_CHECKPOINT_DB", "").strip()
    if override:
        return Path(override).expanduser()
    worker = os.environ.get("PYTEST_XDIST_WORKER", "").strip()
    if worker:
        return (
            Path(tempfile.gettempdir())
            / "antigravity-pytest"
            / f"turn-checkpoints-{worker}-{os.getpid()}.db"
        )
    return Path.home() / ".antigravity" / "proxy" / "turn_checkpoints.db"


class TurnCheckpointStore:
    """SQLite-backed turn lifecycle with bounded retention."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS turn_checkpoints (
                    trace_id TEXT PRIMARY KEY,
                    request_sha256 TEXT NOT NULL,
                    request_bytes INTEGER NOT NULL,
                    message_count INTEGER NOT NULL,
                    tool_count INTEGER NOT NULL,
                    requested_stream INTEGER,
                    state TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    continuity TEXT NOT NULL,
                    partial_stream INTEGER NOT NULL DEFAULT 0,
                    resume_supported INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turn_attempts (
                    trace_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    idempotency_key_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    continuity TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (trace_id, attempt),
                    FOREIGN KEY (trace_id) REFERENCES turn_checkpoints(trace_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS turn_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    from_provider TEXT NOT NULL,
                    to_provider TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    continuity TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (trace_id) REFERENCES turn_checkpoints(trace_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_turn_updated
                    ON turn_checkpoints(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_turn_events_trace
                    ON turn_events(trace_id, id);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def prepare(self, trace_id: str, payload: bytes, provider: str, model: str) -> dict[str, Any]:
        trace_id = normalize_trace_id(trace_id)
        metadata = _request_metadata(payload)
        now = _now()
        provider = _safe_label(provider)
        model = _safe_label(model)
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT request_sha256 FROM turn_checkpoints WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            if existing is not None:
                if existing["request_sha256"] != metadata["sha256"]:
                    raise TurnCheckpointConflict(
                        "trace id reused with a different redacted request fingerprint"
                    )
                return self.get(trace_id) or {}
            self._conn.execute(
                """
                INSERT INTO turn_checkpoints (
                    trace_id, request_sha256, request_bytes, message_count,
                    tool_count, requested_stream, state, provider, model,
                    continuity, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    metadata["sha256"],
                    metadata["bytes"],
                    metadata["messages"],
                    metadata["tools"],
                    (None if metadata["stream"] is None else int(bool(metadata["stream"]))),
                    STATE_PREPARED,
                    provider,
                    model,
                    CONTINUITY_INITIAL,
                    now,
                    now,
                ),
            )
            self._prune_locked()
        return self.get(trace_id) or {}

    def begin_attempt(
        self,
        trace_id: str,
        provider: str,
        model: str,
        *,
        reason: str = "dispatch",
        continuity: str = CONTINUITY_INITIAL,
    ) -> TurnAttempt:
        if continuity not in CONTINUITY_MODES:
            raise ValueError(f"unsupported continuity mode: {continuity}")
        provider = _safe_label(provider)
        model = _safe_label(model)
        reason = _safe_label(reason)
        now = _now()
        key = f"turn-{secrets.token_hex(20)}"
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT attempt FROM turn_checkpoints WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown turn checkpoint: {trace_id}")
            attempt = int(row["attempt"]) + 1
            self._conn.execute(
                """
                INSERT INTO turn_attempts (
                    trace_id, attempt, provider, model, idempotency_key_sha256,
                    state, continuity, reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    attempt,
                    provider,
                    model,
                    key_hash,
                    STATE_SENT,
                    continuity,
                    reason,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                """
                UPDATE turn_checkpoints
                SET state = ?, provider = ?, model = ?, attempt = ?,
                    continuity = ?, partial_stream = 0,
                    resume_supported = 0, updated_at = ?
                WHERE trace_id = ?
                """,
                (STATE_SENT, provider, model, attempt, continuity, now, trace_id),
            )
            self._insert_event_locked(
                trace_id,
                "attempt_sent",
                "",
                provider,
                attempt,
                continuity,
                reason,
                now,
            )
        return TurnAttempt(trace_id, attempt, provider, model, key, continuity)

    def mark_streaming(self, trace_id: str, attempt: int) -> None:
        self._transition(trace_id, attempt, STATE_STREAMING, event="stream_started")

    def complete(self, trace_id: str, attempt: int, *, reason: str = "stream_completed") -> None:
        self._transition(
            trace_id,
            attempt,
            STATE_COMPLETED,
            event="turn_completed",
            reason=reason,
        )

    def fail(
        self,
        trace_id: str,
        attempt: int,
        *,
        reason: str,
        partial_stream: bool,
        resume_supported: bool,
    ) -> None:
        # Capability is not the same as a successful resume. A partial stream
        # remains interrupted until an adapter performs and records a resume.
        now = _now()
        reason = _safe_label(reason)
        with self._lock, self._conn:
            attempt_row = self._conn.execute(
                """
                SELECT continuity FROM turn_attempts
                WHERE trace_id = ? AND attempt = ?
                """,
                (trace_id, attempt),
            ).fetchone()
            continuity = (
                CONTINUITY_INTERRUPTED
                if partial_stream
                else (
                    str(attempt_row["continuity"])
                    if attempt_row is not None
                    else CONTINUITY_INITIAL
                )
            )
            self._conn.execute(
                """
                UPDATE turn_attempts
                SET state = ?, continuity = ?, reason = ?, updated_at = ?
                WHERE trace_id = ? AND attempt = ?
                """,
                (STATE_FAILED, continuity, reason, now, trace_id, attempt),
            )
            self._conn.execute(
                """
                UPDATE turn_checkpoints
                SET state = ?, continuity = ?, partial_stream = ?,
                    resume_supported = ?, updated_at = ?
                WHERE trace_id = ?
                """,
                (
                    STATE_FAILED,
                    continuity,
                    int(partial_stream),
                    int(resume_supported),
                    now,
                    trace_id,
                ),
            )
            self._insert_event_locked(
                trace_id,
                "stream_interrupted" if partial_stream else "attempt_failed",
                "",
                "",
                attempt,
                continuity,
                reason,
                now,
            )

    def record_rotation(
        self,
        trace_id: str,
        *,
        from_provider: str,
        to_provider: str,
        reason: str,
        continuity: str,
    ) -> None:
        if continuity not in CONTINUITY_MODES:
            raise ValueError(f"unsupported continuity mode: {continuity}")
        now = _now()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT attempt FROM turn_checkpoints WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            if row is None:
                return
            self._insert_event_locked(
                trace_id,
                "provider_rotation",
                _safe_label(from_provider),
                _safe_label(to_provider),
                int(row["attempt"]),
                continuity,
                _safe_label(reason),
                now,
            )
            self._conn.execute(
                """
                UPDATE turn_checkpoints
                SET provider = ?, continuity = ?, updated_at = ?
                WHERE trace_id = ?
                """,
                (_safe_label(to_provider), continuity, now, trace_id),
            )

    def _transition(
        self,
        trace_id: str,
        attempt: int,
        state: str,
        *,
        event: str,
        reason: str = "",
    ) -> None:
        if state not in TURN_STATES:
            raise ValueError(f"unsupported turn state: {state}")
        now = _now()
        with self._lock, self._conn:
            attempt_row = self._conn.execute(
                """
                SELECT continuity FROM turn_attempts
                WHERE trace_id = ? AND attempt = ?
                """,
                (trace_id, attempt),
            ).fetchone()
            if attempt_row is None:
                raise KeyError(f"unknown turn attempt: {trace_id}/{attempt}")
            continuity = str(attempt_row["continuity"])
            self._conn.execute(
                """
                UPDATE turn_attempts SET state = ?, updated_at = ?
                WHERE trace_id = ? AND attempt = ?
                """,
                (state, now, trace_id, attempt),
            )
            self._conn.execute(
                """
                UPDATE turn_checkpoints SET state = ?, updated_at = ?
                WHERE trace_id = ?
                """,
                (state, now, trace_id),
            )
            self._insert_event_locked(
                trace_id,
                event,
                "",
                "",
                attempt,
                continuity,
                _safe_label(reason, fallback="") if reason else "",
                now,
            )

    def _insert_event_locked(
        self,
        trace_id: str,
        event: str,
        from_provider: str,
        to_provider: str,
        attempt: int,
        continuity: str,
        reason: str,
        created_at: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO turn_events (
                trace_id, event, from_provider, to_provider, attempt,
                continuity, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                _safe_label(event),
                from_provider,
                to_provider,
                attempt,
                continuity,
                reason,
                created_at,
            ),
        )

    def _prune_locked(self) -> None:
        self._conn.execute(
            """
            DELETE FROM turn_checkpoints
            WHERE trace_id IN (
                SELECT trace_id FROM turn_checkpoints
                ORDER BY updated_at DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (_MAX_RETAINED_TURNS,),
        )

    def get(self, trace_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM turn_checkpoints WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            if row is None:
                return None
            attempts = self._conn.execute(
                """
                SELECT attempt, provider, model, idempotency_key_sha256, state,
                       continuity, reason, created_at, updated_at
                FROM turn_attempts WHERE trace_id = ? ORDER BY attempt
                """,
                (trace_id,),
            ).fetchall()
            events = self._conn.execute(
                """
                SELECT event, from_provider, to_provider, attempt, continuity,
                       reason, created_at
                FROM turn_events WHERE trace_id = ? ORDER BY id
                """,
                (trace_id,),
            ).fetchall()
        data = dict(row)
        data["requested_stream"] = (
            None if data["requested_stream"] is None else bool(data["requested_stream"])
        )
        data["partial_stream"] = bool(data["partial_stream"])
        data["resume_supported"] = bool(data["resume_supported"])
        data["attempts"] = [dict(item) for item in attempts]
        data["events"] = [dict(item) for item in events]
        return data

    def recent(self, limit: int = _DEFAULT_RECENT_LIMIT) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), _MAX_RECENT_LIMIT))
        with self._lock:
            trace_ids = [
                row["trace_id"]
                for row in self._conn.execute(
                    """
                    SELECT trace_id FROM turn_checkpoints
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
        return [checkpoint for trace_id in trace_ids if (checkpoint := self.get(trace_id))]


@lru_cache(maxsize=1)
def get_turn_checkpoint_store() -> TurnCheckpointStore:
    return TurnCheckpointStore()
