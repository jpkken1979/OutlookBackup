"""Markdown update functions for the MCP injector.

Extracts and centralises all markdown document update logic from mcp_injector.py.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .document_envelope import (
    ConcurrentDocumentChangeError,
    ManagedBlockError,
    apply_managed_block_update,
    preview_managed_block_update,
)
from .io_utils import ensure_dir, read_json_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirrored from mcp_injector.py)
# ---------------------------------------------------------------------------

ECOSYSTEM_VERSION: str
"""Ecosystem version, read lazily from VERSION file."""
DEFAULT_GATEWAY_URL = "http://localhost:4747"

# Criterio de conteo: DEBE coincidir con `.agent/scripts/refresh_claude_md.py`,
# fuente canonica de los bloques AUTO de CLAUDE.md. Si divergen, las reglas de
# los IDEs contradicen al CLAUDE.md y un agente externo lee numeros distintos
# segun por donde entre al ecosistema.


def _is_agent_dir(path: Path) -> bool:
    """True si el directorio es un agente real.

    Un agente es un directorio con `IDENTITY.md` (ver
    `.claude/rules/architecture.md`). Contar por ese archivo excluye solo las
    carpetas auxiliares (`_docs`, `_archive`, `__pycache__`, `ce-*`) sin
    mantener blacklists que se desactualizan.

    Args:
        path: Directorio candidato dentro de `.agent/agents/`.

    Returns:
        True si contiene `IDENTITY.md`.
    """
    return path.is_dir() and (path / "IDENTITY.md").is_file()


def _is_skill_dir(path: Path) -> bool:
    """True si el directorio es un skill real (no `_*` ni `__pycache__`).

    Args:
        path: Directorio candidato dentro de `.agent/skills/`.

    Returns:
        False para directorios ocultos o con prefijo `_`.
    """
    return path.is_dir() and not path.name.startswith((".", "_"))


def _read_mcp_servers(target_dir: Path, repo_root: Path) -> list[str]:
    """Lee los servers MCP realmente registrados en `.mcp.json`.

    No hardcodear esta lista: desde la consolidacion del broker (2026-07-27) el
    unico server es `antigravity`, y anunciar los `antigravity-*` granulares
    manda a los IDEs a invocar servidores que no se levantan.

    Args:
        target_dir: Proyecto destino de la inyeccion.
        repo_root: Raiz del ecosistema (fallback).

    Returns:
        Nombres de los servers registrados; lista vacia si no hay `.mcp.json` legible.
    """
    for mcp_path in (target_dir / ".mcp.json", repo_root / ".mcp.json"):
        if not mcp_path.exists():
            continue
        try:
            cfg = read_json_file(mcp_path)
        except Exception as exc:  # noqa: BLE001 - config rota no debe abortar la inyeccion
            logger.warning("[Reglas] .mcp.json ilegible (%s): %s", mcp_path, exc)
            continue
        servers = cfg.get("mcpServers")
        if isinstance(servers, dict) and servers:
            return sorted(servers)
    return []


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


def _strip_all_tagged_blocks(content: str, start_marker: str, end_marker: str) -> str:
    """Elimina todos los bloques ``start_marker ... end_marker`` de ``content``.

    Usado cuando un archivo llego corrupto (mas de un par de tags por merge manual
    o doble inyeccion sin dedup). Remueve cada bloque completo INCLUDING los markers
    y devuelve el texto restante, listo para reinsertar una unica seccion limpia.
    """
    result = content
    while start_marker in result and end_marker in result:
        s = result.index(start_marker)
        e = result.index(end_marker, s) + len(end_marker)
        # Colapsar el hueco: si el bloque estaba en su propia linea, dejar un solo \n.
        before = result[:s].rstrip("\n")
        after = result[e:].lstrip("\n")
        result = before + ("\n" if before and after else "") + after
    return result


def update_markdown_section(
    path: Path,
    start_marker: str,
    end_marker: str,
    section: str,
) -> bool:
    """Insert or replace only the marked section, preserving the document envelope."""
    try:
        preview = preview_managed_block_update(
            path,
            start_marker,
            end_marker,
            section,
        )
        apply_managed_block_update(preview)
        return True
    except (OSError, ManagedBlockError, ConcurrentDocumentChangeError) as exc:
        logger.error("❌ [Docs] No se pudo actualizar %s: %s", path, exc)
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
`conciso` (minimalista). Configurar el runtime via `ANTIGRAVITY_PERSONA`.
`personaConfig` en `.antigravity/config.json` es metadata del adaptador y no
reemplaza la variable de entorno. Ver `.claude/rules/persona.md` para detalles.

### Nexus discovery (MCP-first)

- Nexus is the shared control plane. Its small, versioned client adapter lives at
  `.antigravity/nexus-client.json`.
- Discover the live contract through `GET /v1/nexus/manifest`; authenticate only
  through the credential reference declared by the adapter. Never copy a token
  into this document or into generated client configuration.
- Connect through the single MCP broker named `antigravity`. Start with
  `antigravity_search`, inspect with `antigravity_describe`, then run the selected
  agent or skill.
- Agents and skills remain in Nexus and are loaded on demand. Do not bulk-copy
  the catalog into this project. An offline bundle is an explicit opt-in.
- Local and web gateways expose the same adapter contract, so changing transport
  does not change how the client discovers capabilities.

### Clientes compatibles

- Claude Code: `.claude/settings.json` + `.mcp.json`
- Cursor: `.cursor/mcp.json` + `.cursorrules`
- Windsurf: `.windsurf/mcp.json` + `.windsurfrules`
- VS Code / Roo / Cline: `.vscode/mcp.json` y `.vscode/cline_mcp_settings.json`
- Zed: `.zed/settings.json`
- OpenCode: `opencode.json`
- Cualquier IA/IDE con MCP: `.mcp.json` y `.antigravity/nexus-client.json`

### SDK

{chr(10).join(sdk_blocks) if sdk_blocks else "_Ningun SDK configurado para este tipo de proyecto._"}

### Memoria y reglas

- Memoria MCP: se descubre como conector del broker; no es un servidor separado.
- Memoria de proyecto: `ESTADO_PROYECTO.md`
- Reglas efectivas: manifiesto Nexus, reglas globales editables y reglas locales
  del proyecto. Las reglas locales tienen precedencia cuando son mas estrictas.

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

- Nexus es el plano de control compartido. Lee
  `.antigravity/nexus-client.json` y descubre el contrato vigente en
  `GET /v1/nexus/manifest`.
- Usa un solo servidor MCP, `antigravity`. Empieza con
  `antigravity_search`, continua con `antigravity_describe` y ejecuta con
  `antigravity_run_skill`, `antigravity_run_agent` o `antigravity_call`.
- Agentes, skills, memoria y conectores permanecen centralizados en Nexus y se
  cargan bajo demanda. No copies el catalogo completo al proyecto; un bundle
  offline requiere opt-in explicito.
- Claude Code, Codex, OpenCode, Cursor, Windsurf, VS Code, Zed, Continue y Gemini
  usan el mismo adaptador aunque cambie el transporte local/web.
- Nunca guardes credenciales en archivos generados. Resuelve solo la referencia
  de credencial declarada por el adaptador.
- Conserva todo el contenido y reglas del proyecto fuera de los marcadores
  administrados por Antigravity.
- Memoria de proyecto: `ESTADO_PROYECTO.md`. Reglas locales:
  `RULES.md`, `WORKFLOW_RULES.md` y `.antigravity/rules.md`.

{end}"""
    ok = update_markdown_section(target_dir / "AGENTS.md", start, end, section)
    if ok:
        logger.info("✅ [AGENTS.md] Integracion actualizada")
    return ok


def update_gemini_md(target_dir: Path) -> bool:
    """Add the Gemini-facing ecosystem contract without replacing user rules."""

    start = "<!-- ANTIGRAVITY-GEMINI-START -->"
    end = "<!-- ANTIGRAVITY-GEMINI-END -->"
    section = f"""{start}

## Integración Antigravity

Este workspace está conectado al ecosistema Antigravity mediante el broker MCP
`antigravity` y su adaptador `.antigravity/nexus-client.json`.

1. Descubrí primero la capacidad con `antigravity_search`.
2. Inspeccioná su contrato con `antigravity_describe`.
3. Ejecutá con `antigravity_run_skill`, `antigravity_run_agent` o
   `antigravity_call`.

Los agentes, skills, memoria y conectores permanecen centralizados en Nexus y
se cargan bajo demanda. No copies el catálogo ni guardes credenciales en este
archivo. Conservá intacto todo el contenido fuera de estos marcadores.

{end}"""
    ok = update_markdown_section(target_dir / "GEMINI.md", start, end, section)
    if ok:
        logger.info("✅ [Gemini] GEMINI.md actualizado sin reemplazar reglas locales")
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
        num_agents = sum(1 for d in agents_dir.iterdir() if _is_agent_dir(d))

    # Count skills
    skills_dir = target_dir / ".agent" / "skills"
    if not skills_dir.exists():
        skills_dir = repo_root / ".agent" / "skills"
    num_skills = 0
    if skills_dir.exists():
        num_skills = sum(1 for d in skills_dir.iterdir() if _is_skill_dir(d))

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

    mcp_servers_list = ", ".join(_read_mcp_servers(target_dir, repo_root)) or "(ninguno)"

    rules_content = f"""# Antigravity Ecosystem Rules

This project uses **Antigravity v{ECOSYSTEM_VERSION}** — a modular AI runtime
with {num_agents} active agents and {num_skills} skills.

## MCP Gateway

- Local gateway: `{gateway_url}` (localhost:4747)
- Active MCP servers: {mcp_servers_list}
- Client adapter: `.antigravity/nexus-client.json`
- Live contract: `GET /v1/nexus/manifest`
- Local and web transports share this versioned discovery contract.

## Agent Protocol

The `antigravity` server is a **broker**: one entry point exposing six meta-tools.
The granular `antigravity-*` servers no longer exist — do not try to call them.

1. `antigravity_search` — always start here; find the capability by free text.
2. `antigravity_describe` — inspect the signature/params of what search returned.
3. `antigravity_run_skill` / `antigravity_run_agent` — execute a skill or an agent.
4. `antigravity_call` — one-off connectors (brain, mem0, watcher, …).
5. `antigravity_status` — health of broker and gateway.

Agents, skills, memory and connectors stay in Nexus and are loaded on demand.
Do not bulk-copy the catalog into this workspace; offline bundles are explicit
opt-in. Never place a gateway token in generated rules or MCP configuration.

Each agent ships two directive files: `IDENTITY.md` (identity, tier, capabilities —
parsed by discovery) and `SYSTEM_PROMPT.md` (the executor prompt).

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
        if update_markdown_section(
            rule_file,
            _TAG_START,
            _TAG_END,
            wrapped_content,
        ):
            logger.info(
                f"✅ [Reglas] {rule_file.name} generado "
                f"({num_agents} agentes, {num_skills} skills, gateway={gateway_url})"
            )


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
            if not _is_agent_dir(agent_dir):
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

    copilot_servers_list = (
        ", ".join(f"`{name}`" for name in _read_mcp_servers(target_dir, repo_root)) or "(ninguno)"
    )

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
- Registered servers (from `.mcp.json`): {copilot_servers_list}
- Universal adapter: `.antigravity/nexus-client.json`
- Live contract: `GET /v1/nexus/manifest`
- `antigravity` is a **broker**, not one server per capability: everything is
  reached through six meta-tools (`antigravity_search`, `antigravity_describe`,
  `antigravity_run_skill`, `antigravity_run_agent`, `antigravity_call`,
  `antigravity_status`). Memory (mem0) and Brain are connectors of
  `antigravity_call`, not standalone servers.
- Agents and skills stay in Nexus and are loaded on demand. Do not bulk-copy
  the catalog unless the user explicitly requests an offline bundle.
- Resolve credentials only through the adapter reference; never write a token
  into this file or generated MCP configuration.

## Agent Tiers
{agent_section}

## Key Entry Points

- `.mcp.json` — MCP server config (auto-generated, all IDEs)
- `.antigravity/config.json` — ecosystem config (gateway, version, policy)
- `.antigravity/nexus-client.json` — versioned discovery adapter for all clients
- `.antigravity/rules.md` — project-specific rules
- `ESTADO_PROYECTO.md` — project memory (read before starting work)
- `.agent/agents/` — all agents (each has `IDENTITY.md` + `SYSTEM_PROMPT.md`)
- `.agent/skills/` — modular skills library

## Workflow

1. Find the capability first: `antigravity_search`, then `antigravity_describe`.
2. Execute with `antigravity_run_agent` (complex tasks) or `antigravity_run_skill`.
3. Read `ESTADO_PROYECTO.md` before starting any session.
4. Respect constraints in `.antigravity/rules.md` and `.claude/rules/`.
<!-- ANTIGRAVITY-END -->"""

    github_dir = target_dir / ".github"
    ensure_dir(github_dir)
    out_path = github_dir / "copilot-instructions.md"
    _TAG_START = "<!-- ANTIGRAVITY-START -->"
    _TAG_END = "<!-- ANTIGRAVITY-END -->"
    try:
        if not update_markdown_section(
            out_path,
            _TAG_START,
            _TAG_END,
            content,
        ):
            return False
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
