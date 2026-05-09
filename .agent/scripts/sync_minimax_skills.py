#!/usr/bin/env python3
"""Sync MiniMax-AI skills for Codex and Claude Code.

Integra las skills oficiales de https://github.com/MiniMax-AI/skills
siguiendo el método recomendado por el repo:
- Codex: clone/pull a ~/.codex/minimax-skills y exponer skills via ~/.agents/skills
- Claude Code: intentar instalación oficial via `claude plugin ...`
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sync_minimax_skills")

MINIMAX_SKILLS_REPO_URL = "https://github.com/MiniMax-AI/skills.git"
MINIMAX_SKILLS_REPO_PAGE = "https://github.com/MiniMax-AI/skills"
MINIMAX_PLUGIN_NAME = "minimax-skills"


def get_codex_home(explicit_home: str | None = None) -> Path:
    """Resuelve el CODEX_HOME efectivo."""
    if explicit_home:
        return Path(explicit_home).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Ejecuta un comando sin shell=True."""
    return subprocess.run(  # noqa: S603
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
    )


def ensure_repo_cloned(destination: Path, repo_url: str) -> dict[str, Any]:
    """Clona o actualiza un repositorio git."""
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("git no está disponible en PATH")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        result = _run([git_path, "clone", "--depth", "1", repo_url, str(destination)])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git clone falló")
        return {"action": "cloned", "path": str(destination)}

    result = _run([git_path, "-C", str(destination), "pull", "--ff-only", "origin", "main"])
    if result.returncode != 0:
        return {
            "action": "present",
            "path": str(destination),
            "warning": result.stderr.strip() or result.stdout.strip() or "git pull falló",
        }
    return {"action": "updated", "path": str(destination)}


def _remove_existing_link_or_dir(path: Path) -> None:
    """Elimina enlace/directorio previo para recrear el puente."""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def ensure_windows_junction(link_path: Path, target_path: Path) -> str:
    """Crea un junction en Windows; en otros sistemas usa symlink."""
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
    """Instala MiniMax skills para Codex."""
    repo_dir = codex_home / "minimax-skills"
    repo_status = ensure_repo_cloned(repo_dir, MINIMAX_SKILLS_REPO_URL)

    agents_root = Path.home() / ".agents" / "skills"
    bridge_path = agents_root / MINIMAX_PLUGIN_NAME
    link_kind = ensure_windows_junction(bridge_path, repo_dir / "skills")

    return {
        "repo": repo_status,
        "bridge": str(bridge_path),
        "bridgeType": link_kind,
    }


def _claude_cli_exists() -> bool:
    return shutil.which("claude") is not None


def install_for_claude() -> dict[str, Any]:
    """Instala MiniMax skills/plugin para Claude Code."""
    if not _claude_cli_exists():
        return {"status": "skipped", "reason": "claude CLI no está disponible"}

    add_marketplace = _run(["claude", "plugin", "marketplace", "add", MINIMAX_SKILLS_REPO_PAGE])
    install_plugin = _run(["claude", "plugin", "install", MINIMAX_PLUGIN_NAME])

    add_ok = add_marketplace.returncode == 0 or "already" in (
        (add_marketplace.stdout + add_marketplace.stderr).lower()
    )
    install_ok = install_plugin.returncode == 0 or "already" in (
        (install_plugin.stdout + install_plugin.stderr).lower()
    )

    if add_ok and install_ok:
        return {
            "status": "installed",
            "marketplace": (add_marketplace.stdout or add_marketplace.stderr).strip(),
            "plugin": (install_plugin.stdout or install_plugin.stderr).strip(),
        }

    return {
        "status": "warning",
        "marketplace": (add_marketplace.stdout or add_marketplace.stderr).strip(),
        "plugin": (install_plugin.stdout or install_plugin.stderr).strip(),
    }


def write_manifest(
    target_dir: Path,
    *,
    codex_home: Path,
    codex_result: dict[str, Any] | None,
    claude_result: dict[str, Any] | None,
) -> Path:
    """Escribe manifiesto de la integración MiniMax."""
    manifest_path = target_dir / ".antigravity" / "minimax-skills.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": MINIMAX_SKILLS_REPO_PAGE,
        "installedAt": datetime.now(UTC).isoformat(),
        "codexHome": str(codex_home),
        "codex": codex_result,
        "claude": claude_result,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def sync_minimax_skills(
    target_dir: Path,
    *,
    codex_home: str | None = None,
    install_codex: bool = True,
    install_claude: bool = True,
    write_project_manifest: bool = True,
) -> dict[str, Any]:
    """Sincroniza skills de MiniMax para Codex y/o Claude Code."""
    resolved_codex_home = get_codex_home(codex_home)
    result: dict[str, Any] = {
        "source": MINIMAX_SKILLS_REPO_PAGE,
        "codex_home": str(resolved_codex_home),
        "codex": None,
        "claude": None,
        "manifest": None,
    }

    if install_codex:
        result["codex"] = install_for_codex(resolved_codex_home)
    if install_claude:
        result["claude"] = install_for_claude()

    if write_project_manifest:
        manifest = write_manifest(
            target_dir,
            codex_home=resolved_codex_home,
            codex_result=result["codex"],
            claude_result=result["claude"],
        )
        result["manifest"] = str(manifest)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync MiniMax-AI skills for Codex and Claude")
    parser.add_argument("target_dir", help="Project directory to store integration manifest")
    parser.add_argument(
        "--codex-home", help="Override CODEX_HOME (default: env CODEX_HOME or ~/.codex)"
    )
    parser.add_argument("--codex-only", action="store_true", help="Sync only Codex integration")
    parser.add_argument("--claude-only", action="store_true", help="Sync only Claude integration")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    if not target_dir.exists():
        logger.error(f"❌ Target directory does not exist: {target_dir}")
        sys.exit(1)

    install_codex = not args.claude_only
    install_claude = not args.codex_only

    try:
        result = sync_minimax_skills(
            target_dir,
            codex_home=args.codex_home,
            install_codex=install_codex,
            install_claude=install_claude,
        )
    except RuntimeError as exc:
        logger.error(f"❌ [MiniMax Skills] {exc}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    logger.info("✅ [MiniMax Skills] Integración completada")
    if result["codex"]:
        logger.info(f"   Codex: {result['codex']}")
    if result["claude"]:
        logger.info(f"   Claude: {result['claude']}")
    logger.info("   Reinicia Codex y/o Claude Code para que detecten los cambios.")


if __name__ == "__main__":
    main()
