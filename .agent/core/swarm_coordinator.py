"""
Swarm Coordinator — Coordinación multi-agente para tareas complejas.

Orquesta un enjambre de agentes para resolver tareas que ningún agente
individual puede completar. El flujo:

1. DECOMPOSE — Descompone la tarea compleja en subtareas con dependencias
2. NEGOTIATE — Usa ContractNetProtocol para asignar cada subtarea
3. EXECUTE — Ejecuta subtareas respetando el grafo de dependencias
4. MONITOR — Trackea progreso en blackboard compartido, maneja fallos
5. AGGREGATE — Combina resultados parciales en resultado final

Modos de ejecución:
  - PARALLEL: Subtareas independientes corren en paralelo
  - SEQUENTIAL: Una subtarea tras otra
  - DAG: Grafo de dependencias (respeta orden parcial)

Usage:
    coordinator = SwarmCoordinator(bus=bus)

    result = await coordinator.execute_swarm(SwarmRequest(
        task="Refactoriza el módulo de autenticación",
        agents=["explorer", "architect", "test-engineer", "security-auditor"],
        mode=SwarmMode.DAG,
    ))

    print(result.status)          # SwarmStatus.COMPLETED
    print(result.subtask_results) # {subtask_id: result, ...}
    print(result.final_summary)   # Resumen agregado
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.swarm_coordinator")

# ============================================================
# Constantes
# ============================================================
MAX_SWARM_HISTORY = 100
DEFAULT_SWARM_TIMEOUT = 600.0  # 10 minutos por swarm
DEFAULT_SUBTASK_TIMEOUT = 120.0  # 2 minutos por subtarea
SWARM_CHANNEL = "swarm.events"


# ============================================================
# Enums
# ============================================================
class SwarmMode(str, Enum):
    """Modo de ejecución del enjambre."""

    PARALLEL = "parallel"  # Todas las subtareas en paralelo
    SEQUENTIAL = "sequential"  # Una tras otra
    DAG = "dag"  # Respetando grafo de dependencias


class SwarmStatus(str, Enum):
    """Estado del enjambre."""

    PLANNING = "planning"
    NEGOTIATING = "negotiating"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubtaskStatus(str, Enum):
    """Estado de una subtarea."""

    PENDING = "pending"
    NEGOTIATING = "negotiating"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ============================================================
# Modelos de datos
# ============================================================
@dataclass
class SubTask:
    """Subtarea individual del enjambre."""

    subtask_id: str
    description: str
    required_capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # subtask_ids
    assigned_agent: str | None = None
    status: SubtaskStatus = SubtaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float | None = None
    priority: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "description": self.description,
            "required_capabilities": self.required_capabilities,
            "depends_on": self.depends_on,
            "assigned_agent": self.assigned_agent,
            "status": self.status.value,
            "result": self.result[:200] if self.result else None,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "priority": self.priority,
        }


@dataclass
class SwarmRequest:
    """Solicitud de ejecución de enjambre."""

    task: str
    agents: list[str] = field(default_factory=list)
    mode: SwarmMode = SwarmMode.DAG
    timeout_seconds: float = DEFAULT_SWARM_TIMEOUT
    subtask_timeout: float = DEFAULT_SUBTASK_TIMEOUT
    context: dict[str, Any] = field(default_factory=dict)
    from_agent: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "agents": self.agents,
            "mode": self.mode.value,
            "timeout_seconds": self.timeout_seconds,
            "subtask_timeout": self.subtask_timeout,
            "from_agent": self.from_agent,
        }


@dataclass
class SwarmResult:
    """Resultado de la ejecución de un enjambre."""

    swarm_id: str
    task: str
    status: SwarmStatus
    subtasks: list[SubTask] = field(default_factory=list)
    mode: SwarmMode = SwarmMode.DAG
    final_summary: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    total_duration: float | None = None
    agents_used: list[str] = field(default_factory=list)
    blackboard_entries: int = 0

    def to_dict(self) -> dict[str, Any]:
        completed = sum(1 for s in self.subtasks if s.status == SubtaskStatus.COMPLETED)
        failed = sum(1 for s in self.subtasks if s.status == SubtaskStatus.FAILED)
        return {
            "swarm_id": self.swarm_id,
            "task": self.task[:200],
            "status": self.status.value,
            "mode": self.mode.value,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "subtask_summary": {
                "total": len(self.subtasks),
                "completed": completed,
                "failed": failed,
                "pending": len(self.subtasks) - completed - failed,
            },
            "final_summary": self.final_summary,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration": self.total_duration,
            "agents_used": self.agents_used,
            "blackboard_entries": self.blackboard_entries,
        }


# ============================================================
# Task Decomposer — descompone tareas complejas en subtareas
# ============================================================
class TaskDecomposer:
    """
    Descompone tareas complejas en subtareas con dependencias.

    Usa heurísticas basadas en el tipo de tarea y los agentes disponibles.
    En producción se podría integrar con un LLM para descomposición
    más inteligente.
    """

    # Templates de descomposición por tipo de tarea
    TEMPLATES: dict[str, list[dict[str, Any]]] = {
        "refactor": [
            {
                "description": "Explorar y analizar el código actual, identificar dependencias",
                "capabilities": ["code-analysis", "search", "dependencies"],
                "depends_on": [],
                "priority": 1,
            },
            {
                "description": "Diseñar la nueva arquitectura y plan de refactorización",
                "capabilities": ["design", "architecture", "patterns"],
                "depends_on": [0],
                "priority": 2,
            },
            {
                "description": "Auditar seguridad del código actual y del plan propuesto",
                "capabilities": ["security", "audit"],
                "depends_on": [0],
                "priority": 3,
            },
            {
                "description": "Crear tests de regresión para validar que el refactor no rompe nada",
                "capabilities": ["testing", "quality"],
                "depends_on": [1],
                "priority": 4,
            },
        ],
        "feature": [
            {
                "description": "Analizar el codebase existente y contexto del feature",
                "capabilities": ["code-analysis", "search"],
                "depends_on": [],
                "priority": 1,
            },
            {
                "description": "Diseñar la arquitectura e interfaces del nuevo feature",
                "capabilities": ["design", "architecture"],
                "depends_on": [0],
                "priority": 2,
            },
            {
                "description": "Revisar seguridad del diseño propuesto",
                "capabilities": ["security", "audit"],
                "depends_on": [1],
                "priority": 3,
            },
            {
                "description": "Escribir tests para el nuevo feature",
                "capabilities": ["testing", "quality"],
                "depends_on": [1],
                "priority": 4,
            },
        ],
        "debug": [
            {
                "description": "Reproducir y analizar el error, trazar la causa raíz",
                "capabilities": ["debugging", "troubleshooting"],
                "depends_on": [],
                "priority": 1,
            },
            {
                "description": "Explorar código relacionado y dependencias afectadas",
                "capabilities": ["code-analysis", "dependencies"],
                "depends_on": [],
                "priority": 1,
            },
            {
                "description": "Verificar que el fix no introduce regresiones",
                "capabilities": ["testing", "quality"],
                "depends_on": [0, 1],
                "priority": 3,
            },
        ],
        "review": [
            {
                "description": "Analizar estructura y calidad del código",
                "capabilities": ["code-analysis", "search"],
                "depends_on": [],
                "priority": 1,
            },
            {
                "description": "Auditar seguridad y vulnerabilidades",
                "capabilities": ["security", "audit"],
                "depends_on": [],
                "priority": 1,
            },
            {
                "description": "Evaluar performance y optimizaciones posibles",
                "capabilities": ["performance", "optimization"],
                "depends_on": [],
                "priority": 2,
            },
            {
                "description": "Verificar cobertura de tests y calidad",
                "capabilities": ["testing", "quality"],
                "depends_on": [],
                "priority": 2,
            },
        ],
    }

    # Keywords → template type
    KEYWORD_MAP: dict[str, str] = {
        "refactor": "refactor",
        "refactoriza": "refactor",
        "migra": "refactor",
        "restructura": "refactor",
        "feature": "feature",
        "implementa": "feature",
        "agrega": "feature",
        "añade": "feature",
        "crea": "feature",
        "debug": "debug",
        "bug": "debug",
        "error": "debug",
        "fix": "debug",
        "corrige": "debug",
        "arregla": "debug",
        "review": "review",
        "revisa": "review",
        "analiza": "review",
        "audita": "review",
        "evalúa": "review",
    }

    @classmethod
    def decompose(
        cls,
        task: str,
        available_agents: list[str] | None = None,
    ) -> list[SubTask]:
        """Descompone una tarea en subtareas con dependencias."""
        # Detectar tipo de tarea
        task_type = cls._detect_task_type(task)
        template = cls.TEMPLATES.get(task_type, cls.TEMPLATES["review"])

        subtasks: list[SubTask] = []
        for i, tmpl in enumerate(template):
            subtask = SubTask(
                subtask_id=str(uuid.uuid4()),
                description=f"{tmpl['description']} — contexto: {task[:100]}",
                required_capabilities=tmpl["capabilities"],
                depends_on=[],  # Se resuelven abajo
                priority=tmpl["priority"],
            )
            subtasks.append(subtask)

        # Resolver dependencias (índices → subtask_ids)
        for i, tmpl in enumerate(template):
            for dep_idx in tmpl.get("depends_on", []):
                if dep_idx < len(subtasks):
                    subtasks[i].depends_on.append(subtasks[dep_idx].subtask_id)

        logger.info(
            "Tarea descompuesta en %d subtareas (tipo=%s): '%.50s...'",
            len(subtasks),
            task_type,
            task,
        )
        return subtasks

    @classmethod
    def _detect_task_type(cls, task: str) -> str:
        """Detecta el tipo de tarea por keywords."""
        task_lower = task.lower()
        for keyword, task_type in cls.KEYWORD_MAP.items():
            if keyword in task_lower:
                return task_type
        return "review"  # Default


# ============================================================
# Swarm Coordinator
# ============================================================
class SwarmCoordinator:
    """
    Coordina enjambres de agentes para tareas complejas.

    Combina TaskDecomposer + ContractNetProtocol + AgentDaemon
    para orquestar ejecución multi-agente con tracking de progreso.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._active_swarms: dict[str, SwarmResult] = {}
        self._swarm_history: list[SwarmResult] = []

        # Lazy-loaded components
        self._negotiation: Any = None
        self._daemon: Any = None

        # Métricas
        self._metrics = {
            "swarms_total": 0,
            "swarms_completed": 0,
            "swarms_failed": 0,
            "swarms_partial": 0,
            "total_subtasks": 0,
            "subtasks_completed": 0,
            "subtasks_failed": 0,
            "avg_swarm_duration": 0.0,
            "avg_subtasks_per_swarm": 0.0,
        }

    async def _ensure_components(self) -> None:
        """Inicializa componentes lazy."""
        if self._negotiation is None:
            from .agent_negotiation import get_negotiation_protocol

            self._negotiation = await get_negotiation_protocol(self._bus)
            self._negotiation.auto_discover_agents()

    # --------------------------------------------------------
    # Execute Swarm
    # --------------------------------------------------------
    async def execute_swarm(self, request: SwarmRequest) -> SwarmResult:
        """
        Ejecuta un enjambre completo para una tarea.

        Retorna SwarmResult con status, resultados parciales, y resumen.
        """
        await self._ensure_components()
        self._metrics["swarms_total"] += 1

        swarm_id = str(uuid.uuid4())
        result = SwarmResult(
            swarm_id=swarm_id,
            task=request.task,
            status=SwarmStatus.PLANNING,
            mode=request.mode,
        )
        self._active_swarms[swarm_id] = result

        logger.info(
            "[Swarm %s] Iniciando: '%.80s...' modo=%s agentes=%s",
            swarm_id[:8],
            request.task,
            request.mode.value,
            request.agents,
        )

        # Publicar inicio
        await self._publish_event(swarm_id, "swarm_started", request.to_dict())

        try:
            # Fase 1: Descomponer tarea
            result.status = SwarmStatus.PLANNING
            subtasks = TaskDecomposer.decompose(request.task, request.agents)
            result.subtasks = subtasks
            self._metrics["total_subtasks"] += len(subtasks)
            self._metrics["avg_subtasks_per_swarm"] = (
                self._metrics["total_subtasks"] / self._metrics["swarms_total"]
            )

            # Fase 2: Negociar asignaciones
            result.status = SwarmStatus.NEGOTIATING
            await self._negotiate_assignments(result, request)

            # Fase 3: Ejecutar subtareas
            result.status = SwarmStatus.EXECUTING
            await self._execute_subtasks(result, request)

            # Fase 4: Agregar resultados
            result.status = SwarmStatus.AGGREGATING
            result.final_summary = self._aggregate_results(result)

            # Determinar status final
            completed = sum(1 for s in result.subtasks if s.status == SubtaskStatus.COMPLETED)
            failed = sum(1 for s in result.subtasks if s.status == SubtaskStatus.FAILED)

            if failed == 0:
                result.status = SwarmStatus.COMPLETED
                self._metrics["swarms_completed"] += 1
            elif completed > 0:
                result.status = SwarmStatus.PARTIAL_FAILURE
                self._metrics["swarms_partial"] += 1
            else:
                result.status = SwarmStatus.FAILED
                self._metrics["swarms_failed"] += 1

        except asyncio.CancelledError:
            result.status = SwarmStatus.CANCELLED
            raise
        except Exception as e:
            result.status = SwarmStatus.FAILED
            self._metrics["swarms_failed"] += 1
            logger.error("[Swarm %s] Error fatal: %s", swarm_id[:8], e)

        finally:
            result.completed_at = time.time()
            result.total_duration = result.completed_at - result.started_at
            result.agents_used = list(
                {s.assigned_agent for s in result.subtasks if s.assigned_agent is not None}
            )

            # Actualizar EMA de duración
            alpha = 0.2
            self._metrics["avg_swarm_duration"] = (
                alpha * (result.total_duration or 0)
                + (1 - alpha) * self._metrics["avg_swarm_duration"]
            )

            await self._publish_event(swarm_id, "swarm_completed", result.to_dict())
            self._finalize_swarm(result)

        logger.info(
            "[Swarm %s] Finalizado: status=%s duración=%.1fs subtasks=%d/%d",
            swarm_id[:8],
            result.status.value,
            result.total_duration or 0,
            sum(1 for s in result.subtasks if s.status == SubtaskStatus.COMPLETED),
            len(result.subtasks),
        )

        return result

    # --------------------------------------------------------
    # Negotiate Assignments
    # --------------------------------------------------------
    async def _negotiate_assignments(
        self,
        result: SwarmResult,
        request: SwarmRequest,
    ) -> None:
        """Negocia la asignación de cada subtarea via ContractNetProtocol."""
        from .agent_negotiation import AuctionStatus, TaskAnnouncement

        for subtask in result.subtasks:
            subtask.status = SubtaskStatus.NEGOTIATING

            announcement = TaskAnnouncement(
                task=subtask.description,
                required_capabilities=subtask.required_capabilities,
                from_agent=request.from_agent,
            )

            auction_result = await self._negotiation.auction(announcement)

            if auction_result.status == AuctionStatus.AWARDED and auction_result.winner:
                subtask.assigned_agent = auction_result.winner
                subtask.status = SubtaskStatus.ASSIGNED
                logger.debug(
                    "[Swarm %s] Subtask '%s' → agente '%s'",
                    result.swarm_id[:8],
                    subtask.subtask_id[:8],
                    auction_result.winner,
                )
            else:
                subtask.status = SubtaskStatus.SKIPPED
                logger.warning(
                    "[Swarm %s] Subtask '%s' sin agente asignado",
                    result.swarm_id[:8],
                    subtask.subtask_id[:8],
                )

    # --------------------------------------------------------
    # Execute Subtasks
    # --------------------------------------------------------
    async def _execute_subtasks(
        self,
        result: SwarmResult,
        request: SwarmRequest,
    ) -> None:
        """Ejecuta subtareas según el modo del enjambre."""
        if request.mode == SwarmMode.PARALLEL:
            await self._execute_parallel(result, request)
        elif request.mode == SwarmMode.SEQUENTIAL:
            await self._execute_sequential(result, request)
        elif request.mode == SwarmMode.DAG:
            await self._execute_dag(result, request)

    async def _execute_parallel(
        self,
        result: SwarmResult,
        request: SwarmRequest,
    ) -> None:
        """Ejecuta todas las subtareas en paralelo."""
        tasks = []
        for subtask in result.subtasks:
            if subtask.status == SubtaskStatus.ASSIGNED:
                tasks.append(self._execute_single_subtask(subtask, request))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_sequential(
        self,
        result: SwarmResult,
        request: SwarmRequest,
    ) -> None:
        """Ejecuta subtareas una por una en orden de prioridad."""
        sorted_subtasks = sorted(result.subtasks, key=lambda s: s.priority)
        for subtask in sorted_subtasks:
            if subtask.status == SubtaskStatus.ASSIGNED:
                await self._execute_single_subtask(subtask, request)

    async def _execute_dag(
        self,
        result: SwarmResult,
        request: SwarmRequest,
    ) -> None:
        """Ejecuta subtareas respetando el grafo de dependencias."""
        completed_ids: set[str] = set()
        max_iterations = len(result.subtasks) * 2  # Safety limit

        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Encontrar subtareas listas (dependencias completadas)
            ready = []
            for subtask in result.subtasks:
                if subtask.status != SubtaskStatus.ASSIGNED:
                    continue
                deps_met = all(dep_id in completed_ids for dep_id in subtask.depends_on)
                if deps_met:
                    ready.append(subtask)

            if not ready:
                # No hay más subtareas listas
                break

            # Ejecutar batch en paralelo
            batch_tasks = [self._execute_single_subtask(s, request) for s in ready]
            await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Registrar completadas
            for subtask in ready:
                if subtask.status == SubtaskStatus.COMPLETED:
                    completed_ids.add(subtask.subtask_id)

    async def _execute_single_subtask(
        self,
        subtask: SubTask,
        request: SwarmRequest,
    ) -> None:
        """Ejecuta una subtarea individual via el daemon."""
        subtask.status = SubtaskStatus.RUNNING
        subtask.started_at = time.time()

        agent = subtask.assigned_agent
        if not agent:
            subtask.status = SubtaskStatus.FAILED
            subtask.error = "Sin agente asignado"
            return

        try:
            if self._bus is None:
                raise RuntimeError("Bus no disponible")

            from .redis_message_bus import Priority

            task_id = str(uuid.uuid4())
            await self._bus.enqueue_priority(
                "tasks",
                {
                    "agent": agent,
                    "task": subtask.description,
                    "task_id": task_id,
                    "context": {
                        **request.context,
                        "_swarm_id": request.task[:50],
                        "_subtask_id": subtask.subtask_id,
                    },
                },
                priority=Priority.HIGH,
                from_agent="swarm-coordinator",
            )

            # Esperar resultado (con timeout)
            result_text = await self._wait_for_result(task_id, agent, request.subtask_timeout)

            subtask.status = SubtaskStatus.COMPLETED
            subtask.result = result_text
            self._metrics["subtasks_completed"] += 1

            # Feedback al protocolo de negociación
            duration = time.time() - (subtask.started_at or time.time())
            subtask.duration_seconds = duration
            if self._negotiation:
                self._negotiation.record_outcome(agent, True, duration)

        except TimeoutError:
            subtask.status = SubtaskStatus.FAILED
            subtask.error = f"Timeout: subtarea excedió {request.subtask_timeout}s"
            self._metrics["subtasks_failed"] += 1
            if self._negotiation:
                self._negotiation.record_outcome(agent, False, request.subtask_timeout)

        except Exception as e:
            subtask.status = SubtaskStatus.FAILED
            subtask.error = str(e)
            self._metrics["subtasks_failed"] += 1
            if self._negotiation:
                duration = time.time() - (subtask.started_at or time.time())
                self._negotiation.record_outcome(agent, False, duration)

        subtask.completed_at = time.time()
        if subtask.started_at:
            subtask.duration_seconds = subtask.completed_at - subtask.started_at

    async def _wait_for_result(
        self,
        task_id: str,
        agent: str,
        timeout: float,
    ) -> str:
        """Espera el resultado de una tarea encolada."""
        if self._bus is None:
            raise RuntimeError("Bus no disponible")

        channel = f"agent.{agent}.results"
        queue = await self._bus.subscribe_queue(channel)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=min(remaining, 5.0))
                payload = msg.payload if hasattr(msg, "payload") else msg
                if isinstance(payload, dict) and payload.get("task_id") == task_id:
                    return payload.get("result", "Completado sin output")
            except TimeoutError:
                continue

        raise TimeoutError(f"Timeout esperando resultado de tarea {task_id}")

    # --------------------------------------------------------
    # Result Aggregation
    # --------------------------------------------------------
    def _aggregate_results(self, result: SwarmResult) -> str:
        """Agrega los resultados parciales en un resumen."""
        completed = [s for s in result.subtasks if s.status == SubtaskStatus.COMPLETED]
        failed = [s for s in result.subtasks if s.status == SubtaskStatus.FAILED]

        parts = [
            f"Swarm '{result.task[:80]}' — {len(completed)}/{len(result.subtasks)} subtareas completadas"
        ]

        if completed:
            parts.append("\n--- Resultados ---")
            for s in completed:
                agent = s.assigned_agent or "?"
                snippet = (s.result or "")[:150]
                parts.append(f"  [{agent}] {snippet}")

        if failed:
            parts.append(f"\n--- Fallos ({len(failed)}) ---")
            for s in failed:
                agent = s.assigned_agent or "?"
                parts.append(f"  [{agent}] Error: {s.error}")

        return "\n".join(parts)

    # --------------------------------------------------------
    # Bus events
    # --------------------------------------------------------
    async def _publish_event(
        self,
        swarm_id: str,
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        """Publica evento del swarm en el bus."""
        if self._bus is None:
            return
        try:
            await self._bus.publish(
                SWARM_CHANNEL,
                {"swarm_id": swarm_id, "event": event_name, **data},
                from_agent="swarm-coordinator",
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # Finalize & History
    # --------------------------------------------------------
    def _finalize_swarm(self, result: SwarmResult) -> None:
        """Archiva un swarm completado."""
        self._active_swarms.pop(result.swarm_id, None)
        self._swarm_history.append(result)
        if len(self._swarm_history) > MAX_SWARM_HISTORY:
            self._swarm_history = self._swarm_history[-MAX_SWARM_HISTORY:]

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    def get_swarm(self, swarm_id: str) -> dict[str, Any] | None:
        """Retorna un swarm por ID."""
        if swarm_id in self._active_swarms:
            return self._active_swarms[swarm_id].to_dict()
        for result in reversed(self._swarm_history):
            if result.swarm_id == swarm_id:
                return result.to_dict()
        return None

    def list_swarms(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista swarms."""
        all_swarms = list(self._active_swarms.values()) + self._swarm_history
        if status:
            all_swarms = [s for s in all_swarms if s.status.value == status]
        return [s.to_dict() for s in all_swarms[-limit:]]

    def cancel_swarm(self, swarm_id: str) -> bool:
        """Cancela un swarm activo."""
        result = self._active_swarms.get(swarm_id)
        if result is None:
            return False
        result.status = SwarmStatus.CANCELLED
        result.completed_at = time.time()
        if result.started_at:
            result.total_duration = result.completed_at - result.started_at
        self._finalize_swarm(result)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del coordinador."""
        return {
            "active_swarms": len(self._active_swarms),
            "history_size": len(self._swarm_history),
            "metrics": {**self._metrics},
        }


# ============================================================
# Singleton
# ============================================================
_instance: SwarmCoordinator | None = None


async def get_swarm_coordinator(bus: Any = None) -> SwarmCoordinator:
    """Obtiene o crea el coordinador de enjambre global."""
    global _instance
    if _instance is None:
        _instance = SwarmCoordinator(bus=bus)
    return _instance
