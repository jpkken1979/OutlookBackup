"""User Modeling module for Telegram intelligence.

Extracts and maintains user profiles from chat history.
Tracks engagement via EMA scoring, keywords, sentiment, and skill levels.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """User profile extracted from chat history.

    Args:
        user_id: Telegram user ID.
        name: User display name.
        keywords: Top keywords by frequency.
        skill_level: Estimated skill level (1-5).
        engagement_score: EMA-based engagement (0-1).
        sentiment_avg: Average sentiment from messages (-1 to 1).
        total_messages: Total message count.
        last_active: Last activity timestamp.
        learning_goals: Detected learning interests.
    """

    user_id: int
    name: str
    keywords: list[tuple[str, float]] = field(default_factory=list)
    skill_level: int = 3
    engagement_score: float = 0.5
    sentiment_avg: float = 0.0
    total_messages: int = 0
    last_active: datetime | None = None
    learning_goals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert profile to JSON-serializable dict."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "keywords": self.keywords,
            "skill_level": self.skill_level,
            "engagement_score": self.engagement_score,
            "sentiment_avg": self.sentiment_avg,
            "total_messages": self.total_messages,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "learning_goals": self.learning_goals,
        }


class UserModelDB:
    """SQLite-backed user modeling storage.

    Schema:
        users: user_id, name, skill_level, engagement_score, sentiment_avg, total_messages, last_active
        keywords: user_id, keyword, frequency, weight
        profiles: user_id, data (JSON blob)
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.antigravity/telegram_users.db
        """
        if db_path is None:
            db_path = Path.home() / ".antigravity" / "telegram_users.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    skill_level INTEGER DEFAULT 3,
                    engagement_score REAL DEFAULT 0.5,
                    sentiment_avg REAL DEFAULT 0.0,
                    total_messages INTEGER DEFAULT 0,
                    last_active TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    weight REAL DEFAULT 1.0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, keyword)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            conn.commit()

    def save_user(self, profile: UserProfile) -> None:
        """Save or update user profile.

        Args:
            profile: UserProfile to persist.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO users
                (user_id, name, skill_level, engagement_score, sentiment_avg, total_messages, last_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    profile.user_id,
                    profile.name,
                    profile.skill_level,
                    profile.engagement_score,
                    profile.sentiment_avg,
                    profile.total_messages,
                    profile.last_active.isoformat() if profile.last_active else None,
                ),
            )

            conn.execute(
                "INSERT OR REPLACE INTO profiles (user_id, data) VALUES (?, ?)",
                (profile.user_id, json.dumps(profile.to_dict())),
            )

            conn.commit()

    def get_user(self, user_id: int) -> UserProfile | None:
        """Retrieve user profile.

        Args:
            user_id: Telegram user ID.

        Returns:
            UserProfile or None if not found.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,)).fetchone()

            if not row:
                return None

            data = json.loads(row[0])
            profile = UserProfile(
                user_id=data["user_id"],
                name=data["name"],
                keywords=data["keywords"],
                skill_level=data["skill_level"],
                engagement_score=data["engagement_score"],
                sentiment_avg=data["sentiment_avg"],
                total_messages=data["total_messages"],
                last_active=datetime.fromisoformat(data["last_active"])
                if data["last_active"]
                else None,
                learning_goals=data["learning_goals"],
            )
            return profile


class KeywordExtractor:
    """Extracts keywords from message text with frequency weighting."""

    STOPWORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "be",
        "been",
        "have",
        "has",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "can",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
    }

    def extract(self, text: str, min_length: int = 3) -> list[str]:
        """Extract keywords from text.

        Args:
            text: Input text.
            min_length: Minimum keyword length.

        Returns:
            List of lowercase keywords without stopwords.
        """
        tokens = text.lower().split()
        keywords = [
            token.strip(".,!?;:")
            for token in tokens
            if len(token) >= min_length and token.lower() not in self.STOPWORDS
        ]
        return keywords

    def compute_frequencies(self, messages: list[str]) -> dict[str, float]:
        """Compute TF-IDF-like keyword frequencies.

        Args:
            messages: List of message texts.

        Returns:
            Dict mapping keyword -> frequency weight (0-1).
        """
        keyword_counts: defaultdict[str, int] = defaultdict(int)
        total_keywords = 0

        for msg in messages:
            keywords = self.extract(msg)
            for kw in keywords:
                keyword_counts[kw] += 1
                total_keywords += 1

        if total_keywords == 0:
            return {}

        return {kw: min(count / total_keywords * 10, 1.0) for kw, count in keyword_counts.items()}


class SentimentAnalyzer:
    """Simple lexicon-based sentiment analysis."""

    POSITIVE_WORDS = {
        "good",
        "great",
        "awesome",
        "excellent",
        "love",
        "like",
        "perfect",
        "happy",
        "cool",
    }
    NEGATIVE_WORDS = {
        "bad",
        "terrible",
        "hate",
        "dislike",
        "awful",
        "poor",
        "sad",
        "angry",
        "broken",
    }

    def analyze(self, text: str) -> float:
        """Analyze sentiment of text.

        Args:
            text: Input text.

        Returns:
            Sentiment score (-1 to 1).
        """
        tokens = text.lower().split()
        pos_count = sum(1 for token in tokens if token.strip(".,!?;:") in self.POSITIVE_WORDS)
        neg_count = sum(1 for token in tokens if token.strip(".,!?;:") in self.NEGATIVE_WORDS)
        total = pos_count + neg_count

        if total == 0:
            return 0.0

        return (pos_count - neg_count) / total


class EngagementScorer:
    """Tracks engagement using exponential moving average (EMA).

    EMA gives recent activity higher weight. Formula:
        EMA_t = alpha * value_t + (1 - alpha) * EMA_{t-1}
    """

    def __init__(self, alpha: float = 0.3, decay_days: int = 30):
        """Initialize scorer.

        Args:
            alpha: EMA smoothing factor (0-1). Higher = faster adaptation.
            decay_days: Number of days for full decay to baseline.
        """
        self.alpha = alpha
        self.decay_days = decay_days

    def update(self, current_ema: float, time_delta_days: float) -> float:
        """Apply time decay to engagement score.

        Args:
            current_ema: Current EMA value.
            time_delta_days: Days since last activity.

        Returns:
            Decayed EMA score.
        """
        # Decay factor: e^(-t/tau) where tau is decay constant
        tau = self.decay_days
        decay = math.exp(-time_delta_days / tau)
        return current_ema * decay

    def add_activity(self, current_ema: float, intensity: float = 1.0) -> float:
        """Add activity to engagement score.

        Args:
            current_ema: Current EMA value.
            intensity: Activity intensity (0-1).

        Returns:
            Updated EMA.
        """
        return self.alpha * intensity + (1 - self.alpha) * current_ema


class UserModeler:
    """Main user modeling orchestrator."""

    def __init__(self, db_path: Path | None = None):
        """Initialize modeler.

        Args:
            db_path: Path to SQLite database.
        """
        self.db = UserModelDB(db_path)
        self.keyword_extractor = KeywordExtractor()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.engagement_scorer = EngagementScorer()

    def extract_profile(self, user_id: int, name: str, messages: list[str]) -> UserProfile:
        """Extract user profile from chat history.

        Args:
            user_id: Telegram user ID.
            name: User display name.
            messages: List of message texts.

        Returns:
            UserProfile.
        """
        # Extract keywords
        keywords_freq = self.keyword_extractor.compute_frequencies(messages)
        keywords = sorted(keywords_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        # Analyze sentiment
        sentiments = [self.sentiment_analyzer.analyze(msg) for msg in messages]
        sentiment_avg = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # Estimate skill level from keyword complexity
        skill_level = self._estimate_skill_level(keywords, messages)

        # Calculate engagement
        engagement_score = min(len(messages) / 100, 1.0)  # Normalized by message count

        # Detect learning goals from keywords
        learning_goals = self._detect_learning_goals(keywords)

        profile = UserProfile(
            user_id=user_id,
            name=name,
            keywords=keywords,
            skill_level=skill_level,
            engagement_score=engagement_score,
            sentiment_avg=sentiment_avg,
            total_messages=len(messages),
            last_active=datetime.now(),
            learning_goals=learning_goals,
        )

        self.db.save_user(profile)
        return profile

    def _estimate_skill_level(self, keywords: list[tuple[str, float]], messages: list[str]) -> int:
        """Estimate skill level (1-5) based on keywords and message complexity.

        Args:
            keywords: Top keywords with weights.
            messages: List of messages.

        Returns:
            Skill level 1-5.
        """
        # Heuristics: keyword count, avg message length, technical terms
        technical_keywords = {kw for kw, _ in keywords}
        technical_terms = {
            "api",
            "database",
            "algorithm",
            "async",
            "cache",
            "optimization",
            "architecture",
            "microservice",
            "deployment",
            "scalability",
        }
        tech_score = len(technical_keywords & technical_terms)

        avg_msg_len = sum(len(m.split()) for m in messages) / len(messages) if messages else 0
        length_score = min(avg_msg_len / 30, 1.0)  # Normalize to 30 words

        total_score = (tech_score / 5) * 0.5 + length_score * 0.5
        return max(1, min(5, int(total_score * 5) + 1))

    def _detect_learning_goals(self, keywords: list[tuple[str, float]]) -> list[str]:
        """Detect learning goals from keywords.

        Args:
            keywords: Top keywords.

        Returns:
            List of detected learning interests.
        """
        goal_keywords = {
            "learn",
            "understand",
            "master",
            "build",
            "improve",
            "develop",
            "explore",
            "practice",
            "implement",
            "optimize",
        }
        goals = []
        for kw, _ in keywords:
            if kw in goal_keywords:
                goals.append(kw)
        return goals[:3]  # Top 3 goals
