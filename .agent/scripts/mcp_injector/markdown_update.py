"""Markdown update functions for the MCP injector.

Extracts and centralises all markdown document update logic from mcp_injector.py.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir, read_json_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirrored from mcp_injector.py)
# ---------------------------------------------------------------------------

ECOSYSTEM_VERSION: str
"""Ecosystem version, read lazily from VERSION file."""
DEFAULT_GATEWAY_URL = "http://localhost:4747"


def _read_ecosystem_version() -> str:
    """Lee la version desde .agent/VERSION o VERSION en la raiz del repo."""
    # .agent/scripts/mcp_injector/markdown_update.py → .agent/scripts/mcp_injector
    # parent x3 = raiz de .agent/, no raiz del repo
    script_dir = Path(__file__).resolve().parent  # mcp_injector/
    agent_dir = script_dir.parent.parent  # .agent/
    # Buscar VERSION en .agent/ primero, luego en raiz del repo
    for candidate in [
        agent_dir / "VERSION",  # .agent/VERSION
        agent_dir.parent / "VERSION",  # REPO_ROOT/VERSION
    ]:
        try:
            version = candidate.read_text(encoding="utf-8").strip()
            if version:
                return version
        except OSError:
            continue
    return "6.0.0"


ECOSYSTEM_VERSION = _read_ecosystem_version()

# ---------------------------------------------------------------------------
# Markdown section helpers
# ---------------------------------------------------------------------------


def update_markdown_section(
    path: Path,
    start_marker: str,
    end_marker: str,
    section: str,
) -> bool:
    """Inserta o reemplaza una seccion delimitada por marcadores."""
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error(f"❌ [Docs] Error leyendo {path}: {exc}")
            return False

    if start_marker in existing and end_marker in existing:
        start_idx = existing.index(start_marker)
        end_idx = existing.index(end_marker) + len(end_marker)
        new_content = existing[:start_idx].rstrip() + "\n\n" + section + "\n"
        if end_idx < len(existing):
            new_content += existing[end_idx:].lstrip("\n")
    else:
        separator = "\n\n---\n\n" if existing.strip() else ""
        new_content = existing.rstrip() + separator + section + "\n"

    try:
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception as exc:
        logger.error(f"❌ [Docs] Error escribiendo {path}: {exc}")
        return False


def update_claude_md(target_dir: Path, project_type: str) -> bool:
    """Crea o actualiza CLAUDE.md con la seccion de integracion Antigravity."""
    start = "<!-- ANTIGRAVITY-START -->"
    end = "<!-- ANTIGRAVITY-END -->"
    sdk_blocks: list[str] = []
    if project_type in ("python", "mixed"):
        sdk_blocks.append(
            """### SDK Python

```python
from .antigravity.sdk.client import Client
client = Client()
result = client.run("explorer", "analiza el repo")
```"""
        )
    if project_type in ("js", "mixed"):
        sdk_blocks.append(
            """### SDK JS/TS

```js
import { runAgent } from "./.antigravity/sdk/antigravity.js";
const result = await runAgent("explorer", "analiza el repo");
```"""
        )

    persona_mode = os.environ.get("ANTIGRAVITY_PERSONA", "gentleman")
    section = f"""{start}

## Integracion Antigravity

Proyecto integrado con **Antigravity v{ECOSYSTEM_VERSION}**.
Instalado por Nexus el {datetime.now().strftime("%Y-%m-%d")}.

### Persona activa: {persona_mode}

El estilo de comunicacion de la IA se adapta segun el modo de persona.
Modos disponibles: `gentleman` (detallado, pedagogico), `neutral` (factual),
`conciso` (minimalista). Configurar via `ANTIGRAVITY_PERSONA` env var o
`.antigravity/config.json`. Ver `.claude/rules/persona.md` para detalles.

### Runtime MCP-first

```
.agent/
  agents/ skills/ skills-custom/ workflows/
  scripts/ core/ mcp/ plugins/
.claude/
  settings.json hooks/ rules/
.antigravity/
  config.json sdk/ ai_manifest.json rules.md
```

### Clientes compatibles

- Claude Code: `.claude/settings.json` + `.mcp.json`
- Cursor: `.cursor/mcp.json` + `.cursorrules`
- Windsurf: `.windsurf/mcp.json` + `.windsurfrules`
- VS Code / Roo / Cline: `.vscode/mcp.json` y `.vscode/cline_mcp_settings.json`
- Zed: `.zed/settings.json`
- Cualquier IA/IDE con MCP: `.mcp.json` y `.antigravity/ai_manifest.json`

### SDK

{chr(10).join(sdk_blocks) if sdk_blocks else "_Ningun SDK configurado para este tipo de proyecto._"}

### Memoria

- Memoria MCP: `antigravity-memory` (mem0)
- Memoria de proyecto: `ESTADO_PROYECTO.md`
- Reglas compartidas: `.claude/rules/` y `.antigravity/rules.md`

{end}"""
    ok = update_markdown_section(target_dir / "CLAUDE.md", start, end, section)
    if ok:
        logger.info("✅ [CLAUDE.md] Integracion actualizada")
    return ok


def update_agents_md(target_dir: Path) -> bool:
    """Crea o actualiza AGENTS.md con una seccion de integracion portable."""
    start = "<!-- ANTIGRAVITY-AGENTS-START -->"
    end = "<!-- ANTIGRAVITY-AGENTS-END -->"
    section = f"""{start}

## Integracion Antigravity

- Runtime local: `.agent/` contiene agentes, skills, workflows, core y servidores MCP.
- Claude Code: usa `.claude/settings.json` en modo ligero y resuelve capacidades por MCP.
- Codex: usa `AGENTS.md` del repo y, si el inyector detecta Codex, sincroniza skills curadas, skills propias de Antigravity y comandos portables como `finalize` en `~/.codex/skills`.
- MiniMax: si detectamos Claude Code o Codex, el inyector puede integrar también las skills oficiales de `MiniMax-AI/skills`.
- MCP universal: revisa `.mcp.json`, `.cursor/mcp.json`, `.windsurf/mcp.json`, `.vscode/mcp.json` y `.zed/settings.json`.
- Memoria: `antigravity-memory` (mem0) y la memoria del proyecto en `ESTADO_PROYECTO.md`.
- Reglas compartidas: `RULES.md`, `WORKFLOW_RULES.md`, `.antigravity/rules.md`.

{end}"""
    ok = update_markdown_section(target_dir / "AGENTS.md", start, end, section)
    if ok:
        logger.info("✅ [AGENTS.md] Integracion actualizada")
    return ok


# ---------------------------------------------------------------------------
# IDE rules generation
# ---------------------------------------------------------------------------


def generate_ide_rules(target_dir: Path, repo_root: Path) -> None:
    """Genera .cursorrules, .windsurfrules y .clinerules con valores dinamicos del ecosistema."""
    # Count agents (excluding _deprecated), preferring target_dir if already populated
    agents_dir = target_dir / ".agent" / "agents"
    if not agents_dir.exists():
        agents_dir = repo_root / ".agent" / "agents"
    num_agents = 0
    if agents_dir.exists():
        num_agents = sum(1 for d in agents_dir.iterdir() if d.is_dir() and d.name != "_deprecated")

    # Count skills
    skills_dir = target_dir / ".agent" / "skills"
    if not skills_dir.exists():
        skills_dir = repo_root / ".agent" / "skills"
    num_skills = 0
    if skills_dir.exists():
        num_skills = sum(
            1 for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")
        )

    # Read gateway URL from config, falling back to default
    gateway_url = DEFAULT_GATEWAY_URL
    for config_path in [
        target_dir / ".antigravity" / "config.json",
        repo_root / ".antigravity" / "config.json",
    ]:
        if config_path.exists():
            try:
                cfg = read_json_file(config_path)
                gateway_url = cfg.get("gateway", DEFAULT_GATEWAY_URL)
                break
            except Exception:
                pass

    mcp_servers_list = (
        "antigravity, antigravity-agents, antigravity-skills, "
        "antigravity-observations, antigravity-intelligence, "
        "antigravity-ui, antigravity-memory, stitch"
    )

    rules_content = f"""# Antigravity Ecosystem Rules

This project uses **Antigravity v{ECOSYSTEM_VERSION}** — a modular AI runtime
with {num_agents} active agents and {num_skills} skills.

## MCP Gateway

- Local gateway: `{gateway_url}` (localhost:4747)
- Active MCP servers: {mcp_servers_list}

## Agent Protocol

1. Read `.agent/agents/<name>/SYSTEM_PROMPT.md` before delegating tasks.
2. Use the MCP server `antigravity-agents` to invoke agents via the gateway.
3. Use `antigravity-skills` to load modular skills on demand.

## Key Directories

- `.agent/agents/`   — {num_agents} agents (tier 1–7)
- `.agent/skills/`   — {num_skills} skills
- `.agent/workflows/` — multi-agent orchestration workflows
- `.antigravity/`    — config, manifest, rules, SDK
- `.mcp.json`        — MCP server configuration

## Rules

- Always prefer agent-delegated tasks over inline code for complex operations.
- Read `ESTADO_PROYECTO.md` for current project memory before starting work.
- Respect `.antigravity/rules.md` and `.claude/rules/` for project-specific constraints.
"""

    rule_files = [
        target_dir / ".cursorrules",
        target_dir / ".windsurfrules",
        target_dir / ".clinerules",
    ]
    _TAG_START = "<!-- ANTIGRAVITY-RULES-START -->"
    _TAG_END = "<!-- ANTIGRAVITY-RULES-END -->"
    wrapped_content = f"{_TAG_START}\n{rules_content}\n{_TAG_END}"
    for rule_file in rule_files:
        try:
            if rule_file.exists():
                existing = rule_file.read_text(encoding="utf-8")
                if _TAG_START in existing and _TAG_END in existing:
                    start_idx = existing.index(_TAG_START)
                    end_idx = existing.index(_TAG_END) + len(_TAG_END)
                    new_text = existing[:start_idx] + wrapped_content + existing[end_idx:]
                else:
                    new_text = existing + f"\n---\n{wrapped_content}"
            else:
                new_text = wrapped_content
            rule_file.write_text(new_text, encoding="utf-8")
            logger.info(
                f"✅ [Reglas] {rule_file.name} generado "
                f"({num_agents} agentes, {num_skills} skills, gateway={gateway_url})"
            )
        except Exception as exc:
            logger.error(f"❌ [Reglas] No se pudo escribir {rule_file.name}: {exc}")


# ---------------------------------------------------------------------------
# Copilot instructions
# ---------------------------------------------------------------------------


def install_copilot_instructions(target_dir: Path, repo_root: Path) -> bool:
    """Escribe .github/copilot-instructions.md con contexto del ecosistema Antigravity."""
    # Group agents by tier (reading agent.json from repo_root)
    agents_dir = repo_root / ".agent" / "agents"
    tiers: dict[int, list[str]] = {}
    unlisted: list[str] = []

    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name == "_deprecated":
                continue
            cfg_path = agent_dir / "agent.json"
            if cfg_path.exists():
                try:
                    cfg = read_json_file(cfg_path)
                    tier = int(cfg.get("tier", 0))
                    tiers.setdefault(tier, []).append(agent_dir.name)
                except Exception:
                    unlisted.append(agent_dir.name)
            else:
                unlisted.append(agent_dir.name)

    num_agents = sum(len(v) for v in tiers.values()) + len(unlisted)

    # Read gateway URL
    gateway_url = DEFAULT_GATEWAY_URL
    for config_path in [
        target_dir / ".antigravity" / "config.json",
        repo_root / ".antigravity" / "config.json",
    ]:
        if config_path.exists():
            try:
                cfg = read_json_file(config_path)
                gateway_url = cfg.get("gateway", DEFAULT_GATEWAY_URL)
                break
            except Exception:
                pass

    # Build tier sections
    tier_lines: list[str] = []
    for tier_num in sorted(tiers.keys()):
        tier_lines.append(f"\n### Tier {tier_num}")
        for agent_name in tiers[tier_num]:
            tier_lines.append(f"- `{agent_name}`")
    if unlisted:
        tier_lines.append(f"\n### Specialized / No-tier ({len(unlisted)} agents)")
        for agent_name in unlisted[:10]:
            tier_lines.append(f"- `{agent_name}`")
        if len(unlisted) > 10:
            tier_lines.append(f"- _(and {len(unlisted) - 10} more — see `.agent/agents/`)_")

    agent_section = "\n".join(tier_lines)

    content = f"""<!-- ANTIGRAVITY-START -->
# GitHub Copilot Instructions — Antigravity Ecosystem

This workspace runs **Antigravity v{ECOSYSTEM_VERSION}** with {num_agents} agents
and a modular MCP runtime. Installed by Nexus on {datetime.now().strftime("%Y-%m-%d")}.

## Gateway & MCP Servers

- Local gateway: `{gateway_url}` (port 4747)
- Core servers: `antigravity`, `antigravity-agents`, `antigravity-skills`,
  `antigravity-observations`, `antigravity-intelligence`, `antigravity-ui`
- Memory: `antigravity-memory` (mem0)
- Dev tools: `stitch`, `context7`, `git`, `filesystem`

## Agent Tiers
{agent_section}

## Key Entry Points

- `.mcp.json` — MCP server config (auto-generated, all IDEs)
- `.antigravity/config.json` — ecosystem config (gateway, version, policy)
- `.antigravity/ai_manifest.json` — machine-readable manifest for AI tools
- `.antigravity/rules.md` — project-specific rules
- `ESTADO_PROYECTO.md` — project memory (read before starting work)
- `.agent/agents/` — all agents (read `SYSTEM_PROMPT.md` per agent)
- `.agent/skills/` — modular skills library

## Workflow

1. For complex tasks, delegate to the appropriate agent via MCP `antigravity-agents`.
2. For skill-based work, use `antigravity-skills` to load the relevant skill.
3. Read `ESTADO_PROYECTO.md` before starting any session.
4. Respect constraints in `.antigravity/rules.md` and `.claude/rules/`.
<!-- ANTIGRAVITY-END -->
"""

    github_dir = target_dir / ".github"
    ensure_dir(github_dir)
    out_path = github_dir / "copilot-instructions.md"
    _TAG_START = "<!-- ANTIGRAVITY-START -->"
    _TAG_END = "<!-- ANTIGRAVITY-END -->"
    try:
        if out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            if _TAG_START in existing and _TAG_END in existing:
                start_idx = existing.index(_TAG_START)
                end_idx = existing.index(_TAG_END) + len(_TAG_END)
                final_content = existing[:start_idx] + content + existing[end_idx:]
            else:
                final_content = existing + f"\n---\n{content}"
        else:
            final_content = content
        out_path.write_text(final_content, encoding="utf-8")
        logger.info("✅ [Copilot] .github/copilot-instructions.md generado")
        return True
    except Exception as exc:
        logger.error(f"❌ [Copilot] No se pudo escribir copilot-instructions.md: {exc}")
        return False


# ---------------------------------------------------------------------------
# Smart merge and conflict detection
# ---------------------------------------------------------------------------

_MD_EXTENSIONS = {".md"}


def parse_markdown_sections(content: str) -> dict[str, str]:
    """Divide un archivo markdown en secciones delimitadas por cabeceras ``##``.

    Args:
        content: Contenido completo del archivo markdown.

    Returns:
        Diccionario ``{header: body}`` donde *header* incluye el texto tras
        ``## `` y *body* es todo el contenido hasta la siguiente cabecera o
        el final del archivo.  El contenido previo a la primera cabecera se
        almacena bajo la clave ``"__preamble__"``.
    """
    sections: dict[str, str] = {}
    current_key = "__preamble__"
    buffer: list[str] = []

    for line in content.splitlines(keepends=True):
        if line.startswith("## "):
            sections[current_key] = "".join(buffer)
            current_key = line.strip().removeprefix("## ").strip()
            buffer = [line]
        else:
            buffer.append(line)

    sections[current_key] = "".join(buffer)
    return sections


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extrae el frontmatter YAML delimitado por ``---`` al inicio del archivo.

    Args:
        content: Contenido completo del archivo.

    Returns:
        Tupla ``(frontmatter_dict, body)`` donde *frontmatter_dict* es un
        diccionario con los campos YAML y *body* es el resto del contenido.
        Si no hay frontmatter se devuelve un diccionario vacio y el contenido
        original completo.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_idx: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, content

    frontmatter: dict[str, Any] = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()

    body = "\n".join(lines[end_idx + 1 :])
    return frontmatter, body
