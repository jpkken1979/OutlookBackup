"""
Agent Federation — protocolo A2A para comunicación inter-ecosistema.

Permite que múltiples instancias de Antigravity se descubran,
se conecten y colaboren:
  - Discovery: ecosistemas publican su agent card
  - Registration: ecosistemas se registran en la federación
  - Delegation: delegar tareas a ecosistemas remotos
  - Sync: sincronizar knowledge, reputation, genomes

Usage:
    federation = AgentFederation(bus=bus, node_id="node-alpha")

    # Registrar nodo local
    federation.register_local(
        name="Antigravity Alpha",
        capabilities=["code_analysis", "security"],
        endpoint="http://alpha:4747",
    )

    # Registrar nodo remoto (descubierto)
    federation.register_peer(
        node_id="node-beta",
        name="Antigravity Beta",
        endpoint="http://beta:4747",
    )

    # Delegar tarea
    result = federation.delegate("node-beta", "security-auditor", "audit this code")
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.agent_federation")

# ============================================================
# Constantes
# ============================================================
MAX_PEERS = 50  # Máximo de nodos federados
MAX_DELEGATIONS = 500  # Historial de delegaciones
PEER_TIMEOUT = 300.0  # Timeout de peer sin heartbeat
HEARTBEAT_INTERVAL = 60.0  # Intervalo de heartbeat


# ============================================================
# Modelos
# ============================================================
@dataclass
class FederationNode:
    """Nodo en la federación."""

    node_id: str
    name: str = ""
    endpoint: str = ""
    capabilities: list[str] = field(default_factory=list)
    agents_count: int = 0
    skills_count: int = 0
    trust_score: float = 0.5
    status: str = "active"  # active, inactive, suspended
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < PEER_TIMEOUT

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "capabilities": self.capabilities,
            "agents_count": self.agents_count,
            "skills_count": self.skills_count,
            "trust_score": round(self.trust_score, 3),
            "status": self.status,
            "is_alive": self.is_alive,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
        }


@dataclass
class Delegation:
    """Una tarea delegada a un nodo remoto."""

    delegation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_node: str = ""
    target_node: str = ""
    agent: str = ""
    task: str = ""
    status: str = "pending"  # pending, running, completed, failed
    result: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "agent": self.agent,
            "task": self.task,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ============================================================
# Agent Federation
# ============================================================
class AgentFederation:
    """
    Federación de ecosistemas Antigravity.
    Descubrimiento, delegación y sincronización.
    """

    def __init__(
        self,
        bus: Any = None,
        node_id: str | None = None,
    ) -> None:
        self._bus = bus
        self._node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"

        # Nodo local
        self._local_node: FederationNode | None = None

        # Peers registrados
        self._peers: dict[str, FederationNode] = {}

        # Delegaciones
        self._delegations: list[Delegation] = []

        # Métricas
        self._metrics = {
            "peers_registered": 0,
            "delegations_sent": 0,
            "delegations_received": 0,
            "delegations_completed": 0,
            "delegations_failed": 0,
            "heartbeats_sent": 0,
        }

    # --------------------------------------------------------
    # Local Node
    # --------------------------------------------------------
    def register_local(
        self,
        name: str = "Antigravity",
        capabilities: list[str] | None = None,
        endpoint: str = "http://localhost:4747",
        agents_count: int = 40,
        skills_count: int = 940,
    ) -> dict[str, Any]:
        """Registra el nodo local en la federación."""
        self._local_node = FederationNode(
            node_id=self._node_id,
            name=name,
            endpoint=endpoint,
            capabilities=capabilities or [],
            agents_count=agents_count,
            skills_count=skills_count,
            trust_score=1.0,  # Confianza total en sí mismo
        )
        logger.info("Local node registered: %s (%s)", name, self._node_id)
        return self._local_node.to_dict()

    def get_local(self) -> dict[str, Any] | None:
        """Info del nodo local."""
        return self._local_node.to_dict() if self._local_node else None

    def get_agent_card(self) -> dict[str, Any]:
        """Agent Card A2A del nodo local."""
        if not self._local_node:
            return {"error": "Local node not registered"}

        return {
            "name": self._local_node.name,
            "url": self._local_node.endpoint,
            "version": "2.1.0",
            "protocol": "a2a",
            "capabilities": self._local_node.capabilities,
            "agents": self._local_node.agents_count,
            "skills": self._local_node.skills_count,
            "federation": {
                "node_id": self._node_id,
                "peers": len(self._peers),
            },
        }

    # --------------------------------------------------------
    # Peer Management
    # --------------------------------------------------------
    def register_peer(
        self,
        node_id: str,
        name: str = "",
        endpoint: str = "",
        capabilities: list[str] | None = None,
        agents_count: int = 0,
        skills_count: int = 0,
    ) -> dict[str, Any]:
        """Registra un peer remoto."""
        if len(self._peers) >= MAX_PEERS:
            return {"error": "Max peers reached"}

        peer = FederationNode(
            node_id=node_id,
            name=name or f"Peer-{node_id}",
            endpoint=endpoint,
            capabilities=capabilities or [],
            agents_count=agents_count,
            skills_count=skills_count,
        )
        self._peers[node_id] = peer
        self._metrics["peers_registered"] += 1

        logger.info("Peer registered: %s (%s)", name, node_id)
        return peer.to_dict()

    def remove_peer(self, node_id: str) -> bool:
        """Elimina un peer."""
        if node_id in self._peers:
            del self._peers[node_id]
            return True
        return False

    def heartbeat(self, node_id: str) -> bool:
        """Actualiza heartbeat de un peer."""
        peer = self._peers.get(node_id)
        if not peer:
            return False
        peer.last_heartbeat = time.time()
        self._metrics["heartbeats_sent"] += 1
        return True

    def get_peers(self, only_alive: bool = False) -> list[dict[str, Any]]:
        """Lista peers."""
        peers = list(self._peers.values())
        if only_alive:
            peers = [p for p in peers if p.is_alive]
        return [p.to_dict() for p in peers]

    def get_peer(self, node_id: str) -> dict[str, Any] | None:
        """Info de un peer."""
        peer = self._peers.get(node_id)
        return peer.to_dict() if peer else None

    # --------------------------------------------------------
    # Delegation
    # --------------------------------------------------------
    def delegate(
        self,
        target_node: str,
        agent: str,
        task: str,
    ) -> dict[str, Any]:
        """Delega una tarea a un nodo remoto."""
        if target_node not in self._peers:
            return {"error": f"Peer {target_node} not found"}

        peer = self._peers[target_node]
        if not peer.is_alive:
            return {"error": f"Peer {target_node} is not alive"}

        delegation = Delegation(
            source_node=self._node_id,
            target_node=target_node,
            agent=agent,
            task=task,
        )
        self._delegations.append(delegation)
        if len(self._delegations) > MAX_DELEGATIONS:
            self._delegations = self._delegations[-MAX_DELEGATIONS:]

        self._metrics["delegations_sent"] += 1

        logger.info("Task delegated to %s: agent=%s", target_node, agent)
        return delegation.to_dict()

    def complete_delegation(
        self,
        delegation_id: str,
        success: bool = True,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Marca una delegación como completada."""
        for d in self._delegations:
            if d.delegation_id == delegation_id:
                d.status = "completed" if success else "failed"
                d.result = result or {}
                d.completed_at = time.time()
                if success:
                    self._metrics["delegations_completed"] += 1
                else:
                    self._metrics["delegations_failed"] += 1
                return d.to_dict()
        return None

    def get_delegations(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista delegaciones."""
        delegations = self._delegations
        if status:
            delegations = [d for d in delegations if d.status == status]
        return [d.to_dict() for d in delegations[-limit:]][::-1]

    # --------------------------------------------------------
    # Discovery
    # --------------------------------------------------------
    def find_capability(self, capability: str) -> list[dict[str, Any]]:
        """Busca peers con una capability específica."""
        results = []
        for peer in self._peers.values():
            if capability in peer.capabilities and peer.is_alive:
                results.append(peer.to_dict())
        return sorted(results, key=lambda p: p["trust_score"], reverse=True)

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas de la federación."""
        alive = sum(1 for p in self._peers.values() if p.is_alive)
        return {
            "node_id": self._node_id,
            "local_registered": self._local_node is not None,
            "total_peers": len(self._peers),
            "alive_peers": alive,
            "total_delegations": len(self._delegations),
            "capabilities_available": sorted(
                {c for p in self._peers.values() for c in p.capabilities}
            ),
            "metrics": {**self._metrics},
        }


# ============================================================
# Singleton
# ============================================================
_instance: AgentFederation | None = None


def get_agent_federation(bus: Any = None) -> AgentFederation:
    """Obtiene o crea la federación global."""
    global _instance
    if _instance is None:
        _instance = AgentFederation(bus=bus)
    return _instance
