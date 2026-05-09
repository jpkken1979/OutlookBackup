# mypy: ignore-errors
#!/usr/bin/env python3
"""
Collaborative Memory - Shared memory across agents.

This module provides collaborative memory that:
1. Shares knowledge between agents
2. Maintains project-wide context
3. Enables knowledge discovery
4. Tracks shared decisions
5. Supports memory merging

Usage:
    from .agent.core.intelligence import CollaborativeMemory, share_knowledge

    memory = CollaborativeMemory()

    # Share knowledge
    await memory.share(
        agent_name="architect",
        topic="auth-design",
        content="Using JWT with refresh tokens",
        metadata={"decision_date": "2024-01-15"}
    )

    # Query shared knowledge
    results = await memory.query("authentication approach")
"""

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.collaborative_memory")


class MemoryType(Enum):
    """Types of shared memory."""

    DECISION = "decision"  # A decision made
    CONTEXT = "context"  # Project context
    PATTERN = "pattern"  # Learned pattern
    CONSTRAINT = "constraint"  # Known constraint
    PREFERENCE = "preference"  # User/project preference
    ERROR = "error"  # Known error/issue
    SOLUTION = "solution"  # Working solution
    INSIGHT = "insight"  # General insight


class AccessLevel(Enum):
    """Memory access levels."""

    PUBLIC = "public"  # All agents can access
    DOMAIN = "domain"  # Domain-specific agents
    PRIVATE = "private"  # Single agent
    RESTRICTED = "restricted"  # Requires permission


@dataclass
class SharedMemory:
    """A piece of shared memory."""

    memory_id: str
    topic: str
    content: str
    memory_type: MemoryType
    access_level: AccessLevel
    created_by: str
    tags: list[str]
    relevance_score: float = 0.5
    references: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    useful_votes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "topic": self.topic,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "access_level": self.access_level.value,
            "created_by": self.created_by,
            "tags": self.tags,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
            "useful_votes": self.useful_votes,
        }


@dataclass
class QueryResult:
    """Result of a memory query."""

    memories: list[SharedMemory]
    total_found: int
    query: str
    search_time_ms: int
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memories": [m.to_dict() for m in self.memories],
            "total_found": self.total_found,
            "query": self.query,
            "search_time_ms": self.search_time_ms,
            "suggestions": self.suggestions,
        }


@dataclass
class MemoryMerge:
    """Result of merging memories."""

    merged_memory: SharedMemory
    source_memories: list[str]
    conflict_resolution: str
    merged_by: str


class MemoryIndex:
    """Index for efficient memory search."""

    def __init__(self):
        self.by_topic: dict[str, set[str]] = defaultdict(set)
        self.by_tag: dict[str, set[str]] = defaultdict(set)
        self.by_type: dict[MemoryType, set[str]] = defaultdict(set)
        self.by_agent: dict[str, set[str]] = defaultdict(set)

    def add(self, memory: SharedMemory) -> None:
        """Add memory to index."""
        # Index by topic words
        for word in memory.topic.lower().split():
            self.by_topic[word].add(memory.memory_id)

        # Index by tags
        for tag in memory.tags:
            self.by_tag[tag.lower()].add(memory.memory_id)

        # Index by type
        self.by_type[memory.memory_type].add(memory.memory_id)

        # Index by creator
        self.by_agent[memory.created_by].add(memory.memory_id)

    def remove(self, memory_id: str) -> None:
        """Remove memory from index."""
        for index in [self.by_topic, self.by_tag]:
            for key in list(index.keys()):
                index[key].discard(memory_id)

        for memory_type in self.by_type:
            self.by_type[memory_type].discard(memory_id)

        for agent in self.by_agent:
            self.by_agent[agent].discard(memory_id)

    def search(self, query: str) -> set[str]:
        """Search index for matching memory IDs."""
        query_words = query.lower().split()
        results: set[str] = set()

        for word in query_words:
            # Search topics
            if word in self.by_topic:
                results.update(self.by_topic[word])

            # Search tags
            if word in self.by_tag:
                results.update(self.by_tag[word])

        return results


class ConflictResolver:
    """Resolves conflicts between memories."""

    def resolve(
        self,
        memories: list[SharedMemory],
        strategy: str = "newest",
    ) -> SharedMemory:
        """
        Resolve conflicts between memories.

        Args:
            memories: Conflicting memories
            strategy: Resolution strategy (newest, voted, merge)

        Returns:
            Resolved memory
        """
        if not memories:
            raise ValueError("No memories to resolve")

        if len(memories) == 1:
            return memories[0]

        if strategy == "newest":
            return max(memories, key=lambda m: m.updated_at)

        elif strategy == "voted":
            return max(memories, key=lambda m: m.useful_votes)

        elif strategy == "merge":
            return self._merge_memories(memories)

        else:
            return memories[0]

    def _merge_memories(self, memories: list[SharedMemory]) -> SharedMemory:
        """Merge multiple memories into one."""
        # Use most recent as base
        base = max(memories, key=lambda m: m.updated_at)

        # Merge content
        contents = [m.content for m in memories]
        merged_content = "\n\n---\n\n".join(contents)

        # Merge tags
        all_tags = set()
        for m in memories:
            all_tags.update(m.tags)

        # Calculate combined relevance
        avg_relevance = sum(m.relevance_score for m in memories) / len(memories)

        return SharedMemory(
            memory_id=f"merged_{base.memory_id}",
            topic=base.topic,
            content=merged_content,
            memory_type=base.memory_type,
            access_level=base.access_level,
            created_by="system_merge",
            tags=list(all_tags),
            relevance_score=avg_relevance,
            references=[m.memory_id for m in memories],
        )


class CollaborativeMemory:
    """
    Shared memory system for agent collaboration.

    This class:
    1. Stores shared knowledge
    2. Enables cross-agent queries
    3. Manages access control
    4. Handles memory conflicts
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/collaborative")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.memories: dict[str, SharedMemory] = {}
        self.index = MemoryIndex()
        self.resolver = ConflictResolver()

        # Access tracking
        self.access_log: list[dict[str, Any]] = []

        # Load existing memories
        self._load_memories()

    def _load_memories(self) -> None:
        """Load saved memories."""
        memory_file = self.memory_dir / "shared_memories.json"
        if memory_file.exists():
            try:
                with open(memory_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for mem_data in data.get("memories", []):
                        memory = self._dict_to_memory(mem_data)
                        self.memories[memory.memory_id] = memory
                        self.index.add(memory)
                logger.info(f"Loaded {len(self.memories)} shared memories")
            except Exception as e:
                logger.warning(f"Failed to load memories: {e}")

    def _save_memories(self) -> None:
        """Save memories to disk."""
        memory_file = self.memory_dir / "shared_memories.json"
        data = {
            "memories": [m.to_dict() for m in self.memories.values()],
            "updated_at": datetime.now().isoformat(),
        }
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _dict_to_memory(self, data: dict[str, Any]) -> SharedMemory:
        """Convert dict to SharedMemory."""
        return SharedMemory(
            memory_id=data["memory_id"],
            topic=data["topic"],
            content=data["content"],
            memory_type=MemoryType(data.get("memory_type", "context")),
            access_level=AccessLevel(data.get("access_level", "public")),
            created_by=data["created_by"],
            tags=data.get("tags", []),
            relevance_score=data.get("relevance_score", 0.5),
            access_count=data.get("access_count", 0),
            useful_votes=data.get("useful_votes", 0),
        )

    async def share(
        self,
        agent_name: str,
        topic: str,
        content: str,
        memory_type: MemoryType = MemoryType.CONTEXT,
        access_level: AccessLevel = AccessLevel.PUBLIC,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SharedMemory:
        """
        Share knowledge with other agents.

        Args:
            agent_name: Agent sharing the knowledge
            topic: Topic/title of the knowledge
            content: Knowledge content
            memory_type: Type of memory
            access_level: Access level
            tags: Tags for indexing
            metadata: Additional metadata

        Returns:
            Created SharedMemory
        """
        memory_id = self._generate_id(topic, agent_name)

        memory = SharedMemory(
            memory_id=memory_id,
            topic=topic,
            content=content,
            memory_type=memory_type,
            access_level=access_level,
            created_by=agent_name,
            tags=tags or [],
            metadata=metadata or {},
        )

        # Check for existing memory on same topic
        existing = await self.query(topic, limit=1)
        if existing.memories:
            # Update relevance based on confirmation
            for existing_mem in existing.memories:
                if existing_mem.topic.lower() == topic.lower():
                    existing_mem.useful_votes += 1
                    existing_mem.updated_at = datetime.now()
                    logger.info(f"Confirmed existing memory: {existing_mem.memory_id}")

        self.memories[memory_id] = memory
        self.index.add(memory)
        self._save_memories()

        logger.info(f"Shared memory: {topic} by {agent_name}")
        return memory

    async def query(
        self,
        query: str,
        agent_name: str | None = None,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> QueryResult:
        """
        Query shared memories.

        Args:
            query: Search query
            agent_name: Agent making the query (for access control)
            memory_type: Filter by type
            limit: Maximum results

        Returns:
            QueryResult with matching memories
        """
        import time

        start_time = time.time()

        # Search index
        candidate_ids = self.index.search(query)

        # Get memories
        candidates = [self.memories[mid] for mid in candidate_ids if mid in self.memories]

        # Filter by type if specified
        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]

        # Filter by access level
        candidates = [m for m in candidates if self._can_access(m, agent_name)]

        # Score and sort
        scored = []
        query_words = set(query.lower().split())

        for memory in candidates:
            score = self._calculate_relevance(memory, query_words)
            scored.append((memory, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Get top results
        results = [m for m, s in scored[:limit]]

        # Update access counts
        for memory in results:
            memory.access_count += 1

        # Log access
        self.access_log.append(
            {
                "query": query,
                "agent": agent_name,
                "results": len(results),
                "timestamp": datetime.now().isoformat(),
            }
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Generate suggestions
        suggestions = self._generate_suggestions(query, results)

        return QueryResult(
            memories=results,
            total_found=len(scored),
            query=query,
            search_time_ms=elapsed_ms,
            suggestions=suggestions,
        )

    def _can_access(self, memory: SharedMemory, agent_name: str | None) -> bool:
        """Check if agent can access memory."""
        if memory.access_level == AccessLevel.PUBLIC:
            return True
        if memory.access_level == AccessLevel.PRIVATE:
            return memory.created_by == agent_name
        return True  # Default allow

    def _calculate_relevance(
        self,
        memory: SharedMemory,
        query_words: set[str],
    ) -> float:
        """Calculate relevance score."""
        score = memory.relevance_score

        # Topic match
        topic_words = set(memory.topic.lower().split())
        topic_overlap = len(query_words & topic_words)
        score += topic_overlap * 0.2

        # Content match
        content_words = set(memory.content.lower().split())
        content_overlap = len(query_words & content_words)
        score += min(content_overlap * 0.05, 0.3)

        # Tag match
        tag_words = {t.lower() for t in memory.tags}
        tag_overlap = len(query_words & tag_words)
        score += tag_overlap * 0.15

        # Recency bonus
        age_days = (datetime.now() - memory.updated_at).days
        if age_days < 1:
            score += 0.1
        elif age_days < 7:
            score += 0.05

        # Popularity bonus
        if memory.useful_votes > 0:
            score += min(memory.useful_votes * 0.02, 0.1)

        return min(score, 1.0)

    def _generate_suggestions(
        self,
        query: str,
        results: list[SharedMemory],
    ) -> list[str]:
        """Generate search suggestions."""
        suggestions = []

        if not results:
            suggestions.append("Try broader search terms")
            suggestions.append("Check if knowledge has been shared on this topic")
        else:
            # Suggest related tags
            all_tags = set()
            for m in results:
                all_tags.update(m.tags)

            if all_tags:
                suggestions.append(f"Related tags: {', '.join(list(all_tags)[:5])}")

            # Suggest related topics
            related_topics = {m.topic for m in results} - {query}
            if related_topics:
                suggestions.append(f"Related topics: {', '.join(list(related_topics)[:3])}")

        return suggestions[:3]

    def _generate_id(self, topic: str, agent: str) -> str:
        """Generate memory ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{topic}:{agent}:{timestamp}"
        short_hash = hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"mem_{short_hash}"

    async def vote_useful(self, memory_id: str, agent_name: str) -> None:
        """Mark a memory as useful."""
        if memory_id in self.memories:
            self.memories[memory_id].useful_votes += 1
            self._save_memories()

    async def update(
        self,
        memory_id: str,
        agent_name: str,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Update a shared memory."""
        if memory_id not in self.memories:
            return False

        memory = self.memories[memory_id]

        if content:
            memory.content = content
        if tags:
            memory.tags = tags

        memory.updated_at = datetime.now()
        self._save_memories()

        return True

    async def merge_memories(
        self,
        memory_ids: list[str],
        agent_name: str,
        strategy: str = "merge",
    ) -> MemoryMerge | None:
        """
        Merge multiple memories.

        Args:
            memory_ids: IDs of memories to merge
            agent_name: Agent performing merge
            strategy: Merge strategy

        Returns:
            MemoryMerge result
        """
        memories = [self.memories[mid] for mid in memory_ids if mid in self.memories]

        if len(memories) < 2:
            return None

        merged = self.resolver.resolve(memories, strategy)
        self.memories[merged.memory_id] = merged
        self.index.add(merged)

        # Keep old memories as references
        for mem_id in memory_ids:
            if mem_id in self.memories:
                self.memories[mem_id].references.append(merged.memory_id)

        self._save_memories()

        return MemoryMerge(
            merged_memory=merged,
            source_memories=memory_ids,
            conflict_resolution=strategy,
            merged_by=agent_name,
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        by_type = defaultdict(int)
        by_agent = defaultdict(int)
        total_votes = 0
        total_access = 0

        for memory in self.memories.values():
            by_type[memory.memory_type.value] += 1
            by_agent[memory.created_by] += 1
            total_votes += memory.useful_votes
            total_access += memory.access_count

        return {
            "total_memories": len(self.memories),
            "by_type": dict(by_type),
            "by_agent": dict(by_agent),
            "total_votes": total_votes,
            "total_access": total_access,
            "access_log_size": len(self.access_log),
        }

    def export_report(self) -> str:
        """Export memory report as markdown."""
        stats = self.get_statistics()

        lines = [
            "# Collaborative Memory Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Statistics",
            "",
            f"- Total memories: {stats['total_memories']}",
            f"- Total votes: {stats['total_votes']}",
            f"- Total accesses: {stats['total_access']}",
            "",
            "## By Type",
            "",
        ]

        for mem_type, count in stats["by_type"].items():
            lines.append(f"- {mem_type}: {count}")

        lines.extend(["", "## By Agent", ""])

        for agent, count in sorted(stats["by_agent"].items(), key=lambda x: x[1], reverse=True)[
            :10
        ]:
            lines.append(f"- {agent}: {count}")

        return "\n".join(lines)


# Convenience function
async def share_knowledge(
    agent_name: str,
    topic: str,
    content: str,
) -> SharedMemory:
    """Quick function to share knowledge."""
    memory = CollaborativeMemory()
    return await memory.share(agent_name, topic, content)
