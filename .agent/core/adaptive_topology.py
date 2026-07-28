"""
Adaptive Topology — Self-Organizing Agent Mesh.

Red de agentes que se recablea automáticamente:
  - Monitorea patrones de comunicación entre agentes
  - Crea "fast lanes" entre colaboradores frecuentes
  - Clusteriza agentes por afinidad de dominio
  - Detecta cuellos de botella y agentes sobrecargados
  - Rebalancea carga dinámicamente
  - Genera grafo de relaciones con pesos

Concepts:
  - Edge: conexión ponderada entre dos agentes
  - Cluster: grupo de agentes con afinidad alta
  - Bottleneck: agente con demasiadas conexiones entrantes
  - Fast Lane: ruta preferencial entre agentes frecuentes

Usage:
    topology = AdaptiveTopology(bus=bus)

    # Registrar interacción
    topology.record_interaction("explorer", "architect", domain="architecture")

    # Obtener vecinos preferidos
    neighbors = topology.get_preferred_neighbors("explorer")

    # Detectar clusters
    clusters = topology.detect_clusters()

    # Detectar cuellos de botella
    bottlenecks = topology.detect_bottlenecks()

    # Recomendación de agente
    best = topology.recommend_collaborator("explorer", domain="security")

    # Visualización del grafo
    graph = topology.get_graph()
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.adaptive_topology")

# ============================================================
# Constantes
# ============================================================
EDGE_DECAY_RATE = 0.02  # Peso decae 2% por día sin interacción
MIN_EDGE_WEIGHT = 0.01  # Peso mínimo para mantener un edge
MAX_EDGES_PER_AGENT = 50  # Máximo de conexiones por agente
BOTTLENECK_THRESHOLD = 0.7  # Ratio de carga para ser bottleneck
CLUSTER_AFFINITY_MIN = 0.3  # Afinidad mínima para pertenecer a un cluster
FAST_LANE_THRESHOLD = 5  # Mínimo de interacciones para fast lane
MAX_INTERACTION_HISTORY = 1000


# ============================================================
# Modelos
# ============================================================
@dataclass
class Edge:
    """Conexión ponderada entre dos agentes."""

    edge_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = ""
    target: str = ""
    weight: float = 0.0
    interactions: int = 0
    domains: dict[str, int] = field(default_factory=dict)
    last_interaction: float = field(default_factory=time.time)
    is_fast_lane: bool = False

    @property
    def primary_domain(self) -> str:
        """Dominio principal de la relación."""
        if not self.domains:
            return "general"
        return max(self.domains, key=lambda d: self.domains[d])

    @property
    def strength(self) -> str:
        """Clasificación de fuerza."""
        if self.weight >= 5.0:
            return "strong"
        elif self.weight >= 2.0:
            return "moderate"
        elif self.weight >= 0.5:
            return "weak"
        return "minimal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "weight": round(self.weight, 3),
            "strength": self.strength,
            "interactions": self.interactions,
            "domains": self.domains,
            "primary_domain": self.primary_domain,
            "is_fast_lane": self.is_fast_lane,
            "last_interaction": self.last_interaction,
            "days_since": round((time.time() - self.last_interaction) / 86400, 1),
        }


@dataclass
class AgentNode:
    """Nodo del agente en la topología."""

    agent: str
    edges: dict[str, Edge] = field(default_factory=dict)  # target → Edge
    total_interactions: int = 0
    load: float = 0.0  # [0, 1]
    cluster_id: str | None = None
    joined_at: float = field(default_factory=time.time)

    @property
    def degree(self) -> int:
        """Número de conexiones."""
        return len(self.edges)

    @property
    def is_bottleneck(self) -> bool:
        """Es cuello de botella si tiene alta carga y muchas conexiones."""
        return self.load > BOTTLENECK_THRESHOLD and self.degree > 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "degree": self.degree,
            "total_interactions": self.total_interactions,
            "load": round(self.load, 3),
            "is_bottleneck": self.is_bottleneck,
            "cluster_id": self.cluster_id,
            "fast_lanes": [t for t, e in self.edges.items() if e.is_fast_lane],
            "top_collaborators": sorted(
                [(t, e.weight) for t, e in self.edges.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }


@dataclass
class Cluster:
    """Grupo de agentes con afinidad."""

    cluster_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    members: list[str] = field(default_factory=list)
    primary_domain: str = "general"
    cohesion: float = 0.0  # Promedio de peso entre miembros

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "members": self.members,
            "size": len(self.members),
            "primary_domain": self.primary_domain,
            "cohesion": round(self.cohesion, 3),
        }


@dataclass
class InteractionRecord:
    """Registro de una interacción."""

    source: str
    target: str
    domain: str = "general"
    success: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "domain": self.domain,
            "success": self.success,
            "timestamp": self.timestamp,
        }


# ============================================================
# Adaptive Topology
# ============================================================
class AdaptiveTopology:
    """
    Red auto-organizativa de agentes.
    Monitorea interacciones y recablea la topología.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._nodes: dict[str, AgentNode] = {}
        self._clusters: list[Cluster] = []
        self._interaction_history: list[InteractionRecord] = []

        # Métricas
        self._metrics = {
            "interactions_recorded": 0,
            "fast_lanes_created": 0,
            "clusters_detected": 0,
            "bottlenecks_detected": 0,
            "edges_pruned": 0,
        }

    # --------------------------------------------------------
    # Record Interaction
    # --------------------------------------------------------
    def record_interaction(
        self,
        source: str,
        target: str,
        domain: str = "general",
        success: bool = True,
        weight_boost: float = 1.0,
    ) -> Edge:
        """
        Registra una interacción entre dos agentes.

        Args:
            source: Agente que inicia.
            target: Agente destino.
            domain: Dominio de la interacción.
            success: Si fue exitosa.
            weight_boost: Multiplicador de peso.

        Returns:
            El Edge actualizado.
        """
        source_node = self._get_or_create_node(source)
        self._get_or_create_node(target)  # Asegurar que existe

        # Obtener o crear edge
        if target not in source_node.edges:
            source_node.edges[target] = Edge(source=source, target=target)

        edge = source_node.edges[target]

        # Actualizar peso
        increment = weight_boost * (1.0 if success else 0.3)
        edge.weight += increment
        edge.interactions += 1
        edge.last_interaction = time.time()

        # Trackear dominio
        edge.domains[domain] = edge.domains.get(domain, 0) + 1

        # Actualizar nodo
        source_node.total_interactions += 1

        # Check fast lane
        if edge.interactions >= FAST_LANE_THRESHOLD and not edge.is_fast_lane:
            edge.is_fast_lane = True
            self._metrics["fast_lanes_created"] += 1
            logger.debug("Fast lane: %s ↔ %s", source, target)

        # Registrar en historial
        record = InteractionRecord(
            source=source,
            target=target,
            domain=domain,
            success=success,
        )
        self._interaction_history.append(record)
        if len(self._interaction_history) > MAX_INTERACTION_HISTORY:
            self._interaction_history = self._interaction_history[-MAX_INTERACTION_HISTORY:]

        self._metrics["interactions_recorded"] += 1

        # Prune edges si excede límite
        self._prune_edges(source_node)

        return edge

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_preferred_neighbors(
        self,
        agent: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Vecinos preferidos ordenados por peso de relación."""
        node = self._nodes.get(agent)
        if not node:
            return []

        # Aplicar decay a todos los edges
        self._apply_edge_decay(node)

        neighbors = []
        for target, edge in node.edges.items():
            neighbors.append(
                {
                    "agent": target,
                    "weight": round(edge.weight, 3),
                    "interactions": edge.interactions,
                    "is_fast_lane": edge.is_fast_lane,
                    "primary_domain": edge.primary_domain,
                }
            )

        neighbors.sort(key=lambda x: x["weight"], reverse=True)  # type: ignore[arg-type,return-value]  # dict key access safe: "weight" always present
        return neighbors[:limit]

    def recommend_collaborator(
        self,
        agent: str,
        domain: str = "general",
        exclude: list[str] | None = None,
    ) -> str | None:
        """
        Recomienda el mejor colaborador para un agente en un dominio.

        Considera: peso de relación, afinidad de dominio, carga actual.
        """
        node = self._nodes.get(agent)
        if not node:
            return None

        exclude_set = set(exclude or [])
        exclude_set.add(agent)

        candidates: list[tuple[str, float]] = []

        for target, edge in node.edges.items():
            if target in exclude_set:
                continue

            target_node = self._nodes.get(target)
            if not target_node:
                continue

            # Score = peso * afinidad_dominio * (1 - carga)
            domain_affinity = edge.domains.get(domain, 0) / max(1, edge.interactions)
            load_factor = 1.0 - target_node.load
            score = edge.weight * (0.5 + 0.5 * domain_affinity) * load_factor

            candidates.append((target, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def get_node(self, agent: str) -> dict[str, Any] | None:
        """Obtiene información de un nodo."""
        node = self._nodes.get(agent)
        if not node:
            return None
        self._apply_edge_decay(node)
        return node.to_dict()

    # --------------------------------------------------------
    # Cluster Detection
    # --------------------------------------------------------
    def _gather_cluster_members(
        self,
        seed: str,
        node: AgentNode,
        visited: set[str],
    ) -> list[str]:
        """Agrupa al agente semilla con sus vecinos de alta afinidad.

        Marca como visitados al seed y a los vecinos agregados.

        Args:
            seed: Agente semilla con el que arranca el cluster.
            node: Nodo del agente semilla.
            visited: Conjunto de agentes ya asignados (se muta in-place).

        Returns:
            Lista de miembros del cluster (incluye al seed primero).
        """
        members = [seed]
        visited.add(seed)
        for target, edge in node.edges.items():
            if target in visited:
                continue
            if edge.weight >= CLUSTER_AFFINITY_MIN:
                members.append(target)
                visited.add(target)
        return members

    def _compute_cluster_cohesion(self, members: list[str]) -> float:
        """Calcula la cohesión del cluster (promedio de pesos entre pares).

        Args:
            members: Miembros del cluster.

        Returns:
            Promedio de pesos de los edges existentes entre pares de miembros,
            o 0 si no hay pares.
        """
        total_weight = 0.0
        pair_count = 0
        for i, m1 in enumerate(members):
            for m2 in members[i + 1 :]:
                n1 = self._nodes.get(m1)
                if n1 and m2 in n1.edges:
                    total_weight += n1.edges[m2].weight
                pair_count += 1
        return total_weight / pair_count if pair_count > 0 else 0.0

    def _compute_cluster_primary_domain(self, members: list[str]) -> str:
        """Determina el dominio dominante del cluster.

        Args:
            members: Miembros del cluster.

        Returns:
            Dominio con mayor conteo acumulado entre los edges de los miembros,
            o ``"general"`` si no hay dominios registrados.
        """
        domain_counts: dict[str, int] = defaultdict(int)
        for member in members:
            n = self._nodes.get(member)
            if n:
                for edge in n.edges.values():
                    for d, c in edge.domains.items():
                        domain_counts[d] += c
        if not domain_counts:
            return "general"
        return max(domain_counts, key=lambda d: domain_counts[d])

    def detect_clusters(self, min_size: int = 2) -> list[dict[str, Any]]:
        """
        Detecta clusters de agentes con alta afinidad.

        Algoritmo greedy: agrupa agentes que comparten edges fuertes.
        """
        # Reset clusters
        for node in self._nodes.values():
            node.cluster_id = None

        visited: set[str] = set()
        clusters: list[Cluster] = []

        # Ordenar agentes por degree (los más conectados primero)
        agents_by_degree = sorted(
            self._nodes.keys(),
            key=lambda a: self._nodes[a].degree,
            reverse=True,
        )

        for agent in agents_by_degree:
            if agent in visited:
                continue

            node = self._nodes[agent]
            cluster_members = self._gather_cluster_members(agent, node, visited)

            if len(cluster_members) < min_size:
                continue

            cluster = Cluster(
                members=cluster_members,
                primary_domain=self._compute_cluster_primary_domain(cluster_members),
                cohesion=self._compute_cluster_cohesion(cluster_members),
            )

            # Asignar cluster a nodos
            for member in cluster_members:
                if member in self._nodes:
                    self._nodes[member].cluster_id = cluster.cluster_id

            clusters.append(cluster)

        self._clusters = clusters
        self._metrics["clusters_detected"] = len(clusters)
        return [c.to_dict() for c in clusters]

    # --------------------------------------------------------
    # Bottleneck Detection
    # --------------------------------------------------------
    def detect_bottlenecks(self) -> list[dict[str, Any]]:
        """Detecta agentes que son cuellos de botella."""
        bottlenecks = []
        for agent, node in self._nodes.items():
            # Contar edges entrantes (otros agentes que lo referencian)
            incoming = 0
            for other_agent, other_node in self._nodes.items():
                if other_agent != agent and agent in other_node.edges:
                    incoming += 1

            total_degree = node.degree + incoming
            if total_degree > 5 and node.load > BOTTLENECK_THRESHOLD:
                bottlenecks.append(
                    {
                        "agent": agent,
                        "outgoing": node.degree,
                        "incoming": incoming,
                        "total_degree": total_degree,
                        "load": round(node.load, 3),
                        "recommendation": "distribute_load",
                    }
                )

        self._metrics["bottlenecks_detected"] = len(bottlenecks)
        return bottlenecks

    # --------------------------------------------------------
    # Load Management
    # --------------------------------------------------------
    def update_load(self, agent: str, load: float) -> None:
        """Actualiza la carga de un agente."""
        node = self._get_or_create_node(agent)
        node.load = max(0.0, min(1.0, load))

    def rebalance_recommendations(self) -> list[dict[str, Any]]:
        """
        Genera recomendaciones de rebalanceo.

        Sugiere mover carga de agentes sobrecargados a sus vecinos menos cargados.
        """
        recommendations = []
        for agent, node in self._nodes.items():
            if node.load < 0.8:
                continue

            # Buscar vecinos con baja carga
            for target, edge in node.edges.items():
                target_node = self._nodes.get(target)
                if target_node and target_node.load < 0.4:
                    recommendations.append(
                        {
                            "action": "redistribute",
                            "from_agent": agent,
                            "to_agent": target,
                            "from_load": round(node.load, 3),
                            "to_load": round(target_node.load, 3),
                            "relationship_weight": round(edge.weight, 3),
                            "shared_domain": edge.primary_domain,
                        }
                    )

        return recommendations

    # --------------------------------------------------------
    # Graph Export
    # --------------------------------------------------------
    def get_graph(self) -> dict[str, Any]:
        """Exporta el grafo completo para visualización."""
        nodes = []
        edges = []

        for agent, node in self._nodes.items():
            self._apply_edge_decay(node)
            nodes.append(
                {
                    "id": agent,
                    "degree": node.degree,
                    "load": round(node.load, 3),
                    "cluster": node.cluster_id,
                    "is_bottleneck": node.is_bottleneck,
                }
            )

            for target, edge in node.edges.items():
                if edge.weight >= MIN_EDGE_WEIGHT:
                    edges.append(edge.to_dict())

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas de la topología."""
        total_edges = sum(n.degree for n in self._nodes.values())
        fast_lanes = sum(
            1 for n in self._nodes.values() for e in n.edges.values() if e.is_fast_lane
        )
        return {
            "nodes": len(self._nodes),
            "edges": total_edges,
            "fast_lanes": fast_lanes,
            "clusters": len(self._clusters),
            "interactions_total": sum(n.total_interactions for n in self._nodes.values()),
            "metrics": {**self._metrics},
        }

    def get_interaction_history(
        self,
        agent: str | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de interacciones filtrado."""
        records = self._interaction_history
        if agent:
            records = [r for r in records if r.source == agent or r.target == agent]
        if domain:
            records = [r for r in records if r.domain == domain]
        return [r.to_dict() for r in records[-limit:]][::-1]

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _get_or_create_node(self, agent: str) -> AgentNode:
        """Obtiene o crea un nodo."""
        if agent not in self._nodes:
            self._nodes[agent] = AgentNode(agent=agent)
        return self._nodes[agent]

    def _apply_edge_decay(self, node: AgentNode) -> None:
        """Aplica decay a los edges de un nodo."""
        dead_edges = []
        for target, edge in node.edges.items():
            days = (time.time() - edge.last_interaction) / 86400
            if days < 1:
                continue
            decay = 1.0 - (EDGE_DECAY_RATE * min(days, 30))
            edge.weight *= decay
            if edge.weight < MIN_EDGE_WEIGHT:
                dead_edges.append(target)

        for target in dead_edges:
            del node.edges[target]
            self._metrics["edges_pruned"] += 1

    def _prune_edges(self, node: AgentNode) -> None:
        """Elimina edges más débiles si excede el límite."""
        if node.degree <= MAX_EDGES_PER_AGENT:
            return

        # Ordenar por peso y eliminar los más débiles
        sorted_edges = sorted(
            node.edges.items(),
            key=lambda x: x[1].weight,
        )
        to_remove = node.degree - MAX_EDGES_PER_AGENT
        for target, _ in sorted_edges[:to_remove]:
            del node.edges[target]
            self._metrics["edges_pruned"] += 1


# ============================================================
# Singleton
# ============================================================
_instance: AdaptiveTopology | None = None


def get_adaptive_topology(bus: Any = None) -> AdaptiveTopology:
    """Obtiene o crea la topología global."""
    global _instance
    if _instance is None:
        _instance = AdaptiveTopology(bus=bus)
    return _instance
