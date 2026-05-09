"""
Antigravity Intelligence Layer - TOP A AI Capabilities.

This module provides advanced cognitive capabilities organized in 3 tiers:

=== FOUNDATION (Original) ===
- Self-Reflection: Agents evaluate their own outputs
- Chain-of-Thought: Explicit reasoning before action
- ReAct Pattern: Reasoning + Acting loop
- Multi-Agent Debate: Collaborative decision making
- Metacognition: Knowing what you don't know
- Knowledge Graph: Semantic memory with relationships
- Quality Scoring: Automated output evaluation
- Intelligent Agent: Enhanced agent base with all capabilities

=== NIVEL 1: CRITICAL ===
- Tool Learning: Agents learn new tools from documentation
- Skill Generator: Auto-generate skills from patterns
- Predictive Escalation: Predict failures before they happen
- Context Compression: Smart context management
- Proactive Suggestions: Suggest improvements proactively

=== NIVEL 2: HIGH IMPACT ===
- Adversarial Testing: Test with adversarial inputs
- Explainable Decisions: Human-readable decision explanations
- Cross-Agent Messaging: Direct agent-to-agent communication
- A/B Testing: Compare agent performance
- Emotion Detection: Detect user frustration/satisfaction

=== NIVEL 3: DIFFERENTIATORS ===
- Skill Composition: Dynamically combine skills
- Domain Specialization: Auto-specialize by domain
- Collaborative Memory: Shared knowledge across agents
- Time-Aware Memory: Temporal relevance decay
- Error Recovery: Library of recovery strategies

Version: 2.0.0
Created: 2026-02-03
"""

# ============================================================================
# FOUNDATION - Original Intelligence Modules
# ============================================================================
from .ab_testing import ABTester, ABTestResult, AgentOutput, ComparisonResult, run_ab_test

# ============================================================================
# NIVEL 2: HIGH IMPACT - Enhanced Capabilities
# ============================================================================
from .adversarial_testing import (
    AdversarialCase,
    AdversarialTester,
    TestCategory,
    TestResult,
    Vulnerability,
    test_adversarially,
)
from .chain_of_thought import ChainOfThought, ChainOfThoughtResult, ThoughtStep, think_through
from .collaborative_memory import (
    AccessLevel,
    CollaborativeMemory,
    MemoryType,
    QueryResult,
    SharedMemory,
    share_knowledge,
)
from .context_compression import (
    CompressionResult,
    ContentSegment,
    ContentType,
    ContextCompressor,
    compress_context,
)
from .cross_agent_messaging import (
    AgentMessenger,
    Conversation,
    Message,
    MessagePriority,
    MessageType,
    send_message,
)
from .domain_specialization import (
    AgentProfile,
    Domain,
    DomainKnowledge,
    DomainSpecializer,
    SpecializationLevel,
    specialize,
)
from .emotion_detection import (
    Emotion,
    EmotionAnalysis,
    EmotionDetector,
    EmotionIntensity,
    detect_emotion,
)
from .error_recovery import (
    ErrorCategory,
    ErrorRecovery,
    RecoveryResult,
    RecoveryStep,
    RecoveryStrategy,
    recover_from_error,
)
from .explainable_decisions import (
    DecisionExplainer,
    DecisionExplanation,
    DecisionFactor,
    FactorType,
    explain_decision,
)
from .intelligent_agent import (
    IntelligentAgent,
    IntelligentResult,
    SimpleIntelligentAgent,
    create_intelligent_agent,
)
from .knowledge_graph import (
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    create_knowledge_graph,
    initialize_with_common_knowledge,
)
from .metacognition import ConfidenceAssessment, Metacognition, assess_confidence
from .multi_agent_debate import DebateResult, MultiAgentDebate, quick_debate
from .predictive_escalation import (
    EscalationLevel,
    EscalationPrediction,
    PredictiveEscalation,
    RiskSignal,
    predict_escalation,
)
from .proactive_suggestions import (
    ProactiveSuggester,
    Suggestion,
    SuggestionCategory,
    SuggestionResult,
    get_suggestions,
)
from .quality_scorer import QualityScore, QualityScorer, quick_score
from .react_pattern import (
    Action,
    Observation,
    ReActAgent,
    ReActResult,
    Thought,
    create_default_react_agent,
)
from .self_reflection import ReflectionResult, SelfReflection, quick_reflect

# ============================================================================
# NIVEL 3: DIFFERENTIATORS - Unique Capabilities
# ============================================================================
from .skill_composition import (
    ComposedPipeline,
    CompositionNode,
    CompositionType,
    SkillComposer,
    compose_skills,
)
from .skill_generator import (
    ExecutionPattern,
    GeneratedSkill,
    GenerationResult,
    SkillGenerator,
    auto_generate_skill,
)
from .time_aware_memory import (
    DecayFunction,
    MemoryPriority,
    TemporalMemory,
    TimeAwareMemory,
    remember,
)

# ============================================================================
# NIVEL 1: CRITICAL - Core Capabilities
# ============================================================================
from .tool_learning import (
    LearningResult,
    ToolCategory,
    ToolKnowledge,
    ToolLearner,
    ToolParameter,
    learn_tool,
)

# ============================================================================
# VERSION & EXPORTS
# ============================================================================
__version__ = "2.0.0"

__all__ = [
    # === FOUNDATION ===
    # Self-Reflection
    "SelfReflection",
    "ReflectionResult",
    "quick_reflect",
    # Chain-of-Thought
    "ChainOfThought",
    "ThoughtStep",
    "ChainOfThoughtResult",
    "think_through",
    # ReAct
    "ReActAgent",
    "Observation",
    "Action",
    "Thought",
    "ReActResult",
    "create_default_react_agent",
    # Multi-Agent Debate
    "MultiAgentDebate",
    "DebateResult",
    "quick_debate",
    # Metacognition
    "Metacognition",
    "ConfidenceAssessment",
    "assess_confidence",
    # Knowledge Graph
    "KnowledgeGraph",
    "KnowledgeNode",
    "KnowledgeEdge",
    "create_knowledge_graph",
    "initialize_with_common_knowledge",
    # Quality Scorer
    "QualityScorer",
    "QualityScore",
    "quick_score",
    # Intelligent Agent
    "IntelligentAgent",
    "SimpleIntelligentAgent",
    "IntelligentResult",
    "create_intelligent_agent",
    # === NIVEL 1: CRITICAL ===
    # Tool Learning
    "ToolLearner",
    "ToolKnowledge",
    "ToolParameter",
    "ToolCategory",
    "LearningResult",
    "learn_tool",
    # Skill Generator
    "SkillGenerator",
    "GeneratedSkill",
    "ExecutionPattern",
    "GenerationResult",
    "auto_generate_skill",
    # Predictive Escalation
    "PredictiveEscalation",
    "EscalationPrediction",
    "RiskSignal",
    "EscalationLevel",
    "predict_escalation",
    # Context Compression
    "ContextCompressor",
    "CompressionResult",
    "ContentSegment",
    "ContentType",
    "compress_context",
    # Proactive Suggestions
    "ProactiveSuggester",
    "SuggestionResult",
    "Suggestion",
    "SuggestionCategory",
    "get_suggestions",
    # === NIVEL 2: HIGH IMPACT ===
    # Adversarial Testing
    "AdversarialTester",
    "TestResult",
    "AdversarialCase",
    "Vulnerability",
    "TestCategory",
    "test_adversarially",
    # Explainable Decisions
    "DecisionExplainer",
    "DecisionExplanation",
    "DecisionFactor",
    "FactorType",
    "explain_decision",
    # Cross-Agent Messaging
    "AgentMessenger",
    "Message",
    "Conversation",
    "MessageType",
    "MessagePriority",
    "send_message",
    # A/B Testing
    "ABTester",
    "ABTestResult",
    "AgentOutput",
    "ComparisonResult",
    "run_ab_test",
    # Emotion Detection
    "EmotionDetector",
    "EmotionAnalysis",
    "Emotion",
    "EmotionIntensity",
    "detect_emotion",
    # === NIVEL 3: DIFFERENTIATORS ===
    # Skill Composition
    "SkillComposer",
    "ComposedPipeline",
    "CompositionNode",
    "CompositionType",
    "compose_skills",
    # Domain Specialization
    "DomainSpecializer",
    "AgentProfile",
    "DomainKnowledge",
    "Domain",
    "SpecializationLevel",
    "specialize",
    # Collaborative Memory
    "CollaborativeMemory",
    "SharedMemory",
    "QueryResult",
    "MemoryType",
    "AccessLevel",
    "share_knowledge",
    # Time-Aware Memory
    "TimeAwareMemory",
    "TemporalMemory",
    "DecayFunction",
    "MemoryPriority",
    "remember",
    # Error Recovery
    "ErrorRecovery",
    "RecoveryResult",
    "RecoveryStep",
    "RecoveryStrategy",
    "ErrorCategory",
    "recover_from_error",
]
