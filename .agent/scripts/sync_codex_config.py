#!/usr/bin/env python3
"""Sync MCP servers from project `.mcp.json` into `$CODEX_HOME/config.toml`.

Estrategia:
- Add-only: nunca sobreescribe servidores existentes en `mcp_servers`.
- Convierte la configuración JSON del proyecto a TOML compatible con Codex.
- Crea `~/.codex/config.toml` si no existe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tomllib
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


def _toml_key_fragment(key: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = [f"{_toml_key_fragment(key)} = {_toml_literal(val)}" for key, val in value.items()]
        return "{ " + ", ".join(parts) + " }"
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def _render_server_section(name: str, config: dict[str, Any]) -> str:
    header = f'[mcp_servers.{_toml_key_fragment(name)}]'
    lines = [header]
    ordered_fields = (
        "type",
        "url",
        "command",
        "args",
        "cwd",
        "startup_timeout_sec",
        "tool_timeout_sec",
        "env",
    )
    for field in ordered_fields:
        if field in config:
            lines.append(f"{field} = {_toml_literal(config[field])}")
    for field, value in config.items():
        if field in ordered_fields:
            continue
        lines.append(f"{_toml_key_fragment(field)} = {_toml_literal(value)}")
    return "\n".join(lines)


def _load_project_mcp_servers(repo_root: Path) -> dict[str, dict[str, Any]]:
    mcp_json_path = repo_root / ".mcp.json"
    if not mcp_json_path.exists():
        return {}
    raw = json.loads(mcp_json_path.read_text(encoding="utf-8"))
    servers = raw.get("mcpServers")
    if not isinstance(servers, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for name, value in servers.items():
        if isinstance(name, str) and isinstance(value, dict):
            result[name] = value
    return result


def _load_existing_mcp_servers(config_path: Path) -> set[str]:
    if not config_path.exists():
        return set()
    try:
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return set()
    mcp_servers = parsed.get("mcp_servers")
    if not isinstance(mcp_servers, dict):
        return set()
    return {name for name in mcp_servers if isinstance(name, str)}


def sync_codex_config(
    *,
    repo_root: Path,
    codex_home: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Sincroniza MCP servers del proyecto hacia `$CODEX_HOME/config.toml`."""
    resolved_repo_root = repo_root.resolve()
    resolved_codex_home = get_codex_home(codex_home)
    config_path = resolved_codex_home / "config.toml"

    project_servers = _load_project_mcp_servers(resolved_repo_root)
    if not project_servers:
        return {
            "config_path": str(config_path),
            "codex_home": str(resolved_codex_home),
            "added": [],
            "skipped": [],
        }

    existing_names = _load_existing_mcp_servers(config_path)
    to_add = sorted(name for name in project_servers if name not in existing_names)
    skipped = sorted(name for name in project_servers if name in existing_names)

    if dry_run or not to_add:
        return {
            "config_path": str(config_path),
            "codex_home": str(resolved_codex_home),
            "added": to_add,
            "skipped": skipped,
        }

    rendered_sections = [
        _render_server_section(name, project_servers[name])
        for name in to_add
    ]
    append_block = "\n\n".join(rendered_sections).strip()
    resolved_codex_home.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        current = config_path.read_text(encoding="utf-8").rstrip()
        next_content = f"{current}\n\n{append_block}\n" if current else f"{append_block}\n"
    else:
        next_content = f"{append_block}\n"

    config_path.write_text(next_content, encoding="utf-8")
    return {
        "config_path": str(config_path),
        "codex_home": str(resolved_codex_home),
        "added": to_add,
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync project MCP servers into $CODEX_HOME/config.toml (add-only)"
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Project root containing .mcp.json",
    )
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    result = sync_codex_config(
        repo_root=Path(args.repo_root),
        codex_home=args.codex_home,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
