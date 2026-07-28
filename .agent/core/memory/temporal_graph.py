# mypy: ignore-errors
#!/usr/bin/env python3
"""
Temporal Knowledge Graph (Graphiti-inspired)

Implements a temporal knowledge graph that tracks:
1. Entities: Code files, functions, classes, concepts
2. Relations: Dependencies, calls, inherits, implements
3. Temporal validity: When knowledge was true/false
4. Episodes: Contextual groupings of related facts

Based on: Graphiti - Build Real-Time Knowledge Graphs for AI Agents
https://github.com/getzep/graphiti

Key Features:
- Bi-temporal tracking (valid_time, transaction_time)
- Automatic fact invalidation when contradicted
- Episode-based fact grouping
- Semantic search over entities and relations
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger("antigravity.temporal_graph")


class EntityType(Enum):
    """Types of entities in the knowledge graph."""

    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    MODULE = "module"
    CONCEPT = "concept"
    AGENT = "agent"
    TASK = "task"
    ERROR = "error"
    DECISION = "decision"
    PATTERN = "pattern"


class RelationType(Enum):
    """Types of relations between entities."""

    CONTAINS = "contains"  # file contains class
    IMPORTS = "imports"  # module imports module
    CALLS = "calls"  # function calls function
    INHERITS = "inherits"  # class inherits class
    IMPLEMENTS = "implements"  # class implements interface
    DEPENDS_ON = "depends_on"  # entity depends on entity
    CAUSED_BY = "caused_by"  # error caused by code
    RESOLVES = "resolves"  # fix resolves error
    DECIDED = "decided"  # agent decided something
    LEARNED = "learned"  # agent learned pattern
    SUPERSEDES = "supersedes"  # new fact supersedes old


@dataclass
class Entity:
    """An entity in the knowledge graph."""

    id: str
    name: str
    entity_type: EntityType
    properties: dict = field(default_factory=dict)

    # Temporal metadata
    created_at: str = ""
    valid_from: str = ""
    valid_to: str | None = None  # None = still valid

    # Provenance
    source_agent: str = ""
    source_episode: str | None = None
    confidence: float = 1.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.valid_from:
            self.valid_from = self.created_at

    def to_dict(self) -> dict:
        return {**asdict(self), "entity_type": self.entity_type.value}

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        data["entity_type"] = EntityType(data["entity_type"])
        return cls(**data)

    def is_valid(self) -> bool:
        return self.valid_to is None


@dataclass
class Relation:
    """A relation between two entities."""

    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: dict = field(default_factory=dict)

    # Temporal metadata
    created_at: str = ""
    valid_from: str = ""
    valid_to: str | None = None

    # Provenance
    source_agent: str = ""
    source_episode: str | None = None
    confidence: float = 1.0

    # For supersession tracking
    superseded_by: str | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.valid_from:
            self.valid_from = self.created_at

    def to_dict(self) -> dict:
        return {**asdict(self), "relation_type": self.relation_type.value}

    @classmethod
    def from_dict(cls, data: dict) -> "Relation":
        data["relation_type"] = RelationType(data["relation_type"])
        return cls(**data)

    def is_valid(self) -> bool:
        return self.valid_to is None


@dataclass
class Episode:
    """An episode groups related facts from a single context."""

    id: str
    name: str
    description: str
    agent: str
    task_id: str | None = None

    # Temporal
    started_at: str = ""
    ended_at: str | None = None

    # Content
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)

    # Summary
    summary: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Episode":
        return cls(**data)


@dataclass
class TemporalQuery:
    """Query parameters for temporal graph search."""

    entity_types: list[EntityType] | None = None
    relation_types: list[RelationType] | None = None
    valid_at: str | None = None  # Point-in-time query
    agent_filter: str | None = None
    episode_filter: str | None = None
    include_invalidated: bool = False
    text_query: str | None = None
    limit: int = 50


class TemporalKnowledgeGraph:
    """
    Graphiti-inspired temporal knowledge graph.

    Maintains a graph of entities and relations with full temporal tracking,
    allowing queries like "what did we know about X at time Y?"

    Usage:
        graph = TemporalKnowledgeGraph(storage_path)

        # Start an episode
        episode = graph.start_episode("Analyzing auth module", agent="explorer")

        # Add entities
        file_id = await graph.add_entity(
            name="auth.py",
            entity_type=EntityType.FILE,
            properties={"path": "src/auth.py", "lines": 150},
            episode=episode
        )

        # Add relations
        await graph.add_relation(
            source_id=file_id,
            target_id=class_id,
            relation_type=RelationType.CONTAINS,
            episode=episode
        )

        # Query at a point in time
        results = await graph.query(TemporalQuery(
            entity_types=[EntityType.FILE],
            valid_at="2024-01-15T10:00:00"
        ))
    """

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".antigravity" / "temporal_graph"

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.entities: dict[str, Entity] = {}
        self.relations: dict[str, Relation] = {}
        self.episodes: dict[str, Episode] = {}

        # Indexes for fast lookup
        self._entity_by_name: dict[str, set[str]] = {}
        self._entity_by_type: dict[EntityType, set[str]] = {}
        self._relations_by_source: dict[str, set[str]] = {}
        self._relations_by_target: dict[str, set[str]] = {}
        self._word_index: dict[str, set[str]] = {}  # For text search

        self._load()
        logger.info(f"TemporalKnowledgeGraph initialized at {self.storage_path}")

    def _load(self):
        """Load graph from disk."""
        entities_path = self.storage_path / "entities.json"
        relations_path = self.storage_path / "relations.json"
        episodes_path = self.storage_path / "episodes.json"

        if entities_path.exists():
            try:
                data = json.loads(entities_path.read_text(encoding="utf-8"))
                for entity_data in data.get("entities", []):
                    entity = Entity.from_dict(entity_data)
                    self.entities[entity.id] = entity
                    self._index_entity(entity)
            except Exception as e:
                logger.error(f"Failed to load entities: {e}")

        if relations_path.exists():
            try:
                data = json.loads(relations_path.read_text(encoding="utf-8"))
                for relation_data in data.get("relations", []):
                    relation = Relation.from_dict(relation_data)
                    self.relations[relation.id] = relation
                    self._index_relation(relation)
            except Exception as e:
                logger.error(f"Failed to load relations: {e}")

        if episodes_path.exists():
            try:
                data = json.loads(episodes_path.read_text(encoding="utf-8"))
                for episode_data in data.get("episodes", []):
                    episode = Episode.from_dict(episode_data)
                    self.episodes[episode.id] = episode
            except Exception as e:
                logger.error(f"Failed to load episodes: {e}")

        logger.debug(
            f"Loaded {len(self.entities)} entities, {len(self.relations)} relations, {len(self.episodes)} episodes"
        )

    def _save(self):
        """Save graph to disk."""
        # Save entities
        entities_data = {
            "last_updated": datetime.now().isoformat(),
            "count": len(self.entities),
            "entities": [e.to_dict() for e in self.entities.values()],
        }
        (self.storage_path / "entities.json").write_text(
            json.dumps(entities_data, indent=2),
            encoding="utf-8",
        )

        # Save relations
        relations_data = {
            "last_updated": datetime.now().isoformat(),
            "count": len(self.relations),
            "relations": [r.to_dict() for r in self.relations.values()],
        }
        (self.storage_path / "relations.json").write_text(
            json.dumps(relations_data, indent=2),
            encoding="utf-8",
        )

        # Save episodes
        episodes_data = {
            "last_updated": datetime.now().isoformat(),
            "count": len(self.episodes),
            "episodes": [e.to_dict() for e in self.episodes.values()],
        }
        (self.storage_path / "episodes.json").write_text(
            json.dumps(episodes_data, indent=2),
            encoding="utf-8",
        )

    def _generate_id(self, prefix: str, content: str) -> str:
        """Generate unique ID."""
        hash_input = f"{prefix}{content}{datetime.now().isoformat()}"
        return (
            f"{prefix}_{hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()[:10]}"
        )

    def _tokenize(self, text: str) -> set[str]:
        """Simple tokenization for text search."""
        words = re.findall(r"\b\w+\b", text.lower())
        return set(words)

    def _index_entity(self, entity: Entity):
        """Index entity for fast lookup."""
        # By name
        if entity.name not in self._entity_by_name:
            self._entity_by_name[entity.name] = set()
        self._entity_by_name[entity.name].add(entity.id)

        # By type
        if entity.entity_type not in self._entity_by_type:
            self._entity_by_type[entity.entity_type] = set()
        self._entity_by_type[entity.entity_type].add(entity.id)

        # Word index
        words = self._tokenize(entity.name)
        for _key, value in entity.properties.items():
            if isinstance(value, str):
                words.update(self._tokenize(value))

        for word in words:
            if word not in self._word_index:
                self._word_index[word] = set()
            self._word_index[word].add(entity.id)

    def _index_relation(self, relation: Relation):
        """Index relation for fast lookup."""
        # By source
        if relation.source_id not in self._relations_by_source:
            self._relations_by_source[relation.source_id] = set()
        self._relations_by_source[relation.source_id].add(relation.id)

        # By target
        if relation.target_id not in self._relations_by_target:
            self._relations_by_target[relation.target_id] = set()
        self._relations_by_target[relation.target_id].add(relation.id)

    # =========================================================================
    # Episode Management
    # =========================================================================

    def start_episode(
        self, name: str, agent: str, description: str = "", task_id: str | None = None
    ) -> Episode:
        """Start a new episode for grouping related facts."""
        episode_id = self._generate_id("ep", f"{name}{agent}")

        episode = Episode(
            id=episode_id, name=name, description=description, agent=agent, task_id=task_id
        )

        self.episodes[episode_id] = episode
        self._save()

        logger.info(f"Started episode: {name} (agent: {agent})")
        return episode

    def end_episode(self, episode: Episode, summary: str = "") -> Episode:
        """End an episode with optional summary."""
        episode.ended_at = datetime.now().isoformat()
        episode.summary = summary
        self._save()

        logger.info(f"Ended episode: {episode.name}")
        return episode

    # =========================================================================
    # Entity Operations
    # =========================================================================

    async def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        properties: dict | None = None,
        source_agent: str = "",
        episode: Episode | None = None,
        confidence: float = 1.0,
    ) -> str:
        """Add a new entity to the graph."""
        entity_id = self._generate_id("e", f"{name}{entity_type.value}")

        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            properties=properties or {},
            source_agent=source_agent,
            source_episode=episode.id if episode else None,
            confidence=confidence,
        )

        self.entities[entity_id] = entity
        self._index_entity(entity)

        if episode:
            episode.entity_ids.append(entity_id)

        self._save()
        logger.debug(f"Added entity: {name} ({entity_type.value})")
        return entity_id

    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    async def find_entity(
        self, name: str, entity_type: EntityType | None = None, valid_only: bool = True
    ) -> Entity | None:
        """Find entity by name and optional type."""
        if name not in self._entity_by_name:
            return None

        for entity_id in self._entity_by_name[name]:
            entity = self.entities[entity_id]
            if valid_only and not entity.is_valid():
                continue
            if entity_type and entity.entity_type != entity_type:
                continue
            return entity

        return None

    async def invalidate_entity(
        self, entity_id: str, reason: str = "", invalidated_by: str | None = None
    ):
        """Mark an entity as no longer valid."""
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            entity.valid_to = datetime.now().isoformat()
            entity.properties["invalidation_reason"] = reason
            if invalidated_by:
                entity.properties["invalidated_by"] = invalidated_by
            self._save()
            logger.info(f"Invalidated entity: {entity.name}")

    async def update_entity(
        self,
        entity_id: str,
        properties: dict,
        source_agent: str = "",
        episode: Episode | None = None,
    ) -> str | None:
        """
        Update an entity by creating a new version and invalidating the old.
        Returns the new entity ID.
        """
        old_entity = self.entities.get(entity_id)
        if not old_entity:
            return None

        # Invalidate old
        await self.invalidate_entity(
            entity_id, reason="superseded by update", invalidated_by=source_agent
        )

        # Create new with merged properties
        new_properties = {**old_entity.properties, **properties}
        new_id = await self.add_entity(
            name=old_entity.name,
            entity_type=old_entity.entity_type,
            properties=new_properties,
            source_agent=source_agent,
            episode=episode,
            confidence=old_entity.confidence,
        )

        # Track supersession
        new_entity = self.entities[new_id]
        new_entity.properties["supersedes"] = entity_id
        self._save()

        return new_id

    # =========================================================================
    # Relation Operations
    # =========================================================================

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        properties: dict | None = None,
        source_agent: str = "",
        episode: Episode | None = None,
        confidence: float = 1.0,
    ) -> str:
        """Add a relation between two entities."""
        relation_id = self._generate_id("r", f"{source_id}{target_id}{relation_type.value}")

        relation = Relation(
            id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=properties or {},
            source_agent=source_agent,
            source_episode=episode.id if episode else None,
            confidence=confidence,
        )

        self.relations[relation_id] = relation
        self._index_relation(relation)

        if episode:
            episode.relation_ids.append(relation_id)

        self._save()
        logger.debug(f"Added relation: {source_id} -{relation_type.value}-> {target_id}")
        return relation_id

    async def get_relations(
        self,
        entity_id: str,
        direction: str = "both",  # "outgoing", "incoming", "both"
        relation_type: RelationType | None = None,
        valid_only: bool = True,
    ) -> list[Relation]:
        """Get relations for an entity."""
        relation_ids: set[str] = set()

        if direction in ("outgoing", "both"):
            relation_ids.update(self._relations_by_source.get(entity_id, set()))

        if direction in ("incoming", "both"):
            relation_ids.update(self._relations_by_target.get(entity_id, set()))

        results = []
        for rid in relation_ids:
            relation = self.relations[rid]
            if valid_only and not relation.is_valid():
                continue
            if relation_type and relation.relation_type != relation_type:
                continue
            results.append(relation)

        return results

    async def invalidate_relation(self, relation_id: str, reason: str = ""):
        """Mark a relation as no longer valid."""
        if relation_id in self.relations:
            relation = self.relations[relation_id]
            relation.valid_to = datetime.now().isoformat()
            relation.properties["invalidation_reason"] = reason
            self._save()

    # =========================================================================
    # Querying
    # =========================================================================

    def _candidate_ids_by_type(self, q: "TemporalQuery") -> "set[str]":
        """Obtiene el conjunto inicial de candidatos filtrado por tipo de entidad.

        Args:
            q: Query temporal con el filtro opcional de entity_types.

        Returns:
            Conjunto de IDs candidatos (todos si no hay filtro de tipo).
        """
        if q.entity_types:
            candidate_ids: set[str] = set()
            for et in q.entity_types:
                candidate_ids.update(self._entity_by_type.get(et, set()))
            return candidate_ids
        return set(self.entities.keys())

    def _filter_ids_by_text(self, candidate_ids: "set[str]", text_query: str) -> "set[str]":
        """Filtra los candidatos por interseccion con el indice de palabras.

        Args:
            candidate_ids: Conjunto de IDs a filtrar (se modifica in-place).
            text_query: Texto a tokenizar y buscar en el indice de palabras.

        Returns:
            El conjunto de candidatos intersectado con los matches de texto.
        """
        query_words = self._tokenize(text_query)
        matching_ids: set[str] = set()
        for word in query_words:
            if word in self._word_index:
                if not matching_ids:
                    matching_ids = self._word_index[word].copy()
                else:
                    matching_ids.intersection_update(self._word_index[word])
        candidate_ids.intersection_update(matching_ids)
        return candidate_ids

    @staticmethod
    def _entity_matches_query(entity: "Entity", q: "TemporalQuery") -> bool:
        """Evalua si una entidad pasa todos los filtros temporales y de origen.

        Args:
            entity: Entidad candidata a evaluar.
            q: Query temporal con los filtros activos.

        Returns:
            True si la entidad satisface todos los filtros, False si descarta.
        """
        # Validity filter
        if not q.include_invalidated and not entity.is_valid():
            return False
        # Point-in-time filter
        if q.valid_at:
            if entity.valid_from > q.valid_at:
                return False
            if entity.valid_to and entity.valid_to < q.valid_at:
                return False
        # Agent filter
        if q.agent_filter and entity.source_agent != q.agent_filter:
            return False
        # Episode filter
        if q.episode_filter and entity.source_episode != q.episode_filter:
            return False
        return True

    async def query(self, q: TemporalQuery) -> list[Entity]:
        """Query the graph with temporal and type filters."""
        # Start with all entities or filter by type
        candidate_ids = self._candidate_ids_by_type(q)

        # Text search filter
        if q.text_query:
            candidate_ids = self._filter_ids_by_text(candidate_ids, q.text_query)

        # Apply filters
        results: list[Entity] = [
            entity
            for entity_id in candidate_ids
            if self._entity_matches_query((entity := self.entities[entity_id]), q)
        ]

        # Sort by creation time (newest first) and limit
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[: q.limit]

    async def query_at_time(
        self, point_in_time: str, entity_types: list[EntityType] | None = None
    ) -> list[Entity]:
        """Query what was known at a specific point in time."""
        return await self.query(
            TemporalQuery(
                entity_types=entity_types, valid_at=point_in_time, include_invalidated=False
            )
        )

    async def get_entity_history(self, name: str) -> list[Entity]:
        """Get all versions of an entity over time."""
        if name not in self._entity_by_name:
            return []

        entities = [self.entities[eid] for eid in self._entity_by_name[name]]
        entities.sort(key=lambda e: e.created_at)
        return entities

    async def find_path(
        self, from_entity_id: str, to_entity_id: str, max_depth: int = 5
    ) -> list[tuple[Entity, Relation]] | None:
        """Find a path between two entities (BFS)."""
        if from_entity_id == to_entity_id:
            return []

        visited = {from_entity_id}
        queue = [(from_entity_id, [])]

        while queue:
            current_id, path = queue.pop(0)

            if len(path) >= max_depth:
                continue

            # Get outgoing relations
            relations = await self.get_relations(current_id, direction="outgoing")

            for relation in relations:
                target_id = relation.target_id

                if target_id in visited:
                    continue

                target = self.entities.get(target_id)
                if not target:
                    continue

                new_path = path + [(target, relation)]

                if target_id == to_entity_id:
                    return new_path

                visited.add(target_id)
                queue.append((target_id, new_path))

        return None

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def extract_from_code(
        self, file_path: str, content: str, source_agent: str = "", episode: Episode | None = None
    ) -> dict[str, list[str]]:
        """
        Extract entities and relations from code content.
        Returns dict with 'entities' and 'relations' lists of IDs.
        """
        result = {"entities": [], "relations": []}

        # Add file entity
        file_id = await self.add_entity(
            name=Path(file_path).name,
            entity_type=EntityType.FILE,
            properties={"path": file_path, "lines": len(content.split("\n")), "size": len(content)},
            source_agent=source_agent,
            episode=episode,
        )
        result["entities"].append(file_id)

        # Extract classes
        class_pattern = r"class\s+(\w+)(?:\(([^)]*)\))?:"
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            bases = match.group(2)

            class_id = await self.add_entity(
                name=class_name,
                entity_type=EntityType.CLASS,
                properties={"bases": bases or "", "file": file_path},
                source_agent=source_agent,
                episode=episode,
            )
            result["entities"].append(class_id)

            # Relation: file contains class
            rel_id = await self.add_relation(
                source_id=file_id,
                target_id=class_id,
                relation_type=RelationType.CONTAINS,
                source_agent=source_agent,
                episode=episode,
            )
            result["relations"].append(rel_id)

            # Inheritance relations
            if bases:
                for base in bases.split(","):
                    base = base.strip()
                    if base:
                        base_entity = await self.find_entity(base, EntityType.CLASS)
                        if base_entity:
                            rel_id = await self.add_relation(
                                source_id=class_id,
                                target_id=base_entity.id,
                                relation_type=RelationType.INHERITS,
                                source_agent=source_agent,
                                episode=episode,
                            )
                            result["relations"].append(rel_id)

        # Extract functions
        func_pattern = r"(?:async\s+)?def\s+(\w+)\s*\([^)]*\)"
        for match in re.finditer(func_pattern, content):
            func_name = match.group(1)

            func_id = await self.add_entity(
                name=func_name,
                entity_type=EntityType.FUNCTION,
                properties={"file": file_path},
                source_agent=source_agent,
                episode=episode,
            )
            result["entities"].append(func_id)

            # Relation: file contains function
            rel_id = await self.add_relation(
                source_id=file_id,
                target_id=func_id,
                relation_type=RelationType.CONTAINS,
                source_agent=source_agent,
                episode=episode,
            )
            result["relations"].append(rel_id)

        # Extract imports
        import_pattern = r"(?:from\s+(\S+)\s+)?import\s+([^#\n]+)"
        for match in re.finditer(import_pattern, content):
            module = match.group(1) or match.group(2).split(",")[0].strip()

            module_entity = await self.find_entity(module, EntityType.MODULE)
            if not module_entity:
                module_id = await self.add_entity(
                    name=module,
                    entity_type=EntityType.MODULE,
                    properties={"external": True},
                    source_agent=source_agent,
                    episode=episode,
                )
                result["entities"].append(module_id)
            else:
                module_id = module_entity.id

            # Relation: file imports module
            rel_id = await self.add_relation(
                source_id=file_id,
                target_id=module_id,
                relation_type=RelationType.IMPORTS,
                source_agent=source_agent,
                episode=episode,
            )
            result["relations"].append(rel_id)

        self._save()
        return result

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """Get graph statistics."""
        valid_entities = sum(1 for e in self.entities.values() if e.is_valid())
        valid_relations = sum(1 for r in self.relations.values() if r.is_valid())

        type_counts = {}
        for entity in self.entities.values():
            t = entity.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        relation_type_counts = {}
        for relation in self.relations.values():
            t = relation.relation_type.value
            relation_type_counts[t] = relation_type_counts.get(t, 0) + 1

        return {
            "storage_path": str(self.storage_path),
            "total_entities": len(self.entities),
            "valid_entities": valid_entities,
            "total_relations": len(self.relations),
            "valid_relations": valid_relations,
            "total_episodes": len(self.episodes),
            "entity_types": type_counts,
            "relation_types": relation_type_counts,
        }


# Singleton instance
_temporal_graph_instance: TemporalKnowledgeGraph | None = None


def get_temporal_graph(storage_path: Path | None = None) -> TemporalKnowledgeGraph:
    """Get or create the temporal knowledge graph instance."""
    global _temporal_graph_instance
    if _temporal_graph_instance is None:
        _temporal_graph_instance = TemporalKnowledgeGraph(storage_path)
    return _temporal_graph_instance


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate temporal knowledge graph."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TemporalKnowledgeGraph(Path(tmpdir))

        # Start an episode
        episode = graph.start_episode(
            name="Analyzing auth module", agent="explorer", task_id="security_audit_001"
        )

        # Add entities
        file_id = await graph.add_entity(
            name="auth.py",
            entity_type=EntityType.FILE,
            properties={"path": "src/auth.py", "lines": 150},
            source_agent="explorer",
            episode=episode,
        )

        class_id = await graph.add_entity(
            name="JWTAuthenticator",
            entity_type=EntityType.CLASS,
            properties={"methods": ["validate", "refresh", "revoke"]},
            source_agent="explorer",
            episode=episode,
        )

        # Add relation
        await graph.add_relation(
            source_id=file_id,
            target_id=class_id,
            relation_type=RelationType.CONTAINS,
            source_agent="explorer",
            episode=episode,
        )

        # Add a decision
        await graph.add_entity(
            name="Use RS256 instead of HS256",
            entity_type=EntityType.DECISION,
            properties={"reason": "Better security for production"},
            source_agent="security-auditor",
            episode=episode,
        )

        # End episode
        graph.end_episode(episode, summary="Found JWT auth implementation, recommended RS256")

        # Query
        print("=== All FILE entities ===")
        files = await graph.query(TemporalQuery(entity_types=[EntityType.FILE]))
        for f in files:
            print(f"  {f.name}: {f.properties}")

        # Get relations
        print("\n=== Relations from auth.py ===")
        relations = await graph.get_relations(file_id, direction="outgoing")
        for r in relations:
            target = await graph.get_entity(r.target_id)
            print(f"  -{r.relation_type.value}-> {target.name if target else 'unknown'}")

        # Stats
        print("\n=== Graph Stats ===")
        stats = graph.get_stats()
        print(f"  Entities: {stats['total_entities']}")
        print(f"  Relations: {stats['total_relations']}")
        print(f"  Episodes: {stats['total_episodes']}")


if __name__ == "__main__":
    asyncio.run(demo())
