#!/usr/bin/env python3
"""Sync obra/superpowers across supported local AI apps.

Objetivo:
- Codex: snapshot local vendorizado + junction/symlink hacia ~/.agents/skills/superpowers
- Claude Code: copia local vendorizada de skills/agents/commands
- Cursor: snapshot local + copia a ~/.cursor/skills/superpowers
- OpenCode: copia local vendorizada de skills
- Gemini CLI / GitHub Copilot CLI: sin descarga remota automática
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import stat
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sync_superpowers")

SUPERPOWERS_REPO_URL = "https://github.com/obra/superpowers.git"
SUPERPOWERS_REPO_PAGE = "https://github.com/obra/superpowers"
SUPERPOWERS_PLUGIN_NAME = "superpowers"
DEFAULT_TIMEOUT_SECONDS = 60


def _handle_remove_readonly(function: Any, path: str, excinfo: Any) -> None:
    """Reintenta borrados sobre archivos/directorios read-only en Windows."""
    _ = excinfo
    os.chmod(path, stat.S_IWRITE)
    function(path)


def get_codex_home(explicit_home: str | None = None) -> Path:
    """Resuelve el CODEX_HOME efectivo."""
    if explicit_home:
        return Path(explicit_home).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def get_cursor_home() -> Path:
    """Resuelve la raíz de configuración de Cursor."""
    return (Path.home() / ".cursor").resolve()


def get_claude_home() -> Path:
    """Resuelve la raíz de configuración de Claude Code."""
    return (Path.home() / ".claude").resolve()


def get_opencode_skills_dir() -> Path:
    """Resuelve el directorio global de skills de OpenCode."""
    appdata = os.environ.get("APPDATA")
    if os.name == "nt" and appdata:
        return (Path(appdata) / "OpenCode" / "skills").resolve()
    return (Path.home() / ".config" / "opencode" / "skills").resolve()


def get_vendored_superpowers_root() -> Path:
    """Resuelve el snapshot interno vendorizado de Superpowers."""
    return (
        Path(__file__).resolve().parent.parent / "vendor" / "external-skills" / "superpowers"
    ).resolve()


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Ejecuta un comando sin shell=True."""
    return subprocess.run(  # noqa: S603
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )


def ensure_vendored_snapshot(destination: Path, source_root: Path) -> dict[str, Any]:
    """Copia un snapshot vendorizado al destino sin depender de red."""
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
    """Elimina enlace/directorio previo para recrear el puente."""
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
    """Instala Superpowers para Codex usando descubrimiento nativo."""
    repo_dir = codex_home / SUPERPOWERS_PLUGIN_NAME
    repo_status = ensure_vendored_snapshot(repo_dir, get_vendored_superpowers_root())

    agents_root = Path.home() / ".agents" / "skills"
    bridge_path = agents_root / SUPERPOWERS_PLUGIN_NAME
    link_kind = ensure_windows_junction(bridge_path, repo_dir / "skills")

    return {
        "repo": repo_status,
        "bridge": str(bridge_path),
        "bridgeType": link_kind,
    }


def install_for_cursor() -> dict[str, Any]:
    """Instala Superpowers para Cursor usando skills locales.

    Inferencia: usamos `~/.cursor/skills/` como fallback estable de skills locales,
    evitando depender del marketplace interactivo.
    """
    cursor_home = get_cursor_home()
    repo_dir = cursor_home / SUPERPOWERS_PLUGIN_NAME
    repo_status = ensure_vendored_snapshot(repo_dir, get_vendored_superpowers_root())

    destination = cursor_home / "skills" / SUPERPOWERS_PLUGIN_NAME
    _remove_existing_link_or_dir(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_dir / "skills", destination)

    return {
        "repo": repo_status,
        "skillsPath": str(destination),
        "mode": "local-skills-copy",
    }


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def install_for_claude() -> dict[str, Any]:
    """Instala Superpowers para Claude Code usando copia local vendorizada."""
    source_root = get_vendored_superpowers_root()
    claude_home = get_claude_home()
    installed: dict[str, str] = {}

    for source_name, destination_name in (
        ("skills", "skills"),
        ("agents", "agents"),
        ("commands", "commands"),
    ):
        source_dir = source_root / source_name
        if not source_dir.exists():
            continue
        destination = claude_home / destination_name / SUPERPOWERS_PLUGIN_NAME
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
    """Instala Superpowers para OpenCode mediante skills locales vendorizadas."""
    source_dir = get_vendored_superpowers_root() / "skills"
    if not source_dir.exists():
        raise RuntimeError(f"snapshot vendorizado inválido: falta {source_dir}")

    destination = get_opencode_skills_dir() / SUPERPOWERS_PLUGIN_NAME
    _remove_existing_link_or_dir(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, destination)
    return {
        "status": "installed",
        "skillsPath": str(destination),
        "mode": "local-skills-copy",
    }


def install_for_gemini() -> dict[str, Any]:
    """Evita descargas remotas; Gemini queda en modo manual hasta soportar snapshot local."""
    if not _command_exists("gemini"):
        return {"status": "skipped", "reason": "gemini CLI no está disponible"}
    return {
        "status": "skipped",
        "reason": "instalación vendorizada para gemini aún no implementada",
    }


def install_for_copilot() -> dict[str, Any]:
    """Evita descargas remotas; Copilot CLI queda en modo manual hasta soportar snapshot local."""
    if not _command_exists("copilot"):
        return {"status": "skipped", "reason": "copilot CLI no está disponible"}
    return {
        "status": "skipped",
        "reason": "instalación vendorizada para copilot aún no implementada",
    }


def write_manifest(
    target_dir: Path,
    *,
    codex_home: Path,
    results: dict[str, Any],
) -> Path:
    """Escribe manifiesto de la integración de Superpowers."""
    manifest_path = target_dir / ".antigravity" / "superpowers-plugin.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": SUPERPOWERS_REPO_PAGE,
        "installedAt": datetime.now(UTC).isoformat(),
        "codexHome": str(codex_home),
        "results": results,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def sync_superpowers(
    target_dir: Path,
    *,
    codex_home: str | None = None,
    install_codex: bool = True,
    install_claude: bool = True,
    install_cursor: bool = True,
    install_opencode: bool = True,
    install_gemini: bool = True,
    install_copilot: bool = True,
    write_project_manifest: bool = True,
) -> dict[str, Any]:
    """Sincroniza Superpowers en las apps soportadas."""
    resolved_codex_home = get_codex_home(codex_home)
    results: dict[str, Any] = {
        "source": SUPERPOWERS_REPO_PAGE,
        "codex_home": str(resolved_codex_home),
        "codex": None,
        "claude": None,
        "cursor": None,
        "opencode": None,
        "gemini": None,
        "copilot": None,
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
    if install_gemini:
        results["gemini"] = install_for_gemini()
    if install_copilot:
        results["copilot"] = install_for_copilot()

    if write_project_manifest:
        manifest = write_manifest(target_dir, codex_home=resolved_codex_home, results=results)
        results["manifest"] = str(manifest)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync obra/superpowers across supported apps")
    parser.add_argument("target_dir", help="Project directory to store integration manifest")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--codex-only", action="store_true", help="Sync only Codex integration")
    parser.add_argument("--claude-only", action="store_true", help="Sync only Claude integration")
    parser.add_argument("--cursor-only", action="store_true", help="Sync only Cursor integration")
    parser.add_argument(
        "--opencode-only", action="store_true", help="Sync only OpenCode integration"
    )
    parser.add_argument("--gemini-only", action="store_true", help="Sync only Gemini integration")
    parser.add_argument(
        "--copilot-only", action="store_true", help="Sync only GitHub Copilot CLI integration"
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    if not target_dir.exists():
        logger.error(f"❌ Target directory does not exist: {target_dir}")
        sys.exit(1)

    only_flags = {
        "codex": args.codex_only,
        "claude": args.claude_only,
        "cursor": args.cursor_only,
        "opencode": args.opencode_only,
        "gemini": args.gemini_only,
        "copilot": args.copilot_only,
    }
    only_enabled = [name for name, enabled in only_flags.items() if enabled]
    if len(only_enabled) > 1:
        logger.error("❌ Use solo un flag --*-only por ejecución.")
        sys.exit(1)

    kwargs = {
        "install_codex": not only_enabled or only_enabled == ["codex"],
        "install_claude": not only_enabled or only_enabled == ["claude"],
        "install_cursor": not only_enabled or only_enabled == ["cursor"],
        "install_opencode": not only_enabled or only_enabled == ["opencode"],
        "install_gemini": not only_enabled or only_enabled == ["gemini"],
        "install_copilot": not only_enabled or only_enabled == ["copilot"],
    }

    try:
        result = sync_superpowers(
            target_dir,
            codex_home=args.codex_home,
            **kwargs,
        )
    except RuntimeError as exc:
        logger.error(f"❌ [Superpowers] {exc}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    logger.info("✅ [Superpowers] Integración completada")
    for key in ("codex", "claude", "cursor", "opencode", "gemini", "copilot"):
        if result.get(key) is not None:
            logger.info(f"   {key}: {result[key]}")
    if result.get("manifest"):
        logger.info(f"   manifest: {result['manifest']}")


if __name__ == "__main__":
    main()
