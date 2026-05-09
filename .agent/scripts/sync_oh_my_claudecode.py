#!/usr/bin/env python3
"""Sync oh-my-claudecode across supported local AI apps.

Objetivo:
- Claude Code: copia local vendorizada de skills/agents
- Codex: snapshot local + junction/symlink hacia ~/.agents/skills/oh-my-claudecode
- Cursor: snapshot local + copia de skills
- OpenCode: copia de skills locales vendorizadas
"""

from __future__ import annotations

import argparse
import os
import json
import logging
import stat
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sync_oh_my_claudecode")

REPO_PAGE = "https://github.com/Yeachan-Heo/oh-my-claudecode"
PLUGIN_NAME = "oh-my-claudecode"


def _handle_remove_readonly(function: Any, path: str, excinfo: Any) -> None:
    _ = excinfo
    os.chmod(path, stat.S_IWRITE)
    function(path)


def get_codex_home(explicit_home: str | None = None) -> Path:
    if explicit_home:
        return Path(explicit_home).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def get_cursor_home() -> Path:
    return (Path.home() / ".cursor").resolve()


def get_claude_home() -> Path:
    return (Path.home() / ".claude").resolve()


def get_opencode_skills_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return (Path(appdata) / "OpenCode" / "skills").resolve()
    return (Path.home() / ".config" / "opencode" / "skills").resolve()


def get_vendored_oh_my_claudecode_root() -> Path:
    return (
        Path(__file__).resolve().parent.parent / "vendor" / "external-skills" / PLUGIN_NAME
    ).resolve()


def ensure_vendored_snapshot(destination: Path, source_root: Path) -> dict[str, Any]:
    if not source_root.exists():
        raise RuntimeError(f"snapshot vendorizado no encontrado: {source_root}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination, onexc=_handle_remove_readonly)
        action = "updated"
    else:
        action = "installed"
    shutil.copytree(source_root, destination)
    return {"action": action, "path": str(destination), "source": str(source_root)}


def _remove_existing_link_or_dir(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        if os.name == "nt":
            remove_result = subprocess.run(  # noqa: S603
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f'Remove-Item -LiteralPath "{path}" -Force -Recurse',
                ],
                text=True,
                capture_output=True,
                check=False,
                encoding="utf-8",
            )
            if remove_result.returncode == 0 and not path.exists():
                return
        shutil.rmtree(path, onexc=_handle_remove_readonly)
        return
    path.unlink()


def ensure_windows_junction(link_path: Path, target_path: Path) -> str:
    _remove_existing_link_or_dir(link_path)
    link_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        command = (
            f'New-Item -ItemType Junction -Path "{link_path}" -Target "{target_path}" | Out-Null'
        )
        result = subprocess.run(  # noqa: S603
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            capture_output=True,
            check=False,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip() or result.stdout.strip() or "No se pudo crear junction"
            )
        return "junction"

    link_path.symlink_to(target_path, target_is_directory=True)
    return "symlink"


def install_for_codex(codex_home: Path) -> dict[str, Any]:
    repo_dir = codex_home / PLUGIN_NAME
    repo_status = ensure_vendored_snapshot(repo_dir, get_vendored_oh_my_claudecode_root())

    agents_root = Path.home() / ".agents" / "skills"
    bridge_path = agents_root / PLUGIN_NAME
    link_kind = ensure_windows_junction(bridge_path, repo_dir / "skills")
    return {"repo": repo_status, "bridge": str(bridge_path), "bridgeType": link_kind}


def install_for_cursor() -> dict[str, Any]:
    cursor_home = get_cursor_home()
    repo_dir = cursor_home / PLUGIN_NAME
    repo_status = ensure_vendored_snapshot(repo_dir, get_vendored_oh_my_claudecode_root())

    destination = cursor_home / "skills" / PLUGIN_NAME
    _remove_existing_link_or_dir(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_dir / "skills", destination)
    return {"repo": repo_status, "skillsPath": str(destination), "mode": "local-skills-copy"}


def install_for_claude() -> dict[str, Any]:
    source_root = get_vendored_oh_my_claudecode_root()
    claude_home = get_claude_home()
    installed: dict[str, str] = {}

    for source_name, destination_name in (("skills", "skills"), ("agents", "agents")):
        source_dir = source_root / source_name
        if not source_dir.exists():
            continue
        destination = claude_home / destination_name / PLUGIN_NAME
        _remove_existing_link_or_dir(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, destination)
        installed[destination_name] = str(destination)

    return {
        "status": "installed" if installed else "skipped",
        "channel": "vendored-local-copy",
        "paths": installed,
    }


def install_for_opencode() -> dict[str, Any]:
    opencode_skills = get_opencode_skills_dir()
    repo_dir = opencode_skills.parent / PLUGIN_NAME
    repo_status = ensure_vendored_snapshot(repo_dir, get_vendored_oh_my_claudecode_root())

    destination = opencode_skills / PLUGIN_NAME
    _remove_existing_link_or_dir(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_dir / "skills", destination)
    return {"repo": repo_status, "skillsPath": str(destination), "mode": "local-skills-copy"}


def write_manifest(
    target_dir: Path,
    *,
    codex_home: Path,
    results: dict[str, Any],
) -> Path:
    manifest_path = target_dir / ".antigravity" / "oh-my-claudecode.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "source": REPO_PAGE,
                "installedAt": datetime.now(UTC).isoformat(),
                "codexHome": str(codex_home),
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def sync_oh_my_claudecode(
    target_dir: Path,
    *,
    codex_home: str | None = None,
    install_codex: bool = True,
    install_claude: bool = True,
    install_cursor: bool = True,
    install_opencode: bool = True,
    write_project_manifest: bool = True,
) -> dict[str, Any]:
    resolved_codex_home = get_codex_home(codex_home)
    results: dict[str, Any] = {
        "source": REPO_PAGE,
        "codex_home": str(resolved_codex_home),
        "codex": None,
        "claude": None,
        "cursor": None,
        "opencode": None,
        "manifest": None,
    }

    if install_codex:
        results["codex"] = install_for_codex(resolved_codex_home)
    if install_claude:
        results["claude"] = install_for_claude()
    if install_cursor:
        results["cursor"] = install_for_cursor()
    if install_opencode:
        results["opencode"] = install_for_opencode()

    if write_project_manifest:
        results["manifest"] = str(
            write_manifest(target_dir, codex_home=resolved_codex_home, results=results)
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync oh-my-claudecode across supported apps")
    parser.add_argument("target_dir", help="Project directory to store integration manifest")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    if not target_dir.exists():
        logger.error(f"❌ Target directory does not exist: {target_dir}")
        sys.exit(1)

    result = sync_oh_my_claudecode(target_dir, codex_home=args.codex_home)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(json.dumps({"manifest": result["manifest"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
