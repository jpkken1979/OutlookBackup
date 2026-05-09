#!/usr/bin/env python3
"""
Antigravity Memory System - Persistent shared memory with vector search.

Features:
- ChromaDB vector storage for semantic search
- JSON file persistence for structured data
- Cross-agent memory sharing
- Automatic embeddings generation
"""

import json
import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from pydantic import BaseModel, Field

logger = logging.getLogger("antigravity.memory")


# =============================================================================
# DATA MODELS
# =============================================================================


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    type: str  # decision, context, learning, user_preference
    content: str
    metadata: dict = Field(default_factory=dict)
    agent: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    relevance_score: float = 1.0


class SharedMemoryState(BaseModel):
    """Complete shared memory state."""

    decisions: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    learnings: list[dict] = Field(default_factory=list)
    user_preferences: dict = Field(default_factory=dict)
    agent_states: dict = Field(default_factory=dict)
    project_overview: dict = Field(default_factory=dict)
    session_history: list[dict] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# SHARED MEMORY (JSON-based)
# =============================================================================


class SharedMemory:
    """
    JSON-based shared memory for agents.

    This provides a simple but effective way for agents to share
    context, decisions, and learnings across executions.
    """

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "shared_memory.json"
        self.state = self._load()
        logger.info(f"SharedMemory initialized at {self.memory_dir}")

    @staticmethod
    @contextmanager
    def _file_lock(file_handle: Any, exclusive: bool = True):
        """Acquire a file lock (exclusive for writes, shared for reads).

        Uses fcntl on Unix and msvcrt on Windows. The lock is released
        automatically when the context manager exits.

        Args:
            file_handle: Open file object to lock.
            exclusive: True for exclusive (write) lock, False for shared (read) lock.
        """
        try:
            if sys.platform == "win32":
                # msvcrt.locking operates on the first byte
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(file_handle.fileno(), lock_type)
            yield file_handle
        finally:
            if sys.platform == "win32":
                try:
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)

    def _load(self) -> SharedMemoryState:
        """Load memory from disk with shared file lock."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, encoding="utf-8") as f:
                    with self._file_lock(f, exclusive=False):
                        data = json.load(f)
                        return SharedMemoryState(**data)
            except Exception as e:
                logger.warning(f"Error loading memory: {e}")
        return SharedMemoryState()

    def _save(self) -> None:
        """Save memory to disk with exclusive file lock."""
        self.state.last_updated = datetime.now().isoformat()
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                with self._file_lock(f, exclusive=True):
                    json.dump(self.state.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")

    def store(self, memory_type: str, data: dict, agent: str | None = None) -> None:
        """
        Store a memory entry.

        Args:
            memory_type: Type of memory (decision, context, learning, preference)
            data: Data to store
            agent: Optional agent name
        """
        entry = {"data": data, "agent": agent, "timestamp": datetime.now().isoformat()}

        if memory_type == "decision":
            self.state.decisions.append(entry)
            # Keep last 100 decisions
            if len(self.state.decisions) > 100:
                self.state.decisions = self.state.decisions[-100:]

        elif memory_type == "context":
            key = data.get("key", "default")
            self.state.context[key] = entry

        elif memory_type == "learning":
            self.state.learnings.append(entry)
            if len(self.state.learnings) > 50:
                self.state.learnings = self.state.learnings[-50:]

        elif memory_type == "preference":
            key = data.get("key", "default")
            self.state.user_preferences[key] = data.get("value")

        self._save()
        logger.debug(f"Stored {memory_type} memory")

    def retrieve(self, memory_type: str, query: str | None = None, limit: int = 10) -> list[dict]:
        """
        Retrieve memory entries.

        Args:
            memory_type: Type of memory to retrieve
            query: Optional search query (basic string matching)
            limit: Maximum entries to return
        """
        if memory_type == "decision":
            entries = self.state.decisions
        elif memory_type == "context":
            return list(self.state.context.values())[:limit]
        elif memory_type == "learning":
            entries = self.state.learnings
        elif memory_type == "preference":
            return [{"key": k, "value": v} for k, v in self.state.user_preferences.items()][:limit]
        else:
            return []

        if query:
            query_lower = query.lower()
            entries = [e for e in entries if query_lower in json.dumps(e).lower()]

        return entries[-limit:]

    def get_agent_state(self, agent: str) -> dict:
        """Get state for a specific agent."""
        return self.state.agent_states.get(agent, {})

    def set_agent_state(self, agent: str, state: dict) -> None:
        """Set state for a specific agent."""
        self.state.agent_states[agent] = state
        self._save()

    def clear(self) -> None:
        """Clear all memory."""
        self.state = SharedMemoryState()
        self._save()
        logger.info("Memory cleared")

    def export(self) -> dict:
        """Export all memory as dict."""
        return self.state.model_dump()

    def add_session_history(self, entry: dict, max_entries: int = 50) -> None:
        """Append an execution entry to session history."""
        self.state.session_history.append(entry)
        if len(self.state.session_history) > max_entries:
            self.state.session_history = self.state.session_history[-max_entries:]
        self._save()


# =============================================================================
# VECTOR MEMORY (ChromaDB-based)
# =============================================================================


class VectorMemory:
    """
    ChromaDB-based vector memory for semantic search.

    This enables agents to:
    - Store memories with automatic embeddings
    - Search by semantic similarity
    - Retrieve relevant context for any query
    """

    def __init__(
        self,
        collection_name: str = "antigravity_memory",
        persist_directory: Path | None = None,
        http_host: str | None = None,
        http_port: int = 8000,
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.http_host = http_host
        self.http_port = http_port
        self._client = None
        self._collection = None

    @property
    def client(self):
        """Lazy-load ChromaDB client.

        When http_host is set, uses ChromaHttpClient — a minimal stdlib-only
        REST client that avoids importing the chromadb package (which triggers
        pydantic v1 errors on Python 3.14+).

        Falls back to chromadb.PersistentClient / EphemeralClient when running
        locally without a ChromaDB server.
        """
        if self._client is None:
            if self.http_host:
                # Pure HTTP client — no chromadb package import needed.
                from core.chromadb_http_client import ChromaHttpClient

                self._client = ChromaHttpClient(  # type: ignore[assignment]  # chromadb HTTP: dep opcional
                    host=self.http_host,
                    port=self.http_port,
                )
                logger.info(
                    "ChromaDB HTTP client initialized at %s:%s", self.http_host, self.http_port
                )
            else:
                try:
                    import warnings

                    # Suppress pydantic v1 UserWarning that fires on Python 3.14+ when chromadb
                    # (which bundles pydantic v1 internals) is imported or its client is created.
                    # The warning is cosmetic — if chroma is truly broken the subsequent
                    # collection probe in MemoryBus.__init__ will catch the real AttributeError.
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", category=UserWarning)
                        import chromadb  # noqa: PLC0415

                        if self.persist_directory:
                            self._client = chromadb.PersistentClient(  # type: ignore[assignment]  # chromadb: dep opcional
                                path=str(self.persist_directory),
                            )
                        else:
                            self._client = chromadb.EphemeralClient()  # type: ignore[assignment]  # chromadb: dep opcional

                    logger.info("ChromaDB embedded client initialized")

                except ImportError:
                    logger.error("ChromaDB not installed. Run: pip install chromadb")
                    raise

        return self._client

    @property
    def collection(self):
        """Get or create the memory collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name, metadata={"description": "Antigravity agent memory"}
            )
        return self._collection

    def add(self, content: str, metadata: dict | None = None, memory_id: str | None = None) -> str:
        """
        Add a memory with automatic embedding.

        Args:
            content: Text content to store
            metadata: Optional metadata
            memory_id: Optional custom ID

        Returns:
            Memory ID
        """
        import uuid

        memory_id = memory_id or str(uuid.uuid4())
        metadata = metadata or {}
        metadata["timestamp"] = datetime.now().isoformat()

        self.collection.add(documents=[content], metadatas=[metadata], ids=[memory_id])

        logger.debug(f"Added memory: {memory_id}")
        return memory_id

    def search(self, query: str, limit: int = 5, filter_metadata: dict | None = None) -> list[dict]:
        """
        Search memories by semantic similarity.

        Args:
            query: Search query
            limit: Maximum results
            filter_metadata: Optional metadata filter

        Returns:
            List of matching memories with scores
        """
        try:
            results = self.collection.query(
                query_texts=[query], n_results=limit, where=filter_metadata
            )
        except Exception as e:
            logger.debug("VectorMemory.search failed (returning empty): %s", e)
            return []

        memories = []
        for i, doc in enumerate(results.get("documents", [[]])[0]):
            memories.append(
                {
                    "id": results["ids"][0][i] if results.get("ids") else None,
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                }
            )

        return memories

    def get(self, memory_id: str) -> dict | None:
        """Get a specific memory by ID."""
        try:
            result = self.collection.get(ids=[memory_id])
            if result and result.get("documents"):
                return {
                    "id": memory_id,
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0] if result.get("metadatas") else {},
                }
        except Exception as e:
            logger.warning(f"Error getting memory {memory_id}: {e}")
        return None

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        try:
            self.collection.delete(ids=[memory_id])
            logger.debug(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.warning(f"Error deleting memory {memory_id}: {e}")
            return False

    def count(self) -> int:
        """Get total number of memories."""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all memories."""
        # Recreate collection
        self.client.delete_collection(self.collection_name)
        self._collection = None
        logger.info("Vector memory cleared")


# =============================================================================
# CONVERSATION MEMORY
# =============================================================================


class ConversationMemory:
    """
    Memory specifically for tracking conversations and context.

    Maintains:
    - Short-term: Current conversation buffer
    - Long-term: Important facts extracted from conversations
    """

    def __init__(self, max_buffer_size: int = 20, vector_memory: VectorMemory | None = None):
        self.buffer: list[dict] = []
        self.max_buffer_size = max_buffer_size
        self.vector_memory = vector_memory
        self.facts: list[str] = []

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> None:
        """Add a message to the conversation buffer."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        self.buffer.append(message)

        # Trim buffer if too large
        if len(self.buffer) > self.max_buffer_size:
            # Save oldest to long-term before removing
            old_message = self.buffer.pop(0)
            if self.vector_memory:
                self.vector_memory.add(
                    content=f"{old_message['role']}: {old_message['content']}",
                    metadata={"type": "conversation", **old_message.get("metadata", {})},
                )

    def get_context(self, max_messages: int = 10) -> str:
        """Get recent conversation context as string."""
        recent = self.buffer[-max_messages:]
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent])

    def add_fact(self, fact: str) -> None:
        """Add an important fact to long-term memory."""
        self.facts.append(fact)
        if self.vector_memory:
            self.vector_memory.add(content=fact, metadata={"type": "fact"})

    def search_relevant(self, query: str, limit: int = 5) -> list[str]:
        """Search for relevant past context."""
        if self.vector_memory:
            results = self.vector_memory.search(query, limit=limit)
            return [r["content"] for r in results]
        return []

    def clear_buffer(self) -> None:
        """Clear the conversation buffer."""
        self.buffer = []


# =============================================================================
# MEMORY BUS - Unified Memory Interface
# =============================================================================


class MemoryBus:
    """
    Unified Memory Bus that connects all memory systems.

    Provides single interface to:
    - SharedMemory (structured JSON storage)
    - VectorMemory (semantic search with ChromaDB)
    - Cross-agent memory sharing

    All store operations auto-generate embeddings for semantic retrieval.
    """

    def __init__(
        self,
        memory_dir: Path,
        enable_vector: bool = True,
        collection_name: str = "antigravity_unified",
    ):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Initialize subsystems
        self.shared = SharedMemory(self.memory_dir)
        self.vector = None
        self._vector_enabled = enable_vector

        if enable_vector:
            try:
                # Prefer HTTP client to avoid pydantic v1 conflicts (Python 3.14+).
                # Falls back to local persistent client when no CHROMADB_HOST is set.
                chroma_host = os.environ.get("CHROMADB_HOST")
                chroma_port = int(os.environ.get("CHROMADB_PORT", "8000"))
                self.vector = VectorMemory(
                    collection_name=collection_name,
                    persist_directory=self.memory_dir / "vector" if not chroma_host else None,
                    http_host=chroma_host,
                    http_port=chroma_port,
                )
                # Verify connectivity (probe the collection to catch any init errors)
                try:
                    _ = self.vector.collection
                    logger.info("MemoryBus: VectorMemory enabled")
                except Exception as e:
                    logger.warning(
                        "MemoryBus: VectorMemory probe failed (%s) — disabling vector search", e
                    )
                    self.vector = None
                    self._vector_enabled = False
            except (ImportError, Exception) as e:
                logger.warning("MemoryBus: ChromaDB not available (%s) — vector search disabled", e)
                self._vector_enabled = False

        # Execution context per task
        self._task_contexts: dict[str, dict] = {}

        logger.info(f"MemoryBus initialized at {self.memory_dir}")

    def store(
        self,
        key: str,
        value: Any,
        memory_type: str = "context",
        agent: str | None = None,
        task_id: str | None = None,
        auto_embed: bool = True,
    ) -> str:
        """
        Store data in unified memory.

        Args:
            key: Unique key for the data
            value: Data to store (will be JSON serialized)
            memory_type: Type of memory (context, decision, learning, preference)
            agent: Agent that stored this data
            task_id: Optional task ID for scoping
            auto_embed: Auto-generate embedding for semantic search

        Returns:
            Memory ID
        """
        import uuid

        memory_id = str(uuid.uuid4())[:12]

        # Store in SharedMemory
        data = {"key": key, "value": value, "memory_id": memory_id, "task_id": task_id}
        self.shared.store(memory_type, data, agent)

        # Auto-embed for semantic search
        if auto_embed and self._vector_enabled and self.vector:
            content = self._serialize_for_embedding(key, value)
            try:
                self.vector.add(
                    content=content,
                    metadata={
                        "key": key,
                        "type": memory_type,
                        "agent": agent or "unknown",
                        "task_id": task_id or "none",
                        "memory_id": memory_id,
                    },
                    memory_id=memory_id,
                )
            except Exception as e:
                logger.debug("VectorMemory.add failed (will use SharedMemory only): %s", e)
                self._vector_enabled = False

        # Store in task context if applicable
        if task_id:
            if task_id not in self._task_contexts:
                self._task_contexts[task_id] = {}
            self._task_contexts[task_id][key] = {
                "value": value,
                "agent": agent,
                "memory_id": memory_id,
            }

        logger.debug(f"MemoryBus.store: {memory_type}/{key} by {agent}")
        return memory_id

    def retrieve(
        self, query: str, memory_type: str | None = None, limit: int = 10, semantic: bool = True
    ) -> list[dict]:
        """
        Retrieve memories by query.

        Args:
            query: Search query
            memory_type: Optional filter by type
            limit: Maximum results
            semantic: Use semantic search if available

        Returns:
            List of matching memories
        """
        results = []

        # Semantic search with VectorMemory
        if semantic and self._vector_enabled and self.vector:
            filter_metadata = {"type": memory_type} if memory_type else None
            vector_results = self.vector.search(
                query=query, limit=limit, filter_metadata=filter_metadata
            )
            results.extend(vector_results)

        # Fallback to SharedMemory search
        if not results and memory_type:
            shared_results = self.shared.retrieve(memory_type, query, limit)
            results.extend(
                [
                    {"content": json.dumps(r), "metadata": {"source": "shared"}}
                    for r in shared_results
                ]
            )

        return results[:limit]

    def get_agent_context(self, agent_name: str) -> dict:
        """Get all context relevant to an agent."""
        context = {
            "agent_state": self.shared.get_agent_state(agent_name),
            "recent_decisions": [],
            "learned_preferences": [],
        }

        # Get recent decisions
        decisions = self.shared.retrieve("decision", limit=10)
        context["recent_decisions"] = [d for d in decisions if d.get("agent") == agent_name][-5:]

        # Search for agent-specific context
        if self._vector_enabled and self.vector:
            agent_memories = self.vector.search(
                query=f"agent:{agent_name}", limit=10, filter_metadata={"agent": agent_name}
            )
            context["related_memories"] = agent_memories

        return context

    def get_task_context(self, task_id: str) -> dict:
        """Get all memory for a specific task execution."""
        return self._task_contexts.get(task_id, {})

    def share_with_agents(
        self, data: dict, from_agent: str, to_agents: list[str], task_id: str | None = None
    ) -> None:
        """
        Share data between agents.

        Args:
            data: Data to share
            from_agent: Source agent
            to_agents: Target agents
            task_id: Optional task context
        """
        share_key = f"shared_from_{from_agent}"

        for target_agent in to_agents:
            # Store in each target's context
            self.store(
                key=share_key,
                value={"from": from_agent, "data": data, "shared_at": datetime.now().isoformat()},
                memory_type="context",
                agent=target_agent,
                task_id=task_id,
            )

        logger.info(f"MemoryBus: {from_agent} shared data with {to_agents}")

    def clear_task_context(self, task_id: str) -> None:
        """Clear context for a completed task."""
        if task_id in self._task_contexts:
            del self._task_contexts[task_id]

    def _serialize_for_embedding(self, key: str, value: Any) -> str:
        """Serialize data for embedding generation."""
        if isinstance(value, str):
            return f"{key}: {value}"
        elif isinstance(value, dict):
            parts = [f"{key}:"]
            for k, v in value.items():
                parts.append(f"  {k}={v}")
            return "\n".join(parts)
        else:
            return f"{key}: {json.dumps(value, default=str)}"

    def export_all(self) -> dict:
        """Export complete memory state."""
        return {
            "shared": self.shared.export(),
            "vector_count": self.vector.count() if self.vector else 0,
            "active_tasks": list(self._task_contexts.keys()),
        }


# Singleton instance
_memory_bus: MemoryBus | None = None


def get_memory_bus(memory_dir: Path | None = None) -> MemoryBus:
    """Get the global MemoryBus instance."""
    global _memory_bus
    if _memory_bus is None:
        if memory_dir is None:
            memory_dir = Path(__file__).parent.parent / "data" / "memory"
        _memory_bus = MemoryBus(memory_dir)
    return _memory_bus


# =============================================================================
# CLI
# =============================================================================


def main():
    """Test memory systems."""
    import tempfile

    print("Testing SharedMemory...")
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = SharedMemory(Path(tmpdir))

        # Store some data
        memory.store("decision", {"task": "test", "agents": ["a1", "a2"]})
        memory.store("preference", {"key": "language", "value": "es"})

        # Retrieve
        decisions = memory.retrieve("decision")
        print(f"Decisions: {decisions}")

        prefs = memory.retrieve("preference")
        print(f"Preferences: {prefs}")

    print("\nTesting VectorMemory...")
    try:
        vmem = VectorMemory()

        # Add memories
        vmem.add("The user prefers Python over JavaScript", {"type": "preference"})
        vmem.add("Project uses React and Next.js for frontend", {"type": "context"})
        vmem.add("Database is PostgreSQL with Prisma ORM", {"type": "context"})

        # Search
        results = vmem.search("What frontend framework?", limit=2)
        print(f"Search results: {results}")

        print(f"Total memories: {vmem.count()}")

    except ImportError as e:
        print(f"ChromaDB not available: {e}")

    print("\nMemory tests complete!")


if __name__ == "__main__":
    main()
