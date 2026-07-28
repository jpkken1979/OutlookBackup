# mypy: ignore-errors
"""Intelligence Layer - Advanced cognitive capabilities for Antigravity agents.

Provides:
- Self-reflection: Evaluate outputs before returning
- Chain-of-thought: Explicit reasoning before action
- Multi-agent debate: Collaborative decision making
- Metacognition: Knowing what you don't know
- Error recovery: Automatic recovery from failures
- Quality scoring: Automated output evaluation
- Emotion detection: User emotion analysis
- Predictive escalation: Intelligent task escalation

This module integrates 27+ intelligence modules into a cohesive layer
for autonomous agent decision-making and reasoning.

Version: 4.1.0
"""

import importlib
import logging
from typing import Any

logger = logging.getLogger("antigravity.intelligence")


def _import_sibling_module(module_name: str) -> Any:
    """Imports a sibling module without relying on relative imports."""
    base_module = __name__.rpartition(".")[0]
    candidates = [f"{base_module}.{module_name}"] if base_module else []
    candidates.append(module_name)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return importlib.import_module(candidate)
        except Exception as error:
            last_error = error

    if last_error is not None:
        raise last_error
    raise ImportError(f"Unable to import sibling module: {module_name}")


class IntelligenceLayer:
    """
    Capa de inteligencia que proporciona capacidades cognitivas avanzadas.

    Integra los 27 módulos de inteligencia con la clase base de agentes:
    - FOUNDATION: SelfReflection, ChainOfThought, MultiAgentDebate, etc.
    - NIVEL 1: ToolLearning, SkillGenerator, PredictiveEscalation
    - NIVEL 2: AdversarialTesting, ExplainableDecisions, EmotionDetection
    - NIVEL 3: SkillComposition, DomainSpecialization, CollaborativeMemory
    """

    def __init__(self, agent_name: str, verbose: bool = False):
        self.agent_name = agent_name
        self.verbose = verbose
        self._initialized = False

        # Lazy-loaded modules
        self._reflection: Any | None = None
        self._chain_of_thought: Any | None = None
        self._debate: Any | None = None
        self._metacognition: Any | None = None
        self._quality_scorer: Any | None = None
        self._error_recovery: Any | None = None
        self._escalation: Any | None = None
        self._emotion_detector: Any | None = None

        logger.debug(f"IntelligenceLayer inicializada para {agent_name}")

    def _ensure_initialized(self) -> bool:
        """Inicializa los módulos de inteligencia bajo demanda."""
        if self._initialized:
            return True

        try:
            intelligence_module = _import_sibling_module("intelligence")

            ChainOfThought = intelligence_module.ChainOfThought
            EmotionDetector = intelligence_module.EmotionDetector
            ErrorRecovery = intelligence_module.ErrorRecovery
            Metacognition = intelligence_module.Metacognition
            MultiAgentDebate = intelligence_module.MultiAgentDebate
            PredictiveEscalation = intelligence_module.PredictiveEscalation
            QualityScorer = intelligence_module.QualityScorer
            SelfReflection = intelligence_module.SelfReflection

            self._reflection = SelfReflection()
            self._chain_of_thought = ChainOfThought()
            self._debate = MultiAgentDebate()
            self._metacognition = Metacognition()
            self._quality_scorer = QualityScorer()
            self._error_recovery = ErrorRecovery()
            self._escalation = PredictiveEscalation()
            self._emotion_detector = EmotionDetector()

            self._initialized = True
            logger.info(f"Módulos de inteligencia cargados para {self.agent_name}")
            return True

        except (ImportError, AttributeError) as e:
            # AttributeError: una capability esperada no esta expuesta por el modulo
            # `intelligence` (p.ej. removida o no re-exportada). Se degrada con gracia
            # —el layer queda desactivado— pero se loguea como error para no enmascarar
            # el problema (lo que ya nos costo un bug; ver bugfix_shu_deps_masked_bugs).
            logger.error(
                "No se pudieron cargar módulos de inteligencia para %s: %s",
                self.agent_name,
                e,
            )
            return False

    async def reflect(self, task: str, output: Any) -> Any | None:
        """
        Reflexiona sobre el output del agente antes de devolverlo.

        Args:
            task: La tarea que se ejecutó
            output: El resultado producido

        Returns:
            ReflectionResult con evaluación del output
        """
        if not self._ensure_initialized():
            return None

        try:
            result = await self._reflection.reflect(
                task=task, output=str(output), agent_name=self.agent_name
            )

            if self.verbose:
                logger.info(f"Reflexión: {result.summary}")

            return result

        except Exception as e:
            logger.error(f"Error en reflexión: {e}")
            return None

    async def reason(self, task: str, context: dict | None = None) -> Any | None:
        """
        Razonamiento paso a paso (Chain-of-Thought).

        Args:
            task: La tarea a razonar
            context: Contexto adicional

        Returns:
            ChainOfThoughtResult con pasos de razonamiento
        """
        if not self._ensure_initialized():
            return None

        try:
            agent_context = context or {}
            agent_context["agent_name"] = self.agent_name

            result = await self._chain_of_thought.reason(task=task, agent_context=agent_context)

            if self.verbose:
                logger.info(
                    f"Razonamiento: {len(result.steps)} pasos, confianza {result.overall_confidence:.2f}"
                )

            return result

        except Exception as e:
            logger.error(f"Error en razonamiento: {e}")
            return None

    async def debate(self, question: str, perspectives: list[str] | None = None) -> Any | None:
        """
        Debate multi-agente para decisiones críticas.

        Args:
            question: La pregunta o decisión a debatir
            perspectives: Perspectivas a considerar (default: arquitecto, seguridad, rendimiento)

        Returns:
            DebateResult con consenso y argumentos
        """
        if not self._ensure_initialized():
            return None

        try:
            perspectives = perspectives or ["architect", "security", "performance"]

            result = await self._debate.debate(question=question, perspectives=perspectives)

            if self.verbose:
                status = "alcanzado" if result.consensus_reached else "no alcanzado"
                logger.info(f"Debate: consenso {status}, confianza {result.confidence:.2f}")

            return result

        except Exception as e:
            logger.error(f"Error en debate: {e}")
            return None

    async def assess_confidence(self, task: str, output: Any) -> Any | None:
        """
        Evalúa la confianza en el resultado (metacognición).

        Args:
            task: La tarea ejecutada
            output: El resultado producido

        Returns:
            ConfidenceAssessment indicando qué tan seguro está el agente
        """
        if not self._ensure_initialized():
            return None

        try:
            result = await self._metacognition.assess(
                task=task, output=str(output), agent_name=self.agent_name
            )

            if self.verbose:
                logger.info(f"Metacognición: confianza {result.confidence:.2f}")

            return result

        except Exception as e:
            logger.error(f"Error en metacognición: {e}")
            return None

    async def score_quality(self, task: str, output: Any) -> Any | None:
        """
        Puntúa la calidad del output.

        Args:
            task: La tarea ejecutada
            output: El resultado a evaluar

        Returns:
            QualityScore con puntuación detallada
        """
        if not self._ensure_initialized():
            return None

        try:
            result = await self._quality_scorer.score(task=task, output=str(output))

            if self.verbose:
                logger.info(f"Calidad: {result.overall_score:.2f}/1.0")

            return result

        except Exception as e:
            logger.error(f"Error en scoring de calidad: {e}")
            return None

    async def recover_from_error(self, error: Exception, context: dict) -> Any | None:
        """
        Intenta recuperarse de un error automáticamente.

        Args:
            error: La excepción que ocurrió
            context: Contexto de ejecución

        Returns:
            RecoveryResult con estrategia de recuperación
        """
        if not self._ensure_initialized():
            return None

        try:
            result = await self._error_recovery.recover(
                error=error, context=context, agent_name=self.agent_name
            )

            if self.verbose:
                status = "exitosa" if result.recovered else "fallida"
                logger.info(f"Recuperación {status}: {result.strategy}")

            return result

        except Exception as e:
            logger.error(f"Error en recuperación: {e}")
            return None

    async def predict_escalation(self, task: str, signals: list[str]) -> Any | None:
        """
        Predice si una tarea necesita escalamiento.

        Args:
            task: La tarea actual
            signals: Señales de riesgo observadas

        Returns:
            EscalationPrediction indicando si escalar
        """
        if not self._ensure_initialized():
            return None

        try:
            result = await self._escalation.predict(
                task=task, signals=signals, agent_name=self.agent_name
            )

            if self.verbose:
                logger.info(
                    f"Escalamiento: nivel {result.level}, probabilidad {result.probability:.2f}"
                )

            return result

        except Exception as e:
            logger.error(f"Error en predicción de escalamiento: {e}")
            return None

    async def detect_emotion(self, text: str) -> Any | None:
        """
        Detecta el estado emocional del usuario.

        Args:
            text: Texto del usuario

        Returns:
            EmotionAnalysis con emociones detectadas
        """
        if not self._ensure_initialized():
            return None

        try:
            result = await self._emotion_detector.detect(text=text)

            if self.verbose:
                logger.info(f"Emoción detectada: {result.primary_emotion}")

            return result

        except Exception as e:
            logger.error(f"Error en detección de emoción: {e}")
            return None
