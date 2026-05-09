"""
Dynamic Replanning Module - Replanificacion dinamica durante ejecucion

Permite ajustar planes en tiempo real basado en resultados y eventos.
"""
# mypy: ignore-errors

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StepStatus(Enum):
    """Estado de un paso."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class TriggerType(Enum):
    """Tipo de trigger para replanificacion."""

    STEP_FAILED = "step_failed"
    STEP_SLOW = "step_slow"
    NEW_INFO = "new_info"
    RESOURCE_CHANGE = "resource_change"
    USER_FEEDBACK = "user_feedback"
    DEPENDENCY_CHANGE = "dependency_change"


@dataclass
class PlanStep:
    """Paso de un plan."""

    id: str
    name: str
    agent: str
    status: StepStatus = StepStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    estimated_duration: int = 60  # segundos
    actual_duration: int | None = None
    result: dict | None = None
    retries: int = 0
    max_retries: int = 3


@dataclass
class ReplanningTrigger:
    """Trigger que activa replanificacion."""

    type: TriggerType
    step_id: str
    timestamp: datetime
    data: dict = field(default_factory=dict)
    severity: str = "medium"  # low, medium, high, critical


@dataclass
class ReplanningAction:
    """Accion de replanificacion."""

    action: str  # retry, skip, add, remove, reorder, modify
    step_id: str
    reason: str
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DynamicPlan:
    """Plan dinamico con capacidad de replanificacion."""

    id: str
    name: str
    steps: list[PlanStep]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    replan_history: list[ReplanningAction] = field(default_factory=list)
    confidence: float = 1.0


class DynamicReplanning:
    """
    Motor de replanificacion dinamica.

    Capacidades:
    - Monitoreo continuo de ejecucion
    - Deteccion de triggers de replanificacion
    - Generacion de acciones de ajuste
    - Mantenimiento de historial
    """

    def __init__(self):
        self.plans: dict[str, DynamicPlan] = {}
        self.triggers: list[ReplanningTrigger] = []
        self.replan_callbacks: list[Callable] = []

    def create_plan(self, name: str, steps: list[dict]) -> DynamicPlan:
        """
        Crea un nuevo plan dinamico.

        Args:
            name: Nombre del plan
            steps: Lista de pasos

        Returns:
            DynamicPlan creado
        """
        plan_id = f"plan_{len(self.plans) + 1}_{datetime.now().strftime('%H%M%S')}"

        plan_steps = [
            PlanStep(
                id=f"step_{i}",
                name=step.get("name", f"Step {i}"),
                agent=step.get("agent", "unknown"),
                dependencies=step.get("dependencies", []),
                estimated_duration=step.get("estimated_duration", 60),
            )
            for i, step in enumerate(steps)
        ]

        plan = DynamicPlan(id=plan_id, name=name, steps=plan_steps)

        self.plans[plan_id] = plan
        return plan

    def report_step_result(
        self,
        plan_id: str,
        step_id: str,
        success: bool,
        result: dict | None = None,
        duration: int | None = None,
    ) -> list[ReplanningAction]:
        """
        Reporta resultado de un paso y evalua replanificacion.

        Args:
            plan_id: ID del plan
            step_id: ID del paso
            success: Si fue exitoso
            result: Resultado del paso
            duration: Duracion real

        Returns:
            Lista de acciones de replanificacion
        """
        plan = self.plans.get(plan_id)
        if not plan:
            return []

        step = next((s for s in plan.steps if s.id == step_id), None)
        if not step:
            return []

        actions = []

        if success:
            step.status = StepStatus.COMPLETED
            step.result = result
            step.actual_duration = duration

            # Verificar si hay nueva info que afecte pasos siguientes
            if result:
                new_info_actions = self._check_new_info_impact(plan, step, result)
                actions.extend(new_info_actions)

            # Verificar oportunidades de optimizacion
            opt_actions = self._check_optimization_opportunities(plan, step)
            actions.extend(opt_actions)

        else:
            step.retries += 1

            if step.retries < step.max_retries:
                # Retry
                step.status = StepStatus.PENDING
                actions.append(
                    ReplanningAction(
                        action="retry",
                        step_id=step_id,
                        reason=f"Step failed, retry {step.retries}/{step.max_retries}",
                        details={"attempt": step.retries},
                    )
                )

                self.triggers.append(
                    ReplanningTrigger(
                        type=TriggerType.STEP_FAILED,
                        step_id=step_id,
                        timestamp=datetime.now(),
                        data={"retries": step.retries},
                    )
                )
            else:
                # Fallo definitivo
                step.status = StepStatus.FAILED
                failure_actions = self._handle_step_failure(plan, step)
                actions.extend(failure_actions)

        # Actualizar plan
        plan.updated_at = datetime.now()
        plan.replan_history.extend(actions)
        plan.confidence = self._calculate_confidence(plan)

        # Notificar callbacks
        for callback in self.replan_callbacks:
            callback(plan, actions)

        return actions

    def _check_new_info_impact(
        self, plan: DynamicPlan, completed_step: PlanStep, result: dict
    ) -> list[ReplanningAction]:
        """Verifica si nueva info requiere ajustes."""
        actions = []

        # Detectar complejidad inesperada
        if result.get("complexity") == "high":
            # Agregar paso de analisis
            actions.append(
                ReplanningAction(
                    action="add",
                    step_id=completed_step.id,
                    reason="High complexity detected, adding analysis step",
                    details={"new_step": "detailed_analysis", "after": completed_step.id},
                )
            )

        # Detectar que algunos pasos pueden saltarse
        if result.get("skip_suggested"):
            for skip_id in result.get("skip_suggested", []):
                skip_step = next((s for s in plan.steps if s.id == skip_id), None)
                if skip_step and skip_step.status == StepStatus.PENDING:
                    skip_step.status = StepStatus.SKIPPED
                    actions.append(
                        ReplanningAction(
                            action="skip",
                            step_id=skip_id,
                            reason=f"Not needed based on {completed_step.id} result",
                        )
                    )

        # Detectar dependencias nuevas
        if result.get("new_dependencies"):
            for dep in result.get("new_dependencies", []):
                actions.append(
                    ReplanningAction(
                        action="add",
                        step_id=completed_step.id,
                        reason=f"New dependency discovered: {dep}",
                        details={"dependency": dep},
                    )
                )

        return actions

    def _check_optimization_opportunities(
        self, plan: DynamicPlan, completed_step: PlanStep
    ) -> list[ReplanningAction]:
        """Busca oportunidades de optimizacion."""
        actions = []

        # Buscar pasos que ahora pueden paralelizarse
        completed_ids = {s.id for s in plan.steps if s.status == StepStatus.COMPLETED}
        pending = [s for s in plan.steps if s.status == StepStatus.PENDING]

        parallelizable = []
        for step in pending:
            if all(dep in completed_ids for dep in step.dependencies):
                parallelizable.append(step)

        if len(parallelizable) > 1:
            actions.append(
                ReplanningAction(
                    action="parallelize",
                    step_id=completed_step.id,
                    reason=f"Found {len(parallelizable)} steps that can run in parallel",
                    details={"steps": [s.id for s in parallelizable]},
                )
            )

        return actions

    def _handle_step_failure(
        self, plan: DynamicPlan, failed_step: PlanStep
    ) -> list[ReplanningAction]:
        """Maneja fallo de un paso."""
        actions = []

        # Marcar dependientes como bloqueados
        for step in plan.steps:
            if failed_step.id in step.dependencies:
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.BLOCKED
                    actions.append(
                        ReplanningAction(
                            action="block",
                            step_id=step.id,
                            reason=f"Blocked by failed step {failed_step.id}",
                        )
                    )

        # Agregar paso de recuperacion
        actions.append(
            ReplanningAction(
                action="add",
                step_id=failed_step.id,
                reason="Adding recovery step",
                details={"type": "recovery", "for": failed_step.id},
            )
        )

        # Trigger critico
        self.triggers.append(
            ReplanningTrigger(
                type=TriggerType.STEP_FAILED,
                step_id=failed_step.id,
                timestamp=datetime.now(),
                severity="critical",
                data={"max_retries_exceeded": True},
            )
        )

        return actions

    def _calculate_confidence(self, plan: DynamicPlan) -> float:
        """Calcula confianza del plan."""
        if not plan.steps:
            return 0.0

        completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        blocked = sum(1 for s in plan.steps if s.status == StepStatus.BLOCKED)
        total = len(plan.steps)

        # Base: progreso
        progress = completed / total

        # Penalizaciones
        fail_penalty = (failed / total) * 0.5
        block_penalty = (blocked / total) * 0.3
        replan_penalty = min(0.2, len(plan.replan_history) * 0.02)

        confidence = progress - fail_penalty - block_penalty - replan_penalty + 0.3
        return max(0.0, min(1.0, confidence))

    def inject_user_feedback(
        self, plan_id: str, feedback: str, affected_steps: list[str] | None = None
    ) -> list[ReplanningAction]:
        """
        Inyecta feedback del usuario para replanificacion.

        Args:
            plan_id: ID del plan
            feedback: Feedback del usuario
            affected_steps: Pasos afectados (opcional)

        Returns:
            Acciones de replanificacion
        """
        plan = self.plans.get(plan_id)
        if not plan:
            return []

        actions = []

        # Trigger de feedback
        self.triggers.append(
            ReplanningTrigger(
                type=TriggerType.USER_FEEDBACK,
                step_id=affected_steps[0] if affected_steps else "all",
                timestamp=datetime.now(),
                data={"feedback": feedback},
            )
        )

        # Analizar feedback (simplificado)
        feedback_lower = feedback.lower()

        if "skip" in feedback_lower or "saltar" in feedback_lower:
            for step_id in affected_steps or []:
                step = next((s for s in plan.steps if s.id == step_id), None)
                if step and step.status == StepStatus.PENDING:
                    step.status = StepStatus.SKIPPED
                    actions.append(
                        ReplanningAction(
                            action="skip",
                            step_id=step_id,
                            reason=f"User requested skip: {feedback[:50]}",
                        )
                    )

        elif "add" in feedback_lower or "agregar" in feedback_lower:
            actions.append(
                ReplanningAction(
                    action="add",
                    step_id="user_requested",
                    reason=f"User requested addition: {feedback[:50]}",
                    details={"description": feedback},
                )
            )

        elif "cambiar" in feedback_lower or "change" in feedback_lower:
            for step_id in affected_steps or []:
                actions.append(
                    ReplanningAction(
                        action="modify",
                        step_id=step_id,
                        reason=f"User requested change: {feedback[:50]}",
                    )
                )

        plan.updated_at = datetime.now()
        plan.replan_history.extend(actions)

        return actions

    def get_plan_status(self, plan_id: str) -> dict:
        """Obtiene estado del plan."""
        plan = self.plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}

        status_counts = {}
        for status in StepStatus:
            count = sum(1 for s in plan.steps if s.status == status)
            if count > 0:
                status_counts[status.value] = count

        return {
            "plan_id": plan.id,
            "name": plan.name,
            "total_steps": len(plan.steps),
            "status_counts": status_counts,
            "confidence": plan.confidence,
            "replan_count": len(plan.replan_history),
            "last_updated": plan.updated_at.isoformat(),
        }

    def register_callback(self, callback: Callable):
        """Registra callback para notificaciones de replan."""
        self.replan_callbacks.append(callback)


# Singleton
_dynamic_replanning: DynamicReplanning | None = None


def get_dynamic_replanning() -> DynamicReplanning:
    """Obtiene instancia singleton."""
    global _dynamic_replanning
    if _dynamic_replanning is None:
        _dynamic_replanning = DynamicReplanning()
    return _dynamic_replanning
