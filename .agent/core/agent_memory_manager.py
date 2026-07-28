"""Agent Memory Manager - Manages agent memory and context retrieval.

DEPRECATED (Ola 2b parte 1, 2026-04-18):
    AgentMemoryManager es un wrapper trivial sobre `agent.memory` (3 metodos
    delegados: remember/recall/get_relevant_context). El canonico del ecosistema
    es `core.memory.unified_memory.UnifiedMemory` (facade async-first con
    MemoryType, cross-system query y stats unificados).

    Este modulo se mantiene por compatibilidad con `core.agent_base.AntigravityAgent`
    y sera eliminado en Ola 2b parte 2 una vez que `agent_base` migre a
    `UnifiedMemory` directamente.

    Migracion sugerida:
        from core.memory.unified_memory import get_unified_memory, MemoryType
        unified = get_unified_memory()
        await unified.store_context(key=..., value=..., agent=...)
        results = await unified.query(..., memory_types=[MemoryType.CONTEXT])

Provides:
- Store/recall memory entries (delega a `self.agent.memory`)
- Vector similarity search for context (delega a `self.agent.memory.search`)

Version: 1.0.1 (deprecated wrapper)
"""

import logging
import warnings
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_base import AntigravityAgent

logger = logging.getLogger("antigravity.memory")


class AgentMemoryManager:
    """Gestiona memoria y contexto del agente.

    .. deprecated::
        Usar `core.memory.unified_memory.UnifiedMemory` directamente.
        Este wrapper trivial delega a ``self.agent.memory`` y sera eliminado
        en Ola 2b parte 2 del refactor de memoria.
    """

    def __init__(self, agent_instance: "AntigravityAgent"):
        """Initialize memory manager with agent instance."""
        warnings.warn(
            "AgentMemoryManager is deprecated; use "
            "core.memory.unified_memory.UnifiedMemory via get_unified_memory() instead. "
            "Scheduled for removal in Ola 2b part 2.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.agent = agent_instance
        logger.debug(f"MemoryManager initialized for {agent_instance.identity.name}")

    def remember(self, key: str, value: Any) -> None:
        """
        Store something in agent's memory.

        Args:
            key: Memory key/identifier
            value: Value to store
        """
        if self.agent.memory and hasattr(self.agent.memory, "store"):
            self.agent.memory.store(
                "agent_memory", {"key": key, "value": value, "agent": self.agent.identity.name}
            )
            logger.debug(f"Stored memory: {key}")

    def recall(self, key: str) -> Any | None:
        """
        Recall something from agent's memory.

        Args:
            key: Memory key to retrieve

        Returns:
            Stored value or None if not found
        """
        if self.agent.memory and hasattr(self.agent.memory, "retrieve"):
            results = self.agent.memory.retrieve("agent_memory", query=key)
            for result in results:
                if result.get("data", {}).get("key") == key:
                    logger.debug(f"Recalled memory: {key} for {self.agent.identity.name}")
                    return result["data"].get("value")
        logger.debug(f"Memory miss: {key} for {self.agent.identity.name}")
        return None

    def get_relevant_context(self, query: str, limit: int = 5) -> list[str]:
        """
        Get relevant context from vector memory.

        Args:
            query: Search query for semantic similarity
            limit: Maximum number of results to return

        Returns:
            List of relevant context strings
        """
        if self.agent.memory and hasattr(self.agent.memory, "search"):
            results = self.agent.memory.search(query, limit=limit)
            context = [r.get("content", "") for r in results]
            logger.debug(
                f"Retrieved {len(context)} context items for query '{query}' by {self.agent.identity.name}"
            )
            return context
        logger.debug(f"No memory backend available for {self.agent.identity.name}")
        return []
