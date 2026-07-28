"""
Memory Systems for Antigravity Agents

This package provides advanced memory capabilities:
- DualStreamMemory: MAGMA-inspired dual-stream (observations/reasoning)
- TemporalKnowledgeGraph: Graphiti-style temporal knowledge graph
- UnifiedMemory: Facade over all memory systems
"""

from .dual_stream import (
    DualStreamMemory,
    FusedResult,
    MemoryEntry,
    MemoryStream,
    StreamType,
    get_dual_stream_memory,
)
from .temporal_graph import (
    Entity,
    EntityType,
    Episode,
    Relation,
    RelationType,
    TemporalKnowledgeGraph,
    TemporalQuery,
    get_temporal_graph,
)
from .unified_memory import MemoryType, UnifiedMemory, UnifiedMemoryResult, get_unified_memory

__all__ = [
    # DualStream (MAGMA)
    "DualStreamMemory",
    "MemoryStream",
    "MemoryEntry",
    "FusedResult",
    "StreamType",
    "get_dual_stream_memory",
    # TemporalGraph (Graphiti)
    "TemporalKnowledgeGraph",
    "Entity",
    "Relation",
    "Episode",
    "EntityType",
    "RelationType",
    "TemporalQuery",
    "get_temporal_graph",
    # UnifiedMemory
    "UnifiedMemory",
    "UnifiedMemoryResult",
    "MemoryType",
    "get_unified_memory",
]
