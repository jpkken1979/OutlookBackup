#!/usr/bin/env python3
"""
Sync .mcp.json → Claude Desktop config with absolute paths.

Problem: .mcp.json uses "python", "py", "uvx" without absolute paths.
Claude Desktop spawns MCP servers in an isolated subprocess that resolves
commands differently than an interactive shell — it can find WSL bash's python
before Windows Python, causing ModuleNotFoundError on all antigravity servers.

Solution: This script reads .mcp.json and generates a Claude Desktop config
with absolute Windows paths for all local executables.

Usage:
    python .agent/scripts/sync_mcp_config.py           # dry-run (print diff)
    python .agent/scripts/sync_mcp_config.py --apply      # write to Claude Desktop
    python .agent/scripts/sync_mcp_config.py --apply --no-backup  # skip backup
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Absolute paths for Windows executables
PYTHON_WIN = "C:\\Users\\kenji\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
UVX_WIN = "C:\\Users\\kenji\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\uvx.exe"

# Files that need path resolution
PYTHON_CMDS = {"python", "py"}
UVX_CMDS = {"uvx"}

# Path with env var pattern
ENV_VAR_RE = "${"


def resolve_command(server_name: str, config: dict) -> dict:
    """Convert relative commands to absolute Windows paths."""
    cmd = config.get("command", "")
    args = config.get("args", [])
    env = config.get("env", {})

    if cmd in PYTHON_CMDS:
        cmd = PYTHON_WIN
    elif cmd in UVX_CMDS:
        cmd = UVX_WIN

    # Normalize arg paths that use ${ANTIGRAVITY_ROOT} backslashes
    new_args = []
    for arg in args:
        if isinstance(arg, str) and "${ANTIGRAVITY_ROOT}" in arg:
            arg = arg.replace("/", "\\").replace(
                "${ANTIGRAVITY_ROOT}",
                "C:\\Users\\kenji\\Github\\Jpkken1979\\OpenAntigravity26.3.30",
            )
        new_args.append(arg)

    return {"command": cmd, "args": new_args, "env": env, **({"cwd": config["cwd"]} if config.get("cwd") else {})}


def load_mcp_json() -> dict:
    """Load .mcp.json from repo root."""
    repo = Path(__file__).parent.parent.parent.resolve()
    mcp_path = repo / ".mcp.json"
    with open(mcp_path) as f:
        return json.load(f)


def load_desktop_config() -> dict:
    """Load current Claude Desktop config."""
    config_path = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"mcpServers": {}, "preferences": {}}


def build_new_desktop_config(mcp_data: dict, current: dict) -> dict:
    """Build new desktop config from .mcp.json."""
    new_servers = {}

    for name, config in mcp_data.get("mcpServers", {}).items():
        server_type = config.get("type", "stdio")

        if server_type == "http":
            # HTTP servers (deepwiki etc.) pass through unchanged
            new_servers[name] = config
            continue

        # For stdio servers, resolve absolute paths (only for local executables)
        cmd = config.get("command", "")
        args = config.get("args", [])
        env = config.get("env", {})

        if cmd in PYTHON_CMDS:
            cmd = PYTHON_WIN
            args = [arg.replace("/", "\\") if isinstance(arg, str) else arg for arg in args]
            new_servers[name] = {"command": cmd, "args": args, "env": env, **({"cwd": config["cwd"]} if config.get("cwd") else {})}
        elif cmd in UVX_CMDS:
            cmd = UVX_WIN
            new_servers[name] = {"command": cmd, "args": args, "env": env, **({"cwd": config["cwd"]} if config.get("cwd") else {})}
        else:
            # Leave npx/cmd as-is (they resolve correctly via PATH)
            new_servers[name] = config

    # Preserve preferences section
    result = {
        "mcpServers": new_servers,
        "preferences": current.get("preferences", {}),
    }
    return result


def diff_configs(old: dict, new: dict) -> tuple[int, int, int]:
    """Show diff between configs. Returns (changed, added, removed)."""
    old_servers = set(old.get("mcpServers", {}).keys())
    new_servers = set(new.get("mcpServers", {}).keys())

    changed = 0
    added = len(new_servers - old_servers)
    removed = len(old_servers - new_servers)

    for name in old_servers & new_servers:
        if json.dumps(old["mcpServers"].get(name, {})) != json.dumps(new["mcpServers"].get(name, {})):
            changed += 1

    return changed, added, removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync .mcp.json → Claude Desktop MCP config")
    parser.add_argument("--apply", action="store_true", help="Write to Claude Desktop config")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                        help="Show diff without writing (default)")
    args = parser.parse_args()

    mcp_data = load_mcp_json()
    current = load_desktop_config()

    new_config = build_new_desktop_config(mcp_data, current)
    changed, added, removed = diff_configs(current, new_config)

    print(f"MCP servers in .mcp.json: {len(mcp_data.get('mcpServers', {}))}")
    print(f"Claude Desktop servers:  {len(current.get('mcpServers', {}))}")
    print(f"Changes: {changed} modified, {added} added, {removed} removed")

    if changed == 0 and added == 0 and removed == 0:
        print("No changes needed.")
        return 0

    # Show diff of changed servers
    if changed > 0:
        print("\n--- Changed servers ---")
        for name in set(current.get("mcpServers", {}).keys()) & set(new_config["mcpServers"].keys()):
            old = current["mcpServers"].get(name, {})
            new = new_config["mcpServers"].get(name, {})
            if old != new:
                old_cmd = old.get("command", "")
                new_cmd = new.get("command", "")
                if old_cmd != new_cmd:
                    print(f"  {name}: {old_cmd} → {new_cmd}")

    if not args.apply:
        print("\nRun with --apply to write changes.")
        return 0

    # Backup
    config_path = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    if not args.no_backup and config_path.exists():
        backup = config_path.with_suffix(".json.bak")
        shutil.copy2(config_path, backup)
        print(f"Backup: {backup}")

    with open(config_path, "w") as f:
        json.dump(new_config, f, indent=2)

    print(f"Wrote: {config_path}")
    print("Restart Claude Desktop to pick up changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())