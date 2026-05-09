"""Mixin de coordinación multi-agente para AgentDaemon.

Extraído de agent_daemon.py para reducir el tamaño del archivo principal.
Contiene adaptadores para: ReactiveEventSystem, ContractNetProtocol,
SwarmCoordinator, IntelligentRouter, ConsensusProtocol, AgentObservatory,
WorkflowEngine.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonCoordinationMixin:
    """Adaptadores de coordinación y orquestación multi-agente."""

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _reactive_system: Any | None
    _negotiation_protocol: Any | None
    _swarm_coordinator: Any | None
    _intelligent_router: Any | None
    _consensus_protocol: Any | None
    _agent_observatory: Any | None
    _workflow_engine: Any | None

    # --------------------------------------------------------
    # ReactiveEventSystem (Sprint 4)
    # --------------------------------------------------------
    async def emit_event(
        self,
        event_type: str,
        source: str,
        data: dict[str, Any],
        severity: str = "info",
    ) -> dict[str, Any]:
        """Emite un evento al sistema reactivo."""
        if self._reactive_system is None:
            raise RuntimeError("ReactiveEventSystem no inicializado")
        from .reactive_event_system import EventType, SystemEvent

        event = SystemEvent(
            event_type=EventType(event_type),
            source=source,
            data=data,
            severity=severity,
        )
        await self._reactive_system.emit(event)
        self._metrics["reactive_triggers"] += 1
        return event.to_dict()

    def register_reactive_rule(self, rule_data: dict[str, Any]) -> dict[str, Any]:
        """Registra una regla reactiva."""
        if self._reactive_system is None:
            raise RuntimeError("ReactiveEventSystem no inicializado")
        from .reactive_event_system import EventRule, EventType, MatchStrategy

        rule = EventRule(
            name=rule_data["name"],
            event_type=EventType(rule_data["event_type"]),
            pattern=rule_data["pattern"],
            agent=rule_data["agent"],
            task_template=rule_data["task_template"],
            match_strategy=MatchStrategy(rule_data.get("match_strategy", "glob")),
            match_field=rule_data.get("match_field", ""),
            priority=rule_data.get("priority", 5),
            cooldown_seconds=rule_data.get("cooldown_seconds", 30.0),
            enabled=rule_data.get("enabled", True),
        )
        self._reactive_system.register_rule(rule)
        return rule.to_dict()

    def list_reactive_rules(self) -> list[dict[str, Any]]:
        """Lista reglas reactivas."""
        if self._reactive_system is None:
            return []
        return self._reactive_system.list_rules()

    def toggle_reactive_rule(self, name: str, enabled: bool) -> bool:
        """Habilita/deshabilita una regla."""
        if self._reactive_system is None:
            return False
        if enabled:
            return self._reactive_system.enable_rule(name)
        return self._reactive_system.disable_rule(name)

    def get_reactive_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del sistema reactivo."""
        if self._reactive_system is None:
            return {"status": "disabled"}
        return self._reactive_system.get_stats()

    def get_event_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de eventos."""
        if self._reactive_system is None:
            return []
        return self._reactive_system.get_event_history(limit)

    def get_trigger_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de triggers."""
        if self._reactive_system is None:
            return []
        return self._reactive_system.get_trigger_history(limit)

    # --------------------------------------------------------
    # ContractNetProtocol — Negociación (Sprint 4)
    # --------------------------------------------------------
    async def auction_task(
        self,
        task: str,
        required_capabilities: list[str] | None = None,
        strategy: str = "balanced",
        from_agent: str = "api",
    ) -> dict[str, Any]:
        """Subasta una tarea entre agentes capaces."""
        if self._negotiation_protocol is None:
            raise RuntimeError("ContractNetProtocol no inicializado")
        from .agent_negotiation import AuctionStrategy, TaskAnnouncement

        announcement = TaskAnnouncement(
            task=task,
            required_capabilities=required_capabilities or [],
            strategy=AuctionStrategy(strategy),
            from_agent=from_agent,
        )
        result = await self._negotiation_protocol.auction(announcement)
        self._metrics["auctions_total"] += 1
        return result.to_dict()

    def list_negotiation_agents(self) -> list[dict[str, Any]]:
        """Lista agentes registrados para negociación."""
        if self._negotiation_protocol is None:
            return []
        return self._negotiation_protocol.list_agents()

    def get_auction_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de subastas."""
        if self._negotiation_protocol is None:
            return []
        return self._negotiation_protocol.get_auction_history(limit)

    def get_auction(self, auction_id: str) -> dict[str, Any] | None:
        """Retorna una subasta por ID."""
        if self._negotiation_protocol is None:
            return None
        return self._negotiation_protocol.get_auction(auction_id)

    def get_negotiation_stats(self) -> dict[str, Any]:
        """Retorna estadísticas de negociación."""
        if self._negotiation_protocol is None:
            return {"status": "disabled"}
        return self._negotiation_protocol.get_stats()

    # --------------------------------------------------------
    # SwarmCoordinator (Sprint 4)
    # --------------------------------------------------------
    async def execute_swarm(
        self,
        task: str,
        agents: list[str] | None = None,
        mode: str = "dag",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ejecuta un enjambre multi-agente."""
        if self._swarm_coordinator is None:
            raise RuntimeError("SwarmCoordinator no inicializado")
        from .swarm_coordinator import SwarmMode, SwarmRequest

        request = SwarmRequest(
            task=task,
            agents=agents or [],
            mode=SwarmMode(mode),
            context=context or {},
        )
        result = await self._swarm_coordinator.execute_swarm(request)
        self._metrics["swarms_executed"] += 1
        return result.to_dict()

    def get_swarm(self, swarm_id: str) -> dict[str, Any] | None:
        """Retorna un swarm por ID."""
        if self._swarm_coordinator is None:
            return None
        return self._swarm_coordinator.get_swarm(swarm_id)

    def list_swarms(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista swarms."""
        if self._swarm_coordinator is None:
            return []
        return self._swarm_coordinator.list_swarms(status, limit)

    def cancel_swarm(self, swarm_id: str) -> bool:
        """Cancela un swarm activo."""
        if self._swarm_coordinator is None:
            return False
        return self._swarm_coordinator.cancel_swarm(swarm_id)

    def get_swarm_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del coordinador de enjambre."""
        if self._swarm_coordinator is None:
            return {"status": "disabled"}
        return self._swarm_coordinator.get_stats()

    # --------------------------------------------------------
    # IntelligentRouter (Sprint 5)
    # --------------------------------------------------------
    def analyze_task_route(self, task: str) -> dict[str, Any]:
        """Analiza una tarea y decide la ruta óptima (sin ejecutar)."""
        if self._intelligent_router is None:
            raise RuntimeError("IntelligentRouter no inicializado")
        decision = self._intelligent_router.analyze(task)
        self._metrics["routes_decided"] += 1
        return decision.to_dict()

    async def route_and_execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        from_agent: str = "api",
        force_route: str | None = None,
    ) -> dict[str, Any]:
        """Analiza, decide ruta, y ejecuta automáticamente."""
        if self._intelligent_router is None:
            raise RuntimeError("IntelligentRouter no inicializado")
        self._metrics["routes_decided"] += 1
        return await self._intelligent_router.route_and_execute(
            task,
            context,
            from_agent,
            force_route,
        )

    def get_router_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del router."""
        if self._intelligent_router is None:
            return {"status": "disabled"}
        return self._intelligent_router.get_stats()

    def get_route_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de decisiones del router."""
        if self._intelligent_router is None:
            return []
        return self._intelligent_router.get_decision_history(limit)

    # --------------------------------------------------------
    # ConsensusProtocol (Sprint 5)
    # --------------------------------------------------------
    def create_consensus_proposal(
        self,
        question: str,
        options: list[str],
        voters: list[str],
        mode: str = "majority",
    ) -> dict[str, Any]:
        """Crea una propuesta de consenso."""
        if self._consensus_protocol is None:
            raise RuntimeError("ConsensusProtocol no inicializado")
        from .consensus_protocol import ConsensusMode

        proposal = self._consensus_protocol.create_proposal(
            question=question,
            options=options,
            voters=voters,
            mode=ConsensusMode(mode),
        )
        self._metrics["consensus_proposals"] += 1
        return proposal.to_dict()

    def cast_consensus_vote(
        self,
        proposal_id: str,
        voter: str,
        choice: str,
        confidence: float = 0.8,
        reason: str = "",
    ) -> dict[str, Any] | None:
        """Registra un voto."""
        if self._consensus_protocol is None:
            raise RuntimeError("ConsensusProtocol no inicializado")
        vote = self._consensus_protocol.cast_vote(
            proposal_id,
            voter,
            choice,
            confidence,
            reason,
        )
        return vote.to_dict() if vote else None

    def resolve_consensus(self, proposal_id: str) -> dict[str, Any]:
        """Resuelve una propuesta."""
        if self._consensus_protocol is None:
            raise RuntimeError("ConsensusProtocol no inicializado")
        return self._consensus_protocol.resolve(proposal_id).to_dict()

    def quick_consensus(
        self,
        question: str,
        options: list[str],
        agent_votes: dict[str, tuple[str, float, str]],
        mode: str = "weighted",
    ) -> dict[str, Any]:
        """Atajo: propuesta + votos + resolución en un paso."""
        if self._consensus_protocol is None:
            raise RuntimeError("ConsensusProtocol no inicializado")
        from .consensus_protocol import ConsensusMode

        return self._consensus_protocol.quick_consensus(
            question,
            options,
            agent_votes,
            ConsensusMode(mode),
        ).to_dict()

    def list_consensus_proposals(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista propuestas de consenso."""
        if self._consensus_protocol is None:
            return []
        return self._consensus_protocol.list_proposals(status, limit)

    def get_consensus_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del consenso."""
        if self._consensus_protocol is None:
            return {"status": "disabled"}
        return self._consensus_protocol.get_stats()

    # --------------------------------------------------------
    # AgentObservatory (Sprint 5)
    # --------------------------------------------------------
    def get_observatory_timeline(
        self,
        limit: int = 50,
        event_type: str | None = None,
        agent: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retorna el timeline del observatorio."""
        if self._agent_observatory is None:
            return []
        return self._agent_observatory.get_timeline(
            limit=limit,
            event_type=event_type,
            agent=agent,
            severity=severity,
        )

    async def get_ecosystem_snapshot(self) -> dict[str, Any]:
        """Retorna un snapshot completo del ecosistema."""
        if self._agent_observatory is None:
            return {"status": "disabled"}
        return await self._agent_observatory.get_ecosystem_snapshot()

    def record_observatory_event(
        self,
        event_type: str,
        summary: str,
        agent: str | None = None,
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Registra un evento en el observatorio."""
        if self._agent_observatory is None:
            raise RuntimeError("AgentObservatory no inicializado")
        self._metrics["observatory_events"] += 1
        return self._agent_observatory.record_event(
            event_type,
            summary,
            agent,
            severity,
            data,
        )

    def get_observatory_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del observatorio."""
        if self._agent_observatory is None:
            return {"status": "disabled"}
        return self._agent_observatory.get_stats()

    # --------------------------------------------------------
    # WorkflowEngine (Sprint 3)
    # --------------------------------------------------------
    async def execute_workflow(
        self,
        graph_name: str,
        initial_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ejecuta un workflow registrado."""
        if self._workflow_engine is None:
            raise RuntimeError("WorkflowEngine no inicializado")
        self._metrics["workflows_executed"] += 1
        return await self._workflow_engine.execute(graph_name, initial_state)

    async def resume_workflow(
        self,
        workflow_id: str,
        human_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Reanuda un workflow pausado."""
        if self._workflow_engine is None:
            raise RuntimeError("WorkflowEngine no inicializado")
        return await self._workflow_engine.resume(workflow_id, human_input)

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Retorna estado de un workflow."""
        if self._workflow_engine is None:
            return None
        return self._workflow_engine.get_workflow(workflow_id)

    def list_workflows(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista workflows."""
        if self._workflow_engine is None:
            return []
        return self._workflow_engine.list_workflows(status, limit)

    def list_graphs(self) -> list[dict[str, Any]]:
        """Lista grafos registrados."""
        if self._workflow_engine is None:
            return []
        return self._workflow_engine.list_graphs()

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancela un workflow."""
        if self._workflow_engine is None:
            return False
        return self._workflow_engine.cancel_workflow(workflow_id)

    def get_workflow_events(
        self,
        workflow_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retorna eventos de un workflow."""
        if self._workflow_engine is None:
            return []
        return self._workflow_engine.get_workflow_events(workflow_id, limit)

    def get_workflow_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del WorkflowEngine."""
        if self._workflow_engine is None:
            return {"status": "disabled"}
        return self._workflow_engine.get_stats()
