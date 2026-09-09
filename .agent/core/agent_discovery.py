"""Adaptador compatible del módulo canónico de discovery del orquestador.

La implementación vive en :mod:`core.orchestrator.discovery`. Este módulo se
mantiene para quienes todavía usan el import histórico
``core.agent_discovery``.
"""

import logging
from pathlib import Path
from typing import Any

if __package__:
    from .orchestrator.discovery import (
        _discover_agents as _canonical_discover_agents,
        _discover_single_agent as _canonical_discover_single_agent,
        _parse_identity_frontmatter,
        _parse_markdown_metadata,
        _resolve_agent_metadata as _canonical_resolve_agent_metadata,
    )
    from .orchestrator.models import AgentConfig
else:  # Legacy: `.agent/core` directly on sys.path.
    import sys

    agent_root = str(Path(__file__).resolve().parent.parent)
    if agent_root not in sys.path:
        sys.path.insert(0, agent_root)

    from core.orchestrator.discovery import (  # type: ignore[no-redef]
        _discover_agents as _canonical_discover_agents,
        _discover_single_agent as _canonical_discover_single_agent,
        _parse_identity_frontmatter,
        _parse_markdown_metadata,
        _resolve_agent_metadata as _canonical_resolve_agent_metadata,
    )
    from core.orchestrator.models import AgentConfig  # type: ignore[no-redef]

logger = logging.getLogger("antigravity.agent_discovery")


def _adapt_agent_config(config: AgentConfig, agent_config_class: type | None) -> Any:
    """Convierte una config canónica para el factory inyectable legado."""
    if agent_config_class is None or agent_config_class is AgentConfig:
        return config

    return agent_config_class(
        name=config.name,
        tier=config.tier,
        role=config.role,
        goal=config.goal,
        backstory=config.backstory,
        skills=config.skills,
        tools=config.tools,
    )


def _resolve_agent_metadata(
    metadata: dict[str, Any],
    markdown_body: str,
    agent_name: str,
    agent_config_class: type | None = None,
) -> Any:
    """Delega la resolución preservando el argumento factory legado."""
    config = _canonical_resolve_agent_metadata(metadata, markdown_body, agent_name)
    return _adapt_agent_config(config, agent_config_class)


def _discover_agents(
    agents_dir: Path | None = None, agent_config_class: type | None = None
) -> dict[str, Any]:
    """Delega discovery preservando el argumento factory legado."""
    discovered = _canonical_discover_agents(agents_dir)
    if agent_config_class is None or agent_config_class is AgentConfig:
        return discovered

    adapted: dict[str, Any] = {}
    for name, config in discovered.items():
        try:
            adapted[name] = _adapt_agent_config(config, agent_config_class)
        except (OSError, ValueError, KeyError, TypeError) as error:
            logger.warning("Failed to adapt discovered agent %s: %s", name, error)
    return adapted


def _discover_single_agent(
    agent_dir: Path, agent_config_class: type | None, deprecated: set[str]
) -> tuple[str, Any] | None:
    """Delega un agente con el orden histórico de argumentos."""
    result = _canonical_discover_single_agent(agent_dir, deprecated)
    if result is None:
        return None

    name, config = result
    try:
        return name, _adapt_agent_config(config, agent_config_class)
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("Failed to adapt discovered agent %s: %s", name, error)
        return None


__all__ = [
    "_discover_agents",
    "_discover_single_agent",
    "_parse_identity_frontmatter",
    "_parse_markdown_metadata",
    "_resolve_agent_metadata",
]
