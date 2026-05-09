#!/usr/bin/env python3
"""
Time-Aware Memory - Memory that considers recency and temporal relevance.

This module provides time-aware memory that:
1. Weights memories by recency
2. Manages memory decay over time
3. Prioritizes temporally relevant information
4. Tracks memory freshness
5. Handles version history

Usage:
    from .agent.core.intelligence import TimeAwareMemory, remember

    memory = TimeAwareMemory()

    # Store with temporal context
    await memory.remember(
        key="api_design",
        value="REST with JWT auth",
        ttl_hours=24,
        importance=0.8
    )

    # Recall with time weighting
    result = await memory.recall("api_design")
    print(f"Value: {result.value}, Freshness: {result.freshness:.0%}")
"""

import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.time_aware_memory")


class DecayFunction(Enum):
    """Memory decay functions."""

    LINEAR = "linear"  # Linear decay
    EXPONENTIAL = "exponential"  # Exponential decay (default)
    STEP = "step"  # Step function (fresh then stale)
    NONE = "none"  # No decay


class MemoryPriority(Enum):
    """Memory priority levels."""

    CRITICAL = "critical"  # Never expires
    HIGH = "high"  # Slow decay
    NORMAL = "normal"  # Normal decay
    LOW = "low"  # Fast decay
    TEMPORARY = "temporary"  # Very fast decay


@dataclass
class TemporalMemory:
    """A memory with temporal metadata."""

    key: str
    value: Any
    importance: float  # 0.0 to 1.0
    priority: MemoryPriority
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_hours: int | None = None
    version: int = 1
    previous_values: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "importance": self.importance,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "ttl_hours": self.ttl_hours,
            "version": self.version,
            "tags": self.tags,
        }


@dataclass
class RecallResult:
    """Result of recalling a memory."""

    key: str
    value: Any
    found: bool
    freshness: float  # 0.0 (stale) to 1.0 (fresh)
    age: timedelta
    access_count: int
    version: int
    is_expired: bool
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "found": self.found,
            "freshness": self.freshness,
            "age_hours": self.age.total_seconds() / 3600,
            "access_count": self.access_count,
            "version": self.version,
            "is_expired": self.is_expired,
            "confidence": self.confidence,
        }


class DecayCalculator:
    """Calculates memory decay over time."""

    def __init__(self, default_function: DecayFunction = DecayFunction.EXPONENTIAL):
        self.default_function = default_function

        # Half-life in hours by priority
        self.half_life = {
            MemoryPriority.CRITICAL: float("inf"),
            MemoryPriority.HIGH: 168,  # 1 week
            MemoryPriority.NORMAL: 24,  # 1 day
            MemoryPriority.LOW: 6,  # 6 hours
            MemoryPriority.TEMPORARY: 1,  # 1 hour
        }

    def calculate_freshness(
        self,
        memory: TemporalMemory,
        function: DecayFunction | None = None,
    ) -> float:
        """
        Calculate memory freshness.

        Args:
            memory: The memory to evaluate
            function: Decay function to use

        Returns:
            Freshness score 0.0 to 1.0
        """
        function = function or self.default_function

        # Age in hours
        age_hours = (datetime.now() - memory.updated_at).total_seconds() / 3600

        # Get half-life for priority
        half_life = self.half_life.get(memory.priority, 24)

        if function == DecayFunction.NONE:
            return 1.0

        elif function == DecayFunction.LINEAR:
            # Linear decay to zero at 2x half-life
            return max(0.0, 1.0 - (age_hours / (2 * half_life)))

        elif function == DecayFunction.EXPONENTIAL:
            # Exponential decay: f = e^(-λt) where λ = ln(2)/half_life
            if half_life == float("inf"):
                return 1.0
            decay_constant = math.log(2) / half_life
            return math.exp(-decay_constant * age_hours)

        elif function == DecayFunction.STEP:
            # Fresh if within half-life, stale otherwise
            return 1.0 if age_hours <= half_life else 0.1

        return 0.5

    def is_expired(self, memory: TemporalMemory) -> bool:
        """Check if memory has expired."""
        if memory.priority == MemoryPriority.CRITICAL:
            return False

        if memory.ttl_hours is not None:
            age_hours = (datetime.now() - memory.updated_at).total_seconds() / 3600
            return age_hours > memory.ttl_hours

        # Default expiration at 10% freshness
        freshness = self.calculate_freshness(memory)
        return freshness < 0.1


class VersionTracker:
    """Tracks memory versions."""

    def create_version(
        self,
        memory: TemporalMemory,
        new_value: Any,
    ) -> TemporalMemory:
        """Create a new version of a memory."""
        # Store previous value
        memory.previous_values.append(
            {
                "value": memory.value,
                "version": memory.version,
                "timestamp": memory.updated_at.isoformat(),
            }
        )

        # Keep only last 10 versions
        memory.previous_values = memory.previous_values[-10:]

        # Update memory
        memory.value = new_value
        memory.version += 1
        memory.updated_at = datetime.now()

        return memory

    def get_version(
        self,
        memory: TemporalMemory,
        version: int,
    ) -> Any | None:
        """Get a specific version of a memory value."""
        if version == memory.version:
            return memory.value

        for prev in memory.previous_values:
            if prev.get("version") == version:
                return prev.get("value")

        return None


class TimeAwareMemory:
    """
    Memory system with temporal awareness.

    This class:
    1. Manages memories with time context
    2. Calculates freshness based on decay
    3. Handles TTL and expiration
    4. Tracks versions over time
    """

    def __init__(
        self,
        memory_dir: Path | None = None,
        decay_function: DecayFunction = DecayFunction.EXPONENTIAL,
    ):
        self.memory_dir = memory_dir or Path(".agent/memory/temporal")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.memories: dict[str, TemporalMemory] = {}
        self.decay_calculator = DecayCalculator(decay_function)
        self.version_tracker = VersionTracker()

        # Load existing memories
        self._load_memories()

        # Cleanup expired memories periodically
        self._cleanup_expired()

    def _load_memories(self) -> None:
        """Load saved memories."""
        memory_file = self.memory_dir / "temporal_memories.json"
        if memory_file.exists():
            try:
                with open(memory_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for key, mem_data in data.get("memories", {}).items():
                        memory = self._dict_to_memory(key, mem_data)
                        self.memories[key] = memory
                logger.info(f"Loaded {len(self.memories)} temporal memories")
            except Exception as e:
                logger.warning(f"Failed to load memories: {e}")

    def _save_memories(self) -> None:
        """Save memories to disk."""
        memory_file = self.memory_dir / "temporal_memories.json"
        data = {
            "memories": {k: m.to_dict() for k, m in self.memories.items()},
            "updated_at": datetime.now().isoformat(),
        }
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _dict_to_memory(self, key: str, data: dict[str, Any]) -> TemporalMemory:
        """Convert dict to TemporalMemory."""
        return TemporalMemory(
            key=key,
            value=data.get("value"),
            importance=data.get("importance", 0.5),
            priority=MemoryPriority(data.get("priority", "normal")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            last_accessed=datetime.fromisoformat(
                data.get("last_accessed", datetime.now().isoformat())
            ),
            access_count=data.get("access_count", 0),
            ttl_hours=data.get("ttl_hours"),
            version=data.get("version", 1),
            tags=data.get("tags", []),
        )

    def _cleanup_expired(self) -> None:
        """Remove expired memories."""
        expired_keys = [
            key for key, memory in self.memories.items() if self.decay_calculator.is_expired(memory)
        ]

        for key in expired_keys:
            del self.memories[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired memories")
            self._save_memories()

    async def remember(
        self,
        key: str,
        value: Any,
        importance: float = 0.5,
        priority: MemoryPriority = MemoryPriority.NORMAL,
        ttl_hours: int | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TemporalMemory:
        """
        Store a memory with temporal context.

        Args:
            key: Memory key
            value: Value to store
            importance: Importance score (0-1)
            priority: Memory priority
            ttl_hours: Time to live in hours
            tags: Tags for categorization
            metadata: Additional metadata

        Returns:
            Stored TemporalMemory
        """
        if key in self.memories:
            # Update existing memory
            memory = self.memories[key]
            self.version_tracker.create_version(memory, value)
            memory.importance = importance
            memory.priority = priority
            memory.ttl_hours = ttl_hours
            if tags:
                memory.tags = tags
            if metadata:
                memory.metadata.update(metadata)
        else:
            # Create new memory
            memory = TemporalMemory(
                key=key,
                value=value,
                importance=importance,
                priority=priority,
                ttl_hours=ttl_hours,
                tags=tags or [],
                metadata=metadata or {},
            )
            self.memories[key] = memory

        self._save_memories()
        logger.debug(f"Remembered: {key} (priority={priority.value})")

        return memory

    async def recall(
        self,
        key: str,
        min_freshness: float = 0.0,
    ) -> RecallResult:
        """
        Recall a memory with freshness context.

        Args:
            key: Memory key
            min_freshness: Minimum required freshness

        Returns:
            RecallResult with memory and temporal info
        """
        if key not in self.memories:
            return RecallResult(
                key=key,
                value=None,
                found=False,
                freshness=0.0,
                age=timedelta(0),
                access_count=0,
                version=0,
                is_expired=True,
                confidence=0.0,
            )

        memory = self.memories[key]

        # Calculate freshness
        freshness = self.decay_calculator.calculate_freshness(memory)

        # Check minimum freshness
        if freshness < min_freshness:
            return RecallResult(
                key=key,
                value=memory.value,
                found=True,
                freshness=freshness,
                age=datetime.now() - memory.updated_at,
                access_count=memory.access_count,
                version=memory.version,
                is_expired=True,
                confidence=freshness,
                metadata={"reason": "Below minimum freshness threshold"},
            )

        # Update access
        memory.last_accessed = datetime.now()
        memory.access_count += 1
        self._save_memories()

        # Check expiration
        is_expired = self.decay_calculator.is_expired(memory)

        # Calculate confidence
        confidence = freshness * memory.importance

        return RecallResult(
            key=key,
            value=memory.value,
            found=True,
            freshness=freshness,
            age=datetime.now() - memory.updated_at,
            access_count=memory.access_count,
            version=memory.version,
            is_expired=is_expired,
            confidence=confidence,
        )

    async def recall_version(
        self,
        key: str,
        version: int,
    ) -> Any | None:
        """Recall a specific version of a memory."""
        if key not in self.memories:
            return None
        return self.version_tracker.get_version(self.memories[key], version)

    async def forget(self, key: str) -> bool:
        """Forget a memory."""
        if key in self.memories:
            del self.memories[key]
            self._save_memories()
            return True
        return False

    async def refresh(self, key: str) -> bool:
        """Refresh a memory's timestamp."""
        if key in self.memories:
            self.memories[key].updated_at = datetime.now()
            self._save_memories()
            return True
        return False

    async def search_by_freshness(
        self,
        min_freshness: float = 0.5,
        limit: int = 10,
    ) -> list[RecallResult]:
        """Search for fresh memories."""
        results = []

        for key, memory in self.memories.items():
            freshness = self.decay_calculator.calculate_freshness(memory)
            if freshness >= min_freshness:
                result = await self.recall(key)
                results.append(result)

        # Sort by freshness
        results.sort(key=lambda r: r.freshness, reverse=True)

        return results[:limit]

    async def search_by_tag(
        self,
        tag: str,
        min_freshness: float = 0.0,
    ) -> list[RecallResult]:
        """Search memories by tag."""
        results = []

        for key, memory in self.memories.items():
            if tag in memory.tags:
                result = await self.recall(key, min_freshness)
                if result.found:
                    results.append(result)

        return results

    async def get_recent(
        self,
        hours: int = 24,
        limit: int = 10,
    ) -> list[TemporalMemory]:
        """Get recently updated memories."""
        cutoff = datetime.now() - timedelta(hours=hours)

        recent = [m for m in self.memories.values() if m.updated_at > cutoff]

        # Sort by update time
        recent.sort(key=lambda m: m.updated_at, reverse=True)

        return recent[:limit]

    async def get_frequently_accessed(
        self,
        limit: int = 10,
    ) -> list[TemporalMemory]:
        """Get frequently accessed memories."""
        sorted_memories = sorted(
            self.memories.values(),
            key=lambda m: m.access_count,
            reverse=True,
        )
        return sorted_memories[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        total = len(self.memories)
        by_priority: dict[str, int] = defaultdict(int)
        total_versions = 0
        fresh_count = 0

        for memory in self.memories.values():
            by_priority[memory.priority.value] += 1
            total_versions += memory.version
            if self.decay_calculator.calculate_freshness(memory) > 0.5:
                fresh_count += 1

        return {
            "total_memories": total,
            "fresh_memories": fresh_count,
            "stale_memories": total - fresh_count,
            "by_priority": dict(by_priority),
            "total_versions": total_versions,
            "avg_version": total_versions / total if total > 0 else 0,
        }

    def export_report(self) -> str:
        """Export memory report as markdown."""
        stats = self.get_statistics()

        lines = [
            "# Time-Aware Memory Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Statistics",
            "",
            f"- Total memories: {stats['total_memories']}",
            f"- Fresh (>50%): {stats['fresh_memories']}",
            f"- Stale (<50%): {stats['stale_memories']}",
            f"- Average version: {stats['avg_version']:.1f}",
            "",
            "## By Priority",
            "",
        ]

        for priority, count in stats["by_priority"].items():
            lines.append(f"- {priority}: {count}")

        lines.extend(["", "## Recent Memories", ""])

        # List recent
        recent = sorted(
            self.memories.values(),
            key=lambda m: m.updated_at,
            reverse=True,
        )[:10]

        for memory in recent:
            freshness = self.decay_calculator.calculate_freshness(memory)
            lines.append(
                f"- **{memory.key}**: {freshness:.0%} fresh, "
                f"v{memory.version}, accessed {memory.access_count}x"
            )

        return "\n".join(lines)


# Convenience function
async def remember(
    key: str,
    value: Any,
    ttl_hours: int | None = None,
) -> TemporalMemory:
    """Quick function to remember something."""
    memory = TimeAwareMemory()
    return await memory.remember(key, value, ttl_hours=ttl_hours)
