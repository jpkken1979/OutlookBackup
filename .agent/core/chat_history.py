"""ChatHistory — SQLite storage for OpenClaw messages with full-text search."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Represents a single chat message."""

    id: int | None = None
    conversation_id: str = ""
    role: str = ""  # user, assistant, system
    content: str = ""
    timestamp: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, handling metadata serialization."""
        data = asdict(self)
        if self.metadata:
            data["metadata"] = json.dumps(self.metadata)
        if not self.timestamp:
            data["timestamp"] = datetime.now(UTC).isoformat()
        return data


class ChatHistoryDB:
    """SQLite backend for chat message storage with full-text search."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize chat history database.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.antigravity/chat_history.db
        """
        if db_path is None:
            db_path = Path.home() / ".antigravity" / "chat_history.db"
        else:
            db_path = Path(db_path)

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema with FTS (full-text search)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Main messages table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
                """
            )

            # Full-text search virtual table
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    conversation_id,
                    role,
                    timestamp
                )
                """
            )

            # Conversation metadata table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
                """
            )

            # Create indices for common queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, timestamp DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_role_timestamp
                ON messages(role, timestamp DESC)
                """
            )

            conn.commit()
            log.info("Chat history database initialized at %s", self.db_path)
        finally:
            conn.close()

    async def add_message(self, msg: ChatMessage) -> ChatMessage:
        """Add a message to the database.

        Args:
            msg: ChatMessage to add

        Returns:
            ChatMessage with ID set
        """
        if not msg.timestamp:
            msg.timestamp = datetime.now(UTC).isoformat()

        def _insert() -> ChatMessage:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                metadata_str = json.dumps(msg.metadata) if msg.metadata else None

                cursor.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        msg.conversation_id,
                        msg.role,
                        msg.content,
                        msg.timestamp,
                        metadata_str,
                    ),
                )

                # Add to FTS
                cursor.execute(
                    """
                    INSERT INTO messages_fts (content, conversation_id, role, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        msg.content,
                        msg.conversation_id,
                        msg.role,
                        msg.timestamp,
                    ),
                )

                # Update conversation timestamp
                cursor.execute(
                    """
                    UPDATE conversations SET updated_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now(UTC).isoformat(), msg.conversation_id),
                )

                conn.commit()
                msg.id = cursor.lastrowid
                return msg
            finally:
                conn.close()

        return await asyncio.to_thread(_insert)

    async def search_messages(
        self,
        query: str,
        conversation_id: str | None = None,
        limit: int = 20,
    ) -> list[ChatMessage]:
        """Search messages using full-text search.

        Args:
            query: Search query
            conversation_id: Optional filter by conversation
            limit: Max results to return

        Returns:
            List of matching ChatMessage objects
        """

        def _search() -> list[ChatMessage]:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                sql = """
                    SELECT m.id, m.conversation_id, m.role, m.content, m.timestamp, m.metadata
                    FROM messages m
                    WHERE m.id IN (
                        SELECT rowid FROM messages_fts WHERE content MATCH ?
                    )
                """
                params: list[Any] = [query]

                if conversation_id:
                    sql += " AND m.conversation_id = ?"
                    params.append(conversation_id)

                sql += " ORDER BY m.timestamp DESC LIMIT ?"
                params.append(limit)

                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()

                messages = []
                for row in rows:
                    msg = ChatMessage(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        role=row["role"],
                        content=row["content"],
                        timestamp=row["timestamp"],
                        metadata=(json.loads(row["metadata"]) if row["metadata"] else None),
                    )
                    messages.append(msg)

                return messages
            finally:
                conn.close()

        return await asyncio.to_thread(_search)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> list[ChatMessage]:
        """Get all messages from a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Max messages to return

        Returns:
            List of ChatMessage objects in chronological order
        """

        def _fetch() -> list[ChatMessage]:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, conversation_id, role, content, timestamp, metadata
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (conversation_id, limit),
                )
                rows = cursor.fetchall()

                messages = []
                for row in rows:
                    msg = ChatMessage(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        role=row["role"],
                        content=row["content"],
                        timestamp=row["timestamp"],
                        metadata=(json.loads(row["metadata"]) if row["metadata"] else None),
                    )
                    messages.append(msg)

                return messages
            finally:
                conn.close()

        return await asyncio.to_thread(_fetch)

    async def export_to_markdown(
        self,
        conversation_id: str,
        output_path: Path | None = None,
    ) -> str:
        """Export a conversation to markdown.

        Args:
            conversation_id: Conversation to export
            output_path: Optional file path to write to

        Returns:
            Markdown content
        """
        messages = await self.get_conversation_messages(conversation_id, limit=500)

        lines = [
            f"# Chat History: {conversation_id}",
            "",
            f"Exported: {datetime.now(UTC).isoformat()}",
            "",
        ]

        for msg in messages:
            role_str = msg.role.upper()
            lines.append(f"## {role_str}")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            if msg.timestamp:
                lines.append(f"**Time:** {msg.timestamp}")
                lines.append("")

        content = "\n".join(lines)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            log.info("Exported conversation to %s", output_path)

        return content

    async def export_to_json(
        self,
        conversation_id: str,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        """Export a conversation to JSON.

        Args:
            conversation_id: Conversation to export
            output_path: Optional file path to write to

        Returns:
            Dictionary with conversation data
        """
        messages = await self.get_conversation_messages(conversation_id, limit=500)

        data = {
            "conversation_id": conversation_id,
            "exported_at": datetime.now(UTC).isoformat(),
            "message_count": len(messages),
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "metadata": msg.metadata,
                }
                for msg in messages
            ],
        }

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            log.info("Exported conversation to %s", output_path)

        return data

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with stats
        """

        def _stats() -> dict[str, Any]:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) as total FROM messages")
                total_messages = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(DISTINCT conversation_id) as count FROM messages")
                total_conversations = cursor.fetchone()[0]

                cursor.execute("SELECT role, COUNT(*) as count FROM messages GROUP BY role")
                role_counts = {row[0]: row[1] for row in cursor.fetchall()}

                cursor.execute(
                    "SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM messages"
                )
                row = cursor.fetchone()
                oldest = row[0] if row else None
                newest = row[1] if row else None

                return {
                    "total_messages": total_messages,
                    "total_conversations": total_conversations,
                    "messages_by_role": role_counts,
                    "oldest_message": oldest,
                    "newest_message": newest,
                    "db_path": str(self.db_path),
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_stats)
