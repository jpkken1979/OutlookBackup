#!/usr/bin/env python3
"""
Feedback Refiner Agent - Incorpora feedback del usuario y refina soluciones

Cierra el loop entre entrega inicial y satisfaccion mediante refinamiento iterativo.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum


class FeedbackType(Enum):
    """Tipos de feedback del usuario."""

    CLARIFICATION = "clarification"  # Necesita mas detalles
    MODIFICATION = "modification"  # Cambio especifico
    REJECTION = "rejection"  # No es lo que queria
    APPROVAL = "approval"  # Satisfecho
    PARTIAL = "partial"  # Casi bien, pero...


class Priority(Enum):
    """Prioridad del cambio solicitado."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    NICE_TO_HAVE = "nice_to_have"


@dataclass
class ChangeRequest:
    """Solicitud de cambio extraida del feedback."""

    description: str
    priority: Priority
    affected_component: str | None = None
    current_behavior: str | None = None
    desired_behavior: str | None = None


@dataclass
class ParsedFeedback:
    """Feedback parseado y estructurado."""

    original_text: str
    feedback_type: FeedbackType
    sentiment: float  # -1 a 1
    change_requests: list[ChangeRequest] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class RefinementPlan:
    """Plan de refinamiento basado en feedback."""

    feedback: ParsedFeedback
    actions: list[dict]
    estimated_effort: str  # "small", "medium", "large"
    requires_confirmation: bool = False


@dataclass
class RefinementResult:
    """Resultado del proceso de refinamiento."""

    success: bool
    iteration: int
    original_feedback: str
    changes_made: list[str]
    pending_clarifications: list[str]
    confidence: float


class FeedbackRefiner:
    """Refina soluciones basado en feedback del usuario."""

    # Patrones para detectar tipo de feedback
    MODIFICATION_PATTERNS = [
        r"(pero|sin embargo|aunque).*(quiero|necesito|prefiero)",
        r"(cambiar?|modificar?|ajustar?).*(a|por|para)",
        r"(en vez de|en lugar de|mejor|preferir[ií]a)",
        r"(agregar?|añadir?|incluir?|faltar?)",
        r"(quitar?|remover?|eliminar?|sobrar?)",
    ]

    REJECTION_PATTERNS = [
        r"no (es|era) (lo que|esto)",
        r"esto no (sirve|funciona|es)",
        r"(completamente|totalmente) (mal|incorrecto|equivocado)",
        r"empezar? (de nuevo|desde cero)",
    ]

    APPROVAL_PATTERNS = [
        r"(perfecto|excelente|genial|bien|correcto)",
        r"(eso es|as[ií] es|exacto|exactamente)",
        r"(gracias|listo|terminado)",
        r"(me gusta|funciona|sirve)",
    ]

    CLARIFICATION_PATTERNS = [
        r"(no entend[ií]|no s[ée]|c[óo]mo)",
        r"(qu[ée] (significa|es|quieres decir))",
        r"(puedes (explicar|aclarar))",
    ]

    def __init__(self):
        self.iteration = 0
        self.history: list[RefinementResult] = []

    def parse_feedback(self, feedback_text: str) -> ParsedFeedback:
        """Parsea feedback en lenguaje natural."""
        text_lower = feedback_text.lower()

        # Detectar tipo de feedback
        feedback_type = self._detect_feedback_type(text_lower)

        # Analizar sentimiento basico
        sentiment = self._analyze_sentiment(text_lower)

        # Extraer solicitudes de cambio
        change_requests = self._extract_change_requests(feedback_text)

        # Generar preguntas clarificadoras si es necesario
        clarifying_questions = self._generate_clarifying_questions(feedback_text, feedback_type)

        # Extraer keywords
        keywords = self._extract_keywords(feedback_text)

        return ParsedFeedback(
            original_text=feedback_text,
            feedback_type=feedback_type,
            sentiment=sentiment,
            change_requests=change_requests,
            clarifying_questions=clarifying_questions,
            keywords=keywords,
        )

    def _detect_feedback_type(self, text: str) -> FeedbackType:
        """Detecta el tipo de feedback."""
        # Verificar patrones en orden de especificidad
        for pattern in self.REJECTION_PATTERNS:
            if re.search(pattern, text):
                return FeedbackType.REJECTION

        for pattern in self.APPROVAL_PATTERNS:
            if re.search(pattern, text):
                # Verificar si hay "pero" despues
                if "pero" in text or "aunque" in text:
                    return FeedbackType.PARTIAL
                return FeedbackType.APPROVAL

        for pattern in self.CLARIFICATION_PATTERNS:
            if re.search(pattern, text):
                return FeedbackType.CLARIFICATION

        for pattern in self.MODIFICATION_PATTERNS:
            if re.search(pattern, text):
                return FeedbackType.MODIFICATION

        # Default
        return FeedbackType.MODIFICATION

    def _analyze_sentiment(self, text: str) -> float:
        """Analiza sentimiento del feedback (-1 a 1)."""
        positive_words = [
            "bien",
            "bueno",
            "excelente",
            "perfecto",
            "genial",
            "gracias",
            "funciona",
            "correcto",
            "me gusta",
        ]
        negative_words = [
            "mal",
            "malo",
            "incorrecto",
            "error",
            "falla",
            "no funciona",
            "no sirve",
            "problema",
            "no quiero",
        ]

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        return (positive_count - negative_count) / total

    def _extract_change_requests(self, text: str) -> list[ChangeRequest]:
        """Extrae solicitudes de cambio del feedback."""
        requests = []

        # Patrones para extraer cambios
        patterns = [
            (r"(?:quiero|necesito|prefiero)\s+(.+?)(?:\.|$)", Priority.IMPORTANT),
            (r"(?:agregar?|añadir?)\s+(.+?)(?:\.|$)", Priority.IMPORTANT),
            (r"(?:quitar?|remover?|eliminar?)\s+(.+?)(?:\.|$)", Priority.IMPORTANT),
            (r"(?:cambiar?)\s+(.+?)\s+(?:a|por)\s+(.+?)(?:\.|$)", Priority.IMPORTANT),
            (r"(?:en vez de|en lugar de)\s+(.+?),?\s*(.+?)(?:\.|$)", Priority.IMPORTANT),
        ]

        for pattern, priority in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                description = match.group(1).strip()
                if len(match.groups()) > 1:
                    description = f"{match.group(1)} -> {match.group(2)}"

                requests.append(ChangeRequest(description=description, priority=priority))

        return requests

    def _generate_clarifying_questions(self, text: str, feedback_type: FeedbackType) -> list[str]:
        """Genera preguntas clarificadoras si el feedback es ambiguo."""
        questions = []

        if feedback_type == FeedbackType.CLARIFICATION:
            questions.append("¿Puedes especificar qué parte no entendiste?")

        # Detectar ambiguedades
        if "algo" in text.lower() or "eso" in text.lower():
            questions.append("¿A qué te refieres específicamente?")

        if "mejor" in text.lower() and not re.search(r"mejor\s+\w+", text.lower()):
            questions.append("¿Cómo sería 'mejor' para ti?")

        if "no funciona" in text.lower():
            questions.append("¿Qué comportamiento esperabas vs lo que obtuviste?")

        return questions

    def _extract_keywords(self, text: str) -> list[str]:
        """Extrae keywords relevantes del feedback."""
        # Palabras a ignorar
        stopwords = {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "que",
            "de",
            "en",
            "y",
            "a",
            "por",
            "para",
            "con",
            "no",
            "es",
            "pero",
            "si",
            "esto",
            "eso",
            "este",
            "ese",
            "como",
            "mas",
            "muy",
            "ya",
        }

        # Extraer palabras
        words = re.findall(r"\b[a-záéíóúñ]+\b", text.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 3]

        # Deduplicar manteniendo orden
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        return unique[:10]  # Top 10 keywords

    def create_refinement_plan(self, feedback: ParsedFeedback) -> RefinementPlan:
        """Crea plan de refinamiento basado en feedback parseado."""
        actions = []
        requires_confirmation = False

        if feedback.feedback_type == FeedbackType.APPROVAL:
            return RefinementPlan(
                feedback=feedback,
                actions=[{"type": "complete", "description": "Solucion aceptada"}],
                estimated_effort="none",
                requires_confirmation=False,
            )

        if feedback.feedback_type == FeedbackType.REJECTION:
            actions.append({"type": "restart", "description": "Reiniciar desde requerimientos"})
            requires_confirmation = True

        elif feedback.feedback_type == FeedbackType.CLARIFICATION:
            actions.append({"type": "clarify", "questions": feedback.clarifying_questions})
            requires_confirmation = True

        else:  # MODIFICATION or PARTIAL
            for change in feedback.change_requests:
                actions.append(
                    {
                        "type": "modify",
                        "description": change.description,
                        "priority": change.priority.value,
                    }
                )

        # Agregar preguntas si hay ambiguedad
        if feedback.clarifying_questions and feedback.feedback_type != FeedbackType.CLARIFICATION:
            actions.append({"type": "clarify", "questions": feedback.clarifying_questions})

        # Estimar esfuerzo
        effort = "small"
        if len(feedback.change_requests) > 3:
            effort = "large"
        elif len(feedback.change_requests) > 1:
            effort = "medium"
        if feedback.feedback_type == FeedbackType.REJECTION:
            effort = "large"

        return RefinementPlan(
            feedback=feedback,
            actions=actions,
            estimated_effort=effort,
            requires_confirmation=requires_confirmation,
        )

    def execute(self, feedback_text: str) -> RefinementResult:
        """Ejecuta proceso completo de refinamiento."""
        self.iteration += 1

        # Parsear feedback
        parsed = self.parse_feedback(feedback_text)

        # Crear plan
        plan = self.create_refinement_plan(parsed)

        # Ejecutar acciones (simulado - en produccion invocaria otros agentes)
        changes_made = []
        for action in plan.actions:
            if action["type"] == "modify":
                changes_made.append(f"Applied: {action['description']}")
            elif action["type"] == "complete":
                changes_made.append("Solution finalized")

        # Calcular confianza
        confidence = 0.5
        if parsed.feedback_type == FeedbackType.APPROVAL:
            confidence = 1.0
        elif parsed.feedback_type == FeedbackType.PARTIAL:
            confidence = 0.7
        elif len(parsed.clarifying_questions) == 0:
            confidence = 0.8

        result = RefinementResult(
            success=True,
            iteration=self.iteration,
            original_feedback=feedback_text,
            changes_made=changes_made,
            pending_clarifications=parsed.clarifying_questions,
            confidence=confidence,
        )

        self.history.append(result)
        return result


def main():
    parser = argparse.ArgumentParser(
        description="Feedback Refiner - Incorpora feedback y refina soluciones"
    )
    parser.add_argument("feedback", nargs="?", help="Feedback del usuario a procesar")
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Solo analizar feedback, no ejecutar refinamiento",
    )

    args = parser.parse_args()

    if not args.feedback:
        print('Usage: feedback_refiner.py "tu feedback aqui"')
        sys.exit(1)

    refiner = FeedbackRefiner()

    if args.analyze_only:
        parsed = refiner.parse_feedback(args.feedback)
        if args.json:
            print(
                json.dumps(
                    {
                        "feedback_type": parsed.feedback_type.value,
                        "sentiment": parsed.sentiment,
                        "change_requests": [
                            {"description": cr.description, "priority": cr.priority.value}
                            for cr in parsed.change_requests
                        ],
                        "clarifying_questions": parsed.clarifying_questions,
                        "keywords": parsed.keywords,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(f"Tipo: {parsed.feedback_type.value}")
            print(f"Sentimiento: {parsed.sentiment:.2f}")
            print(f"Keywords: {', '.join(parsed.keywords)}")
            if parsed.change_requests:
                print("Cambios solicitados:")
                for cr in parsed.change_requests:
                    print(f"  - [{cr.priority.value}] {cr.description}")
            if parsed.clarifying_questions:
                print("Preguntas pendientes:")
                for q in parsed.clarifying_questions:
                    print(f"  ? {q}")
    else:
        result = refiner.execute(args.feedback)

        if args.json:
            print(
                json.dumps(
                    {
                        "success": result.success,
                        "iteration": result.iteration,
                        "changes_made": result.changes_made,
                        "pending_clarifications": result.pending_clarifications,
                        "confidence": result.confidence,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            status = "✓" if result.success else "✗"
            print(f"[{status}] Refinamiento #{result.iteration}")
            print(f"Confianza: {result.confidence:.0%}")
            if result.changes_made:
                print("Cambios aplicados:")
                for change in result.changes_made:
                    print(f"  + {change}")
            if result.pending_clarifications:
                print("Necesito clarificar:")
                for q in result.pending_clarifications:
                    print(f"  ? {q}")

    sys.exit(0)


if __name__ == "__main__":
    main()
