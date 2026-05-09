"""Mixin de planificación, anomalías y observabilidad para AgentDaemon.

Extraído de agent_daemon.py para reducir el tamaño del archivo principal.
Contiene adaptadores para: MetaPlanner, AnomalyDetector, Telemetry, SelfImprover.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonPlanningMixin:
    """Adaptadores de planificación, anomalías y auto-mejora."""

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _meta_planner: Any | None
    _anomaly_detector: Any | None
    _self_improver: Any | None
    _enable_memory: bool
    _enable_telemetry: bool
    _daemon_id: str
    _get_agent_memory: Any

    # --------------------------------------------------------
    # MetaPlanner (Sprint 2)
    # --------------------------------------------------------
    async def plan_and_execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Descompone una tarea compleja y la ejecuta via MetaPlanner."""
        if self._meta_planner is None:
            raise RuntimeError("MetaPlanner no inicializado")

        self._metrics["plans_executed"] += 1
        result = await self._meta_planner.execute(task, context)

        if self._enable_memory:
            mem = self._get_agent_memory("meta-planner")
            if mem:
                summary = result.get("summary", "")
                mem.store_output(
                    task=task,
                    result=summary[:2000],
                    context={"plan_id": result.get("plan_id", "")},
                    task_id=result.get("plan_id"),
                )

        return result

    def analyze_task(self, task: str) -> dict[str, Any]:
        """Analiza una tarea sin ejecutarla (solo planificación)."""
        if self._meta_planner is None:
            raise RuntimeError("MetaPlanner no inicializado")
        return self._meta_planner.analyze(task)

    def create_plan(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Crea un plan de ejecución sin ejecutarlo."""
        if self._meta_planner is None:
            raise RuntimeError("MetaPlanner no inicializado")
        plan = self._meta_planner.plan(task, context)
        return plan.to_dict()

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        """Retorna un plan por su ID."""
        if self._meta_planner is None:
            return None
        return self._meta_planner.get_plan(plan_id)

    def list_plans(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lista planes recientes."""
        if self._meta_planner is None:
            return []
        return self._meta_planner.list_plans(limit)

    def get_planner_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del MetaPlanner."""
        if self._meta_planner is None:
            return {"status": "disabled"}
        return self._meta_planner.get_stats()

    # --------------------------------------------------------
    # AnomalyDetector (Sprint 2)
    # --------------------------------------------------------
    def _record_anomaly(
        self,
        agent_name: str,
        duration: float,
        success: bool,
        task_id: str | None = None,
    ) -> None:
        """Registra una ejecución en el AnomalyDetector."""
        if self._anomaly_detector is None:
            return
        try:
            alerts = self._anomaly_detector.record_execution(
                agent=agent_name,
                duration_seconds=duration,
                success=success,
                task_id=task_id,
            )
            self._metrics["anomalies_detected"] += len(alerts)
        except Exception as e:
            logger.debug("Error registrando anomalía: %s", e)

    def get_anomaly_alerts(
        self,
        agent: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retorna alertas de anomalía."""
        if self._anomaly_detector is None:
            return []
        return self._anomaly_detector.get_alerts(agent, severity, limit)

    def acknowledge_anomaly(self, alert_id: str) -> bool:
        """Marca una alerta como reconocida."""
        if self._anomaly_detector is None:
            return False
        return self._anomaly_detector.acknowledge_alert(alert_id)

    def get_agent_anomaly_profile(self, agent: str) -> dict[str, Any] | None:
        """Retorna el perfil de anomalía de un agente."""
        if self._anomaly_detector is None:
            return None
        return self._anomaly_detector.get_agent_profile(agent)

    def get_anomaly_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del AnomalyDetector."""
        if self._anomaly_detector is None:
            return {"status": "disabled"}
        return self._anomaly_detector.get_stats()

    # --------------------------------------------------------
    # Telemetry (Sprint 3)
    # --------------------------------------------------------
    def _get_trace_context(
        self,
        agent_name: str,
        task: str,
        task_id: str,
    ) -> Any:
        """Retorna un context manager de tracing para la ejecución."""
        if not self._enable_telemetry:
            from contextlib import nullcontext

            return nullcontext()
        try:
            from .telemetry import trace_agent_execution

            return trace_agent_execution(
                agent_name=agent_name,
                task=task,
                attributes={"task.id": task_id, "daemon.id": self._daemon_id},
            )
        except Exception as tel_err:
            logger.debug("Telemetry no disponible para %s: %s", agent_name, tel_err)
            from contextlib import nullcontext

            return nullcontext()

    def _record_telemetry(
        self,
        agent_name: str,
        duration: float,
        success: bool,
    ) -> None:
        """Registra métricas de telemetry para una ejecución."""
        if not self._enable_telemetry:
            return
        try:
            from .telemetry import record_agent_execution

            record_agent_execution(
                agent_name=agent_name,
                duration_seconds=duration,
                success=success,
            )
        except Exception as e:
            logger.debug("Error registrando telemetry: %s", e)

    # --------------------------------------------------------
    # SelfImprover (Sprint 3)
    # --------------------------------------------------------
    def _record_self_improvement(
        self,
        agent_name: str,
        task: str,
        success: bool,
        duration_ms: float,
        errors: list[str],
    ) -> None:
        """Registra ejecución en el SelfImprover."""
        if self._self_improver is None:
            return
        try:
            self._self_improver.record_execution(
                agent_name=agent_name,
                task=task[:200],
                success=success,
                duration_ms=duration_ms * 1000,
                quality_score=1.0 if success else 0.0,
                confidence=0.8 if success else 0.3,
                retries=0,
                errors=errors,
            )
        except Exception as e:
            logger.debug("Error registrando en SelfImprover: %s", e)

    def get_improvement_proposals(self) -> list[dict[str, Any]]:
        """Genera y retorna propuestas de mejora."""
        if self._self_improver is None:
            return []
        try:
            proposals = self._self_improver.propose_improvements()
            self._metrics["improvements_proposed"] += len(proposals)
            return [p.to_dict() for p in proposals]
        except Exception as e:
            logger.debug("Error generando propuestas: %s", e)
            return []

    def apply_improvement(self, proposal_id: str, approved: bool = False) -> bool:
        """Aplica o rechaza una propuesta de mejora."""
        if self._self_improver is None:
            return False
        return self._self_improver.apply_improvement(proposal_id, approved)

    def get_improvement_report(self) -> dict[str, Any]:
        """Retorna reporte de mejoras."""
        if self._self_improver is None:
            return {"status": "disabled"}
        return self._self_improver.get_improvement_report()

    def get_ecosystem_health(self) -> dict[str, Any]:
        """Retorna salud del ecosistema basada en métricas de SelfImprover."""
        if self._self_improver is None:
            return {"status": "disabled"}
        return self._self_improver.get_ecosystem_health()

    def analyze_agent_prompt(self, agent_name: str) -> dict[str, Any]:
        """Analiza la efectividad del prompt de un agente."""
        if self._self_improver is None:
            return {"status": "disabled"}
        return self._self_improver.analyze_prompt_effectiveness(agent_name)

    def auto_apply_improvements(self) -> list[dict[str, Any]]:
        """Auto-aplica mejoras seguras (bajo riesgo)."""
        if self._self_improver is None:
            return []
        return self._self_improver.auto_apply_safe_improvements()
