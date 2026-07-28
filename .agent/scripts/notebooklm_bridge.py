#!/usr/bin/env python3
"""NotebookLM account bridge for local agents and MCP-compatible IDEs.

This script keeps account sync operational without committing credentials:
the local MCP package lives under .venv-mcp/ and browser/login state remains in
the user's home directory or the NotebookLM skill data folder.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCAL_MCP_VENV = ROOT / ".venv-mcp" / "notebooklm"
SKILL_DIR = ROOT / ".agent" / "skills" / "notebooklm"

# Version validada localmente (2026-07-17). Override: ANTIGRAVITY_NLM_CLI_VERSION.
NOTEBOOKLM_MCP_CLI_VERSION = "0.8.3"


def configure_utf8_output() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def scripts_dir(venv_dir: Path = LOCAL_MCP_VENV) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin")


def exe(name: str, venv_dir: Path = LOCAL_MCP_VENV) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return scripts_dir(venv_dir) / f"{name}{suffix}"


def venv_python(venv_dir: Path = LOCAL_MCP_VENV) -> Path:
    return exe("python", venv_dir)


def bridge_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{scripts_dir()}{os.pathsep}{env.get('PATH', '')}"
    return env


def run(
    command: list[str], *, cwd: Path = ROOT, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=bridge_env(),
    )


def capture(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=bridge_env(),
    )


def ensure_mcp_cli() -> Path:
    nlm = exe("nlm")
    if nlm.exists():
        return nlm

    LOCAL_MCP_VENV.parent.mkdir(parents=True, exist_ok=True)
    if not venv_python().exists():
        print(f"Creating local MCP venv: {LOCAL_MCP_VENV}")
        venv.create(LOCAL_MCP_VENV, with_pip=True)

    # Version pineada: el upstream depende de APIs internas de NotebookLM y
    # puede romper sin aviso (ej. device-binding, issue #248). Subir la version
    # es una decision consciente: cambiar el pin o exportar la env var.
    pinned = os.environ.get("ANTIGRAVITY_NLM_CLI_VERSION", NOTEBOOKLM_MCP_CLI_VERSION)
    print(f"Installing notebooklm-mcp-cli=={pinned} into local venv...")
    run([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_python()), "-m", "pip", "install", f"notebooklm-mcp-cli=={pinned}"])

    if not nlm.exists():
        raise FileNotFoundError(f"nlm was not installed at {nlm}")
    return nlm


def skill_status() -> int:
    return run(
        ["python", "scripts/run.py", "auth_manager.py", "status"],
        cwd=SKILL_DIR,
        check=False,
    ).returncode


def local_paths() -> dict[str, str]:
    nlm = exe("nlm")
    mcp = exe("notebooklm-mcp")
    return {
        "repo": str(ROOT),
        "mcp_venv": str(LOCAL_MCP_VENV),
        "nlm": str(nlm) if nlm.exists() else "",
        "notebooklm_mcp": str(mcp) if mcp.exists() else "",
        "skill": str(SKILL_DIR),
    }


def print_mcp_json() -> None:
    mcp = exe("notebooklm-mcp")
    if not mcp.exists():
        mcp = ensure_mcp_cli().with_name(
            "notebooklm-mcp.exe" if os.name == "nt" else "notebooklm-mcp"
        )

    config = {
        "mcpServers": {
            "notebooklm-mcp": {
                "command": str(mcp),
                "args": [],
            }
        }
    }
    print(json.dumps(config, ensure_ascii=False, indent=2))


def setup_claude_code() -> int:
    ensure_mcp_cli()
    claude = shutil.which("claude")
    if not claude:
        print(
            "Claude CLI is not in PATH. Use `notebooklm_bridge.py mcp-json` and paste the JSON manually."
        )
        return 1

    mcp = exe("notebooklm-mcp")
    return run(
        [claude, "mcp", "add", "--scope", "user", "notebooklm-mcp", str(mcp)], check=False
    ).returncode


def run_nlm(args: list[str]) -> int:
    nlm = ensure_mcp_cli()
    return run([str(nlm), *args], check=False).returncode


def status() -> int:
    print("NotebookLM bridge status")
    print()
    print("Local skill auth:")
    sys.stdout.flush()
    skill_rc = skill_status()
    print()

    paths = local_paths()
    print("MCP bridge:")
    print(f"  Installed: {'Yes' if paths['nlm'] and paths['notebooklm_mcp'] else 'No'}")
    print(f"  Venv: {paths['mcp_venv']}")
    if paths["nlm"]:
        print(f"  nlm: {paths['nlm']}")
    if paths["notebooklm_mcp"]:
        print(f"  server: {paths['notebooklm_mcp']}")

    print()
    if not paths["nlm"]:
        print("Next: python .agent/scripts/notebooklm_bridge.py install")
    if skill_rc != 0:
        print("Next local skill auth: /notebooklm auth")
    print("Next MCP auth after install: python .agent/scripts/notebooklm_bridge.py login")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync NotebookLM with local AI tools.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show local skill and MCP bridge state")
    subparsers.add_parser("install", help="Install notebooklm-mcp-cli in .venv-mcp/")
    subparsers.add_parser("login", help="Run browser login for the MCP bridge")
    subparsers.add_parser("doctor", help="Run notebooklm-mcp-cli diagnostics")
    subparsers.add_parser("mcp-json", help="Print generic MCP JSON for Codex/OpenCode/etc.")
    subparsers.add_parser(
        "setup-claude-code", help="Register MCP server with Claude Code if CLI exists"
    )

    nlm_parser = subparsers.add_parser(
        "nlm", add_help=False, help="Pass through to the local nlm CLI"
    )
    nlm_parser.add_argument("args", nargs=argparse.REMAINDER)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["nlm"]:
        return run_nlm(argv[1:])

    args = build_parser().parse_args(argv)

    if args.command in (None, "status"):
        return status()
    if args.command == "install":
        ensure_mcp_cli()
        print("NotebookLM MCP CLI installed.")
        print_mcp_json()
        return 0
    if args.command == "login":
        return run_nlm(["login"])
    if args.command == "doctor":
        return run_nlm(["doctor"])
    if args.command == "mcp-json":
        print_mcp_json()
        return 0
    if args.command == "setup-claude-code":
        return setup_claude_code()
    build_parser().print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
