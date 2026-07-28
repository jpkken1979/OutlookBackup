"""Mixin de autonomía y comportamiento emergente para AgentDaemon.

Adaptadores para: Metacognition (Sprint 9C), GoalAutonomy (Sprint 9C),
EmergentBehavior (Sprint 9C). Gestiona la auto-reflexión, metas
autónomas y detección de patrones emergentes.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonAutonomyMixin:
    """Adaptadores de metacognición, metas autónomas y comportamiento emergente.

    Agrupa los subsistemas de autonomía del ecosistema: reflexión
    sobre decisiones propias, gestión de metas sin intervención
    humana y detección de patrones de comportamiento emergente
    en la población de agentes.
    """

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _metacognition: Any | None
    _goal_autonomy: Any | None
    _emergent_behavior: Any | None

    # --------------------------------------------------------
    # Metacognition (Sprint 9C)
    # --------------------------------------------------------
    def meta_record(
        self,
        decision: str,
        strategy: str = "default",
        outcome: str = "unknown",
        quality: float = 0.5,
    ) -> dict[str, Any]:
        """Registra una decisión metacognitiva."""
        if self._metacognition is None:
            return {"status": "disabled"}
        self._metrics["metacognition_decisions"] += 1
        return self._metacognition.record_decision(
            decision, strategy, outcome=outcome, quality=quality
        )

    def meta_diagnose(self) -> dict[str, Any]:
        """Ejecuta diagnóstico metacognitivo del sistema."""
        if self._metacognition is None:
            return {"status": "disabled"}
        return self._metacognition.diagnose()

    def meta_recommendations(self) -> list[dict[str, Any]]:
        """Obtiene recomendaciones metacognitivas."""
        if self._metacognition is None:
            return []
        return self._metacognition.get_recommendations()

    def get_metacognition_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de metacognición."""
        if self._metacognition is None:
            return {"status": "disabled"}
        return self._metacognition.get_stats()

    # --------------------------------------------------------
    # Goal Autonomy (Sprint 9C)
    # --------------------------------------------------------
    def goal_create(
        self,
        title: str,
        category: str = "general",
        priority: float = 0.5,
    ) -> dict[str, Any]:
        """Crea una meta autónoma."""
        if self._goal_autonomy is None:
            return {"status": "disabled"}
        self._metrics["goals_created"] += 1
        return self._goal_autonomy.create_goal(title, category=category, priority=priority)

    def goal_get_active(self, category: str | None = None) -> list[dict[str, Any]]:
        """Obtiene metas activas, opcionalmente filtradas por categoría."""
        if self._goal_autonomy is None:
            return []
        return self._goal_autonomy.get_active_goals(category)

    def goal_update_progress(self, goal_id: str, progress: float) -> dict[str, Any] | None:
        """Actualiza el progreso de una meta."""
        if self._goal_autonomy is None:
            return None
        return self._goal_autonomy.update_progress(goal_id, progress=progress)

    def goal_complete(self, goal_id: str) -> dict[str, Any] | None:
        """Marca una meta como completada."""
        if self._goal_autonomy is None:
            return None
        return self._goal_autonomy.complete_goal(goal_id)

    def get_goal_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de metas autónomas."""
        if self._goal_autonomy is None:
            return {"status": "disabled"}
        return self._goal_autonomy.get_stats()

    # --------------------------------------------------------
    # Emergent Behavior (Sprint 9C)
    # --------------------------------------------------------
    def emergent_observe(
        self,
        agents: list[str],
        pattern: str = "",
        effectiveness: float = 0.5,
    ) -> dict[str, Any]:
        """Registra una observación de comportamiento emergente."""
        if self._emergent_behavior is None:
            return {"status": "disabled"}
        self._metrics["emergent_observations"] += 1
        return self._emergent_behavior.observe(agents, pattern, effectiveness)

    def emergent_detect(self) -> list[dict[str, Any]]:
        """Detecta patrones de comportamiento emergente."""
        if self._emergent_behavior is None:
            return []
        return self._emergent_behavior.detect()

    def emergent_get_patterns(self) -> list[dict[str, Any]]:
        """Obtiene patrones emergentes activos."""
        if self._emergent_behavior is None:
            return []
        return self._emergent_behavior.get_active_patterns()

    def get_emergent_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de comportamiento emergente."""
        if self._emergent_behavior is None:
            return {"status": "disabled"}
        return self._emergent_behavior.get_stats()
