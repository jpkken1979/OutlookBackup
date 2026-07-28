"""
Sync Commands & Skills across IDEs.

Sincroniza slash commands y skills del ecosistema Antigravity
a todos los IDEs compatibles (Claude Code, Cursor, Codex, etc.)

Uso:
    python .agent/scripts/sync_commands.py --all
    python .agent/scripts/sync_commands.py --ide cursor
    python .agent/scripts/sync_commands.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# IDEs compatibles y sus configs
IDE_CONFIGS: dict[str, dict] = {
    # Origen, no destino: es el directorio del repo de donde salen los comandos.
    # Se excluye de la sincronizacion "all" (ver main()).
    "claude-code": {
        "commands_dir": ".claude/commands",
        "skills_dir": ".claude/skills",
        "mcp_json": ".mcp.json",
        "cursorrules": None,  # No tiene commands dir
    },
    # Destino global de Claude Code: sin esto los slash commands solo existen si
    # la sesion se abre con el repo como workspace activo. Abriendo `claude` desde
    # cualquier otra carpeta no aparecia ninguno de los 72.
    "claude-code-global": {
        "commands_dir": "~/.claude/commands",
        "skills_dir": "~/.claude/skills",
        "mcp_json": None,
        "cursorrules": None,
        "all_commands": True,
    },
    "cursor": {
        "commands_dir": None,  # Cursor no tiene slash commands
        "skills_dir": "~/.cursor/skills",
        "mcp_json": ".cursor/mcp.json",
        "cursorrules": "~/.cursor/.cursorrules",
        "all_commands": True,
    },
    "codex": {
        "commands_dir": None,  # Codex no tiene slash commands
        "skills_dir": "~/.codex/skills",
        "mcp_json": None,
        "cursorrules": None,
        "all_commands": True,
    },
    "windsurf": {
        "commands_dir": None,
        "skills_dir": "~/.windsurf/skills",
        "mcp_json": ".windsurf/mcp.json",
        "cursorrules": ".windsurfrules",
        "all_commands": True,
    },
    "vscode": {
        "commands_dir": None,
        "skills_dir": "~/.vscode/chat/extensions",
        "mcp_json": ".vscode/mcp.json",
        "cursorrules": None,
        "all_commands": True,
    },
}


def _wants_all_commands(ide: str) -> bool:
    """Si el IDE recibe los 72 comandos o solo los de CRITICAL_COMMANDS.

    Los destinos globales llevan todo: el objetivo es que `/` autocomplete el
    catalogo completo en cualquier carpeta. Ojo — varios comandos ejecutan
    scripts del repo con rutas relativas, asi que fuera del repo aparecen en el
    autocompletado pero fallan al correrlos. Es el trade-off aceptado.
    """
    return bool(IDE_CONFIGS.get(ide, {}).get("all_commands"))

# Comandos críticos para sincronizar (los más importantes)
CRITICAL_COMMANDS: list[str] = [
    "jp.md",
    "jpread.md",
    "brain.md",
    "finalize.md",
    "autonomous.md",
    "recall.md",
    "session-summary.md",
    "sdd.md",
    "finalize.md",
    "git-pushing.md",
    "search.md",
    "findings.md",
    "progress.md",
    "plan.md",
    "self-improver.md",
    "team.md",
]

# Skills críticos para sincronizar
CRITICAL_SKILLS: list[str] = [
    "brainstorming-planning",
    "jp",
    "jpread",
    "autonomous-executor",
    "brain-network",
]


def _build_command_skill_markdown(command_name: str, command_content: str) -> str:
    """Convierte un slash command en una skill portable para IDEs sin slash parser."""
    title = command_name.replace("-", " ").strip() or command_name
    return (
        f"# {title}\n\n"
        f"Skill generada desde .claude/commands/{command_name}.md para IDEs sin slash commands.\n\n"
        "Usa esta skill cuando el usuario pida el comando exacto o un flujo equivalente.\n\n"
        "---\n\n"
        f"{command_content.strip()}\n"
    )


def _export_commands_as_skills(
    ide: str,
    source_dir: Path,
    target_skills_dir: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Exporta slash commands como skills para IDEs sin soporte nativo de comandos."""
    synced = 0
    skipped = 0
    failed = 0

    if not dry_run:
        target_skills_dir.mkdir(parents=True, exist_ok=True)

    sync_all = _wants_all_commands(ide)
    for cmd_file in source_dir.glob("*.md"):
        if not sync_all and cmd_file.name not in CRITICAL_COMMANDS:
            skipped += 1
            continue

        command_name = cmd_file.stem
        skill_dir_name = f"antigravity-cmd-{command_name}"
        skill_dir = target_skills_dir / skill_dir_name
        skill_file = skill_dir / "SKILL.md"

        if dry_run:
            logger.info(
                "[DRY RUN] Exportaría command como skill (%s): %s -> %s",
                ide,
                cmd_file,
                skill_file,
            )
            synced += 1
            continue

        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file.write_text(
                _build_command_skill_markdown(
                    command_name,
                    cmd_file.read_text(encoding="utf-8"),
                ),
                encoding="utf-8",
            )
            logger.info(
                "✓ Export command->skill (%s): %s -> %s",
                ide,
                cmd_file.name,
                skill_dir_name,
            )
            synced += 1
        except Exception as e:
            logger.error("✗ Error exportando command %s: %s", cmd_file.name, e)
            failed += 1

    return {"synced": synced, "skipped": skipped, "failed": failed}


def sync_commands_to_ide(
    ide: str,
    source_dir: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Sincroniza commands a un IDE específico.

    Returns:
        Dict con {synced, skipped, failed}
    """
    config = IDE_CONFIGS.get(ide, {})
    target_dir = config.get("commands_dir")

    if not target_dir:
        fallback_skills_dir = config.get("skills_dir")
        if not fallback_skills_dir:
            logger.info(
                "IDE '%s' no soporta slash commands ni skills fallback, saltando...",
                ide,
            )
            return {"synced": 0, "skipped": 1, "failed": 0}

        if fallback_skills_dir.startswith("~"):
            resolved_skills_dir = Path(fallback_skills_dir.replace("~", str(Path.home())))
        else:
            resolved_skills_dir = Path(fallback_skills_dir)

        logger.info(
            "IDE '%s' no soporta slash commands; exportando commands como skills...",
            ide,
        )
        return _export_commands_as_skills(
            ide,
            source_dir,
            resolved_skills_dir,
            dry_run=dry_run,
        )

    # Resolver path
    if target_dir.startswith("~"):
        target_dir = Path(target_dir.replace("~", str(Path.home())))
    else:
        target_dir = Path(target_dir)

    # Crear directorio si no existe
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    synced = 0
    skipped = 0
    failed = 0

    # Sincronizar commands
    sync_all = _wants_all_commands(ide)
    for cmd_file in source_dir.glob("*.md"):
        if not sync_all and cmd_file.name not in CRITICAL_COMMANDS:
            skipped += 1
            continue

        target = target_dir / cmd_file.name

        if dry_run:
            logger.info("[DRY RUN] Copiaría: %s -> %s", cmd_file, target)
            synced += 1
            continue

        try:
            shutil.copy2(cmd_file, target)
            logger.info("✓ Sync: %s -> %s", cmd_file.name, target_dir)
            synced += 1
        except Exception as e:
            logger.error("✗ Error sync %s: %s", cmd_file.name, e)
            failed += 1

    return {"synced": synced, "skipped": skipped, "failed": failed}


def sync_skills_to_ide(
    ide: str,
    source_skills_dir: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Sincroniza skills a un IDE específico.

    Returns:
        Dict con {synced, skipped, failed}
    """
    config = IDE_CONFIGS.get(ide, {})
    target_dir = config.get("skills_dir")

    if not target_dir:
        logger.warning("IDE '%s' no tiene directorio de skills configurado", ide)
        return {"synced": 0, "skipped": 0, "failed": 0}

    # Resolver path
    if target_dir.startswith("~"):
        target_dir = Path(target_dir.replace("~", str(Path.home())))
    else:
        target_dir = Path(target_dir)

    # Crear directorio si no existe
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    synced = 0
    skipped = 0
    failed = 0

    # Los skills viven en `.agent/`, no en `.claude/`: hasta 2026-07-26 este
    # source apuntaba a `.claude/skills`, un directorio que no existe, asi que
    # sync_skills_to_ide nunca copio un solo skill real a ningun IDE.
    skill_dirs = [source_skills_dir]
    custom_dir = source_skills_dir.parent / "skills-custom"
    if custom_dir != source_skills_dir:
        skill_dirs.append(custom_dir)

    for skill_dir in skill_dirs:
        if not skill_dir.exists():
            continue

        for skill_path in skill_dir.iterdir():
            if not skill_path.is_dir():
                continue

            # Los skills base (`.agent/skills/`, 800+) NO se copian: se consumen
            # on-demand por el MCP `antigravity-skills`. Copiarlos a un dir global
            # los cargaria en cada sesion de cualquier carpeta, que es lo que
            # `.claude/rules/ecosystem-usage.md` pide evitar explicitamente.
            # Los custom si van completos a los destinos globales (decision del
            # usuario, 2026-07-26): son pocos y especificos del negocio UNS.
            is_custom = skill_dir.name == "skills-custom"
            if not (is_custom and _wants_all_commands(ide)) and (
                skill_path.name not in CRITICAL_SKILLS
            ):
                skipped += 1
                continue
            # `_deprecated_*`, `_archive`, `_archive_stubs`: convencion del repo
            # para lo que no es un skill vivo.
            if skill_path.name.startswith("_"):
                skipped += 1
                continue

            target = target_dir / skill_path.name

            if dry_run:
                logger.info("[DRY RUN] Sincronizaría skill: %s", skill_path.name)
                synced += 1
                continue

            try:
                if target.exists():
                    # Actualizar skill existente
                    shutil.rmtree(target)
                shutil.copytree(skill_path, target)
                logger.info("✓ Sync skill: %s -> %s", skill_path.name, target_dir)
                synced += 1
            except Exception as e:
                logger.error("✗ Error sync skill %s: %s", skill_path.name, e)
                failed += 1

    return {"synced": synced, "skipped": skipped, "failed": failed}


def _resolve_user_path(path: str) -> Path:
    """Resolve a path that may start with ~ into an absolute Path."""
    if path.startswith("~"):
        return Path(path.replace("~", str(Path.home()), 1))
    return Path(path)


def _copy_with_retries(
    source: Path,
    target: Path,
    *,
    attempts: int = 6,
    delay_s: float = 0.2,
) -> None:
    """Copy a file retrying on Windows 'file in use' errors (WinError 32)."""
    for i in range(attempts):
        try:
            shutil.copy2(source, target)
            return
        except OSError as e:
            is_locked = getattr(e, "winerror", None) == 32
            if not is_locked:
                raise
            if i < attempts - 1:
                time.sleep(delay_s * (i + 1))
                continue
            raise


def sync_cursorrules(ide: str, source: Path, dry_run: bool = False) -> int:
    """Sincroniza .cursorrules al archivo global de Cursor (~/.cursor/.cursorrules)."""
    if ide != "cursor":
        return 0

    config = IDE_CONFIGS.get(ide, {})
    target_path = config.get("cursorrules")
    if not target_path or not source.exists():
        return 0

    target = _resolve_user_path(str(target_path))
    try:
        if source.resolve() == target.resolve():
            logger.info("↷ Skip .cursorrules (source == target): %s", target)
            return 1
    except OSError:
        # Si no podemos resolver (paths raros), seguimos con el copy.
        pass

    if dry_run:
        logger.info("[DRY RUN] Copiaría .cursorrules -> %s", target)
        return 1

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_with_retries(source, target)
        logger.info("✓ Sync .cursorrules -> %s", target)
        return 1
    except Exception as e:
        pending = Path(f"{target}.pending")
        try:
            pending.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, pending)
            logger.warning("⚠ .cursorrules estaba en uso; dejé pendiente: %s", pending)
        except Exception:
            pass
        logger.error("✗ Error sync .cursorrules: %s", e)
        return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync commands & skills across IDEs",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Alias de compatibilidad para sincronizar todos los IDEs",
    )
    parser.add_argument(
        "--ide",
        choices=list(IDE_CONFIGS.keys()) + ["all"],
        default="all",
        help="IDE a sincronizar (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar qué se sincronizaría",
    )
    parser.add_argument(
        "--skills-only",
        action="store_true",
        help="Solo sincronizar skills (no commands)",
    )
    parser.add_argument(
        "--commands-only",
        action="store_true",
        help="Solo sincronizar commands (no skills)",
    )
    args = parser.parse_args()

    # Paths
    repo_root = Path(__file__).parent.parent.parent
    commands_dir = repo_root / ".claude" / "commands"
    # `.agent/skills`, no `.claude/skills`: este ultimo no existe en el repo y por
    # eso la sincronizacion de skills era un no-op silencioso.
    skills_dir = repo_root / ".agent" / "skills"
    cursorrules = repo_root / ".cursorrules"

    if not commands_dir.exists():
        logger.error("No se encontró: %s", commands_dir)
        return 1

    # IDEs a procesar
    if args.all or args.ide == "all":
        ides = [k for k in IDE_CONFIGS if k != "claude-code"]
    else:
        ides = [args.ide]

    logger.info("Sincronizando a: %s", ", ".join(ides))
    if args.dry_run:
        logger.info("[DRY RUN MODE]")

    total = {"synced": 0, "skipped": 0, "failed": 0}

    for ide in ides:
        logger.info("\n=== Sincronizando %s ===", ide)

        if not args.skills_only:
            result = sync_commands_to_ide(ide, commands_dir, args.dry_run)
            for k, v in result.items():
                total[k] += v

        if not args.commands_only:
            result = sync_skills_to_ide(ide, skills_dir, args.dry_run)
            for k, v in result.items():
                total[k] += v

        # Sync .cursorrules para Cursor
        if cursorrules.exists():
            sync_cursorrules(ide, cursorrules, args.dry_run)

    logger.info("\n=== Resumen ===")
    logger.info("Sincronizados: %d", total["synced"])
    logger.info("Omitidos: %d", total["skipped"])
    logger.info("Fallidos: %d", total["failed"])

    return 0 if total["failed"] == 0 else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
