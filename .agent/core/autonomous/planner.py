"""
BrainAwarePlanner — Autonomous planning with Brain Network integration.

Phase 1 features:
- A) Recall semántico: consulta Brain antes de planificar
- B) Plan brain-aware: usa decisiones/patrones del Brain como constraints

Phase 2 features:
- C) Workflow condicional brain-driven: autonomía auto-triggered si Brain no tiene respuesta
- D) Loop con checkpoint en Brain: persistencia de estado para recoverability

Phase 3 features:
- E) Ingesta automática post-ejecución: todo outcome va al Brain
- F) Brain como orquestador: decide cuál flow/agent correr
- G) Audit trail automático: tracking de todas las ejecuciones

Usage:
    from core.autonomous import BrainAwarePlanner, AutonomousLoop

    # Phase 1: Planificador brain-aware
    planner = BrainAwarePlanner(brain_path=".agent/brain")
    context = planner.prepare("implementar feature X")

    # Phase 3: Brain como orquestador
    plan = planner.orchestrate("implementar auth")

    # Phase 2: Loop con checkpoints
    loop = AutonomousLoop(planner=planner)
    loop.run(objective="implementar módulo", max_iterations=5)
    # Si muere, recovery desde último checkpoint:
    loop = AutonomousLoop(planner=planner, resume_from="mi_checkpoint")
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add parent to path for Brain import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.brain import Brain, BrainNode

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class PlanContext:
    """Contexto enriquecido con conocimiento del Brain."""

    objective: str
    task_description: str

    # Brain findings
    relevant_nodes: list[BrainNode] = field(default_factory=list)
    similar_tasks: list[BrainNode] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Plan metadata
    plans_from_brain: list[str] = field(default_factory=list)
    patterns_to_apply: list[str] = field(default_factory=list)
    decisions_to_respect: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Genera resumen legible del contexto."""
        lines = [f"## Plan Context: {self.objective}", ""]

        if self.relevant_nodes:
            lines.append("### Conocimiento Relevante del Brain")
            for node in self.relevant_nodes[:3]:
                lines.append(f"- [[{node.slug}]]: {node.title}")
                if node.decisions:
                    lines.append(f"  Decisiones: {node.decisions[:100]}...")
            lines.append("")

        if self.warnings:
            lines.append("### Warnings del Brain")
            for w in self.warnings:
                lines.append(f"- ⚠️ {w}")
            lines.append("")

        if self.constraints:
            lines.append("### Constraints")
            for c in self.constraints:
                lines.append(f"- {c}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class ExecutionOutcome:
    """Resultado de una ejecución autónoma."""

    objective: str
    success: bool
    output: str
    errors: list[str] = field(default_factory=list)
    nodes_created: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_brain_node(self) -> dict[str, Any]:
        """Convierte a dict para ingestar al Brain."""
        return {
            "title": f"Autonomous: {self.objective}",
            "context": self.output[:500] if self.output else "",
            "decisions": "\n".join(f"- {d}" for d in self.constraints)
            if hasattr(self, "constraints")
            else "",
            "output": f"Success: {self.success}\nDuration: {self.duration_seconds:.1f}s",
            "area": "autonomous",
            "tags": ["autonomous", "execution"] + (["error"] if not self.success else ["success"]),
            "node_type": "session",
            "importance": "high" if not self.success else "normal",
        }


# ---------------------------------------------------------------------------
# BrainAwarePlanner
# ---------------------------------------------------------------------------


class BrainAwarePlanner:
    """Planificador autónomo que consulta el Brain antes de actuar.

    Integración bidirectional:
    - BEFORE: consulta Brain para evitar errores conocidos
    - AFTER: ingesta resultados al Brain para futuras ejecuciones
    """

    def __init__(
        self,
        brain_path: str | Path = ".agent/brain",
        app_id: str = "autonomous-planner",
    ) -> None:
        """Inicializa el planner con conexión al Brain.

        Args:
            brain_path: Ruta al directorio del Brain.
            app_id: Identificador de esta app para el Brain.
        """
        self.brain_path = Path(brain_path)
        self.app_id = app_id
        self._brain: Brain | None = None

    @property
    def brain(self) -> Brain:
        """Lazy load del Brain para evitar imports costosos."""
        if self._brain is None:
            self._brain = Brain(self.brain_path, app_id=self.app_id)
        return self._brain

    def prepare(self, objective: str, *, task_description: str = "") -> PlanContext:
        """Prepara contexto enriquecedo consultando el Brain.

        Args:
            objective: Objetivo de la tarea a planificar.
            task_description: Descripción opcional más detallada.

        Returns:
            PlanContext con conocimiento del Brain inyectado.
        """
        logger.info("BrainAwarePlanner.prepare: %s", objective)

        context = PlanContext(
            objective=objective,
            task_description=task_description or objective,
        )

        # A) Recall semántico — buscar conocimiento relevante
        try:
            context.relevant_nodes = self.brain.query(objective, limit=5)
            logger.info("  → %d nodos relevantes encontrados", len(context.relevant_nodes))
        except Exception as e:
            logger.warning("  → Error consultando Brain: %s", e)
            context.warnings.append(f"No se pudo consultar Brain: {e}")

        # Extraer constraints y warnings de nodos relacionados
        for node in context.relevant_nodes:
            self._extract_node_signals(node, context)

        # B) Plan brain-aware — detectar constraints de decisiones previas y patterns
        self._collect_decision_constraints(objective, context)
        self._collect_relevant_patterns(objective, context)

        logger.info(
            "  → Plan context: %d nodes, %d constraints, %d warnings",
            len(context.relevant_nodes),
            len(context.constraints),
            len(context.warnings),
        )

        return context

    def _extract_node_signals(self, node: BrainNode, context: PlanContext) -> None:
        """Extrae constraints, warnings y tasks similares de un nodo del Brain.

        Args:
            node: Nodo relacionado encontrado en el recall semántico.
            context: Contexto de plan a enriquecer (se muta in-place).
        """
        # Decisions como constraints
        if node.decisions:
            context.decisions_to_respect.append(f"[[{node.slug}]]: {node.decisions[:200]}")

        # Warnings de patterns fallidos
        if node.type == "pattern" and node.output:
            if "fail" in node.output.lower() or "error" in node.output.lower():
                context.warnings.append(f"Pattern [[{node.slug}]] tiene historial de errores")

        # Buscar tasks similares para no repetir
        if node.type == "session" and node.pending:
            context.similar_tasks.append(node)

    def _collect_decision_constraints(self, objective: str, context: PlanContext) -> None:
        """Consulta decisiones previas en el Brain y las agrega como constraints.

        Args:
            objective: Objetivo de la tarea para la búsqueda semántica.
            context: Contexto de plan a enriquecer (se muta in-place).
        """
        try:
            decisions = self.brain.query(f"decision {objective}", limit=3)
            for decision in decisions:
                if decision.type == "decision" or decision.type == "adr":
                    context.constraints.append(
                        f"Decisión documented en [[{decision.slug}]]: {decision.decisions[:150]}"
                    )
        except Exception as e:
            logger.warning("  → Error consultando decisiones: %s", e)

    def _collect_relevant_patterns(self, objective: str, context: PlanContext) -> None:
        """Consulta patterns relevantes en el Brain y los agrega para aplicar.

        Args:
            objective: Objetivo de la tarea para la búsqueda semántica.
            context: Contexto de plan a enriquecer (se muta in-place).
        """
        try:
            patterns = self.brain.query(f"pattern {objective}", limit=2)
            for pattern in patterns:
                if pattern.type == "pattern":
                    context.patterns_to_apply.append(
                        f"Pattern [[{pattern.slug}]]: {pattern.context[:100]}"
                    )
        except Exception as e:
            logger.warning("  → Error consultando patterns: %s", e)

    def ingest_outcome(
        self,
        objective: str,
        success: bool,
        output: str,
        errors: list[str] | None = None,
        duration_seconds: float = 0.0,
    ) -> BrainNode:
        """Ingesta el resultado de una ejecución al Brain.

        Args:
            objective: Objetivo original de la tarea.
            success: Si la ejecución fue exitosa.
            output: Output o resultado de la ejecución.
            errors: Lista de errores (si falló).
            duration_seconds: Duración de la ejecución.

        Returns:
            El nodo creado en el Brain.
        """
        logger.info("Ingesting outcome: %s (success=%s)", objective, success)

        context_parts = [f"Ejecución autónoma de: {objective}"]
        if output:
            context_parts.append(f"\nOutput: {output[:300]}")

        decisions_parts = []
        if success:
            decisions_parts.append("Resultado: ÉXITO")
        else:
            decisions_parts.append("Resultado: FALLO")
            if errors:
                decisions_parts.append("\nErrores:")
                decisions_parts.extend(f"- {e}" for e in errors)

        output_parts = [
            f"Duration: {duration_seconds:.1f}s",
            f"Success: {success}",
        ]

        node = self.brain.ingest(
            title=f"Autonomous: {objective}",
            context="\n".join(context_parts),
            decisions="\n".join(decisions_parts),
            output="\n".join(output_parts),
            area="autonomous",
            tags=["autonomous", "execution", "outcome", "success" if success else "error"],
            node_type="session",
            importance="high" if not success else "normal",
        )

        logger.info("  → Created node: %s", node.slug)
        return node

    def check_similar_failures(self, objective: str) -> list[str]:
        """Check si hay failures previos similares en el Brain.

        Args:
            objective: Objetivo a verificar.

        Returns:
            Lista de warnings con failures previos.
        """
        warnings: list[str] = []

        try:
            # Buscar nodos con tag "error" o "failure" recientes
            recent_nodes = self.brain.list_nodes(
                node_type="session",
                tag="error",
            )

            for node in recent_nodes[:5]:
                # Verificar similarity con objective
                if any(
                    keyword in objective.lower()
                    for keyword in node.title.lower().split()
                    if len(keyword) > 4
                ):
                    warnings.append(f"Failure previo en [[{node.slug}]]: {node.output[:100]}")
        except Exception as e:
            logger.warning("Error checking failures: %s", e)

        return warnings


# ---------------------------------------------------------------------------
# Convenience function for quick integration
# ---------------------------------------------------------------------------


def create_brain_aware_planner(
    brain_path: str | Path = ".agent/brain",
) -> BrainAwarePlanner:
    """Factory para crear un planner conectado al Brain.

    Args:
        brain_path: Ruta al Brain.

    Returns:
        BrainAwarePlanner listo para usar.
    """
    return BrainAwarePlanner(brain_path=brain_path)


# ---------------------------------------------------------------------------
# Phase 2: AutonomousLoop — Loop with Brain Checkpoints
# ---------------------------------------------------------------------------


@dataclass
class LoopCheckpoint:
    """Checkpoint de un loop autónomo."""

    checkpoint_id: str
    objective: str
    iteration: int
    state: dict[str, Any]
    timestamp: str
    next_action: str = ""
    context_snapshot: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializa checkpoint."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopCheckpoint:
        """Deserializa checkpoint."""
        return cls(**data)


@dataclass
class LoopConfig:
    """Configuración para un loop autónomo."""

    max_iterations: int = 5
    checkpoint_every: int = 1  # Cada cuántas iteraciones guardar checkpoint
    abort_on_error_count: int = 3  # Abortar después de N errores consecutivos
    continue_on_empty_brain: bool = True  # Si Brain no tiene info, continuar igual
    verbose: bool = True


# ---------------------------------------------------------------------------
# AutonomousLoop
# ---------------------------------------------------------------------------


class AutonomousLoop:
    """Loop autónomo con persistencia de estado en Brain.

    Características:
    - Cada iteración puede checkpointearse en Brain
    - Recovery desde último checkpoint si el loop muere
    - Integración con BrainAwarePlanner para contexto enriquecido
    - Abort threshold para evitar loops infinitos
    """

    def __init__(
        self,
        planner: BrainAwarePlanner | None = None,
        brain_path: str | Path = ".agent/brain",
        config: LoopConfig | None = None,
    ) -> None:
        """Inicializa el loop.

        Args:
            planner: Planner brain-aware (crea uno si no se pasa).
            brain_path: Ruta al Brain (para crear planner).
            config: Configuración del loop.
        """
        self.config = config or LoopConfig()
        self._planner = planner or create_brain_aware_planner(brain_path)
        self._current_checkpoint: LoopCheckpoint | None = None
        self._checkpoints: list[LoopCheckpoint] = []

    @property
    def brain(self) -> Brain:
        """Access al Brain via planner."""
        return self._planner.brain

    def _create_checkpoint(
        self,
        objective: str,
        iteration: int,
        state: dict[str, Any],
        next_action: str = "",
    ) -> LoopCheckpoint:
        """Crea un checkpoint en el Brain."""
        checkpoint_id = f"{objective[:20]}-{iteration}-{datetime.now(UTC).strftime('%H%M%S')}"

        checkpoint = LoopCheckpoint(
            checkpoint_id=checkpoint_id,
            objective=objective,
            iteration=iteration,
            state=state,
            timestamp=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            next_action=next_action,
            context_snapshot=self._planner.prepare(objective).summary()[:500],
        )

        # Guardar en Brain como nodo especial
        self.brain.ingest(
            title=f"Checkpoint: {objective[:40]}",
            context=f"Loop checkpoint ID: {checkpoint_id}\n"
            f"Iteration: {iteration}\n"
            f"State: {str(state)[:300]}\n"
            f"Next action: {next_action}",
            decisions="Checkpoint para recovery de loop autónomo",
            output=f"Iteration {iteration} de loop para: {objective}",
            area="autonomous",
            tags=["checkpoint", "autonomous-loop", "recovery"],
            node_type="session",
            importance="high",
        )

        if self.config.verbose:
            logger.info("  → Checkpoint creado: %s (iter %d)", checkpoint_id, iteration)

        self._current_checkpoint = checkpoint
        self._checkpoints.append(checkpoint)
        return checkpoint

    def _get_latest_checkpoint(self, objective: str) -> LoopCheckpoint | None:
        """Recupera el último checkpoint para un objetivo."""
        try:
            checkpoints = self.brain.list_nodes(
                node_type="session",
                tag="checkpoint",
            )

            # Filtrar por objetivo
            relevant = [n for n in checkpoints if objective.lower() in n.title.lower()]

            if not relevant:
                return None

            # Tomar el más reciente
            latest = relevant[0]

            # Crear checkpoint desde el nodo del Brain
            return LoopCheckpoint(
                checkpoint_id=f"recovery-{latest.slug}",
                objective=objective,
                iteration=int(latest.output.split("iteration ")[1].split()[0])
                if "iteration" in latest.output
                else 0,
                state={},
                timestamp=latest.date,
                context_snapshot=latest.context[:500] if latest.context else "",
            )
        except Exception as e:
            logger.warning("Error recovering checkpoint: %s", e)
            return None

    def run(
        self,
        objective: str,
        executor_fn: Callable[..., Any] | None = None,
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        """Ejecuta el loop autónomo.

        Args:
            objective: Objetivo a lograr.
            executor_fn: Función que ejecuta cada iteración (recibe context, retorna result).
            max_iterations: Override de max_iterations del config.

        Returns:
            Dict con resultados del loop.
        """
        max_iters = max_iterations or self.config.max_iterations
        results: list[dict[str, Any]] = []
        error_count = 0
        start_time = time.monotonic()

        # Preparar contexto inicial
        context = self._planner.prepare(objective)

        if self.config.verbose:
            logger.info("=== AutonomousLoop.start: %s", objective)
            logger.info("  → Contexto: %d nodos relevantes", len(context.relevant_nodes))
            if context.warnings:
                logger.info("  → Warnings: %s", context.warnings)

        # Loop principal
        for iteration in range(1, max_iters + 1):
            if self.config.verbose:
                logger.info("--- Iteración %d/%d", iteration, max_iters)

            try:
                # Ejecutar iteración
                if executor_fn:
                    result = executor_fn(context, iteration)
                else:
                    result = {"status": "completed", "iteration": iteration}

                results.append(result)
                error_count = 0  # Reset on success

                # Checkpoint si corresponde
                if iteration % self.config.checkpoint_every == 0:
                    self._create_checkpoint(
                        objective=objective,
                        iteration=iteration,
                        state={"results": results[-5:], "iteration": iteration},
                        next_action=result.get("next_action", "done"),
                    )

                # Si el executor indica que terminó, salir
                if result.get("status") == "done":
                    break

            except Exception as e:
                error_count += 1
                logger.error("  → Error en iteración %d: %s", iteration, e)
                results.append({"status": "error", "iteration": iteration, "error": str(e)})

                # Abortar si hay demasiados errores
                if error_count >= self.config.abort_on_error_count:
                    logger.warning("Abortando por %d errores consecutivos", error_count)
                    break

        # Ingestar resultado final
        duration_seconds = time.monotonic() - start_time
        self._planner.ingest_outcome(
            objective=objective,
            success=error_count == 0,
            output=f"Loop completado: {len(results)} iteraciones",
            errors=[r.get("error", "") for r in results if "error" in r],
            duration_seconds=duration_seconds,
        )

        return {
            "objective": objective,
            "iterations": len(results),
            "success": error_count == 0,
            "results": results,
            "duration_seconds": duration_seconds,
        }

    def resume(self, objective: str) -> dict[str, Any]:
        """Recupera y continua desde un checkpoint.

        Args:
            objective: Objetivo del checkpoint a recuperar.

        Returns:
            Info del checkpoint recuperado.
        """
        checkpoint = self._get_latest_checkpoint(objective)

        if not checkpoint:
            logger.info("No se encontró checkpoint para: %s", objective)
            return {"status": "no_checkpoint", "objective": objective}

        self._current_checkpoint = checkpoint

        if self.config.verbose:
            logger.info(
                "=== Recovery desde checkpoint: %s (iter %d)",
                checkpoint.checkpoint_id,
                checkpoint.iteration,
            )

        return {
            "status": "recovered",
            "checkpoint": checkpoint.to_dict(),
            "resume_from_iteration": checkpoint.iteration + 1,
        }


# ---------------------------------------------------------------------------
# Phase 3: Brain Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class OrchestratedPlan:
    """Plan orquestado por el Brain."""

    objective: str
    recommended_flow: str
    steps: list[str]
    constraints: list[str]
    estimated_risk: str  # low | medium | high
    reasoning: str

    def summary(self) -> str:
        """Resumen legible del plan."""
        lines = [
            f"## Plan Orquestado: {self.objective}",
            f"**Flow**: {self.recommended_flow}",
            f"**Riesgo**: {self.estimated_risk}",
            "",
            "### Pasos",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. {step}")
        if self.constraints:
            lines.append("")
            lines.append("### Constraints del Brain")
            for c in self.constraints:
                lines.append(f"- {c}")
        return "\n".join(lines)


class BrainOrchestrator:
    """Brain como orquestador — decide qué flow/agent correr basándose en conocimiento.

    Analiza el objetivo contra el Brain y recomienda:
    - Qué flow usar (autonomous, sequential, parallel, etc.)
    - Qué constraints aplicar
    - Qué risks anticipate
    """

    # Mapeo de keywords a flows recomendados
    FLOW_MAP: dict[str, str] = {
        "implement": "autonomous-sequential",
        "build": "autonomous-sequential",
        "create": "autonomous-sequential",
        "fix": "focused-autonomous",
        "debug": "focused-autonomous",
        "refactor": "autonomous-with-review",
        "audit": "parallel-investigation",
        "review": "parallel-investigation",
        "test": "sequential-with-validation",
        "deploy": "sequential-with-gates",
    }

    def __init__(
        self,
        brain_path: str | Path = ".agent/brain",
        app_id: str = "brain-orchestrator",
    ) -> None:
        """Inicializa el orquestador.

        Args:
            brain_path: Ruta al Brain.
            app_id: Identificador.
        """
        self._brain_path = Path(brain_path)
        self._app_id = app_id
        self._brain: Brain | None = None

    @property
    def brain(self) -> Brain:
        """Lazy load."""
        if self._brain is None:
            self._brain = Brain(self._brain_path, app_id=self._app_id)
        return self._brain

    def orchestrate(self, objective: str) -> OrchestratedPlan:
        """Orquesta un plan basándose en el Brain.

        Args:
            objective: Objetivo a orquestar.

        Returns:
            OrchestratedPlan con flujo recomendado.
        """
        logger.info("BrainOrchestrator.orchestrate: %s", objective)

        # 1. Detectar flow basado en keywords
        recommended_flow = "autonomous-sequential"
        flow_keyword = "default"
        for keyword, flow in self.FLOW_MAP.items():
            if keyword in objective.lower():
                recommended_flow = flow
                flow_keyword = keyword
                break

        # 2. Consultar Brain para constraints y decisiones
        context = BrainAwarePlanner(brain_path=self._brain_path).prepare(objective)

        # 3. Estimar riesgo basándose en decisiones/warnings
        estimated_risk = "low"
        if context.warnings:
            estimated_risk = "medium"
        if len(context.warnings) > 2:
            estimated_risk = "high"

        # 4. Generar steps
        steps = self._generate_steps(objective, recommended_flow, context)

        # 5. Extraer constraints
        constraints = [
            *context.decisions_to_respect,
            *[f"⚠️ {w}" for w in context.warnings],
        ]

        reasoning = (
            f"Flow '{recommended_flow}' detectado por keyword '{flow_keyword}'. "
            f"{len(context.relevant_nodes)} nodos relevantes del Brain. "
            f"Riesgo estimado: {estimated_risk}."
        )

        plan = OrchestratedPlan(
            objective=objective,
            recommended_flow=recommended_flow,
            steps=steps,
            constraints=constraints,
            estimated_risk=estimated_risk,
            reasoning=reasoning,
        )

        # 6. Ingestar el plan al Brain
        self.brain.ingest(
            title=f"Plan orquestado: {objective[:50]}",
            context=plan.summary(),
            decisions=f"Flow: {recommended_flow} | Riesgo: {estimated_risk}",
            output=f"Plan orquestado por Brain para: {objective}",
            area="autonomous",
            tags=["orchestrated", "plan", "brain-orchestrator"],
            node_type="decision",
            importance="high",
        )

        return plan

    def _generate_steps(
        self,
        objective: str,
        flow: str,
        context: PlanContext,
    ) -> list[str]:
        """Genera steps según el flow."""
        base_steps = [
            "1. Preparar contexto (Brain query)",
            "2. Planificar implementación",
            "3. Ejecutar con validación",
            "4. Tests y verificación",
            "5. Documentar y cerrar",
        ]

        if flow == "focused-autonomous":
            return [
                "1. Identificar el problema exacto",
                "2. Buscar patrones similares en Brain",
                "3. Implementar fix focalizado",
                "4. Validar con tests",
            ]

        if flow == "parallel-investigation":
            return [
                "1. Dividir investigación en buckets",
                "2. Ejecutar en paralelo",
                "3. Consolidar findings",
                "4. Presentar recomendación",
            ]

        if flow == "autonomous-with-review":
            return [
                "1. Planificar refactor",
                "2. Implementar cambios",
                "3. Review de código",
                "4. Validar tests",
                "5. Merge",
            ]

        return base_steps

    def audit_trail(self, days: int = 7) -> list[dict[str, Any]]:
        """Genera audit trail de ejecuciones autónomas.

        Args:
            days: Cuántos días atrás incluir.

        Returns:
            Lista de entradas de audit.
        """
        all_nodes = self.brain.list_nodes(node_type="session", tag="autonomous")

        audit_entries = []
        for node in all_nodes:
            if node.area == "autonomous":
                audit_entries.append(
                    {
                        "slug": node.slug,
                        "title": node.title,
                        "date": node.date,
                        "success": "success" in node.tags,
                        "importance": node.importance,
                        "context": node.context[:200] if node.context else "",
                    }
                )

        return audit_entries


# ---------------------------------------------------------------------------
# Exported API
# ---------------------------------------------------------------------------

from dataclasses import asdict

__all__ = [
    "BrainAwarePlanner",
    "PlanContext",
    "ExecutionOutcome",
    "create_brain_aware_planner",
    # Phase 2
    "AutonomousLoop",
    "LoopCheckpoint",
    "LoopConfig",
    # Phase 3
    "BrainOrchestrator",
    "OrchestratedPlan",
]
