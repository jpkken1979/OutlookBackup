"""Skill Recommender module for Telegram intelligence.

Parses user intent from messages and recommends relevant skills
based on TF-IDF similarity, user skill level, and semantic matching.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


@dataclass
class SkillMatch:
    """Matched skill recommendation.

    Args:
        skill_name: Name of the skill.
        confidence: Confidence score (0-1).
        reasons: List of reasons why recommended.
        tier: Skill tier/difficulty level.
        prerequisites: Required prior knowledge.
    """

    skill_name: str
    confidence: float
    reasons: list[str]
    tier: str = "intermediate"
    prerequisites: list[str] = field(default_factory=list)


class IntentParser:
    """Parses user intent from natural language messages."""

    INTENT_PATTERNS: dict[str, list[str]] = {
        "learn": ["learn", "teach", "explain", "understand", "how to", "tutorial", "guide"],
        "debug": ["debug", "error", "broken", "fix", "issue", "problem", "crash", "bug"],
        "optimize": ["optimize", "improve", "performance", "faster", "efficient", "slow"],
        "build": ["build", "create", "develop", "implement", "make", "construct", "write"],
        "analyze": ["analyze", "review", "audit", "check", "evaluate", "inspect", "scan"],
        "integrate": ["integrate", "connect", "link", "combine", "sync", "merge"],
        "document": ["document", "comment", "explain", "write docs", "readme"],
    }

    def parse_intent(self, message: str) -> tuple[str, float]:
        """Parse primary intent from message.

        Args:
            message: User message text.

        Returns:
            Tuple of (intent_type, confidence).
        """
        text_lower = message.lower()
        intent_scores: defaultdict[str, float] = defaultdict(float)

        for intent, keywords in self.INTENT_PATTERNS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    intent_scores[intent] += 1.0

        if not intent_scores:
            return "learn", 0.3  # Default low-confidence

        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        # Normalize confidence: 1 match = 0.5, 2+ = 0.8+
        confidence = min(best_intent[1] / 3, 1.0)
        return best_intent[0], confidence

    def extract_domain(self, message: str, skill_catalog: dict[str, dict]) -> str | None:
        """Extract technology domain from message.

        Args:
            message: User message.
            skill_catalog: Available skills with metadata.

        Returns:
            Detected domain or None.
        """
        text_lower = message.lower()
        domain_scores: defaultdict[str, int] = defaultdict(int)

        for skill_name, meta in skill_catalog.items():
            tags = meta.get("tags", [])
            for tag in tags:
                if tag.lower() in text_lower:
                    domain_scores[tag] += 1

        if not domain_scores:
            return None

        return max(domain_scores.items(), key=lambda x: x[1])[0]


class TFIDFRanker:
    """TF-IDF based skill ranking."""

    def __init__(self, min_term_freq: int = 2):
        """Initialize ranker.

        Args:
            min_term_freq: Minimum term frequency for inclusion.
        """
        self.min_term_freq = min_term_freq
        self.idf_cache: dict[str, float] = {}

    def compute_tfidf(self, query_tokens: list[str], doc_tokens: dict[str, int]) -> float:
        """Compute TF-IDF similarity.

        Args:
            query_tokens: Tokenized query (user message).
            doc_tokens: Skill tokens with frequencies.

        Returns:
            TF-IDF score (0-1).
        """
        if not query_tokens or not doc_tokens:
            return 0.0

        score = 0.0
        for token in query_tokens:
            if token in doc_tokens:
                tf = doc_tokens[token]
                # Simple TF * IDF approximation
                score += tf * math.log(len(doc_tokens) + 1)

        # Normalize by query length and max possible score
        max_score = len(query_tokens) * math.log(len(doc_tokens) + 1)
        return min(score / max_score if max_score > 0 else 0.0, 1.0)

    def rank_skills(
        self,
        query: str,
        skills: dict[str, dict],
        top_k: int = 3,
    ) -> list[tuple[str, float]]:
        """Rank skills by TF-IDF relevance.

        Args:
            query: User query/message.
            skills: Dict of skill_name -> skill_metadata.
            top_k: Number of top skills to return.

        Returns:
            List of (skill_name, score) tuples.
        """
        query_tokens = query.lower().split()
        rankings: list[tuple[str, float]] = []

        for skill_name, meta in skills.items():
            description = meta.get("description", "").lower()
            tags = " ".join(meta.get("tags", [])).lower()
            combined_text = f"{description} {tags}"

            doc_tokens = self._tokenize_and_count(combined_text)
            score = self.compute_tfidf(query_tokens, doc_tokens)

            if score > 0.1:  # Filter very low scores
                rankings.append((skill_name, score))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings[:top_k]

    def _tokenize_and_count(self, text: str) -> dict[str, int]:
        """Tokenize and count term frequencies.

        Args:
            text: Input text.

        Returns:
            Dict of token -> frequency.
        """
        tokens = text.split()
        freq: defaultdict[str, int] = defaultdict(int)
        for token in tokens:
            token_clean = token.strip(".,!?;:")
            if len(token_clean) > 2:
                freq[token_clean] += 1
        return dict(freq)


class SemanticMatcher:
    """Simple semantic matching based on word overlap and synonyms."""

    SYNONYM_GROUPS = [
        {"api", "rest", "endpoint", "service", "http"},
        {"database", "db", "sql", "postgres", "mongodb"},
        {"react", "frontend", "ui", "component", "jsx"},
        {"python", "backend", "fastapi", "django", "async"},
        {"test", "unit", "e2e", "pytest", "vitest"},
        {"deploy", "docker", "k8s", "ci", "pipeline"},
    ]

    def similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity (0-1).

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Similarity score.
        """
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())

        # Direct overlap
        overlap = tokens1 & tokens2
        union = tokens1 | tokens2
        jaccard = len(overlap) / len(union) if union else 0.0

        # Synonym-based overlap
        synonym_overlap = 0
        for group in self.SYNONYM_GROUPS:
            if tokens1 & group and tokens2 & group:
                synonym_overlap += 1

        # Weighted score
        score = 0.7 * jaccard + 0.3 * min(synonym_overlap / len(self.SYNONYM_GROUPS), 1.0)
        return min(score, 1.0)


class SkillRecommender:
    """Main skill recommendation orchestrator."""

    def __init__(self, skill_catalog_path: Path | None = None):
        """Initialize recommender.

        Args:
            skill_catalog_path: Path to skill catalog JSON.
        """
        self.intent_parser = IntentParser()
        self.tfidf_ranker = TFIDFRanker()
        self.semantic_matcher = SemanticMatcher()

        if skill_catalog_path is None:
            skill_catalog_path = Path.cwd() / ".agent" / "skills" / "catalog.json"

        self.skill_catalog = self._load_catalog(skill_catalog_path)

    def _load_catalog(self, path: Path) -> dict[str, dict]:
        """Load skill catalog from JSON.

        Args:
            path: Path to catalog file.

        Returns:
            Skill catalog dict or empty dict if file missing.
        """
        if not path.exists():
            logger.warning(f"Skill catalog not found at {path}")
            # Return minimal default catalog for testing
            return {
                "python-basics": {
                    "description": "Learn Python fundamentals and syntax",
                    "tags": ["python", "learn", "beginner"],
                    "tier": "beginner",
                },
                "api-design": {
                    "description": "Design and build REST APIs",
                    "tags": ["api", "rest", "backend", "design"],
                    "tier": "intermediate",
                },
                "react-advanced": {
                    "description": "Advanced React patterns and optimization",
                    "tags": ["react", "frontend", "advanced", "performance"],
                    "tier": "advanced",
                },
            }

        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load skill catalog: {e}")
            return {}

    def recommend(
        self,
        message: str,
        user_skill_level: int,
        top_k: int = 3,
    ) -> list[SkillMatch]:
        """Recommend skills based on user message and level.

        Args:
            message: User message.
            user_skill_level: User's skill level (1-5).
            top_k: Number of recommendations to return.

        Returns:
            List of SkillMatch objects sorted by confidence.
        """
        if not self.skill_catalog:
            return []

        # Parse intent
        intent, intent_confidence = self.intent_parser.parse_intent(message)

        # Rank by TF-IDF
        tfidf_rankings = self.tfidf_ranker.rank_skills(message, self.skill_catalog, top_k=10)

        # Filter by skill level
        filtered_rankings = [
            (skill, score)
            for skill, score in tfidf_rankings
            if self._check_skill_level_match(skill, user_skill_level)
        ]

        # Score using multiple signals
        matches = []
        for skill_name, tfidf_score in filtered_rankings[:top_k]:
            skill_meta = self.skill_catalog[skill_name]
            description = skill_meta.get("description", "")

            # Combine signals
            semantic_score = self.semantic_matcher.similarity(message, description)
            confidence = 0.4 * tfidf_score + 0.3 * semantic_score + 0.3 * intent_confidence

            reasons = [
                f"Intent match: {intent}",
                f"TF-IDF relevance: {tfidf_score:.2f}",
            ]
            if semantic_score > 0.5:
                reasons.append(f"Semantic alignment: {semantic_score:.2f}")

            match = SkillMatch(
                skill_name=skill_name,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                tier=skill_meta.get("tier", "intermediate"),
                prerequisites=skill_meta.get("prerequisites", []),
            )
            matches.append(match)

        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches[:top_k]

    def _check_skill_level_match(self, skill_name: str, user_level: int) -> bool:
        """Check if skill tier matches user level.

        Args:
            skill_name: Name of the skill.
            user_level: User's skill level (1-5).

        Returns:
            True if appropriate for user level.
        """
        skill = self.skill_catalog.get(skill_name, {})
        tier = skill.get("tier", "intermediate").lower()

        tier_levels = {
            "beginner": 1,
            "intermediate": 3,
            "advanced": 4,
            "expert": 5,
        }

        required_level = tier_levels.get(tier, 3)
        # Allow user 1 level below required (soft match)
        return user_level >= required_level - 1
