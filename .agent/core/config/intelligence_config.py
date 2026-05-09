#!/usr/bin/env python3
"""
Intelligence Configuration Center.

Centralized configuration for all intelligence modules.

Supports:
- Default configurations
- Environment-based overrides
- Runtime tuning
- Per-agent customization
- Persistence

Version: 1.0.0
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("intelligence-config")


class DecayType(Enum):
    """Memory decay types."""

    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    STEP = "step"


class EmotionSensitivity(Enum):
    """Emotion detection sensitivity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class QualityStandard(Enum):
    """Quality standard levels."""

    BASIC = "basic"
    STANDARD = "standard"
    HIGH = "high"
    EXCELLENT = "excellent"


@dataclass
class ReflectionConfig:
    """Self-reflection module configuration."""

    enabled: bool = True
    depth: int = 3
    include_improvements: bool = True
    min_confidence_for_skip: float = 0.95
    aspects: list[str] = field(
        default_factory=lambda: ["accuracy", "completeness", "clarity", "relevance"]
    )


@dataclass
class ChainOfThoughtConfig:
    """Chain-of-thought module configuration."""

    enabled: bool = True
    max_steps: int = 10
    min_steps: int = 2
    require_conclusion: bool = True
    verbose: bool = False
    step_validation: bool = True


@dataclass
class DebateConfig:
    """Multi-agent debate module configuration."""

    enabled: bool = True
    max_rounds: int = 5
    min_rounds: int = 2
    perspectives: list[str] = field(default_factory=lambda: ["optimist", "pessimist", "pragmatist"])
    require_consensus: bool = True
    consensus_threshold: float = 0.7


@dataclass
class MetacognitionConfig:
    """Metacognition module configuration."""

    enabled: bool = True
    confidence_threshold: float = 0.6
    uncertainty_handling: str = "explicit"  # explicit, implicit, skip
    knowledge_gap_detection: bool = True


@dataclass
class KnowledgeGraphConfig:
    """Knowledge graph module configuration."""

    enabled: bool = True
    max_nodes: int = 10000
    max_edges: int = 50000
    auto_prune: bool = True
    prune_threshold: float = 0.1
    default_edge_weight: float = 0.5


@dataclass
class QualityScoringConfig:
    """Quality scoring module configuration."""

    enabled: bool = True
    standard: QualityStandard = QualityStandard.HIGH
    min_passing_score: float = 0.7
    dimensions: list[str] = field(
        default_factory=lambda: ["accuracy", "completeness", "clarity", "relevance", "consistency"]
    )
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "accuracy": 0.25,
            "completeness": 0.25,
            "clarity": 0.2,
            "relevance": 0.2,
            "consistency": 0.1,
        }
    )


@dataclass
class ToolLearningConfig:
    """Tool learning module configuration."""

    enabled: bool = True
    auto_learn: bool = True
    confidence_threshold: float = 0.6
    max_tools_cached: int = 100
    persist_learned_tools: bool = True


@dataclass
class SkillGeneratorConfig:
    """Skill generator module configuration."""

    enabled: bool = True
    min_examples: int = 3
    auto_generate: bool = False
    validation_required: bool = True
    output_dir: str = ".agent/skills/generated"


@dataclass
class PredictiveEscalationConfig:
    """Predictive escalation module configuration."""

    enabled: bool = True
    risk_threshold: float = 0.8
    auto_escalate: bool = True
    escalation_cooldown_minutes: int = 5
    risk_factors: list[str] = field(
        default_factory=lambda: [
            "destructive_operation",
            "production_environment",
            "security_sensitive",
            "data_loss_potential",
        ]
    )


@dataclass
class ContextCompressionConfig:
    """Context compression module configuration."""

    enabled: bool = True
    max_tokens: int = 8000
    preserve_code: bool = True
    preserve_recent: bool = True
    compression_ratio_target: float = 0.5
    importance_threshold: float = 0.3


@dataclass
class ProactiveSuggestionsConfig:
    """Proactive suggestions module configuration."""

    enabled: bool = True
    categories: list[str] = field(
        default_factory=lambda: ["security", "performance", "quality", "accessibility"]
    )
    max_suggestions: int = 5
    min_confidence: float = 0.7
    learn_from_feedback: bool = True


@dataclass
class AdversarialTestingConfig:
    """Adversarial testing module configuration."""

    enabled: bool = True
    categories: list[str] = field(
        default_factory=lambda: ["injection", "boundary", "malformed", "semantic"]
    )
    intensity: str = "medium"  # low, medium, high
    max_test_cases: int = 50
    timeout_seconds: int = 30


@dataclass
class ExplainableDecisionsConfig:
    """Explainable decisions module configuration."""

    enabled: bool = True
    detail_level: str = "medium"  # brief, medium, detailed
    include_alternatives: bool = True
    include_risks: bool = True
    audience: str = "technical"  # technical, non-technical, mixed


@dataclass
class CrossAgentMessagingConfig:
    """Cross-agent messaging module configuration."""

    enabled: bool = True
    max_queue_size: int = 1000
    message_ttl_seconds: int = 3600
    retry_attempts: int = 3
    async_by_default: bool = True


@dataclass
class ABTestingConfig:
    """A/B testing module configuration."""

    enabled: bool = True
    min_samples: int = 10
    confidence_level: float = 0.95
    metrics: list[str] = field(
        default_factory=lambda: ["quality", "speed", "accuracy", "completeness"]
    )
    auto_select_winner: bool = False


@dataclass
class EmotionDetectionConfig:
    """Emotion detection module configuration."""

    enabled: bool = True
    sensitivity: EmotionSensitivity = EmotionSensitivity.MEDIUM
    adapt_responses: bool = True
    emotions_tracked: list[str] = field(
        default_factory=lambda: ["neutral", "happy", "frustrated", "confused", "satisfied"]
    )
    frustration_threshold: float = 0.7


@dataclass
class SkillCompositionConfig:
    """Skill composition module configuration."""

    enabled: bool = True
    max_pipeline_length: int = 10
    parallel_execution: bool = True
    auto_optimize: bool = True
    cache_pipelines: bool = True


@dataclass
class DomainSpecializationConfig:
    """Domain specialization module configuration."""

    enabled: bool = True
    auto_specialize: bool = True
    specialization_threshold: float = 0.7
    domains: list[str] = field(
        default_factory=lambda: [
            "frontend",
            "backend",
            "database",
            "security",
            "devops",
            "testing",
            "documentation",
            "ml",
        ]
    )


@dataclass
class CollaborativeMemoryConfig:
    """Collaborative memory module configuration."""

    enabled: bool = True
    default_access_level: str = "team"  # private, team, public
    conflict_resolution: str = "latest_wins"  # latest_wins, merge, manual
    max_memories: int = 10000


@dataclass
class TimeAwareMemoryConfig:
    """Time-aware memory module configuration."""

    enabled: bool = True
    default_decay: DecayType = DecayType.EXPONENTIAL
    decay_rate: float = 0.1
    min_relevance: float = 0.1
    auto_cleanup: bool = True
    cleanup_interval_hours: int = 24


@dataclass
class ErrorRecoveryConfig:
    """Error recovery module configuration."""

    enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    exponential_backoff: bool = True
    learn_from_errors: bool = True
    recovery_strategies: list[str] = field(
        default_factory=lambda: ["retry", "fallback", "skip", "manual", "alternative"]
    )


@dataclass
class OrchestratorConfig:
    """Intelligent orchestrator configuration."""

    enabled: bool = True
    default_strategy: str = "adaptive"
    max_steps: int = 50
    parallel_agents: bool = True
    max_parallel_agents: int = 5
    timeout_seconds: int = 300
    auto_learn: bool = True


@dataclass
class IntelligenceConfig:
    """Master configuration for all intelligence modules."""

    # Module configurations
    reflection: ReflectionConfig = field(default_factory=ReflectionConfig)
    chain_of_thought: ChainOfThoughtConfig = field(default_factory=ChainOfThoughtConfig)
    debate: DebateConfig = field(default_factory=DebateConfig)
    metacognition: MetacognitionConfig = field(default_factory=MetacognitionConfig)
    knowledge_graph: KnowledgeGraphConfig = field(default_factory=KnowledgeGraphConfig)
    quality_scoring: QualityScoringConfig = field(default_factory=QualityScoringConfig)
    tool_learning: ToolLearningConfig = field(default_factory=ToolLearningConfig)
    skill_generator: SkillGeneratorConfig = field(default_factory=SkillGeneratorConfig)
    predictive_escalation: PredictiveEscalationConfig = field(
        default_factory=PredictiveEscalationConfig
    )
    context_compression: ContextCompressionConfig = field(default_factory=ContextCompressionConfig)
    proactive_suggestions: ProactiveSuggestionsConfig = field(
        default_factory=ProactiveSuggestionsConfig
    )
    adversarial_testing: AdversarialTestingConfig = field(default_factory=AdversarialTestingConfig)
    explainable_decisions: ExplainableDecisionsConfig = field(
        default_factory=ExplainableDecisionsConfig
    )
    cross_agent_messaging: CrossAgentMessagingConfig = field(
        default_factory=CrossAgentMessagingConfig
    )
    ab_testing: ABTestingConfig = field(default_factory=ABTestingConfig)
    emotion_detection: EmotionDetectionConfig = field(default_factory=EmotionDetectionConfig)
    skill_composition: SkillCompositionConfig = field(default_factory=SkillCompositionConfig)
    domain_specialization: DomainSpecializationConfig = field(
        default_factory=DomainSpecializationConfig
    )
    collaborative_memory: CollaborativeMemoryConfig = field(
        default_factory=CollaborativeMemoryConfig
    )
    time_aware_memory: TimeAwareMemoryConfig = field(default_factory=TimeAwareMemoryConfig)
    error_recovery: ErrorRecoveryConfig = field(default_factory=ErrorRecoveryConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)

    # Global settings
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    logging_level: str = "INFO"
    persistence_enabled: bool = True
    persistence_path: str = ".agent/data/intelligence"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "IntelligenceConfig":
        """Create from dictionary."""
        config = cls()

        # Update module configs
        module_configs = {
            "reflection": ReflectionConfig,
            "chain_of_thought": ChainOfThoughtConfig,
            "debate": DebateConfig,
            "metacognition": MetacognitionConfig,
            "knowledge_graph": KnowledgeGraphConfig,
            "quality_scoring": QualityScoringConfig,
            "tool_learning": ToolLearningConfig,
            "skill_generator": SkillGeneratorConfig,
            "predictive_escalation": PredictiveEscalationConfig,
            "context_compression": ContextCompressionConfig,
            "proactive_suggestions": ProactiveSuggestionsConfig,
            "adversarial_testing": AdversarialTestingConfig,
            "explainable_decisions": ExplainableDecisionsConfig,
            "cross_agent_messaging": CrossAgentMessagingConfig,
            "ab_testing": ABTestingConfig,
            "emotion_detection": EmotionDetectionConfig,
            "skill_composition": SkillCompositionConfig,
            "domain_specialization": DomainSpecializationConfig,
            "collaborative_memory": CollaborativeMemoryConfig,
            "time_aware_memory": TimeAwareMemoryConfig,
            "error_recovery": ErrorRecoveryConfig,
            "orchestrator": OrchestratorConfig,
        }

        for key, config_class in module_configs.items():
            if key in data:
                setattr(config, key, config_class(**data[key]))

        # Update global settings
        for key in [
            "version",
            "environment",
            "debug",
            "logging_level",
            "persistence_enabled",
            "persistence_path",
        ]:
            if key in data:
                setattr(config, key, data[key])

        return config

    @classmethod
    def from_json(cls, json_str: str) -> "IntelligenceConfig":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str) -> "IntelligenceConfig":
        """Load from file."""
        with open(path, encoding="utf-8") as f:
            return cls.from_json(f.read())

    def save(self, path: str):
        """Save to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_environment(cls) -> "IntelligenceConfig":
        """Create from environment variables."""
        config = cls()

        # Global settings from environment
        config.environment = os.getenv("INTELLIGENCE_ENV", "development")
        config.debug = os.getenv("INTELLIGENCE_DEBUG", "false").lower() == "true"
        config.logging_level = os.getenv("INTELLIGENCE_LOG_LEVEL", "INFO")

        # Module-specific from environment
        if os.getenv("INTELLIGENCE_REFLECTION_DEPTH"):
            config.reflection.depth = int(os.getenv("INTELLIGENCE_REFLECTION_DEPTH") or 0)

        if os.getenv("INTELLIGENCE_COT_MAX_STEPS"):
            config.chain_of_thought.max_steps = int(os.getenv("INTELLIGENCE_COT_MAX_STEPS") or 0)

        if os.getenv("INTELLIGENCE_DEBATE_ROUNDS"):
            config.debate.max_rounds = int(os.getenv("INTELLIGENCE_DEBATE_ROUNDS") or 0)

        if os.getenv("INTELLIGENCE_RISK_THRESHOLD"):
            config.predictive_escalation.risk_threshold = float(
                os.getenv("INTELLIGENCE_RISK_THRESHOLD") or 0.0
            )

        if os.getenv("INTELLIGENCE_QUALITY_THRESHOLD"):
            config.quality_scoring.min_passing_score = float(
                os.getenv("INTELLIGENCE_QUALITY_THRESHOLD") or 0.0
            )

        if os.getenv("INTELLIGENCE_EMOTION_SENSITIVITY"):
            sensitivity = os.getenv("INTELLIGENCE_EMOTION_SENSITIVITY")
            config.emotion_detection.sensitivity = EmotionSensitivity(sensitivity)

        if os.getenv("INTELLIGENCE_MEMORY_DECAY"):
            decay = os.getenv("INTELLIGENCE_MEMORY_DECAY")
            config.time_aware_memory.default_decay = DecayType(decay)

        return config

    def get_module_config(self, module_name: str) -> Any:
        """Get configuration for a specific module."""
        return getattr(self, module_name, None)

    def enable_module(self, module_name: str):
        """Enable a module."""
        module = getattr(self, module_name, None)
        if module and hasattr(module, "enabled"):
            module.enabled = True

    def disable_module(self, module_name: str):
        """Disable a module."""
        module = getattr(self, module_name, None)
        if module and hasattr(module, "enabled"):
            module.enabled = False

    def is_module_enabled(self, module_name: str) -> bool:
        """Check if module is enabled."""
        module = getattr(self, module_name, None)
        return module.enabled if module and hasattr(module, "enabled") else False

    def get_enabled_modules(self) -> list[str]:
        """Get list of enabled modules."""
        modules = [
            "reflection",
            "chain_of_thought",
            "debate",
            "metacognition",
            "knowledge_graph",
            "quality_scoring",
            "tool_learning",
            "skill_generator",
            "predictive_escalation",
            "context_compression",
            "proactive_suggestions",
            "adversarial_testing",
            "explainable_decisions",
            "cross_agent_messaging",
            "ab_testing",
            "emotion_detection",
            "skill_composition",
            "domain_specialization",
            "collaborative_memory",
            "time_aware_memory",
            "error_recovery",
            "orchestrator",
        ]
        return [m for m in modules if self.is_module_enabled(m)]

    def validate(self) -> list[str]:
        """Validate configuration, return list of issues."""
        issues = []

        # Check thresholds
        if self.quality_scoring.min_passing_score > 1.0:
            issues.append("quality_scoring.min_passing_score should be <= 1.0")

        if self.predictive_escalation.risk_threshold > 1.0:
            issues.append("predictive_escalation.risk_threshold should be <= 1.0")

        if self.debate.consensus_threshold > 1.0:
            issues.append("debate.consensus_threshold should be <= 1.0")

        # Check ranges
        if self.chain_of_thought.min_steps > self.chain_of_thought.max_steps:
            issues.append("chain_of_thought.min_steps should be <= max_steps")

        if self.debate.min_rounds > self.debate.max_rounds:
            issues.append("debate.min_rounds should be <= max_rounds")

        # Check paths
        if self.persistence_enabled:
            persistence_dir = Path(self.persistence_path)
            if not persistence_dir.exists():
                try:
                    persistence_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create persistence path: {e}")

        return issues


# =============================================================================
# PRESETS
# =============================================================================


def get_minimal_config() -> IntelligenceConfig:
    """Get minimal configuration (only essential modules)."""
    config = IntelligenceConfig()

    # Disable non-essential modules
    config.debate.enabled = False
    config.ab_testing.enabled = False
    config.adversarial_testing.enabled = False
    config.skill_generator.enabled = False
    config.domain_specialization.enabled = False

    return config


def get_production_config() -> IntelligenceConfig:
    """Get production-optimized configuration."""
    config = IntelligenceConfig()

    config.environment = "production"
    config.debug = False
    config.logging_level = "WARNING"

    # Higher thresholds for production
    config.quality_scoring.min_passing_score = 0.8
    config.predictive_escalation.risk_threshold = 0.7
    config.predictive_escalation.auto_escalate = True

    # More conservative settings
    config.chain_of_thought.max_steps = 15
    config.debate.max_rounds = 3
    config.error_recovery.max_retries = 5

    return config


def get_development_config() -> IntelligenceConfig:
    """Get development configuration with verbose output."""
    config = IntelligenceConfig()

    config.environment = "development"
    config.debug = True
    config.logging_level = "DEBUG"

    # More lenient for development
    config.quality_scoring.min_passing_score = 0.5
    config.predictive_escalation.risk_threshold = 0.9
    config.chain_of_thought.verbose = True

    return config


def get_high_quality_config() -> IntelligenceConfig:
    """Get configuration optimized for highest quality output."""
    config = IntelligenceConfig()

    config.quality_scoring.standard = QualityStandard.EXCELLENT
    config.quality_scoring.min_passing_score = 0.85

    config.reflection.depth = 5
    config.chain_of_thought.max_steps = 20
    config.debate.max_rounds = 7

    config.adversarial_testing.intensity = "high"

    return config


def get_fast_config() -> IntelligenceConfig:
    """Get configuration optimized for speed."""
    config = IntelligenceConfig()

    # Reduce iterations
    config.reflection.depth = 1
    config.chain_of_thought.max_steps = 5
    config.debate.max_rounds = 2
    config.debate.enabled = False  # Skip debate for speed

    # Lower thresholds
    config.quality_scoring.min_passing_score = 0.6
    config.metacognition.confidence_threshold = 0.5

    # Skip optional features
    config.adversarial_testing.enabled = False
    config.ab_testing.enabled = False

    return config


# =============================================================================
# SINGLETON CONFIG
# =============================================================================

_config: IntelligenceConfig | None = None


def get_config() -> IntelligenceConfig:
    """Get the global intelligence configuration."""
    global _config
    if _config is None:
        # Try to load from file first
        config_paths = [
            ".agent/config/intelligence.json",
            ".agent/data/intelligence/config.json",
            "intelligence_config.json",
        ]

        for path in config_paths:
            if Path(path).exists():
                try:
                    _config = IntelligenceConfig.from_file(path)
                    logger.info(f"Loaded intelligence config from {path}")
                    return _config
                except Exception as e:
                    logger.warning(f"Failed to load config from {path}: {e}")

        # Fall back to environment-based config
        _config = IntelligenceConfig.from_environment()
        logger.info("Using environment-based intelligence config")

    return _config


def set_config(config: IntelligenceConfig):
    """Set the global intelligence configuration."""
    global _config
    _config = config


def reset_config():
    """Reset to default configuration."""
    global _config
    _config = None


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI for intelligence configuration."""
    import argparse

    parser = argparse.ArgumentParser(description="Intelligence Configuration Manager")
    parser.add_argument("--show", action="store_true", help="Show current config")
    parser.add_argument("--validate", action="store_true", help="Validate config")
    parser.add_argument(
        "--preset", choices=["minimal", "production", "development", "high_quality", "fast"]
    )
    parser.add_argument("--save", help="Save config to file")
    parser.add_argument("--load", help="Load config from file")
    parser.add_argument("--enabled", action="store_true", help="Show enabled modules")
    args = parser.parse_args()

    if args.load:
        config = IntelligenceConfig.from_file(args.load)
        set_config(config)
        print(f"Loaded config from {args.load}")
    elif args.preset:
        presets = {
            "minimal": get_minimal_config,
            "production": get_production_config,
            "development": get_development_config,
            "high_quality": get_high_quality_config,
            "fast": get_fast_config,
        }
        config = presets[args.preset]()
        set_config(config)
        print(f"Loaded {args.preset} preset")
    else:
        config = get_config()

    if args.validate:
        issues = config.validate()
        if issues:
            print("Validation issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("Configuration is valid")

    if args.enabled:
        print("Enabled modules:")
        for module in config.get_enabled_modules():
            print(f"  - {module}")

    if args.show:
        print(config.to_json())

    if args.save:
        config.save(args.save)
        print(f"Saved config to {args.save}")


if __name__ == "__main__":
    main()
