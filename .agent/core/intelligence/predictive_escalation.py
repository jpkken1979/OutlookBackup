# mypy: ignore-errors
#!/usr/bin/env python3
"""
Predictive Escalation - Predicts when to escalate before failure.

This module provides early warning systems that:
1. Monitor execution progress and patterns
2. Predict potential failures before they occur
3. Recommend escalation to appropriate resources
4. Learn from historical escalation decisions

Usage:
    from .agent.core.intelligence import PredictiveEscalation, predict_escalation

    predictor = PredictiveEscalation()

    # Check if escalation might be needed
    prediction = await predictor.predict(
        task="Complex database migration",
        current_progress={"steps_completed": 3, "confidence": 0.4},
        context={"complexity": "high"}
    )

    if prediction.should_escalate:
        print(f"Recommend escalation: {prediction.recommendation}")
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.predictive_escalation")


class EscalationLevel(Enum):
    """Levels of escalation."""

    NONE = "none"  # No escalation needed
    WATCH = "watch"  # Monitor closely
    SOFT = "soft"  # Suggest getting help
    HARD = "hard"  # Strongly recommend escalation
    CRITICAL = "critical"  # Immediate escalation required


class EscalationTarget(Enum):
    """Who/what to escalate to."""

    HUMAN = "human"  # Human intervention
    SPECIALIST_AGENT = "specialist_agent"  # Another specialized agent
    SENIOR_AGENT = "senior_agent"  # Higher-tier agent
    DOCUMENTATION = "documentation"  # Need to consult docs
    EXTERNAL_RESOURCE = "external_resource"  # External API, service, etc.


class RiskCategory(Enum):
    """Categories of risk."""

    TECHNICAL = "technical"  # Technical complexity
    TIME = "time"  # Running out of time
    CONFIDENCE = "confidence"  # Low confidence
    RESOURCE = "resource"  # Resource constraints
    DEPENDENCY = "dependency"  # External dependencies
    UNKNOWN = "unknown"  # Unknown territory


@dataclass
class RiskSignal:
    """A signal indicating potential risk."""

    category: RiskCategory
    severity: float  # 0.0 to 1.0
    indicator: str
    detected_at: datetime = field(default_factory=datetime.now)
    trend: str = "stable"  # increasing, stable, decreasing

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "indicator": self.indicator,
            "detected_at": self.detected_at.isoformat(),
            "trend": self.trend,
        }


@dataclass
class EscalationPrediction:
    """Prediction about escalation need."""

    should_escalate: bool
    level: EscalationLevel
    confidence: float
    target: EscalationTarget
    recommendation: str
    risk_signals: list[RiskSignal]
    time_to_failure_estimate: timedelta | None
    suggested_actions: list[str]
    alternative_approaches: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_escalate": self.should_escalate,
            "level": self.level.value,
            "confidence": self.confidence,
            "target": self.target.value,
            "recommendation": self.recommendation,
            "risk_signals": [r.to_dict() for r in self.risk_signals],
            "time_to_failure_estimate": str(self.time_to_failure_estimate)
            if self.time_to_failure_estimate
            else None,
            "suggested_actions": self.suggested_actions,
            "alternative_approaches": self.alternative_approaches,
        }


@dataclass
class EscalationHistory:
    """Record of a past escalation."""

    task: str
    prediction: EscalationPrediction
    actual_outcome: str
    was_correct: bool
    timestamp: datetime = field(default_factory=datetime.now)


class RiskDetector:
    """Detects risk signals from execution state."""

    def __init__(self):
        self.risk_patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> dict[str, dict[str, Any]]:
        """Initialize known risk patterns."""
        return {
            # Technical complexity patterns
            "high_complexity": {
                "category": RiskCategory.TECHNICAL,
                "keywords": ["complex", "difficult", "tricky", "advanced", "sophisticated"],
                "base_severity": 0.6,
            },
            "unknown_domain": {
                "category": RiskCategory.UNKNOWN,
                "keywords": ["unfamiliar", "new", "unknown", "first time", "never done"],
                "base_severity": 0.7,
            },
            "multiple_systems": {
                "category": RiskCategory.DEPENDENCY,
                "keywords": [
                    "integration",
                    "multiple",
                    "distributed",
                    "microservices",
                    "cross-system",
                ],
                "base_severity": 0.5,
            },
            # Time patterns
            "tight_deadline": {
                "category": RiskCategory.TIME,
                "keywords": ["urgent", "asap", "deadline", "time-sensitive", "rush"],
                "base_severity": 0.6,
            },
            # Confidence patterns
            "low_confidence": {
                "category": RiskCategory.CONFIDENCE,
                "keywords": ["unsure", "uncertain", "might", "maybe", "possibly"],
                "base_severity": 0.5,
            },
            # Resource patterns
            "resource_intensive": {
                "category": RiskCategory.RESOURCE,
                "keywords": ["large-scale", "heavy", "resource-intensive", "memory", "cpu"],
                "base_severity": 0.4,
            },
        }

    def detect_risks(
        self,
        task: str,
        progress: dict[str, Any],
        context: dict[str, Any],
    ) -> list[RiskSignal]:
        """
        Detect risk signals from task and progress.

        Args:
            task: Task description
            progress: Current progress data
            context: Additional context

        Returns:
            List of detected risk signals
        """
        signals = []
        task_lower = task.lower()

        # Pattern-based detection
        for pattern_name, pattern in self.risk_patterns.items():
            keywords = pattern["keywords"]
            matches = sum(1 for kw in keywords if kw in task_lower)

            if matches > 0:
                severity = min(1.0, pattern["base_severity"] + matches * 0.1)
                signals.append(
                    RiskSignal(
                        category=pattern["category"],
                        severity=severity,
                        indicator=f"Pattern '{pattern_name}' detected ({matches} keyword matches)",
                    )
                )

        # Progress-based detection
        signals.extend(self._analyze_progress(progress))

        # Context-based detection
        signals.extend(self._analyze_context(context))

        # Sort by severity
        return sorted(signals, key=lambda s: s.severity, reverse=True)

    def _analyze_progress(self, progress: dict[str, Any]) -> list[RiskSignal]:
        """Analyze progress for risk signals."""
        signals = []

        # Check confidence
        confidence = progress.get("confidence", 1.0)
        if confidence < 0.4:
            signals.append(
                RiskSignal(
                    category=RiskCategory.CONFIDENCE,
                    severity=0.8,
                    indicator=f"Very low confidence: {confidence:.0%}",
                    trend="decreasing" if progress.get("confidence_trend") == "down" else "stable",
                )
            )
        elif confidence < 0.6:
            signals.append(
                RiskSignal(
                    category=RiskCategory.CONFIDENCE,
                    severity=0.5,
                    indicator=f"Low confidence: {confidence:.0%}",
                )
            )

        # Check steps progress
        steps_completed = progress.get("steps_completed", 0)
        total_steps = progress.get("total_steps", 0)
        if total_steps > 0:
            progress_ratio = steps_completed / total_steps
            if progress_ratio < 0.2 and steps_completed > 0:
                # Slow progress
                signals.append(
                    RiskSignal(
                        category=RiskCategory.TIME,
                        severity=0.4,
                        indicator=f"Slow progress: {steps_completed}/{total_steps} steps",
                    )
                )

        # Check retries
        retries = progress.get("retries", 0)
        if retries >= 2:
            signals.append(
                RiskSignal(
                    category=RiskCategory.TECHNICAL,
                    severity=0.6 + retries * 0.1,
                    indicator=f"Multiple retries: {retries}",
                    trend="increasing",
                )
            )

        # Check errors
        errors = progress.get("errors", [])
        if len(errors) >= 2:
            signals.append(
                RiskSignal(
                    category=RiskCategory.TECHNICAL,
                    severity=0.7,
                    indicator=f"Multiple errors encountered: {len(errors)}",
                )
            )

        # Check duration
        duration_ms = progress.get("duration_ms", 0)
        expected_ms = progress.get("expected_duration_ms", 0)
        if expected_ms > 0 and duration_ms > expected_ms * 1.5:
            signals.append(
                RiskSignal(
                    category=RiskCategory.TIME,
                    severity=0.6,
                    indicator=f"Taking longer than expected: {duration_ms / 1000:.1f}s vs {expected_ms / 1000:.1f}s expected",
                )
            )

        return signals

    def _analyze_context(self, context: dict[str, Any]) -> list[RiskSignal]:
        """Analyze context for risk signals."""
        signals = []

        # Check complexity rating
        complexity = context.get("complexity", "").lower()
        if complexity in ["high", "very high", "extreme"]:
            signals.append(
                RiskSignal(
                    category=RiskCategory.TECHNICAL,
                    severity=0.7 if complexity == "high" else 0.9,
                    indicator=f"High complexity rating: {complexity}",
                )
            )

        # Check external dependencies
        dependencies = context.get("external_dependencies", [])
        if len(dependencies) >= 3:
            signals.append(
                RiskSignal(
                    category=RiskCategory.DEPENDENCY,
                    severity=0.5,
                    indicator=f"Multiple external dependencies: {len(dependencies)}",
                )
            )

        # Check if this is new territory
        is_new = context.get("is_new_domain", False)
        if is_new:
            signals.append(
                RiskSignal(
                    category=RiskCategory.UNKNOWN,
                    severity=0.6,
                    indicator="Operating in unfamiliar domain",
                )
            )

        # Check security sensitivity
        is_security = context.get("security_sensitive", False)
        if is_security:
            signals.append(
                RiskSignal(
                    category=RiskCategory.TECHNICAL,
                    severity=0.5,
                    indicator="Security-sensitive operation",
                )
            )

        # Check production impact
        is_production = context.get("production_impact", False)
        if is_production:
            signals.append(
                RiskSignal(
                    category=RiskCategory.TECHNICAL,
                    severity=0.6,
                    indicator="Has production impact",
                )
            )

        return signals


class EscalationPredictor:
    """Predicts escalation need from risk signals."""

    # Thresholds
    WATCH_THRESHOLD = 0.3
    SOFT_THRESHOLD = 0.5
    HARD_THRESHOLD = 0.7
    CRITICAL_THRESHOLD = 0.9

    def predict(
        self,
        signals: list[RiskSignal],
        task: str,
        context: dict[str, Any],
    ) -> EscalationPrediction:
        """
        Predict escalation need from signals.

        Args:
            signals: Detected risk signals
            task: Task description
            context: Additional context

        Returns:
            EscalationPrediction
        """
        if not signals:
            return EscalationPrediction(
                should_escalate=False,
                level=EscalationLevel.NONE,
                confidence=0.9,
                target=EscalationTarget.HUMAN,
                recommendation="No escalation needed - no risk signals detected",
                risk_signals=[],
                time_to_failure_estimate=None,
                suggested_actions=["Continue execution"],
                alternative_approaches=[],
            )

        # Calculate aggregate risk
        aggregate_risk = self._calculate_aggregate_risk(signals)

        # Determine escalation level
        level = self._determine_level(aggregate_risk)

        # Determine target
        target = self._determine_target(signals, context)

        # Generate recommendation
        recommendation = self._generate_recommendation(level, signals, target)

        # Estimate time to failure
        time_estimate = self._estimate_time_to_failure(signals, context)

        # Generate suggested actions
        actions = self._generate_actions(level, signals)

        # Generate alternatives
        alternatives = self._generate_alternatives(signals, context)

        # Calculate confidence
        confidence = self._calculate_confidence(signals, aggregate_risk)

        return EscalationPrediction(
            should_escalate=level.value not in ["none", "watch"],
            level=level,
            confidence=confidence,
            target=target,
            recommendation=recommendation,
            risk_signals=signals,
            time_to_failure_estimate=time_estimate,
            suggested_actions=actions,
            alternative_approaches=alternatives,
        )

    def _calculate_aggregate_risk(self, signals: list[RiskSignal]) -> float:
        """Calculate aggregate risk from signals."""
        if not signals:
            return 0.0

        # Weighted combination
        # Higher weights for more signals with high severity
        total_weight = 0.0
        weighted_sum = 0.0

        for i, signal in enumerate(signals):
            # More weight to higher severity signals
            weight = 1.0 + signal.severity
            # Slightly less weight to later signals (diminishing returns)
            weight *= 0.9**i

            weighted_sum += signal.severity * weight
            total_weight += weight

        base_risk = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Bonus for multiple signals
        signal_bonus = min(0.2, len(signals) * 0.03)

        # Bonus for increasing trends
        trend_bonus = sum(0.05 for s in signals if s.trend == "increasing")

        return min(1.0, base_risk + signal_bonus + trend_bonus)

    def _determine_level(self, aggregate_risk: float) -> EscalationLevel:
        """Determine escalation level from aggregate risk."""
        if aggregate_risk >= self.CRITICAL_THRESHOLD:
            return EscalationLevel.CRITICAL
        elif aggregate_risk >= self.HARD_THRESHOLD:
            return EscalationLevel.HARD
        elif aggregate_risk >= self.SOFT_THRESHOLD:
            return EscalationLevel.SOFT
        elif aggregate_risk >= self.WATCH_THRESHOLD:
            return EscalationLevel.WATCH
        else:
            return EscalationLevel.NONE

    def _determine_target(
        self,
        signals: list[RiskSignal],
        context: dict[str, Any],
    ) -> EscalationTarget:
        """Determine best escalation target."""
        # Analyze dominant risk categories
        category_severity = {}
        for signal in signals:
            cat = signal.category
            if cat not in category_severity:
                category_severity[cat] = 0.0
            category_severity[cat] = max(category_severity[cat], signal.severity)

        # Decision logic
        if (
            RiskCategory.UNKNOWN in category_severity
            and category_severity[RiskCategory.UNKNOWN] > 0.6
        ):
            return EscalationTarget.HUMAN

        if (
            RiskCategory.TECHNICAL in category_severity
            and category_severity[RiskCategory.TECHNICAL] > 0.7
        ):
            return EscalationTarget.SPECIALIST_AGENT

        if (
            RiskCategory.CONFIDENCE in category_severity
            and category_severity[RiskCategory.CONFIDENCE] > 0.6
        ):
            return EscalationTarget.DOCUMENTATION

        if (
            RiskCategory.DEPENDENCY in category_severity
            and category_severity[RiskCategory.DEPENDENCY] > 0.5
        ):
            return EscalationTarget.EXTERNAL_RESOURCE

        # Default to human for high overall risk
        max_severity = max(s.severity for s in signals) if signals else 0
        if max_severity > 0.8:
            return EscalationTarget.HUMAN

        return EscalationTarget.SENIOR_AGENT

    def _generate_recommendation(
        self,
        level: EscalationLevel,
        signals: list[RiskSignal],
        target: EscalationTarget,
    ) -> str:
        """Generate human-readable recommendation."""
        if level == EscalationLevel.NONE:
            return "Continue execution - no significant risks detected."

        if level == EscalationLevel.WATCH:
            top_signal = signals[0] if signals else None
            return f"Monitor closely - {top_signal.indicator if top_signal else 'elevated risk signals'}"

        if level == EscalationLevel.SOFT:
            target_desc = {
                EscalationTarget.HUMAN: "human oversight",
                EscalationTarget.SPECIALIST_AGENT: "a specialist agent",
                EscalationTarget.SENIOR_AGENT: "a senior agent",
                EscalationTarget.DOCUMENTATION: "documentation",
                EscalationTarget.EXTERNAL_RESOURCE: "external resources",
            }
            return f"Consider getting {target_desc.get(target, 'help')} - multiple risk signals detected"

        if level == EscalationLevel.HARD:
            return f"Strongly recommend escalation to {target.value} - high risk of failure"

        if level == EscalationLevel.CRITICAL:
            return f"IMMEDIATE ESCALATION REQUIRED to {target.value} - critical risk level"

        return "Evaluate escalation need"

    def _estimate_time_to_failure(
        self,
        signals: list[RiskSignal],
        context: dict[str, Any],
    ) -> timedelta | None:
        """Estimate time until likely failure."""
        # Check for time-related signals
        time_signals = [s for s in signals if s.category == RiskCategory.TIME]
        if not time_signals:
            return None

        # Check for increasing trend
        increasing = any(s.trend == "increasing" for s in signals)

        # Base estimate on severity
        max_severity = max(s.severity for s in time_signals)

        if max_severity > 0.8:
            minutes = 5 if increasing else 15
        elif max_severity > 0.6:
            minutes = 15 if increasing else 30
        elif max_severity > 0.4:
            minutes = 30 if increasing else 60
        else:
            minutes = 60 if increasing else 120

        return timedelta(minutes=minutes)

    def _generate_actions(
        self,
        level: EscalationLevel,
        signals: list[RiskSignal],
    ) -> list[str]:
        """Generate suggested actions."""
        actions = []

        if level == EscalationLevel.NONE:
            actions.append("Continue with current approach")
            return actions

        # Category-specific actions
        categories = {s.category for s in signals}

        if RiskCategory.TECHNICAL in categories:
            actions.append("Break down task into smaller steps")
            actions.append("Document current understanding before proceeding")

        if RiskCategory.CONFIDENCE in categories:
            actions.append("Verify assumptions with explicit checks")
            actions.append("Add intermediate validation steps")

        if RiskCategory.TIME in categories:
            actions.append("Prioritize critical path items")
            actions.append("Consider parallel execution where possible")

        if RiskCategory.UNKNOWN in categories:
            actions.append("Research domain before proceeding")
            actions.append("Find similar solved problems for reference")

        if RiskCategory.DEPENDENCY in categories:
            actions.append("Verify all dependencies are available")
            actions.append("Create fallback plan for dependency failures")

        # Level-specific actions
        if level in [EscalationLevel.HARD, EscalationLevel.CRITICAL]:
            actions.insert(0, "PAUSE execution and escalate")
            actions.append("Document current state for handover")

        return actions[:5]

    def _generate_alternatives(
        self,
        signals: list[RiskSignal],
        context: dict[str, Any],
    ) -> list[str]:
        """Generate alternative approaches."""
        alternatives = []

        # Based on risk categories
        categories = {s.category for s in signals}

        if RiskCategory.TECHNICAL in categories:
            alternatives.append("Use a simpler implementation approach")
            alternatives.append("Delegate to specialist agent")

        if RiskCategory.TIME in categories:
            alternatives.append("Implement minimum viable solution first")
            alternatives.append("Request deadline extension")

        if RiskCategory.DEPENDENCY in categories:
            alternatives.append("Use mock/stub implementations temporarily")
            alternatives.append("Isolate dependent components")

        if RiskCategory.UNKNOWN in categories:
            alternatives.append("Use well-known patterns from similar domains")
            alternatives.append("Prototype and validate before full implementation")

        return alternatives[:3]

    def _calculate_confidence(
        self,
        signals: list[RiskSignal],
        aggregate_risk: float,
    ) -> float:
        """Calculate confidence in the prediction."""
        # Base confidence
        confidence = 0.7

        # More signals = more confident
        if len(signals) >= 3:
            confidence += 0.1
        elif len(signals) >= 2:
            confidence += 0.05

        # Consistent signals = more confident
        categories = [s.category for s in signals]
        unique_categories = len(set(categories))
        if unique_categories == 1 and len(signals) > 1:
            confidence += 0.1  # All signals point to same issue

        # Extreme risk = more confident
        if aggregate_risk > 0.8 or aggregate_risk < 0.2:
            confidence += 0.1

        return min(0.95, confidence)


class PredictiveEscalation:
    """
    Main class for predictive escalation.

    This class:
    1. Monitors execution state
    2. Detects risk signals
    3. Predicts escalation needs
    4. Learns from outcomes
    """

    def __init__(self, memory_dir: Path | None = None):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_ESCALATION_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_ESCALATION_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "escalation"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.detector = RiskDetector()
        self.predictor = EscalationPredictor()

        # History for learning
        self.history: list[EscalationHistory] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load escalation history."""
        history_file = self.memory_dir / "escalation_history.json"
        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    json.load(f)
                    # Load history (simplified)
                    logger.info("Loaded escalation history")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

    def _save_history(self) -> None:
        """Save escalation history."""
        history_file = self.memory_dir / "escalation_history.json"
        data = [
            {
                "task": h.task,
                "was_correct": h.was_correct,
                "timestamp": h.timestamp.isoformat(),
            }
            for h in self.history[-100:]  # Keep last 100
        ]
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def predict(
        self,
        task: str,
        current_progress: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EscalationPrediction:
        """
        Predict if escalation is needed.

        Args:
            task: Task description
            current_progress: Current execution progress
            context: Additional context

        Returns:
            EscalationPrediction
        """
        context = context or {}

        # Detect risk signals
        signals = self.detector.detect_risks(task, current_progress, context)

        # Make prediction
        prediction = self.predictor.predict(signals, task, context)

        # Log prediction
        logger.info(
            f"Escalation prediction: level={prediction.level.value}, "
            f"should_escalate={prediction.should_escalate}, "
            f"confidence={prediction.confidence:.0%}"
        )

        return prediction

    async def record_outcome(
        self,
        task: str,
        prediction: EscalationPrediction,
        actual_outcome: str,
        was_escalation_helpful: bool,
    ) -> None:
        """
        Record the actual outcome for learning.

        Args:
            task: The task
            prediction: The prediction made
            actual_outcome: What actually happened
            was_escalation_helpful: Whether escalation (or lack thereof) was the right call
        """
        history = EscalationHistory(
            task=task,
            prediction=prediction,
            actual_outcome=actual_outcome,
            was_correct=was_escalation_helpful,
        )
        self.history.append(history)
        self._save_history()

        # Update predictor thresholds based on feedback
        # (In a real system, this would adjust the model)
        logger.info(f"Recorded escalation outcome: correct={was_escalation_helpful}")

    async def analyze_task(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> EscalationPrediction:
        """
        Quick analysis of a task before execution.

        Args:
            task: Task description
            context: Optional context

        Returns:
            Initial risk assessment
        """
        # Use empty progress for pre-execution analysis
        return await self.predict(
            task=task,
            current_progress={},
            context=context or {},
        )

    def get_historical_accuracy(self) -> float:
        """Get prediction accuracy from history."""
        if not self.history:
            return 0.0
        correct = sum(1 for h in self.history if h.was_correct)
        return correct / len(self.history)

    def export_report(self) -> str:
        """Export escalation report as markdown."""
        lines = [
            "# Escalation Analysis Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Historical Accuracy",
            "",
            f"Total predictions: {len(self.history)}",
            f"Accuracy: {self.get_historical_accuracy():.0%}",
            "",
            "## Risk Patterns",
            "",
        ]

        # Analyze history for patterns
        if self.history:
            category_counts: dict[str, int] = {}
            for h in self.history:
                for signal in h.prediction.risk_signals:
                    cat = signal.category.value
                    category_counts[cat] = category_counts.get(cat, 0) + 1

            lines.append("| Risk Category | Occurrences |")
            lines.append("|---------------|-------------|")
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {cat} | {count} |")

        return "\n".join(lines)


# Convenience function
async def predict_escalation(
    task: str,
    progress: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> EscalationPrediction:
    """Quick function to predict escalation."""
    predictor = PredictiveEscalation()
    return await predictor.predict(task, progress, context)
