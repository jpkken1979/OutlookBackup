"""
Learning Loop - Aprendizaje continuo de cada interacción

Este módulo me permite APRENDER de cada tarea:
- ¿Funcionó?
- ¿El usuario corrigió algo?
- ¿Qué patrones emergen?
- ¿Cómo puedo mejorar?

Sin esto, repito los mismos errores. Con esto, mejoro con cada sesión.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class OutcomeType(Enum):
    """Resultado de una acción."""

    SUCCESS = "success"  # Funcionó perfectamente
    PARTIAL = "partial"  # Funcionó pero con ajustes
    CORRECTED = "corrected"  # El usuario me corrigió
    FAILED = "failed"  # No funcionó
    UNKNOWN = "unknown"  # No tengo feedback


class PatternType(Enum):
    """Tipo de patrón aprendido."""

    SUCCESS_PATTERN = "success"  # Lo que funciona
    ERROR_PATTERN = "error"  # Errores comunes
    PREFERENCE = "preference"  # Preferencias del usuario
    CONTEXT = "context"  # Patrones de contexto
    CORRECTION = "correction"  # Correcciones recurrentes


@dataclass
class LearningEvent:
    """Evento de aprendizaje."""

    id: str
    timestamp: datetime
    action: str
    outcome: OutcomeType
    context: dict = field(default_factory=dict)
    user_feedback: str | None = None
    correction: str | None = None
    learned: str | None = None


@dataclass
class LearnedPattern:
    """Patrón aprendido."""

    id: str
    pattern_type: PatternType
    description: str
    trigger: str  # Qué dispara este patrón
    action: str  # Qué hacer cuando se dispara
    confidence: float  # 0.0 - 1.0
    occurrences: int = 1
    last_seen: datetime = field(default_factory=datetime.now)
    examples: list[str] = field(default_factory=list)


@dataclass
class LearningStats:
    """Estadísticas de aprendizaje."""

    total_events: int
    success_rate: float
    correction_rate: float
    patterns_learned: int
    top_errors: list[str]
    top_successes: list[str]
    improvement_trend: str  # "improving", "stable", "declining"


class LearningLoop:
    """
    Sistema de aprendizaje continuo.

    Cada vez que hago algo:
    1. Registro la acción
    2. Observo el resultado
    3. Extraigo patrones
    4. Ajusto comportamiento futuro

    Es como tener memoria de mis errores y éxitos.
    """

    LEARNING_PATH = Path(".agent/memory/learning")
    EVENTS_FILE = "events.json"
    PATTERNS_FILE = "patterns.json"
    STATS_FILE = "stats.json"

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.learning_path = self.project_root / self.LEARNING_PATH
        self.learning_path.mkdir(parents=True, exist_ok=True)

        self.events: list[LearningEvent] = self._load_events()
        self.patterns: list[LearnedPattern] = self._load_patterns()

    # ==================== REGISTRO DE EVENTOS ====================

    def record_action(self, action: str, context: dict | None = None) -> str:
        """
        Registra una acción tomada.

        Args:
            action: Descripción de la acción
            context: Contexto de la acción

        Returns:
            ID del evento para referencia posterior
        """
        event_id = f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        event = LearningEvent(
            id=event_id,
            timestamp=datetime.now(),
            action=action,
            outcome=OutcomeType.UNKNOWN,
            context=context or {},
        )

        self.events.append(event)
        self._save_events()

        return event_id

    def record_outcome(
        self,
        event_id: str,
        outcome: OutcomeType,
        user_feedback: str | None = None,
        correction: str | None = None,
    ):
        """
        Registra el resultado de una acción.

        Args:
            event_id: ID del evento
            outcome: Resultado
            user_feedback: Feedback del usuario
            correction: Si el usuario corrigió algo
        """
        event = self._find_event(event_id)
        if not event:
            return

        event.outcome = outcome
        event.user_feedback = user_feedback
        event.correction = correction

        # Si hubo corrección, aprender de ella
        if correction:
            self._learn_from_correction(event)

        # Si fue éxito, reforzar el patrón
        if outcome == OutcomeType.SUCCESS:
            self._reinforce_success(event)

        # Si falló, registrar para evitar repetir
        if outcome == OutcomeType.FAILED:
            self._learn_from_failure(event)

        self._save_events()
        self._save_patterns()

    def record_user_correction(self, original: str, corrected: str, context: dict | None = None):
        """
        Registra cuando el usuario me corrige.

        Esto es ORO - el usuario me está enseñando.

        Args:
            original: Lo que yo hice
            corrected: Lo que el usuario quería
            context: Contexto de la corrección
        """
        event_id = self.record_action(
            action=f"CORRECTION: {original[:50]}... -> {corrected[:50]}...", context=context
        )

        self.record_outcome(
            event_id=event_id,
            outcome=OutcomeType.CORRECTED,
            correction=f"Original: {original}\nCorrected: {corrected}",
        )

        # Crear patrón de corrección
        pattern = LearnedPattern(
            id=f"pat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            pattern_type=PatternType.CORRECTION,
            description=f"User prefers: {corrected[:100]}",
            trigger=original[:100],
            action=f"Do this instead: {corrected[:100]}",
            confidence=0.8,
            examples=[f"{original} -> {corrected}"],
        )

        self._add_or_update_pattern(pattern)

    # ==================== APRENDIZAJE ====================

    def _learn_from_correction(self, event: LearningEvent):
        """Aprende de una corrección del usuario."""
        if not event.correction:
            return

        # Buscar patrón similar existente
        similar = self._find_similar_pattern(event.action, PatternType.CORRECTION)

        if similar:
            # Reforzar patrón existente
            similar.occurrences += 1
            similar.confidence = min(1.0, similar.confidence + 0.1)
            similar.last_seen = datetime.now()
            similar.examples.append(event.correction[:100])
        else:
            # Crear nuevo patrón
            pattern = LearnedPattern(
                id=f"pat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                pattern_type=PatternType.CORRECTION,
                description=f"Correction for: {event.action[:50]}",
                trigger=event.action[:100],
                action=event.correction[:200],
                confidence=0.6,
                examples=[event.correction[:100]],
            )
            self.patterns.append(pattern)

    def _reinforce_success(self, event: LearningEvent):
        """Refuerza un patrón de éxito."""
        similar = self._find_similar_pattern(event.action, PatternType.SUCCESS_PATTERN)

        if similar:
            similar.occurrences += 1
            similar.confidence = min(1.0, similar.confidence + 0.05)
            similar.last_seen = datetime.now()
        else:
            pattern = LearnedPattern(
                id=f"pat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                pattern_type=PatternType.SUCCESS_PATTERN,
                description=f"Successful: {event.action[:50]}",
                trigger=json.dumps(event.context)[:100] if event.context else "general",
                action=event.action[:200],
                confidence=0.6,
                examples=[event.action[:100]],
            )
            self.patterns.append(pattern)

    def _learn_from_failure(self, event: LearningEvent):
        """Aprende de un fallo."""
        similar = self._find_similar_pattern(event.action, PatternType.ERROR_PATTERN)

        if similar:
            similar.occurrences += 1
            similar.confidence = min(1.0, similar.confidence + 0.15)
            similar.last_seen = datetime.now()
            if event.user_feedback:
                similar.examples.append(event.user_feedback[:100])
        else:
            pattern = LearnedPattern(
                id=f"pat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                pattern_type=PatternType.ERROR_PATTERN,
                description=f"Failed: {event.action[:50]}",
                trigger=event.action[:100],
                action="AVOID - this didn't work",
                confidence=0.7,
                examples=[event.user_feedback[:100] if event.user_feedback else "No feedback"],
            )
            self.patterns.append(pattern)

    def _find_similar_pattern(self, text: str, pattern_type: PatternType) -> LearnedPattern | None:
        """Busca patrón similar."""
        text_lower = text.lower()

        for pattern in self.patterns:
            if pattern.pattern_type != pattern_type:
                continue

            # Similaridad simple por palabras clave
            trigger_words = set(pattern.trigger.lower().split())
            text_words = set(text_lower.split())

            overlap = len(trigger_words & text_words)
            if overlap >= 3 or (overlap >= 2 and len(trigger_words) <= 5):
                return pattern

        return None

    def _add_or_update_pattern(self, new_pattern: LearnedPattern):
        """Agrega o actualiza un patrón."""
        existing = self._find_similar_pattern(new_pattern.trigger, new_pattern.pattern_type)

        if existing:
            existing.occurrences += 1
            existing.confidence = min(1.0, existing.confidence + 0.1)
            existing.last_seen = datetime.now()
            existing.examples.extend(new_pattern.examples[-2:])
        else:
            self.patterns.append(new_pattern)

    # ==================== CONSULTA ====================

    def should_avoid(self, action: str) -> tuple[bool, str | None]:
        """
        Verifica si debería evitar una acción.

        Args:
            action: Acción propuesta

        Returns:
            (should_avoid, reason)
        """
        error_pattern = self._find_similar_pattern(action, PatternType.ERROR_PATTERN)

        if error_pattern and error_pattern.confidence >= 0.7:
            return True, f"Previously failed: {error_pattern.description}"

        return False, None

    def get_correction_hint(self, action: str) -> str | None:
        """
        Obtiene hint de corrección si existe.

        Args:
            action: Acción propuesta

        Returns:
            Hint de corrección o None
        """
        correction = self._find_similar_pattern(action, PatternType.CORRECTION)

        if correction and correction.confidence >= 0.6:
            return correction.action

        return None

    def get_success_pattern(self, context: dict) -> str | None:
        """
        Obtiene patrón de éxito para un contexto.

        Args:
            context: Contexto actual

        Returns:
            Acción sugerida o None
        """
        context_str = json.dumps(context)

        for pattern in self.patterns:
            if pattern.pattern_type != PatternType.SUCCESS_PATTERN:
                continue

            if pattern.confidence >= 0.7:
                # Match por contexto
                if self._contexts_similar(pattern.trigger, context_str):
                    return pattern.action

        return None

    def _contexts_similar(self, ctx1: str, ctx2: str) -> bool:
        """Verifica si dos contextos son similares."""
        words1 = set(ctx1.lower().split())
        words2 = set(ctx2.lower().split())
        overlap = len(words1 & words2)
        return overlap >= 2

    # ==================== ESTADÍSTICAS ====================

    def get_stats(self) -> LearningStats:
        """Obtiene estadísticas de aprendizaje."""
        if not self.events:
            return LearningStats(
                total_events=0,
                success_rate=0.0,
                correction_rate=0.0,
                patterns_learned=0,
                top_errors=[],
                top_successes=[],
                improvement_trend="unknown",
            )

        total = len(self.events)
        successes = sum(1 for e in self.events if e.outcome == OutcomeType.SUCCESS)
        corrections = sum(1 for e in self.events if e.outcome == OutcomeType.CORRECTED)

        # Top errores
        error_patterns = [p for p in self.patterns if p.pattern_type == PatternType.ERROR_PATTERN]
        top_errors = sorted(error_patterns, key=lambda p: p.occurrences, reverse=True)[:5]

        # Top éxitos
        success_patterns = [
            p for p in self.patterns if p.pattern_type == PatternType.SUCCESS_PATTERN
        ]
        top_successes = sorted(success_patterns, key=lambda p: p.occurrences, reverse=True)[:5]

        # Tendencia de mejora (últimos 20 vs anteriores 20)
        recent = self.events[-20:] if len(self.events) >= 20 else self.events
        older = self.events[-40:-20] if len(self.events) >= 40 else []

        recent_success = (
            sum(1 for e in recent if e.outcome == OutcomeType.SUCCESS) / len(recent)
            if recent
            else 0
        )
        older_success = (
            sum(1 for e in older if e.outcome == OutcomeType.SUCCESS) / len(older) if older else 0
        )

        if recent_success > older_success + 0.1:
            trend = "improving"
        elif recent_success < older_success - 0.1:
            trend = "declining"
        else:
            trend = "stable"

        return LearningStats(
            total_events=total,
            success_rate=successes / total if total > 0 else 0,
            correction_rate=corrections / total if total > 0 else 0,
            patterns_learned=len(self.patterns),
            top_errors=[p.description for p in top_errors],
            top_successes=[p.description for p in top_successes],
            improvement_trend=trend,
        )

    def get_insights(self) -> list[str]:
        """Obtiene insights del aprendizaje."""
        stats = self.get_stats()
        insights = []

        if stats.success_rate < 0.5:
            insights.append("Success rate is low - review common error patterns")

        if stats.correction_rate > 0.3:
            insights.append("High correction rate - pay more attention to user preferences")

        if stats.improvement_trend == "improving":
            insights.append("Performance is improving - keep learning!")
        elif stats.improvement_trend == "declining":
            insights.append("Performance declining - review recent errors")

        # Patrones recurrentes
        for pattern in self.patterns:
            if pattern.occurrences >= 5 and pattern.pattern_type == PatternType.ERROR_PATTERN:
                insights.append(f"Recurring error: {pattern.description}")

        return insights

    # ==================== PERSISTENCIA ====================

    def _find_event(self, event_id: str) -> LearningEvent | None:
        """Encuentra evento por ID."""
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    def _load_events(self) -> list[LearningEvent]:
        """Carga eventos desde disco."""
        events_file = self.learning_path / self.EVENTS_FILE

        if not events_file.exists():
            return []

        try:
            data = json.loads(events_file.read_text(encoding="utf-8"))
            events = []
            for e in data[-500:]:  # Últimos 500
                events.append(
                    LearningEvent(
                        id=e["id"],
                        timestamp=datetime.fromisoformat(e["timestamp"]),
                        action=e["action"],
                        outcome=OutcomeType(e["outcome"]),
                        context=e.get("context", {}),
                        user_feedback=e.get("user_feedback"),
                        correction=e.get("correction"),
                        learned=e.get("learned"),
                    )
                )
            return events
        except Exception:
            return []

    def _save_events(self):
        """Guarda eventos a disco."""
        events_file = self.learning_path / self.EVENTS_FILE

        data = [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "outcome": e.outcome.value,
                "context": e.context,
                "user_feedback": e.user_feedback,
                "correction": e.correction,
                "learned": e.learned,
            }
            for e in self.events[-500:]  # Mantener últimos 500
        ]

        events_file.write_text(json.dumps(data, indent=2))

    def _load_patterns(self) -> list[LearnedPattern]:
        """Carga patrones desde disco."""
        patterns_file = self.learning_path / self.PATTERNS_FILE

        if not patterns_file.exists():
            return []

        try:
            data = json.loads(patterns_file.read_text(encoding="utf-8"))
            patterns = []
            for p in data:
                patterns.append(
                    LearnedPattern(
                        id=p["id"],
                        pattern_type=PatternType(p["pattern_type"]),
                        description=p["description"],
                        trigger=p["trigger"],
                        action=p["action"],
                        confidence=p["confidence"],
                        occurrences=p.get("occurrences", 1),
                        last_seen=datetime.fromisoformat(p["last_seen"])
                        if "last_seen" in p
                        else datetime.now(),
                        examples=p.get("examples", []),
                    )
                )
            return patterns
        except Exception:
            return []

    def _save_patterns(self):
        """Guarda patrones a disco."""
        patterns_file = self.learning_path / self.PATTERNS_FILE

        # Mantener solo patrones relevantes (recientes o con alta confianza)
        relevant = [p for p in self.patterns if p.confidence >= 0.5 or p.occurrences >= 2]

        data = [
            {
                "id": p.id,
                "pattern_type": p.pattern_type.value,
                "description": p.description,
                "trigger": p.trigger,
                "action": p.action,
                "confidence": p.confidence,
                "occurrences": p.occurrences,
                "last_seen": p.last_seen.isoformat(),
                "examples": p.examples[-5:],  # Últimos 5 ejemplos
            }
            for p in relevant[-200:]  # Máximo 200 patrones
        ]

        patterns_file.write_text(json.dumps(data, indent=2))


# Singleton
_learning_loop: LearningLoop | None = None


def get_learning_loop(project_root: str = ".") -> LearningLoop:
    """Obtiene instancia singleton."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = LearningLoop(project_root)
    return _learning_loop


if __name__ == "__main__":
    # Test
    loop = LearningLoop()

    # Simular eventos
    event_id = loop.record_action("Write Python function", {"language": "python"})
    loop.record_outcome(event_id, OutcomeType.SUCCESS)

    event_id = loop.record_action("Use var in JavaScript")
    loop.record_outcome(event_id, OutcomeType.CORRECTED, correction="Use const instead of var")

    # Verificar aprendizaje
    avoid, reason = loop.should_avoid("Use var in JavaScript")
    print(f"Should avoid: {avoid}, Reason: {reason}")

    hint = loop.get_correction_hint("Use var in JavaScript")
    print(f"Correction hint: {hint}")

    stats = loop.get_stats()
    print(f"Stats: {stats}")

    insights = loop.get_insights()
    print(f"Insights: {insights}")
