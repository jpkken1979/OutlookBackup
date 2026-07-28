#!/usr/bin/env python3
"""
Dual-Stream Memory System (MAGMA-inspired)

Implements a dual-stream architecture that separates:
1. Observations: Factual data (file contents, API responses, scan results)
2. Reasoning: Thoughts, decisions, analyses, hypotheses

Based on: MAGMA: A Multi-Graph based Agentic Memory Architecture
https://arxiv.org/html/2601.03236v1

Key Benefits:
- Better retrieval relevance (observations vs reasoning have different patterns)
- Observations are more stable; reasoning evolves with context
- Cross-stream fusion for comprehensive recall
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger("antigravity.dual_stream")


class StreamType(Enum):
    """Types of memory streams."""

    OBSERVATION = "observation"  # Facts: file content, API responses, scan results
    REASONING = "reasoning"  # Thoughts: analyses, decisions, hypotheses


@dataclass
class MemoryEntry:
    """Entry in a memory stream."""

    id: str
    content: str
    stream_type: StreamType
    source_agent: str
    timestamp: str
    metadata: dict = field(default_factory=dict)
    relevance_score: float = 1.0

    # Temporal metadata
    valid_from: str = ""  # When this became true
    valid_to: str | None = None  # When this became false (None = still valid)

    # Linking
    related_entries: list[str] = field(default_factory=list)
    task_id: str | None = None

    def to_dict(self) -> dict:
        return {**asdict(self), "stream_type": self.stream_type.value}

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        data["stream_type"] = StreamType(data["stream_type"])
        return cls(**data)


@dataclass
class FusedResult:
    """Result from fused recall across streams."""

    entry: MemoryEntry
    score: float
    source_stream: StreamType
    fusion_reason: str = ""


class MemoryStream:
    """
    Single memory stream with vector-like semantic search.

    Uses simple TF-IDF-like scoring for retrieval without external dependencies.
    Can be upgraded to ChromaDB/Pinecone for production.
    """

    def __init__(self, stream_type: StreamType, storage_path: Path):
        self.stream_type = stream_type
        self.storage_path = storage_path / f"{stream_type.value}_stream.json"
        self.entries: dict[str, MemoryEntry] = {}
        self._word_index: dict[str, set[str]] = {}  # word -> entry_ids
        self._load()

    def _load(self):
        """Load stream from disk."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry.from_dict(entry_data)
                    self.entries[entry.id] = entry
                    self._index_entry(entry)
                logger.debug(
                    f"Loaded {len(self.entries)} entries from {self.stream_type.value} stream"
                )
            except Exception as e:
                logger.error(f"Failed to load stream: {e}")

    def _save(self):
        """Save stream to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "stream_type": self.stream_type.value,
            "last_updated": datetime.now().isoformat(),
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries.values()],
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _index_entry(self, entry: MemoryEntry):
        """Index entry for search."""
        words = self._tokenize(entry.content)
        for word in words:
            if word not in self._word_index:
                self._word_index[word] = set()
            self._word_index[word].add(entry.id)

    def _tokenize(self, text: str) -> set[str]:
        """Simple tokenization."""
        import re

        words = re.findall(r"\b\w+\b", text.lower())
        return set(words)

    def _generate_id(self, content: str, agent: str) -> str:
        """Generate unique entry ID."""
        hash_input = f"{content[:100]}{agent}{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()[:12]

    async def store(
        self,
        content: str,
        source_agent: str,
        metadata: dict | None = None,
        task_id: str | None = None,
        related_entries: list[str] | None = None,
    ) -> str:
        """Store entry in stream."""
        entry_id = self._generate_id(content, source_agent)
        now = datetime.now().isoformat()

        entry = MemoryEntry(
            id=entry_id,
            content=content,
            stream_type=self.stream_type,
            source_agent=source_agent,
            timestamp=now,
            valid_from=now,
            metadata=metadata or {},
            task_id=task_id,
            related_entries=related_entries or [],
        )

        self.entries[entry_id] = entry
        self._index_entry(entry)
        self._save()

        logger.debug(f"Stored entry {entry_id} in {self.stream_type.value} stream")
        return entry_id

    async def recall(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.1,
        agent_filter: str | None = None,
        task_filter: str | None = None,
    ) -> list[tuple[MemoryEntry, float]]:
        """Recall entries matching query."""
        query_words = self._tokenize(query)

        # Score entries by word overlap (simple TF-IDF-like)
        scores: dict[str, float] = {}
        for word in query_words:
            if word in self._word_index:
                for entry_id in self._word_index[word]:
                    if entry_id not in scores:
                        scores[entry_id] = 0
                    # IDF-like weighting (rare words score higher)
                    idf = 1.0 / (len(self._word_index[word]) + 1)
                    scores[entry_id] += idf

        # Normalize and filter
        results = []
        for entry_id, score in scores.items():
            entry = self.entries[entry_id]

            # Apply filters
            if agent_filter and entry.source_agent != agent_filter:
                continue
            if task_filter and entry.task_id != task_filter:
                continue
            if entry.valid_to is not None:  # Skip invalidated entries
                continue

            # Normalize score
            normalized_score = score / (len(query_words) + 1)
            if normalized_score >= min_score:
                results.append((entry, normalized_score))

        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def invalidate(self, entry_id: str, reason: str = ""):
        """Mark entry as no longer valid."""
        if entry_id in self.entries:
            self.entries[entry_id].valid_to = datetime.now().isoformat()
            self.entries[entry_id].metadata["invalidation_reason"] = reason
            self._save()

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Get most recent entries."""
        sorted_entries = sorted(self.entries.values(), key=lambda e: e.timestamp, reverse=True)
        return sorted_entries[:limit]

    def get_stats(self) -> dict:
        """Get stream statistics."""
        valid_count = sum(1 for e in self.entries.values() if e.valid_to is None)
        return {
            "stream_type": self.stream_type.value,
            "total_entries": len(self.entries),
            "valid_entries": valid_count,
            "invalidated_entries": len(self.entries) - valid_count,
            "unique_agents": len({e.source_agent for e in self.entries.values()}),
            "unique_tasks": len({e.task_id for e in self.entries.values() if e.task_id}),
        }


class DualStreamMemory:
    """
    MAGMA-inspired dual-stream memory system.

    Separates memory into two streams:
    - Observations: Factual data that agents observe
    - Reasoning: Thoughts, analyses, and decisions agents make

    Usage:
        memory = DualStreamMemory(storage_path)

        # Store observation (fact)
        await memory.store_observation(
            "File auth.py contains JWT validation logic",
            source_agent="explorer"
        )

        # Store reasoning (thought)
        await memory.store_reasoning(
            "JWT validation should use asymmetric keys for better security",
            source_agent="security-auditor"
        )

        # Fused recall
        results = await memory.fused_recall("JWT security")
    """

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".antigravity" / "dual_stream"

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.observations = MemoryStream(StreamType.OBSERVATION, self.storage_path)
        self.reasoning = MemoryStream(StreamType.REASONING, self.storage_path)

        logger.info(f"DualStreamMemory initialized at {self.storage_path}")

    async def store_observation(
        self,
        content: str,
        source_agent: str,
        metadata: dict | None = None,
        task_id: str | None = None,
    ) -> str:
        """
        Store factual observation.

        Examples:
        - "File src/auth.py contains 150 lines"
        - "API endpoint /users returns JSON"
        - "Test coverage is 75%"
        """
        return await self.observations.store(
            content=content, source_agent=source_agent, metadata=metadata, task_id=task_id
        )

    async def store_reasoning(
        self,
        content: str,
        source_agent: str,
        metadata: dict | None = None,
        task_id: str | None = None,
        related_observations: list[str] | None = None,
    ) -> str:
        """
        Store reasoning/thought.

        Examples:
        - "Based on the auth module, we should add rate limiting"
        - "The test coverage is low, prioritize testing auth flows"
        - "Decided to use async patterns for better performance"
        """
        return await self.reasoning.store(
            content=content,
            source_agent=source_agent,
            metadata=metadata,
            task_id=task_id,
            related_entries=related_observations,
        )

    async def fused_recall(
        self,
        query: str,
        limit: int = 10,
        observation_weight: float = 0.5,
        reasoning_weight: float = 0.5,
        agent_filter: str | None = None,
        task_filter: str | None = None,
    ) -> list[FusedResult]:
        """
        Query both streams and fuse results.

        Args:
            query: Search query
            limit: Max results
            observation_weight: Weight for observation results (0-1)
            reasoning_weight: Weight for reasoning results (0-1)
            agent_filter: Only include entries from this agent
            task_filter: Only include entries from this task

        Returns:
            Fused and ranked results from both streams
        """
        # Query both streams
        obs_results = await self.observations.recall(
            query, limit=limit * 2, agent_filter=agent_filter, task_filter=task_filter
        )
        reason_results = await self.reasoning.recall(
            query, limit=limit * 2, agent_filter=agent_filter, task_filter=task_filter
        )

        # Convert to fused results with weighted scores
        fused = []

        for entry, score in obs_results:
            fused.append(
                FusedResult(
                    entry=entry,
                    score=score * observation_weight,
                    source_stream=StreamType.OBSERVATION,
                    fusion_reason="Matched observation",
                )
            )

        for entry, score in reason_results:
            fused.append(
                FusedResult(
                    entry=entry,
                    score=score * reasoning_weight,
                    source_stream=StreamType.REASONING,
                    fusion_reason="Matched reasoning",
                )
            )

        # Sort by score and limit
        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[:limit]

    async def recall_observations(
        self, query: str, limit: int = 10, **kwargs
    ) -> list[tuple[MemoryEntry, float]]:
        """Recall only from observations stream."""
        return await self.observations.recall(query, limit, **kwargs)

    async def recall_reasoning(
        self, query: str, limit: int = 10, **kwargs
    ) -> list[tuple[MemoryEntry, float]]:
        """Recall only from reasoning stream."""
        return await self.reasoning.recall(query, limit, **kwargs)

    async def link_reasoning_to_observation(self, reasoning_id: str, observation_id: str):
        """Link a reasoning entry to its supporting observation."""
        if reasoning_id in self.reasoning.entries:
            entry = self.reasoning.entries[reasoning_id]
            if observation_id not in entry.related_entries:
                entry.related_entries.append(observation_id)
                self.reasoning._save()

    def get_recent_observations(self, limit: int = 10) -> list[MemoryEntry]:
        """Get recent observations."""
        return self.observations.get_recent(limit)

    def get_recent_reasoning(self, limit: int = 10) -> list[MemoryEntry]:
        """Get recent reasoning."""
        return self.reasoning.get_recent(limit)

    def get_stats(self) -> dict:
        """Get combined statistics."""
        obs_stats = self.observations.get_stats()
        reason_stats = self.reasoning.get_stats()

        return {
            "storage_path": str(self.storage_path),
            "observations": obs_stats,
            "reasoning": reason_stats,
            "total_entries": obs_stats["total_entries"] + reason_stats["total_entries"],
        }

    async def clear_task_memory(self, task_id: str):
        """Clear all memory related to a specific task."""
        for stream in [self.observations, self.reasoning]:
            to_remove = [eid for eid, e in stream.entries.items() if e.task_id == task_id]
            for eid in to_remove:
                del stream.entries[eid]
            stream._save()


# Singleton instance
_dual_stream_instance: DualStreamMemory | None = None


def get_dual_stream_memory(storage_path: Path | None = None) -> DualStreamMemory:
    """Get or create the dual-stream memory instance."""
    global _dual_stream_instance
    if _dual_stream_instance is None:
        _dual_stream_instance = DualStreamMemory(storage_path)
    return _dual_stream_instance


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate dual-stream memory."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        memory = DualStreamMemory(Path(tmpdir))

        # Store observations
        obs1 = await memory.store_observation(
            "File auth.py contains JWT validation using HS256 algorithm",
            source_agent="explorer",
            task_id="security_audit_001",
        )

        obs2 = await memory.store_observation(
            "No rate limiting found on /api/login endpoint",
            source_agent="security-auditor",
            task_id="security_audit_001",
        )

        # Store reasoning based on observations
        await memory.store_reasoning(
            "HS256 is vulnerable to brute force attacks; recommend RS256 for production",
            source_agent="security-auditor",
            task_id="security_audit_001",
            related_observations=[obs1],
        )

        await memory.store_reasoning(
            "Missing rate limiting is critical; attackers can brute force passwords",
            source_agent="security-auditor",
            task_id="security_audit_001",
            related_observations=[obs2],
        )

        # Fused recall
        print("=== Fused Recall: 'JWT security' ===")
        results = await memory.fused_recall("JWT security")
        for r in results:
            print(f"[{r.source_stream.value}] ({r.score:.2f}) {r.entry.content[:60]}...")

        # Stats
        print("\n=== Memory Stats ===")
        stats = memory.get_stats()
        print(f"Total entries: {stats['total_entries']}")
        print(f"Observations: {stats['observations']['total_entries']}")
        print(f"Reasoning: {stats['reasoning']['total_entries']}")


if __name__ == "__main__":
    asyncio.run(demo())
