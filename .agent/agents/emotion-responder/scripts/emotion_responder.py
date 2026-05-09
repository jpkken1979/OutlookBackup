#!/usr/bin/env python3
"""
Emotion Responder Agent.

Detects emotions and adapts responses for better user experience.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("emotion-responder")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class Emotion(Enum):
    """Detected emotions."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SATISFIED = "satisfied"
    EXCITED = "excited"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    STRESSED = "stressed"
    WORRIED = "worried"
    DISAPPOINTED = "disappointed"


class ResponseTone(Enum):
    """Response tone adaptations."""

    NEUTRAL = "neutral"
    SUPPORTIVE = "supportive"
    CELEBRATORY = "celebratory"
    CALMING = "calming"
    PATIENT = "patient"
    DIRECT = "direct"
    ENCOURAGING = "encouraging"
    EMPATHETIC = "empathetic"


@dataclass
class EmotionAnalysis:
    """Emotion analysis result."""

    primary_emotion: Emotion
    confidence: float
    intensity: float  # 0-1
    signals: list[str]
    secondary_emotions: list[Emotion]


@dataclass
class AdaptedResponse:
    """Response adapted to emotion."""

    original_message: str
    detected_emotion: Emotion
    emotion_confidence: float
    response_tone: ResponseTone
    adapted_response: str
    suggestions: list[str]
    follow_up: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "original_message": self.original_message,
            "detected_emotion": self.detected_emotion.value,
            "emotion_confidence": self.emotion_confidence,
            "response_tone": self.response_tone.value,
            "adapted_response": self.adapted_response,
            "suggestions": self.suggestions,
            "follow_up": self.follow_up,
            "metadata": self.metadata,
        }


class EmotionResponder:
    """
    Agent that detects emotions and adapts responses.

    Uses:
    - Emotion Detection module
    - Response tone mapping
    - Contextual adaptation
    """

    def __init__(self):
        self.response_history: list[AdaptedResponse] = []
        self._modules_loaded = False
        self._modules = {}

        # Emotion to tone mapping
        self.emotion_tone_map = {
            Emotion.NEUTRAL: ResponseTone.NEUTRAL,
            Emotion.HAPPY: ResponseTone.CELEBRATORY,
            Emotion.SATISFIED: ResponseTone.ENCOURAGING,
            Emotion.EXCITED: ResponseTone.CELEBRATORY,
            Emotion.CONFUSED: ResponseTone.PATIENT,
            Emotion.FRUSTRATED: ResponseTone.SUPPORTIVE,
            Emotion.ANGRY: ResponseTone.CALMING,
            Emotion.STRESSED: ResponseTone.CALMING,
            Emotion.WORRIED: ResponseTone.EMPATHETIC,
            Emotion.DISAPPOINTED: ResponseTone.ENCOURAGING,
        }

        # Tone templates
        self.tone_prefixes = {
            ResponseTone.NEUTRAL: "",
            ResponseTone.SUPPORTIVE: "I understand this can be challenging. ",
            ResponseTone.CELEBRATORY: "Great news! ",
            ResponseTone.CALMING: "Let's take this step by step. ",
            ResponseTone.PATIENT: "No worries, let me explain clearly. ",
            ResponseTone.DIRECT: "Here's what you need to do: ",
            ResponseTone.ENCOURAGING: "You're making good progress. ",
            ResponseTone.EMPATHETIC: "I can see this is important to you. ",
        }

    async def _load_modules(self):
        """Lazy load intelligence modules."""
        if self._modules_loaded:
            return

        try:
            from core.intelligence import EmotionDetector, ProactiveSuggester

            self._modules["emotion"] = EmotionDetector()
            self._modules["suggester"] = ProactiveSuggester()
            self._modules_loaded = True
        except ImportError as e:
            logger.warning(f"Could not load modules: {e}")
            self._modules_loaded = True

    def _detect_emotion_heuristic(self, message: str) -> EmotionAnalysis:
        """Heuristic emotion detection."""
        message_lower = message.lower()
        signals = []

        # Frustration signals
        frustration_keywords = [
            "not working",
            "doesn't work",
            "broken",
            "error",
            "failed",
            "why won't",
            "can't",
            "stuck",
            "help",
            "ugh",
            "again",
            "still not",
            "keeps failing",
            "frustrated",
            "annoying",
        ]

        # Confusion signals
        confusion_keywords = [
            "don't understand",
            "confused",
            "what does",
            "how do",
            "unclear",
            "lost",
            "not sure",
            "?",
            "explain",
            "meaning",
        ]

        # Happy signals
        happy_keywords = [
            "thanks",
            "great",
            "awesome",
            "perfect",
            "works",
            "excellent",
            "amazing",
            "love it",
            "wonderful",
            "!!",
        ]

        # Stressed signals
        stressed_keywords = [
            "urgent",
            "asap",
            "deadline",
            "hurry",
            "quickly",
            "critical",
            "emergency",
            "immediately",
            "now",
        ]

        # Count signals
        frustration_count = sum(1 for kw in frustration_keywords if kw in message_lower)
        confusion_count = sum(1 for kw in confusion_keywords if kw in message_lower)
        happy_count = sum(1 for kw in happy_keywords if kw in message_lower)
        stressed_count = sum(1 for kw in stressed_keywords if kw in message_lower)

        # Build signals list
        if frustration_count > 0:
            signals.append(f"Frustration indicators: {frustration_count}")
        if confusion_count > 0:
            signals.append(f"Confusion indicators: {confusion_count}")
        if happy_count > 0:
            signals.append(f"Positive indicators: {happy_count}")
        if stressed_count > 0:
            signals.append(f"Urgency indicators: {stressed_count}")

        # Determine primary emotion
        scores = {
            Emotion.FRUSTRATED: frustration_count * 2,
            Emotion.CONFUSED: confusion_count * 1.5,
            Emotion.HAPPY: happy_count * 1.5,
            Emotion.STRESSED: stressed_count * 2,
            Emotion.NEUTRAL: 1,  # Default baseline
        }

        # Check for angry (high frustration + caps/exclamation)
        if frustration_count > 2 or (message.isupper() and len(message) > 10):
            scores[Emotion.ANGRY] = frustration_count * 3

        primary = max(scores, key=scores.get)
        max_score = scores[primary]

        # Calculate confidence
        total_signals = sum(scores.values())
        confidence = min(max_score / (total_signals + 1), 0.95) if total_signals > 1 else 0.5

        # Calculate intensity
        intensity = min(max_score / 5, 1.0)

        # Secondary emotions
        secondary = [
            e
            for e, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if e != primary and s > 0
        ][:2]

        return EmotionAnalysis(
            primary_emotion=primary,
            confidence=confidence,
            intensity=intensity,
            signals=signals,
            secondary_emotions=secondary,
        )

    async def _detect_emotion(self, message: str) -> EmotionAnalysis:
        """Detect emotion using module or heuristic."""
        if "emotion" in self._modules and self._modules["emotion"]:
            try:
                result = await self._modules["emotion"].detect(message)
                return EmotionAnalysis(
                    primary_emotion=Emotion(
                        result.emotion.value if hasattr(result, "emotion") else "neutral"
                    ),
                    confidence=result.confidence if hasattr(result, "confidence") else 0.7,
                    intensity=result.intensity if hasattr(result, "intensity") else 0.5,
                    signals=result.signals if hasattr(result, "signals") else [],
                    secondary_emotions=[],
                )
            except Exception as e:
                logger.warning(f"Module detection failed: {e}")

        return self._detect_emotion_heuristic(message)

    def _select_tone(self, emotion: Emotion, intensity: float) -> ResponseTone:
        """Select appropriate response tone."""
        base_tone = self.emotion_tone_map.get(emotion, ResponseTone.NEUTRAL)

        # Adjust for intensity
        if intensity > 0.8 and emotion in [Emotion.FRUSTRATED, Emotion.ANGRY]:
            return ResponseTone.CALMING
        if intensity > 0.8 and emotion == Emotion.CONFUSED:
            return ResponseTone.PATIENT

        return base_tone

    def _adapt_message(self, content: str, tone: ResponseTone, emotion: Emotion) -> str:
        """Adapt message content for the tone."""
        prefix = self.tone_prefixes.get(tone, "")

        # Additional adaptations based on emotion
        if emotion == Emotion.CONFUSED:
            # Add clarity
            content = content.replace("you can", "here's how to")
            content = content.replace("simply", "")

        if emotion in [Emotion.FRUSTRATED, Emotion.ANGRY]:
            # Be more direct, less fluffy
            content = content.replace("you might want to", "please")
            content = content.replace("perhaps", "")
            content = content.replace("maybe", "")

        if emotion == Emotion.STRESSED:
            # Prioritize and simplify
            content = f"The most important thing right now: {content}"

        return f"{prefix}{content}"

    def _generate_suggestions(self, emotion: Emotion, context: dict | None) -> list[str]:
        """Generate suggestions based on emotion."""
        suggestions = []

        if emotion == Emotion.FRUSTRATED:
            suggestions = [
                "Would you like me to try a different approach?",
                "I can break this down into smaller steps",
                "Let me check for common issues",
            ]
        elif emotion == Emotion.CONFUSED:
            suggestions = [
                "I can provide a step-by-step walkthrough",
                "Would an example help clarify?",
                "Let me explain the concept differently",
            ]
        elif emotion == Emotion.HAPPY:
            suggestions = [
                "Ready for the next step?",
                "Would you like to explore advanced features?",
                "Should I document this solution?",
            ]
        elif emotion == Emotion.STRESSED:
            suggestions = [
                "Let's focus on the critical path",
                "I can help prioritize tasks",
                "Here's the quickest solution",
            ]
        else:
            suggestions = [
                "Let me know if you need more details",
                "I'm here to help with any questions",
            ]

        return suggestions[:3]

    def _generate_follow_up(self, emotion: Emotion) -> str:
        """Generate appropriate follow-up."""
        follow_ups = {
            Emotion.NEUTRAL: "Is there anything else you'd like help with?",
            Emotion.HAPPY: "Shall we continue to the next task?",
            Emotion.SATISFIED: "Ready when you are for the next step!",
            Emotion.CONFUSED: "Does this make more sense now? I'm happy to explain further.",
            Emotion.FRUSTRATED: "Did this help resolve the issue? I can try another approach if needed.",
            Emotion.ANGRY: "I hope this helps. Please let me know how else I can assist.",
            Emotion.STRESSED: "Is there anything urgent I should prioritize?",
            Emotion.WORRIED: "I'm here to help work through this. What concerns you most?",
            Emotion.DISAPPOINTED: "Let's see how we can improve this outcome together.",
            Emotion.EXCITED: "Great energy! What would you like to tackle next?",
        }
        return follow_ups.get(emotion, "How can I help further?")

    async def respond(
        self, message: str, content: str = "", context: dict | None = None
    ) -> AdaptedResponse:
        """
        Generate emotion-adapted response.

        Args:
            message: User's message to analyze
            content: Base response content to adapt
            context: Additional context

        Returns:
            Adapted response
        """
        await self._load_modules()
        context = context or {}

        # Detect emotion
        analysis = await self._detect_emotion(message)
        logger.info(
            f"Detected emotion: {analysis.primary_emotion.value} ({analysis.confidence:.0%})"
        )

        # Select tone
        tone = self._select_tone(analysis.primary_emotion, analysis.intensity)

        # Adapt response
        if not content:
            content = f"I understand you need help with: {message[:100]}..."

        adapted = self._adapt_message(content, tone, analysis.primary_emotion)

        # Generate suggestions
        suggestions = self._generate_suggestions(analysis.primary_emotion, context)

        # Generate follow-up
        follow_up = self._generate_follow_up(analysis.primary_emotion)

        result = AdaptedResponse(
            original_message=message,
            detected_emotion=analysis.primary_emotion,
            emotion_confidence=analysis.confidence,
            response_tone=tone,
            adapted_response=adapted,
            suggestions=suggestions,
            follow_up=follow_up,
            metadata={
                "intensity": analysis.intensity,
                "signals": analysis.signals,
                "secondary_emotions": [e.value for e in analysis.secondary_emotions],
            },
        )

        self.response_history.append(result)
        return result

    def get_emotion_stats(self) -> dict:
        """Get statistics on detected emotions."""
        if not self.response_history:
            return {"total": 0}

        emotion_counts = {}
        for response in self.response_history:
            emotion = response.detected_emotion.value
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        return {
            "total": len(self.response_history),
            "emotions": emotion_counts,
            "avg_confidence": sum(r.emotion_confidence for r in self.response_history)
            / len(self.response_history),
        }


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Emotion Responder Agent")
    parser.add_argument("message", nargs="?", help="User message to analyze")
    parser.add_argument("--response", help="Base response to adapt")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.message:
        # Interactive mode
        print("Emotion Responder - Enter messages to analyze (Ctrl+C to exit)")
        responder = EmotionResponder()
        try:
            while True:
                message = input("\n> ")
                result = await responder.respond(message)
                print(f"\n[{result.detected_emotion.value}] ({result.emotion_confidence:.0%})")
                print(f"Tone: {result.response_tone.value}")
                print(f"\n{result.adapted_response}")
                print("\nSuggestions:")
                for s in result.suggestions:
                    print(f"  - {s}")
                print(f"\n{result.follow_up}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
        return

    responder = EmotionResponder()
    result = await responder.respond(args.message, args.response or "")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(
            f"Detected Emotion: {result.detected_emotion.value} ({result.emotion_confidence:.0%})"
        )
        print(f"Response Tone: {result.response_tone.value}")
        print(f"\nAdapted Response:\n{result.adapted_response}")
        print("\nSuggestions:")
        for s in result.suggestions:
            print(f"  - {s}")
        print(f"\nFollow-up: {result.follow_up}")


if __name__ == "__main__":
    asyncio.run(main())
