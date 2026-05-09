"""
Predictive Prefetch — Motor anticipatorio.

Analiza patrones temporales de tareas para predecir qué viene:
  - Secuencias frecuentes: si "explorer" siempre precede a "architect",
    pre-calentar "architect" cuando "explorer" inicia
  - Patrones temporales: ciertos agentes se usan en horarios específicos
  - Markov chain: la probabilidad del siguiente agente basada en el actual
  - Pre-warming: notifica al sistema para reservar recursos
  - Cache de predicciones para respuesta instantánea

Usage:
    prefetch = PredictivePrefetch(bus=bus)

    # Registrar activación de agente
    prefetch.record_activation("explorer", task="analyze code")

    # Obtener predicciones
    predictions = prefetch.predict_next(current_agent="explorer")
    # [{"agent": "architect", "confidence": 0.82, "reason": "frequent_sequence"}]

    # Warm-up recomendado
    warmup = prefetch.get_warmup_list()
    # ["architect", "security-auditor"]

    # Estadísticas de precisión
    stats = prefetch.get_prediction_accuracy()
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.predictive_prefetch")

# ============================================================
# Constantes
# ============================================================
MIN_SEQUENCE_COUNT = 2  # Mínimo de ocurrencias para ser patrón
PREDICTION_CONFIDENCE_MIN = 0.2  # Confianza mínima para predecir
MAX_ACTIVATION_HISTORY = 2000  # Máximo de activaciones en memoria
MAX_PREDICTIONS_RETURNED = 5  # Máximo de predicciones retornadas
PREDICTION_DECAY_HOURS = 24  # Ventana temporal para predicciones
WARMUP_CONFIDENCE_MIN = 0.5  # Confianza mínima para warmup


# ============================================================
# Modelos
# ============================================================
@dataclass
class Activation:
    """Registro de una activación de agente."""

    agent: str
    task: str = ""
    domain: str = "general"
    timestamp: float = field(default_factory=time.time)
    success: bool | None = None  # None = en progreso

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "task": self.task,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "success": self.success,
        }


@dataclass
class Prediction:
    """Una predicción de próxima activación."""

    agent: str
    confidence: float  # [0, 1]
    reason: str  # "markov_chain", "time_pattern", "domain_affinity"
    expected_domain: str = "general"
    warmup_recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "expected_domain": self.expected_domain,
            "warmup_recommended": self.warmup_recommended,
        }


@dataclass
class PredictionResult:
    """Resultado de una predicción verificada."""

    predicted_agent: str
    actual_agent: str
    confidence: float
    correct: bool
    timestamp: float = field(default_factory=time.time)


# ============================================================
# Predictive Prefetch
# ============================================================
class PredictivePrefetch:
    """
    Motor anticipatorio que predice qué agentes se necesitarán.
    Usa cadenas de Markov + patrones temporales + afinidad de dominio.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Historial de activaciones
        self._activations: list[Activation] = []

        # Markov: transition_counts[from_agent][to_agent] = count
        self._transitions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Patrones temporales: hour_patterns[hour][agent] = count
        self._hour_patterns: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Domain sequences: domain_patterns[domain][agent] = count
        self._domain_patterns: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Tracking de precisión
        self._prediction_results: list[PredictionResult] = []
        self._last_predictions: list[Prediction] = []

        # Métricas
        self._metrics = {
            "activations_recorded": 0,
            "predictions_made": 0,
            "predictions_correct": 0,
            "predictions_incorrect": 0,
            "warmups_recommended": 0,
        }

    # --------------------------------------------------------
    # Record Activation
    # --------------------------------------------------------
    def record_activation(
        self,
        agent: str,
        task: str = "",
        domain: str = "general",
        success: bool | None = None,
    ) -> None:
        """
        Registra una activación de agente.

        Actualiza las matrices de transición, patrones temporales,
        y verifica predicciones anteriores.
        """
        activation = Activation(
            agent=agent,
            task=task,
            domain=domain,
            success=success,
        )
        self._activations.append(activation)

        # Update Markov chain
        if len(self._activations) >= 2:
            prev_agent = self._activations[-2].agent
            self._transitions[prev_agent][agent] += 1

        # Update temporal patterns
        hour = time.localtime().tm_hour
        self._hour_patterns[hour][agent] += 1

        # Update domain patterns
        self._domain_patterns[domain][agent] += 1

        # Verify previous predictions
        self._verify_predictions(agent)

        # Limit history
        if len(self._activations) > MAX_ACTIVATION_HISTORY:
            self._activations = self._activations[-MAX_ACTIVATION_HISTORY:]

        self._metrics["activations_recorded"] += 1

    # --------------------------------------------------------
    # Predict Next
    # --------------------------------------------------------
    def predict_next(
        self,
        current_agent: str | None = None,
        current_domain: str | None = None,
        limit: int = MAX_PREDICTIONS_RETURNED,
    ) -> list[dict[str, Any]]:
        """
        Predice los próximos agentes que se necesitarán.

        Combina:
          1. Markov chain (transiciones históricas)
          2. Patrones temporales (hora del día)
          3. Afinidad de dominio

        Returns:
            Lista de predicciones ordenadas por confianza.
        """
        if not current_agent and self._activations:
            current_agent = self._activations[-1].agent

        if not current_agent:
            return []

        candidates: dict[str, float] = defaultdict(float)
        reasons: dict[str, str] = {}
        domains: dict[str, str] = {}

        # 1. Markov chain predictions (weight: 0.5)
        if current_agent in self._transitions:
            total = sum(self._transitions[current_agent].values())
            if total >= MIN_SEQUENCE_COUNT:
                for next_agent, count in self._transitions[current_agent].items():
                    prob = count / total
                    candidates[next_agent] += prob * 0.5
                    if next_agent not in reasons or prob > candidates[next_agent]:
                        reasons[next_agent] = "markov_chain"

        # 2. Temporal patterns (weight: 0.3)
        hour = time.localtime().tm_hour
        if hour in self._hour_patterns:
            total = sum(self._hour_patterns[hour].values())
            if total >= MIN_SEQUENCE_COUNT:
                for agent, count in self._hour_patterns[hour].items():
                    prob = count / total
                    candidates[agent] += prob * 0.3
                    if agent not in reasons:
                        reasons[agent] = "time_pattern"

        # 3. Domain affinity (weight: 0.2)
        domain = current_domain or "general"
        if domain in self._domain_patterns:
            total = sum(self._domain_patterns[domain].values())
            if total >= MIN_SEQUENCE_COUNT:
                for agent, count in self._domain_patterns[domain].items():
                    prob = count / total
                    candidates[agent] += prob * 0.2
                    if agent not in reasons:
                        reasons[agent] = "domain_affinity"
                    domains[agent] = domain

        # Filter and sort
        predictions = []
        for agent, confidence in sorted(
            candidates.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if confidence < PREDICTION_CONFIDENCE_MIN:
                continue
            if agent == current_agent:
                continue  # Don't predict self

            pred = Prediction(
                agent=agent,
                confidence=min(1.0, confidence),
                reason=reasons.get(agent, "combined"),
                expected_domain=domains.get(agent, "general"),
                warmup_recommended=confidence >= WARMUP_CONFIDENCE_MIN,
            )
            predictions.append(pred)

            if len(predictions) >= limit:
                break

        self._last_predictions = predictions
        self._metrics["predictions_made"] += 1

        return [p.to_dict() for p in predictions]

    # --------------------------------------------------------
    # Warmup List
    # --------------------------------------------------------
    def get_warmup_list(
        self,
        current_agent: str | None = None,
    ) -> list[str]:
        """
        Retorna lista de agentes que deberían pre-calentarse.

        Solo incluye agentes con confianza >= WARMUP_CONFIDENCE_MIN.
        """
        predictions = self.predict_next(current_agent)
        warmup = [p["agent"] for p in predictions if p["warmup_recommended"]]
        self._metrics["warmups_recommended"] += len(warmup)
        return warmup

    # --------------------------------------------------------
    # Sequence Analysis
    # --------------------------------------------------------
    def get_frequent_sequences(
        self,
        min_count: int = 3,
        max_length: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Encuentra secuencias frecuentes de agentes.

        Returns:
            Lista de secuencias con sus frecuencias.
        """
        if len(self._activations) < 2:
            return []

        # Extract sequences of different lengths
        sequence_counts: dict[tuple[str, ...], int] = defaultdict(int)

        agents = [a.agent for a in self._activations]
        for length in range(2, max_length + 1):
            for i in range(len(agents) - length + 1):
                seq = tuple(agents[i : i + length])
                sequence_counts[seq] += 1

        # Filter and sort
        results = []
        for seq, count in sorted(
            sequence_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if count >= min_count:
                results.append(
                    {
                        "sequence": list(seq),
                        "length": len(seq),
                        "count": count,
                        "frequency": round(count / (len(agents) - len(seq) + 1), 3),
                    }
                )

        return results[:20]

    def get_transition_matrix(self) -> dict[str, dict[str, float]]:
        """Retorna la matriz de transición normalizada."""
        matrix: dict[str, dict[str, float]] = {}
        for from_agent, targets in self._transitions.items():
            total = sum(targets.values())
            if total > 0:
                matrix[from_agent] = {
                    to_agent: round(count / total, 3)
                    for to_agent, count in sorted(
                        targets.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                }
        return matrix

    # --------------------------------------------------------
    # Prediction Accuracy
    # --------------------------------------------------------
    def get_prediction_accuracy(self) -> dict[str, Any]:
        """Estadísticas de precisión de predicciones."""
        total = self._metrics["predictions_correct"] + self._metrics["predictions_incorrect"]
        accuracy = self._metrics["predictions_correct"] / total if total > 0 else 0.0
        return {
            "total_verified": total,
            "correct": self._metrics["predictions_correct"],
            "incorrect": self._metrics["predictions_incorrect"],
            "accuracy": round(accuracy, 3),
            "predictions_made": self._metrics["predictions_made"],
        }

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del motor predictivo."""
        unique_agents = set()
        for a in self._activations:
            unique_agents.add(a.agent)

        return {
            "activations_total": len(self._activations),
            "unique_agents": len(unique_agents),
            "transition_pairs": sum(len(targets) for targets in self._transitions.values()),
            "hours_tracked": len(self._hour_patterns),
            "domains_tracked": len(self._domain_patterns),
            "accuracy": self.get_prediction_accuracy(),
            "metrics": {**self._metrics},
        }

    def get_activation_history(
        self,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de activaciones."""
        records = self._activations
        if agent:
            records = [a for a in records if a.agent == agent]
        return [a.to_dict() for a in records[-limit:]][::-1]

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _verify_predictions(self, actual_agent: str) -> None:
        """Verifica si las predicciones anteriores fueron correctas."""
        if not self._last_predictions:
            return

        predicted_agents = {p.agent for p in self._last_predictions}
        if actual_agent in predicted_agents:
            self._metrics["predictions_correct"] += 1
            # Find the prediction
            for p in self._last_predictions:
                if p.agent == actual_agent:
                    self._prediction_results.append(
                        PredictionResult(
                            predicted_agent=p.agent,
                            actual_agent=actual_agent,
                            confidence=p.confidence,
                            correct=True,
                        )
                    )
                    break
        elif self._last_predictions:
            self._metrics["predictions_incorrect"] += 1
            self._prediction_results.append(
                PredictionResult(
                    predicted_agent=self._last_predictions[0].agent,
                    actual_agent=actual_agent,
                    confidence=self._last_predictions[0].confidence,
                    correct=False,
                )
            )

        # Keep results bounded
        if len(self._prediction_results) > 500:
            self._prediction_results = self._prediction_results[-500:]


# ============================================================
# Singleton
# ============================================================
_instance: PredictivePrefetch | None = None


def get_predictive_prefetch(bus: Any = None) -> PredictivePrefetch:
    """Obtiene o crea el motor predictivo global."""
    global _instance
    if _instance is None:
        _instance = PredictivePrefetch(bus=bus)
    return _instance
