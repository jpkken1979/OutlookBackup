"""
Antigravity SDK - Tools for developing skills, agents, and connecting to the gateway.

Usage:
    from antigravity.sdk.client import Client
    client = Client()
    result = client.run("explorer", "analizar codebase")

    from antigravity.sdk import SkillBuilder, create_agent
"""

from typing import Any

# Client (stdlib only - always available)
from .client import (
    AgentInfo,
    AgentMatch,
    AgentRunResult,
    AntigravityError,
    AuthenticationError,
    AutonomousResult,
    Client,
    CostReport,
    GatewayConnectionError,
    GatewayInfo,
    GatewayTimeoutError,
    HealthStatus,
    HistoryEntry,
    NotFoundError,
    PaginatedResult,
    RateLimitError,
    ReadinessStatus,
    ServerError,
    SkillDetail,
    SkillInfo,
    TeamInfo,
    TeamMessageResult,
    ValidationError,
)


# Builders (require pydantic - lazy import)
def __getattr__(name: str) -> Any:
    """Lazy import for builder modules that require pydantic."""
    if name in ("SkillBuilder", "create_skill"):
        from .skill_builder import SkillBuilder, create_skill

        globals()["SkillBuilder"] = SkillBuilder
        globals()["create_skill"] = create_skill
        return globals()[name]
    if name in ("AgentBuilder", "create_agent"):
        from .agent_builder import AgentBuilder, create_agent

        globals()["AgentBuilder"] = AgentBuilder
        globals()["create_agent"] = create_agent
        return globals()[name]
    if name in ("validate_skill", "validate_agent"):
        from .validators import validate_agent, validate_skill

        globals()["validate_skill"] = validate_skill
        globals()["validate_agent"] = validate_agent
        return globals()[name]
    if name in ("PluginManager",):
        from core.plugin_manager import PluginManager

        globals()["PluginManager"] = PluginManager
        return globals()[name]
    if name in ("PluginRegistry",):
        from core.plugin_registry import PluginRegistry

        globals()["PluginRegistry"] = PluginRegistry
        return globals()[name]
    raise AttributeError(f"module 'antigravity.sdk' has no attribute {name!r}")


__all__ = [
    # Client SDK (stdlib only)
    "Client",
    "AgentInfo",
    "AgentMatch",
    "AgentRunResult",
    "AutonomousResult",
    "CostReport",
    "GatewayInfo",
    "HealthStatus",
    "HistoryEntry",
    "ReadinessStatus",
    "SkillInfo",
    "SkillDetail",
    "TeamInfo",
    "TeamMessageResult",
    "PaginatedResult",
    "AntigravityError",
    "AuthenticationError",
    "GatewayConnectionError",
    "GatewayTimeoutError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    # Builders (require pydantic)
    "SkillBuilder",
    "AgentBuilder",
    "create_skill",
    "create_agent",
    "validate_skill",
    "validate_agent",
    # Plugin management (require pydantic)
    "PluginManager",
    "PluginRegistry",
]
