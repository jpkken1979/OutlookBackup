"""Persistencia SQLite del historial de eventos del watcher.

El `EventBus` del gateway mantiene un ring buffer en memoria que se pierde
al reiniciar. Para casos donde el usuario necesita auditar matches pasados
(bugfix analysis, post-mortem, evidencia), persistimos los eventos en
SQLite con TTL configurable.

Uso:
    store = WatcherEventStore(default_store_path())
    store.append(event_dict)
    rows = store.recent(limit=50, importance="critical")
    store.cleanup_expired()

La instancia es thread-safe (sqlite3 con WAL) y se usa desde el mixin del
gateway sin acoplar al EventBus core — es una capa opcional.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity-gateway")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS watcher_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at   INTEGER NOT NULL,
    channel       TEXT NOT NULL,
    watch_id      TEXT NOT NULL,
    label         TEXT,
    pattern_label TEXT,
    importance    TEXT NOT NULL,
    line_text     TEXT,
    line_number   INTEGER NOT NULL DEFAULT 0,
    stream        TEXT,
    matched_at    INTEGER NOT NULL DEFAULT 0,
    raw_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_watch ON watcher_events(watch_id);
CREATE INDEX IF NOT EXISTS idx_events_importance ON watcher_events(importance);
CREATE INDEX IF NOT EXISTS idx_events_received ON watcher_events(received_at);
"""


def default_store_path() -> Path:
    """Ruta por defecto del store. Override via ANTIGRAVITY_WATCHER_HISTORY_DB."""
    override = os.environ.get("ANTIGRAVITY_WATCHER_HISTORY_DB", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".antigravity" / "watcher" / "history.db"


class WatcherEventStore:
    """SQLite-backed store de eventos del watcher.

    Escrituras son single-statement con autocommit para latencia minima.
    TTL default 30 dias (override via ANTIGRAVITY_WATCHER_HISTORY_TTL_DAYS).
    """

    def __init__(self, db_path: Path | None = None, ttl_days: int | None = None) -> None:
        self.db_path = db_path or default_store_path()
        if ttl_days is None:
            try:
                ttl_days = int(
                    os.environ.get("ANTIGRAVITY_WATCHER_HISTORY_TTL_DAYS", "30") or 30
                )
            except ValueError:
                ttl_days = 30
        self.ttl_seconds = max(1, ttl_days) * 86400
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA_SQL)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path), isolation_level=None, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            conn.close()

    def append(self, channel: str, data: dict[str, Any]) -> int | None:
        """Inserta un evento. Silent failure si el store esta corrupto."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO watcher_events "
                    "(received_at, channel, watch_id, label, pattern_label, "
                    "importance, line_text, line_number, stream, matched_at, raw_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(time.time()),
                        channel,
                        str(data.get("watch_id", "")),
                        str(data.get("label") or ""),
                        str(data.get("pattern_label") or ""),
                        str(data.get("importance") or "low"),
                        str(data.get("line_text") or "")[:500],
                        int(data.get("line_number", 0) or 0),
                        str(data.get("stream") or "stdout"),
                        int(data.get("matched_at", 0) or 0),
                        json.dumps(data, ensure_ascii=False),
                    ),
                )
                return cur.lastrowid
        except sqlite3.Error as exc:
            logger.debug("WatcherEventStore.append fallo: %s", exc)
            return None

    def recent(
        self,
        limit: int = 50,
        importance: str | None = None,
        watch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retorna eventos recientes ordenados de mas nuevo a mas viejo."""
        limit = max(1, min(limit, 1000))
        query = "SELECT * FROM watcher_events WHERE 1=1"
        params: list[Any] = []
        if importance in {"low", "high", "critical"}:
            query += " AND importance = ?"
            params.append(importance)
        if watch_id:
            query += " AND watch_id = ?"
            params.append(watch_id)
        query += " ORDER BY received_at DESC, id DESC LIMIT ?"
        params.append(limit)
        try:
            with self._conn() as conn:
                rows = conn.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            logger.debug("WatcherEventStore.recent fallo: %s", exc)
            return []
        return [dict(r) for r in rows]

    def cleanup_expired(self) -> int:
        """Borra eventos mas viejos que TTL. Retorna cantidad eliminada."""
        cutoff = int(time.time()) - self.ttl_seconds
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "DELETE FROM watcher_events WHERE received_at < ?", (cutoff,)
                )
                return cur.rowcount or 0
        except sqlite3.Error as exc:
            logger.debug("WatcherEventStore.cleanup fallo: %s", exc)
            return 0

    def stats(self) -> dict[str, Any]:
        """Contadores basicos para monitoring."""
        try:
            with self._conn() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) AS n FROM watcher_events"
                ).fetchone()["n"]
                by_importance = {
                    r["importance"]: r["n"]
                    for r in conn.execute(
                        "SELECT importance, COUNT(*) AS n FROM watcher_events "
                        "GROUP BY importance"
                    )
                }
                oldest = conn.execute(
                    "SELECT MIN(received_at) AS t FROM watcher_events"
                ).fetchone()["t"]
                newest = conn.execute(
                    "SELECT MAX(received_at) AS t FROM watcher_events"
                ).fetchone()["t"]
        except sqlite3.Error as exc:
            logger.debug("WatcherEventStore.stats fallo: %s", exc)
            return {"available": False, "error": str(exc)}
        return {
            "available": True,
            "total": total,
            "by_importance": by_importance,
            "oldest_timestamp": oldest,
            "newest_timestamp": newest,
            "ttl_seconds": self.ttl_seconds,
            "db_path": str(self.db_path),
        }
