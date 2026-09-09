"""Memory Bridge module for Telegram intelligence.

Synchronizes Telegram session memory with Nexus Brain Network
and gateway mem0. Enables persistent context across conversations.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Never
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    # Fallback mock for httpx if not available
    class httpx:  # type: ignore
        class Client:
            def __init__(self, *args, **kwargs):
                pass

            def post(self, *args, **kwargs) -> Never:
                raise Exception("httpx not installed")

            def get(self, *args, **kwargs) -> Never:
                raise Exception("httpx not installed")

            def close(self) -> None:
                pass


logger = logging.getLogger(__name__)


@dataclass
class SessionMemory:
    """Telegram session memory snapshot.

    Args:
        session_id: Unique session identifier.
        user_id: Telegram user ID.
        messages: List of (role, content) tuples.
        context: Extracted context data.
        tags: Memory tags for categorization.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    session_id: str
    user_id: int
    messages: list[tuple[str, str]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": self.messages,
            "context": self.context,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class BrainClient:
    """Client for Nexus Brain Network via gateway.

    Communicates with gateway at /v1/call with connector=brain.
    """

    def __init__(self, gateway_url: str = "http://127.0.0.1:4747", api_key: str | None = None):
        """Initialize Brain client.

        Args:
            gateway_url: Gateway base URL.
            api_key: Optional API key for authentication.
        """
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.client = httpx.Client(timeout=10.0)

    def query(self, query_text: str) -> dict[str, Any] | None:
        """Query Brain Network.

        Args:
            query_text: Query string.

        Returns:
            Query results or None on error.
        """
        try:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            response = self.client.post(
                urljoin(self.gateway_url, "/v1/call"),
                json={
                    "connector": "brain",
                    "operation": "query",
                    "arguments": {"query": query_text},
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Brain query failed: {e}")
            return None

    def ingest(
        self,
        title: str,
        context: str,
        area: str,
        tags: list[str],
        node_type: str = "discovery",
        importance: str = "medium",
    ) -> bool:
        """Ingest knowledge into Brain.

        Args:
            title: Node title.
            context: Node content/context.
            area: Knowledge area/category.
            tags: List of tags.
            node_type: Node type (discovery, decision, pattern, etc.).
            importance: Importance level (low, medium, high).

        Returns:
            True if successful.
        """
        try:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            response = self.client.post(
                urljoin(self.gateway_url, "/v1/call"),
                json={
                    "connector": "brain",
                    "operation": "ingest",
                    "arguments": {
                        "title": title,
                        "context": context,
                        "area": area,
                        "tags": tags,
                        "node_type": node_type,
                        "importance": importance,
                    },
                },
                headers=headers,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Brain ingest failed: {e}")
            return False

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()


class Mem0Client:
    """Client for mem0 semantic memory cache.

    Communicates with gateway at /v1/mem0/*.
    """

    def __init__(self, gateway_url: str = "http://127.0.0.1:4747", api_key: str | None = None):
        """Initialize mem0 client.

        Args:
            gateway_url: Gateway base URL.
            api_key: Optional API key for authentication.
        """
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.client = httpx.Client(timeout=10.0)

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> bool:
        """Store memory in mem0.

        Args:
            content: Memory content.
            metadata: Optional metadata dict.

        Returns:
            True if successful.
        """
        try:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            response = self.client.post(
                urljoin(self.gateway_url, "/v1/mem0/add"),
                json={
                    "content": content,
                    "metadata": metadata or {},
                },
                headers=headers,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"mem0 store failed: {e}")
            return False

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]] | None:
        """Search mem0 for similar memories.

        Args:
            query: Search query.
            top_k: Number of top results.

        Returns:
            List of memory results or None on error.
        """
        try:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            response = self.client.get(
                urljoin(self.gateway_url, "/v1/mem0/search"),
                params={"q": query, "top_k": top_k},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"mem0 search failed: {e}")
            return None

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()


class SessionMemoryStore:
    """Local file-based session memory storage."""

    def __init__(self, storage_dir: Path | None = None):
        """Initialize store.

        Args:
            storage_dir: Directory for session files. Defaults to ~/.antigravity/telegram_sessions
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".antigravity" / "telegram_sessions"

        storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir = storage_dir

    def save(self, memory: SessionMemory) -> Path:
        """Save session memory to file.

        Args:
            memory: SessionMemory to save.

        Returns:
            Path to saved file.
        """
        file_path = self.storage_dir / f"{memory.session_id}.json"
        with open(file_path, "w") as f:
            json.dump(memory.to_dict(), f, indent=2)
        logger.info(f"Saved session memory: {file_path}")
        return file_path

    def load(self, session_id: str) -> SessionMemory | None:
        """Load session memory from file.

        Args:
            session_id: Session ID.

        Returns:
            SessionMemory or None if not found.
        """
        file_path = self.storage_dir / f"{session_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = json.load(f)

            return SessionMemory(
                session_id=data["session_id"],
                user_id=data["user_id"],
                messages=data["messages"],
                context=data["context"],
                tags=data["tags"],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
            )
        except Exception as e:
            logger.error(f"Failed to load session memory: {e}")
            return None

    def list_sessions(self, user_id: int) -> list[str]:
        """List all sessions for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            List of session IDs.
        """
        sessions = []
        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                if data.get("user_id") == user_id:
                    sessions.append(data["session_id"])
            except Exception:
                pass
        return sessions


class MemoryBridge:
    """Main memory bridge orchestrator.

    Synchronizes Telegram session memory with Brain and mem0.
    """

    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:4747",
        api_key: str | None = None,
        storage_dir: Path | None = None,
    ):
        """Initialize bridge.

        Args:
            gateway_url: Gateway URL.
            api_key: Optional API key.
            storage_dir: Session storage directory.
        """
        self.brain_client = BrainClient(gateway_url, api_key)
        self.mem0_client = Mem0Client(gateway_url, api_key)
        self.session_store = SessionMemoryStore(storage_dir)

    def create_session(self, session_id: str, user_id: int) -> SessionMemory:
        """Create new session memory.

        Args:
            session_id: Unique session ID.
            user_id: Telegram user ID.

        Returns:
            New SessionMemory object.
        """
        memory = SessionMemory(session_id=session_id, user_id=user_id)
        self.session_store.save(memory)
        return memory

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add message to session and sync to memory systems.

        Args:
            session_id: Session ID.
            role: Message role (user/assistant/system).
            content: Message content.
            metadata: Optional metadata.

        Returns:
            True if successful.
        """
        memory = self.session_store.load(session_id)
        if not memory:
            logger.error(f"Session not found: {session_id}")
            return False

        # Add to session
        memory.messages.append((role, content))
        memory.updated_at = datetime.now()

        # Extract context if user message
        if role == "user":
            self._extract_context(memory, content, metadata)

        # Save locally
        self.session_store.save(memory)

        # Sync to mem0
        self.mem0_client.store(
            content=f"[{role}] {content}",
            metadata={
                "session_id": session_id,
                "user_id": memory.user_id,
                "role": role,
                **(metadata or {}),
            },
        )

        return True

    def _extract_context(
        self,
        memory: SessionMemory,
        content: str,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Extract and store context from user message.

        Args:
            memory: Current session memory.
            content: Message content.
            metadata: Message metadata.
        """
        # Simple context extraction
        if "error" in content.lower():
            memory.context["last_error"] = content
            memory.tags.append("error")
        elif "question" in content.lower():
            memory.context["last_question"] = content
            memory.tags.append("question")
        elif "code" in content.lower():
            memory.context["has_code"] = True
            memory.tags.append("code")

    def sync_to_brain(
        self,
        session_id: str,
        summary: str,
        area: str = "telegram",
        node_type: str = "session",
    ) -> bool:
        """Sync session to Brain Network.

        Args:
            session_id: Session ID.
            summary: Session summary.
            area: Knowledge area.
            node_type: Node type.

        Returns:
            True if successful.
        """
        memory = self.session_store.load(session_id)
        if not memory:
            return False

        tags = memory.tags + ["telegram", "session"]

        return self.brain_client.ingest(
            title=f"Telegram Session: {session_id}",
            context=summary,
            area=area,
            tags=list(set(tags)),
            node_type=node_type,
            importance="medium",
        )

    def query_context(self, query: str) -> dict[str, Any] | None:
        """Query Brain for relevant context.

        Args:
            query: Query string.

        Returns:
            Query results or None.
        """
        return self.brain_client.query(query)

    def close(self) -> None:
        """Close clients."""
        self.brain_client.close()
        self.mem0_client.close()
