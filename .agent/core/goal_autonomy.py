"""
Goal Autonomy — auto-generación de objetivos.

El sistema genera objetivos propios basados en patrones detectados,
brechas de capacidad y oportunidades de mejora:
  - Goal generation: crea objetivos desde diagnóstico
  - Goal prioritization: prioriza por impacto y factibilidad
  - Goal tracking: sigue progreso de objetivos
  - Goal decomposition: divide objetivos en sub-tareas
  - Goal completion: marca objetivos como logrados

Usage:
    autonomy = GoalAutonomy(bus=bus)

    # Generar objetivos desde diagnóstico
    goals = autonomy.generate_from_diagnosis(diagnosis)

    # Crear objetivo manual
    autonomy.create_goal(
        title="Mejorar routing success rate",
        category="performance",
        priority=0.8,
    )

    # Progreso
    autonomy.update_progress("goal-id", progress=0.5)

    # Completar
    autonomy.complete_goal("goal-id")
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.goal_autonomy")

# ============================================================
# Constantes
# ============================================================
MAX_ACTIVE_GOALS = 20  # Máximo de objetivos activos
MAX_GOAL_HISTORY = 200  # Historial de objetivos
PRIORITY_LEVELS = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}


# ============================================================
# Modelos
# ============================================================
@dataclass
class Goal:
    """Un objetivo autónomo del sistema."""

    goal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    category: str = "general"  # performance, reliability, knowledge, growth
    priority: float = 0.5
    status: str = "active"  # active, paused, completed, abandoned
    progress: float = 0.0  # [0, 1]
    subtasks: list[str] = field(default_factory=list)
    completed_subtasks: list[str] = field(default_factory=list)
    source: str = "auto"  # auto (generado) o manual
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": round(self.priority, 2),
            "status": self.status,
            "progress": round(self.progress, 2),
            "subtasks": self.subtasks,
            "completed_subtasks": self.completed_subtasks,
            "source": self.source,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ============================================================
# Goal Autonomy
# ============================================================
class GoalAutonomy:
    """
    Motor de objetivos autónomos. Genera, prioriza y trackea
    objetivos que el sistema se propone a sí mismo.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Objetivos activos
        self._goals: dict[str, Goal] = {}

        # Historial
        self._history: list[Goal] = []

        # Métricas
        self._metrics = {
            "goals_created": 0,
            "goals_completed": 0,
            "goals_abandoned": 0,
            "goals_auto_generated": 0,
        }

    # --------------------------------------------------------
    # Create Goal
    # --------------------------------------------------------
    def create_goal(
        self,
        title: str,
        description: str = "",
        category: str = "general",
        priority: float = 0.5,
        subtasks: list[str] | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        """Crea un nuevo objetivo."""
        if len(self._goals) >= MAX_ACTIVE_GOALS:
            # Auto-abandonar el de menor prioridad
            lowest = min(self._goals.values(), key=lambda g: g.priority)
            self.abandon_goal(lowest.goal_id, reason="auto-displaced")

        goal = Goal(
            title=title,
            description=description,
            category=category,
            priority=max(0.0, min(1.0, priority)),
            subtasks=subtasks or [],
            source=source,
        )
        self._goals[goal.goal_id] = goal
        self._metrics["goals_created"] += 1

        logger.info("Goal created: %s (priority=%.2f)", title, priority)
        return goal.to_dict()

    # --------------------------------------------------------
    # Generate from Diagnosis
    # --------------------------------------------------------
    def generate_from_diagnosis(
        self,
        diagnosis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Genera objetivos desde un diagnóstico metacognitivo."""
        generated = []

        health = diagnosis.get("health", "healthy")
        failure_rate = diagnosis.get("failure_rate", 0)
        bottlenecks = diagnosis.get("bottlenecks", [])
        avg_quality = diagnosis.get("avg_quality", 0.5)

        if health == "critical":
            goal = self.create_goal(
                title="Restaurar salud del sistema",
                description=f"Failure rate: {failure_rate}",
                category="reliability",
                priority=1.0,
                subtasks=["Identificar causa raíz", "Aplicar fix", "Verificar recovery"],
                source="auto",
            )
            generated.append(goal)
            self._metrics["goals_auto_generated"] += 1

        if health == "degraded":
            goal = self.create_goal(
                title="Mejorar tasa de éxito",
                description=f"Failure rate actual: {failure_rate}",
                category="performance",
                priority=0.8,
                subtasks=["Analizar failures", "Ajustar estrategias"],
                source="auto",
            )
            generated.append(goal)
            self._metrics["goals_auto_generated"] += 1

        for bottleneck in bottlenecks:
            goal = self.create_goal(
                title=f"Resolver bottleneck en {bottleneck.get('strategy', 'unknown')}",
                description=bottleneck.get("detail", ""),
                category="performance",
                priority=0.7,
                source="auto",
            )
            generated.append(goal)
            self._metrics["goals_auto_generated"] += 1

        if avg_quality < 0.6:
            goal = self.create_goal(
                title="Elevar calidad promedio de outputs",
                description=f"Calidad actual: {avg_quality}",
                category="growth",
                priority=0.6,
                subtasks=["Identificar áreas débiles", "Aplicar knowledge distillation"],
                source="auto",
            )
            generated.append(goal)
            self._metrics["goals_auto_generated"] += 1

        return generated

    # --------------------------------------------------------
    # Progress & Completion
    # --------------------------------------------------------
    def update_progress(
        self,
        goal_id: str,
        progress: float | None = None,
        completed_subtask: str | None = None,
    ) -> dict[str, Any] | None:
        """Actualiza progreso de un objetivo."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None

        if progress is not None:
            goal.progress = max(0.0, min(1.0, progress))

        if completed_subtask and completed_subtask in goal.subtasks:
            if completed_subtask not in goal.completed_subtasks:
                goal.completed_subtasks.append(completed_subtask)
                # Auto-calcular progreso basado en subtasks
                if goal.subtasks:
                    goal.progress = len(goal.completed_subtasks) / len(goal.subtasks)

        # Auto-complete si progress == 1.0
        if goal.progress >= 1.0:
            return self.complete_goal(goal_id)

        return goal.to_dict()

    def complete_goal(self, goal_id: str) -> dict[str, Any] | None:
        """Marca un objetivo como completado."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None

        goal.status = "completed"
        goal.progress = 1.0
        goal.completed_at = time.time()

        self._history.append(goal)
        del self._goals[goal_id]
        if len(self._history) > MAX_GOAL_HISTORY:
            self._history = self._history[-MAX_GOAL_HISTORY:]

        self._metrics["goals_completed"] += 1
        logger.info("Goal completed: %s", goal.title)
        return goal.to_dict()

    def abandon_goal(
        self,
        goal_id: str,
        reason: str = "",
    ) -> dict[str, Any] | None:
        """Abandona un objetivo."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None

        goal.status = "abandoned"
        goal.description += f" [abandoned: {reason}]" if reason else ""

        self._history.append(goal)
        del self._goals[goal_id]

        self._metrics["goals_abandoned"] += 1
        return goal.to_dict()

    def pause_goal(self, goal_id: str) -> dict[str, Any] | None:
        """Pausa un objetivo."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        goal.status = "paused"
        return goal.to_dict()

    def resume_goal(self, goal_id: str) -> dict[str, Any] | None:
        """Resume un objetivo pausado."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        goal.status = "active"
        return goal.to_dict()

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        """Obtiene un objetivo."""
        goal = self._goals.get(goal_id)
        return goal.to_dict() if goal else None

    def get_active_goals(
        self,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Objetivos activos, ordenados por prioridad."""
        goals = [g for g in self._goals.values() if g.status == "active"]
        if category:
            goals = [g for g in goals if g.category == category]
        return [
            g.to_dict()
            for g in sorted(
                goals,
                key=lambda g: g.priority,
                reverse=True,
            )
        ]

    def get_all_goals(self) -> list[dict[str, Any]]:
        """Todos los objetivos activos."""
        return [
            g.to_dict()
            for g in sorted(
                self._goals.values(),
                key=lambda g: g.priority,
                reverse=True,
            )
        ]

    def get_history(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de objetivos."""
        goals = self._history
        if status:
            goals = [g for g in goals if g.status == status]
        return [g.to_dict() for g in goals[-limit:]][::-1]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del motor de objetivos."""
        active = [g for g in self._goals.values() if g.status == "active"]
        return {
            "active_goals": len(active),
            "paused_goals": sum(1 for g in self._goals.values() if g.status == "paused"),
            "total_in_memory": len(self._goals),
            "history_size": len(self._history),
            "avg_progress": round(
                sum(g.progress for g in active) / len(active),
                3,
            )
            if active
            else 0.0,
            "categories": sorted({g.category for g in self._goals.values()}),
            "metrics": {**self._metrics},
        }


# ============================================================
# Singleton
# ============================================================
_instance: GoalAutonomy | None = None


def get_goal_autonomy(bus: Any = None) -> GoalAutonomy:
    """Obtiene o crea el motor de objetivos global."""
    global _instance
    if _instance is None:
        _instance = GoalAutonomy(bus=bus)
    return _instance
