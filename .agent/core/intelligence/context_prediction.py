"""
Context Prediction Module - Prediccion de uso de contexto

Predice cuando el context window sera excedido y sugiere acciones.
"""
# mypy: ignore-errors

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ContextRisk(Enum):
    """Nivel de riesgo de overflow."""

    SAFE = "safe"  # < 50%
    MODERATE = "moderate"  # 50-70%
    WARNING = "warning"  # 70-85%
    CRITICAL = "critical"  # 85-95%
    OVERFLOW = "overflow"  # > 95%


class PredictionConfidence(Enum):
    """Confianza en la prediccion."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ContextUsage:
    """Uso de contexto en un momento."""

    timestamp: datetime
    tokens: int
    max_tokens: int
    message_count: int


@dataclass
class PredictionResult:
    """Prediccion de uso de contexto."""

    current_tokens: int
    predicted_tokens: int
    turns_until_warning: int
    turns_until_overflow: int
    risk_level: ContextRisk
    confidence: PredictionConfidence
    recommendations: list[str]


@dataclass
class CompressionRecommendation:
    """Recomendacion de compresion."""

    segment_id: str
    content_preview: str
    tokens: int
    priority: int  # 1-5, 1 = comprimir primero
    compression_type: str  # "archive", "summarize", "remove"
    expected_savings: int


class ContextPrediction:
    """
    Motor de prediccion de contexto.

    Funcionalidades:
    - Tracking de uso de tokens
    - Prediccion de overflow
    - Recomendaciones de compresion
    - Alertas proactivas
    """

    # Estimaciones de tokens por tipo de mensaje
    TOKEN_ESTIMATES = {
        "user_message": 150,
        "assistant_message": 500,
        "code_block": 800,
        "file_content": 2000,
        "tool_result": 300,
    }

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self.usage_history: list[ContextUsage] = []
        self.current_tokens = 0
        self.message_count = 0
        self.segments: list[dict] = []

    def record_usage(self, tokens: int):
        """
        Registra uso de tokens.

        Args:
            tokens: Tokens usados
        """
        self.current_tokens = tokens
        self.message_count += 1

        self.usage_history.append(
            ContextUsage(
                timestamp=datetime.now(),
                tokens=tokens,
                max_tokens=self.max_tokens,
                message_count=self.message_count,
            )
        )

        # Mantener solo ultimas 100 entradas
        if len(self.usage_history) > 100:
            self.usage_history = self.usage_history[-100:]

    def estimate_tokens(self, content: str, content_type: str = "user_message") -> int:
        """
        Estima tokens en contenido.

        Args:
            content: Contenido a estimar
            content_type: Tipo de contenido

        Returns:
            Tokens estimados
        """
        # Estimacion basica: ~4 caracteres por token
        char_estimate = len(content) // 4

        # Ajustar por tipo
        type_multiplier = {
            "user_message": 1.0,
            "assistant_message": 1.2,
            "code_block": 1.5,
            "file_content": 1.3,
            "tool_result": 1.1,
        }

        multiplier = type_multiplier.get(content_type, 1.0)
        return int(char_estimate * multiplier) + self.TOKEN_ESTIMATES.get(content_type, 100)

    def predict_overflow(
        self, additional_content: str | None = None, additional_tokens: int = 0
    ) -> PredictionResult:
        """
        Predice overflow de contexto.

        Args:
            additional_content: Contenido adicional a considerar
            additional_tokens: Tokens adicionales (alternativa)

        Returns:
            ContextPrediction
        """
        if additional_content:
            additional_tokens = self.estimate_tokens(additional_content)

        projected = self.current_tokens + additional_tokens
        usage_percent = (projected / self.max_tokens) * 100

        # Determinar nivel de riesgo
        if usage_percent < 50:
            risk = ContextRisk.SAFE
        elif usage_percent < 70:
            risk = ContextRisk.MODERATE
        elif usage_percent < 85:
            risk = ContextRisk.WARNING
        elif usage_percent < 95:
            risk = ContextRisk.CRITICAL
        else:
            risk = ContextRisk.OVERFLOW

        # Calcular turns hasta warning/overflow
        avg_tokens_per_turn = self._get_average_tokens_per_turn()
        tokens_until_warning = int(self.max_tokens * 0.7) - self.current_tokens
        tokens_until_overflow = self.max_tokens - self.current_tokens

        turns_until_warning = (
            max(0, tokens_until_warning // avg_tokens_per_turn) if avg_tokens_per_turn > 0 else 999
        )
        turns_until_overflow = (
            max(0, tokens_until_overflow // avg_tokens_per_turn) if avg_tokens_per_turn > 0 else 999
        )

        # Determinar confianza
        if len(self.usage_history) >= 10:
            confidence = PredictionConfidence.HIGH
        elif len(self.usage_history) >= 5:
            confidence = PredictionConfidence.MEDIUM
        else:
            confidence = PredictionConfidence.LOW

        # Generar recomendaciones
        recommendations = self._generate_recommendations(risk, usage_percent)

        return PredictionResult(
            current_tokens=self.current_tokens,
            predicted_tokens=projected,
            turns_until_warning=turns_until_warning,
            turns_until_overflow=turns_until_overflow,
            risk_level=risk,
            confidence=confidence,
            recommendations=recommendations,
        )

    def _get_average_tokens_per_turn(self) -> int:
        """Calcula tokens promedio por turno."""
        if len(self.usage_history) < 2:
            return 1000  # Default

        # Calcular diferencia entre registros consecutivos
        diffs = []
        for i in range(1, len(self.usage_history)):
            diff = self.usage_history[i].tokens - self.usage_history[i - 1].tokens
            if diff > 0:
                diffs.append(diff)

        if not diffs:
            return 1000

        return sum(diffs) // len(diffs)

    def _generate_recommendations(self, risk: ContextRisk, usage_percent: float) -> list[str]:
        """Genera recomendaciones basadas en riesgo."""
        recommendations = []

        if risk == ContextRisk.SAFE:
            recommendations.append("Context usage is healthy, no action needed")

        elif risk == ContextRisk.MODERATE:
            recommendations.append("Consider summarizing old context if conversation is long")

        elif risk == ContextRisk.WARNING:
            recommendations.append("Archive old context segments to free space")
            recommendations.append("Summarize completed tasks")
            recommendations.append("Remove redundant information")

        elif risk == ContextRisk.CRITICAL:
            recommendations.append("URGENT: Compress context immediately")
            recommendations.append("Archive all non-essential context")
            recommendations.append("Keep only: current task, critical decisions, active code")
            recommendations.append("Consider starting new conversation for new topics")

        elif risk == ContextRisk.OVERFLOW:
            recommendations.append("CRITICAL: Context will overflow")
            recommendations.append("Aggressive compression required")
            recommendations.append("Remove all archivable content")
            recommendations.append("Summarize everything except current task")

        return recommendations

    def add_segment(
        self, segment_id: str, content: str, priority: int = 3, category: str = "general"
    ):
        """
        Agrega segmento para tracking.

        Args:
            segment_id: ID del segmento
            content: Contenido
            priority: Prioridad (1=baja, 5=alta)
            category: Categoria
        """
        tokens = self.estimate_tokens(content)

        self.segments.append(
            {
                "id": segment_id,
                "content_preview": content[:100],
                "tokens": tokens,
                "priority": priority,
                "category": category,
                "added_at": datetime.now(),
            }
        )

    def get_compression_recommendations(
        self, target_reduction: int = 0
    ) -> list[CompressionRecommendation]:
        """
        Obtiene recomendaciones de compresion.

        Args:
            target_reduction: Tokens a reducir (0 = auto)

        Returns:
            Lista de recomendaciones ordenadas por prioridad
        """
        if target_reduction == 0:
            # Calcular objetivo: reducir a 60% si estamos > 80%
            if self.current_tokens > self.max_tokens * 0.8:
                target_reduction = self.current_tokens - int(self.max_tokens * 0.6)

        if target_reduction <= 0:
            return []

        recommendations = []

        # Ordenar segmentos por prioridad (menor primero)
        sorted_segments = sorted(self.segments, key=lambda s: (s["priority"], -s["tokens"]))

        tokens_to_remove = 0
        for seg in sorted_segments:
            if tokens_to_remove >= target_reduction:
                break

            # Determinar tipo de compresion
            if seg["priority"] <= 1:
                compression_type = "remove"
                expected_savings = seg["tokens"]
            elif seg["priority"] <= 3:
                compression_type = "archive"
                expected_savings = int(seg["tokens"] * 0.9)
            else:
                compression_type = "summarize"
                expected_savings = int(seg["tokens"] * 0.5)

            recommendations.append(
                CompressionRecommendation(
                    segment_id=seg["id"],
                    content_preview=seg["content_preview"],
                    tokens=seg["tokens"],
                    priority=seg["priority"],
                    compression_type=compression_type,
                    expected_savings=expected_savings,
                )
            )

            tokens_to_remove += expected_savings

        return recommendations

    def get_usage_trend(self) -> dict:
        """Obtiene tendencia de uso."""
        if len(self.usage_history) < 2:
            return {"trend": "unknown", "rate": 0}

        # Calcular tasa de crecimiento
        recent = self.usage_history[-5:]
        if len(recent) < 2:
            return {"trend": "stable", "rate": 0}

        growth = recent[-1].tokens - recent[0].tokens
        turns = len(recent)
        rate = growth / turns if turns > 0 else 0

        if rate > 1000:
            trend = "rapid_growth"
        elif rate > 500:
            trend = "growing"
        elif rate > 0:
            trend = "slow_growth"
        elif rate == 0:
            trend = "stable"
        else:
            trend = "decreasing"

        return {
            "trend": trend,
            "rate": rate,
            "current_usage_percent": (self.current_tokens / self.max_tokens) * 100,
            "samples": len(self.usage_history),
        }

    def get_summary(self) -> dict:
        """Obtiene resumen de predicciones."""
        prediction = self.predict_overflow()
        trend = self.get_usage_trend()

        return {
            "current_tokens": self.current_tokens,
            "max_tokens": self.max_tokens,
            "usage_percent": (self.current_tokens / self.max_tokens) * 100,
            "risk_level": prediction.risk_level.value,
            "turns_until_warning": prediction.turns_until_warning,
            "turns_until_overflow": prediction.turns_until_overflow,
            "trend": trend["trend"],
            "growth_rate": trend["rate"],
            "segments_tracked": len(self.segments),
            "recommendations": prediction.recommendations[:3],
        }


# Singleton
_context_prediction: ContextPrediction | None = None


def get_context_prediction(max_tokens: int = 200000) -> ContextPrediction:
    """Obtiene instancia singleton."""
    global _context_prediction
    if _context_prediction is None:
        _context_prediction = ContextPrediction(max_tokens)
    return _context_prediction
