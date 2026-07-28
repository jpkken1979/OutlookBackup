#!/usr/bin/env python3
"""Sync Antigravity local skills and Claude commands into $CODEX_HOME/skills.

Objetivo:
- Exponer skills propias de `.agent/skills` y `.agent/skills-custom`
- Exportar `.claude/commands/*.md` como skills consumibles por Codex
- Dejar un manifiesto por proyecto para trazabilidad de la inyección
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def get_codex_home(explicit_home: str | None = None) -> Path:
    """Resuelve el CODEX_HOME efectivo."""
    if explicit_home:
        return Path(explicit_home).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def slugify(value: str) -> str:
    """Convierte un nombre en slug ASCII estable para un directorio de skill."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "skill"


def resolve_destination_name(skills_root: Path, preferred_name: str) -> str:
    """Evita colisiones con skills ya existentes sin sobrescribir skills ajenas."""
    destination = skills_root / preferred_name
    marker = destination / ".antigravity-source.json"
    if not destination.exists():
        return preferred_name
    if marker.exists():
        return preferred_name
    return f"antigravity-{preferred_name}"


def write_marker(destination: Path, payload: dict[str, Any]) -> None:
    """Escribe metadatos mínimos para reconocer skills generadas por Antigravity."""
    marker = destination / ".antigravity-source.json"
    marker.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def copy_skill_directory(source_dir: Path, destination_dir: Path) -> None:
    """Sincroniza un directorio de skill al destino."""
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)


def build_command_skill_markdown(command_name: str, command_markdown: str) -> str:
    """Convierte un slash command de Claude en una skill simple para Codex."""
    title = command_name.replace("-", " ").strip() or command_name
    return (
        f"# {title}\n\n"
        f"Skill generada desde `.claude/commands/{command_name}.md`.\n\n"
        f"Usa esta skill cuando el usuario pida `{command_name}` o solicite un flujo equivalente.\n\n"
        "---\n\n"
        f"{command_markdown.strip()}\n"
    )


def sync_local_skills(
    repo_root: Path,
    skills_root: Path,
) -> list[dict[str, str]]:
    """Sincroniza skills locales de Antigravity hacia CODEX_HOME."""
    results: list[dict[str, str]] = []
    source_roots = [
        repo_root / ".agent" / "skills",
        repo_root / ".agent" / "skills-custom",
    ]

    for source_root in source_roots:
        if not source_root.exists():
            continue
        for skill_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            preferred_name = slugify(skill_dir.name)
            destination_name = resolve_destination_name(skills_root, preferred_name)
            destination_dir = skills_root / destination_name
            copy_skill_directory(skill_dir, destination_dir)
            write_marker(
                destination_dir,
                {
                    "type": "antigravity-skill",
                    "source": str(skill_dir),
                    "syncedAt": datetime.now(UTC).isoformat(),
                },
            )
            results.append(
                {
                    "kind": "skill",
                    "source": str(skill_dir),
                    "name": destination_name,
                    "destination": str(destination_dir),
                }
            )

    return results


def sync_claude_commands(
    repo_root: Path,
    skills_root: Path,
) -> list[dict[str, str]]:
    """Exporta slash commands de Claude como skills de Codex."""
    results: list[dict[str, str]] = []
    commands_root = repo_root / ".claude" / "commands"
    if not commands_root.exists():
        return results

    for command_file in sorted(commands_root.glob("*.md")):
        command_name = slugify(command_file.stem)
        destination_name = resolve_destination_name(skills_root, command_name)
        destination_dir = skills_root / destination_name
        if destination_dir.exists():
            shutil.rmtree(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        command_markdown = command_file.read_text(encoding="utf-8")
        (destination_dir / "SKILL.md").write_text(
            build_command_skill_markdown(command_file.stem, command_markdown),
            encoding="utf-8",
        )
        write_marker(
            destination_dir,
            {
                "type": "claude-command-export",
                "source": str(command_file),
                "syncedAt": datetime.now(UTC).isoformat(),
            },
        )
        results.append(
            {
                "kind": "command",
                "source": str(command_file),
                "name": destination_name,
                "destination": str(destination_dir),
            }
        )

    return results


def write_manifest(
    target_dir: Path,
    *,
    codex_home: Path,
    synced_items: list[dict[str, str]],
) -> Path:
    """Guarda el resultado de la sincronización portable de Antigravity -> Codex."""
    manifest_path = target_dir / ".antigravity" / "codex-antigravity-assets.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "installedAt": datetime.now(UTC).isoformat(),
                "codexHome": str(codex_home),
                "items": synced_items,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def sync_antigravity_assets_to_codex(
    target_dir: Path,
    *,
    repo_root: Path,
    codex_home: str | None = None,
    write_project_manifest: bool = True,
) -> dict[str, Any]:
    """Sincroniza skills propias de Antigravity y comandos de Claude a Codex."""
    resolved_codex_home = get_codex_home(codex_home)
    skills_root = resolved_codex_home / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)

    synced_items = [
        *sync_local_skills(repo_root, skills_root),
        *sync_claude_commands(repo_root, skills_root),
    ]

    manifest_path: str | None = None
    if write_project_manifest:
        manifest_path = str(
            write_manifest(
                target_dir,
                codex_home=resolved_codex_home,
                synced_items=synced_items,
            )
        )

    return {
        "codex_home": str(resolved_codex_home),
        "installed": synced_items,
        "manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Antigravity local skills and Claude commands into $CODEX_HOME/skills"
    )
    parser.add_argument("target_dir", help="Project directory to store integration manifest")
    parser.add_argument("--repo-root", help="Override repo root path")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    repo_root = (
        Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    )
    result = sync_antigravity_assets_to_codex(
        target_dir,
        repo_root=repo_root,
        codex_home=args.codex_home,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(
        json.dumps(
            {
                "installed": len(result["installed"]),
                "codex_home": result["codex_home"],
                "manifest": result["manifest"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
