#!/usr/bin/env python3
"""
Plan Optimizer Agent - Optimizacion dinamica de planes durante ejecucion

Reajusta planes en tiempo real basado en resultados parciales y fallos.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random


class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AdjustmentType(Enum):
    REORDER = "reorder"
    SKIP = "skip"
    ADD = "add"
    MODIFY = "modify"
    PARALLELIZE = "parallelize"
    RETRY = "retry"


@dataclass
class PlanStep:
    id: str
    description: str
    agent: str
    status: StepStatus = StepStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    result: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempts: int = 0


@dataclass
class Adjustment:
    type: AdjustmentType
    reason: str
    affected_steps: list[str]
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict = field(default_factory=dict)


@dataclass
class DynamicPlan:
    id: str
    description: str
    steps: list[PlanStep]
    current_step: int = 0
    adjustments: list[Adjustment] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationResult:
    success: bool
    plan_id: str
    adjustments_made: list[Adjustment]
    new_confidence: float
    message: str


class PlanOptimizer:
    """Optimiza planes dinamicamente durante ejecucion."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.plans: dict[str, DynamicPlan] = {}

    def create_plan(self, description: str, steps: list[dict]) -> DynamicPlan:
        """Crea un nuevo plan dinamico."""
        plan_id = f"plan_{len(self.plans) + 1}"

        plan_steps = [
            PlanStep(
                id=f"step_{i}",
                description=step.get("description", f"Step {i}"),
                agent=step.get("agent", "unknown"),
                dependencies=step.get("dependencies", []),
            )
            for i, step in enumerate(steps)
        ]

        plan = DynamicPlan(id=plan_id, description=description, steps=plan_steps)

        self.plans[plan_id] = plan
        return plan

    def get_ready_steps(self, plan: DynamicPlan) -> list[PlanStep]:
        """Obtiene pasos listos para ejecutar."""
        completed_ids = {s.id for s in plan.steps if s.status == StepStatus.COMPLETED}

        ready = []
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(dep in completed_ids for dep in step.dependencies):
                ready.append(step)

        return ready

    def report_result(
        self, plan_id: str, step_id: str, success: bool, result: dict | None = None
    ) -> OptimizationResult:
        """Reporta resultado de un paso y optimiza si es necesario."""
        plan = self.plans.get(plan_id)
        if not plan:
            return OptimizationResult(
                success=False,
                plan_id=plan_id,
                adjustments_made=[],
                new_confidence=0,
                message=f"Plan {plan_id} not found",
            )

        step = next((s for s in plan.steps if s.id == step_id), None)
        if not step:
            return OptimizationResult(
                success=False,
                plan_id=plan_id,
                adjustments_made=[],
                new_confidence=plan.confidence,
                message=f"Step {step_id} not found",
            )

        adjustments = []

        if success:
            step.status = StepStatus.COMPLETED
            step.result = result
            step.completed_at = datetime.now()

            # Verificar si podemos optimizar (paralelizar pasos siguientes)
            ready = self.get_ready_steps(plan)
            if len(ready) > 1:
                adj = Adjustment(
                    type=AdjustmentType.PARALLELIZE,
                    reason=f"Multiple steps ready: {[s.id for s in ready]}",
                    affected_steps=[s.id for s in ready],
                    details={"parallel_count": len(ready)},
                )
                adjustments.append(adj)
                plan.adjustments.append(adj)

            # Analizar resultado para posibles optimizaciones
            if result:
                new_adjs = self._analyze_result_for_optimizations(plan, step, result)
                adjustments.extend(new_adjs)
                plan.adjustments.extend(new_adjs)

        else:
            step.attempts += 1

            if step.attempts < self.max_retries:
                # Retry
                adj = Adjustment(
                    type=AdjustmentType.RETRY,
                    reason=f"Step failed, attempt {step.attempts}/{self.max_retries}",
                    affected_steps=[step.id],
                    details={"attempt": step.attempts},
                )
                adjustments.append(adj)
                plan.adjustments.append(adj)
                step.status = StepStatus.PENDING  # Reset for retry
            else:
                step.status = StepStatus.FAILED

                # Intentar replanificar
                new_adjs = self._handle_failure(plan, step)
                adjustments.extend(new_adjs)
                plan.adjustments.extend(new_adjs)

        # Recalcular confianza
        plan.confidence = self._calculate_confidence(plan)

        return OptimizationResult(
            success=True,
            plan_id=plan_id,
            adjustments_made=adjustments,
            new_confidence=plan.confidence,
            message=f"Step {step_id} {'completed' if success else 'failed'}",
        )

    def _analyze_result_for_optimizations(
        self, plan: DynamicPlan, step: PlanStep, result: dict
    ) -> list[Adjustment]:
        """Analiza resultado para encontrar optimizaciones."""
        adjustments = []

        # Si el resultado indica complejidad inesperada
        if result.get("complexity") == "high":
            # Agregar paso de analisis adicional
            adj = Adjustment(
                type=AdjustmentType.ADD,
                reason="High complexity detected, adding analysis step",
                affected_steps=[step.id],
                details={"new_step": "detailed_analysis"},
            )
            adjustments.append(adj)

        # Si el resultado indica que algunos pasos no son necesarios
        if result.get("skip_recommended"):
            skip_ids = result.get("skip_recommended", [])
            for skip_id in skip_ids:
                skip_step = next((s for s in plan.steps if s.id == skip_id), None)
                if skip_step and skip_step.status == StepStatus.PENDING:
                    skip_step.status = StepStatus.SKIPPED
                    adj = Adjustment(
                        type=AdjustmentType.SKIP,
                        reason=f"Step {skip_id} not needed based on {step.id} result",
                        affected_steps=[skip_id],
                    )
                    adjustments.append(adj)

        return adjustments

    def _handle_failure(self, plan: DynamicPlan, failed_step: PlanStep) -> list[Adjustment]:
        """Maneja fallo de un paso."""
        adjustments = []

        # Buscar pasos dependientes y marcarlos como skipped
        for step in plan.steps:
            if failed_step.id in step.dependencies and step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED
                adj = Adjustment(
                    type=AdjustmentType.SKIP,
                    reason=f"Dependency {failed_step.id} failed",
                    affected_steps=[step.id],
                )
                adjustments.append(adj)

        # Agregar paso de recuperacion si es posible
        adj = Adjustment(
            type=AdjustmentType.ADD,
            reason=f"Recovery step for failed {failed_step.id}",
            affected_steps=[failed_step.id],
            details={"recovery_type": "manual_intervention"},
        )
        adjustments.append(adj)

        return adjustments

    def _calculate_confidence(self, plan: DynamicPlan) -> float:
        """Calcula confianza del plan basado en estado actual."""
        if not plan.steps:
            return 0.0

        completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        total = len(plan.steps)

        # Base: porcentaje completado
        base = completed / total

        # Penalizar por fallos
        fail_penalty = failed * 0.2

        # Penalizar por muchos ajustes
        adj_penalty = min(0.3, len(plan.adjustments) * 0.05)

        return max(0.0, min(1.0, base - fail_penalty - adj_penalty + 0.3))

    def get_status(self, plan_id: str) -> dict:
        """Obtiene estado actual del plan."""
        plan = self.plans.get(plan_id)
        if not plan:
            return {"error": f"Plan {plan_id} not found"}

        steps_by_status = {}
        for status in StepStatus:
            count = sum(1 for s in plan.steps if s.status == status)
            if count > 0:
                steps_by_status[status.value] = count

        return {
            "plan_id": plan.id,
            "description": plan.description,
            "total_steps": len(plan.steps),
            "steps_by_status": steps_by_status,
            "adjustments_count": len(plan.adjustments),
            "confidence": plan.confidence,
            "ready_steps": [s.id for s in self.get_ready_steps(plan)],
        }

    def optimize(self, plan_id: str) -> OptimizationResult:
        """Ejecuta optimizacion proactiva del plan."""
        plan = self.plans.get(plan_id)
        if not plan:
            return OptimizationResult(
                success=False,
                plan_id=plan_id,
                adjustments_made=[],
                new_confidence=0,
                message=f"Plan {plan_id} not found",
            )

        adjustments = []

        # Buscar oportunidades de paralelizacion
        ready = self.get_ready_steps(plan)
        if len(ready) > 1:
            adj = Adjustment(
                type=AdjustmentType.PARALLELIZE,
                reason=f"Found {len(ready)} parallelizable steps",
                affected_steps=[s.id for s in ready],
            )
            adjustments.append(adj)
            plan.adjustments.append(adj)

        # Buscar pasos que podrian saltarse
        pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
        for step in pending:
            # Heuristica: si un paso de validacion sigue a uno de implementacion
            # y la implementacion fue exitosa, podriamos saltarlo
            if "validat" in step.description.lower() or "verify" in step.description.lower():
                # Verificar si dependencias fueron exitosas
                deps_ok = all(
                    any(s.id == dep and s.status == StepStatus.COMPLETED for s in plan.steps)
                    for dep in step.dependencies
                )
                if deps_ok and random.random() > 0.7:  # Simulacion
                    adj = Adjustment(
                        type=AdjustmentType.SKIP,
                        reason="Validation may be redundant",
                        affected_steps=[step.id],
                        details={"reason": "dependencies_successful"},
                    )
                    adjustments.append(adj)

        plan.confidence = self._calculate_confidence(plan)

        return OptimizationResult(
            success=True,
            plan_id=plan_id,
            adjustments_made=adjustments,
            new_confidence=plan.confidence,
            message=f"Optimization complete: {len(adjustments)} adjustments",
        )


def main():
    parser = argparse.ArgumentParser(description="Plan Optimizer - Optimizacion dinamica de planes")
    parser.add_argument(
        "command", nargs="?", default="status", help="Comando (create, status, optimize, report)"
    )
    parser.add_argument("--plan", help="ID del plan")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    optimizer = PlanOptimizer()

    # Demo: crear plan de ejemplo
    demo_plan = optimizer.create_plan(
        "Implement authentication feature",
        [
            {"description": "Analyze requirements", "agent": "explorer"},
            {
                "description": "Design architecture",
                "agent": "architect",
                "dependencies": ["step_0"],
            },
            {
                "description": "Implement backend",
                "agent": "backend-specialist",
                "dependencies": ["step_1"],
            },
            {
                "description": "Implement frontend",
                "agent": "frontend-specialist",
                "dependencies": ["step_1"],
            },
            {
                "description": "Write tests",
                "agent": "test-engineer",
                "dependencies": ["step_2", "step_3"],
            },
            {"description": "Review code", "agent": "code-reviewer", "dependencies": ["step_4"]},
        ],
    )

    # Simular algunos resultados
    optimizer.report_result(demo_plan.id, "step_0", True, {"complexity": "medium"})
    optimizer.report_result(demo_plan.id, "step_1", True, {})

    if args.command == "status":
        result = optimizer.get_status(args.plan or demo_plan.id)
    elif args.command == "optimize":
        result = optimizer.optimize(args.plan or demo_plan.id)
        result = {
            "success": result.success,
            "adjustments": len(result.adjustments_made),
            "confidence": result.new_confidence,
            "message": result.message,
        }
    else:
        result = optimizer.get_status(demo_plan.id)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Plan Optimizer Status")
        print("=" * 40)
        for key, value in result.items():
            print(f"{key}: {value}")

    sys.exit(0)


if __name__ == "__main__":
    main()
