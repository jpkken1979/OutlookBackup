# mypy: ignore-errors
#!/usr/bin/env python3
"""
Self Improvement - Sistema de auto-mejora continua del ecosistema.

Analiza patrones de exito/fallo de los agentes y propone mejoras
automaticamente a prompts, skills, y configuraciones.

Uso:
    from .agent.core.self_improvement import SelfImprover

    improver = SelfImprover()

    # Analizar ejecuciones recientes
    insights = await improver.analyze_recent_executions()

    # Proponer mejoras
    proposals = await improver.propose_improvements()

    # Aplicar mejoras (con supervision humana)
    await improver.apply_improvement(proposal_id, approved=True)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("antigravity.core.self_improvement")


class ImprovementType(Enum):
    """Tipos de mejoras posibles."""

    PROMPT_ENHANCEMENT = "prompt_enhancement"
    SKILL_ADDITION = "skill_addition"
    AGENT_DELEGATION = "agent_delegation"
    ERROR_HANDLING = "error_handling"
    PERFORMANCE = "performance"
    WORKFLOW = "workflow"


class ImprovementStatus(Enum):
    """Estado de una propuesta de mejora."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    REVERTED = "reverted"


@dataclass
class ExecutionMetrics:
    """Metricas de una ejecucion de agente."""

    agent_name: str
    task: str
    success: bool
    duration_ms: float
    quality_score: float
    confidence: float
    retries: int
    errors: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PerformanceInsight:
    """Insight sobre el rendimiento de un agente."""

    agent_name: str
    metric_name: str
    current_value: float
    baseline_value: float
    trend: str  # "improving", "stable", "degrading"
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImprovementProposal:
    """Propuesta de mejora."""

    id: str
    improvement_type: ImprovementType
    target: str  # agente, skill, o workflow afectado
    title: str
    description: str
    rationale: str
    expected_impact: str
    implementation: str  # Codigo o cambios propuestos
    risk_level: str  # "low", "medium", "high"
    status: ImprovementStatus = ImprovementStatus.PROPOSED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    applied_at: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["improvement_type"] = self.improvement_type.value
        d["status"] = self.status.value
        return d


class SelfImprover:
    """
    Sistema de auto-mejora continua.

    Analiza metricas de ejecucion y propone mejoras al ecosistema.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".antigravity" / "self_improvement"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.executions_path = self.storage_path / "executions"
        self.executions_path.mkdir(exist_ok=True)

        self.proposals_path = self.storage_path / "proposals"
        self.proposals_path.mkdir(exist_ok=True)

        self.proposals: dict[str, ImprovementProposal] = {}
        self._load_proposals()

    def _load_proposals(self):
        """Cargar propuestas existentes."""
        for file in self.proposals_path.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                proposal = ImprovementProposal(
                    id=data["id"],
                    improvement_type=ImprovementType[data["improvement_type"].upper()],
                    target=data["target"],
                    title=data["title"],
                    description=data["description"],
                    rationale=data["rationale"],
                    expected_impact=data["expected_impact"],
                    implementation=data["implementation"],
                    risk_level=data["risk_level"],
                    status=ImprovementStatus[data["status"].upper()],
                    created_at=data["created_at"],
                    applied_at=data.get("applied_at"),
                )
                self.proposals[proposal.id] = proposal
            except Exception as e:
                logger.warning(f"No se pudo cargar propuesta {file}: {e}")

    def record_execution(self, metrics: ExecutionMetrics = None, **kwargs):
        """Registrar metricas de una ejecucion."""
        if metrics is None:
            metrics = ExecutionMetrics(
                agent_name=kwargs.get("agent_name", ""),
                task=kwargs.get("task", ""),
                success=kwargs.get("success", True),
                duration_ms=kwargs.get("duration_ms", 0.0),
                quality_score=kwargs.get("quality_score", 1.0),
                confidence=kwargs.get("confidence", 1.0),
                retries=kwargs.get("retries", 0),
                errors=kwargs.get("errors", []),
            )

        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.executions_path / f"{date_str}.jsonl"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics.to_dict()) + "\n")

    def get_agent_metrics(self, agent_name: str) -> dict:
        """Obtener metricas agregadas de un agente."""
        executions = self._load_recent_executions(days=30, agent_name=agent_name)

        if not executions:
            return {
                "success_rate": 0,
                "avg_duration_ms": 0,
                "avg_quality": 0,
                "total_executions": 0,
            }

        return {
            "success_rate": sum(1 for e in executions if e.success) / len(executions),
            "avg_duration_ms": sum(e.duration_ms for e in executions) / len(executions),
            "avg_quality": sum(e.quality_score for e in executions) / len(executions),
            "total_executions": len(executions),
        }

    def analyze_recent_executions(self, days: int = 7) -> list[PerformanceInsight]:
        """
        Analizar ejecuciones recientes y generar insights.

        Returns:
            Lista de insights sobre rendimiento
        """
        executions = self._load_recent_executions(days)

        if not executions:
            return []

        insights = []

        # Agrupar por agente
        by_agent: dict[str, list[ExecutionMetrics]] = {}
        for ex in executions:
            if ex.agent_name not in by_agent:
                by_agent[ex.agent_name] = []
            by_agent[ex.agent_name].append(ex)

        for agent_name, agent_execs in by_agent.items():
            # Tasa de exito
            success_rate = sum(1 for e in agent_execs if e.success) / len(agent_execs)

            if success_rate < 0.8:
                insights.append(
                    PerformanceInsight(
                        agent_name=agent_name,
                        metric_name="success_rate",
                        current_value=success_rate,
                        baseline_value=0.9,
                        trend="degrading" if success_rate < 0.7 else "stable",
                        recommendation=f"Revisar SYSTEM_PROMPT de {agent_name} para mejorar precision",
                    )
                )

            # Calidad promedio
            avg_quality = sum(e.quality_score for e in agent_execs) / len(agent_execs)

            if avg_quality < 0.7:
                insights.append(
                    PerformanceInsight(
                        agent_name=agent_name,
                        metric_name="quality_score",
                        current_value=avg_quality,
                        baseline_value=0.8,
                        trend="degrading",
                        recommendation=f"Agregar reflexion obligatoria para {agent_name}",
                    )
                )

            # Reintentos excesivos
            avg_retries = sum(e.retries for e in agent_execs) / len(agent_execs)

            if avg_retries > 2:
                insights.append(
                    PerformanceInsight(
                        agent_name=agent_name,
                        metric_name="avg_retries",
                        current_value=avg_retries,
                        baseline_value=1.0,
                        trend="degrading",
                        recommendation=f"Mejorar manejo de errores en {agent_name}",
                    )
                )

            # Errores comunes
            all_errors = [err for e in agent_execs for err in e.errors]
            if all_errors:
                error_counts: dict[str, int] = {}
                for err in all_errors:
                    err_key = err[:50]
                    error_counts[err_key] = error_counts.get(err_key, 0) + 1

                most_common = max(error_counts.items(), key=lambda x: x[1])
                if most_common[1] > 3:
                    insights.append(
                        PerformanceInsight(
                            agent_name=agent_name,
                            metric_name="recurring_error",
                            current_value=float(most_common[1]),
                            baseline_value=0.0,
                            trend="degrading",
                            recommendation=f"Error recurrente: '{most_common[0]}' - agregar handling especifico",
                        )
                    )

        logger.info(f"Generados {len(insights)} insights de {len(executions)} ejecuciones")

        return insights

    def propose_improvements(self) -> list[ImprovementProposal]:
        """
        Proponer mejoras basadas en analisis de ejecuciones.

        Returns:
            Lista de propuestas de mejora
        """
        insights = self.analyze_recent_executions()

        new_proposals = []

        for insight in insights:
            proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(new_proposals)}"

            if insight.metric_name == "success_rate":
                proposal = ImprovementProposal(
                    id=proposal_id,
                    improvement_type=ImprovementType.PROMPT_ENHANCEMENT,
                    target=insight.agent_name,
                    title=f"Mejorar precision de {insight.agent_name}",
                    description=f"La tasa de exito actual ({insight.current_value:.0%}) "
                    f"esta por debajo del baseline ({insight.baseline_value:.0%})",
                    rationale=insight.recommendation,
                    expected_impact=f"Aumentar tasa de exito a >{insight.baseline_value:.0%}",
                    implementation=f"""
# Agregar a SYSTEM_PROMPT.md de {insight.agent_name}:

## Verificacion Pre-Ejecucion
Antes de ejecutar, verificar:
1. Tengo suficiente contexto?
2. La tarea esta dentro de mi expertise?
3. Hay ambiguedades que resolver?

Si alguna respuesta es NO, solicitar clarificacion.
""",
                    risk_level="low",
                )

            elif insight.metric_name == "quality_score":
                proposal = ImprovementProposal(
                    id=proposal_id,
                    improvement_type=ImprovementType.WORKFLOW,
                    target=insight.agent_name,
                    title=f"Agregar reflexion obligatoria a {insight.agent_name}",
                    description=f"La calidad promedio ({insight.current_value:.0%}) necesita mejora",
                    rationale=insight.recommendation,
                    expected_impact="Aumentar calidad de outputs",
                    implementation=f"""
# Modificar invocacion de {insight.agent_name}:

result = await agent.run(
    task=task,
    use_reflection=True,  # CAMBIO: Habilitar reflexion
    max_retries=2
)
""",
                    risk_level="low",
                )

            elif insight.metric_name == "recurring_error":
                proposal = ImprovementProposal(
                    id=proposal_id,
                    improvement_type=ImprovementType.ERROR_HANDLING,
                    target=insight.agent_name,
                    title="Agregar handling para error recurrente",
                    description=f"Error detectado {int(insight.current_value)} veces",
                    rationale=insight.recommendation,
                    expected_impact="Reducir fallos por este error",
                    implementation="""
# Agregar try-except especifico para este error
try:
    result = await self.execute(task)
except SpecificError as e:
    # Handling especifico
    result = await self.fallback_strategy(task, e)
""",
                    risk_level="medium",
                )

            else:
                proposal = ImprovementProposal(
                    id=proposal_id,
                    improvement_type=ImprovementType.PERFORMANCE,
                    target=insight.agent_name,
                    title=f"Optimizar {insight.metric_name} de {insight.agent_name}",
                    description=insight.recommendation,
                    rationale=f"Valor actual: {insight.current_value}, baseline: {insight.baseline_value}",
                    expected_impact="Mejorar rendimiento general",
                    implementation="# Revisar y optimizar manualmente",
                    risk_level="low",
                )

            new_proposals.append(proposal)
            self.proposals[proposal.id] = proposal
            self._save_proposal(proposal)

        logger.info(f"Generadas {len(new_proposals)} propuestas de mejora")

        return new_proposals

    def _save_proposal(self, proposal: ImprovementProposal):
        """Guardar propuesta a disco."""
        file_path = self.proposals_path / f"{proposal.id}.json"
        file_path.write_text(json.dumps(proposal.to_dict(), indent=2, ensure_ascii=False))

    def apply_improvement(self, proposal_id: str, approved: bool = False) -> bool:
        """
        Aplicar una mejora propuesta.

        Args:
            proposal_id: ID de la propuesta
            approved: Si fue aprobada por humano

        Returns:
            True si se aplico exitosamente
        """
        proposal = self.proposals.get(proposal_id)

        if not proposal:
            logger.error(f"Propuesta {proposal_id} no encontrada")
            return False

        if not approved:
            proposal.status = ImprovementStatus.REJECTED
            self._save_proposal(proposal)
            logger.info(f"Propuesta {proposal_id} rechazada")
            return False

        applied = False

        if proposal.improvement_type == ImprovementType.PROMPT_ENHANCEMENT:
            applied = self._apply_prompt_enhancement(proposal)
        elif proposal.improvement_type == ImprovementType.ERROR_HANDLING:
            applied = self._apply_error_handling(proposal)
        else:
            logger.info(
                "Tipo %s requiere aplicación manual: %s",
                proposal.improvement_type.value,
                proposal.implementation,
            )
            applied = True  # Registrar como aplicada (manual)

        if applied:
            proposal.status = ImprovementStatus.APPLIED
            proposal.applied_at = datetime.now().isoformat()
        else:
            proposal.status = ImprovementStatus.PROPOSED  # Revertir a propuesta
            logger.warning("No se pudo aplicar propuesta %s", proposal_id)

        self._save_proposal(proposal)
        return applied

    def _apply_prompt_enhancement(self, proposal: ImprovementProposal) -> bool:
        """Aplica una mejora de prompt al SYSTEM_PROMPT.md del agente.

        Añade la sección de mejora al final del SYSTEM_PROMPT.md existente.

        Args:
            proposal: Propuesta con el agente objetivo y la implementación.

        Returns:
            True si se aplicó exitosamente.
        """
        agent_dir = Path(__file__).parent.parent.parent / "agents" / proposal.target
        prompt_file = agent_dir / "SYSTEM_PROMPT.md"

        if not prompt_file.exists():
            logger.warning("SYSTEM_PROMPT.md no encontrado para %s", proposal.target)
            return False

        try:
            current = prompt_file.read_text(encoding="utf-8")
            separator = "\n\n---\n\n"
            header = f"<!-- Auto-improvement {proposal.id} ({proposal.created_at}) -->\n"
            new_content = current + separator + header + proposal.implementation.strip() + "\n"
            prompt_file.write_text(new_content, encoding="utf-8")
            logger.info("Prompt mejorado para agente %s", proposal.target)
            return True
        except Exception as e:
            logger.error("Error aplicando mejora de prompt: %s", e)
            return False

    def _apply_error_handling(self, proposal: ImprovementProposal) -> bool:
        """Registra un error conocido en el archivo de avoidances del agente.

        Args:
            proposal: Propuesta con el error y la estrategia de manejo.

        Returns:
            True si se registró exitosamente.
        """
        agent_dir = Path(__file__).parent.parent.parent / "agents" / proposal.target
        avoidances_file = agent_dir / "memory" / "avoidances.json"
        avoidances_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing: list[dict] = []
            if avoidances_file.exists():
                existing = json.loads(avoidances_file.read_text(encoding="utf-8"))

            existing.append(
                {
                    "proposal_id": proposal.id,
                    "error_pattern": proposal.title,
                    "mitigation": proposal.implementation,
                    "added_at": datetime.now().isoformat(),
                }
            )

            avoidances_file.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Error handling registrado para agente %s", proposal.target)
            return True
        except Exception as e:
            logger.error("Error registrando avoidance: %s", e)
            return False

    def list_proposals(self, status: ImprovementStatus | None = None) -> list[ImprovementProposal]:
        """Listar propuestas, opcionalmente filtradas por estado."""
        proposals = list(self.proposals.values())

        if status:
            proposals = [p for p in proposals if p.status == status]

        return sorted(proposals, key=lambda p: p.created_at, reverse=True)

    def get_improvement_report(self) -> dict:
        """Generar reporte de mejoras."""
        all_proposals = list(self.proposals.values())

        return {
            "total_proposals": len(all_proposals),
            "by_status": {
                status.value: sum(1 for p in all_proposals if p.status == status)
                for status in ImprovementStatus
            },
            "by_type": {
                itype.value: sum(1 for p in all_proposals if p.improvement_type == itype)
                for itype in ImprovementType
            },
            "recent_applied": [
                p.to_dict() for p in all_proposals if p.status == ImprovementStatus.APPLIED
            ][:5],
        }

    # -------------------------------------------------------------------
    # Prompt Optimization Engine
    # -------------------------------------------------------------------

    def analyze_prompt_effectiveness(self, agent_name: str, days: int = 30) -> dict:
        """Analiza la efectividad del prompt actual de un agente.

        Examina las metricas de ejecucion para identificar patrones
        de exito y fallo, y genera sugerencias de optimizacion.

        Args:
            agent_name: Nombre del agente a analizar
            days: Dias de historial a considerar

        Returns:
            Dict con analisis y sugerencias de optimizacion
        """
        metrics = self.get_agent_metrics(agent_name)
        if not metrics or metrics.get("total_executions", 0) < 5:
            return {
                "agent": agent_name,
                "status": "insufficient_data",
                "message": f"Se necesitan al menos 5 ejecuciones (tiene {metrics.get('total_executions', 0)})",
                "suggestions": [],
            }

        success_rate = metrics.get("success_rate", 0)
        avg_quality = metrics.get("avg_quality", 0)
        avg_duration = metrics.get("avg_duration_ms", 0)

        suggestions: list[dict] = []

        # Analisis 1: Success rate bajo
        if success_rate < 0.80:
            suggestions.append(
                {
                    "type": "prompt_enhancement",
                    "priority": "high",
                    "issue": f"Success rate bajo ({success_rate:.0%})",
                    "suggestion": "Agregar instrucciones de verificacion al system prompt",
                    "implementation": (
                        "Anadir al final del prompt: "
                        "'Before responding, verify: 1) All requirements addressed, "
                        "2) Code compiles/runs, 3) Edge cases considered.'"
                    ),
                }
            )

        # Analisis 2: Calidad baja
        if avg_quality < 0.70:
            suggestions.append(
                {
                    "type": "prompt_enhancement",
                    "priority": "high",
                    "issue": f"Calidad promedio baja ({avg_quality:.2f})",
                    "suggestion": "Activar reflexion post-generacion",
                    "implementation": (
                        "Agregar al prompt: "
                        "'After generating your response, critically review it: "
                        "Is it complete? Is it correct? Does it follow best practices? "
                        "Revise if needed before submitting.'"
                    ),
                }
            )

        # Analisis 3: Errores recurrentes
        error_counts: dict[str, int] = {}
        for exec_data in self._load_recent_executions(days=days, agent_name=agent_name):
            for err in exec_data.errors:
                error_counts[err] = error_counts.get(err, 0) + 1

        for error_type, count in error_counts.items():
            if count >= 3:
                suggestions.append(
                    {
                        "type": "error_prevention",
                        "priority": "medium",
                        "issue": f"Error recurrente: {error_type} ({count} veces)",
                        "suggestion": f"Agregar guardia especifica para {error_type}",
                        "implementation": (
                            f"Agregar al prompt: 'IMPORTANT: You have previously "
                            f"encountered {error_type} errors. Before proceeding, "
                            f"explicitly check for and prevent this error type.'"
                        ),
                    }
                )

        # Analisis 4: Duracion excesiva
        if avg_duration > 30000:  # > 30 seconds
            suggestions.append(
                {
                    "type": "performance",
                    "priority": "low",
                    "issue": f"Duracion promedio alta ({avg_duration / 1000:.1f}s)",
                    "suggestion": "Simplificar instrucciones para reducir tokens",
                    "implementation": (
                        "Revisar el prompt para eliminar redundancias. "
                        "Considerar usar bullet points en vez de prosa."
                    ),
                }
            )

        # Analisis 5: Success rate excelente - proponer expansion
        if success_rate > 0.95 and metrics.get("total_executions", 0) > 20:
            suggestions.append(
                {
                    "type": "capability_expansion",
                    "priority": "low",
                    "issue": "Agente consistentemente exitoso",
                    "suggestion": "Considerar expandir sus capacidades",
                    "implementation": (
                        "Este agente tiene un track record excelente. "
                        "Considerar delegarle tareas mas complejas o "
                        "expandir su scope de responsabilidad."
                    ),
                }
            )

        return {
            "agent": agent_name,
            "status": "analyzed",
            "metrics": metrics,
            "suggestions": suggestions,
            "auto_applicable": [
                s
                for s in suggestions
                if s["priority"] == "high" and s["type"] == "prompt_enhancement"
            ],
        }

    def _load_recent_executions(
        self, days: int = 30, agent_name: str | None = None
    ) -> list[ExecutionMetrics]:
        """Carga ejecuciones recientes desde disco.

        Args:
            days: Numero de dias a cargar
            agent_name: Si se especifica, filtra por agente
        """
        executions: list[ExecutionMetrics] = []
        exec_dir = self.storage_path / "executions"
        if not exec_dir.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        for file in sorted(exec_dir.glob("*.jsonl"), reverse=True):
            try:
                # El nombre del archivo es la fecha: YYYY-MM-DD.jsonl
                file_date_str = file.stem
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    break
            except ValueError:
                continue

            try:
                for line in file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if agent_name is not None and entry.get("agent_name") != agent_name:
                        continue
                    executions.append(
                        ExecutionMetrics(
                            agent_name=entry.get("agent_name", ""),
                            task=entry.get("task", ""),
                            success=entry.get("success", False),
                            duration_ms=entry.get("duration_ms", 0.0),
                            quality_score=entry.get("quality_score", 0.0),
                            confidence=entry.get("confidence", 0.0),
                            retries=entry.get("retries", 0),
                            errors=entry.get("errors", []),
                            timestamp=entry.get("timestamp", ""),
                        )
                    )
            except Exception:
                continue

        return executions

    def auto_apply_safe_improvements(self) -> list[dict]:
        """Auto-aplica mejoras seguras (alta confianza, bajo riesgo).

        Criterios para auto-aplicacion:
        - Tipo: PROMPT_ENHANCEMENT o ERROR_HANDLING
        - Basado en >= 10 ejecuciones
        - Success rate del agente < 80%
        - La mejora propuesta no modifica codigo, solo prompts

        Returns:
            Lista de mejoras aplicadas automaticamente
        """
        applied: list[dict] = []
        proposals = self.list_proposals(status=ImprovementStatus.PROPOSED)

        for proposal in proposals:
            # Solo auto-aplicar PROMPT_ENHANCEMENT y ERROR_HANDLING
            if proposal.improvement_type not in (
                ImprovementType.PROMPT_ENHANCEMENT,
                ImprovementType.ERROR_HANDLING,
            ):
                continue

            # Verificar que hay suficientes datos
            metrics = self.get_agent_metrics(proposal.agent_name)
            if not metrics or metrics.get("total_executions", 0) < 10:
                continue

            # Solo auto-aplicar si el agente realmente necesita mejora
            if metrics.get("success_rate", 1.0) >= 0.80:
                continue

            # Aplicar
            self.apply_improvement(proposal.id, approved=True)
            applied.append(
                {
                    "proposal_id": proposal.id,
                    "agent": proposal.agent_name,
                    "type": proposal.improvement_type.value,
                    "rationale": proposal.rationale,
                }
            )

            logger.info(
                "Auto-aplicada mejora %s para agente %s: %s",
                proposal.id,
                proposal.agent_name,
                proposal.rationale,
            )

        return applied

    def get_ecosystem_health(self) -> dict:
        """Reporte de salud del ecosistema basado en metricas de todos los agentes.

        Returns:
            Dict con estado general, agentes saludables/degradados, y recomendaciones
        """
        all_metrics = self._get_all_agent_metrics()
        if not all_metrics:
            return {"status": "no_data", "agents": [], "recommendations": []}

        healthy: list[str] = []
        degraded: list[dict] = []
        recommendations: list[str] = []

        for agent_name, metrics in all_metrics.items():
            if metrics.get("total_executions", 0) < 3:
                continue
            sr = metrics.get("success_rate", 0)
            if sr >= 0.80:
                healthy.append(agent_name)
            else:
                degraded.append(
                    {
                        "agent": agent_name,
                        "success_rate": sr,
                        "executions": metrics.get("total_executions", 0),
                    }
                )

        if degraded:
            recommendations.append(
                f"{len(degraded)} agentes con success rate < 80%: "
                + ", ".join(d["agent"] for d in degraded[:5])
            )
            recommendations.append(
                "Ejecutar analyze_prompt_effectiveness() para cada agente degradado"
            )

        if len(healthy) > 0:
            avg_health = len(healthy) / (len(healthy) + len(degraded))
        else:
            avg_health = 0.0

        return {
            "status": "healthy" if avg_health > 0.80 else "needs_attention",
            "health_score": round(avg_health, 2),
            "healthy_agents": len(healthy),
            "degraded_agents": len(degraded),
            "degraded_details": degraded,
            "recommendations": recommendations,
        }

    def _get_all_agent_metrics(self) -> dict[str, dict]:
        """Obtiene metricas de todos los agentes que tienen ejecuciones."""
        all_metrics: dict[str, dict] = {}
        exec_dir = self.storage_path / "executions"
        if not exec_dir.exists():
            return {}

        agent_stats: dict[str, dict] = {}
        for file in exec_dir.glob("*.jsonl"):
            try:
                for line in file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    agent = entry.get("agent_name", "unknown")
                    if agent not in agent_stats:
                        agent_stats[agent] = {
                            "total_executions": 0,
                            "successes": 0,
                            "total_quality": 0.0,
                        }
                    stats = agent_stats[agent]
                    stats["total_executions"] += 1
                    if entry.get("success", False):
                        stats["successes"] += 1
                    stats["total_quality"] += entry.get("quality_score", 0.0)
            except Exception:
                continue

        for agent, stats in agent_stats.items():
            total = stats["total_executions"]
            all_metrics[agent] = {
                "total_executions": total,
                "success_rate": stats["successes"] / total if total > 0 else 0,
                "avg_quality": stats["total_quality"] / total if total > 0 else 0,
            }

        return all_metrics


# Singleton
_improver: SelfImprover | None = None


def get_self_improver() -> SelfImprover:
    """Obtener instancia de SelfImprover."""
    global _improver
    if _improver is None:
        _improver = SelfImprover()
    return _improver
