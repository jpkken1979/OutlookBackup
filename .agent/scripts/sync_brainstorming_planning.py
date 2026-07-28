#!/usr/bin/env python3
"""Sync the standalone brainstorming-planning skill across supported apps.

Fuente:
- MCP Market entry: https://mcpmarket.com/es/tools/skills/brainstorming-planning
- Skill real: https://github.com/gakonst/dotfiles/.codex/skills/brainstorm/SKILL.md
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SKILL_NAME = "brainstorm"
INSTALL_DIR_NAME = "brainstorming-planning"
SOURCE_PAGE = "https://mcpmarket.com/es/tools/skills/brainstorming-planning"


def get_vendored_brainstorming_skill() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "vendor"
        / "external-skills"
        / INSTALL_DIR_NAME
        / "SKILL.md"
    ).resolve()


def read_vendored_skill() -> tuple[str, str]:
    skill_path = get_vendored_brainstorming_skill()
    if not skill_path.exists():
        raise RuntimeError(f"snapshot vendorizado no encontrado: {skill_path}")
    return skill_path.read_text(encoding="utf-8"), str(skill_path)


def get_codex_skills_dir() -> Path:
    return (Path.home() / ".agents" / "skills").resolve()


def get_claude_skills_dir() -> Path:
    return (Path.home() / ".claude" / "skills").resolve()


def get_cursor_skills_dir() -> Path:
    return (Path.home() / ".cursor" / "skills").resolve()


def get_opencode_skills_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return (Path(appdata) / "OpenCode" / "skills").resolve()
    return (Path.home() / ".config" / "opencode" / "skills").resolve()


def write_skill(
    destination_root: Path,
    skill_text: str,
    *,
    source_url: str | None = None,
) -> dict[str, Any]:
    destination = destination_root / INSTALL_DIR_NAME
    destination.mkdir(parents=True, exist_ok=True)
    skill_path = destination / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")
    marker = destination / ".antigravity-source.json"
    resolved_source_url = source_url or str(get_vendored_brainstorming_skill())
    marker.write_text(
        json.dumps(
            {
                "type": "external-skill",
                "name": SKILL_NAME,
                "source": resolved_source_url,
                "installedAt": datetime.now(UTC).isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"path": str(destination), "skill": str(skill_path)}


def write_manifest(target_dir: Path, *, results: dict[str, Any]) -> Path:
    manifest_path = target_dir / ".antigravity" / "brainstorming-planning.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "source": SOURCE_PAGE,
                "installedAt": datetime.now(UTC).isoformat(),
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def sync_brainstorming_planning(
    target_dir: Path,
    *,
    install_codex: bool = True,
    install_claude: bool = True,
    install_cursor: bool = True,
    install_opencode: bool = True,
    write_project_manifest: bool = True,
) -> dict[str, Any]:
    skill_text, source_url = read_vendored_skill()
    results: dict[str, Any] = {
        "source": source_url,
        "codex": None,
        "claude": None,
        "cursor": None,
        "opencode": None,
        "manifest": None,
    }

    if install_codex:
        results["codex"] = write_skill(get_codex_skills_dir(), skill_text, source_url=source_url)
    if install_claude:
        results["claude"] = write_skill(get_claude_skills_dir(), skill_text, source_url=source_url)
    if install_cursor:
        results["cursor"] = write_skill(
            get_cursor_skills_dir(),
            skill_text,
            source_url=source_url,
        )
    if install_opencode:
        results["opencode"] = write_skill(
            get_opencode_skills_dir(),
            skill_text,
            source_url=source_url,
        )

    if write_project_manifest:
        results["manifest"] = str(write_manifest(target_dir, results=results))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync the brainstorming-planning skill across supported apps"
    )
    parser.add_argument("target_dir", help="Project directory to store integration manifest")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    result = sync_brainstorming_planning(target_dir)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(json.dumps({"manifest": result["manifest"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
