"""
Sync Antigravity skills to other IDEs.

Crea un SKILL.md unificado que funciona en todos los IDEs,
copiando los skills críticos a ~/.cursor/skills/, ~/.codex/skills/, etc.

Uso:
    python .agent/scripts/sync_skills_to_ides.py --dry-run
    python .agent/scripts/sync_skills_to_ides.py --apply
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Skills críticos a sincronizar
CRITICAL_SKILLS: list[str] = [
    "jp",
    "jpread",
    "brain",
    "brainstorming-planning",
    "autonomous",
    "finalize",
    "sdd",
    "recall",
]

# IDEs y sus directorios de skills
IDE_SKILL_DIRS: dict[str, Path] = {
    "cursor": Path.home() / ".cursor" / "skills",
    "codex": Path.home() / ".codex" / "skills",
    "windsurf": Path.home() / ".windsurf" / "skills",
    "vscode": Path.home() / ".vscode" / "chat" / "extensions",
}


def get_skill_source(skill_name: str) -> Path | None:
    """Busca el skill en los directorios de Claude Code y del repo."""
    # Primero buscar en skills instalados de Claude Code
    claude_skills = Path.home() / ".claude" / "skills"
    if (claude_skills / skill_name).exists():
        return claude_skills / skill_name

    # Luego buscar en el repo
    repo_root = Path(__file__).parent.parent.parent
    possible_paths = [
        repo_root / ".claude" / "skills" / skill_name,
        repo_root / ".claude" / "skills-custom" / skill_name,
        repo_root / ".agent" / "skills" / skill_name,
    ]

    for p in possible_paths:
        if p.exists() and p.is_dir():
            return p

    return None


def create_unified_skill_md(source_dir: Path, skill_name: str) -> str:
    """Crea un SKILL.md unificado con el contenido del skill.

    El formato es compatible con todos los IDEs que usan skills.sh.
    """
    # Leer el SKILL.md original si existe
    skill_md = source_dir / "SKILL.md"
    if skill_md.exists():
        return skill_md.read_text(encoding="utf-8")

    # Si no hay SKILL.md, crear uno genérico basado en la estructura
    # Buscar scripts o README
    readme = source_dir / "README.md"
    scripts_dir = source_dir / "scripts"

    content_lines = [
        f"# {skill_name}",
        "",
        f"> Skill de Antigravity Ecosystem para {skill_name}",
        "",
        "## Descripción",
        "",
    ]

    if readme.exists():
        content_lines.append(readme.read_text(encoding="utf-8")[:500])
    else:
        content_lines.append(f"Skill {skill_name} del ecosistema Antigravity.")

    if scripts_dir.exists():
        main_scripts = list(scripts_dir.glob("*.py"))
        if main_scripts:
            content_lines.append("")
            content_lines.append("## Scripts disponibles")
            for s in main_scripts[:3]:
                content_lines.append(f"- `{s.name}`")

    content_lines.append("")
    content_lines.append("---")
    content_lines.append(f"*Source: {source_dir}*")

    return "\n".join(content_lines)


def sync_skill_to_ide(
    skill_name: str,
    ide: str,
    target_dir: Path,
    dry_run: bool = False,
) -> bool:
    """Sincroniza un skill a un IDE específico."""
    source = get_skill_source(skill_name)

    if not source:
        logger.debug("Skill '%s' no encontrado en Claude Code", skill_name)
        return False

    target = target_dir / skill_name

    if dry_run:
        logger.info("[DRY RUN] Sincronizaría %s -> %s", skill_name, target)
        return True

    try:
        # Crear directorio del skill
        target.mkdir(parents=True, exist_ok=True)

        # Copiar SKILL.md
        unified_md = create_unified_skill_md(source, skill_name)
        (target / "SKILL.md").write_text(unified_md, encoding="utf-8")

        # Copiar scripts si existen
        scripts_dir = source / "scripts"
        if scripts_dir.exists():
            target_scripts = target / "scripts"
            target_scripts.mkdir(exist_ok=True)
            for script in scripts_dir.glob("*.py"):
                shutil.copy2(script, target_scripts / script.name)

        logger.info("✓ Synced: %s -> %s", skill_name, ide)
        return True
    except Exception as e:
        logger.error("✗ Error syncing %s: %s", skill_name, e)
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync skills to IDEs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--ide", choices=list(IDE_SKILL_DIRS.keys()), help="IDE específico")
    args = parser.parse_args()

    ides = [args.ide] if args.ide else list(IDE_SKILL_DIRS.keys())

    logger.info("Sincronizando skills a: %s", ", ".join(ides))
    if args.dry_run:
        logger.info("[DRY RUN MODE]")

    total_synced = 0

    for ide in ides:
        target_dir = IDE_SKILL_DIRS[ide]

        # Crear directorio si no existe
        if not args.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        logger.info("\n=== Sincronizando a %s ===", ide)

        for skill in CRITICAL_SKILLS:
            if sync_skill_to_ide(skill, ide, target_dir, args.dry_run):
                total_synced += 1

    logger.info("\n✓ Total sincronizados: %d", total_synced)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
