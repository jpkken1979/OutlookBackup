"""
Brain Graph — Motor de visualizacion del Brain Network.

Transforma nodos y relaciones del Brain en un grafo navegable
compatible con D3.js force-directed graph.

API:
    graph = BrainGraph(brain_dir)
    data = graph.get_graph()           # grafo completo
    data = graph.get_graph("nexus-...") # foco en un nodo
    neighbors = graph.get_neighbors("slug")
    by_tag = graph.search_by_tag("nexus")

v1.0.0 — 2026-05-09
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.brain import Brain, BrainNode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Models para Visualizacion D3
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """Un nodo listo para renderizar en D3."""

    id: str  # slug
    title: str
    type: str  # session | concept | adr | entity | decision | pattern
    area: str
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    importance: str = "normal"
    access_count: int = 0
    date: str = ""
    related_count: int = 0

    def to_d3_node(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "area": self.area,
            "tags": self.tags,
            "status": self.status,
            "importance": self.importance,
            "access_count": self.access_count,
            "date": self.date,
            "relatedCount": self.related_count,
            # D3 force defaults
            "x": 0,
            "y": 0,
            "vx": 0.0,
            "vy": 0.0,
            "fx": None,
            "fy": None,
        }


@dataclass
class GraphEdge:
    """Un edge (relacion) listo para renderizar en D3."""

    source: str  # slug origen
    target: str  # slug destino
    type: str = "related"  # related | same_area | same_tag

    def to_d3_link(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type,
        }


@dataclass
class GraphData:
    """Grafo completo con nodes y edges."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    center_slug: str | None = None
    total_nodes: int = 0
    total_edges: int = 0
    tags: list[str] = field(default_factory=list)  # tags unicos en el grafo
    areas: list[str] = field(default_factory=list)  # areas unicas

    def to_d3(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_d3_node() for n in self.nodes],
            "edges": [e.to_d3_link() for e in self.edges],
            "center": self.center_slug,
            "totalNodes": self.total_nodes,
            "totalEdges": self.total_edges,
            "tags": self.tags,
            "areas": self.areas,
        }


@dataclass
class NodeDetail:
    """Detalle completo de un nodo para el panel de informacion."""

    slug: str
    title: str
    type: str
    area: str
    date: str
    status: str
    importance: str
    tags: list[str]
    related: list[dict[str, str]]  # [{slug, title, type}]
    context: str
    decisions: str
    output: str
    pending: str
    access_count: int
    last_accessed: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "type": self.type,
            "area": self.area,
            "date": self.date,
            "status": self.status,
            "importance": self.importance,
            "tags": self.tags,
            "related": self.related,
            "context": self.context,
            "decisions": self.decisions,
            "output": self.output,
            "pending": self.pending,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }


# ---------------------------------------------------------------------------
# Brain Graph Engine
# ---------------------------------------------------------------------------

_TYPE_COLORS: dict[str, str] = {
    "session": "#6366f1",  # indigo
    "concept": "#22d3ee",  # cyan
    "adr": "#f59e0b",  # amber
    "entity": "#a78bfa",  # violet
    "decision": "#34d399",  # emerald
    "pattern": "#fb923c",  # orange
}

_TYPE_ICONS: dict[str, str] = {
    "session": "chat",
    "concept": "lightbulb",
    "adr": "scale",
    "entity": "box",
    "decision": "check-square",
    "pattern": "repeat",
}


class BrainGraph:
    """Motor de visualizacion del Brain Network.

    Transforma la base de conocimiento en un grafo navegable
    con nodos por tipo/area y links hacia relacionados.

    Uso:
        graph = BrainGraph(Path(".agent/brain"))
        data = graph.get_graph(center_slug="nexus-...", depth=2)
        detail = graph.get_node_detail("nexus-2026-04-11-...")
        neighbors = graph.get_neighbors("nexus-...")
    """

    def __init__(self, brain_dir: str | Path) -> None:
        """Inicializa el graph engine.

        Args:
            brain_dir: Directorio raiz del brain (ej: .agent/brain/).
        """
        self.brain = Brain(brain_dir, app_id="nexus-mother")

    # ----- Graph API -----

    def get_graph(
        self,
        center_slug: str | None = None,
        depth: int = 2,
    ) -> GraphData:
        """Retorna nodos y edges para visualizacion D3.

        Si center_slug es None, retorna el grafo completo.
        Si center_slug se provee, foca en ese nodo expandido depth niveles.

        Args:
            center_slug: Nodo central para focar (slug completo).
            depth: Profundidad de expansion a partir del centro.

        Returns:
            GraphData con nodos, edges y metadata para D3.
        """
        if center_slug:
            return self._build_focused_graph(center_slug, depth)

        return self._build_full_graph()

    def get_neighbors(self, slug: str) -> list[GraphNode]:
        """Nodos relacionados directos (1 salto).

        Args:
            slug: Slug del nodo central.

        Returns:
            Lista de GraphNode vecinos ordenados por relevancia.
        """
        try:
            center = self.brain.get_node(slug, track_access=False)
        except FileNotFoundError:
            return []

        neighbors: list[GraphNode] = []
        for rel_slug in center.related:
            try:
                node = self.brain.get_node(rel_slug, track_access=False)
                neighbors.append(self._node_to_graph_node(node))
            except FileNotFoundError:
                continue

        # Ordenar por importancia y access_count
        neighbors.sort(
            key=lambda n: (
                {"critical": 4, "high": 3, "normal": 2, "low": 1}.get(n.importance, 0),
                n.access_count,
            ),
            reverse=True,
        )
        return neighbors

    def search_by_tag(self, tag: str) -> list[GraphNode]:
        """Buscar todos los nodos con un tag.

        Args:
            tag: Tag a buscar (case-insensitive).

        Returns:
            Lista de GraphNode que tienen el tag.
        """
        nodes = self.brain.list_nodes(status="active", tag=tag)
        return [self._node_to_graph_node(n) for n in nodes]

    def get_node_detail(self, slug: str) -> NodeDetail | None:
        """Detalle completo de un nodo para el panel lateral.

        Args:
            slug: Slug del nodo.

        Returns:
            NodeDetail o None si no existe.
        """
        try:
            node = self.brain.get_node(slug, track_access=True)
        except FileNotFoundError:
            return None

        # Cargar titulos de los related
        related_details: list[dict[str, str]] = []
        for rel_slug in node.related:
            try:
                rel = self.brain.get_node(rel_slug, track_access=False)
                related_details.append(
                    {
                        "slug": rel.slug,
                        "title": rel.title,
                        "type": rel.type,
                    }
                )
            except FileNotFoundError:
                related_details.append({"slug": rel_slug, "title": rel_slug, "type": "unknown"})

        return NodeDetail(
            slug=node.slug,
            title=node.title,
            type=node.type,
            area=node.area,
            date=node.date,
            status=node.status,
            importance=node.importance,
            tags=node.tags,
            related=related_details,
            context=node.context,
            decisions=node.decisions,
            output=node.output,
            pending=node.pending,
            access_count=node.access_count,
            last_accessed=node.last_accessed,
        )

    def get_stats(self) -> dict[str, Any]:
        """Estadisticas del grafo para el header UI."""
        brain_stats = self.brain.stats()
        return {
            **brain_stats,
            "typeColors": _TYPE_COLORS,
            "typeIcons": _TYPE_ICONS,
        }

    # ----- Private Builders -----

    def _build_full_graph(self) -> GraphData:
        """Construye el grafo completo (todos los nodos activos)."""
        all_nodes = self.brain.list_nodes(status="active")
        graph_nodes = [self._node_to_graph_node(n) for n in all_nodes]

        # Construir edges desde related de cada nodo
        edges: list[GraphEdge] = []
        slugs_seen = {n.slug for n in all_nodes}

        for node in all_nodes:
            for rel_slug in node.related:
                if rel_slug in slugs_seen:
                    edges.append(
                        GraphEdge(
                            source=node.slug,
                            target=rel_slug,
                            type="related",
                        )
                    )

        # Extraer tags y areas unicos
        all_tags: set[str] = set()
        all_areas: set[str] = set()
        for node in all_nodes:
            all_tags.update(node.tags)
            all_areas.add(node.area)

        return GraphData(
            nodes=graph_nodes,
            edges=edges,
            total_nodes=len(graph_nodes),
            total_edges=len(edges),
            tags=sorted(all_tags),
            areas=sorted(all_areas),
        )

    @staticmethod
    def _collect_neighborhood_slugs(center_slug: str, neighborhood: dict) -> set[str]:
        """Recolecta los slugs del vecindario devuelto por el brain.

        Args:
            center_slug: Slug del nodo central.
            neighborhood: Resultado de Brain.get_neighborhood().

        Returns:
            Conjunto de slugs (incluye el central).
        """
        all_slugs = {center_slug}
        for nodes_list in neighborhood.get("by_depth", {}).values():
            for item in nodes_list:
                if "slug" in item:
                    all_slugs.add(item["slug"])
        return all_slugs

    def _build_focused_edges(
        self, all_slugs: set[str], slugs_loaded: dict[str, str]
    ) -> list[GraphEdge]:
        """Construye edges 'related' solo entre nodos presentes en el grafo.

        Args:
            all_slugs: Slugs a inspeccionar.
            slugs_loaded: Slugs efectivamente cargados (destinos válidos).

        Returns:
            Lista de GraphEdge entre nodos presentes.
        """
        edges: list[GraphEdge] = []
        for slug in all_slugs:
            try:
                node = self.brain.get_node(slug, track_access=False)
            except FileNotFoundError:
                continue
            for rel_slug in node.related:
                if rel_slug in slugs_loaded and rel_slug != slug:
                    edges.append(GraphEdge(source=slug, target=rel_slug, type="related"))
        return edges

    def _build_focused_graph(self, center_slug: str, depth: int) -> GraphData:
        """Construye un grafo focalizado en un nodo + profundidad."""
        # Traverse del brain para descubrir el vecindario
        neighborhood = self.brain.get_neighborhood(center_slug, depth=depth)
        all_slugs = self._collect_neighborhood_slugs(center_slug, neighborhood)

        # Cargar nodos
        graph_nodes: list[GraphNode] = []
        slugs_loaded: dict[str, str] = {}  # slug -> title (para resolver edges)

        for slug in all_slugs:
            try:
                node = self.brain.get_node(slug, track_access=False)
            except FileNotFoundError:
                continue
            graph_nodes.append(self._node_to_graph_node(node))
            slugs_loaded[slug] = node.title

        # Construir edges solo entre nodos presentes en el grafo
        edges = self._build_focused_edges(all_slugs, slugs_loaded)

        # Tags y areas del subgraph
        all_tags: set[str] = set()
        all_areas: set[str] = set()
        for gn in graph_nodes:
            all_tags.update(gn.tags)
            all_areas.add(gn.area)

        return GraphData(
            nodes=graph_nodes,
            edges=edges,
            center_slug=center_slug,
            total_nodes=len(graph_nodes),
            total_edges=len(edges),
            tags=sorted(all_tags),
            areas=sorted(all_areas),
        )

    def _node_to_graph_node(self, node: BrainNode) -> GraphNode:
        """Convierte un BrainNode a GraphNode para D3."""
        return GraphNode(
            id=node.slug,
            title=node.title,
            type=node.type,
            area=node.area,
            tags=node.tags,
            status=node.status,
            importance=node.importance,
            access_count=node.access_count,
            date=node.date,
            related_count=len(node.related),
        )


# ---------------------------------------------------------------------------
# Helpers para UI
# ---------------------------------------------------------------------------


def get_type_color(node_type: str) -> str:
    """Color D3-compatible segun tipo de nodo."""
    return _TYPE_COLORS.get(node_type, "#9ca3af")


def get_type_icon(node_type: str) -> str:
    """Icono lucide segun tipo de nodo."""
    return _TYPE_ICONS.get(node_type, "circle")
