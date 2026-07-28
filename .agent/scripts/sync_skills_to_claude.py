#!/usr/bin/env python3
"""Sync complete Antigravity skills to Claude Code native skills.

Copies each skill package from `.agent/skills/` or `.agent/skills-custom/`
to `.claude/skills/{skill-name}/` so Claude Code receives its instructions,
scripts, references and examples without generated caches.

Usage:
    # Sync all skills to a target project
    python .agent/scripts/sync_skills_to_claude.py D:/Git/MyProject

    # Sync to current project
    python .agent/scripts/sync_skills_to_claude.py .

    # Sync globally (~/.claude/skills/)
    python .agent/scripts/sync_skills_to_claude.py --global

    # Dry run (show what would be created)
    python .agent/scripts/sync_skills_to_claude.py D:/Git/MyProject --dry-run

    # Only sync specific skills
    python .agent/scripts/sync_skills_to_claude.py . --only ui-ux-pro-max,frontend-design

    # Exclude deprecated skills
    python .agent/scripts/sync_skills_to_claude.py . --skip-deprecated
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sync_skills")

# Skills explicitly excluded from sync (internal, deprecated, or meta-skills)
EXCLUDED_SKILLS = {
    "_deprecated",
    "_archived_",  # carpeta archivada en .claude/skills/
    "_official-template",  # template vacio, no skill funcional
    "init",  # data warehouse init, not general
    "imagen",  # empty
    "jp-executor",  # skill local del repo source, no portable
}
SKILL_COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
)


def sync_skills(
    target_dir: Path,
    repo_root: Path,
    dry_run: bool = False,
    only: list[str] | None = None,
    skip_deprecated: bool = True,
    global_mode: bool = False,
) -> dict[str, int]:
    """Sync Antigravity skills to .claude/skills/ in target_dir.

    Args:
        target_dir: Where to create .claude/skills/ (project root or ~/.claude/)
        repo_root: Antigravity ecosystem root (where .agent/skills/ lives)
        dry_run: If True, only show what would be done
        only: If set, only sync these specific skill names
        skip_deprecated: Skip skills in _deprecated folder
        global_mode: If True, target_dir is ~/.claude/

    Returns:
        Dict with counts: created, skipped, errors, total
    """
    skill_roots = [
        repo_root / ".agent" / "skills",
        repo_root / ".agent" / "skills-custom",
        repo_root / ".claude" / "skills",  # skills oficiales Anthropic + locales
    ]

    if not skill_roots[0].exists():
        logger.error(f"❌ Skills directory not found: {skill_roots[0]}")
        return {"created": 0, "skipped": 0, "errors": 0, "total": 0}

    if global_mode:
        skills_dir_target = target_dir / "skills"
    else:
        skills_dir_target = target_dir / ".claude" / "skills"

    stats = {"created": 0, "skipped": 0, "errors": 0, "total": 0}

    # Collect all skills from base + custom roots
    seen: set[str] = set()
    skill_dirs: list[Path] = []
    for skills_dir in skill_roots:
        if not skills_dir.exists():
            continue
        for skill_dir in sorted(
            d for d in skills_dir.iterdir() if d.is_dir() and d.name not in EXCLUDED_SKILLS
        ):
            if skill_dir.name in seen:
                continue
            seen.add(skill_dir.name)
            skill_dirs.append(skill_dir)

    if skip_deprecated:
        skill_dirs = [d for d in skill_dirs if not d.name.startswith("_")]

    if only:
        only_set = set(only)
        skill_dirs = [d for d in skill_dirs if d.name in only_set]

    stats["total"] = len(skill_dirs)

    if not dry_run:
        skills_dir_target.mkdir(parents=True, exist_ok=True)

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            stats["skipped"] += 1
            continue

        skill_name = skill_dir.name
        try:
            skill_md.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"  ❌ Error reading {skill_md}: {e}")
            stats["errors"] += 1
            continue

        target_skill_dir = skills_dir_target / skill_name

        if dry_run:
            logger.info(f"  [DRY] Would sync package: {target_skill_dir}")
            stats["created"] += 1
            continue

        try:
            if skill_dir.resolve() == target_skill_dir.resolve():
                stats["skipped"] += 1
                continue
            shutil.copytree(
                skill_dir,
                target_skill_dir,
                dirs_exist_ok=True,
                ignore=SKILL_COPY_IGNORE,
            )
            stats["created"] += 1
        except Exception as e:
            logger.error(f"  ❌ Error creating {skill_path}: {e}")
            stats["errors"] += 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Antigravity skills to Claude Code skills")
    parser.add_argument(
        "target_dir",
        nargs="?",
        help="Target project directory (creates .claude/skills/ there)",
    )
    parser.add_argument(
        "--root",
        help="Antigravity ecosystem root. Default: auto-detected from script location.",
    )
    parser.add_argument(
        "--global",
        dest="global_mode",
        action="store_true",
        help="Sync to global ~/.claude/skills/ instead of a project.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created, without writing files.",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated list of skill names to sync (e.g. ui-ux-pro-max,frontend-design).",
    )
    parser.add_argument(
        "--skip-deprecated",
        action="store_true",
        default=True,
        help="Skip skills in _deprecated folder (default: True).",
    )
    parser.add_argument(
        "--include-deprecated",
        action="store_true",
        help="Include deprecated skills.",
    )

    args = parser.parse_args()

    # Resolve repo root
    if args.root:
        repo_root = Path(args.root).resolve()
    else:
        repo_root = Path(__file__).parent.parent.parent.resolve()

    if not (repo_root / ".agent" / "skills").exists():
        logger.error(f"❌ No .agent/skills/ found in {repo_root}")
        sys.exit(1)

    # Resolve target
    if args.global_mode:
        target_dir = Path.home() / ".claude"
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info("🔄 Syncing skills to GLOBAL ~/.claude/skills/")
    elif args.target_dir:
        target_dir = Path(args.target_dir).resolve()
        if not target_dir.exists():
            logger.error(f"❌ Target directory does not exist: {target_dir}")
            sys.exit(1)
        logger.info(f"🔄 Syncing skills to {target_dir}/.claude/skills/")
    else:
        logger.error("❌ Provide a target directory or use --global")
        parser.print_help()
        sys.exit(1)

    only = args.only.split(",") if args.only else None
    skip_deprecated = not args.include_deprecated

    if args.dry_run:
        logger.info("   (DRY RUN — no files will be created)\n")

    stats = sync_skills(
        target_dir=target_dir,
        repo_root=repo_root,
        dry_run=args.dry_run,
        only=only,
        skip_deprecated=skip_deprecated,
        global_mode=args.global_mode,
    )

    logger.info("")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"✅ Skills synced: {stats['created']}")
    logger.info(f"   Skipped (no SKILL.md): {stats['skipped']}")
    if stats["errors"]:
        logger.info(f"   ❌ Errors: {stats['errors']}")
    logger.info(f"   Total scanned: {stats['total']}")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not args.dry_run and stats["created"] > 0:
        logger.info("")
        logger.info("🎉 Skills are now available natively in Claude Code!")
        logger.info("   Example: @ui-ux-pro-max build a dashboard for analytics")


if __name__ == "__main__":
    main()
