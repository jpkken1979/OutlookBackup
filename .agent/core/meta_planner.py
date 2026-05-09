"""
MetaPlanner — Descomposición inteligente de tareas y delegación A2A.

Recibe una tarea compleja, la analiza, genera un plan de ejecución
(DAG de sub-tareas), delega cada sub-tarea al agente especializado
via A2A request-reply (Sprint 1), y sintetiza los resultados.

Ejemplo de uso:
    planner = MetaPlanner(bus)
    result = await planner.execute("Implementar autenticación JWT con tests de seguridad")
    # → {plan: [...], results: [...], summary: "...", status: "completed"}

El MetaPlanner es la pieza que convierte agentes individuales en un
sistema orquestado que se auto-organiza para tareas complejas.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.meta_planner")

# ============================================================
# Mapeo de dominios a agentes especializados
# ============================================================
DOMAIN_AGENT_MAP: dict[str, list[str]] = {
    "architecture": ["architect", "infrastructure-architect"],
    "security": ["security-auditor", "penetration-tester"],
    "testing": ["test-engineer", "debugger"],
    "frontend": ["frontend-specialist", "ui-ux-designer"],
    "backend": ["backend-specialist", "api-gateway-specialist"],
    "database": ["database-architect", "data-engineer"],
    "devops": ["devops-engineer", "serverless-architect"],
    "documentation": ["documentation-writer"],
    "performance": ["performance-optimizer"],
    "exploration": ["explorer", "code-archaeologist"],
    "planning": ["planner", "product-manager"],
    "ml": ["ml-engineer", "data-engineer"],
}

# Keywords para detectar dominios
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "architecture": ["architect", "design", "structure", "pattern", "microservice", "monolith"],
    "security": ["security", "auth", "jwt", "token", "encrypt", "vulnerability", "audit"],
    "testing": ["test", "coverage", "unit test", "integration", "e2e", "pytest", "jest"],
    "frontend": ["ui", "react", "component", "css", "tailwind", "layout", "page"],
    "backend": ["api", "endpoint", "rest", "graphql", "server", "route", "handler"],
    "database": ["database", "db", "sql", "migration", "schema", "table", "query", "postgres"],
    "devops": ["docker", "ci", "cd", "deploy", "pipeline", "kubernetes", "infra"],
    "documentation": ["document", "readme", "guide", "wiki", "manual"],
    "performance": ["performance", "optimize", "cache", "speed", "latency", "benchmark"],
    "exploration": ["explore", "analyze", "understand", "investigate", "scan", "search"],
    "planning": ["plan", "strategy", "roadmap", "decompose", "break down"],
    "ml": ["model", "training", "dataset", "ml", "ai", "neural", "prediction"],
}


# ============================================================
# Data models
# ============================================================
class SubTaskStatus(Enum):
    """Estado de una sub-tarea en el plan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(Enum):
    """Estado global del plan."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Algunas sub-tareas fallaron
    FAILED = "failed"


@dataclass
class SubTask:
    """Una sub-tarea dentro de un plan de ejecución."""

    subtask_id: str
    description: str
    agent: str
    domain: str
    depends_on: list[str] = field(default_factory=list)
    status: SubTaskStatus = SubTaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "description": self.description,
            "agent": self.agent,
            "domain": self.domain,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ExecutionPlan:
    """Plan de ejecución con sub-tareas organizadas en fases."""

    plan_id: str
    original_task: str
    subtasks: list[SubTask]
    status: PlanStatus = PlanStatus.CREATED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "original_task": self.original_task,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "summary": self.summary,
            "total_subtasks": len(self.subtasks),
            "completed_count": sum(
                1 for st in self.subtasks if st.status == SubTaskStatus.COMPLETED
            ),
            "failed_count": sum(1 for st in self.subtasks if st.status == SubTaskStatus.FAILED),
        }


# ============================================================
# MetaPlanner
# ============================================================
class MetaPlanner:
    """
    Planificador que descompone tareas complejas y las delega via A2A.

    Flujo:
    1. analyze() — detecta dominios y complejidad
    2. plan()    — genera plan con sub-tareas y dependencias
    3. execute() — ejecuta el plan delegando via A2A request-reply
    4. synthesize() — combina resultados en un resumen final
    """

    def __init__(
        self,
        bus: Any,
        timeout_per_subtask: float = 120.0,
        max_parallel: int = 3,
    ) -> None:
        self._bus = bus
        self._timeout = timeout_per_subtask
        self._max_parallel = max_parallel
        self._plans: dict[str, ExecutionPlan] = {}
        self._stats = {
            "plans_created": 0,
            "plans_completed": 0,
            "plans_failed": 0,
            "subtasks_executed": 0,
            "subtasks_succeeded": 0,
            "subtasks_failed": 0,
            "total_duration_seconds": 0.0,
        }

    # --------------------------------------------------------
    # Paso 1: Análisis de tarea
    # --------------------------------------------------------
    def analyze(self, task: str) -> dict[str, Any]:
        """
        Analiza una tarea y detecta los dominios involucrados.

        Args:
            task: Descripción de la tarea compleja.

        Returns:
            dict con dominios detectados, agentes recomendados y complejidad.
        """
        task_lower = task.lower()
        detected_domains: dict[str, float] = {}

        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw in task_lower:
                    score += 1.0
            if score > 0:
                detected_domains[domain] = score / len(keywords)

        # Ordenar por relevancia
        sorted_domains = sorted(detected_domains.items(), key=lambda x: x[1], reverse=True)

        # Siempre incluir exploración si hay más de 1 dominio
        if len(sorted_domains) > 1 and "exploration" not in detected_domains:
            sorted_domains.insert(0, ("exploration", 0.5))

        # Si no se detectó nada, explorar primero
        if not sorted_domains:
            sorted_domains = [("exploration", 1.0)]

        recommended_agents = []
        for domain, _score in sorted_domains:
            agents = DOMAIN_AGENT_MAP.get(domain, [])
            if agents:
                recommended_agents.append(agents[0])

        complexity = "simple"
        if len(sorted_domains) >= 4:
            complexity = "expert"
        elif len(sorted_domains) >= 3:
            complexity = "complex"
        elif len(sorted_domains) >= 2:
            complexity = "moderate"

        return {
            "task": task,
            "domains": [d for d, _ in sorted_domains],
            "domain_scores": {d: round(s, 2) for d, s in sorted_domains},
            "recommended_agents": recommended_agents,
            "complexity": complexity,
            "estimated_subtasks": max(len(sorted_domains), 1),
        }

    # --------------------------------------------------------
    # Paso 2: Generación de plan
    # --------------------------------------------------------
    def plan(self, task: str, context: dict[str, Any] | None = None) -> ExecutionPlan:
        """
        Genera un plan de ejecución con sub-tareas y dependencias.

        Args:
            task: Tarea compleja a descomponer.
            context: Contexto adicional para la planificación.

        Returns:
            ExecutionPlan con sub-tareas organizadas.
        """
        analysis = self.analyze(task)
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        subtasks: list[SubTask] = []
        prev_id: str | None = None

        ctx_summary = ""
        if context:
            import json

            ctx_summary = json.dumps(context, default=str)[:200]

        for i, domain in enumerate(analysis["domains"]):
            agents = DOMAIN_AGENT_MAP.get(domain, ["explorer"])
            agent = agents[0]

            # Construir descripción de la sub-tarea según el dominio
            description = self._build_subtask_description(
                domain,
                task,
                ctx_summary,
            )

            subtask_id = f"{plan_id}-st{i}"
            depends = [prev_id] if prev_id else []

            subtasks.append(
                SubTask(
                    subtask_id=subtask_id,
                    description=description,
                    agent=agent,
                    domain=domain,
                    depends_on=depends,
                )
            )

            prev_id = subtask_id

        execution_plan = ExecutionPlan(
            plan_id=plan_id,
            original_task=task,
            subtasks=subtasks,
        )

        self._plans[plan_id] = execution_plan
        self._stats["plans_created"] += 1

        logger.info(
            "Plan generado: %s — %d sub-tareas para: %.60s...",
            plan_id,
            len(subtasks),
            task,
        )

        return execution_plan

    def _build_subtask_description(
        self,
        domain: str,
        task: str,
        context: str,
    ) -> str:
        """Construye la descripción de una sub-tarea según su dominio."""
        prefix_map = {
            "exploration": f"Explorar y analizar el contexto para: {task}",
            "architecture": f"Diseñar la arquitectura para: {task}",
            "security": f"Revisar la seguridad de: {task}",
            "testing": f"Crear tests para: {task}",
            "frontend": f"Implementar la interfaz de: {task}",
            "backend": f"Implementar la lógica backend de: {task}",
            "database": f"Diseñar el esquema de datos para: {task}",
            "devops": f"Configurar el despliegue para: {task}",
            "documentation": f"Documentar: {task}",
            "performance": f"Optimizar el rendimiento de: {task}",
            "planning": f"Planificar la ejecución de: {task}",
            "ml": f"Implementar el modelo ML para: {task}",
        }
        desc = prefix_map.get(domain, f"Ejecutar tarea [{domain}]: {task}")
        if context:
            desc += f" | Contexto: {context}"
        return desc[:500]

    # --------------------------------------------------------
    # Paso 3: Ejecución del plan
    # --------------------------------------------------------
    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        plan: ExecutionPlan | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta un plan completo: descompone, delega via A2A, sintetiza.

        Args:
            task: Tarea compleja (se genera plan automáticamente si no se provee).
            context: Contexto adicional.
            plan: Plan pre-generado (opcional).

        Returns:
            dict con plan, resultados, resumen y estadísticas.
        """
        if plan is None:
            plan = self.plan(task, context)

        plan.status = PlanStatus.RUNNING
        plan.started_at = time.time()

        logger.info(
            "Ejecutando plan %s: %d sub-tareas",
            plan.plan_id,
            len(plan.subtasks),
        )

        # Acumular contexto de sub-tareas completadas
        accumulated_context: dict[str, str] = {}

        # Resolver orden de ejecución respetando dependencias
        executed: set[str] = set()

        while any(st.status == SubTaskStatus.PENDING for st in plan.subtasks):
            # Encontrar sub-tareas listas (dependencias completadas)
            ready = [
                st
                for st in plan.subtasks
                if st.status == SubTaskStatus.PENDING
                and all(dep in executed for dep in st.depends_on)
            ]

            if not ready:
                break

            # Ejecutar lote de sub-tareas listas (hasta max_parallel)
            batch = ready[: self._max_parallel]
            tasks = [self._execute_subtask(st, accumulated_context) for st in batch]

            await asyncio.gather(*tasks, return_exceptions=True)

            # Actualizar ejecutadas y acumular contexto
            for st in batch:
                executed.add(st.subtask_id)
                if st.status == SubTaskStatus.COMPLETED and st.result:
                    accumulated_context[st.domain] = st.result[:500]

        # Determinar estado final
        completed = sum(1 for st in plan.subtasks if st.status == SubTaskStatus.COMPLETED)
        failed = sum(1 for st in plan.subtasks if st.status == SubTaskStatus.FAILED)
        total = len(plan.subtasks)

        if completed == total:
            plan.status = PlanStatus.COMPLETED
            self._stats["plans_completed"] += 1
        elif failed == total:
            plan.status = PlanStatus.FAILED
            self._stats["plans_failed"] += 1
        else:
            plan.status = PlanStatus.PARTIAL
            self._stats["plans_completed"] += 1

        plan.completed_at = time.time()
        duration = plan.completed_at - (plan.started_at or plan.completed_at)
        self._stats["total_duration_seconds"] += duration

        # Sintetizar resultados
        plan.summary = self._synthesize(plan)

        logger.info(
            "Plan %s finalizado: %s (%d/%d exitosas) en %.1fs",
            plan.plan_id,
            plan.status.value,
            completed,
            total,
            duration,
        )

        return plan.to_dict()

    async def _execute_subtask(
        self,
        subtask: SubTask,
        accumulated_context: dict[str, str],
    ) -> None:
        """Ejecuta una sub-tarea delegando al agente via A2A."""
        subtask.status = SubTaskStatus.RUNNING
        subtask.started_at = time.time()
        self._stats["subtasks_executed"] += 1

        logger.info(
            "Ejecutando sub-tarea %s → agente '%s': %.50s...",
            subtask.subtask_id,
            subtask.agent,
            subtask.description,
        )

        try:
            # Contexto de sub-tareas previas
            ctx = {
                "plan_context": accumulated_context,
                "subtask_id": subtask.subtask_id,
                "domain": subtask.domain,
            }

            response = await self._bus.request(
                from_agent="meta-planner",
                to_agent=subtask.agent,
                question=subtask.description,
                context=ctx,
                timeout=self._timeout,
                request_type="delegation",
            )

            subtask.status = SubTaskStatus.COMPLETED
            subtask.result = str(response.get("response", response))[:2000]
            self._stats["subtasks_succeeded"] += 1

        except TimeoutError:
            subtask.status = SubTaskStatus.FAILED
            subtask.error = f"Timeout ({self._timeout}s)"
            self._stats["subtasks_failed"] += 1
            logger.warning(
                "Sub-tarea %s timeout: agente '%s'",
                subtask.subtask_id,
                subtask.agent,
            )

        except Exception as e:
            subtask.status = SubTaskStatus.FAILED
            subtask.error = f"{type(e).__name__}: {e}"
            self._stats["subtasks_failed"] += 1
            logger.warning(
                "Sub-tarea %s fallida: %s",
                subtask.subtask_id,
                e,
            )

        finally:
            subtask.completed_at = time.time()
            subtask.duration_seconds = subtask.completed_at - (
                subtask.started_at or subtask.completed_at
            )

    # --------------------------------------------------------
    # Paso 4: Síntesis de resultados
    # --------------------------------------------------------
    def _synthesize(self, plan: ExecutionPlan) -> str:
        """Sintetiza los resultados de todas las sub-tareas en un resumen."""
        parts = [f"Plan: {plan.original_task}"]
        parts.append(f"Estado: {plan.status.value}")

        completed = [st for st in plan.subtasks if st.status == SubTaskStatus.COMPLETED]
        failed = [st for st in plan.subtasks if st.status == SubTaskStatus.FAILED]

        if completed:
            parts.append(f"\nResultados ({len(completed)}/{len(plan.subtasks)}):")
            for st in completed:
                result_preview = (st.result or "")[:200]
                parts.append(f"  [{st.domain}] {st.agent}: {result_preview}")

        if failed:
            parts.append(f"\nFallos ({len(failed)}):")
            for st in failed:
                parts.append(f"  [{st.domain}] {st.agent}: {st.error}")

        return "\n".join(parts)

    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------
    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        """Retorna un plan por su ID."""
        plan = self._plans.get(plan_id)
        return plan.to_dict() if plan else None

    def list_plans(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lista los planes más recientes."""
        plans = sorted(
            self._plans.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )
        return [p.to_dict() for p in plans[:limit]]

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del MetaPlanner."""
        return {
            **self._stats,
            "active_plans": sum(1 for p in self._plans.values() if p.status == PlanStatus.RUNNING),
            "total_plans": len(self._plans),
        }
