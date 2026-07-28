"""
ShuMobile PWA Backend Sync Module.

Handles synchronization of PWA responses to backend goal tracking via SQLite.
Provides session management, response persistence, and offline queueing.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class ShuPWASession:
    """Represents a PWA session tracking responses to multiple dimensions.

    Attributes:
        session_id: Unique session identifier (UUID).
        goal_id: Goal being tracked in this session.
        created_at: Timestamp when session was created.
        responses: Dimension -> answer mapping.
        status: Session lifecycle state.
        synced_at: Timestamp of last successful sync.
    """

    session_id: str
    goal_id: str
    created_at: datetime
    responses: dict[str, str] = field(default_factory=dict)
    status: Literal["draft", "submitted"] = "draft"
    synced_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for serialization.

        Returns:
            Dictionary representation of the session.
        """
        return {
            "session_id": self.session_id,
            "goal_id": self.goal_id,
            "created_at": self.created_at.isoformat(),
            "responses": self.responses,
            "status": self.status,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }


# =============================================================================
# DATABASE INITIALIZATION & SCHEMA
# =============================================================================


def _ensure_db_initialized(db_path: Path) -> None:
    """Initialize SQLite database with required schema if not exists.

    Args:
        db_path: Path to SQLite database file.

    Raises:
        sqlite3.OperationalError: If database cannot be created or schema fails.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pwa_sessions (
                session_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                responses TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                synced_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pwa_status
            ON pwa_sessions(status)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pwa_goal
            ON pwa_sessions(goal_id)
            """
        )
        conn.commit()
        logger.debug(f"Database initialized at {db_path}")
    except sqlite3.OperationalError as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()


# =============================================================================
# MAIN SYNC CLASS
# =============================================================================


class ShuPWASync:
    """Backend sync service for ShuMobile PWA session responses.

    Manages persistent storage of PWA sessions, response synchronization,
    and offline queue handling via SQLite.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the sync service.

        Args:
            db_path: Path to SQLite database. Defaults to
                ~/.antigravity/pwa_sessions.db.

        Raises:
            ValueError: If db_path parent directory cannot be created.
        """
        if db_path is None:
            antigravity_root = Path.home() / ".antigravity"
            db_path = antigravity_root / "pwa_sessions.db"

        self.db_path = db_path
        _ensure_db_initialized(self.db_path)
        logger.info(f"ShuPWASync initialized with database at {self.db_path}")

    async def async_sync_responses(
        self, session_id: str, responses: dict[str, str]
    ) -> dict[str, Any]:
        """Synchronize PWA responses to backend goal tracking.

        Args:
            session_id: Unique session identifier.
            responses: Dictionary mapping dimension names to answers.

        Returns:
            Result dictionary with keys:
            - status: "success" on success
            - synced_to_goal: Goal ID the responses were synced to
            - error: Error message if sync failed

        Raises:
            ValueError: If session_id or responses are invalid.
            sqlite3.DatabaseError: If database operation fails.
        """
        if not session_id or not isinstance(session_id, str):
            logger.error(f"Invalid session_id: {session_id}")
            return {"status": "error", "error": "Invalid session_id"}

        if not isinstance(responses, dict) or not responses:
            logger.error(f"Invalid responses for session {session_id}: empty or not dict")
            return {"status": "error", "error": "Invalid responses"}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch existing session
            cursor.execute(
                "SELECT goal_id, responses, status FROM pwa_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()

            if not row:
                logger.warning(f"Session {session_id} not found")
                conn.close()
                return {"status": "error", "error": f"Session {session_id} not found"}

            goal_id, existing_responses_json, status = row
            existing_responses = json.loads(existing_responses_json)

            # Merge responses (new ones take precedence)
            merged_responses = {**existing_responses, **responses}

            # Update session
            now = datetime.utcnow()
            cursor.execute(
                """
                UPDATE pwa_sessions
                SET responses = ?, status = ?, synced_at = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    json.dumps(merged_responses),
                    "submitted",
                    now.isoformat(),
                    now.isoformat(),
                    session_id,
                ),
            )
            conn.commit()

            logger.info(
                f"Synced {len(responses)} responses for session {session_id} "
                f"(total: {len(merged_responses)})"
            )

            conn.close()
            return {"status": "success", "synced_to_goal": goal_id}

        except sqlite3.DatabaseError as e:
            logger.error(f"Database error during sync for session {session_id}: {e}")
            return {"status": "error", "error": f"Database error: {str(e)}"}

    async def async_get_sessions(
        self, status: Literal["draft", "submitted"] | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve list of sessions, optionally filtered by status.

        Args:
            status: Filter by session status ("draft", "submitted", or None for all).

        Returns:
            List of session dictionaries.

        Raises:
            sqlite3.DatabaseError: If database operation fails.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    "SELECT * FROM pwa_sessions WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cursor.execute("SELECT * FROM pwa_sessions ORDER BY created_at DESC")

            rows = cursor.fetchall()
            conn.close()

            sessions = []
            for row in rows:
                session_id, goal_id, responses_json, sess_status, created_at, synced_at, _ = row
                sessions.append(
                    {
                        "session_id": session_id,
                        "goal_id": goal_id,
                        "responses": json.loads(responses_json),
                        "status": sess_status,
                        "created_at": created_at,
                        "synced_at": synced_at,
                    }
                )

            logger.debug(f"Retrieved {len(sessions)} sessions")
            return sessions

        except sqlite3.DatabaseError as e:
            logger.error(f"Database error retrieving sessions: {e}")
            raise

    async def async_get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a specific session by ID.

        Args:
            session_id: Unique session identifier.

        Returns:
            Session dictionary if found, None otherwise.

        Raises:
            sqlite3.DatabaseError: If database operation fails.
        """
        if not session_id or not isinstance(session_id, str):
            logger.error(f"Invalid session_id: {session_id}")
            return None

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pwa_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                logger.debug(f"Session {session_id} not found")
                return None

            session_id, goal_id, responses_json, status, created_at, synced_at, _ = row
            return {
                "session_id": session_id,
                "goal_id": goal_id,
                "responses": json.loads(responses_json),
                "status": status,
                "created_at": created_at,
                "synced_at": synced_at,
            }

        except sqlite3.DatabaseError as e:
            logger.error(f"Database error retrieving session {session_id}: {e}")
            raise

    async def async_create_session(
        self, session_id: str, goal_id: str, initial_responses: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Create a new PWA session.

        Args:
            session_id: Unique session identifier (should be UUID).
            goal_id: Goal ID this session tracks.
            initial_responses: Optional initial responses to store.

        Returns:
            Result dictionary with status and created session ID.

        Raises:
            ValueError: If session_id or goal_id are invalid.
            sqlite3.DatabaseError: If database operation fails.
        """
        if not session_id or not isinstance(session_id, str):
            logger.error(f"Invalid session_id: {session_id}")
            return {"status": "error", "error": "Invalid session_id"}

        if not goal_id or not isinstance(goal_id, str):
            logger.error(f"Invalid goal_id: {goal_id}")
            return {"status": "error", "error": "Invalid goal_id"}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if session already exists
            cursor.execute(
                "SELECT session_id FROM pwa_sessions WHERE session_id = ?", (session_id,)
            )
            if cursor.fetchone():
                logger.warning(f"Session {session_id} already exists")
                conn.close()
                return {"status": "error", "error": "Session already exists"}

            # Create new session
            now = datetime.utcnow()
            responses = initial_responses or {}
            cursor.execute(
                """
                INSERT INTO pwa_sessions
                (session_id, goal_id, responses, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    goal_id,
                    json.dumps(responses),
                    "draft",
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            conn.commit()
            conn.close()

            logger.info(f"Created session {session_id} for goal {goal_id}")
            return {"status": "success", "session_id": session_id, "goal_id": goal_id}

        except sqlite3.DatabaseError as e:
            logger.error(f"Database error creating session {session_id}: {e}")
            return {"status": "error", "error": f"Database error: {str(e)}"}

    async def async_get_offline_queue(self) -> list[dict[str, Any]]:
        """Retrieve sessions that are in draft status (offline queue).

        Returns:
            List of draft sessions waiting to be synced.

        Raises:
            sqlite3.DatabaseError: If database operation fails.
        """
        return await self.async_get_sessions(status="draft")

    async def async_delete_session(self, session_id: str) -> dict[str, Any]:
        """Delete a session by ID.

        Args:
            session_id: Unique session identifier.

        Returns:
            Result dictionary with status.

        Raises:
            sqlite3.DatabaseError: If database operation fails.
        """
        if not session_id or not isinstance(session_id, str):
            logger.error(f"Invalid session_id: {session_id}")
            return {"status": "error", "error": "Invalid session_id"}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pwa_sessions WHERE session_id = ?", (session_id,))
            deleted_rows = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted_rows == 0:
                logger.warning(f"Session {session_id} not found for deletion")
                return {"status": "error", "error": "Session not found"}

            logger.info(f"Deleted session {session_id}")
            return {"status": "success", "session_id": session_id}

        except sqlite3.DatabaseError as e:
            logger.error(f"Database error deleting session {session_id}: {e}")
            return {"status": "error", "error": f"Database error: {str(e)}"}


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_sync_instance: ShuPWASync | None = None


def get_pwa_sync(db_path: Path | None = None) -> ShuPWASync:
    """Get or create the singleton ShuPWASync instance.

    Args:
        db_path: Optional path to SQLite database (only used on first call).

    Returns:
        Singleton ShuPWASync instance.
    """
    global _sync_instance
    if _sync_instance is None:
        _sync_instance = ShuPWASync(db_path)
    return _sync_instance


__all__ = [
    "ShuPWASession",
    "ShuPWASync",
    "get_pwa_sync",
]
