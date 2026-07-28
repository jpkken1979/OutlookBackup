"""
Knowledge Hub - Collective Intelligence Repository

Central repository for accumulated knowledge across all agents:
- Pattern storage and retrieval
- Insight sharing
- Best practice accumulation
- Warning/anti-pattern tracking

Version: 1.0.0
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeType(Enum):
    """Types of knowledge entries."""

    PATTERN = "pattern"  # Reusable pattern/solution
    INSIGHT = "insight"  # Learned insight from execution
    WARNING = "warning"  # Things to avoid
    BEST_PRACTICE = "best_practice"  # Recommended approach
    DECISION = "decision"  # Architectural/design decision
    ERROR_SOLUTION = "error_solution"  # How to fix specific errors
    OPTIMIZATION = "optimization"  # Performance improvement
    SECURITY = "security"  # Security-related knowledge


class ValidationStatus(Enum):
    """Validation status of knowledge."""

    UNVALIDATED = "unvalidated"  # Not yet validated
    VALIDATED = "validated"  # Confirmed by multiple agents
    DISPUTED = "disputed"  # Conflicting opinions
    DEPRECATED = "deprecated"  # No longer applicable


@dataclass
class KnowledgeEntry:
    """A piece of learned knowledge."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    knowledge_type: KnowledgeType = KnowledgeType.INSIGHT
    title: str = ""
    content: str = ""
    source_agent: str = ""
    context: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    confidence: float = 0.5
    validations: int = 0
    contradictions: int = 0
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    related_entries: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "knowledge_type": self.knowledge_type.value,
            "title": self.title,
            "content": self.content,
            "source_agent": self.source_agent,
            "context": self.context,
            "tags": self.tags,
            "confidence": self.confidence,
            "validations": self.validations,
            "contradictions": self.contradictions,
            "validation_status": self.validation_status.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "related_entries": self.related_entries,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeEntry":
        entry = cls()
        entry.id = data.get("id", entry.id)
        entry.knowledge_type = KnowledgeType(data.get("knowledge_type", "insight"))
        entry.title = data.get("title", "")
        entry.content = data.get("content", "")
        entry.source_agent = data.get("source_agent", "")
        entry.context = data.get("context", {})
        entry.tags = data.get("tags", [])
        entry.confidence = data.get("confidence", 0.5)
        entry.validations = data.get("validations", 0)
        entry.contradictions = data.get("contradictions", 0)
        entry.validation_status = ValidationStatus(data.get("validation_status", "unvalidated"))
        entry.access_count = data.get("access_count", 0)
        entry.related_entries = data.get("related_entries", [])
        entry.metadata = data.get("metadata", {})
        return entry


@dataclass
class SynthesizedKnowledge:
    """Knowledge synthesized from multiple entries."""

    topic: str
    sources: list[str]  # Entry IDs
    synthesis: str
    confidence: float
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "sources": self.sources,
            "synthesis": self.synthesis,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }


class KnowledgeHub:
    """
    Collective intelligence repository.

    Central place where agents contribute and query knowledge,
    building a shared understanding over time.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path(".agent/data/knowledge")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, KnowledgeEntry] = {}
        self.tag_index: dict[str, list[str]] = {}  # tag -> entry_ids
        self.type_index: dict[str, list[str]] = {}  # type -> entry_ids
        self.agent_index: dict[str, list[str]] = {}  # agent -> entry_ids
        self._lock = asyncio.Lock()
        self._load_from_disk()

    def _load_from_disk(self):
        """Load knowledge from persistent storage."""
        knowledge_file = self.storage_path / "knowledge.json"
        if knowledge_file.exists():
            try:
                with open(knowledge_file, encoding="utf-8") as f:
                    data = json.load(f)
                for entry_data in data.get("entries", []):
                    entry = KnowledgeEntry.from_dict(entry_data)
                    self.entries[entry.id] = entry
                    self._index_entry(entry)
                logger.info(f"Loaded {len(self.entries)} knowledge entries")
            except Exception as e:
                logger.error(f"Error loading knowledge: {e}")

    def _save_to_disk(self):
        """Save knowledge to persistent storage."""
        knowledge_file = self.storage_path / "knowledge.json"
        try:
            data = {
                "entries": [e.to_dict() for e in self.entries.values()],
                "last_saved": datetime.now().isoformat(),
            }
            with open(knowledge_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving knowledge: {e}")

    def _index_entry(self, entry: KnowledgeEntry):
        """Index an entry for fast lookup."""
        # Tag index
        for tag in entry.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            if entry.id not in self.tag_index[tag]:
                self.tag_index[tag].append(entry.id)

        # Type index
        type_key = entry.knowledge_type.value
        if type_key not in self.type_index:
            self.type_index[type_key] = []
        if entry.id not in self.type_index[type_key]:
            self.type_index[type_key].append(entry.id)

        # Agent index
        if entry.source_agent:
            if entry.source_agent not in self.agent_index:
                self.agent_index[entry.source_agent] = []
            if entry.id not in self.agent_index[entry.source_agent]:
                self.agent_index[entry.source_agent].append(entry.id)

    async def contribute(
        self,
        knowledge_type: KnowledgeType,
        title: str,
        content: str,
        source_agent: str,
        tags: list[str] | None = None,
        context: dict | None = None,
        confidence: float = 0.5,
        metadata: dict | None = None,
    ) -> str:
        """
        Agent contributes knowledge to the hub.

        Args:
            knowledge_type: Type of knowledge
            title: Short descriptive title
            content: Detailed knowledge content
            source_agent: Agent contributing this
            tags: Searchable tags
            context: Situational context
            confidence: Agent's confidence in this knowledge
            metadata: Additional metadata

        Returns:
            Entry ID
        """
        entry = KnowledgeEntry(
            knowledge_type=knowledge_type,
            title=title,
            content=content,
            source_agent=source_agent,
            tags=tags or [],
            context=context or {},
            confidence=confidence,
            metadata=metadata or {},
        )

        async with self._lock:
            self.entries[entry.id] = entry
            self._index_entry(entry)
            self._save_to_disk()

        logger.info(f"Knowledge contributed by {source_agent}: {title}")
        return entry.id

    async def query(
        self,
        topic: str | None = None,
        knowledge_type: KnowledgeType | None = None,
        tags: list[str] | None = None,
        source_agent: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 10,
        include_deprecated: bool = False,
    ) -> list[KnowledgeEntry]:
        """
        Query relevant knowledge.

        Args:
            topic: Text to search in title/content
            knowledge_type: Filter by type
            tags: Filter by tags (any match)
            source_agent: Filter by source
            min_confidence: Minimum confidence threshold
            limit: Maximum results
            include_deprecated: Include deprecated entries

        Returns:
            List of matching entries
        """
        results = []

        for entry in self.entries.values():
            # Skip deprecated unless requested
            if not include_deprecated and entry.validation_status == ValidationStatus.DEPRECATED:
                continue

            # Confidence filter
            if entry.confidence < min_confidence:
                continue

            # Type filter
            if knowledge_type and entry.knowledge_type != knowledge_type:
                continue

            # Source filter
            if source_agent and entry.source_agent != source_agent:
                continue

            # Tag filter (any match)
            if tags and not any(t in entry.tags for t in tags):
                continue

            # Topic search (simple substring)
            if topic:
                topic_lower = topic.lower()
                if (
                    topic_lower not in entry.title.lower()
                    and topic_lower not in entry.content.lower()
                ):
                    continue

            results.append(entry)

        # Sort by confidence and access count
        results.sort(key=lambda e: (e.confidence, e.access_count), reverse=True)

        # Update access counts
        async with self._lock:
            for entry in results[:limit]:
                entry.last_accessed = datetime.now()
                entry.access_count += 1

        return results[:limit]

    async def validate(
        self, entry_id: str, agent: str, agrees: bool, comment: str | None = None
    ) -> bool:
        """
        Agent validates or disputes knowledge.

        Args:
            entry_id: Knowledge entry ID
            agent: Validating agent
            agrees: True if agrees, False if disputes
            comment: Optional comment

        Returns:
            Success status
        """
        if entry_id not in self.entries:
            return False

        async with self._lock:
            entry = self.entries[entry_id]

            if agrees:
                entry.validations += 1
            else:
                entry.contradictions += 1

            # Update validation status
            total_votes = entry.validations + entry.contradictions
            if total_votes >= 3:  # Minimum votes for status change
                agreement_ratio = entry.validations / total_votes
                if agreement_ratio >= 0.7:
                    entry.validation_status = ValidationStatus.VALIDATED
                    entry.confidence = min(1.0, entry.confidence + 0.1)
                elif agreement_ratio <= 0.3:
                    entry.validation_status = ValidationStatus.DISPUTED
                    entry.confidence = max(0.1, entry.confidence - 0.1)

            # Add comment to metadata
            if comment:
                if "validation_comments" not in entry.metadata:
                    entry.metadata["validation_comments"] = []
                entry.metadata["validation_comments"].append(
                    {
                        "agent": agent,
                        "agrees": agrees,
                        "comment": comment,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            self._save_to_disk()

        logger.info(f"Knowledge {entry_id} {'validated' if agrees else 'disputed'} by {agent}")
        return True

    async def synthesize(self, entry_ids: list[str], topic: str) -> SynthesizedKnowledge:
        """
        Synthesize multiple entries into coherent knowledge.

        Args:
            entry_ids: Entries to synthesize
            topic: What we're synthesizing about

        Returns:
            Synthesized knowledge
        """
        entries = [self.entries[eid] for eid in entry_ids if eid in self.entries]

        if not entries:
            return SynthesizedKnowledge(
                topic=topic, sources=[], synthesis="No entries found to synthesize", confidence=0.0
            )

        # Simple synthesis - combine contents
        # In production, would use LLM for intelligent synthesis
        combined_content = []
        total_confidence = 0.0

        for entry in entries:
            combined_content.append(f"[{entry.source_agent}] {entry.title}: {entry.content}")
            total_confidence += entry.confidence

        synthesis = "\n\n".join(combined_content)
        avg_confidence = total_confidence / len(entries)

        return SynthesizedKnowledge(
            topic=topic, sources=entry_ids, synthesis=synthesis, confidence=avg_confidence
        )

    async def get_related(self, entry_id: str, limit: int = 5) -> list[KnowledgeEntry]:
        """Get entries related to a given entry."""
        if entry_id not in self.entries:
            return []

        entry = self.entries[entry_id]

        # Find entries with overlapping tags
        related_ids = set()
        for tag in entry.tags:
            if tag in self.tag_index:
                related_ids.update(self.tag_index[tag])

        # Remove self
        related_ids.discard(entry_id)

        # Get entries and sort by relevance
        related = [self.entries[eid] for eid in related_ids if eid in self.entries]
        related.sort(key=lambda e: len(set(e.tags) & set(entry.tags)), reverse=True)

        return related[:limit]

    async def deprecate(self, entry_id: str, reason: str) -> bool:
        """Mark an entry as deprecated."""
        if entry_id not in self.entries:
            return False

        async with self._lock:
            entry = self.entries[entry_id]
            entry.validation_status = ValidationStatus.DEPRECATED
            entry.metadata["deprecation_reason"] = reason
            entry.metadata["deprecated_at"] = datetime.now().isoformat()
            self._save_to_disk()

        return True

    async def prune_old_unvalidated(self, days: int = 30) -> int:
        """Remove old unvalidated entries."""
        cutoff = datetime.now() - timedelta(days=days)
        to_remove = []

        for entry_id, entry in self.entries.items():
            if entry.validation_status == ValidationStatus.UNVALIDATED:
                if entry.created_at < cutoff and entry.access_count < 5:
                    to_remove.append(entry_id)

        async with self._lock:
            for entry_id in to_remove:
                del self.entries[entry_id]
            self._save_to_disk()

        logger.info(f"Pruned {len(to_remove)} old unvalidated entries")
        return len(to_remove)

    def get_stats(self) -> dict:
        """Get hub statistics."""
        type_counts = {}
        for type_key, ids in self.type_index.items():
            type_counts[type_key] = len(ids)

        status_counts = {s.value: 0 for s in ValidationStatus}
        for entry in self.entries.values():
            status_counts[entry.validation_status.value] += 1

        return {
            "total_entries": len(self.entries),
            "by_type": type_counts,
            "by_status": status_counts,
            "unique_tags": len(self.tag_index),
            "contributing_agents": len(self.agent_index),
        }


# Singleton instance
_hub_instance: KnowledgeHub | None = None


def get_knowledge_hub(storage_path: Path | None = None) -> KnowledgeHub:
    """Get the global KnowledgeHub instance."""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = KnowledgeHub(storage_path)
    return _hub_instance


# Example usage
if __name__ == "__main__":

    async def demo():
        hub = get_knowledge_hub()

        # Contribute knowledge
        entry_id = await hub.contribute(
            knowledge_type=KnowledgeType.BEST_PRACTICE,
            title="Use async/await for I/O operations",
            content="Always use async/await for I/O-bound operations to improve concurrency.",
            source_agent="backend-specialist",
            tags=["python", "async", "performance"],
            confidence=0.9,
        )
        print(f"Contributed entry: {entry_id}")

        # Query knowledge
        results = await hub.query(topic="async", min_confidence=0.5)
        print(f"Found {len(results)} entries about async")

        # Validate
        await hub.validate(entry_id, "architect", agrees=True)
        await hub.validate(entry_id, "performance-optimizer", agrees=True)

        # Get stats
        print(f"Hub stats: {hub.get_stats()}")

    asyncio.run(demo())
