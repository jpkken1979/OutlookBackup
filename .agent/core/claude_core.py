"""
Claude Core - El cerebro integrador del ecosistema

Este es el módulo central que integra todos los agentes críticos
y proporciona una interfaz unificada para que Claude sea máximamente efectivo.

NO es otro agente más. Es la INTELIGENCIA CENTRAL que coordina todo.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Imports de módulos internos
try:
    from .intelligence.context_prediction import ContextPrediction, get_context_prediction
    from .intelligence.cost_awareness import CostAwareness, get_cost_awareness
    from .intelligence.dynamic_replanning import DynamicReplanning
    from .intelligence.output_verification import OutputVerification, get_output_verification
    from .intelligence.user_preference_model import UserPreferenceModel, get_user_preference_model
    from .session_bootstrap import SessionBootstrap
except ImportError:
    # Fallback para ejecución directa
    pass


class TaskPhase(Enum):
    """Fase de una tarea."""

    RECEIVED = "received"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    LEARNING = "learning"
    COMPLETE = "complete"


class ConfidenceLevel(Enum):
    """Nivel de confianza en una acción."""

    HIGH = "high"  # > 85% - Proceder automáticamente
    MEDIUM = "medium"  # 60-85% - Proceder con verificación
    LOW = "low"  # 40-60% - Consultar al usuario
    UNCERTAIN = "uncertain"  # < 40% - Definitivamente consultar


@dataclass
class TaskContext:
    """Contexto de una tarea en ejecución."""

    id: str
    description: str
    phase: TaskPhase
    started_at: datetime
    confidence: ConfidenceLevel
    files_involved: list[str] = field(default_factory=list)
    decisions_made: list[dict] = field(default_factory=list)
    verifications: list[dict] = field(default_factory=list)
    user_interactions: int = 0


@dataclass
class ClaudeState:
    """Estado actual de Claude."""

    session_id: str
    context_usage_percent: float
    tasks_completed: int
    errors_encountered: int
    user_satisfaction_score: float
    learning_events: int
    active_task: TaskContext | None = None


class ClaudeCore:
    """
    El cerebro central de Claude en el ecosistema Antigravity.

    Responsabilidades:
    1. Coordinar agentes críticos automáticamente
    2. Mantener estado de sesión
    3. Aprender de cada interacción
    4. Verificar outputs antes de entregar
    5. Gestionar contexto proactivamente

    Este NO es un agente que se invoca. Es el SISTEMA OPERATIVO de Claude.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Estado
        self.state = ClaudeState(
            session_id=self.session_id,
            context_usage_percent=0.0,
            tasks_completed=0,
            errors_encountered=0,
            user_satisfaction_score=1.0,
            learning_events=0,
        )

        # Componentes core (lazy loading)
        self._bootstrap: SessionBootstrap | None = None
        self._context_predictor: ContextPrediction | None = None
        self._preference_model: UserPreferenceModel | None = None
        self._verifier: OutputVerification | None = None
        self._cost_tracker: CostAwareness | None = None
        self._replanner: DynamicReplanning | None = None

        # Hooks
        self._pre_action_hooks: list[Callable] = []
        self._post_action_hooks: list[Callable] = []
        self._error_hooks: list[Callable] = []

        # Historial de la sesión
        self.session_history: list[dict] = []

    # ==================== PROPIEDADES LAZY ====================

    @property
    def bootstrap(self) -> SessionBootstrap:
        if self._bootstrap is None:
            self._bootstrap = SessionBootstrap(str(self.project_root))
        return self._bootstrap

    @property
    def context_predictor(self):
        if self._context_predictor is None:
            try:
                self._context_predictor = get_context_prediction()
            except Exception as _e:
                log.debug("Modulo opcional no disponible: %s", _e)
        return self._context_predictor

    @property
    def preference_model(self):
        if self._preference_model is None:
            try:
                self._preference_model = get_user_preference_model()
            except Exception as _e:
                log.debug("Modulo opcional no disponible: %s", _e)
        return self._preference_model

    @property
    def verifier(self):
        if self._verifier is None:
            try:
                self._verifier = get_output_verification()
            except Exception as _e:
                log.debug("Modulo opcional no disponible: %s", _e)
        return self._verifier

    @property
    def cost_tracker(self):
        if self._cost_tracker is None:
            try:
                self._cost_tracker = get_cost_awareness()
            except Exception as _e:
                log.debug("Modulo opcional no disponible: %s", _e)
        return self._cost_tracker

    # ==================== CICLO DE VIDA DE SESIÓN ====================

    def start_session(self) -> dict:
        """
        Inicia una nueva sesión.
        LLAMAR ESTO AL INICIO DE CADA CONVERSACIÓN.

        Returns:
            Contexto de la sesión cargado
        """
        result = self.bootstrap.bootstrap()

        self._log_event(
            "session_started",
            {
                "project": result.project.name,
                "language": result.project.language,
                "framework": result.project.framework,
                "memory_loaded": len(result.memory.decisions) > 0,
                "preferences_loaded": True,
            },
        )

        return {
            "session_id": self.session_id,
            "project": {
                "name": result.project.name,
                "stack": f"{result.project.language}"
                + (f" ({result.project.framework})" if result.project.framework else ""),
                "branch": result.project.git_branch,
                "status": result.project.git_status,
            },
            "preferences": {
                "language": result.preferences.language,
                "auto_verify": result.preferences.auto_verify,
                "commit_style": result.preferences.commit_style,
            },
            "memory": {
                "decisions_loaded": len(result.memory.decisions),
                "patterns_learned": len(result.memory.learned_patterns),
                "notes": result.memory.important_notes[-3:],  # Últimas 3 notas
            },
            "ready": True,
        }

    def end_session(self, summary: str | None = None):
        """
        Finaliza la sesión actual.
        LLAMAR ESTO AL FINAL DE CADA CONVERSACIÓN.
        """
        self._log_event(
            "session_ended",
            {
                "tasks_completed": self.state.tasks_completed,
                "errors": self.state.errors_encountered,
                "satisfaction": self.state.user_satisfaction_score,
                "learning_events": self.state.learning_events,
                "summary": summary,
            },
        )

        # Guardar historial de sesión
        self._save_session_history()

    # ==================== GESTIÓN DE TAREAS ====================

    def start_task(self, description: str, confidence: float = 0.8) -> TaskContext:
        """
        Inicia una nueva tarea.

        Args:
            description: Descripción de la tarea
            confidence: Confianza inicial (0-1)

        Returns:
            Contexto de la tarea
        """
        task = TaskContext(
            id=f"task_{datetime.now().strftime('%H%M%S')}",
            description=description,
            phase=TaskPhase.RECEIVED,
            started_at=datetime.now(),
            confidence=self._confidence_level(confidence),
        )

        self.state.active_task = task

        self._log_event(
            "task_started",
            {"task_id": task.id, "description": description, "confidence": confidence},
        )

        # Ejecutar pre-hooks
        for hook in self._pre_action_hooks:
            try:
                hook(task)
            except Exception as _e:
                log.debug("Pre-action hook failed: %s", _e)

        return task

    def complete_task(self, success: bool = True, learned: str | None = None):
        """
        Completa la tarea actual.

        Args:
            success: Si la tarea fue exitosa
            learned: Algo que aprendí de esta tarea
        """
        task = self.state.active_task
        if not task:
            return

        task.phase = TaskPhase.COMPLETE
        self.state.tasks_completed += 1

        if not success:
            self.state.errors_encountered += 1

        if learned:
            self.state.learning_events += 1
            self.bootstrap.save_to_memory(
                learned_pattern={"task": task.description, "learned": learned}
            )

        self._log_event(
            "task_completed",
            {
                "task_id": task.id,
                "success": success,
                "learned": learned,
                "decisions_made": len(task.decisions_made),
            },
        )

        # Ejecutar post-hooks
        for hook in self._post_action_hooks:
            try:
                hook(task, success)
            except Exception as _e:
                log.debug("Post-action hook failed: %s", _e)

        self.state.active_task = None

    def record_decision(self, decision: str, reason: str, confidence: float = 0.8):
        """
        Registra una decisión tomada.

        Args:
            decision: Qué se decidió
            reason: Por qué
            confidence: Confianza en la decisión
        """
        task = self.state.active_task

        record = {
            "decision": decision,
            "reason": reason,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }

        if task:
            task.decisions_made.append(record)

        # Guardar en memoria persistente si es importante
        if confidence >= 0.8:
            self.bootstrap.save_to_memory(decision=record)

    # ==================== VERIFICACIÓN AUTOMÁTICA ====================

    def verify_code(self, code: str, language: str = "python") -> dict:
        """
        Verifica código antes de entregarlo.

        Args:
            code: Código a verificar
            language: Lenguaje del código

        Returns:
            Resultado de verificación
        """
        if not self.verifier:
            return {"verified": True, "issues": [], "message": "Verifier not available"}

        result = self.verifier.verify_code(code, language)

        verification = {
            "verified": result.passed,
            "score": result.score,
            "issues_count": len(result.issues),
            "critical_issues": result.critical_count,
            "auto_fixed": result.auto_fixed,
        }

        if self.state.active_task:
            self.state.active_task.verifications.append(verification)

        self._log_event("code_verified", verification)

        return {
            "verified": result.passed,
            "score": result.score,
            "issues": [
                {
                    "type": i.verification_type.value,
                    "severity": i.severity.value,
                    "message": i.message,
                    "line": i.line,
                    "suggestion": i.suggestion,
                }
                for i in result.issues[:10]  # Limitar a 10
            ],
            "message": "Code verified" if result.passed else f"Found {len(result.issues)} issues",
        }

    def should_verify(self) -> bool:
        """Determina si debería verificar el output actual."""
        prefs = self.bootstrap._load_preferences()
        return prefs.auto_verify

    # ==================== GESTIÓN DE CONTEXTO ====================

    def check_context(self, current_tokens: int) -> dict:
        """
        Verifica estado del contexto.

        Args:
            current_tokens: Tokens actuales usados

        Returns:
            Estado y recomendaciones
        """
        if not self.context_predictor:
            return {"healthy": True, "message": "Context predictor not available"}

        self.context_predictor.record_usage(current_tokens)
        prediction = self.context_predictor.predict_overflow()

        self.state.context_usage_percent = (current_tokens / 200000) * 100

        return {
            "current_tokens": current_tokens,
            "max_tokens": 200000,
            "usage_percent": self.state.context_usage_percent,
            "risk_level": prediction.risk_level.value,
            "turns_until_warning": prediction.turns_until_warning,
            "recommendations": prediction.recommendations[:3],
            "should_compress": prediction.risk_level.value in ["warning", "critical", "overflow"],
        }

    # ==================== PREFERENCIAS DEL USUARIO ====================

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Obtiene preferencia del usuario."""
        if self.preference_model:
            value, confidence = self.preference_model.get(key, default)
            return value
        return default

    def learn_preference(self, key: str, value: Any, evidence: str):
        """Aprende una preferencia del usuario."""
        if self.preference_model:
            from .intelligence.user_preference_model import PreferenceSource

            self.preference_model.set(key, value, PreferenceSource.INFERRED, evidence)

    def observe_user_action(self, action_type: str, data: dict):
        """Observa una acción del usuario para aprender."""
        if self.preference_model:
            self.preference_model.observe(action_type, data)

    # ==================== FEEDBACK DEL USUARIO ====================

    def record_user_feedback(self, feedback_type: str, content: str):
        """
        Registra feedback del usuario.

        Args:
            feedback_type: "positive", "negative", "correction"
            content: Contenido del feedback
        """
        if feedback_type == "positive":
            self.state.user_satisfaction_score = min(1.0, self.state.user_satisfaction_score + 0.1)
        elif feedback_type == "negative":
            self.state.user_satisfaction_score = max(0.0, self.state.user_satisfaction_score - 0.15)
        elif feedback_type == "correction":
            self.state.user_satisfaction_score = max(0.0, self.state.user_satisfaction_score - 0.05)
            self.bootstrap.save_to_memory(
                user_correction={
                    "correction": content,
                    "task": self.state.active_task.description
                    if self.state.active_task
                    else "unknown",
                }
            )

        self._log_event(
            "user_feedback",
            {
                "type": feedback_type,
                "content": content[:100],
                "new_satisfaction": self.state.user_satisfaction_score,
            },
        )

        # Compatibilidad hacia atrás: algunos consumidores esperan feedback_type
        # en el nivel raíz del evento (además de data.type)
        if self.session_history:
            self.session_history[-1]["feedback_type"] = feedback_type

    # ==================== COSTOS ====================

    def estimate_cost(self, operation: str, tokens: int = 0) -> dict:
        """Estima costo de una operación."""
        if not self.cost_tracker:
            return {"estimated": 0.0, "approved": True}

        profile = self.cost_tracker.estimate_operation_cost(operation=operation, tokens=tokens)

        budget_check = self.cost_tracker.check_budget(profile.estimated_cost)

        return {
            "estimated_cost": profile.estimated_cost,
            "tier": profile.tier.value,
            "approved": budget_check["approved"],
            "budget_warning": budget_check["warning"],
            "alternatives": profile.alternatives,
        }

    # ==================== HELPERS INTERNOS ====================

    def _confidence_level(self, value: float) -> ConfidenceLevel:
        """Convierte valor numérico a nivel de confianza."""
        if value >= 0.85:
            return ConfidenceLevel.HIGH
        if value >= 0.60:
            return ConfidenceLevel.MEDIUM
        if value >= 0.40:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.UNCERTAIN

    def _log_event(self, event_type: str, data: dict):
        """Registra evento en historial de sesión."""
        self.session_history.append(
            {"event": event_type, "timestamp": datetime.now().isoformat(), "data": data}
        )

    def _save_session_history(self):
        """Guarda historial de sesión a disco."""
        history_dir = self.project_root / ".agent" / "memory" / "sessions"
        history_dir.mkdir(parents=True, exist_ok=True)

        history_file = history_dir / f"{self.session_id}.json"
        history_file.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "started_at": self.session_history[0]["timestamp"]
                    if self.session_history
                    else None,
                    "ended_at": datetime.now().isoformat(),
                    "stats": {
                        "tasks_completed": self.state.tasks_completed,
                        "errors": self.state.errors_encountered,
                        "satisfaction": self.state.user_satisfaction_score,
                        "learning_events": self.state.learning_events,
                    },
                    "events": self.session_history,
                },
                indent=2,
            )
        )

    # ==================== ESTADO ====================

    def get_status(self) -> dict:
        """Obtiene estado actual de Claude."""
        return {
            "session_id": self.session_id,
            "context_usage": f"{self.state.context_usage_percent:.1f}%",
            "tasks_completed": self.state.tasks_completed,
            "errors": self.state.errors_encountered,
            "satisfaction": f"{self.state.user_satisfaction_score * 100:.0f}%",
            "learning_events": self.state.learning_events,
            "active_task": {
                "id": self.state.active_task.id,
                "description": self.state.active_task.description,
                "phase": self.state.active_task.phase.value,
            }
            if self.state.active_task
            else None,
        }


# ==================== SINGLETON Y ACCESO RÁPIDO ====================

_claude_core: ClaudeCore | None = None


def get_claude_core(project_root: str = ".") -> ClaudeCore:
    """Obtiene instancia singleton de ClaudeCore."""
    global _claude_core
    if _claude_core is None:
        _claude_core = ClaudeCore(project_root)
    return _claude_core


def init_session() -> dict:
    """Inicializa sesión de Claude. LLAMAR AL INICIO."""
    return get_claude_core().start_session()


def end_session(summary: str | None = None):
    """Finaliza sesión de Claude. LLAMAR AL FINAL."""
    get_claude_core().end_session(summary)


def claude_status() -> dict:
    """Estado actual de Claude."""
    return get_claude_core().get_status()


if __name__ == "__main__":
    # Test
    core = ClaudeCore()
    session = core.start_session()
    print(json.dumps(session, indent=2))

    task = core.start_task("Test task")
    core.record_decision("Use Python", "It's the project's main language", 0.9)
    core.complete_task(success=True, learned="Tests are important")

    print(json.dumps(core.get_status(), indent=2))
    core.end_session("Test completed")
