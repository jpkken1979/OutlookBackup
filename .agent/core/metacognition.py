"""
Metacognition — el sistema piensa sobre cómo piensa.

Capa de auto-reflexión que monitorea el rendimiento del ecosistema
y ajusta estrategias globales:
  - Performance tracking: mide eficiencia de decisiones
  - Strategy assessment: evalúa si las estrategias actuales funcionan
  - Bottleneck detection: identifica cuellos de botella
  - Self-diagnosis: diagnostica problemas sistémicos
  - Adaptation recommendations: sugiere cambios

Usage:
    meta = Metacognition(bus=bus)

    # Registrar decisión y resultado
    meta.record_decision(
        decision="route_to_explorer",
        context={"task_type": "code_analysis"},
        outcome="success",
        quality=0.9,
    )

    # Evaluar estrategia
    assessment = meta.assess_strategy("routing")

    # Diagnóstico
    diagnosis = meta.diagnose()

    # Recomendaciones
    recs = meta.get_recommendations()
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.metacognition")

# ============================================================
# Constantes
# ============================================================
MAX_DECISIONS = 1000  # Historial de decisiones
ASSESSMENT_WINDOW = 300  # Ventana de evaluación (5 min)
MIN_SAMPLES_FOR_ASSESSMENT = 5  # Mínimo de samples para evaluar
QUALITY_THRESHOLD = 0.6  # Umbral de calidad aceptable
BOTTLENECK_THRESHOLD = 0.3  # Umbral de detección de bottleneck


# ============================================================
# Modelos
# ============================================================
@dataclass
class Decision:
    """Registro de una decisión del sistema."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    decision: str = ""
    strategy: str = "default"
    context: dict[str, Any] = field(default_factory=dict)
    outcome: str = "unknown"  # success, failure, partial, unknown
    quality: float = 0.5
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision": self.decision,
            "strategy": self.strategy,
            "context": self.context,
            "outcome": self.outcome,
            "quality": round(self.quality, 3),
            "latency_ms": round(self.latency_ms, 1),
            "timestamp": self.timestamp,
        }


@dataclass
class StrategyAssessment:
    """Evaluación de una estrategia."""

    strategy: str
    success_rate: float = 0.0
    avg_quality: float = 0.0
    avg_latency_ms: float = 0.0
    sample_count: int = 0
    recommendation: str = "maintain"  # maintain, adjust, replace
    issues: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "success_rate": round(self.success_rate, 3),
            "avg_quality": round(self.avg_quality, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "sample_count": self.sample_count,
            "recommendation": self.recommendation,
            "issues": self.issues,
        }


# ============================================================
# Metacognition
# ============================================================
class Metacognition:
    """
    Motor de metacognición — auto-reflexión y ajuste de estrategias.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Historial de decisiones
        self._decisions: list[Decision] = []

        # Decisiones por estrategia
        self._by_strategy: dict[str, list[Decision]] = defaultdict(list)

        # Assessments anteriores
        self._assessments: list[StrategyAssessment] = []

        # Bottlenecks detectados
        self._bottlenecks: list[dict[str, Any]] = []

        # Métricas
        self._metrics = {
            "decisions_recorded": 0,
            "assessments_performed": 0,
            "diagnoses_run": 0,
            "bottlenecks_detected": 0,
            "recommendations_generated": 0,
        }

    # --------------------------------------------------------
    # Record Decision
    # --------------------------------------------------------
    def record_decision(
        self,
        decision: str,
        strategy: str = "default",
        context: dict[str, Any] | None = None,
        outcome: str = "unknown",
        quality: float = 0.5,
        latency_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Registra una decisión y su resultado."""
        d = Decision(
            decision=decision,
            strategy=strategy,
            context=context or {},
            outcome=outcome,
            quality=max(0.0, min(1.0, quality)),
            latency_ms=latency_ms,
        )

        self._decisions.append(d)
        self._by_strategy[strategy].append(d)

        if len(self._decisions) > MAX_DECISIONS:
            self._decisions = self._decisions[-MAX_DECISIONS:]
        for key in self._by_strategy:
            if len(self._by_strategy[key]) > MAX_DECISIONS:
                self._by_strategy[key] = self._by_strategy[key][-MAX_DECISIONS:]

        self._metrics["decisions_recorded"] += 1
        return d.to_dict()

    # --------------------------------------------------------
    # Assess Strategy
    # --------------------------------------------------------
    def assess_strategy(
        self,
        strategy: str,
        window_seconds: float = ASSESSMENT_WINDOW,
    ) -> dict[str, Any]:
        """Evalúa una estrategia basada en decisiones recientes."""
        cutoff = time.time() - window_seconds
        decisions = [d for d in self._by_strategy.get(strategy, []) if d.timestamp >= cutoff]

        if len(decisions) < MIN_SAMPLES_FOR_ASSESSMENT:
            return {
                "strategy": strategy,
                "status": "insufficient_data",
                "sample_count": len(decisions),
                "minimum_required": MIN_SAMPLES_FOR_ASSESSMENT,
            }

        successes = sum(1 for d in decisions if d.outcome == "success")
        success_rate = successes / len(decisions)
        avg_quality = sum(d.quality for d in decisions) / len(decisions)
        avg_latency = sum(d.latency_ms for d in decisions) / len(decisions)

        issues = []
        recommendation = "maintain"

        if success_rate < 0.5:
            issues.append("Low success rate")
            recommendation = "replace"
        elif success_rate < 0.7:
            issues.append("Below-average success rate")
            recommendation = "adjust"

        if avg_quality < QUALITY_THRESHOLD:
            issues.append("Low quality outputs")
            if recommendation == "maintain":
                recommendation = "adjust"

        assessment = StrategyAssessment(
            strategy=strategy,
            success_rate=success_rate,
            avg_quality=avg_quality,
            avg_latency_ms=avg_latency,
            sample_count=len(decisions),
            recommendation=recommendation,
            issues=issues,
        )
        self._assessments.append(assessment)
        self._metrics["assessments_performed"] += 1

        return assessment.to_dict()

    def assess_all_strategies(self) -> list[dict[str, Any]]:
        """Evalúa todas las estrategias activas."""
        return [self.assess_strategy(s) for s in self._by_strategy]

    # --------------------------------------------------------
    # Diagnose
    # --------------------------------------------------------
    def diagnose(self) -> dict[str, Any]:
        """Diagnóstico completo del sistema."""
        self._metrics["diagnoses_run"] += 1
        now = time.time()
        recent = [d for d in self._decisions if d.timestamp > now - ASSESSMENT_WINDOW]

        if not recent:
            return {"status": "no_data", "message": "No recent decisions to analyze"}

        # Métricas globales
        total = len(recent)
        successes = sum(1 for d in recent if d.outcome == "success")
        failures = sum(1 for d in recent if d.outcome == "failure")
        avg_quality = sum(d.quality for d in recent) / total
        avg_latency = sum(d.latency_ms for d in recent) / total

        # Detectar bottlenecks
        bottlenecks = self._detect_bottlenecks(recent)

        # Detectar patrones problemáticos
        patterns = self._detect_patterns(recent)

        health = "healthy"
        if failures / total > 0.3:
            health = "degraded"
        if failures / total > 0.5:
            health = "critical"

        return {
            "health": health,
            "total_decisions": total,
            "success_rate": round(successes / total, 3),
            "failure_rate": round(failures / total, 3),
            "avg_quality": round(avg_quality, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "bottlenecks": bottlenecks,
            "patterns": patterns,
            "strategies_active": len(self._by_strategy),
        }

    # --------------------------------------------------------
    # Recommendations
    # --------------------------------------------------------
    def get_recommendations(self) -> list[dict[str, Any]]:
        """Genera recomendaciones basadas en diagnóstico."""
        self._metrics["recommendations_generated"] += 1
        recs = []

        diagnosis = self.diagnose()

        if diagnosis.get("health") == "critical":
            recs.append(
                {
                    "priority": "critical",
                    "action": "Review system health urgently",
                    "detail": f"Failure rate: {diagnosis.get('failure_rate', 0)}",
                }
            )

        for bottleneck in diagnosis.get("bottlenecks", []):
            recs.append(
                {
                    "priority": "high",
                    "action": f"Address bottleneck in {bottleneck['strategy']}",
                    "detail": bottleneck.get("detail", ""),
                }
            )

        # Strategy recommendations
        for strategy in self._by_strategy:
            assessment = self.assess_strategy(strategy)
            if assessment.get("recommendation") == "replace":
                recs.append(
                    {
                        "priority": "high",
                        "action": f"Replace strategy '{strategy}'",
                        "detail": f"Success rate: {assessment.get('success_rate', 0)}",
                    }
                )
            elif assessment.get("recommendation") == "adjust":
                recs.append(
                    {
                        "priority": "medium",
                        "action": f"Adjust strategy '{strategy}'",
                        "detail": ", ".join(assessment.get("issues", [])),
                    }
                )

        return sorted(
            recs, key=lambda r: {"critical": 0, "high": 1, "medium": 2}.get(r["priority"], 3)
        )

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_decisions(
        self,
        strategy: str | None = None,
        outcome: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de decisiones."""
        decisions = self._decisions
        if strategy:
            decisions = [d for d in decisions if d.strategy == strategy]
        if outcome:
            decisions = [d for d in decisions if d.outcome == outcome]
        return [d.to_dict() for d in decisions[-limit:]][::-1]

    def get_strategy_summary(self) -> list[dict[str, Any]]:
        """Resumen por estrategia."""
        summaries = []
        for strategy, decisions in self._by_strategy.items():
            if not decisions:
                continue
            recent = decisions[-50:]
            successes = sum(1 for d in recent if d.outcome == "success")
            summaries.append(
                {
                    "strategy": strategy,
                    "total_decisions": len(decisions),
                    "recent_success_rate": round(successes / len(recent), 3) if recent else 0.0,
                    "avg_quality": round(sum(d.quality for d in recent) / len(recent), 3),
                }
            )
        return sorted(summaries, key=lambda s: s["recent_success_rate"], reverse=True)

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del motor metacognitivo."""
        return {
            "total_decisions": len(self._decisions),
            "strategies_tracked": len(self._by_strategy),
            "assessments_history": len(self._assessments),
            "bottlenecks_active": len(self._bottlenecks),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _detect_bottlenecks(self, decisions: list[Decision]) -> list[dict[str, Any]]:
        """Detecta bottlenecks en decisiones recientes."""
        bottlenecks = []
        by_strategy: dict[str, list[Decision]] = defaultdict(list)
        for d in decisions:
            by_strategy[d.strategy].append(d)

        for strategy, decs in by_strategy.items():
            failures = sum(1 for d in decs if d.outcome == "failure")
            if len(decs) >= 3 and failures / len(decs) > BOTTLENECK_THRESHOLD:
                bottlenecks.append(
                    {
                        "strategy": strategy,
                        "failure_rate": round(failures / len(decs), 3),
                        "sample_count": len(decs),
                        "detail": f"{failures}/{len(decs)} failures",
                    }
                )
                self._metrics["bottlenecks_detected"] += 1

        self._bottlenecks = bottlenecks
        return bottlenecks

    def _detect_patterns(self, decisions: list[Decision]) -> list[dict[str, Any]]:
        """Detecta patrones en decisiones."""
        patterns = []

        # Patrón: decisiones repetidas con mismo resultado
        decision_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for d in decisions:
            decision_counts[d.decision][d.outcome] += 1

        for decision, outcomes in decision_counts.items():
            total = sum(outcomes.values())
            if total >= 3:
                dominant = max(outcomes, key=outcomes.get)  # type: ignore[arg-type]  # defaultdict.get is valid key func
                if outcomes[dominant] / total >= 0.8:
                    patterns.append(
                        {
                            "type": "dominant_outcome",
                            "decision": decision,
                            "outcome": dominant,
                            "frequency": round(outcomes[dominant] / total, 3),
                        }
                    )

        return patterns


# ============================================================
# Singleton
# ============================================================
_instance: Metacognition | None = None


def get_metacognition(bus: Any = None) -> Metacognition:
    """Obtiene o crea la metacognición global."""
    global _instance
    if _instance is None:
        _instance = Metacognition(bus=bus)
    return _instance
