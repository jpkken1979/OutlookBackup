"""Session management for Excel Engine.

Pool of workbook sessions with per-session locks (threading.Lock),
TTL-based GC, LRU eviction when capped.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from excel_engine.types import Backend, SessionId, SessionInfo, SessionState

logger = logging.getLogger(__name__)


class SessionLimitExceeded(Exception):
    """Raised when max_sessions reached and eviction is disabled."""


class SessionManager:
    """Pool of Excel sessions.

    Concurrency model: threading.Lock per session (Excel ops are not async).
    TTL-based purge of idle sessions, LRU eviction when capped.

    Args:
        max_sessions: Maximum concurrent sessions allowed.
        ttl_seconds: Idle TTL before gc_expired() purges a session.
        evict_lru: If True, oldest session is closed when at cap; else raises.
    """

    def __init__(
        self,
        max_sessions: int = 5,
        ttl_seconds: int = 1800,
        evict_lru: bool = True,
    ) -> None:
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self.evict_lru = evict_lru
        self._states: dict[SessionId, SessionState] = {}
        self._locks: dict[SessionId, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def create(
        self,
        path: str,
        mode: Literal["read", "write", "live"],
        backend: Backend,
    ) -> SessionId:
        """Create a new session and return its id.

        Args:
            path: Path to the workbook file.
            mode: Access mode — read, write, or live.
            backend: Backend to use for this session.

        Returns:
            The new session id.

        Raises:
            SessionLimitExceeded: If at cap and evict_lru is False.
        """
        with self._global_lock:
            if len(self._states) >= self.max_sessions:
                if self.evict_lru:
                    self._evict_lru_locked()
                else:
                    raise SessionLimitExceeded(f"max_sessions={self.max_sessions} reached")
            sid = self._generate_id()
            now = time.time()
            self._states[sid] = SessionState(
                session_id=sid,
                path=path,
                mode=mode,
                opened_with=backend,
                state="idle",
                opened_at=now,
                last_used_at=now,
                n_ops=0,
                error_count=0,
            )
            self._locks[sid] = threading.Lock()
            logger.info(
                "[session] created sid=%s path=%s mode=%s backend=%s",
                sid,
                path,
                mode,
                backend.value,
            )
            return sid

    def get(self, session_id: SessionId) -> SessionState:
        """Return the session state. Raises KeyError if unknown.

        Synchronized via _global_lock for consistency with list()/close().

        Args:
            session_id: The session identifier.

        Returns:
            The mutable SessionState for this session.

        Raises:
            KeyError: If session_id is unknown.
        """
        with self._global_lock:
            if session_id not in self._states:
                raise KeyError(session_id)
            return self._states[session_id]

    def list(self) -> list[SessionInfo]:
        """Return public snapshots of all active sessions.

        Returns:
            List of SessionInfo for each active session.
        """
        with self._global_lock:
            return [
                SessionInfo(
                    session_id=st.session_id,
                    path=st.path,
                    mode=st.mode,
                    backend=st.opened_with,
                    opened_at=st.opened_at,
                    last_used_at=st.last_used_at,
                    n_ops=st.n_ops,
                )
                for st in self._states.values()
            ]

    def close(self, session_id: SessionId) -> None:
        """Remove the session. Idempotent.

        Args:
            session_id: The session to close. No-op if unknown.
        """
        with self._global_lock:
            self._states.pop(session_id, None)
            self._locks.pop(session_id, None)
        logger.info("[session] closed sid=%s", session_id)

    @contextmanager
    def acquire(self, session_id: SessionId) -> Iterator[SessionState]:
        """Acquire the per-session lock and yield the state.

        Increments n_ops and updates last_used_at on entry.
        Marks state="busy" inside the block, restores to "idle" on exit.

        Note: if close() runs concurrently AFTER acquire() obtained its
        references but BEFORE entering the lock body, the operation still
        completes against the (now-orphaned) state. The session is treated
        as closed for subsequent get()/list() calls.

        Args:
            session_id: The session to lock.

        Yields:
            The SessionState while the lock is held.

        Raises:
            KeyError: If session_id is unknown.
        """
        with self._global_lock:
            if session_id not in self._states:
                raise KeyError(session_id)
            lock = self._locks[session_id]
            st = self._states[session_id]
        # Released _global_lock before acquiring per-session lock to avoid
        # holding both at once.
        with lock:
            st.state = "busy"
            st.n_ops += 1
            st.last_used_at = time.time()
            try:
                yield st
            finally:
                st.state = "idle"
                st.last_used_at = time.time()

    def gc_expired(self) -> list[SessionId]:
        """Purge sessions idle longer than ttl_seconds.

        Only purges sessions in state="idle" (not busy ones).

        Returns:
            The list of purged session ids.
        """
        cutoff = time.time() - self.ttl_seconds
        with self._global_lock:
            expired = [
                sid
                for sid, st in self._states.items()
                if st.last_used_at < cutoff and st.state == "idle"
            ]
            for sid in expired:
                self._states.pop(sid, None)
                self._locks.pop(sid, None)
        if expired:
            logger.info("[session] gc purged %d sessions: %s", len(expired), expired)
        return expired

    def _evict_lru_locked(self) -> None:
        """Evict the least-recently-used session. Caller holds _global_lock."""
        if not self._states:
            return
        lru_sid = min(
            self._states.keys(),
            key=lambda sid: self._states[sid].last_used_at,
        )
        self._states.pop(lru_sid, None)
        self._locks.pop(lru_sid, None)
        logger.info("[session] evicted LRU sid=%s", lru_sid)

    def _generate_id(self) -> SessionId:
        """Generate a unique session id with an s_ prefix."""
        return f"s_{secrets.token_hex(6)}"
