"""
Antigravity Core - Enterprise-grade Agent Orchestration Framework.

This module provides the core infrastructure for the Antigravity ecosystem:
- CrewAI-based multi-agent orchestration
- ChromaDB vector memory
- A2A Protocol for agent discovery
- OpenTelemetry observability
- WebSocket Gateway control plane
- Multi-channel message routing

IMPROVED in v4.3.1: Lazy imports with clear error messages instead of silent fallbacks.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING, Any, TypeVar

logger = logging.getLogger(__name__)

__version__ = "2.1.0"  # Synced with pyproject.toml (single source of truth)

# =============================================================================
# LAZY IMPORT SYSTEM - Clear errors instead of silent None fallbacks
# =============================================================================


class ModuleStatus(Enum):
    """Status of a module import attempt."""

    NOT_LOADED = "not_loaded"
    LOADED = "loaded"
    FAILED = "failed"
    OPTIONAL_MISSING = "optional_missing"


@dataclass
class ModuleInfo:
    """Information about a module's import status."""

    name: str
    status: ModuleStatus = ModuleStatus.NOT_LOADED
    error: str | None = None
    optional: bool = False
    requires: list[str] = field(default_factory=list)


# Track all module import attempts for diagnostics
_module_registry: dict[str, ModuleInfo] = {}


def _lazy_import(
    module_path: str, attribute: str, optional: bool = False, requires: list[str] | None = None
) -> Callable[[], Any]:
    """
    Create a lazy importer that loads on first access.

    Args:
        module_path: Full module path (e.g., '.orchestrator')
        attribute: Attribute to import from module
        optional: If True, return None on failure instead of raising
        requires: List of pip packages required

    Returns:
        A callable that returns the imported attribute
    """
    _cached_value: list[Any] = []  # Use list to allow mutation in closure

    def _get() -> Any:
        if _cached_value:
            return _cached_value[0]

        full_path = f".agent.core{module_path}" if module_path.startswith(".") else module_path
        info = ModuleInfo(
            name=f"{full_path}.{attribute}", optional=optional, requires=requires or []
        )

        try:
            # Import relative to this package
            if module_path.startswith("."):
                mod = import_module(module_path, package=__name__)
            else:
                mod = import_module(module_path)

            value = getattr(mod, attribute)
            _cached_value.append(value)
            info.status = ModuleStatus.LOADED
            _module_registry[info.name] = info
            return value

        except ImportError as e:
            info.status = ModuleStatus.OPTIONAL_MISSING if optional else ModuleStatus.FAILED
            info.error = str(e)
            _module_registry[info.name] = info

            if optional:
                _cached_value.append(None)
                return None

            # Provide helpful error message
            deps = ", ".join(requires) if requires else "unknown"
            raise ImportError(
                f"Failed to import {attribute} from {module_path}. "
                f"Required packages: {deps}. "
                f"Install with: pip install antigravity[{deps}]\n"
                f"Original error: {e}"
            ) from e
        except AttributeError:
            info.status = ModuleStatus.FAILED
            info.error = f"Attribute '{attribute}' not found in module"
            _module_registry[info.name] = info

            if optional:
                _cached_value.append(None)
                return None
            raise

    return _get


# =============================================================================
# CORE MODULES - Required for basic functionality
# =============================================================================

# Orchestrator
_get_orchestrator = _lazy_import(".orchestrator", "AntigravityOrchestrator")

# Memory System
_get_shared_memory = _lazy_import(".shared_memory", "SharedMemory")
_get_vector_memory = _lazy_import(".shared_memory", "VectorMemory")
_get_memory_bus_class = _lazy_import(".shared_memory", "MemoryBus")
_get_memory_bus_fn = _lazy_import(".shared_memory", "get_memory_bus")

# Agent Base
_get_agent_base = _lazy_import(".agent_base", "AntigravityAgent")

# A2A Protocol
_get_a2a_protocol = _lazy_import(".a2a", "A2AProtocol", optional=True)
_get_agent_card = _lazy_import(".a2a", "AgentCard", optional=True)
_get_agent_message_bus = _lazy_import(".a2a", "AgentMessageBus", optional=True)
_get_message_bus_fn = _lazy_import(".a2a", "get_message_bus", optional=True)

# Telemetry
_get_setup_telemetry = _lazy_import(
    ".telemetry", "setup_telemetry", optional=True, requires=["opentelemetry"]
)

# LLM
_get_llm_client = _lazy_import(".llm", "LLMClient", optional=True)
_get_llm_response = _lazy_import(".llm", "LLMResponse", optional=True)

# =============================================================================
# EXECUTION & ORCHESTRATION
# =============================================================================

_get_execution_engine = _lazy_import(".execution_engine", "ExecutionEngine", optional=True)
_get_execution_plan = _lazy_import(".execution_engine", "ExecutionPlan", optional=True)
_get_execution_report = _lazy_import(".execution_engine", "ExecutionReport", optional=True)
_get_agent_result = _lazy_import(".execution_engine", "AgentResult", optional=True)
_get_run_task = _lazy_import(".execution_engine", "run_task", optional=True)
_get_run_task_sync = _lazy_import(".execution_engine", "run_task_sync", optional=True)
_get_engine_fn = _lazy_import(".execution_engine", "get_engine", optional=True)
_get_task_type = _lazy_import(".execution_engine", "TaskType", optional=True)
_get_execution_status = _lazy_import(".execution_engine", "ExecutionStatus", optional=True)

# =============================================================================
# FEEDBACK & LEARNING
# =============================================================================

_get_feedback_collector = _lazy_import(".feedback", "FeedbackCollector", optional=True)
_get_feedback_collector_fn = _lazy_import(".feedback", "get_feedback_collector", optional=True)
_get_learning_pipeline = _lazy_import(
    ".autonomous_learning", "AutonomousLearningPipeline", optional=True
)
_get_learning_pipeline_fn = _lazy_import(
    ".autonomous_learning", "get_learning_pipeline", optional=True
)
_get_learning_type = _lazy_import(".autonomous_learning", "LearningType", optional=True)
_get_feedback_type = _lazy_import(".autonomous_learning", "FeedbackType", optional=True)

# =============================================================================
# GATEWAY & ROUTING (OpenClaw-inspired)
# =============================================================================

_get_gateway = _lazy_import(".gateway", "AntigravityGateway", optional=True)
_get_gateway_config = _lazy_import(".gateway", "GatewayConfig", optional=True)
_get_create_gateway = _lazy_import(".gateway", "create_gateway", optional=True)

_get_channel_router = _lazy_import(".channel_router", "ChannelRouter", optional=True)
_get_platform = _lazy_import(".channel_router", "Platform", optional=True)
_get_unified_message = _lazy_import(".channel_router", "UnifiedMessage", optional=True)
_get_create_router = _lazy_import(".channel_router", "create_router", optional=True)
_get_quick_connect = _lazy_import(".channel_router", "quick_connect", optional=True)

# =============================================================================
# COST & CAPABILITY TRACKING
# =============================================================================

_get_cost_tracker = _lazy_import(".cost_tracker", "CostTracker", optional=True)
_get_tracker_fn = _lazy_import(".cost_tracker", "get_tracker", optional=True)
_get_cost_report = _lazy_import(".cost_tracker", "CostReport", optional=True)

_get_capability_registry = _lazy_import(".capability_registry", "CapabilityRegistry", optional=True)
_get_registry_fn = _lazy_import(".capability_registry", "get_registry", optional=True)
_get_agent_capability = _lazy_import(".capability_registry", "AgentCapability", optional=True)

# =============================================================================
# INTELLIGENCE LAYER
# =============================================================================

_get_chain_of_thought = _lazy_import(".intelligence", "ChainOfThought", optional=True)
_get_metacognition = _lazy_import(".intelligence", "Metacognition", optional=True)
_get_multi_agent_debate = _lazy_import(".intelligence", "MultiAgentDebate", optional=True)
_get_knowledge_graph = _lazy_import(".intelligence", "KnowledgeGraph", optional=True)
_get_quality_scorer = _lazy_import(".intelligence", "QualityScorer", optional=True)
_get_react_agent = _lazy_import(".intelligence", "ReActAgent", optional=True)
_get_self_reflection = _lazy_import(".intelligence", "SelfReflection", optional=True)
_get_intelligent_agent = _lazy_import(".intelligence", "IntelligentAgent", optional=True)

# =============================================================================
# ADVANCED MODULES
# =============================================================================

# Agent Mesh (P2P)
_get_agent_mesh = _lazy_import(".agent_mesh", "AgentMesh", optional=True)
_get_agent_mesh_fn = _lazy_import(".agent_mesh", "get_agent_mesh", optional=True)

# Knowledge Hub
_get_knowledge_hub = _lazy_import(".knowledge_hub", "KnowledgeHub", optional=True)
_get_knowledge_hub_fn = _lazy_import(".knowledge_hub", "get_knowledge_hub", optional=True)

# Debate Protocol
_get_debate_protocol = _lazy_import(".debate_protocol", "DebateProtocol", optional=True)
_get_debate_protocol_fn = _lazy_import(".debate_protocol", "get_debate_protocol", optional=True)

# Meta-Orchestrator
_get_meta_orchestrator = _lazy_import(".meta_orchestrator", "MetaOrchestrator", optional=True)
_get_meta_orchestrator_fn = _lazy_import(
    ".meta_orchestrator", "get_meta_orchestrator", optional=True
)

# Skill Composer
_get_skill_composer = _lazy_import(".skill_composer", "SkillComposer", optional=True)
_get_skill_composer_fn = _lazy_import(".skill_composer", "get_skill_composer", optional=True)

# Federated Learning
_get_federated_learning = _lazy_import(".federated_learning", "FederatedLearning", optional=True)
_get_federated_learning_fn = _lazy_import(
    ".federated_learning", "get_federated_learning", optional=True
)

# Auto-Healing
_get_auto_healer = _lazy_import(".auto_healing", "AutoHealer", optional=True)
_get_healer_fn = _lazy_import(".auto_healing", "get_healer", optional=True)
_get_circuit_breaker = _lazy_import(".auto_healing", "CircuitBreaker", optional=True)

# Skill System
_get_skill_registry = _lazy_import(".skill_registry", "SkillRegistry", optional=True)
_get_skill_registry_error = _lazy_import(".skill_registry", "SkillRegistryError", optional=True)
_get_skill_record = _lazy_import(".skill_record", "SkillRecord", optional=True)
_get_skill_record_lazy = _lazy_import(".skill_record", "SkillRecordLazy", optional=True)
_get_skill_category = _lazy_import(".skill_record", "SkillCategory", optional=True)
_get_skill_status = _lazy_import(".skill_record", "SkillStatus", optional=True)

# Agent Teams
_get_agent_team = _lazy_import(".agent_teams", "AgentTeam", optional=True)
_get_team_manager = _lazy_import(".agent_teams", "TeamManager", optional=True)
_get_team_manager_fn = _lazy_import(".agent_teams", "get_team_manager", optional=True)
_get_spawn_team = _lazy_import(".agent_teams", "spawn_team", optional=True)
_get_auto_team = _lazy_import(".agent_teams", "auto_team", optional=True)

# =============================================================================
# PUBLIC API - Properties that trigger lazy loading
# =============================================================================


class _LazyModule:
    """Lazy module loader that provides clear errors on access."""

    # Core
    @property
    def AntigravityOrchestrator(self):
        return _get_orchestrator()

    @property
    def SharedMemory(self):
        return _get_shared_memory()

    @property
    def VectorMemory(self):
        return _get_vector_memory()

    @property
    def MemoryBus(self):
        return _get_memory_bus_class()

    @property
    def get_memory_bus(self):
        return _get_memory_bus_fn()

    @property
    def AntigravityAgent(self):
        return _get_agent_base()

    # A2A
    @property
    def A2AProtocol(self):
        return _get_a2a_protocol()

    @property
    def AgentCard(self):
        return _get_agent_card()

    @property
    def AgentMessageBus(self):
        return _get_agent_message_bus()

    @property
    def get_message_bus(self):
        return _get_message_bus_fn()

    # Telemetry
    @property
    def setup_telemetry(self):
        return _get_setup_telemetry()

    # Execution
    @property
    def ExecutionEngine(self):
        return _get_execution_engine()

    @property
    def run_task(self):
        return _get_run_task()

    @property
    def run_task_sync(self):
        return _get_run_task_sync()

    @property
    def get_engine(self):
        return _get_engine_fn()

    # Intelligence
    @property
    def ChainOfThought(self):
        return _get_chain_of_thought()

    @property
    def Metacognition(self):
        return _get_metacognition()

    @property
    def MultiAgentDebate(self):
        return _get_multi_agent_debate()

    @property
    def KnowledgeGraph(self):
        return _get_knowledge_graph()

    @property
    def QualityScorer(self):
        return _get_quality_scorer()

    @property
    def IntelligentAgent(self):
        return _get_intelligent_agent()

    # Advanced
    @property
    def AgentMesh(self):
        return _get_agent_mesh()

    @property
    def get_agent_mesh(self):
        return _get_agent_mesh_fn()

    @property
    def KnowledgeHub(self):
        return _get_knowledge_hub()

    @property
    def get_knowledge_hub(self):
        return _get_knowledge_hub_fn()

    @property
    def DebateProtocol(self):
        return _get_debate_protocol()

    @property
    def get_debate_protocol(self):
        return _get_debate_protocol_fn()

    @property
    def AutoHealer(self):
        return _get_auto_healer()

    @property
    def get_healer(self):
        return _get_healer_fn()

    @property
    def CircuitBreaker(self):
        return _get_circuit_breaker()

    # Cost Tracking
    @property
    def CostTracker(self):
        return _get_cost_tracker()

    @property
    def get_tracker(self):
        return _get_tracker_fn()

    # Gateway
    @property
    def AntigravityGateway(self):
        return _get_gateway()

    @property
    def create_gateway(self):
        return _get_create_gateway()

    @property
    def ChannelRouter(self):
        return _get_channel_router()


# =============================================================================
# HEALTH CHECK SYSTEM
# =============================================================================


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    healthy: bool
    total_modules: int
    loaded_modules: int
    failed_modules: int
    optional_missing: int
    details: dict[str, ModuleInfo]

    def __str__(self) -> str:
        status = "HEALTHY" if self.healthy else "DEGRADED"
        return (
            f"System Status: {status}\n"
            f"  Loaded: {self.loaded_modules}/{self.total_modules}\n"
            f"  Failed: {self.failed_modules}\n"
            f"  Optional Missing: {self.optional_missing}"
        )


def check_health(verbose: bool = False) -> HealthCheckResult:
    """
    Check the health of all core modules.

    Args:
        verbose: If True, attempt to load all modules for full check

    Returns:
        HealthCheckResult with detailed status
    """
    if verbose:
        # Trigger all lazy imports to check what works
        _test_imports = [
            _get_orchestrator,
            _get_shared_memory,
            _get_agent_base,
            _get_execution_engine,
            _get_chain_of_thought,
            _get_agent_mesh,
            _get_auto_healer,
        ]
        for fn in _test_imports:
            try:
                fn()
            except Exception:
                pass

    loaded = sum(1 for m in _module_registry.values() if m.status == ModuleStatus.LOADED)
    failed = sum(1 for m in _module_registry.values() if m.status == ModuleStatus.FAILED)
    optional = sum(
        1 for m in _module_registry.values() if m.status == ModuleStatus.OPTIONAL_MISSING
    )

    return HealthCheckResult(
        healthy=failed == 0,
        total_modules=len(_module_registry),
        loaded_modules=loaded,
        failed_modules=failed,
        optional_missing=optional,
        details=dict(_module_registry),
    )


def get_module_status() -> dict[str, str]:
    """Get a simple dict of module name -> status for diagnostics."""
    return {name: info.status.value for name, info in _module_registry.items()}


def list_available_modules() -> list[str]:
    """List all modules that loaded successfully."""
    return [name for name, info in _module_registry.items() if info.status == ModuleStatus.LOADED]


def list_failed_modules() -> list[tuple[str, str]]:
    """List modules that failed to load with their error messages."""
    return [
        (name, info.error or "Unknown error")
        for name, info in _module_registry.items()
        if info.status == ModuleStatus.FAILED
    ]


# =============================================================================
# BACKWARDS COMPATIBILITY - Direct imports still work
# =============================================================================

# For code that does: from .agent.core import AntigravityOrchestrator
# We need to support this without breaking, but with clear errors


def __getattr__(name: str) -> Any:
    """
    Module-level __getattr__ for lazy loading on attribute access.
    This enables: from .agent.core import SomeClass
    """
    # Map attribute names to their lazy loaders
    _attr_map = {
        # Core
        "AntigravityOrchestrator": _get_orchestrator,
        "SharedMemory": _get_shared_memory,
        "VectorMemory": _get_vector_memory,
        "MemoryBus": _get_memory_bus_class,
        "get_memory_bus": _get_memory_bus_fn,
        "AntigravityAgent": _get_agent_base,
        # A2A
        "A2AProtocol": _get_a2a_protocol,
        "AgentCard": _get_agent_card,
        "AgentMessageBus": _get_agent_message_bus,
        "get_message_bus": _get_message_bus_fn,
        # Telemetry
        "setup_telemetry": _get_setup_telemetry,
        # Execution
        "ExecutionEngine": _get_execution_engine,
        "ExecutionPlan": _get_execution_plan,
        "ExecutionReport": _get_execution_report,
        "AgentResult": _get_agent_result,
        "run_task": _get_run_task,
        "run_task_sync": _get_run_task_sync,
        "get_engine": _get_engine_fn,
        "TaskType": _get_task_type,
        "ExecutionStatus": _get_execution_status,
        # Feedback
        "FeedbackCollector": _get_feedback_collector,
        "get_feedback_collector": _get_feedback_collector_fn,
        "AutonomousLearningPipeline": _get_learning_pipeline,
        "get_learning_pipeline": _get_learning_pipeline_fn,
        "LearningType": _get_learning_type,
        "FeedbackType": _get_feedback_type,
        # Gateway
        "AntigravityGateway": _get_gateway,
        "GatewayConfig": _get_gateway_config,
        "create_gateway": _get_create_gateway,
        "ChannelRouter": _get_channel_router,
        "Platform": _get_platform,
        "UnifiedMessage": _get_unified_message,
        "create_router": _get_create_router,
        "quick_connect": _get_quick_connect,
        # Cost
        "CostTracker": _get_cost_tracker,
        "get_tracker": _get_tracker_fn,
        "CostReport": _get_cost_report,
        # Capability
        "CapabilityRegistry": _get_capability_registry,
        "get_registry": _get_registry_fn,
        "AgentCapability": _get_agent_capability,
        # Intelligence
        "ChainOfThought": _get_chain_of_thought,
        "Metacognition": _get_metacognition,
        "MultiAgentDebate": _get_multi_agent_debate,
        "KnowledgeGraph": _get_knowledge_graph,
        "QualityScorer": _get_quality_scorer,
        "ReActAgent": _get_react_agent,
        "SelfReflection": _get_self_reflection,
        "IntelligentAgent": _get_intelligent_agent,
        # Agent Mesh
        "AgentMesh": _get_agent_mesh,
        "get_agent_mesh": _get_agent_mesh_fn,
        # Knowledge Hub
        "KnowledgeHub": _get_knowledge_hub,
        "get_knowledge_hub": _get_knowledge_hub_fn,
        # Debate Protocol
        "DebateProtocol": _get_debate_protocol,
        "get_debate_protocol": _get_debate_protocol_fn,
        # Meta-Orchestrator
        "MetaOrchestrator": _get_meta_orchestrator,
        "get_meta_orchestrator": _get_meta_orchestrator_fn,
        # Skill Composer
        "SkillComposer": _get_skill_composer,
        "get_skill_composer": _get_skill_composer_fn,
        # Federated Learning
        "FederatedLearning": _get_federated_learning,
        "get_federated_learning": _get_federated_learning_fn,
        # Auto-Healing
        "AutoHealer": _get_auto_healer,
        "get_healer": _get_healer_fn,
        "CircuitBreaker": _get_circuit_breaker,
        # Agent Teams
        "AgentTeam": _get_agent_team,
        "TeamManager": _get_team_manager,
        "get_team_manager": _get_team_manager_fn,
        "spawn_team": _get_spawn_team,
        "auto_team": _get_auto_team,
        # Skill System
        "SkillRegistry": _get_skill_registry,
        "SkillRegistryError": _get_skill_registry_error,
        "SkillRecord": _get_skill_record,
        "SkillRecordLazy": _get_skill_record_lazy,
        "SkillCategory": _get_skill_category,
        "SkillStatus": _get_skill_status,
    }

    if name in _attr_map:
        return _attr_map[name]()

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Flag to check if intelligence layer is available
@lru_cache(maxsize=1)
def _check_intelligence_available() -> bool:
    """Check if intelligence layer modules are available."""
    try:
        _get_chain_of_thought()
        return True
    except ImportError:
        return False


# This is evaluated lazily
INTELLIGENCE_AVAILABLE = property(lambda self: _check_intelligence_available())


# =============================================================================
# __all__ - Public API
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # Health Check
    "check_health",
    "get_module_status",
    "list_available_modules",
    "list_failed_modules",
    "HealthCheckResult",
    "ModuleStatus",
    "ModuleInfo",
    # Core (these trigger lazy loading)
    "AntigravityOrchestrator",
    "SharedMemory",
    "VectorMemory",
    "MemoryBus",
    "get_memory_bus",
    "AntigravityAgent",
    # A2A
    "A2AProtocol",
    "AgentCard",
    "AgentMessageBus",
    "get_message_bus",
    # Telemetry
    "setup_telemetry",
    # Execution
    "ExecutionEngine",
    "ExecutionPlan",
    "ExecutionReport",
    "AgentResult",
    "run_task",
    "run_task_sync",
    "get_engine",
    "TaskType",
    "ExecutionStatus",
    # Feedback
    "FeedbackCollector",
    "get_feedback_collector",
    "AutonomousLearningPipeline",
    "get_learning_pipeline",
    "LearningType",
    "FeedbackType",
    # Gateway
    "AntigravityGateway",
    "GatewayConfig",
    "create_gateway",
    "ChannelRouter",
    "Platform",
    "UnifiedMessage",
    "create_router",
    "quick_connect",
    # Cost
    "CostTracker",
    "get_tracker",
    "CostReport",
    # Capability
    "CapabilityRegistry",
    "get_registry",
    "AgentCapability",
    # Intelligence
    "ChainOfThought",
    "Metacognition",
    "MultiAgentDebate",
    "KnowledgeGraph",
    "QualityScorer",
    "ReActAgent",
    "SelfReflection",
    "IntelligentAgent",
    "INTELLIGENCE_AVAILABLE",
    # Agent Mesh
    "AgentMesh",
    "get_agent_mesh",
    # Knowledge Hub
    "KnowledgeHub",
    "get_knowledge_hub",
    # Debate Protocol
    "DebateProtocol",
    "get_debate_protocol",
    # Meta-Orchestrator
    "MetaOrchestrator",
    "get_meta_orchestrator",
    # Skill Composer
    "SkillComposer",
    "get_skill_composer",
    # Skill Record & Registry (Phase 1 Consolidation)
    "SkillRecord",
    "SkillRecordLazy",
    "SkillRegistry",
    "SkillRegistryError",
    "SkillCategory",
    "SkillStatus",
    # Federated Learning
    "FederatedLearning",
    "get_federated_learning",
    # Auto-Healing
    "AutoHealer",
    "get_healer",
    "CircuitBreaker",
]
