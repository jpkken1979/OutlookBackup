"""Mixin de reputación, topología y confianza para AgentDaemon.

Adaptadores para: AgentReputation (Sprint 6), AdaptiveTopology (Sprint 6),
TrustNetwork (Sprint 9B). Gestiona la calidad, relaciones y confianza
entre agentes del ecosistema.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonReputationMixin:
    """Adaptadores de reputación, topología adaptativa y red de confianza.

    Agrupa los subsistemas que evalúan la calidad de los agentes,
    sus relaciones topológicas y niveles de confianza mutua.
    """

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _agent_reputation: Any | None
    _adaptive_topology: Any | None
    _trust_network: Any | None

    # --------------------------------------------------------
    # AgentReputation (Sprint 6)
    # --------------------------------------------------------
    def record_reputation_outcome(
        self,
        agent: str,
        domain: str,
        success: bool = True,
        duration: float = 0.0,
        partial: bool = False,
        timeout: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Registra un resultado en el sistema de reputación."""
        if self._agent_reputation is None:
            raise RuntimeError("AgentReputation no inicializado")
        self._metrics["reputation_outcomes"] += 1
        record = self._agent_reputation.record_outcome(
            agent,
            domain,
            success,
            duration,
            partial,
            timeout,
            metadata,
        )
        return record.to_dict()

    def get_agent_trust(self, agent: str, domain: str = "general") -> dict[str, Any]:
        """Obtiene la confianza de un agente en un dominio."""
        if self._agent_reputation is None:
            return {"status": "disabled"}
        return self._agent_reputation.get_trust(agent, domain).to_dict()

    def get_agent_reputation_profile(self, agent: str) -> dict[str, Any]:
        """Obtiene el perfil de reputación completo de un agente."""
        if self._agent_reputation is None:
            return {"status": "disabled"}
        return self._agent_reputation.get_agent_profile(agent)

    def get_reputation_rankings(
        self,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Rankings de agentes por reputación."""
        if self._agent_reputation is None:
            return []
        return self._agent_reputation.get_rankings(domain, limit)

    def vouch_for_agent(
        self,
        voucher: str,
        vouchee: str,
        domain: str,
        weight: float = 0.5,
    ) -> dict[str, Any] | None:
        """Un agente voucha por otro."""
        if self._agent_reputation is None:
            return None
        record = self._agent_reputation.vouch(voucher, vouchee, domain, weight)
        return record.to_dict() if record else None

    def get_reputation_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de reputación."""
        if self._agent_reputation is None:
            return {"status": "disabled"}
        return self._agent_reputation.get_stats()

    def get_reputation_history(
        self,
        agent: str | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de reputación filtrado."""
        if self._agent_reputation is None:
            return []
        return self._agent_reputation.get_history(agent, domain, limit)

    # --------------------------------------------------------
    # AdaptiveTopology (Sprint 6)
    # --------------------------------------------------------
    def record_topology_interaction(
        self,
        source: str,
        target: str,
        domain: str = "general",
        success: bool = True,
    ) -> dict[str, Any]:
        """Registra una interacción en la topología."""
        if self._adaptive_topology is None:
            raise RuntimeError("AdaptiveTopology no inicializado")
        self._metrics["topology_interactions"] += 1
        edge = self._adaptive_topology.record_interaction(source, target, domain, success)
        return edge.to_dict()

    def get_topology_neighbors(self, agent: str, limit: int = 10) -> list[dict[str, Any]]:
        """Vecinos preferidos de un agente."""
        if self._adaptive_topology is None:
            return []
        return self._adaptive_topology.get_preferred_neighbors(agent, limit)

    def recommend_collaborator(self, agent: str, domain: str = "general") -> str | None:
        """Recomienda un colaborador para un agente."""
        if self._adaptive_topology is None:
            return None
        return self._adaptive_topology.recommend_collaborator(agent, domain)

    def get_topology_clusters(self) -> list[dict[str, Any]]:
        """Detecta clusters de agentes."""
        if self._adaptive_topology is None:
            return []
        return self._adaptive_topology.detect_clusters()

    def get_topology_bottlenecks(self) -> list[dict[str, Any]]:
        """Detecta cuellos de botella."""
        if self._adaptive_topology is None:
            return []
        return self._adaptive_topology.detect_bottlenecks()

    def get_topology_graph(self) -> dict[str, Any]:
        """Exporta el grafo de topología."""
        if self._adaptive_topology is None:
            return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}
        return self._adaptive_topology.get_graph()

    def get_topology_rebalance(self) -> list[dict[str, Any]]:
        """Recomendaciones de rebalanceo."""
        if self._adaptive_topology is None:
            return []
        return self._adaptive_topology.rebalance_recommendations()

    def get_topology_stats(self) -> dict[str, Any]:
        """Estadísticas de la topología."""
        if self._adaptive_topology is None:
            return {"status": "disabled"}
        return self._adaptive_topology.get_stats()

    # --------------------------------------------------------
    # Trust Network (Sprint 9B)
    # --------------------------------------------------------
    def trust_set(self, target: str, trust: float, evidence: str = "") -> dict[str, Any]:
        """Establece nivel de confianza hacia un nodo."""
        if self._trust_network is None:
            return {"status": "disabled"}
        return self._trust_network.set_trust(target, trust, evidence)

    def trust_calculate(self, target: str) -> float:
        """Calcula la confianza agregada hacia un nodo."""
        if self._trust_network is None:
            return 0.0
        return self._trust_network.calculate_trust(target)

    def trust_is_trusted(self, target: str, min_trust: float = 0.3) -> bool:
        """Verifica si un nodo supera el umbral de confianza."""
        if self._trust_network is None:
            return False
        return self._trust_network.is_trusted(target, min_trust)

    def trust_get_graph(self) -> dict[str, Any]:
        """Exporta el grafo de confianza."""
        if self._trust_network is None:
            return {"status": "disabled"}
        return self._trust_network.get_trust_graph()

    def get_trust_stats(self) -> dict[str, Any]:
        """Estadísticas de la red de confianza."""
        if self._trust_network is None:
            return {"status": "disabled"}
        return self._trust_network.get_stats()
