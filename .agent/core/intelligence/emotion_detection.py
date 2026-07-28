# mypy: ignore-errors
#!/usr/bin/env python3
"""
Emotion Detection - Detects user frustration/satisfaction from input.

This module provides emotion analysis that:
1. Analyzes text for emotional signals
2. Detects frustration, satisfaction, confusion
3. Tracks emotion trends over conversation
4. Suggests response adaptations
5. Enables empathetic agent behavior

Usage:
    from .agent.core.intelligence import EmotionDetector, detect_emotion

    detector = EmotionDetector()

    # Analyze a message
    result = await detector.analyze(
        text="This is really frustrating, nothing is working!",
        context={"previous_messages": 3}
    )

    print(f"Emotion: {result.primary_emotion}")
    print(f"Frustration level: {result.frustration_level:.0%}")
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.emotion_detection")


class Emotion(Enum):
    """Primary emotions to detect."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SATISFIED = "satisfied"
    CURIOUS = "curious"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    DISAPPOINTED = "disappointed"
    ANXIOUS = "anxious"
    EXCITED = "excited"


class EmotionIntensity(Enum):
    """Intensity levels."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class EmotionSignal:
    """A detected emotional signal."""

    signal_type: str
    emotion: Emotion
    strength: float  # 0.0 to 1.0
    evidence: str
    offset: int = 0  # Position in text

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "emotion": self.emotion.value,
            "strength": self.strength,
            "evidence": self.evidence,
        }


@dataclass
class EmotionAnalysis:
    """Result of emotion analysis."""

    primary_emotion: Emotion
    intensity: EmotionIntensity
    confidence: float
    frustration_level: float  # 0.0 to 1.0
    satisfaction_level: float  # 0.0 to 1.0
    signals: list[EmotionSignal]
    sentiment_score: float  # -1.0 (negative) to 1.0 (positive)
    urgency_level: float  # 0.0 to 1.0
    needs_attention: bool
    suggested_tone: str
    suggested_actions: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_emotion": self.primary_emotion.value,
            "intensity": self.intensity.value,
            "confidence": self.confidence,
            "frustration_level": self.frustration_level,
            "satisfaction_level": self.satisfaction_level,
            "signals": [s.to_dict() for s in self.signals],
            "sentiment_score": self.sentiment_score,
            "urgency_level": self.urgency_level,
            "needs_attention": self.needs_attention,
            "suggested_tone": self.suggested_tone,
            "suggested_actions": self.suggested_actions,
        }


class TextAnalyzer:
    """Analyzes text for emotional signals."""

    def __init__(self):
        self.emotion_patterns = self._initialize_patterns()
        self.intensifiers = self._initialize_intensifiers()
        self.negation_words = {
            "not",
            "no",
            "never",
            "don't",
            "doesn't",
            "didn't",
            "won't",
            "can't",
            "isn't",
        }

    def _initialize_patterns(self) -> dict[Emotion, list[dict[str, Any]]]:
        """Initialize emotion detection patterns."""
        return {
            Emotion.FRUSTRATED: [
                {"pattern": r"\b(frustrat\w*|annoy\w*|irritat\w*)\b", "weight": 0.8},
                {"pattern": r"\b(not working|doesn't work|won't work)\b", "weight": 0.7},
                {"pattern": r"\b(broken|failed|error)\b", "weight": 0.5},
                {"pattern": r"\b(stuck|blocked|can't)\b", "weight": 0.5},
                {"pattern": r"\bugh\b|\bargh\b|\bgrr\b", "weight": 0.7},
                {"pattern": r"[!?]{2,}", "weight": 0.4},  # Multiple punctuation
                {"pattern": r"\bstill\b.*\bnot\b", "weight": 0.6},
                {"pattern": r"\bagain\b", "weight": 0.3},
            ],
            Emotion.ANGRY: [
                {"pattern": r"\b(angry|mad|furious|livid)\b", "weight": 0.9},
                {"pattern": r"\b(hate|terrible|awful|worst)\b", "weight": 0.7},
                {"pattern": r"\b(ridiculous|absurd|stupid)\b", "weight": 0.6},
                {"pattern": r"[!]{3,}", "weight": 0.6},  # Multiple exclamations
                {"pattern": r"\bwhat the\b", "weight": 0.5},
            ],
            Emotion.CONFUSED: [
                {"pattern": r"\b(confus\w*|unclear|don't understand)\b", "weight": 0.8},
                {"pattern": r"\b(what|how|why)\b.*\?", "weight": 0.4},
                {"pattern": r"\b(lost|puzzled|bewildered)\b", "weight": 0.7},
                {"pattern": r"\b(huh|hmm|eh)\b\??", "weight": 0.5},
                {"pattern": r"\?{2,}", "weight": 0.5},  # Multiple question marks
            ],
            Emotion.SATISFIED: [
                {"pattern": r"\b(thank|thanks|thx)\b", "weight": 0.7},
                {"pattern": r"\b(great|excellent|perfect|awesome)\b", "weight": 0.8},
                {"pattern": r"\b(works|working|solved)\b", "weight": 0.6},
                {"pattern": r"\b(helped|helpful)\b", "weight": 0.7},
                {"pattern": r"\b(nice|good job|well done)\b", "weight": 0.7},
            ],
            Emotion.HAPPY: [
                {"pattern": r"\b(happy|glad|pleased|delighted)\b", "weight": 0.8},
                {"pattern": r"\b(love|amazing|wonderful)\b", "weight": 0.7},
                {"pattern": r"[!]+\s*$", "weight": 0.3},  # Exclamation at end (mild)
                {"pattern": r":[\)D]|😊|😄|🎉", "weight": 0.7},
            ],
            Emotion.EXCITED: [
                {"pattern": r"\b(excit\w*|can't wait|eager)\b", "weight": 0.8},
                {"pattern": r"\b(wow|omg|yay)\b", "weight": 0.7},
                {"pattern": r"[!]{2,}", "weight": 0.5},
                {"pattern": r"🚀|🎉|💪|✨", "weight": 0.6},
            ],
            Emotion.ANXIOUS: [
                {"pattern": r"\b(worr\w*|anxious|nervous)\b", "weight": 0.8},
                {"pattern": r"\b(urgent|asap|deadline)\b", "weight": 0.6},
                {"pattern": r"\b(hope|hopefully|please)\b", "weight": 0.4},
                {"pattern": r"\b(afraid|scared|concern\w*)\b", "weight": 0.7},
            ],
            Emotion.DISAPPOINTED: [
                {"pattern": r"\b(disappoint\w*|letdown|let down)\b", "weight": 0.8},
                {"pattern": r"\b(expected|thought|hoped)\b.*\b(but|however)\b", "weight": 0.6},
                {"pattern": r"\b(unfortunately|sadly)\b", "weight": 0.6},
                {"pattern": r"😕|😞|:\(", "weight": 0.6},
            ],
            Emotion.CURIOUS: [
                {"pattern": r"\b(wonder\w*|curious|interest\w*)\b", "weight": 0.7},
                {"pattern": r"\b(how|why|what)\b.*\?", "weight": 0.4},
                {"pattern": r"\b(tell me|explain|elaborate)\b", "weight": 0.5},
                {"pattern": r"\b(could you|can you|would you)\b", "weight": 0.3},
            ],
        }

    def _initialize_intensifiers(self) -> dict[str, float]:
        """Initialize intensity modifiers."""
        return {
            # Strong intensifiers
            "very": 1.3,
            "really": 1.3,
            "extremely": 1.5,
            "incredibly": 1.5,
            "absolutely": 1.4,
            "completely": 1.4,
            "totally": 1.3,
            "so": 1.2,
            # Weak intensifiers
            "a bit": 0.7,
            "slightly": 0.7,
            "somewhat": 0.8,
            "kind of": 0.7,
            "a little": 0.7,
        }

    def analyze(self, text: str) -> list[EmotionSignal]:
        """Analyze text for emotional signals."""
        signals = []
        text_lower = text.lower()

        for emotion, patterns in self.emotion_patterns.items():
            for pattern_info in patterns:
                pattern = pattern_info["pattern"]
                base_weight = pattern_info["weight"]

                matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
                for match in matches:
                    # Check for intensifiers nearby
                    start = max(0, match.start() - 20)
                    prefix = text_lower[start : match.start()]

                    intensity_modifier = 1.0
                    for intensifier, modifier in self.intensifiers.items():
                        if intensifier in prefix:
                            intensity_modifier = modifier
                            break

                    # Check for negation
                    negated = any(neg in prefix for neg in self.negation_words)
                    if negated:
                        # Flip positive/negative emotions
                        if emotion in [Emotion.HAPPY, Emotion.SATISFIED, Emotion.EXCITED]:
                            emotion = Emotion.DISAPPOINTED
                            intensity_modifier *= 0.8

                    signals.append(
                        EmotionSignal(
                            signal_type="pattern_match",
                            emotion=emotion,
                            strength=min(1.0, base_weight * intensity_modifier),
                            evidence=match.group(0),
                            offset=match.start(),
                        )
                    )

        return signals


class ConversationTracker:
    """Tracks emotional state over a conversation."""

    def __init__(self):
        self.history: list[EmotionAnalysis] = []
        self.trend: str = "stable"  # improving, declining, stable

    def add_analysis(self, analysis: EmotionAnalysis) -> None:
        """Add an analysis to history."""
        self.history.append(analysis)
        self._update_trend()

    def _update_trend(self) -> None:
        """Update the emotional trend."""
        if len(self.history) < 2:
            self.trend = "stable"
            return

        recent = self.history[-3:]
        sentiments = [a.sentiment_score for a in recent]

        if len(sentiments) >= 2:
            change = sentiments[-1] - sentiments[0]
            if change > 0.2:
                self.trend = "improving"
            elif change < -0.2:
                self.trend = "declining"
            else:
                self.trend = "stable"

    def get_average_frustration(self) -> float:
        """Get average frustration level."""
        if not self.history:
            return 0.0
        return sum(a.frustration_level for a in self.history) / len(self.history)

    def get_recent_emotions(self, n: int = 3) -> list[Emotion]:
        """Get recent primary emotions."""
        return [a.primary_emotion for a in self.history[-n:]]


class EmotionDetector:
    """
    Detects emotions in user messages.

    This class:
    1. Analyzes text for emotional signals
    2. Calculates frustration/satisfaction levels
    3. Tracks emotion trends
    4. Suggests appropriate responses
    """

    # Thresholds
    FRUSTRATION_WARNING = 0.5
    FRUSTRATION_CRITICAL = 0.7
    NEEDS_ATTENTION_THRESHOLD = 0.6

    def __init__(self, memory_dir: Path | None = None):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_EMOTIONS_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_EMOTIONS_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "emotions"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.text_analyzer = TextAnalyzer()
        self.conversation_tracker = ConversationTracker()

    async def analyze(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> EmotionAnalysis:
        """
        Analyze text for emotions.

        Args:
            text: Text to analyze
            context: Additional context

        Returns:
            EmotionAnalysis with detected emotions
        """
        context = context or {}

        # Get emotional signals
        signals = self.text_analyzer.analyze(text)

        # Aggregate signals by emotion
        emotion_scores: dict[Emotion, float] = {}
        for signal in signals:
            if signal.emotion not in emotion_scores:
                emotion_scores[signal.emotion] = 0.0
            emotion_scores[signal.emotion] = max(emotion_scores[signal.emotion], signal.strength)

        # Determine primary emotion
        if emotion_scores:
            primary_emotion = max(emotion_scores, key=emotion_scores.get)
            max_score = emotion_scores[primary_emotion]
        else:
            primary_emotion = Emotion.NEUTRAL
            max_score = 0.0

        # Calculate intensity
        intensity = self._score_to_intensity(max_score)

        # Calculate frustration level
        frustration_level = self._calculate_frustration(signals, emotion_scores)

        # Calculate satisfaction level
        satisfaction_level = self._calculate_satisfaction(signals, emotion_scores)

        # Calculate sentiment score
        sentiment_score = self._calculate_sentiment(emotion_scores)

        # Calculate urgency
        urgency_level = self._calculate_urgency(signals, context, frustration_level)

        # Determine if needs attention
        needs_attention = (
            frustration_level >= self.NEEDS_ATTENTION_THRESHOLD
            or primary_emotion in [Emotion.ANGRY, Emotion.FRUSTRATED]
            or urgency_level > 0.7
        )

        # Get suggested tone and actions
        suggested_tone = self._suggest_tone(primary_emotion, frustration_level)
        suggested_actions = self._suggest_actions(
            primary_emotion, frustration_level, satisfaction_level
        )

        # Calculate confidence
        confidence = self._calculate_confidence(signals, max_score)

        analysis = EmotionAnalysis(
            primary_emotion=primary_emotion,
            intensity=intensity,
            confidence=confidence,
            frustration_level=frustration_level,
            satisfaction_level=satisfaction_level,
            signals=signals,
            sentiment_score=sentiment_score,
            urgency_level=urgency_level,
            needs_attention=needs_attention,
            suggested_tone=suggested_tone,
            suggested_actions=suggested_actions,
            metadata={
                "text_length": len(text),
                "signal_count": len(signals),
                "emotion_scores": {k.value: v for k, v in emotion_scores.items()},
            },
        )

        # Track in conversation
        self.conversation_tracker.add_analysis(analysis)

        logger.info(
            f"Emotion detected: {primary_emotion.value} "
            f"(frustration={frustration_level:.0%}, satisfaction={satisfaction_level:.0%})"
        )

        return analysis

    def _score_to_intensity(self, score: float) -> EmotionIntensity:
        """Convert score to intensity level."""
        if score >= 0.8:
            return EmotionIntensity.VERY_HIGH
        elif score >= 0.6:
            return EmotionIntensity.HIGH
        elif score >= 0.4:
            return EmotionIntensity.MODERATE
        elif score >= 0.2:
            return EmotionIntensity.LOW
        else:
            return EmotionIntensity.VERY_LOW

    def _calculate_frustration(
        self,
        signals: list[EmotionSignal],
        emotion_scores: dict[Emotion, float],
    ) -> float:
        """Calculate frustration level."""
        frustrating_emotions = [
            Emotion.FRUSTRATED,
            Emotion.ANGRY,
            Emotion.DISAPPOINTED,
            Emotion.CONFUSED,
        ]

        frustration = 0.0
        weights = {
            Emotion.ANGRY: 1.0,
            Emotion.FRUSTRATED: 0.9,
            Emotion.DISAPPOINTED: 0.6,
            Emotion.CONFUSED: 0.4,
        }

        for emotion in frustrating_emotions:
            if emotion in emotion_scores:
                weight = weights.get(emotion, 0.5)
                frustration = max(frustration, emotion_scores[emotion] * weight)

        # Boost if multiple frustrating signals
        frustrating_signals = [s for s in signals if s.emotion in frustrating_emotions]
        if len(frustrating_signals) > 2:
            frustration = min(1.0, frustration + 0.1)

        return frustration

    def _calculate_satisfaction(
        self,
        signals: list[EmotionSignal],
        emotion_scores: dict[Emotion, float],
    ) -> float:
        """Calculate satisfaction level."""
        positive_emotions = [
            Emotion.SATISFIED,
            Emotion.HAPPY,
            Emotion.EXCITED,
        ]

        satisfaction = 0.0
        for emotion in positive_emotions:
            if emotion in emotion_scores:
                satisfaction = max(satisfaction, emotion_scores[emotion])

        return satisfaction

    def _calculate_sentiment(
        self,
        emotion_scores: dict[Emotion, float],
    ) -> float:
        """Calculate overall sentiment (-1 to 1)."""
        positive_emotions = {
            Emotion.HAPPY: 1.0,
            Emotion.SATISFIED: 0.8,
            Emotion.EXCITED: 0.9,
            Emotion.CURIOUS: 0.3,
        }

        negative_emotions = {
            Emotion.ANGRY: -1.0,
            Emotion.FRUSTRATED: -0.8,
            Emotion.DISAPPOINTED: -0.6,
            Emotion.ANXIOUS: -0.4,
            Emotion.CONFUSED: -0.2,
        }

        sentiment = 0.0
        total_weight = 0.0

        for emotion, score in emotion_scores.items():
            if emotion in positive_emotions:
                sentiment += score * positive_emotions[emotion]
                total_weight += score
            elif emotion in negative_emotions:
                sentiment += score * negative_emotions[emotion]
                total_weight += score

        if total_weight > 0:
            return sentiment / total_weight
        return 0.0

    def _calculate_urgency(
        self,
        signals: list[EmotionSignal],
        context: dict[str, Any],
        frustration: float,
    ) -> float:
        """Calculate urgency level."""
        urgency = 0.0

        # Frustration adds urgency
        urgency += frustration * 0.5

        # Check for urgency signals
        anxious_signals = [s for s in signals if s.emotion == Emotion.ANXIOUS]
        if anxious_signals:
            urgency += 0.3

        # Context-based urgency
        if context.get("deadline"):
            urgency += 0.2
        if context.get("blocking"):
            urgency += 0.3

        return min(1.0, urgency)

    def _calculate_confidence(
        self,
        signals: list[EmotionSignal],
        max_score: float,
    ) -> float:
        """Calculate confidence in the analysis."""
        if not signals:
            return 0.3  # Low confidence without signals

        # Base confidence from signal strength
        confidence = 0.5 + max_score * 0.3

        # Bonus for multiple signals
        if len(signals) >= 3:
            confidence += 0.1
        elif len(signals) >= 2:
            confidence += 0.05

        # Bonus for consistent signals
        emotions = [s.emotion for s in signals]
        if len(set(emotions)) == 1:
            confidence += 0.1

        return min(0.95, confidence)

    def _suggest_tone(
        self,
        emotion: Emotion,
        frustration: float,
    ) -> str:
        """Suggest appropriate response tone."""
        if frustration >= self.FRUSTRATION_CRITICAL:
            return "empathetic and solution-focused"
        elif frustration >= self.FRUSTRATION_WARNING:
            return "understanding and helpful"
        elif emotion == Emotion.CONFUSED:
            return "clear and patient"
        elif emotion in [Emotion.HAPPY, Emotion.SATISFIED]:
            return "positive and encouraging"
        elif emotion == Emotion.EXCITED:
            return "enthusiastic and supportive"
        elif emotion == Emotion.ANXIOUS:
            return "reassuring and calm"
        elif emotion == Emotion.CURIOUS:
            return "informative and engaging"
        else:
            return "neutral and professional"

    def _suggest_actions(
        self,
        emotion: Emotion,
        frustration: float,
        satisfaction: float,
    ) -> list[str]:
        """Suggest actions based on emotional state."""
        actions = []

        if frustration >= self.FRUSTRATION_CRITICAL:
            actions.extend(
                [
                    "Acknowledge their frustration",
                    "Offer immediate, concrete help",
                    "Consider escalating to human if needed",
                ]
            )
        elif frustration >= self.FRUSTRATION_WARNING:
            actions.extend(
                [
                    "Show understanding",
                    "Focus on solutions",
                    "Provide clear next steps",
                ]
            )

        if emotion == Emotion.CONFUSED:
            actions.extend(
                [
                    "Provide clearer explanations",
                    "Use examples",
                    "Break down complex information",
                ]
            )

        if satisfaction >= 0.7:
            actions.extend(
                [
                    "Reinforce positive outcome",
                    "Offer additional help if needed",
                ]
            )

        if emotion == Emotion.ANXIOUS:
            actions.extend(
                [
                    "Provide reassurance",
                    "Set clear expectations",
                    "Offer timeline if applicable",
                ]
            )

        return actions[:4]

    def get_conversation_trend(self) -> str:
        """Get the emotional trend of the conversation."""
        return self.conversation_tracker.trend

    def get_average_frustration(self) -> float:
        """Get average frustration level."""
        return self.conversation_tracker.get_average_frustration()

    def reset_conversation(self) -> None:
        """Reset conversation tracking."""
        self.conversation_tracker = ConversationTracker()

    def export_report(self) -> str:
        """Export emotion analysis report as markdown."""
        lines = [
            "# Emotion Analysis Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Conversation Summary",
            "",
            f"- Messages analyzed: {len(self.conversation_tracker.history)}",
            f"- Overall trend: {self.conversation_tracker.trend}",
            f"- Average frustration: {self.get_average_frustration():.0%}",
            "",
        ]

        if self.conversation_tracker.history:
            lines.extend(
                [
                    "## Recent Emotions",
                    "",
                ]
            )

            for analysis in self.conversation_tracker.history[-5:]:
                lines.append(
                    f"- {analysis.primary_emotion.value} "
                    f"(frustration: {analysis.frustration_level:.0%}, "
                    f"confidence: {analysis.confidence:.0%})"
                )

        return "\n".join(lines)


# Convenience function
async def detect_emotion(
    text: str,
    context: dict[str, Any] | None = None,
) -> EmotionAnalysis:
    """Quick function to detect emotions."""
    detector = EmotionDetector()
    return await detector.analyze(text, context)
