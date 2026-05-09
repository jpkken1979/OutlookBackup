#!/usr/bin/env python3
"""
AutoTune — Adaptive Parameter Optimization Engine.

Classifies conversation context and automatically optimizes LLM parameters
(temperature, top_p, top_k, max_tokens) based on the type of request.

Features:
- Pattern-based context classification (8 categories)
- Per-category optimal parameter profiles
- Feedback loop with exponential moving average
- Usage statistics and category distribution tracking

Usage:
    from .agent.core.autotune import AutoTuneEngine

    engine = AutoTuneEngine()
    profile = engine.tune([
        {"role": "user", "content": "Write a Python class for authentication"}
    ])

    print(f"Category: {profile.category.value}")
    print(f"Temperature: {profile.temperature}")
    print(f"Confidence: {profile.confidence:.0%}")
"""

import logging
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.core.autotune")

__all__ = [
    "AutoTuneEngine",
    "ContextCategory",
    "TuneProfile",
    "CategoryDefaults",
]


# ---------------------------------------------------------------------------
# Enums & data structures
# ---------------------------------------------------------------------------


class ContextCategory(str, Enum):
    """Categories for conversation context classification."""

    CODE = "code"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    CONVERSATIONAL = "conversational"
    TECHNICAL_DOCS = "technical_docs"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    UNS_ENTERPRISE = "uns_enterprise"


@dataclass
class CategoryDefaults:
    """Default LLM parameters for a context category.

    Attributes:
        temperature: Sampling temperature.
        top_p: Nucleus sampling probability mass.
        top_k: Top-k token filtering.
        max_tokens: Maximum tokens to generate.
    """

    temperature: float
    top_p: float
    top_k: int
    max_tokens: int


@dataclass
class TuneProfile:
    """Optimized parameter profile returned by the engine.

    Attributes:
        category: Detected context category.
        temperature: Recommended sampling temperature.
        top_p: Recommended nucleus sampling value.
        top_k: Recommended top-k value.
        max_tokens: Recommended max tokens.
        confidence: Classification confidence (0-1).
        reasoning: Human-readable explanation of classification.
        detected_patterns: List of pattern names that fired.
    """

    category: ContextCategory
    temperature: float
    top_p: float
    top_k: int
    max_tokens: int
    confidence: float
    reasoning: str
    detected_patterns: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to a plain dictionary.

        Returns:
            Dictionary representation of the profile.
        """
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class FeedbackEntry:
    """A single feedback record for parameter adjustment.

    Attributes:
        category: The context category that was used.
        rating: User satisfaction rating (0.0 to 1.0).
        temperature: Temperature used when the rating was given.
        top_p: top_p used when the rating was given.
        top_k: top_k used when the rating was given.
        timestamp: ISO-format timestamp of the feedback.
    """

    category: ContextCategory
    rating: float
    temperature: float
    top_p: float
    top_k: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Each entry maps a ContextCategory to a list of compiled regex patterns.
# Patterns are case-insensitive and match against the concatenated message text.

_PATTERN_DEFS: dict[ContextCategory, list[tuple[str, re.Pattern[str]]]] = {
    ContextCategory.CODE: [
        ("import_statement", re.compile(r"(?:^|\n)\s*(?:import |from \S+ import )", re.IGNORECASE)),
        ("function_def", re.compile(r"(?:^|\n)\s*(?:def |async def |function\s)", re.IGNORECASE)),
        ("class_def", re.compile(r"(?:^|\n)\s*class\s+\w+", re.IGNORECASE)),
        ("variable_assignment", re.compile(r"(?:^|\n)\s*\w+\s*[:=]\s*", re.IGNORECASE)),
        ("code_brackets", re.compile(r"[{}\[\]();]", re.IGNORECASE)),
        (
            "programming_keywords",
            re.compile(
                r"\b(?:return|if|else|elif|for|while|try|except|catch|throw|"
                r"const|let|var|public|private|static|void|int|str|bool|float|"
                r"async|await|yield|lambda|interface|struct|enum)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "code_request",
            re.compile(
                r"\b(?:implement|refactor|debug|compile|runtime|syntax|"
                r"algorithm|API|endpoint|function|method|class|module|"
                r"test|unit test|integration test|bug|fix|error|exception)\b",
                re.IGNORECASE,
            ),
        ),
    ],
    ContextCategory.CREATIVE: [
        (
            "creative_verbs",
            re.compile(
                r"\b(?:story|poem|write|imagine|create|fiction|narrative|"
                r"character|plot|scene|dialogue|creative|fantasy|novel|"
                r"compose|invent|dream|brainstorm|ideate)\b",
                re.IGNORECASE,
            ),
        ),
    ],
    ContextCategory.ANALYTICAL: [
        (
            "analysis_keywords",
            re.compile(
                r"\b(?:analyze|analyse|compare|evaluate|pros\s*(?:/|and)\s*cons|"
                r"statistics|statistic|data|metrics|metric|benchmark|"
                r"assessment|trade-?off|cost-?benefit|risk|advantage|"
                r"disadvantage|correlation|trend|insight|findings)\b",
                re.IGNORECASE,
            ),
        ),
    ],
    ContextCategory.TECHNICAL_DOCS: [
        (
            "docs_keywords",
            re.compile(
                r"\b(?:document(?:ation)?|API\s*(?:reference|spec)|"
                r"specification|schema|endpoint|swagger|openapi|"
                r"reference\s*guide|technical\s*(?:writing|manual)|"
                r"readme|changelog|architecture\s*(?:doc|diagram))\b",
                re.IGNORECASE,
            ),
        ),
    ],
    ContextCategory.TRANSLATION: [
        (
            "translation_keywords",
            re.compile(
                r"\b(?:translate|traducir|traduire|翻訳|翻译|übersetzen|"
                r"convert\s+to|en\s+español|in\s+english|in\s+japanese|"
                r"en\s+français|auf\s+deutsch|to\s+(?:spanish|english|"
                r"japanese|french|german|chinese|korean|portuguese))\b",
                re.IGNORECASE,
            ),
        ),
    ],
    ContextCategory.SUMMARIZATION: [
        (
            "summarization_keywords",
            re.compile(
                r"\b(?:summarize|summarise|summary|resumen|resumir|"
                r"tl;?\s*dr|key\s*points|brief\s*overview|recap|"
                r"condense|abstract|digest|synopsis|outline\s*of|"
                r"main\s*(?:ideas|takeaways|points))\b",
                re.IGNORECASE,
            ),
        ),
    ],
    ContextCategory.UNS_ENTERPRISE: [
        (
            "uns_japanese",
            re.compile(
                r"(?:派遣|給与|勤怠|契約|社員|労働者|有給|残業|"
                r"シフト|出勤|退勤|勤務|請求|納品|受注|発注|"
                r"人材|採用|雇用|解雇|就業)"
            ),
        ),
        (
            "uns_spanish",
            re.compile(
                r"\b(?:nómina|dispatch|haken|planilla|contrato\s*laboral|"
                r"asistencia|turno|jornada|empresa\s*de\s*despacho)\b",
                re.IGNORECASE,
            ),
        ),
    ],
}

# ---------------------------------------------------------------------------
# Default parameter profiles per category
# ---------------------------------------------------------------------------

_CATEGORY_DEFAULTS: dict[ContextCategory, CategoryDefaults] = {
    ContextCategory.CODE: CategoryDefaults(temperature=0.15, top_p=0.8, top_k=25, max_tokens=4096),
    ContextCategory.CREATIVE: CategoryDefaults(
        temperature=0.9, top_p=0.95, top_k=80, max_tokens=4096
    ),
    ContextCategory.ANALYTICAL: CategoryDefaults(
        temperature=0.4, top_p=0.85, top_k=40, max_tokens=4096
    ),
    ContextCategory.CONVERSATIONAL: CategoryDefaults(
        temperature=0.7, top_p=0.9, top_k=60, max_tokens=2048
    ),
    ContextCategory.TECHNICAL_DOCS: CategoryDefaults(
        temperature=0.3, top_p=0.85, top_k=35, max_tokens=4096
    ),
    ContextCategory.TRANSLATION: CategoryDefaults(
        temperature=0.2, top_p=0.8, top_k=30, max_tokens=4096
    ),
    ContextCategory.SUMMARIZATION: CategoryDefaults(
        temperature=0.3, top_p=0.8, top_k=30, max_tokens=2048
    ),
    ContextCategory.UNS_ENTERPRISE: CategoryDefaults(
        temperature=0.2, top_p=0.8, top_k=25, max_tokens=4096
    ),
}

# Model-specific max_tokens overrides (larger models can handle more)
_MODEL_TOKEN_OVERRIDES: dict[str, int] = {
    "gpt-4": 8192,
    "gpt-4o": 16384,
    "gpt-4-turbo": 16384,
    "claude-3-opus": 4096,
    "claude-3-sonnet": 4096,
    "claude-3-haiku": 4096,
    "claude-opus-4": 16384,
    "claude-sonnet-4": 8192,
}

# Maximum feedback entries to keep per category
_MAX_FEEDBACK_HISTORY = 100

# EMA smoothing factor for feedback-based parameter adjustment
_EMA_ALPHA = 0.1


# ---------------------------------------------------------------------------
# AutoTuneEngine
# ---------------------------------------------------------------------------


class AutoTuneEngine:
    """Adaptive parameter optimization engine.

    Classifies conversation context using pattern detection and
    adjusts LLM parameters for optimal response quality.

    The engine maintains per-category parameter adjustments learned
    from user feedback via exponential moving average (EMA).

    Attributes:
        feedback_history: Per-category deque of recent feedback entries.
        category_counts: Running count of classifications per category.
        adjustments: Per-category parameter deltas learned from feedback.
    """

    def __init__(self) -> None:
        """Initialize pattern matchers, feedback history, and adjustment state."""
        self.feedback_history: dict[ContextCategory, deque[FeedbackEntry]] = {
            cat: deque(maxlen=_MAX_FEEDBACK_HISTORY) for cat in ContextCategory
        }
        self.category_counts: dict[ContextCategory, int] = dict.fromkeys(ContextCategory, 0)
        self.adjustments: dict[ContextCategory, dict[str, float]] = {
            cat: {"temperature": 0.0, "top_p": 0.0, "top_k": 0.0} for cat in ContextCategory
        }
        logger.info("AutoTuneEngine initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, messages: list[dict[str, str]]) -> ContextCategory:
        """Classify conversation context from message history.

        Scans messages for known patterns and returns the best-matching
        context category. Falls back to ``CONVERSATIONAL`` when no
        strong signal is detected.

        Args:
            messages: List of message dicts with ``role`` and ``content`` keys.

        Returns:
            The detected ContextCategory.
        """
        scores = self._score_patterns(messages)
        if not scores:
            return ContextCategory.CONVERSATIONAL

        best_category = max(scores, key=scores.get)  # type: ignore[arg-type]
        if scores[best_category] == 0:
            return ContextCategory.CONVERSATIONAL

        return best_category

    def tune(self, messages: list[dict[str, str]], model: str = "") -> TuneProfile:
        """Get optimized parameters for the given context.

        Combines default category parameters with learned adjustments
        from prior feedback. Optionally adjusts ``max_tokens`` based
        on the target model.

        Args:
            messages: List of message dicts with ``role`` and ``content`` keys.
            model: Optional model identifier for token-limit overrides.

        Returns:
            A ``TuneProfile`` with recommended parameters.
        """
        scores = self._score_patterns(messages)
        category, confidence, matched_patterns = self._pick_category(scores)

        # Update usage counter
        self.category_counts[category] += 1

        # Start from defaults
        defaults = _CATEGORY_DEFAULTS[category]
        temperature = defaults.temperature
        top_p = defaults.top_p
        top_k = defaults.top_k
        max_tokens = defaults.max_tokens

        # Apply learned adjustments
        adj = self.adjustments[category]
        temperature = self._clamp(temperature + adj["temperature"], 0.0, 2.0)
        top_p = self._clamp(top_p + adj["top_p"], 0.0, 1.0)
        top_k = max(1, int(top_k + adj["top_k"]))

        # Model-specific max_tokens override
        if model:
            for model_prefix, token_limit in _MODEL_TOKEN_OVERRIDES.items():
                if model_prefix in model.lower():
                    max_tokens = min(max_tokens, token_limit)
                    break

        reasoning = self._build_reasoning(category, matched_patterns, confidence)

        profile = TuneProfile(
            category=category,
            temperature=round(temperature, 4),
            top_p=round(top_p, 4),
            top_k=top_k,
            max_tokens=max_tokens,
            confidence=round(confidence, 4),
            reasoning=reasoning,
            detected_patterns=matched_patterns,
        )

        logger.info(
            "AutoTune: category=%s confidence=%.2f temperature=%.3f top_p=%.3f top_k=%d",
            category.value,
            confidence,
            profile.temperature,
            profile.top_p,
            profile.top_k,
        )
        return profile

    def apply_feedback(self, profile: TuneProfile, rating: float) -> None:
        """Apply user feedback to improve future tuning via exponential moving average.

        A rating above 0.5 reinforces the current parameters; a rating
        below 0.5 nudges them toward the category defaults.

        Args:
            profile: The TuneProfile that was used for generation.
            rating: User satisfaction score in the range [0.0, 1.0].

        Raises:
            ValueError: If rating is outside [0.0, 1.0].
        """
        if not 0.0 <= rating <= 1.0:
            raise ValueError(f"Rating must be between 0.0 and 1.0, got {rating}")

        entry = FeedbackEntry(
            category=profile.category,
            rating=rating,
            temperature=profile.temperature,
            top_p=profile.top_p,
            top_k=profile.top_k,
        )
        self.feedback_history[profile.category].append(entry)

        # Compute direction: positive rating reinforces, negative corrects
        # toward defaults
        defaults = _CATEGORY_DEFAULTS[profile.category]
        direction = rating - 0.5  # range [-0.5, 0.5]

        adj = self.adjustments[profile.category]

        if direction >= 0:
            # Good feedback — reinforce current deviation from defaults
            delta_t = profile.temperature - defaults.temperature
            delta_p = profile.top_p - defaults.top_p
            delta_k = float(profile.top_k - defaults.top_k)
            adj["temperature"] += _EMA_ALPHA * delta_t * direction * 2
            adj["top_p"] += _EMA_ALPHA * delta_p * direction * 2
            adj["top_k"] += _EMA_ALPHA * delta_k * direction * 2
        else:
            # Poor feedback — decay adjustments toward zero (back to defaults)
            adj["temperature"] *= 1.0 - _EMA_ALPHA
            adj["top_p"] *= 1.0 - _EMA_ALPHA
            adj["top_k"] *= 1.0 - _EMA_ALPHA

        logger.info(
            "AutoTune feedback: category=%s rating=%.2f adj_temp=%.4f adj_top_p=%.4f adj_top_k=%.1f",
            profile.category.value,
            rating,
            adj["temperature"],
            adj["top_p"],
            adj["top_k"],
        )

    def get_stats(self) -> dict[str, Any]:
        """Return tuning statistics and category distribution.

        Returns:
            Dictionary with ``total_classifications``, ``category_distribution``,
            ``feedback_counts``, ``average_ratings``, and ``current_adjustments``.
        """
        total = sum(self.category_counts.values())
        distribution: dict[str, float] = {}
        if total > 0:
            distribution = {
                cat.value: round(count / total, 4)
                for cat, count in self.category_counts.items()
                if count > 0
            }

        feedback_counts: dict[str, int] = {}
        average_ratings: dict[str, float] = {}
        for cat in ContextCategory:
            history = self.feedback_history[cat]
            if history:
                feedback_counts[cat.value] = len(history)
                avg = sum(e.rating for e in history) / len(history)
                average_ratings[cat.value] = round(avg, 4)

        current_adjustments: dict[str, dict[str, float]] = {
            cat.value: {k: round(v, 4) for k, v in adj.items()}
            for cat, adj in self.adjustments.items()
            if any(abs(v) > 1e-6 for v in adj.values())
        }

        return {
            "total_classifications": total,
            "category_distribution": distribution,
            "feedback_counts": feedback_counts,
            "average_ratings": average_ratings,
            "current_adjustments": current_adjustments,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_patterns(self, messages: list[dict[str, str]]) -> dict[ContextCategory, int]:
        """Score each category by counting pattern matches across messages.

        Args:
            messages: Conversation message list.

        Returns:
            Mapping of category to total match count.
        """
        text = self._extract_text(messages)
        scores: dict[ContextCategory, int] = dict.fromkeys(ContextCategory, 0)

        for category, patterns in _PATTERN_DEFS.items():
            for _name, regex in patterns:
                matches = regex.findall(text)
                scores[category] += len(matches)

        return scores

    def _pick_category(
        self, scores: dict[ContextCategory, int]
    ) -> tuple[ContextCategory, float, list[str]]:
        """Select the winning category and compute confidence.

        Args:
            scores: Per-category pattern match counts.

        Returns:
            Tuple of (winning category, confidence 0-1, list of matched pattern names).
        """
        total_matches = sum(scores.values())
        if total_matches == 0:
            return ContextCategory.CONVERSATIONAL, 0.5, []

        best_category = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_category]

        if best_score == 0:
            return ContextCategory.CONVERSATIONAL, 0.5, []

        # Confidence: proportion of matches belonging to the winner,
        # scaled into [0.5, 1.0] range.
        raw_confidence = best_score / total_matches
        confidence = 0.5 + 0.5 * raw_confidence

        # Collect which patterns fired for the winner
        matched_patterns: list[str] = []
        for category, patterns in _PATTERN_DEFS.items():
            if category != best_category:
                continue
            for name, regex in patterns:
                # We just need to know if it matched at all
                if name not in matched_patterns:
                    matched_patterns.append(name)

        return best_category, round(confidence, 4), matched_patterns

    @staticmethod
    def _extract_text(messages: list[dict[str, str]]) -> str:
        """Concatenate message contents into a single string for scanning.

        Args:
            messages: Conversation message list.

        Returns:
            Single string with all message content joined by newlines.
        """
        parts: list[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if content:
                parts.append(content)
        return "\n".join(parts)

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        """Clamp a value to the [lo, hi] range.

        Args:
            value: Value to clamp.
            lo: Lower bound.
            hi: Upper bound.

        Returns:
            Clamped value.
        """
        return max(lo, min(hi, value))

    @staticmethod
    def _build_reasoning(
        category: ContextCategory,
        patterns: list[str],
        confidence: float,
    ) -> str:
        """Build a human-readable reasoning string.

        Args:
            category: The detected category.
            patterns: Names of patterns that matched.
            confidence: Classification confidence.

        Returns:
            Explanation string.
        """
        if not patterns:
            return (
                f"Classified as {category.value} (default fallback, "
                f"confidence={confidence:.0%}). No strong patterns detected."
            )
        pattern_list = ", ".join(patterns)
        return (
            f"Classified as {category.value} (confidence={confidence:.0%}) "
            f"based on detected patterns: {pattern_list}."
        )
