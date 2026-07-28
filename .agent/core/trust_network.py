"""
Trust Network — web of trust entre ecosistemas federados.

Modelo de confianza transitiva entre nodos:
  - Direct trust: confianza directa por interacción
  - Transitive trust: A confía en B, B confía en C → A confía parcialmente en C
  - Trust decay: la confianza decae sin interacción
  - Trust evidence: cada cambio de confianza tiene evidencia
  - Trust threshold: umbral mínimo para permitir operaciones

Usage:
    network = TrustNetwork(bus=bus, local_node="node-alpha")

    # Establecer confianza directa
    network.set_trust("node-beta", 0.8, evidence="10 delegaciones exitosas")

    # Calcular confianza transitiva
    trust = network.calculate_trust("node-gamma")

    # Verificar si un nodo es confiable para una operación
    allowed = network.is_trusted("node-gamma", min_trust=0.5)

    # Grafo de confianza
    graph = network.get_trust_graph()
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.trust_network")

# ============================================================
# Constantes
# ============================================================
TRUST_DECAY_RATE = 0.001  # Decaimiento por segundo
TRUST_MIN = 0.0
TRUST_MAX = 1.0
TRANSITIVE_DECAY = 0.6  # Factor de decay transitivo
MAX_TRUST_DEPTH = 3  # Máxima profundidad de transitividad
MAX_EVIDENCE_HISTORY = 100  # Historial de evidencia por nodo
DEFAULT_TRUST_THRESHOLD = 0.3  # Umbral mínimo por defecto


# ============================================================
# Modelos
# ============================================================
@dataclass
class TrustEdge:
    """Arista de confianza entre dos nodos."""

    source: str
    target: str
    trust: float = 0.5
    evidence: str = ""
    interactions: int = 0
    last_update: float = field(default_factory=time.time)

    def decayed_trust(self) -> float:
        """Trust con decay temporal."""
        elapsed = time.time() - self.last_update
        decay = max(0.0, 1.0 - (TRUST_DECAY_RATE * elapsed))
        return self.trust * decay

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "trust": round(self.trust, 3),
            "decayed_trust": round(self.decayed_trust(), 3),
            "evidence": self.evidence,
            "interactions": self.interactions,
            "last_update": self.last_update,
        }


@dataclass
class TrustEvent:
    """Evento de cambio de confianza."""

    source: str
    target: str
    old_trust: float
    new_trust: float
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "old_trust": round(self.old_trust, 3),
            "new_trust": round(self.new_trust, 3),
            "delta": round(self.new_trust - self.old_trust, 3),
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ============================================================
# Trust Network
# ============================================================
class TrustNetwork:
    """
    Red de confianza transitiva entre nodos federados.
    """

    def __init__(
        self,
        bus: Any = None,
        local_node: str = "local",
    ) -> None:
        self._bus = bus
        self._local_node = local_node

        # Grafo de confianza: source -> target -> TrustEdge
        self._edges: dict[str, dict[str, TrustEdge]] = defaultdict(dict)

        # Historial de eventos
        self._events: list[TrustEvent] = []

        # Métricas
        self._metrics = {
            "trust_updates": 0,
            "transitive_calculations": 0,
            "trust_checks": 0,
            "trust_violations": 0,
        }

    # --------------------------------------------------------
    # Set Trust
    # --------------------------------------------------------
    def set_trust(
        self,
        target: str,
        trust: float,
        evidence: str = "",
        source: str | None = None,
    ) -> dict[str, Any]:
        """
        Establece confianza directa hacia un nodo.

        Args:
            target: Nodo destino.
            trust: Nivel de confianza [0, 1].
            evidence: Razón del cambio.
            source: Nodo origen (default: local).
        """
        src = source or self._local_node
        trust = max(TRUST_MIN, min(TRUST_MAX, trust))

        existing = self._edges[src].get(target)
        old_trust = existing.trust if existing else 0.0

        edge = TrustEdge(
            source=src,
            target=target,
            trust=trust,
            evidence=evidence,
            interactions=(existing.interactions + 1) if existing else 1,
        )
        self._edges[src][target] = edge

        event = TrustEvent(
            source=src,
            target=target,
            old_trust=old_trust,
            new_trust=trust,
            reason=evidence,
        )
        self._events.append(event)
        if len(self._events) > MAX_EVIDENCE_HISTORY * 10:
            self._events = self._events[-(MAX_EVIDENCE_HISTORY * 5) :]

        self._metrics["trust_updates"] += 1

        logger.info("Trust %s→%s: %.2f→%.2f (%s)", src, target, old_trust, trust, evidence)
        return edge.to_dict()

    # --------------------------------------------------------
    # Calculate Trust
    # --------------------------------------------------------
    def calculate_trust(
        self,
        target: str,
        source: str | None = None,
    ) -> float:
        """
        Calcula confianza (directa + transitiva) hacia un nodo.

        Si hay confianza directa, la retorna (con decay).
        Si no, busca caminos transitivos hasta MAX_TRUST_DEPTH.
        """
        src = source or self._local_node
        self._metrics["transitive_calculations"] += 1

        # Directo
        edge = self._edges.get(src, {}).get(target)
        if edge:
            return edge.decayed_trust()

        # Transitivo: BFS con decay
        visited = {src}
        current_level = {src: 1.0}
        max_trust = 0.0

        for _depth in range(MAX_TRUST_DEPTH):
            next_level: dict[str, float] = {}
            for node, incoming_trust in current_level.items():
                for neighbor, nedge in self._edges.get(node, {}).items():
                    if neighbor in visited:
                        continue
                    transitive = incoming_trust * nedge.decayed_trust() * TRANSITIVE_DECAY
                    if neighbor == target:
                        max_trust = max(max_trust, transitive)
                    elif transitive > 0.01:  # Prune low-trust paths
                        next_level[neighbor] = max(
                            next_level.get(neighbor, 0.0),
                            transitive,
                        )
                        visited.add(neighbor)

            if max_trust > 0:
                return max_trust
            if not next_level:
                break
            current_level = next_level

        return max_trust

    # --------------------------------------------------------
    # Trust Checks
    # --------------------------------------------------------
    def is_trusted(
        self,
        target: str,
        min_trust: float = DEFAULT_TRUST_THRESHOLD,
        source: str | None = None,
    ) -> bool:
        """Verifica si un nodo cumple el umbral de confianza."""
        self._metrics["trust_checks"] += 1
        trust = self.calculate_trust(target, source)
        trusted = trust >= min_trust
        if not trusted:
            self._metrics["trust_violations"] += 1
        return trusted

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_direct_trust(
        self,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Confianzas directas de un nodo."""
        src = source or self._local_node
        edges = self._edges.get(src, {})
        return [
            e.to_dict()
            for e in sorted(
                edges.values(),
                key=lambda e: e.trust,
                reverse=True,
            )
        ]

    def get_trust_graph(self) -> dict[str, Any]:
        """Grafo completo de confianza."""
        nodes = set()
        edges_list = []

        for src, targets in self._edges.items():
            nodes.add(src)
            for tgt, edge in targets.items():
                nodes.add(tgt)
                edges_list.append(
                    {
                        "source": src,
                        "target": tgt,
                        "trust": round(edge.decayed_trust(), 3),
                        "interactions": edge.interactions,
                    }
                )

        return {
            "nodes": sorted(nodes),
            "edges": edges_list,
            "node_count": len(nodes),
            "edge_count": len(edges_list),
        }

    def get_most_trusted(
        self,
        source: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Nodos más confiables."""
        src = source or self._local_node
        edges = self._edges.get(src, {})
        sorted_edges = sorted(
            edges.values(),
            key=lambda e: e.decayed_trust(),
            reverse=True,
        )
        return [
            {"node": e.target, "trust": round(e.decayed_trust(), 3)} for e in sorted_edges[:limit]
        ]

    def get_trust_history(
        self,
        target: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de cambios de confianza."""
        events = self._events
        if target:
            events = [e for e in events if e.target == target]
        return [e.to_dict() for e in events[-limit:]][::-1]

    # --------------------------------------------------------
    # Bulk Operations
    # --------------------------------------------------------
    def update_from_delegation(
        self,
        target: str,
        success: bool,
        boost: float = 0.05,
    ) -> dict[str, Any]:
        """Actualiza confianza basado en resultado de delegación."""
        current = self.calculate_trust(target)
        if success:
            new_trust = min(TRUST_MAX, current + boost)
            evidence = "Delegación exitosa"
        else:
            new_trust = max(TRUST_MIN, current - boost * 2)
            evidence = "Delegación fallida"

        return self.set_trust(target, new_trust, evidence)

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas de la red."""
        total_edges = sum(len(t) for t in self._edges.values())
        nodes = set()
        for src, targets in self._edges.items():
            nodes.add(src)
            nodes.update(targets.keys())

        return {
            "local_node": self._local_node,
            "total_nodes": len(nodes),
            "total_edges": total_edges,
            "trust_events": len(self._events),
            "avg_trust": round(
                sum(e.trust for targets in self._edges.values() for e in targets.values())
                / max(1, total_edges),
                3,
            ),
            "metrics": {**self._metrics},
        }


# ============================================================
# Singleton
# ============================================================
_instance: TrustNetwork | None = None


def get_trust_network(bus: Any = None) -> TrustNetwork:
    """Obtiene o crea la trust network global."""
    global _instance
    if _instance is None:
        _instance = TrustNetwork(bus=bus)
    return _instance
