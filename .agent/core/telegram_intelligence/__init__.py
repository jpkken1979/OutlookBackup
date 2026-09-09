"""Telegram Intelligence subsystem.

Provides user modeling, skill recommendation, and memory bridge
for Telegram bot integration with Nexus Brain and mem0.
"""

from .user_modeling import (
    UserProfile,
    UserModeler,
    KeywordExtractor,
    SentimentAnalyzer,
    EngagementScorer,
    UserModelDB,
)
from .skill_recommender import (
    SkillMatch,
    SkillRecommender,
    IntentParser,
    TFIDFRanker,
    SemanticMatcher,
)
from .memory_bridge import (
    SessionMemory,
    MemoryBridge,
    BrainClient,
    Mem0Client,
    SessionMemoryStore,
)

__all__ = [
    "UserProfile",
    "UserModeler",
    "KeywordExtractor",
    "SentimentAnalyzer",
    "EngagementScorer",
    "UserModelDB",
    "SkillMatch",
    "SkillRecommender",
    "IntentParser",
    "TFIDFRanker",
    "SemanticMatcher",
    "SessionMemory",
    "MemoryBridge",
    "BrainClient",
    "Mem0Client",
    "SessionMemoryStore",
]
