"""
Agent Daemon - Loop autónomo de ejecución en background.

Este daemon es el corazón de la autonomía real del ecosistema.
Corre como un proceso background (asyncio), escucha tareas en la cola
de prioridad del Redis Message Bus, las ejecuta sin intervención humana,
y reporta resultados de vuelta via pub/sub.

Características:
  - Ejecución autónoma sin humano en el loop
  - Worker pool configurable (N workers concurrentes)
  - Heartbeat periódico para monitoreo
  - Retry automático con backoff exponencial (max 3 intentos)
  - Enruta tareas al agente correcto según capabilities
  - Notificación de resultados via RedisMessageBus
  - Graceful shutdown con drain de tareas pendientes
  - Métricas de ejecución en tiempo real

Usage:
    # Como proceso independiente
    daemon = AgentDaemon(workers=4)
    await daemon.start()

    # Encolar tarea autónoma desde cualquier parte del sistema
    bus = await get_message_bus()
    await bus.enqueue_priority(
        "tasks",
        {"agent": "explorer", "task": "analiza dependencias del proyecto"},
        priority=Priority.HIGH,
        from_agent="planner",
    )
    # El daemon la toma, ejecuta el agente, y publica resultado en:
    # "agent.explorer.results" y "tasks.completed"
"""
# mypy: ignore-errors

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ._daemon_mixin_advanced import DaemonAdvancedMixin
from ._daemon_mixin_coordination import DaemonCoordinationMixin
from ._daemon_mixin_planning import DaemonPlanningMixin

logger = logging.getLogger("antigravity.agent_daemon")

# Paths del ecosistema
_BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_BASE_DIR / ".agent"))

# ============================================================
# Constantes
# ============================================================
TASK_QUEUE = "tasks"
RESULTS_CHANNEL_TPL = "agent.{agent}.results"
COMPLETED_CHANNEL = "tasks.completed"
FAILED_CHANNEL = "tasks.failed"
HEARTBEAT_INTERVAL = 10.0  # segundos entre heartbeats
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2.0  # segundos (se dobla con cada retry)
WORKER_IDLE_TIMEOUT = 5.0  # segundos de espera cuando cola vacía

# Nombres de parámetros enable_* del constructor (para lite mode)
_SUBSYSTEM_PARAM_NAMES: tuple[str, ...] = (
    "enable_memory",
    "enable_planner",
    "enable_anomaly_detection",
    "enable_telemetry",
    "enable_self_improvement",
    "enable_workflows",
    "enable_reactive",
    "enable_negotiation",
    "enable_swarm",
    "enable_router",
    "enable_consensus",
    "enable_observatory",
    "enable_reputation",
    "enable_topology",
    "enable_chronicle",
    "enable_circuit_breaker",
    "enable_prefetch",
    "enable_contracts",
    "enable_genome",
    "enable_distillation",
    "enable_adversarial",
    "enable_ws_bridge",
    "enable_dashboard",
    "enable_alerts",
    "enable_federation",
    "enable_marketplace",
    "enable_trust",
    "enable_metacognition",
    "enable_goals",
    "enable_emergent",
)


# ============================================================
# Estado de la tarea
# ============================================================
class TaskStatus(Enum):
    """Estado del ciclo de vida de una tarea."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DLQ = "dlq"


@dataclass
class TaskRecord:
    """Registro de una tarea ejecutada por el daemon."""

    task_id: str
    agent_name: str
    task_description: str
    from_agent: str
    status: TaskStatus = TaskStatus.QUEUED
    result: str | None = None
    error: str | None = None
    retries: int = 0
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "from_agent": self.from_agent,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "retries": self.retries,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


# ============================================================
# Agent Daemon
# ============================================================
class AgentDaemon(DaemonPlanningMixin, DaemonCoordinationMixin, DaemonAdvancedMixin):
    """
    Daemon autónomo que ejecuta tareas de agentes en background.

    El daemon:
    1. Escucha continuamente la cola de prioridad de tareas
    2. Asigna cada tarea a un worker disponible
    3. El worker ejecuta el agente correspondiente
    4. Publica el resultado en el canal de resultados
    5. Envía heartbeats periódicos
    6. Maneja reintentos con backoff exponencial
    """

    def __init__(
        self,
        workers: int = 3,
        queue_name: str = TASK_QUEUE,
        daemon_id: str | None = None,
        enable_a2a: bool = True,
        enable_memory: bool = True,
        enable_planner: bool = True,
        enable_anomaly_detection: bool = True,
        enable_telemetry: bool = True,
        enable_self_improvement: bool = True,
        enable_workflows: bool = True,
        enable_reactive: bool = True,
        enable_negotiation: bool = True,
        enable_swarm: bool = True,
        enable_router: bool = True,
        enable_consensus: bool = True,
        enable_observatory: bool = True,
        enable_reputation: bool = True,
        enable_topology: bool = True,
        enable_chronicle: bool = True,
        enable_circuit_breaker: bool = True,
        enable_prefetch: bool = True,
        enable_contracts: bool = True,
        enable_genome: bool = True,
        enable_distillation: bool = True,
        enable_adversarial: bool = True,
        enable_ws_bridge: bool = True,
        enable_dashboard: bool = True,
        enable_alerts: bool = True,
        enable_federation: bool = True,
        enable_marketplace: bool = True,
        enable_trust: bool = True,
        enable_metacognition: bool = True,
        enable_goals: bool = True,
        enable_emergent: bool = True,
    ) -> None:
        self._workers = workers
        self._queue_name = queue_name
        self._daemon_id = daemon_id or f"daemon-{uuid.uuid4().hex[:8]}"
        self._running = False

        # Pool de semáforos para limitar workers concurrentes
        self._semaphore: asyncio.Semaphore | None = None

        # Historial de tareas (últimas 500)
        self._task_history: list[TaskRecord] = []
        self._active_tasks: dict[str, TaskRecord] = {}

        # Métricas
        self._metrics = {
            "tasks_processed": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "tasks_dlq": 0,
            "uptime_start": 0.0,
            "a2a_conversations": 0,
            "plans_executed": 0,
            "anomalies_detected": 0,
            "workflows_executed": 0,
            "improvements_proposed": 0,
            "reactive_triggers": 0,
            "auctions_total": 0,
            "swarms_executed": 0,
            "routes_decided": 0,
            "consensus_proposals": 0,
            "observatory_events": 0,
            "reputation_outcomes": 0,
            "topology_interactions": 0,
            "chronicle_entries": 0,
            "circuit_breaker_checks": 0,
            "prefetch_predictions": 0,
            "contract_executions": 0,
            "genome_evaluations": 0,
            "distillation_transfers": 0,
            "adversarial_challenges": 0,
            "ws_broadcasts": 0,
            "alerts_fired": 0,
            "federation_delegations": 0,
            "marketplace_acquisitions": 0,
            "metacognition_decisions": 0,
            "goals_created": 0,
            "emergent_observations": 0,
        }

        self._bus = None
        self._worker_tasks: list[asyncio.Task] = []
        self._heartbeat_task: asyncio.Task | None = None

        # A2A y AgentMemory
        self._enable_a2a = enable_a2a
        self._enable_memory = enable_memory
        self._a2a_inbox_tasks: dict[str, asyncio.Task] = {}
        self._agent_memories: dict[str, Any] = {}

        # MetaPlanner y AnomalyDetector (Sprint 2)
        self._enable_planner = enable_planner
        self._enable_anomaly = enable_anomaly_detection
        self._meta_planner: Any = None
        self._anomaly_detector: Any = None

        # Telemetry, SelfImprovement, WorkflowEngine (Sprint 3)
        self._enable_telemetry = enable_telemetry
        self._enable_self_improvement = enable_self_improvement
        self._enable_workflows = enable_workflows
        self._self_improver: Any = None
        self._workflow_engine: Any = None

        # ReactiveEvents, Negotiation, SwarmCoordinator (Sprint 4)
        self._enable_reactive = enable_reactive
        self._enable_negotiation = enable_negotiation
        self._enable_swarm = enable_swarm
        self._reactive_system: Any = None
        self._negotiation_protocol: Any = None
        self._swarm_coordinator: Any = None

        # IntelligentRouter, ConsensusProtocol, AgentObservatory (Sprint 5)
        self._enable_router = enable_router
        self._enable_consensus = enable_consensus
        self._enable_observatory = enable_observatory
        self._intelligent_router: Any = None
        self._consensus_protocol: Any = None
        self._agent_observatory: Any = None

        # AgentReputation, AdaptiveTopology, EventChronicle (Sprint 6)
        self._enable_reputation = enable_reputation
        self._enable_topology = enable_topology
        self._enable_chronicle = enable_chronicle
        self._agent_reputation: Any = None
        self._adaptive_topology: Any = None
        self._event_chronicle: Any = None

        # CircuitBreaker, PredictivePrefetch, AgentContracts (Sprint 7)
        self._enable_circuit_breaker = enable_circuit_breaker
        self._enable_prefetch = enable_prefetch
        self._enable_contracts = enable_contracts
        self._circuit_breaker: Any = None
        self._predictive_prefetch: Any = None
        self._contract_manager: Any = None

        # GenomeManager, KnowledgeDistiller, AdversarialArena (Sprint 8)
        self._enable_genome = enable_genome
        self._enable_distillation = enable_distillation
        self._enable_adversarial = enable_adversarial
        self._genome_manager: Any = None
        self._knowledge_distiller: Any = None
        self._adversarial_arena: Any = None

        # Sprint 9A: Nervous System
        self._enable_ws_bridge = enable_ws_bridge
        self._enable_dashboard = enable_dashboard
        self._enable_alerts = enable_alerts
        self._ws_bridge: Any = None
        self._dashboard_feed: Any = None
        self._alert_engine: Any = None

        # Sprint 9B: Federation
        self._enable_federation = enable_federation
        self._enable_marketplace = enable_marketplace
        self._enable_trust = enable_trust
        self._agent_federation: Any = None
        self._capability_marketplace: Any = None
        self._trust_network: Any = None

        # Sprint 9C: Cortex
        self._enable_metacognition = enable_metacognition
        self._enable_goals = enable_goals
        self._enable_emergent = enable_emergent
        self._metacognition: Any = None
        self._goal_autonomy: Any = None
        self._emergent_behavior: Any = None

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    def _get_subsystem_registry(self) -> list[tuple[str, str, str, str]]:
        """Retorna la lista de subsistemas a inicializar.

        Cada tupla: (flag_attr, module_path, factory_name, instance_attr).
        Las factorías se invocan con (bus) excepto las marcadas especialmente.

        Returns:
            Lista de tuplas (enable_flag, module, factory, target_attr).
        """
        return [
            # Sprint 2
            ("_enable_planner", ".meta_planner", "MetaPlanner", "_meta_planner"),
            ("_enable_anomaly", ".anomaly_detector", "AnomalyDetector", "_anomaly_detector"),
            # Sprint 3 — telemetry se maneja aparte (no usa bus)
            (
                "_enable_self_improvement",
                ".self_improvement",
                "get_self_improver",
                "_self_improver",
            ),
            ("_enable_workflows", ".workflow_engine", "get_workflow_engine", "_workflow_engine"),
            # Sprint 4
            (
                "_enable_reactive",
                ".reactive_event_system",
                "get_reactive_system",
                "_reactive_system",
            ),
            (
                "_enable_negotiation",
                ".agent_negotiation",
                "get_negotiation_protocol",
                "_negotiation_protocol",
            ),
            ("_enable_swarm", ".swarm_coordinator", "get_swarm_coordinator", "_swarm_coordinator"),
            # Sprint 5
            (
                "_enable_router",
                ".intelligent_router",
                "get_intelligent_router",
                "_intelligent_router",
            ),
            (
                "_enable_consensus",
                ".consensus_protocol",
                "get_consensus_protocol",
                "_consensus_protocol",
            ),
            (
                "_enable_observatory",
                ".agent_observatory",
                "get_agent_observatory",
                "_agent_observatory",
            ),
            # Sprint 6
            (
                "_enable_reputation",
                ".agent_reputation",
                "get_agent_reputation",
                "_agent_reputation",
            ),
            (
                "_enable_topology",
                ".adaptive_topology",
                "get_adaptive_topology",
                "_adaptive_topology",
            ),
            ("_enable_chronicle", ".event_chronicle", "get_event_chronicle", "_event_chronicle"),
            # Sprint 7
            (
                "_enable_circuit_breaker",
                ".circuit_breaker",
                "get_circuit_breaker",
                "_circuit_breaker",
            ),
            (
                "_enable_prefetch",
                ".predictive_prefetch",
                "get_predictive_prefetch",
                "_predictive_prefetch",
            ),
            ("_enable_contracts", ".agent_contracts", "get_contract_manager", "_contract_manager"),
            # Sprint 8
            ("_enable_genome", ".agent_genome", "get_genome_manager", "_genome_manager"),
            (
                "_enable_distillation",
                ".knowledge_distillation",
                "get_knowledge_distiller",
                "_knowledge_distiller",
            ),
            (
                "_enable_adversarial",
                ".adversarial_testing",
                "get_adversarial_arena",
                "_adversarial_arena",
            ),
            # Sprint 9A: Nervous System
            ("_enable_ws_bridge", ".ws_bridge", "get_ws_bridge", "_ws_bridge"),
            ("_enable_dashboard", ".dashboard_feed", "get_dashboard_feed", "_dashboard_feed"),
            ("_enable_alerts", ".alert_engine", "get_alert_engine", "_alert_engine"),
            # Sprint 9B: Federation
            (
                "_enable_federation",
                ".agent_federation",
                "get_agent_federation",
                "_agent_federation",
            ),
            (
                "_enable_marketplace",
                ".capability_marketplace",
                "get_capability_marketplace",
                "_capability_marketplace",
            ),
            ("_enable_trust", ".trust_network", "get_trust_network", "_trust_network"),
            # Sprint 9C: Cortex
            ("_enable_metacognition", ".metacognition", "get_metacognition", "_metacognition"),
            ("_enable_goals", ".goal_autonomy", "get_goal_autonomy", "_goal_autonomy"),
            (
                "_enable_emergent",
                ".emergent_behavior",
                "get_emergent_behavior",
                "_emergent_behavior",
            ),
        ]

    async def _init_subsystem(self, module_path: str, factory_name: str, target_attr: str) -> None:
        """Importa e inicializa un subsistema individual.

        Args:
            module_path: Ruta relativa del módulo (e.g. '.meta_planner').
            factory_name: Nombre de la clase o función factoría a importar.
            target_attr: Atributo de self donde almacenar la instancia.
        """
        import importlib

        mod = importlib.import_module(module_path, package=__package__)
        factory = getattr(mod, factory_name)

        # Detectar si la factoría necesita bus o no (heurística por nombre)
        needs_no_args = factory_name in ("get_self_improver",)
        is_class_constructor = factory_name[0].isupper()

        if needs_no_args:
            instance = factory()
        elif is_class_constructor:
            instance = factory(self._bus)
        else:
            # Las factorías async get_* que reciben bus
            import asyncio as _aio

            result = (
                factory(self._bus)
                if "bus" in factory.__code__.co_varnames[:2]
                else factory(self._bus)
            )
            if _aio.iscoroutine(result):
                instance = await result
            else:
                instance = result

        setattr(self, target_attr, instance)

        # Post-init hooks para subsistemas que requieren start()
        if target_attr in ("_reactive_system", "_agent_observatory"):
            if hasattr(instance, "start"):
                await instance.start()
        if target_attr == "_negotiation_protocol":
            if hasattr(instance, "auto_discover_agents"):
                instance.auto_discover_agents()

        label = factory_name.replace("get_", "").replace("_", " ").title()
        logger.info("[%s] %s inicializado", self._daemon_id, label)

    async def _init_telemetry(self) -> None:
        """Inicializa telemetry (caso especial: no usa bus ni factoría estándar)."""
        if not self._enable_telemetry:
            return
        try:
            from .telemetry import setup_telemetry

            setup_telemetry(service_name=f"antigravity.daemon.{self._daemon_id}")
            logger.info("[%s] Telemetry inicializado", self._daemon_id)
        except Exception as e:
            logger.warning("[%s] Telemetry no disponible: %s", self._daemon_id, e)

    async def _init_workflow_engine(self) -> None:
        """Inicializa WorkflowEngine (caso especial: usa keyword arg bus=)."""
        if not self._enable_workflows:
            return
        try:
            from .workflow_engine import get_workflow_engine

            self._workflow_engine = get_workflow_engine(bus=self._bus)
            logger.info("[%s] WorkflowEngine inicializado", self._daemon_id)
        except Exception as e:
            logger.warning("[%s] WorkflowEngine no disponible: %s", self._daemon_id, e)

    async def _init_all_subsystems(self) -> None:
        """Inicializa todos los subsistemas registrados según sus flags.

        Itera sobre el registry de subsistemas e inicializa los habilitados.
        Fallos individuales se loguean como warnings sin detener el arranque.
        """
        await self._init_telemetry()
        await self._init_workflow_engine()

        # Subsistemas excluidos del loop genérico (ya manejados arriba)
        _skip_targets = {"_workflow_engine"}

        for flag_attr, module_path, factory_name, target_attr in self._get_subsystem_registry():
            if target_attr in _skip_targets:
                continue
            if not getattr(self, flag_attr, False):
                continue
            try:
                await self._init_subsystem(module_path, factory_name, target_attr)
            except Exception as e:
                label = factory_name.replace("get_", "").replace("_", " ").title()
                logger.warning("[%s] %s no disponible: %s", self._daemon_id, label, e)

    async def ensure_subsystem(self, subsystem_name: str) -> bool:
        """Inicializa un subsistema bajo demanda si no está cargado.

        Args:
            subsystem_name: Nombre interno sin prefijo (e.g. 'genome_manager').

        Returns:
            True si el subsistema está disponible, False si falló.
        """
        target_attr = f"_{subsystem_name}"
        if getattr(self, target_attr, None) is not None:
            return True  # Ya cargado

        for flag_attr, module_path, factory_name, t_attr in self._get_subsystem_registry():
            if t_attr == target_attr:
                setattr(self, flag_attr, True)
                try:
                    await self._init_subsystem(module_path, factory_name, t_attr)
                    logger.info("[%s] Lazy init: %s cargado", self._daemon_id, subsystem_name)
                    return True
                except Exception as e:
                    logger.warning(
                        "[%s] Lazy init de %s falló: %s", self._daemon_id, subsystem_name, e
                    )
                    return False
        logger.warning(
            "[%s] Subsistema '%s' no encontrado en registry", self._daemon_id, subsystem_name
        )
        return False

    async def start(self) -> None:
        """Inicia el daemon y sus workers."""
        from .redis_message_bus import get_message_bus

        self._bus = await get_message_bus()
        self._semaphore = asyncio.Semaphore(self._workers)
        self._running = True
        self._metrics["uptime_start"] = time.time()

        await self._init_all_subsystems()

        logger.info(
            "[%s] AgentDaemon iniciado con %d workers. Cola: '%s'",
            self._daemon_id,
            self._workers,
            self._queue_name,
        )

        # Publicar evento de inicio (best-effort, no bloquear arranque)
        try:
            await asyncio.wait_for(
                self._bus.publish(
                    "daemon.lifecycle",
                    {"event": "started", "daemon_id": self._daemon_id, "workers": self._workers},
                    from_agent=self._daemon_id,
                ),
                timeout=2.0,
            )
        except Exception as e:
            logger.debug(
                "[%s] No se pudo publicar daemon.lifecycle started: %s", self._daemon_id, e
            )

        # Iniciar heartbeat
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name=f"{self._daemon_id}-heartbeat"
        )

        # Iniciar workers
        for i in range(self._workers):
            task = asyncio.create_task(
                self._worker_loop(worker_id=i),
                name=f"{self._daemon_id}-worker-{i}",
            )
            self._worker_tasks.append(task)

    async def stop(self, drain_timeout: float = 30.0) -> None:
        """Para el daemon gracefully, esperando que las tareas activas terminen."""
        logger.info("[%s] Iniciando shutdown graceful...", self._daemon_id)
        self._running = False

        # Detener subsistemas async para evitar tareas huérfanas
        if self._agent_observatory and hasattr(self._agent_observatory, "stop"):
            try:
                await self._agent_observatory.stop()
            except Exception as e:
                logger.debug("[%s] Error deteniendo AgentObservatory: %s", self._daemon_id, e)

        if self._reactive_system and hasattr(self._reactive_system, "stop"):
            try:
                await self._reactive_system.stop()
            except Exception as e:
                logger.debug("[%s] Error deteniendo ReactiveEventSystem: %s", self._daemon_id, e)

        # Esperar que las tareas activas terminen (hasta drain_timeout)
        if self._active_tasks:
            logger.info(
                "[%s] Esperando %d tareas activas...", self._daemon_id, len(self._active_tasks)
            )
            deadline = time.monotonic() + drain_timeout
            while self._active_tasks and time.monotonic() < deadline:
                await asyncio.sleep(0.5)

        # Cancelar workers
        for task in self._worker_tasks:
            task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

        if self._heartbeat_task:
            await asyncio.gather(self._heartbeat_task, return_exceptions=True)
            self._heartbeat_task = None

        # Publicar evento de parada
        if self._bus:
            await self._bus.publish(
                "daemon.lifecycle",
                {"event": "stopped", "daemon_id": self._daemon_id, "metrics": self._metrics},
                from_agent=self._daemon_id,
            )

        logger.info("[%s] AgentDaemon detenido. Métricas: %s", self._daemon_id, self._metrics)

    # --------------------------------------------------------
    # Worker loop
    # --------------------------------------------------------
    async def _worker_loop(self, worker_id: int) -> None:
        """Loop principal de un worker: dequeue → ejecutar → publicar resultado."""
        worker_name = f"{self._daemon_id}-worker-{worker_id}"
        logger.debug("[%s] Worker iniciado", worker_name)

        while self._running:
            try:
                msg = await self._bus.dequeue_priority(
                    self._queue_name,
                    timeout_seconds=WORKER_IDLE_TIMEOUT,
                )

                if msg is None:
                    continue  # Cola vacía, volver a intentar

                payload = msg.payload
                agent_name = payload.get("agent", "")
                task_description = payload.get("task", "")
                from_agent = msg.from_agent
                task_id = payload.get("task_id", str(uuid.uuid4()))
                retry_count = payload.get("_retry", 0)

                if not agent_name or not task_description:
                    logger.warning("[%s] Tarea inválida (sin agent/task): %s", worker_name, payload)
                    continue

                async with self._semaphore:
                    await self._execute_task(
                        task_id=task_id,
                        agent_name=agent_name,
                        task_description=task_description,
                        from_agent=from_agent,
                        retry_count=retry_count,
                        context=payload.get("context", {}),
                        original_msg=msg,
                    )

            except asyncio.CancelledError:
                logger.debug("[%s] Worker cancelado", worker_name)
                return
            except Exception as e:
                logger.error("[%s] Error inesperado en worker: %s", worker_name, e)
                self._metrics["tasks_failed"] += 1
                await asyncio.sleep(1)

    # --------------------------------------------------------
    # Ejecutar tarea
    # --------------------------------------------------------
    async def _execute_task(
        self,
        task_id: str,
        agent_name: str,
        task_description: str,
        from_agent: str,
        retry_count: int = 0,
        context: dict | None = None,
        original_msg: Any = None,
    ) -> None:
        """Ejecuta un agente y publica el resultado."""
        record = TaskRecord(
            task_id=task_id,
            agent_name=agent_name,
            task_description=task_description,
            from_agent=from_agent,
            status=TaskStatus.RUNNING,
            retries=retry_count,
            started_at=time.time(),
        )
        self._active_tasks[task_id] = record
        self._metrics["tasks_processed"] += 1

        logger.info(
            "[%s] Ejecutando agente '%s': %.60s... (retry=%d)",
            self._daemon_id,
            agent_name,
            task_description,
            retry_count,
        )

        # Notificar inicio
        await self._bus.publish(
            f"agent.{agent_name}.status",
            {"task_id": task_id, "status": "running", "ts": time.time()},
            from_agent=self._daemon_id,
        )

        # Telemetry: tracing span para la ejecución completa (Sprint 3)
        trace_ctx = self._get_trace_context(agent_name, task_description, task_id)

        try:
            with trace_ctx:
                result = await asyncio.wait_for(
                    self._run_agent(agent_name, task_description, context or {}),
                    timeout=300.0,  # 5 minutos máximo por tarea
                )

            record.status = TaskStatus.COMPLETED
            record.result = result
            record.completed_at = time.time()
            record.duration_seconds = record.completed_at - record.started_at
            self._metrics["tasks_succeeded"] += 1

            logger.info(
                "[%s] Tarea completada '%s' en %.1fs",
                self._daemon_id,
                task_id,
                record.duration_seconds,
            )

            # Publicar resultado
            result_payload = {
                "task_id": task_id,
                "agent": agent_name,
                "task": task_description,
                "result": result,
                "duration_seconds": record.duration_seconds,
                "from_agent": from_agent,
                "ts": time.time(),
            }
            await self._bus.publish(
                RESULTS_CHANNEL_TPL.format(agent=agent_name),
                result_payload,
                from_agent=self._daemon_id,
            )
            await self._bus.publish(
                COMPLETED_CHANNEL,
                result_payload,
                from_agent=self._daemon_id,
            )

            # Almacenar en AgentMemory para el siguiente ciclo
            if self._enable_memory:
                self._store_in_agent_memory(
                    agent_name,
                    task_description,
                    result,
                    context or {},
                    task_id,
                    record.duration_seconds,
                )

            # Registrar ejecución exitosa en AnomalyDetector
            self._record_anomaly(agent_name, record.duration_seconds or 0, True, task_id)

            # Registrar en Telemetry metrics (Sprint 3)
            self._record_telemetry(agent_name, record.duration_seconds or 0, True)

            # Registrar en SelfImprover (Sprint 3)
            self._record_self_improvement(
                agent_name,
                task_description,
                True,
                record.duration_seconds or 0,
                [],
            )

        except TimeoutError:
            error = f"Timeout: el agente '{agent_name}' excedió 300s"
            self._record_anomaly(agent_name, 300.0, False, task_id)
            self._record_telemetry(agent_name, 300.0, False)
            self._record_self_improvement(agent_name, task_description, False, 300.0, [error])
            await self._handle_failure(record, error, original_msg)

        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            duration = time.time() - record.started_at
            self._record_anomaly(agent_name, duration, False, task_id)
            self._record_telemetry(agent_name, duration, False)
            self._record_self_improvement(agent_name, task_description, False, duration, [error])
            await self._handle_failure(record, error, original_msg)

        finally:
            self._active_tasks.pop(task_id, None)
            if len(self._task_history) >= 500:
                self._task_history = self._task_history[-400:]
            self._task_history.append(record)

    async def _handle_failure(
        self,
        record: TaskRecord,
        error: str,
        original_msg: Any,
    ) -> None:
        """Maneja un fallo con retry backoff o envío a DLQ."""
        record.error = error
        record.completed_at = time.time()
        record.duration_seconds = record.completed_at - record.started_at

        if record.retries < MAX_RETRIES:
            # Retry con backoff exponencial
            delay = BASE_RETRY_DELAY * (2**record.retries)
            record.status = TaskStatus.RETRYING
            self._metrics["tasks_retried"] += 1

            logger.warning(
                "[%s] Tarea %s fallida (%s). Reintento %d/%d en %.0fs",
                self._daemon_id,
                record.task_id,
                error,
                record.retries + 1,
                MAX_RETRIES,
                delay,
            )

            await asyncio.sleep(delay)

            # Re-encolar con contador de retry incrementado
            from .redis_message_bus import Priority

            await self._bus.enqueue_priority(
                self._queue_name,
                {
                    "agent": record.agent_name,
                    "task": record.task_description,
                    "task_id": record.task_id,
                    "_retry": record.retries + 1,
                },
                priority=Priority.HIGH,
                from_agent=self._daemon_id,
            )
        else:
            # Máximo de reintentos alcanzado → DLQ
            record.status = TaskStatus.DLQ
            self._metrics["tasks_dlq"] += 1
            self._metrics["tasks_failed"] += 1

            logger.error(
                "[%s] Tarea %s enviada a DLQ después de %d reintentos: %s",
                self._daemon_id,
                record.task_id,
                MAX_RETRIES,
                error,
            )

            if original_msg:
                await self._bus.send_to_dlq(original_msg, reason=error)

            await self._bus.publish(
                FAILED_CHANNEL,
                {
                    "task_id": record.task_id,
                    "agent": record.agent_name,
                    "error": error,
                    "retries": record.retries,
                    "ts": time.time(),
                },
                from_agent=self._daemon_id,
            )

    # --------------------------------------------------------
    # Ejecutar agente (integración con el ecosistema)
    # --------------------------------------------------------
    async def _run_agent(
        self,
        agent_name: str,
        task: str,
        context: dict,
    ) -> str:
        """
        Ejecuta un agente del ecosistema y retorna su output.
        Usa el Orchestrator del ecosistema si está disponible,
        o el script directo del agente como fallback.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._run_agent_sync,
            agent_name,
            task,
            context,
        )

    def _run_agent_sync(self, agent_name: str, task: str, context: dict) -> str:
        """Ejecuta el agente en un thread executor (blocking)."""
        # Intentar invocar via script del ecosistema
        agent_dir = _BASE_DIR / ".agent" / "agents" / agent_name
        script = agent_dir / "scripts" / "main.py"

        if script.exists():
            import shlex
            import subprocess

            cmd = shlex.split(f"python {script} --task {shlex.quote(task)}")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=290,
                    cwd=str(_BASE_DIR),
                    env={**os.environ, "ANTIGRAVITY_HOME": str(_BASE_DIR)},
                )
                output = result.stdout.strip() or result.stderr.strip()
                return output or f"Agente '{agent_name}' completado sin output"
            except subprocess.TimeoutExpired:
                raise TimeoutError("Script de agente excedió timeout") from None
            except Exception as e:
                raise RuntimeError(f"Error ejecutando script de agente: {e}") from e

        # Fallback: intentar via invoke-agent.py
        invoke_script = _BASE_DIR / ".agent" / "scripts" / "invoke-agent.py"
        if invoke_script.exists():
            import shlex
            import subprocess

            cmd = ["python", str(invoke_script), agent_name, task, "--json"]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=290,
                    cwd=str(_BASE_DIR),
                    env={**os.environ, "ANTIGRAVITY_HOME": str(_BASE_DIR)},
                )
                return result.stdout.strip() or f"Agente '{agent_name}' completado"
            except Exception as e:
                raise RuntimeError(f"Error invocando agente: {e}") from e

        # Último fallback: agente no encontrado
        raise ValueError(f"Agente '{agent_name}' no encontrado en {agent_dir}")

    # --------------------------------------------------------
    # Heartbeat loop
    # --------------------------------------------------------
    async def _heartbeat_loop(self) -> None:
        """Publica heartbeats periódicos para monitoreo."""
        while self._running:
            try:
                uptime = time.time() - self._metrics["uptime_start"]
                await self._bus.heartbeat(
                    agent_name=self._daemon_id,
                    metadata={
                        "type": "daemon",
                        "workers": self._workers,
                        "active_tasks": len(self._active_tasks),
                        "metrics": {**self._metrics, "uptime_seconds": uptime},
                    },
                )
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug("Error en heartbeat: %s", e)
                await asyncio.sleep(HEARTBEAT_INTERVAL)

    # --------------------------------------------------------
    # API pública (status & control)
    # --------------------------------------------------------
    def get_status(self) -> dict[str, Any]:
        """Retorna el estado actual del daemon."""
        uptime = time.time() - self._metrics["uptime_start"] if self._metrics["uptime_start"] else 0
        return {
            "daemon_id": self._daemon_id,
            "running": self._running,
            "workers": self._workers,
            "active_tasks": len(self._active_tasks),
            "active_task_list": [t.to_dict() for t in self._active_tasks.values()],
            "recent_tasks": [t.to_dict() for t in self._task_history[-10:]],
            "metrics": {**self._metrics, "uptime_seconds": uptime},
        }

    async def submit_task(
        self,
        agent_name: str,
        task: str,
        from_agent: str = "api",
        context: dict | None = None,
        priority_name: str = "NORMAL",
    ) -> str:
        """
        Encola una tarea para ejecución autónoma.
        Retorna el task_id para tracking.
        """
        from .redis_message_bus import Priority

        priority = Priority[priority_name.upper()]
        task_id = str(uuid.uuid4())

        await self._bus.enqueue_priority(
            self._queue_name,
            {
                "agent": agent_name,
                "task": task,
                "task_id": task_id,
                "context": context or {},
            },
            priority=priority,
            from_agent=from_agent,
        )

        logger.info(
            "[%s] Tarea encolada: agent='%s' task='%.50s...' id=%s",
            self._daemon_id,
            agent_name,
            task,
            task_id,
        )
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Busca una tarea por ID (activa o histórica)."""
        if task_id in self._active_tasks:
            return self._active_tasks[task_id].to_dict()
        for record in reversed(self._task_history):
            if record.task_id == task_id:
                return record.to_dict()
        return None

    # --------------------------------------------------------
    # A2A Request-Reply (conversaciones inter-agente)
    # --------------------------------------------------------
    async def a2a_request(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        context: dict | None = None,
        timeout: float = 60.0,
        request_type: str = "question",
    ) -> dict[str, Any]:
        """
        Envía una solicitud A2A a otro agente y espera la respuesta.

        El daemon enruta la solicitud via RedisMessageBus.request()
        y almacena la conversación en AgentMemory.

        Args:
            from_agent: Agente que origina la solicitud.
            to_agent: Agente que debe responder.
            question: La pregunta o instrucción.
            context: Contexto adicional.
            timeout: Tiempo máximo de espera.
            request_type: Tipo de request.

        Returns:
            dict con la respuesta del agente destino.
        """
        result = await self._bus.request(
            from_agent=from_agent,
            to_agent=to_agent,
            question=question,
            context=context,
            timeout=timeout,
            request_type=request_type,
        )

        self._metrics["a2a_conversations"] += 1

        # Almacenar conversación en memoria de ambos agentes
        if self._enable_memory:
            answer_text = json.dumps(result.get("response", {}), default=str)[:500]
            for agent in (from_agent, to_agent):
                mem = self._get_agent_memory(agent)
                if mem:
                    mem.store_conversation(
                        correlation_id=str(uuid.uuid4()),
                        from_agent=from_agent,
                        to_agent=to_agent,
                        question=question,
                        answer=answer_text,
                        request_type=request_type,
                    )

        return result

    async def register_a2a_handler(
        self,
        agent_name: str,
    ) -> None:
        """
        Registra un handler A2A para un agente.

        El handler ejecuta la tarea del agente cuando recibe un request A2A
        y responde automáticamente con el resultado.
        """
        if not self._enable_a2a or self._bus is None:
            return

        async def _handle_a2a_request(msg: Any) -> None:
            """Handler que procesa requests A2A entrantes."""
            from .redis_message_bus import BusMessage

            if not isinstance(msg, BusMessage):
                return

            question = msg.payload.get("question", "")
            req_context = msg.payload.get("context", {})
            req_type = msg.payload.get("type", "question")

            logger.info(
                "[%s] A2A request recibido de '%s': %.60s...",
                agent_name,
                msg.from_agent,
                question,
            )

            try:
                # Ejecutar el agente con la pregunta como tarea
                result = await asyncio.wait_for(
                    self._run_agent(agent_name, question, req_context),
                    timeout=120.0,
                )

                await self._bus.reply(
                    msg,
                    response={
                        "answer": result,
                        "agent": agent_name,
                        "request_type": req_type,
                    },
                    status="completed",
                )

                # Almacenar en memoria
                if self._enable_memory:
                    mem = self._get_agent_memory(agent_name)
                    if mem:
                        mem.store_conversation(
                            correlation_id=msg.correlation_id or "",
                            from_agent=msg.from_agent,
                            to_agent=agent_name,
                            question=question,
                            answer=result[:500],
                            request_type=req_type,
                        )

            except Exception as e:
                logger.error("[%s] Error procesando A2A request: %s", agent_name, e)
                try:
                    await self._bus.reply(
                        msg,
                        response={"error": str(e), "agent": agent_name},
                        status="error",
                    )
                except Exception as reply_err:
                    logger.warning("[%s] No se pudo enviar reply A2A: %s", agent_name, reply_err)

        task = await self._bus.subscribe_inbox(agent_name, _handle_a2a_request)
        self._a2a_inbox_tasks[agent_name] = task
        logger.info("[%s] A2A handler registrado para '%s'", self._daemon_id, agent_name)

    # --------------------------------------------------------
    # AgentMemory helpers
    # --------------------------------------------------------
    def _get_agent_memory(self, agent_name: str) -> Any:
        """Obtiene la instancia de AgentMemory para un agente."""
        if agent_name not in self._agent_memories:
            try:
                from .agent_memory import get_agent_memory

                self._agent_memories[agent_name] = get_agent_memory(agent_name)
            except Exception as e:
                logger.debug("AgentMemory no disponible para %s: %s", agent_name, e)
                return None
        return self._agent_memories[agent_name]

    def _store_in_agent_memory(
        self,
        agent_name: str,
        task: str,
        result: str,
        context: dict,
        task_id: str,
        duration: float | None,
    ) -> None:
        """Almacena el resultado de una tarea en la memoria del agente."""
        mem = self._get_agent_memory(agent_name)
        if mem is None:
            return
        try:
            mem.store_output(
                task=task,
                result=result[:2000],
                context=context,
                task_id=task_id,
                duration_seconds=duration,
            )
        except Exception as e:
            logger.debug("Error almacenando en AgentMemory: %s", e)

    def get_agent_memory_stats(self, agent_name: str) -> dict[str, Any] | None:
        """Retorna estadísticas de la memoria de un agente."""
        mem = self._get_agent_memory(agent_name)
        if mem is None:
            return None
        return mem.get_stats()

    def recall_agent_context(
        self,
        agent_name: str,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Busca contexto relevante en la memoria de un agente."""
        mem = self._get_agent_memory(agent_name)
        if mem is None:
            return []
        return mem.recall(query, limit=limit)

    # --------------------------------------------------------
    # Adaptadores de subsistemas — extraídos a mixins
    # --------------------------------------------------------
    # Los métodos de planificación, coordinación y sistemas avanzados
    # están en las clases base (mixins):
    #   - DaemonPlanningMixin     → _daemon_mixin_planning.py
    #     (MetaPlanner, AnomalyDetector, Telemetry, SelfImprover)
    #   - DaemonCoordinationMixin → _daemon_mixin_coordination.py
    #     (Reactive, Negotiation, Swarm, Router, Consensus, Observatory, Workflow)
    #   - DaemonAdvancedMixin     → _daemon_mixin_advanced.py (compuesto)
    #     ├─ DaemonReputationMixin     → _daemon_mixin_reputation.py
    #     │  (Reputation, Topology, Trust)
    #     ├─ DaemonObservabilityMixin  → _daemon_mixin_observability.py
    #     │  (Chronicle, CircuitBreaker, Dashboard, Alerts)
    #     ├─ DaemonIntelligenceMixin   → _daemon_mixin_intelligence.py
    #     │  (Prefetch, Genome, Knowledge)
    #     ├─ DaemonAutonomyMixin       → _daemon_mixin_autonomy.py
    #     │  (Metacognition, Goals, Emergent)
    #     └─ DaemonEcosystemMixin      → _daemon_mixin_ecosystem.py
    #        (Contracts, Arena, WS, Federation, Marketplace)


# ============================================================
# Singleton global del daemon
# ============================================================
_daemon_instance: AgentDaemon | None = None
_daemon_init_lock: asyncio.Lock | None = None


async def get_daemon(workers: int = 3, lite: bool = False) -> AgentDaemon:
    """Obtiene o crea el daemon global.

    Args:
        workers: Número de workers concurrentes.
        lite: Si True, arranca solo bus + workers + heartbeat (sin subsistemas).
              Reduce el arranque de ~30s a ~2s.  Ideal para daemon_worker subprocess.
    """
    global _daemon_instance, _daemon_init_lock

    # Fast-path: daemon ya disponible
    if _daemon_instance is not None and _daemon_instance._running:
        return _daemon_instance

    # Evita inicializaciones concurrentes cuando llegan varias requests en paralelo
    if _daemon_init_lock is None:
        _daemon_init_lock = asyncio.Lock()

    async with _daemon_init_lock:
        # Double-check dentro del lock para evitar carreras
        if _daemon_instance is not None and _daemon_instance._running:
            return _daemon_instance

        kwargs: dict[str, Any] = {"workers": workers}
        if lite:
            # Desactivar todos los subsistemas para arranque rápido
            kwargs.update(dict.fromkeys(_SUBSYSTEM_PARAM_NAMES, False))
            kwargs["enable_a2a"] = True  # A2A necesita bus, se mantiene

        daemon = AgentDaemon(**kwargs)
        await daemon.start()
        _daemon_instance = daemon

    return _daemon_instance


# ============================================================
# Entry point para ejecutar como proceso independiente
# ============================================================
async def _main() -> None:
    import signal as sig

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )

    workers = int(os.environ.get("DAEMON_WORKERS", "3"))
    daemon = AgentDaemon(workers=workers)

    # Graceful shutdown
    loop = asyncio.get_running_loop()

    def _handle_signal():
        logger.info("Señal recibida, iniciando shutdown...")
        loop.create_task(daemon.stop())

    loop.add_signal_handler(sig.SIGINT, _handle_signal)
    loop.add_signal_handler(sig.SIGTERM, _handle_signal)

    await daemon.start()
    logger.info("AgentDaemon corriendo. Ctrl+C para detener.")

    # Mantener proceso vivo
    while daemon._running:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(_main())
