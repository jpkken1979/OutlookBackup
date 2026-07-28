# mypy: ignore-errors
"""Helpers async que despachan a los modulos de inteligencia (mixin).

Extraido de ``IntelligentOrchestrator`` (Plan 021 / cierre del 018). Es un MIXIN: estos
helpers siguen el patron "intentar ``self._modules[X]``, caer a un fallback si no esta o
levanta". Operan sobre ``self._modules``/``self.config``/``self._get_intelligence_hub`` del
orchestrator via herencia. Sigue el patron de ``ExecutionStrategiesMixin``. No tiene estado
propio.

Metodos: ``_predict_risk``, ``_assess_confidence``, ``_generate_suggestions`` (fase de
analisis) y ``_detect_emotion``, ``_score_quality``, ``_reflect``, ``_extract_learnings``,
``_generate_explanation``, ``_attempt_recovery`` (fase de post-ejecucion).
"""

from __future__ import annotations

import logging
from typing import Any

from .heuristics import heuristic_confidence, heuristic_risk
from .models import ExecutionStep, TaskAnalysis

logger = logging.getLogger("antigravity.orchestrator.modules")


class ModuleBackedMixin:
    """Helpers backed por ``self._modules`` (opera sobre ``self`` del host)."""

    async def _predict_risk(self, task: str, context: dict) -> float:
        """Predict risk level using predictive escalation module."""
        if "escalation" in self._modules and self._modules["escalation"]:
            try:
                prediction = await self._modules["escalation"].predict(task, context)
                return prediction.risk_score if hasattr(prediction, "risk_score") else 0.5
            except Exception:
                logger.exception(
                    "Error in escalation module for task %s",
                    task.get("id") if isinstance(task, dict) else str(task),
                )

        # Fallback heuristic
        return heuristic_risk(task)

    async def _assess_confidence(self, task: str, domains: list[str]) -> float:
        """Assess confidence using metacognition module."""
        if "metacognition" in self._modules and self._modules["metacognition"]:
            try:
                assessment = await self._modules["metacognition"].assess(task)
                return assessment.confidence if hasattr(assessment, "confidence") else 0.7
            except Exception:
                logger.exception(
                    "Error in metacognition assessment for task %s",
                    task[:50] if isinstance(task, str) else str(task),
                )

        # Fallback: higher confidence for familiar domains
        return heuristic_confidence(domains)

    async def _generate_suggestions(self, task: str, context: dict) -> list[str]:
        """Generate proactive suggestions."""
        if "suggester" in self._modules and self._modules["suggester"]:
            try:
                suggestions = await self._modules["suggester"].suggest(task, context)
                return [s.text if hasattr(s, "text") else str(s) for s in suggestions[:3]]
            except Exception:
                logger.exception("Error in suggester suggest")
        return []

    async def _detect_emotion(self, text: str) -> dict | None:
        """Detect emotion in text."""
        if "emotion" in self._modules and self._modules["emotion"]:
            try:
                result = await self._modules["emotion"].detect(text)
                return result.to_dict() if hasattr(result, "to_dict") else {"emotion": "neutral"}
            except Exception:
                logger.exception("Error in emotion detection for text (len=%d)", len(text))
        return None

    async def _score_quality(self, output: Any, task: str) -> float:
        """Score output quality."""
        if "quality" in self._modules and self._modules["quality"]:
            try:
                result = await self._modules["quality"].score(str(output), task)
                return result.score if hasattr(result, "score") else 0.7
            except Exception:
                logger.exception("Error in quality scoring")
        return 0.7

    async def _reflect(self, output: Any, task: str, analysis: TaskAnalysis) -> dict | None:
        """Reflect on output."""
        if "reflection" in self._modules and self._modules["reflection"]:
            try:
                result = await self._modules["reflection"].reflect(str(output), task)
                return result.to_dict() if hasattr(result, "to_dict") else None
            except Exception:
                logger.exception("Error in reflection reflect")
        return None

    async def _extract_learnings(
        self, task: str, output: Any, analysis: TaskAnalysis, steps: list[ExecutionStep]
    ) -> list[str]:
        """Extract learnings from execution."""
        learnings = []

        # Strategy effectiveness
        learnings.append(
            f"Strategy '{analysis.recommended_strategy.value}' used for {analysis.complexity.value} task"
        )

        # Domain insights
        if analysis.domains:
            learnings.append(f"Domains involved: {', '.join(analysis.domains)}")

        # Step analysis
        successful_steps = sum(1 for s in steps if s.status == "completed")
        learnings.append(f"{successful_steps}/{len(steps)} steps completed successfully")

        # Risk handling
        if analysis.risk_level > 0.5:
            learnings.append(f"High-risk task (risk={analysis.risk_level:.2f}) handled")

        return learnings

    async def _generate_explanation(
        self, task: str, analysis: TaskAnalysis, steps: list[ExecutionStep], output: Any
    ) -> str:
        """Generate human-readable explanation."""
        if "explainer" in self._modules and self._modules["explainer"]:
            try:
                result = await self._modules["explainer"].explain(
                    {
                        "task": task,
                        "strategy": analysis.recommended_strategy.value,
                        "steps": len(steps),
                    }
                )
                return str(result)
            except Exception:
                logger.exception("Error in explainer explain")

        return (
            f"Task analyzed as {analysis.complexity.value} complexity with "
            f"{len(analysis.domains)} domain(s). Used {analysis.recommended_strategy.value} "
            f"strategy with {len(steps)} execution steps."
        )

    async def _attempt_recovery(self, task: str, error: str, context: dict) -> dict | None:
        """Attempt to recover from error."""
        if "recovery" in self._modules and self._modules["recovery"]:
            try:
                result = await self._modules["recovery"].recover(error, context)
                return result.to_dict() if hasattr(result, "to_dict") else None
            except Exception:
                logger.exception("Error in recovery module")
        return None
