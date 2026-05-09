#!/usr/bin/env python3
"""
Knowledge Graph Module - Semantic memory with relationships.

This module provides a graph-based knowledge representation:
- Store concepts, decisions, patterns as nodes
- Capture relationships between knowledge
- Enable semantic search across knowledge
- Support reasoning over connected knowledge

Usage:
    from .agent.core.intelligence import KnowledgeGraph

    kg = KnowledgeGraph()

    # Add knowledge
    kg.add_node("pattern:repository", "Repository pattern for data access")
    kg.add_node("benefit:testability", "Improved testability through abstraction")
    kg.add_edge("pattern:repository", "benefit:testability", "enables")

    # Query knowledge
    related = kg.get_related("pattern:repository")
    path = kg.find_path("pattern:repository", "benefit:testability")
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.knowledge_graph")


class NodeType(Enum):
    """Types of knowledge nodes."""

    CONCEPT = "concept"
    DECISION = "decision"
    PATTERN = "pattern"
    LESSON = "lesson"
    ERROR = "error"
    SOLUTION = "solution"
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    ENTITY = "entity"
    ACTION = "action"


class EdgeType(Enum):
    """Types of relationships between nodes."""

    CAUSES = "causes"
    PREVENTS = "prevents"
    REQUIRES = "requires"
    ENABLES = "enables"
    CONFLICTS_WITH = "conflicts_with"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    INSTANCE_OF = "instance_of"
    SOLVES = "solves"
    DEPENDS_ON = "depends_on"
    LEARNED_FROM = "learned_from"
    LEADS_TO = "leads_to"


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph."""

    id: str
    node_type: NodeType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["node_type"] = self.node_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeNode":
        data["node_type"] = NodeType(data["node_type"])
        return cls(**data)


@dataclass
class KnowledgeEdge:
    """An edge (relationship) in the knowledge graph."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["edge_type"] = self.edge_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeEdge":
        data["edge_type"] = EdgeType(data["edge_type"])
        return cls(**data)


@dataclass
class QueryResult:
    """Result of a knowledge graph query."""

    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
    paths: list[list[str]]
    relevance_scores: dict[str, float]


class KnowledgeGraph:
    """
    Graph-based knowledge representation system.

    Stores knowledge as interconnected nodes with typed relationships,
    enabling semantic queries and reasoning over knowledge.
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        auto_save: bool = True,
    ):
        self.storage_path = storage_path or Path(".agent/memory/knowledge_graph")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.auto_save = auto_save

        # Graph data structures
        self.nodes: dict[str, KnowledgeNode] = {}
        self.edges: list[KnowledgeEdge] = []

        # Indices for fast lookup
        self._adjacency: dict[str, set[str]] = defaultdict(set)  # node_id -> connected node_ids
        self._reverse_adjacency: dict[str, set[str]] = defaultdict(
            set
        )  # node_id -> nodes pointing to it
        self._type_index: dict[NodeType, set[str]] = defaultdict(set)  # node_type -> node_ids
        self._tag_index: dict[str, set[str]] = defaultdict(set)  # tag -> node_ids
        self._edge_index: dict[tuple[str, str], list[KnowledgeEdge]] = defaultdict(list)

        # Load existing graph
        self._load()
        logger.info(
            f"KnowledgeGraph initialized with {len(self.nodes)} nodes, {len(self.edges)} edges"
        )

    def add_node(
        self,
        node_id: str,
        content: str,
        node_type: NodeType = NodeType.CONCEPT,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        source: str = "system",
    ) -> KnowledgeNode:
        """Add a knowledge node to the graph."""
        if node_id in self.nodes:
            # Update existing node
            node = self.nodes[node_id]
            node.content = content
            node.metadata.update(metadata or {})
            node.tags = list(set(node.tags + (tags or [])))
            node.confidence = confidence
            node.updated_at = datetime.now().isoformat()
            logger.debug(f"Updated node: {node_id}")
        else:
            # Create new node
            node = KnowledgeNode(
                id=node_id,
                node_type=node_type,
                content=content,
                metadata=metadata or {},
                tags=tags or [],
                confidence=confidence,
                source=source,
            )
            self.nodes[node_id] = node
            self._type_index[node_type].add(node_id)
            for tag in node.tags:
                self._tag_index[tag].add(node_id)
            logger.debug(f"Added node: {node_id}")

        if self.auto_save:
            self._save()

        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEdge | None:
        """Add a relationship between nodes."""
        if source_id not in self.nodes or target_id not in self.nodes:
            logger.warning(
                f"Cannot add edge: one or both nodes don't exist ({source_id}, {target_id})"
            )
            return None

        edge = KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata or {},
        )

        self.edges.append(edge)
        self._adjacency[source_id].add(target_id)
        self._reverse_adjacency[target_id].add(source_id)
        self._edge_index[(source_id, target_id)].append(edge)

        logger.debug(f"Added edge: {source_id} --{edge_type.value}--> {target_id}")

        if self.auto_save:
            self._save()

        return edge

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        """Get a node by ID."""
        node = self.nodes.get(node_id)
        if node:
            node.access_count += 1
        return node

    def get_related(
        self,
        node_id: str,
        edge_types: list[EdgeType] | None = None,
        max_depth: int = 1,
    ) -> QueryResult:
        """Get nodes related to a given node."""
        if node_id not in self.nodes:
            return QueryResult(nodes=[], edges=[], paths=[], relevance_scores={})

        visited = {node_id}
        related_nodes = []
        related_edges = []
        relevance_scores = {node_id: 1.0}

        # BFS traversal
        current_level = [node_id]
        for depth in range(max_depth):
            next_level = []
            for current_id in current_level:
                # Get outgoing edges
                for target_id in self._adjacency[current_id]:
                    edges = self._edge_index[(current_id, target_id)]
                    for edge in edges:
                        if edge_types is None or edge.edge_type in edge_types:
                            if target_id not in visited:
                                visited.add(target_id)
                                next_level.append(target_id)
                                related_nodes.append(self.nodes[target_id])
                                related_edges.append(edge)
                                # Relevance decays with depth
                                relevance_scores[target_id] = 1.0 / (depth + 2)

                # Get incoming edges
                for source_id in self._reverse_adjacency[current_id]:
                    edges = self._edge_index[(source_id, current_id)]
                    for edge in edges:
                        if edge_types is None or edge.edge_type in edge_types:
                            if source_id not in visited:
                                visited.add(source_id)
                                next_level.append(source_id)
                                related_nodes.append(self.nodes[source_id])
                                related_edges.append(edge)
                                relevance_scores[source_id] = 1.0 / (depth + 2)

            current_level = next_level

        return QueryResult(
            nodes=related_nodes,
            edges=related_edges,
            paths=[],
            relevance_scores=relevance_scores,
        )

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 5,
    ) -> list[str] | None:
        """Find shortest path between two nodes."""
        if source_id not in self.nodes or target_id not in self.nodes:
            return None

        if source_id == target_id:
            return [source_id]

        # BFS for shortest path
        visited = {source_id}
        queue = [(source_id, [source_id])]

        while queue:
            current_id, path = queue.pop(0)

            if len(path) > max_length:
                continue

            for neighbor_id in self._adjacency[current_id] | self._reverse_adjacency[current_id]:
                if neighbor_id == target_id:
                    return path + [neighbor_id]

                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))

        return None

    def search(
        self,
        query: str,
        node_types: list[NodeType] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[tuple[KnowledgeNode, float]]:
        """Search for nodes matching query."""
        results = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        candidates = set(self.nodes.keys())

        # Filter by type
        if node_types:
            type_nodes = set()
            for nt in node_types:
                type_nodes |= self._type_index[nt]
            candidates &= type_nodes

        # Filter by tags
        if tags:
            tag_nodes = set()
            for tag in tags:
                tag_nodes |= self._tag_index[tag]
            candidates &= tag_nodes

        # Score candidates
        for node_id in candidates:
            node = self.nodes[node_id]
            score = self._calculate_relevance(node, query_lower, query_terms)
            if score > 0:
                results.append((node, score))

        # Sort by score and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _calculate_relevance(
        self,
        node: KnowledgeNode,
        query: str,
        query_terms: set[str],
    ) -> float:
        """Calculate relevance score for a node."""
        score = 0.0

        content_lower = node.content.lower()

        # Exact phrase match
        if query in content_lower:
            score += 1.0

        # Term matches
        content_terms = set(content_lower.split())
        term_overlap = len(query_terms & content_terms)
        score += term_overlap * 0.3

        # ID match
        if query in node.id.lower():
            score += 0.5

        # Tag match
        for tag in node.tags:
            if query in tag.lower():
                score += 0.3

        # Boost by confidence and access frequency
        score *= node.confidence
        score *= 1 + min(node.access_count, 10) * 0.01

        return score

    def get_by_type(self, node_type: NodeType) -> list[KnowledgeNode]:
        """Get all nodes of a specific type."""
        return [self.nodes[nid] for nid in self._type_index[node_type]]

    def get_by_tag(self, tag: str) -> list[KnowledgeNode]:
        """Get all nodes with a specific tag."""
        return [self.nodes[nid] for nid in self._tag_index[tag]]

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its edges."""
        if node_id not in self.nodes:
            return False

        node = self.nodes[node_id]

        # Remove from type index
        self._type_index[node.node_type].discard(node_id)

        # Remove from tag index
        for tag in node.tags:
            self._tag_index[tag].discard(node_id)

        # Remove edges
        self.edges = [e for e in self.edges if e.source_id != node_id and e.target_id != node_id]

        # Update adjacency
        del self._adjacency[node_id]
        del self._reverse_adjacency[node_id]

        for adj_set in self._adjacency.values():
            adj_set.discard(node_id)
        for adj_set in self._reverse_adjacency.values():
            adj_set.discard(node_id)

        # Remove edge index entries
        keys_to_remove = [k for k in self._edge_index if node_id in k]
        for key in keys_to_remove:
            del self._edge_index[key]

        # Remove node
        del self.nodes[node_id]

        if self.auto_save:
            self._save()

        return True

    def merge_graphs(self, other: "KnowledgeGraph") -> int:
        """Merge another knowledge graph into this one."""
        added = 0

        for node_id, node in other.nodes.items():
            if node_id not in self.nodes:
                self.add_node(
                    node_id=node.id,
                    content=node.content,
                    node_type=node.node_type,
                    metadata=node.metadata,
                    tags=node.tags,
                    confidence=node.confidence,
                    source=node.source,
                )
                added += 1

        for edge in other.edges:
            self.add_edge(
                source_id=edge.source_id,
                target_id=edge.target_id,
                edge_type=edge.edge_type,
                weight=edge.weight,
                metadata=edge.metadata,
            )

        return added

    def export_subgraph(
        self,
        root_id: str,
        max_depth: int = 2,
    ) -> "KnowledgeGraph":
        """Export a subgraph starting from a root node."""
        subgraph = KnowledgeGraph(auto_save=False)

        result = self.get_related(root_id, max_depth=max_depth)

        # Add root node
        if root_id in self.nodes:
            root = self.nodes[root_id]
            subgraph.add_node(
                root.id,
                root.content,
                root.node_type,
                root.metadata,
                root.tags,
                root.confidence,
                root.source,
            )

        # Add related nodes
        for node in result.nodes:
            subgraph.add_node(
                node.id,
                node.content,
                node.node_type,
                node.metadata,
                node.tags,
                node.confidence,
                node.source,
            )

        # Add edges between nodes in subgraph
        for edge in result.edges:
            if edge.source_id in subgraph.nodes and edge.target_id in subgraph.nodes:
                subgraph.add_edge(
                    edge.source_id, edge.target_id, edge.edge_type, edge.weight, edge.metadata
                )

        return subgraph

    def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        type_counts = {nt.value: len(ids) for nt, ids in self._type_index.items()}
        edge_type_counts: dict[str, int] = defaultdict(int)
        for edge in self.edges:
            edge_type_counts[edge.edge_type.value] += 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "edge_types": dict(edge_type_counts),
            "avg_connections": sum(len(adj) for adj in self._adjacency.values())
            / max(len(self.nodes), 1),
            "total_tags": len(self._tag_index),
        }

    def _save(self) -> None:
        """Save graph to disk."""
        try:
            data = {
                "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
                "edges": [edge.to_dict() for edge in self.edges],
                "metadata": {
                    "saved_at": datetime.now().isoformat(),
                    "version": "1.0",
                },
            }
            filepath = self.storage_path / "graph.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save knowledge graph: {e}")

    def _load(self) -> None:
        """Load graph from disk."""
        filepath = self.storage_path / "graph.json"
        if not filepath.exists():
            return

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            # Load nodes
            for node_id, node_data in data.get("nodes", {}).items():
                node = KnowledgeNode.from_dict(node_data)
                self.nodes[node_id] = node
                self._type_index[node.node_type].add(node_id)
                for tag in node.tags:
                    self._tag_index[tag].add(node_id)

            # Load edges
            for edge_data in data.get("edges", []):
                edge = KnowledgeEdge.from_dict(edge_data)
                self.edges.append(edge)
                self._adjacency[edge.source_id].add(edge.target_id)
                self._reverse_adjacency[edge.target_id].add(edge.source_id)
                self._edge_index[(edge.source_id, edge.target_id)].append(edge)

            logger.info(f"Loaded knowledge graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
        except Exception as e:
            logger.error(f"Failed to load knowledge graph: {e}")


# Convenience functions
def create_knowledge_graph(path: Path | None = None) -> KnowledgeGraph:
    """Create a new knowledge graph."""
    return KnowledgeGraph(storage_path=path)


# Pre-built knowledge for common patterns
COMMON_PATTERNS = [
    (
        "pattern:repository",
        "Repository pattern - abstracts data access",
        NodeType.PATTERN,
        ["database", "architecture"],
    ),
    (
        "pattern:factory",
        "Factory pattern - object creation abstraction",
        NodeType.PATTERN,
        ["creation", "architecture"],
    ),
    (
        "pattern:observer",
        "Observer pattern - event-based communication",
        NodeType.PATTERN,
        ["events", "architecture"],
    ),
    (
        "pattern:singleton",
        "Singleton pattern - single instance guarantee",
        NodeType.PATTERN,
        ["instance", "architecture"],
    ),
    (
        "pattern:strategy",
        "Strategy pattern - interchangeable algorithms",
        NodeType.PATTERN,
        ["algorithms", "architecture"],
    ),
    (
        "pattern:mvc",
        "Model-View-Controller architectural pattern",
        NodeType.PATTERN,
        ["web", "architecture"],
    ),
    (
        "pattern:circuit-breaker",
        "Circuit breaker for fault tolerance",
        NodeType.PATTERN,
        ["resilience", "microservices"],
    ),
    (
        "lesson:validation-early",
        "Validate input at system boundaries",
        NodeType.LESSON,
        ["security", "best-practice"],
    ),
    (
        "lesson:fail-fast",
        "Fail fast and provide clear errors",
        NodeType.LESSON,
        ["error-handling", "best-practice"],
    ),
    (
        "lesson:dry",
        "Don't Repeat Yourself - avoid duplication",
        NodeType.LESSON,
        ["code-quality", "best-practice"],
    ),
]

COMMON_RELATIONSHIPS = [
    ("pattern:repository", "lesson:dry", EdgeType.ENABLES),
    ("pattern:circuit-breaker", "lesson:fail-fast", EdgeType.ENABLES),
    ("lesson:validation-early", "pattern:mvc", EdgeType.REQUIRES),
]


def initialize_with_common_knowledge(kg: KnowledgeGraph) -> None:
    """Initialize graph with common software engineering knowledge."""
    for node_id, content, node_type, tags in COMMON_PATTERNS:
        kg.add_node(node_id, content, node_type, tags=tags)

    for source, target, edge_type in COMMON_RELATIONSHIPS:
        kg.add_edge(source, target, edge_type)
