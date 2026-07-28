#!/usr/bin/env python3
"""Refrescar bloques AUTO:* en CLAUDE.md con datos reales del repositorio.

Reemplaza el contenido entre marcadores ``<!-- AUTO:section -->`` y
``<!-- /AUTO:section -->`` por valores calculados en vivo desde el filesystem.
Idempotente: si nada cambio, no escribe.

Uso:
    python .agent/scripts/refresh_claude_md.py            # dry-run + diff
    python .agent/scripts/refresh_claude_md.py --apply    # escribir cambios

Secciones soportadas:
    AUTO:versions   versiones canonicas (.agent/VERSION, pyproject, package.json)
    AUTO:counts     inventario (agentes, skills, MCP servers, commands, brain, ...)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
BRAIN_README_MD = REPO_ROOT / "BRAIN_README.md"

MARKER_OPEN = "<!-- AUTO:{name} -->"
MARKER_CLOSE = "<!-- /AUTO:{name} -->"


@dataclass
class Counts:
    """Conteos vivos del ecosistema."""

    agents: int = 0
    skills_base: int = 0
    skills_custom: int = 0
    mcp_total: int = 0
    mcp_principal: bool = False
    mcp_specialized: list[str] = field(default_factory=list)
    mcp_external: list[str] = field(default_factory=list)
    slash_commands: int = 0
    rules: int = 0
    workflows: int = 0
    memories: int = 0
    brain_nodes: int = 0
    rust_commands: int = 0


@dataclass
class Versions:
    """Versiones canonicas declaradas en archivos de manifest."""

    runtime: str = "unknown"
    pyproject: str = "unknown"
    nexus: str = "unknown"
    bot: str = "unknown"


def _count_dirs(path: Path, *, exclude_prefixes: tuple[str, ...] = ()) -> int:
    """Cuenta subdirectorios visibles, excluyendo prefijos dados."""
    if not path.is_dir():
        return 0
    return sum(
        1
        for p in path.iterdir()
        if p.is_dir() and not p.name.startswith(".") and not p.name.startswith(exclude_prefixes)
    )


def _count_files(
    path: Path,
    suffix: str,
    *,
    recursive: bool = False,
    exclude: set[str] | None = None,
) -> int:
    """Cuenta archivos con sufijo dado, excluyendo nombres reservados."""
    if not path.is_dir():
        return 0
    pattern = f"**/*{suffix}" if recursive else f"*{suffix}"
    excluded = exclude or set()
    return sum(1 for p in path.glob(pattern) if p.is_file() and p.name not in excluded)


def collect_counts(root: Path) -> Counts:
    """Calcula los conteos vivos del repo."""
    c = Counts()

    agents_dir = root / ".agent" / "agents"
    if agents_dir.is_dir():
        # Un agente es un directorio con IDENTITY.md (ver .claude/rules/architecture.md).
        # Contar por presencia de IDENTITY.md excluye automaticamente carpetas
        # auxiliares (_docs, _archive, __pycache__, ce-*) sin mantener blacklists.
        c.agents = sum(
            1 for p in agents_dir.iterdir() if p.is_dir() and (p / "IDENTITY.md").is_file()
        )

    c.skills_base = _count_dirs(root / ".agent" / "skills", exclude_prefixes=("__", "_"))
    c.skills_custom = _count_dirs(root / ".agent" / "skills-custom", exclude_prefixes=("__", "_"))

    mcp_path = root / ".mcp.json"
    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer .mcp.json: %s", exc)
        else:
            servers = data.get("mcpServers", {})
            c.mcp_total = len(servers)
            for name in servers:
                if name == "antigravity":
                    c.mcp_principal = True
                elif name.startswith("antigravity-"):
                    c.mcp_specialized.append(name)
                else:
                    c.mcp_external.append(name)

    c.slash_commands = _count_files(root / ".claude" / "commands", ".md")
    c.rules = _count_files(root / ".claude" / "rules", ".md")

    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.is_dir():
        c.workflows = sum(
            1 for p in workflows_dir.iterdir() if p.is_file() and p.suffix in {".yml", ".yaml"}
        )

    c.memories = _count_files(root / ".claude" / "memory", ".md")
    c.brain_nodes = _count_files(
        root / ".agent" / "brain",
        ".md",
        recursive=True,
        exclude={"index.md", "log.md", "README.md"},
    )
    c.rust_commands = _count_files(
        root / "nexus-app" / "src-tauri" / "src" / "commands",
        ".rs",
        exclude={"mod.rs"},  # mod.rs es el agregador, no un command module
    )

    return c


def collect_versions(root: Path) -> Versions:
    """Lee versiones canonicas desde los manifests del repo."""
    v = Versions()

    runtime_file = root / ".agent" / "VERSION"
    if runtime_file.is_file():
        v.runtime = runtime_file.read_text(encoding="utf-8").strip()

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version") and "=" in stripped:
                value = stripped.split("=", 1)[1].strip()
                v.pyproject = value.strip('"').strip("'")
                break

    nexus_pkg = root / "nexus-app" / "package.json"
    if nexus_pkg.is_file():
        try:
            v.nexus = json.loads(nexus_pkg.read_text(encoding="utf-8")).get("version", "unknown")
        except json.JSONDecodeError as exc:
            logger.warning("nexus-app/package.json invalido: %s", exc)

    bot_pkg = root / "package.json"
    if bot_pkg.is_file():
        try:
            v.bot = json.loads(bot_pkg.read_text(encoding="utf-8")).get("version", "unknown")
        except json.JSONDecodeError as exc:
            logger.warning("package.json invalido: %s", exc)

    return v


def render_versions(v: Versions) -> str:
    """Renderiza el bloque AUTO:versions."""
    return (
        f"- Runtime: `.agent/VERSION` -> `{v.runtime}`\n"
        f"- Package Python: `pyproject.toml` -> `{v.pyproject}`\n"
        f"- Nexus App: `nexus-app/package.json` -> `{v.nexus}`\n"
        f"- Bot TS: `package.json` -> `{v.bot}`"
    ).replace("->", "→")


def render_counts(c: Counts) -> str:
    """Renderiza el bloque AUTO:counts respetando orden de aparicion."""
    specialized_short = (
        ", ".join(n.removeprefix("antigravity-") for n in c.mcp_specialized) or "ninguno"
    )
    external = ", ".join(c.mcp_external) or "ninguno"
    principal = "el principal `antigravity` + " if c.mcp_principal else ""
    return (
        f"- **Agentes**: {c.agents} en `.agent/agents/` "
        f"(limpios de obsoletos `__pycache__`, `_archive*`, `ce-*`)\n"
        f"- **Skills base**: {c.skills_base} en `.agent/skills/`\n"
        f"- **Skills custom**: {c.skills_custom} en `.agent/skills-custom/`\n"
        f"- **MCP servers**: {c.mcp_total} en `.mcp.json` — {principal}"
        f"{len(c.mcp_specialized)} especializados `antigravity-*` "
        f"({specialized_short}) + externos ({external})\n"
        f"- **Slash commands**: {c.slash_commands} en `.claude/commands/`\n"
        f"- **Reglas auto-inyectadas**: {c.rules} en `.claude/rules/`\n"
        f"- **GitHub workflows**: {c.workflows} en `.github/workflows/`\n"
        f"- **Memorias capa 1**: {c.memories} en `.claude/memory/` "
        f"(markdown versionado en git)\n"
        f"- **Brain nodes (capa 2)**: {c.brain_nodes} en `.agent/brain/` "
        f"(concepts, sessions, patterns, decisions)\n"
        f"- **Rust command modules de Nexus**: {c.rust_commands} en "
        f"`nexus-app/src-tauri/src/commands/`"
    )


def replace_block(text: str, name: str, new_content: str) -> tuple[str, bool]:
    """Reemplaza bloque entre marcadores y devuelve (texto, hubo_cambio)."""
    open_tag = MARKER_OPEN.format(name=name)
    close_tag = MARKER_CLOSE.format(name=name)
    pattern = re.compile(re.escape(open_tag) + r"(.*?)" + re.escape(close_tag), re.DOTALL)
    replacement = f"{open_tag}\n{new_content}\n{close_tag}"
    new_text, n = pattern.subn(replacement, text, count=1)
    if n == 0:
        logger.warning("Marcador '%s' no encontrado en CLAUDE.md", name)
        return text, False
    return new_text, new_text != text


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribir cambios al disco (sin esto, dry-run + diff)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Raiz del repo (default: deducida desde el script)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Modo CI: no escribe, sale con codigo 1 si hay drift (sin --apply).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logging DEBUG")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    claude_md = args.root / "CLAUDE.md"
    brain_readme_md = args.root / "BRAIN_README.md"

    if not claude_md.is_file():
        logger.error("No existe %s", claude_md)
        return 1

    counts = collect_counts(args.root)
    versions = collect_versions(args.root)

    logger.info(
        "Conteos: agents=%d skills=%d custom=%d mcp=%d cmds=%d rules=%d "
        "workflows=%d mem=%d brain=%d rust=%d",
        counts.agents,
        counts.skills_base,
        counts.skills_custom,
        counts.mcp_total,
        counts.slash_commands,
        counts.rules,
        counts.workflows,
        counts.memories,
        counts.brain_nodes,
        counts.rust_commands,
    )
    logger.info(
        "Versiones: runtime=%s py=%s nexus=%s bot=%s",
        versions.runtime,
        versions.pyproject,
        versions.nexus,
        versions.bot,
    )

    text = claude_md.read_text(encoding="utf-8")
    original = text

    text, _ = replace_block(text, "versions", render_versions(versions))
    text, _ = replace_block(text, "counts", render_counts(counts))

    # Actualizar BRAIN_README.md si existe
    brain_text = None
    brain_original = None
    if brain_readme_md.is_file():
        brain_text = brain_readme_md.read_text(encoding="utf-8")
        brain_original = brain_text
        brain_text, _ = replace_block(brain_text, "brain_count", f"**{counts.brain_nodes} nodos")

    changed_any = (text != original) or (brain_text and brain_text != brain_original)

    if not changed_any:
        logger.info("Sin cambios — archivos ya sincronizados.")
        return 0

    if args.apply:
        if text != original:
            claude_md.write_text(text, encoding="utf-8")
            logger.info("✓ CLAUDE.md actualizado.")
        if brain_text and brain_text != brain_original:
            brain_readme_md.write_text(brain_text, encoding="utf-8")
            logger.info("✓ BRAIN_README.md actualizado.")
    else:
        logger.info("Cambios detectados (dry-run). Usa --apply para escribir.")
        if text != original:
            diff = unified_diff(
                original.splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile="CLAUDE.md (actual)",
                tofile="CLAUDE.md (refrescado)",
                n=2,
            )
            sys.stdout.writelines(diff)
        if brain_text and brain_text != brain_original:
            diff = unified_diff(
                brain_original.splitlines(keepends=True),
                brain_text.splitlines(keepends=True),
                fromfile="BRAIN_README.md (actual)",
                tofile="BRAIN_README.md (refrescado)",
                n=2,
            )
            sys.stdout.writelines(diff)
        if args.check:
            logger.error(
                "Archivos AUTO tienen drift. Corre: py .agent/scripts/refresh_claude_md.py --apply"
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
