"""Agent metadata discovery and parsing utilities.

Provides utilities for discovering agents from IDENTITY.md files,
parsing both YAML frontmatter and Markdown-formatted metadata.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.agent_discovery")

# Import locally to avoid circular dependency
# AgentConfig is imported at function level where needed


def _parse_markdown_metadata(content: str) -> dict[str, Any]:
    """Extract agent metadata from Markdown content (non-YAML format).

    Parses patterns like **Nombre:** value, **Rol:** value, **Tier:** value
    from IDENTITY.md files that lack YAML frontmatter.

    Args:
        content: Raw Markdown content of the IDENTITY.md file.

    Returns:
        Dictionary with extracted metadata fields.
    """
    metadata: dict[str, Any] = {}

    # Extract **Nombre:** or **Name:** value
    name_match = re.search(r"\*\*(?:Nombre|Name)[:\s]*\*\*\s*(.+)", content, re.IGNORECASE)
    if name_match:
        metadata["name"] = name_match.group(1).strip()

    # Extract **Rol:** or **Role:** value
    role_match = re.search(r"\*\*(?:Rol|Role)[:\s]*\*\*\s*(.+)", content, re.IGNORECASE)
    if role_match:
        metadata["role"] = role_match.group(1).strip()

    # Extract **Tier:** value from various formats:
    # "**Tier:** 3 (Calidad)", "- **Tier**: 2 (Desarrollo)", "> **Tier:** 2 | ..."
    tier_match = re.search(r"\*\*Tier[:\s]*\*\*[:\s]*(\d+)", content, re.IGNORECASE)
    if tier_match:
        metadata["tier"] = int(tier_match.group(1))

    # Extraer description del formato inline: "- **Description:** texto"
    inline_desc_match = re.search(
        r"\*\*(?:Description|Descripci[oó]n|Goal|Objetivo)[:\s]*\*\*\s*(.+)",
        content,
        re.IGNORECASE,
    )
    if inline_desc_match:
        metadata["description"] = inline_desc_match.group(1).strip()[:300]

    # Extract description from common heading patterns in IDENTITY.md files
    purpose_match = re.search(
        r"##\s*(?:Prop[oó]sito|Objetivos?|Purpose|Mission|Goal|Perfil|Rol"
        r"|Description|Identidad)\s*\n+(.+?)(?:\n\n|\n##)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if purpose_match:
        desc = purpose_match.group(1).strip()
        # Clean markdown formatting
        desc = re.sub(r"\*\*|__", "", desc)
        desc = re.sub(r"\n\d+\.\s+", " ", desc)
        metadata["description"] = desc[:300]

    # Extract tools from markdown tables or lists
    tools_section = re.search(
        r"##\s*(?:Tools|Herramientas|Stack)[^\n]*\n(.*?)(?:\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if tools_section:
        tools_text = tools_section.group(1)
        tools = re.findall(r"`([^`]+)`", tools_text)
        if tools:
            metadata["tools"] = tools[:10]

    # Extract skills from Skills section (various naming conventions)
    skills_section = re.search(
        r"##\s*(?:Skills?|Capacidades|Capabilities|Skills?\s+Asociad[ao]s?"
        r"|Skills?\s+Utilizad[ao]s?)[^\n]*\n(.*?)(?:\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if skills_section:
        skills_text = skills_section.group(1)
        skills = re.findall(r"`([^`]+)`", skills_text)
        if skills:
            metadata["skills"] = skills[:20]

    return metadata


def _parse_identity_frontmatter(content: str, agent_name: str) -> tuple[dict[str, Any], str]:
    """Parsea el frontmatter YAML de un IDENTITY.md.

    Args:
        content: Contenido completo del archivo.
        agent_name: Nombre del agente (para logs).

    Returns:
        Tupla (metadata_dict, markdown_body).
    """
    metadata: dict[str, Any] = {}
    markdown_body = content

    if not content.startswith("---"):
        return metadata, markdown_body

    parts = content.split("---", 2)
    if len(parts) < 3:
        return metadata, markdown_body

    import yaml  # type: ignore[import-untyped]  # lazy import

    try:
        yaml_data = yaml.safe_load(parts[1])
    except yaml.YAMLError as yaml_err:
        logger.warning("YAML inválido en IDENTITY.md de agente %s: %s", agent_name, yaml_err)
        yaml_data = None

    if isinstance(yaml_data, dict):
        metadata = yaml_data
    markdown_body = parts[2]
    return metadata, markdown_body


def _resolve_agent_metadata(
    metadata: dict[str, Any],
    markdown_body: str,
    agent_name: str,
    agent_config_class: type | None = None,
) -> Any:  # Returns AgentConfig instance
    """Construye AgentConfig a partir de metadata parseada.

    Args:
        metadata: Dict con campos del agente.
        markdown_body: Cuerpo Markdown del IDENTITY.md.
        agent_name: Nombre del directorio del agente.
        agent_config_class: AgentConfig class. If None, imports late to avoid circular dependency.

    Returns:
        AgentConfig construido.
    """
    if agent_config_class is None:
        # Late import only if needed (helps avoid circular imports)
        from .orchestrator import AgentConfig as agent_config_class
    assert agent_config_class is not None  # mypy narrowing

    # Resolve tier
    tier = metadata.get("tier", 5)
    if isinstance(tier, str):
        tier_digits = re.search(r"\d+", str(tier))
        tier = int(tier_digits.group()) if tier_digits else 5
    tier = max(1, min(6, int(tier)))

    role = metadata.get("role", metadata.get("description", agent_name.replace("-", " ").title()))

    # Resolve list-or-string fields
    raw_skills = metadata.get("skills", [])
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",")]
    raw_tools = metadata.get("tools", [])
    if isinstance(raw_tools, str):
        raw_tools = [t.strip() for t in raw_tools.split(",")]

    goal = metadata.get("goal", metadata.get("description", ""))
    if not goal:
        first_para = re.search(r"(?:^|\n)(?!#)([A-Z\u00C0-\u024F].{20,})", markdown_body)
        if first_para:
            goal = first_para.group(1).strip()[:300]

    backstory = metadata.get("backstory", "")
    if not backstory and metadata.get("description"):
        backstory = metadata["description"]
    if not backstory and goal:
        backstory = goal

    return agent_config_class(
        name=agent_name,
        tier=tier,
        role=role,
        goal=goal,
        backstory=backstory,
        skills=raw_skills,
        tools=raw_tools,
    )


def _discover_agents(
    agents_dir: Path | None = None, agent_config_class: type | None = None
) -> dict[str, Any]:  # Returns dict[str, AgentConfig]
    """Auto-discover agents from IDENTITY.md files.

    Scans .agent/agents/ directory for IDENTITY.md files and creates
    AgentConfig entries automatically. Supports two formats:

    1. YAML frontmatter (between --- markers) with fields like name, tier,
       description, tools, skills.
    2. Markdown-only format with **Nombre:**, **Rol:**, **Tier:** patterns.

    Falls back to hardcoded registry if discovery fails or finds no agents.

    Args:
        agents_dir: Directory containing agent subdirectories.
            Defaults to .agent/agents/ relative to this file.
        agent_config_class: AgentConfig class. If None, imports late.

    Returns:
        Dictionary mapping agent names to AgentConfig instances.
    """
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent / "agents"

    discovered: dict[str, Any] = {}
    if not agents_dir.exists():
        logger.warning("Agents directory not found: %s", agents_dir)
        return discovered

    deprecated_agent_names = {"project-planner", "qa-automation-engineer", "qa-specialist"}

    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith(("_", ".")):
            continue
        if agent_dir.name in deprecated_agent_names:
            logger.debug("Skipping deprecated agent in registry: %s", agent_dir.name)
            continue
        identity_file = agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            continue
        try:
            content = identity_file.read_text(encoding="utf-8")
            metadata, markdown_body = _parse_identity_frontmatter(content, agent_dir.name)

            md_metadata = _parse_markdown_metadata(markdown_body)
            for key, value in md_metadata.items():
                if key not in metadata:
                    metadata[key] = value

            if not metadata:
                logger.debug("No metadata found for agent %s", agent_dir.name)
                continue

            discovered[agent_dir.name] = _resolve_agent_metadata(
                metadata, markdown_body, agent_dir.name, agent_config_class
            )
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to discover agent %s: %s", agent_dir.name, e)

    if discovered:
        logger.info("Auto-discovered %d agents from %s", len(discovered), agents_dir)
    return discovered
