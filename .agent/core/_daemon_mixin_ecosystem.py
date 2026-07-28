"""Mixin de ecosistema multi-agente para AgentDaemon."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonEcosystemMixin:
    """Adaptadores de contratos, arena, websocket, federación y marketplace."""

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _contract_manager: Any | None
    _adversarial_arena: Any | None
    _ws_bridge: Any | None
    _agent_federation: Any | None
    _capability_marketplace: Any | None

    # -- AgentContracts (Sprint 7) --
    def contract_create(
        self,
        agent: str,
        max_response_time: float = 30.0,
        min_success_rate: float = 0.75,
        domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Crea un contrato de nivel de servicio para un agente."""
        if self._contract_manager is None:
            raise RuntimeError("ContractManager no inicializado")
        return self._contract_manager.create_contract(
            agent, max_response_time, min_success_rate, domains
        )

    def contract_record_execution(
        self,
        agent: str,
        duration: float = 0.0,
        success: bool = True,
        domain: str = "general",
    ) -> dict[str, Any] | None:
        """Registra una ejecución contra el contrato de un agente."""
        if self._contract_manager is None:
            return None
        self._metrics["contract_executions"] += 1
        return self._contract_manager.record_execution(agent, duration, success, domain)

    def contract_check_compliance(self, agent: str) -> dict[str, Any]:
        """Verifica el cumplimiento del contrato de un agente."""
        if self._contract_manager is None:
            return {"status": "disabled"}
        return self._contract_manager.check_compliance(agent)

    def contract_check_all(self) -> list[dict[str, Any]]:
        """Verifica cumplimiento de todos los contratos."""
        if self._contract_manager is None:
            return []
        return self._contract_manager.check_all_compliance()

    def contract_get(self, agent: str) -> dict[str, Any] | None:
        """Obtiene el contrato de un agente."""
        if self._contract_manager is None:
            return None
        return self._contract_manager.get_contract(agent)

    def contract_list(self, status: str | None = None) -> list[dict[str, Any]]:
        """Lista contratos, opcionalmente filtrados por estado."""
        if self._contract_manager is None:
            return []
        return self._contract_manager.list_contracts(status)

    def contract_auto_generate(self, agent: str) -> dict[str, Any]:
        """Genera automáticamente un contrato basado en historial."""
        if self._contract_manager is None:
            return {"status": "disabled"}
        return self._contract_manager.auto_generate_contract(agent)

    def contract_get_violations(
        self, agent: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Obtiene violaciones de contratos."""
        if self._contract_manager is None:
            return []
        return self._contract_manager.get_violations(agent, limit=limit)

    def contract_non_compliant(self) -> list[dict[str, Any]]:
        """Obtiene agentes que no cumplen sus contratos."""
        if self._contract_manager is None:
            return []
        return self._contract_manager.get_non_compliant_agents()

    def get_contract_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de contratos."""
        if self._contract_manager is None:
            return {"status": "disabled"}
        return self._contract_manager.get_stats()

    # -- AdversarialArena (Sprint 8) --
    def arena_create_challenge(
        self,
        challenger: str,
        defender: str,
        challenge_type: str = "edge_case",
        description: str = "",
        difficulty: float = 0.5,
    ) -> dict[str, Any]:
        """Crea un desafío adversarial entre agentes."""
        if self._adversarial_arena is None:
            return {"status": "disabled"}
        self._metrics["adversarial_challenges"] += 1
        return self._adversarial_arena.create_challenge(
            challenger,
            defender,
            challenge_type,
            description,
            difficulty,
        )

    def arena_submit_response(
        self,
        challenge_id: str,
        success: bool = True,
        quality: float = 0.5,
    ) -> dict[str, Any]:
        """Envía respuesta a un desafío adversarial."""
        if self._adversarial_arena is None:
            return {"status": "disabled"}
        return self._adversarial_arena.submit_response(challenge_id, success, quality)

    def arena_get_rankings(self, sort_by: str = "elo") -> list[dict[str, Any]]:
        """Obtiene rankings de la arena adversarial."""
        if self._adversarial_arena is None:
            return []
        return self._adversarial_arena.get_rankings(sort_by)

    def arena_get_profile(self, agent: str) -> dict[str, Any]:
        """Obtiene perfil de un agente en la arena."""
        if self._adversarial_arena is None:
            return {"status": "disabled"}
        return self._adversarial_arena.get_profile(agent)

    def arena_get_matchups(self) -> list[dict[str, Any]]:
        """Obtiene emparejamientos sugeridos."""
        if self._adversarial_arena is None:
            return []
        return self._adversarial_arena.get_matchups()

    def arena_battle_history(
        self, agent: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Obtiene historial de batallas."""
        if self._adversarial_arena is None:
            return []
        return self._adversarial_arena.get_battle_history(agent, limit)

    def arena_pending(self, defender: str | None = None) -> list[dict[str, Any]]:
        """Obtiene desafíos pendientes."""
        if self._adversarial_arena is None:
            return []
        return self._adversarial_arena.get_pending_challenges(defender)

    def get_arena_stats(self) -> dict[str, Any]:
        """Estadísticas de la arena adversarial."""
        if self._adversarial_arena is None:
            return {"status": "disabled"}
        return self._adversarial_arena.get_stats()

    # -- WebSocket Bridge (Sprint 9A) --
    def ws_broadcast(self, topic: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Envía broadcast a todos los clientes WebSocket."""
        if self._ws_bridge is None:
            return {"status": "disabled"}
        self._metrics["ws_broadcasts"] += 1
        return self._ws_bridge.broadcast(topic, payload)

    def ws_connect(self, client_id: str | None = None) -> dict[str, Any]:
        """Conecta un cliente al bridge WebSocket."""
        if self._ws_bridge is None:
            return {"status": "disabled"}
        return self._ws_bridge.connect_client(client_id)

    def ws_subscribe(self, client_id: str, topics: list[str]) -> dict[str, Any]:
        """Suscribe un cliente a topics del bridge."""
        if self._ws_bridge is None:
            return {"status": "disabled"}
        return self._ws_bridge.subscribe(client_id, topics)

    def ws_get_clients(self) -> list[dict[str, Any]]:
        """Obtiene lista de clientes conectados."""
        if self._ws_bridge is None:
            return []
        return self._ws_bridge.get_clients()

    def get_ws_stats(self) -> dict[str, Any]:
        """Estadísticas del bridge WebSocket."""
        if self._ws_bridge is None:
            return {"status": "disabled"}
        return self._ws_bridge.get_stats()

    # -- Federation (Sprint 9B) --
    def federation_register_local(
        self,
        name: str = "Antigravity",
        endpoint: str = "http://localhost:4747",
    ) -> dict[str, Any]:
        """Registra el nodo local en la federación."""
        if self._agent_federation is None:
            return {"status": "disabled"}
        return self._agent_federation.register_local(name=name, endpoint=endpoint)

    def federation_register_peer(
        self,
        node_id: str,
        name: str = "",
        endpoint: str = "",
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Registra un nodo peer en la federación."""
        if self._agent_federation is None:
            return {"status": "disabled"}
        return self._agent_federation.register_peer(node_id, name, endpoint, capabilities)

    def federation_delegate(self, target_node: str, agent: str, task: str) -> dict[str, Any]:
        """Delega una tarea a un nodo remoto de la federación."""
        if self._agent_federation is None:
            return {"status": "disabled"}
        self._metrics["federation_delegations"] += 1
        return self._agent_federation.delegate(target_node, agent, task)

    def federation_get_peers(self) -> list[dict[str, Any]]:
        """Obtiene lista de peers en la federación."""
        if self._agent_federation is None:
            return []
        return self._agent_federation.get_peers()

    def get_federation_stats(self) -> dict[str, Any]:
        """Estadísticas de la federación."""
        if self._agent_federation is None:
            return {"status": "disabled"}
        return self._agent_federation.get_stats()

    # -- Marketplace (Sprint 9B) --
    def marketplace_publish(
        self,
        skill_name: str,
        provider: str,
        domain: str = "general",
        description: str = "",
        quality: float = 0.5,
    ) -> dict[str, Any]:
        """Publica una capacidad en el marketplace."""
        if self._capability_marketplace is None:
            return {"status": "disabled"}
        return self._capability_marketplace.publish(
            skill_name, provider, domain, description, quality
        )

    def marketplace_search(
        self, query: str = "", domain: str | None = None
    ) -> list[dict[str, Any]]:
        """Busca capacidades en el marketplace."""
        if self._capability_marketplace is None:
            return []
        return self._capability_marketplace.search(query, domain)

    def marketplace_acquire(self, skill_name: str, requester: str) -> dict[str, Any]:
        """Adquiere una capacidad del marketplace."""
        if self._capability_marketplace is None:
            return {"status": "disabled"}
        self._metrics["marketplace_acquisitions"] += 1
        return self._capability_marketplace.acquire(skill_name, requester)

    def marketplace_trending(self, limit: int = 10) -> list[dict[str, Any]]:
        """Obtiene capacidades trending del marketplace."""
        if self._capability_marketplace is None:
            return []
        return self._capability_marketplace.trending(limit)

    def get_marketplace_stats(self) -> dict[str, Any]:
        """Estadísticas del marketplace."""
        if self._capability_marketplace is None:
            return {"status": "disabled"}
        return self._capability_marketplace.get_stats()
