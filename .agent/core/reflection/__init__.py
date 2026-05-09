"""
Active Reflection System for Antigravity Agents

This package provides MARS-inspired active reflection capabilities:
- ActiveReflection: Real-time reflection during task execution
- ReflectionCheckpoint: Configurable reflection points
- StrategyAdjustment: Dynamic strategy modifications
"""

from .active_reflection import (
    ActiveReflection,
    ReflectionCheckpoint,
    ReflectionSession,
    StrategyAdjustment,
    get_active_reflection,
)

__all__ = [
    "ActiveReflection",
    "ReflectionCheckpoint",
    "ReflectionSession",
    "StrategyAdjustment",
    "get_active_reflection",
]
