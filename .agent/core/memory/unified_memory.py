# mypy: ignore-errors
#!/usr/bin/env python3
"""
Unified Memory Interface

Provides a single interface over all memory systems:
1. DualStreamMemory: Observations vs Reasoning (MAGMA-inspired)
2. TemporalKnowledgeGraph: Entities and relations with temporal tracking
3. SharedMemory: Simple key-value storage
4. VectorMemory: Semantic search (ChromaDB when available)

This facade simplifies memory operations for agents by:
- Auto-routing stores to the appropriate system
- Fusing queries across all systems
- Managing memory lifecycle
- Providing unified statistics
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.unified_memory")


class MemoryType(Enum):
    """Types of memory stores."""

    OBSERVATION = "observation"  # Facts from DualStream
    REASONING = "reasoning"  # Thoughts from DualStream
    ENTITY = "entity"  # Entities from TemporalGraph
    RELATION = "relation"  # Relations from TemporalGraph
    CONTEXT = "context"  # Shared context
    LEARNED = "learned"  # Learned patterns
    EPHEMERAL = "ephemeral"  # Temporary session data


@dataclass
class UnifiedMemoryResult:
    """Result from unified memory query."""

    content: str
    memory_type: MemoryType
    source_system: str
    score: float = 1.0
    metadata: dict = None
    timestamp: str = ""
    agent: str = ""

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class UnifiedMemory:
    """
    Unified interface over all memory systems.

    Usage:
        memory = UnifiedMemory(storage_path)

        # Store (auto-routed)
        await memory.store(
            content="File auth.py uses JWT",
            memory_type=MemoryType.OBSERVATION,
            agent="explorer"
        )

        # Query across all systems
        results = await memory.query("JWT authentication")

        # Get context for a task
        context = await memory.get_task_context("task_001")
    """

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".antigravity" / "unified_memory"

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize sub-systems lazily
        self._dual_stream = None
        self._temporal_graph = None
        self._shared_memory = None

        # Ephemeral memory (session-only)
        self._ephemeral: dict[str, Any] = {}

        logger.info(f"UnifiedMemory initialized at {self.storage_path}")

    @property
    def dual_stream(self):
        """Lazy load DualStreamMemory."""
        if self._dual_stream is None:
            try:
                # Try relative import first
                from .dual_stream import DualStreamMemory

                self._dual_stream = DualStreamMemory(self.storage_path / "dual_stream")
            except ImportError:
                try:
                    # Try absolute import using __file__
                    import importlib.util

                    module_dir = Path(__file__).parent
                    spec = importlib.util.spec_from_file_location(
                        "dual_stream", module_dir / "dual_stream.py"
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self._dual_stream = module.DualStreamMemory(
                            self.storage_path / "dual_stream"
                        )
                except Exception as e:
                    logger.warning(f"DualStreamMemory not available: {e}")
                    self._dual_stream = None
        return self._dual_stream

    @property
    def temporal_graph(self):
        """Lazy load TemporalKnowledgeGraph."""
        if self._temporal_graph is None:
            try:
                # Try relative import first
                from .temporal_graph import TemporalKnowledgeGraph

                self._temporal_graph = TemporalKnowledgeGraph(self.storage_path / "temporal_graph")
            except ImportError:
                try:
                    # Try absolute import using __file__
                    import importlib.util

                    module_dir = Path(__file__).parent
                    spec = importlib.util.spec_from_file_location(
                        "temporal_graph", module_dir / "temporal_graph.py"
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self._temporal_graph = module.TemporalKnowledgeGraph(
                            self.storage_path / "temporal_graph"
                        )
                except Exception as e:
                    logger.warning(f"TemporalKnowledgeGraph not available: {e}")
                    self._temporal_graph = None
        return self._temporal_graph

    @property
    def shared_memory(self):
        """Lazy load SharedMemory."""
        if self._shared_memory is None:
            try:
                # Try to import from parent core module
                import sys

                sys.path.insert(0, str(self.storage_path.parent.parent))
                from core.shared_memory import SharedMemory

                self._shared_memory = SharedMemory(self.storage_path)
            except Exception:
                try:
                    import importlib.util

                    core_dir = Path(__file__).resolve().parents[1]
                    spec = importlib.util.spec_from_file_location(
                        "core_memory_module", core_dir / "shared_memory.py"
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self._shared_memory = module.SharedMemory(self.storage_path)
                    else:
                        self._shared_memory = SimpleSharedMemory(self.storage_path)
                except Exception:
                    # Fallback to simple dict-based storage
                    self._shared_memory = SimpleSharedMemory(self.storage_path)
        return self._shared_memory

    # =========================================================================
    # Store Operations
    # =========================================================================

    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        agent: str = "",
        task_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Store content in the appropriate memory system.

        Returns the ID of the stored item.
        """
        if memory_type == MemoryType.OBSERVATION:
            if self.dual_stream:
                return await self.dual_stream.store_observation(
                    content=content, source_agent=agent, task_id=task_id, metadata=metadata
                )

        elif memory_type == MemoryType.REASONING:
            if self.dual_stream:
                return await self.dual_stream.store_reasoning(
                    content=content, source_agent=agent, task_id=task_id, metadata=metadata
                )

        elif memory_type == MemoryType.ENTITY:
            if self.temporal_graph:
                try:
                    from .temporal_graph import EntityType
                except ImportError:
                    import importlib.util

                    module_dir = Path(__file__).parent
                    spec = importlib.util.spec_from_file_location(
                        "temporal_graph", module_dir / "temporal_graph.py"
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        EntityType = module.EntityType

                entity_type = (
                    metadata.get("entity_type", EntityType.CONCEPT)
                    if metadata
                    else EntityType.CONCEPT
                )
                if isinstance(entity_type, str):
                    entity_type = EntityType(entity_type)
                return await self.temporal_graph.add_entity(
                    name=content,
                    entity_type=entity_type,
                    properties=metadata or {},
                    source_agent=agent,
                )

        elif memory_type == MemoryType.CONTEXT:
            key = (
                metadata.get("key", f"ctx_{datetime.now().timestamp()}")
                if metadata
                else f"ctx_{datetime.now().timestamp()}"
            )
            self.shared_memory.set(
                key,
                {
                    "content": content,
                    "agent": agent,
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return key

        elif memory_type == MemoryType.EPHEMERAL:
            key = (
                metadata.get("key", f"eph_{datetime.now().timestamp()}")
                if metadata
                else f"eph_{datetime.now().timestamp()}"
            )
            self._ephemeral[key] = {
                "content": content,
                "agent": agent,
                "timestamp": datetime.now().isoformat(),
            }
            return key

        # Fallback to shared memory
        key = f"{memory_type.value}_{datetime.now().timestamp()}"
        self.shared_memory.set(key, {"content": content, "type": memory_type.value})
        return key

    async def store_observation(self, content: str, agent: str, **kwargs) -> str:
        """Convenience method for storing observations."""
        return await self.store(content, MemoryType.OBSERVATION, agent, **kwargs)

    async def store_reasoning(self, content: str, agent: str, **kwargs) -> str:
        """Convenience method for storing reasoning."""
        return await self.store(content, MemoryType.REASONING, agent, **kwargs)

    async def store_context(self, key: str, value: Any, agent: str = "") -> str:
        """Convenience method for storing context."""
        return await self.store(
            content=str(value),
            memory_type=MemoryType.CONTEXT,
            agent=agent,
            metadata={"key": key, "value": value},
        )

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def query(
        self,
        query: str,
        memory_types: list[MemoryType] | None = None,
        limit: int = 20,
        agent_filter: str | None = None,
        task_filter: str | None = None,
        include_ephemeral: bool = True,
    ) -> list[UnifiedMemoryResult]:
        """
        Query across all memory systems.

        Returns unified results sorted by relevance.
        """
        results: list[UnifiedMemoryResult] = []

        # Default to all types
        if memory_types is None:
            memory_types = [MemoryType.OBSERVATION, MemoryType.REASONING, MemoryType.ENTITY]

        # Query DualStream
        if self.dual_stream and (
            MemoryType.OBSERVATION in memory_types or MemoryType.REASONING in memory_types
        ):
            try:
                fused = await self.dual_stream.fused_recall(
                    query=query, limit=limit, agent_filter=agent_filter, task_filter=task_filter
                )
                for item in fused:
                    results.append(
                        UnifiedMemoryResult(
                            content=item.entry.content,
                            memory_type=MemoryType.OBSERVATION
                            if item.source_stream.value == "observation"
                            else MemoryType.REASONING,
                            source_system="dual_stream",
                            score=item.score,
                            metadata=item.entry.metadata,
                            timestamp=item.entry.timestamp,
                            agent=item.entry.source_agent,
                        )
                    )
            except Exception as e:
                logger.error(f"DualStream query failed: {e}")

        # Query TemporalGraph
        if self.temporal_graph and MemoryType.ENTITY in memory_types:
            try:
                try:
                    from .temporal_graph import TemporalQuery
                except ImportError:
                    import importlib.util

                    module_dir = Path(__file__).parent
                    spec = importlib.util.spec_from_file_location(
                        "temporal_graph", module_dir / "temporal_graph.py"
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        TemporalQuery = module.TemporalQuery

                entities = await self.temporal_graph.query(
                    TemporalQuery(text_query=query, agent_filter=agent_filter, limit=limit)
                )
                for entity in entities:
                    results.append(
                        UnifiedMemoryResult(
                            content=f"{entity.name}: {entity.properties}",
                            memory_type=MemoryType.ENTITY,
                            source_system="temporal_graph",
                            score=entity.confidence,
                            metadata=entity.properties,
                            timestamp=entity.created_at,
                            agent=entity.source_agent,
                        )
                    )
            except Exception as e:
                logger.error(f"TemporalGraph query failed: {e}")

        # Query ephemeral
        if include_ephemeral and MemoryType.EPHEMERAL in memory_types:
            query_lower = query.lower()
            for _key, value in self._ephemeral.items():
                if query_lower in value.get("content", "").lower():
                    results.append(
                        UnifiedMemoryResult(
                            content=value["content"],
                            memory_type=MemoryType.EPHEMERAL,
                            source_system="ephemeral",
                            score=0.5,
                            timestamp=value.get("timestamp", ""),
                            agent=value.get("agent", ""),
                        )
                    )

        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    async def get_task_context(self, task_id: str, include_history: bool = True) -> dict:
        """Get all context related to a task."""
        context = {
            "task_id": task_id,
            "observations": [],
            "reasoning": [],
            "entities": [],
            "timeline": [],
        }

        # From DualStream
        if include_history and self.dual_stream:
            obs = await self.dual_stream.recall_observations(query=task_id, task_filter=task_id)
            context["observations"] = [o[0].content for o in obs]

            reason = await self.dual_stream.recall_reasoning(query=task_id, task_filter=task_id)
            context["reasoning"] = [r[0].content for r in reason]

        return context

    async def get_agent_memory(self, agent: str, limit: int = 50) -> list[UnifiedMemoryResult]:
        """Get all memories from a specific agent."""
        return await self.query(query="", agent_filter=agent, limit=limit)

    # =========================================================================
    # Entity Operations (delegated to TemporalGraph)
    # =========================================================================

    async def add_entity(
        self, name: str, entity_type: str, properties: dict | None = None, agent: str = ""
    ) -> str | None:
        """Add an entity to the knowledge graph."""
        if not self.temporal_graph:
            return None

        try:
            from .temporal_graph import EntityType
        except ImportError:
            import importlib.util

            module_dir = Path(__file__).parent
            spec = importlib.util.spec_from_file_location(
                "temporal_graph", module_dir / "temporal_graph.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                EntityType = module.EntityType
            else:
                return None

        try:
            et = EntityType(entity_type)
        except ValueError:
            et = EntityType.CONCEPT

        return await self.temporal_graph.add_entity(
            name=name, entity_type=et, properties=properties or {}, source_agent=agent
        )

    async def add_relation(
        self, source_name: str, target_name: str, relation_type: str, agent: str = ""
    ) -> str | None:
        """Add a relation between entities."""
        if not self.temporal_graph:
            return None

        try:
            from .temporal_graph import RelationType
        except ImportError:
            import importlib.util

            module_dir = Path(__file__).parent
            spec = importlib.util.spec_from_file_location(
                "temporal_graph", module_dir / "temporal_graph.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                RelationType = module.RelationType
            else:
                return None

        # Find entities
        source = await self.temporal_graph.find_entity(source_name)
        target = await self.temporal_graph.find_entity(target_name)

        if not source or not target:
            return None

        try:
            rt = RelationType(relation_type)
        except ValueError:
            rt = RelationType.DEPENDS_ON

        return await self.temporal_graph.add_relation(
            source_id=source.id, target_id=target.id, relation_type=rt, source_agent=agent
        )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def clear_ephemeral(self):
        """Clear all ephemeral memory."""
        self._ephemeral.clear()
        logger.info("Ephemeral memory cleared")

    async def clear_task_memory(self, task_id: str):
        """Clear all memory related to a task."""
        if self.dual_stream:
            await self.dual_stream.clear_task_memory(task_id)
        logger.info(f"Cleared memory for task {task_id}")

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """Get unified statistics."""
        stats = {
            "storage_path": str(self.storage_path),
            "systems": {},
            "ephemeral_items": len(self._ephemeral),
        }

        if self.dual_stream:
            stats["systems"]["dual_stream"] = self.dual_stream.get_stats()

        if self.temporal_graph:
            stats["systems"]["temporal_graph"] = self.temporal_graph.get_stats()

        return stats


class SimpleSharedMemory:
    """Simple fallback shared memory implementation."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.data_file = storage_path / "shared_memory.json"
        self._data: dict = {}
        self._load()

    def _load(self):
        if self.data_file.exists():
            import json

            self._data = json.loads(self.data_file.read_text(encoding="utf-8"))

    def _save(self):
        import json

        self.data_file.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._save()

    def delete(self, key: str):
        if key in self._data:
            del self._data[key]
            self._save()

    def export(self) -> dict:
        return self._data

    def add_session_history(self, entry: dict, max_entries: int = 50) -> None:
        history = self._data.get("session_history", [])
        if not isinstance(history, list):
            history = []
        history.append(entry)
        if len(history) > max_entries:
            history = history[-max_entries:]
        self.set("session_history", history)


# Singleton instance
_unified_memory_instance: UnifiedMemory | None = None


def get_unified_memory(storage_path: Path | None = None) -> UnifiedMemory:
    """Get or create the unified memory instance."""
    global _unified_memory_instance
    if _unified_memory_instance is None:
        _unified_memory_instance = UnifiedMemory(storage_path)
    return _unified_memory_instance


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate unified memory."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        memory = UnifiedMemory(Path(tmpdir))

        print("=== Unified Memory Demo ===")

        # Store observations
        await memory.store_observation(
            "Auth module uses JWT with HS256 algorithm", agent="explorer"
        )

        # Store reasoning
        await memory.store_reasoning(
            "Should upgrade to RS256 for better security", agent="security-auditor"
        )

        # Store context
        await memory.store_context(
            key="current_task",
            value={"name": "Security Audit", "priority": "high"},
            agent="planner",
        )

        # Add entity
        await memory.add_entity(
            name="JWTAuthenticator",
            entity_type="class",
            properties={"file": "auth.py"},
            agent="explorer",
        )

        # Query
        print("\n=== Query: 'JWT security' ===")
        results = await memory.query("JWT security")
        for r in results:
            print(f"  [{r.memory_type.value}] ({r.score:.2f}) {r.content[:60]}...")

        # Stats
        print("\n=== Memory Stats ===")
        stats = memory.get_stats()
        print(f"  Ephemeral items: {stats['ephemeral_items']}")
        for system, system_stats in stats.get("systems", {}).items():
            print(f"  {system}: {system_stats.get('total_entries', 'N/A')} entries")


if __name__ == "__main__":
    asyncio.run(demo())
