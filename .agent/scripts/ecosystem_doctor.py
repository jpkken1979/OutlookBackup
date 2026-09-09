#!/usr/bin/env python3
"""Read-only health audit for the OpenAntigravity ecosystem.

The doctor intentionally avoids creating gateway credentials, writing memories,
or mutating client configuration.  It is safe to run repeatedly and supports a
machine-readable JSON report for Nexus and CI.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

DEFAULT_GATEWAY = "http://127.0.0.1:4747"
DEFAULT_OCX_PORT = 10100
CLAUDE_MIN_VERSION = (2, 1, 176)
CLIENT_CONFIGS = (
    ("Claude Code", ".mcp.json"),
    ("Codex", ".codex/config.toml"),
    ("Cursor", ".cursor/mcp.json"),
    ("Windsurf", ".windsurf/mcp.json"),
    ("VS Code / Copilot", ".vscode/mcp.json"),
    ("Cline / Roo", ".vscode/cline_mcp_settings.json"),
    ("Zed", ".zed/settings.json"),
    ("Gemini", ".gemini/settings.json"),
    ("Continue", ".continue/config.json"),
)


@dataclass(frozen=True)
class Check:
    """A single doctor result."""

    name: str
    status: str
    detail: str
    hint: str = ""


def _check(name: str, status: str, detail: str, hint: str = "") -> Check:
    return Check(name=name, status=status, detail=detail, hint=hint)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_json(
    url: str,
    *,
    api_key: str | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload


def _read_session_key(repo_root: Path) -> str | None:
    agent_path = str(repo_root / ".agent")
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
    try:
        from core.session_key import read_session_key

        return read_session_key()
    except (ImportError, OSError, ValueError):
        return None


def _count_dirs(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(
        1 for item in path.iterdir() if item.is_dir() and not item.name.startswith(("_", "__"))
    )


def check_inventory(repo_root: Path) -> list[Check]:
    """Validate canonical agent/skill inventory using the same live rules as CLAUDE.md."""
    agents_dir = repo_root / ".agent" / "agents"
    agents = (
        sum(
            1 for item in agents_dir.iterdir() if item.is_dir() and (item / "IDENTITY.md").is_file()
        )
        if agents_dir.is_dir()
        else 0
    )
    base_skills = _count_dirs(repo_root / ".agent" / "skills")
    custom_skills = _count_dirs(repo_root / ".agent" / "skills-custom")
    status = "ok" if agents and base_skills else "fail"
    return [
        _check(
            "inventory",
            status,
            f"{agents} agents, {base_skills} base skills, {custom_skills} custom skills",
            "Run .agent/scripts/refresh_claude_md.py after inventory changes.",
        )
    ]


def check_environment(repo_root: Path) -> list[Check]:
    """Inspect provider declarations without exposing or requiring secret values."""
    env_path = repo_root / ".env"
    if not env_path.is_file():
        return [_check("environment", "warn", ".env not found", "Configure providers in .env.")]

    definitions: dict[str, int] = {}
    configured_keys = 0
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        definitions[key] = definitions.get(key, 0) + 1
        if key.endswith("_API_KEY") and value.strip().strip("\"'"):
            configured_keys += 1

    duplicates = sorted(key for key, count in definitions.items() if count > 1)
    if duplicates:
        return [
            _check(
                "environment",
                "warn",
                f"{configured_keys} API keys configured; duplicate variables: {', '.join(duplicates)}",
                "Keep one definition per variable; live OAuth status is checked through the gateway.",
            )
        ]
    return [
        _check(
            "environment",
            "ok",
            f"{configured_keys} non-empty API key declarations; OAuth may add providers at runtime",
        )
    ]


def check_gateway(repo_root: Path, base_url: str) -> list[Check]:
    """Probe public health plus authenticated read-only runtime endpoints."""
    results: list[Check] = []
    try:
        health = _http_json(f"{base_url}/health")
        health_data = health.get("data") if isinstance(health.get("data"), dict) else health
        health_state = health_data.get("status", "reachable")
        results.append(_check("gateway", "ok", f"reachable ({health_state}) at {base_url}"))
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        return [
            _check(
                "gateway",
                "fail",
                f"unreachable at {base_url}: {exc}",
                f"Run {repo_root / '.venv/Scripts/python.exe'} start_gateway.py",
            )
        ]

    api_key = _read_session_key(repo_root)
    if not api_key:
        results.append(
            _check(
                "gateway-auth",
                "warn",
                "session key is not available; private read-only probes were skipped",
                "Start the gateway once so it can create the encrypted per-user session key.",
            )
        )
        return results

    try:
        payload = _http_json(f"{base_url}/v1/provider/status", api_key=api_key)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        providers = data.get("providers") if isinstance(data.get("providers"), list) else []
        routable = sum(
            1 for provider in providers if isinstance(provider, dict) and provider.get("routable")
        )
        detail = (
            f"active={data.get('active_provider', 'unknown')}/"
            f"{data.get('active_model', 'unknown')}; "
            f"{routable}/{len(providers)} providers routable; "
            f"proxy_connected={bool(data.get('proxy_connected'))}"
        )
        provider_status = (
            "warn" if data.get("needs_restart") or data.get("has_api_key") is False else "ok"
        )
        results.append(_check("providers", provider_status, detail))
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        results.append(_check("providers", "fail", f"/v1/provider/status failed: {exc}"))

    try:
        payload = _http_json(f"{base_url}/v1/memory/stats", api_key=api_key)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        backend = str(data.get("backend", "unknown"))
        detail = (
            f"backend={backend}; memories={data.get('total_memories', data.get('total', 0))}; "
            f"mem0_available={bool(data.get('mem0_available'))}"
        )
        memory_status = "warn" if "fallback" in str(data.get("status", "")).lower() else "ok"
        results.append(_check("memory", memory_status, detail))
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        results.append(_check("memory", "fail", f"/v1/memory/stats failed: {exc}"))
    return results


def check_mcp_configs(repo_root: Path) -> list[Check]:
    configured: list[str] = []
    invalid: list[str] = []
    for client, relative in CLIENT_CONFIGS:
        path = repo_root / relative
        if not path.is_file():
            invalid.append(f"{client}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        required = ("core.mcp_stdio_proxy", "ANTIGRAVITY_MCP_URL", "PYTHONPATH")
        missing = [token for token in required if token not in text]
        if missing:
            invalid.append(f"{client}: missing {','.join(missing)}")
        else:
            configured.append(client)
    status = "ok" if len(configured) == len(CLIENT_CONFIGS) else "fail"
    detail = f"{len(configured)}/{len(CLIENT_CONFIGS)} client configs structurally ready"
    if invalid:
        detail = f"{detail}; {'; '.join(invalid)}"
    return [
        _check(
            "mcp-configs",
            status,
            detail,
            "Run nexus-app/scripts/verify-mcp-connections.ps1 for the live handshake.",
        )
    ]


def _resolve_python(repo_root: Path) -> Path | None:
    candidates = (
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
    )
    local = next((path for path in candidates if path.is_file()), None)
    if local:
        return local
    try:
        mcp_config = json.loads((repo_root / ".mcp.json").read_text(encoding="utf-8"))
        command = mcp_config["mcpServers"]["antigravity"]["command"]
        configured = Path(command)
        if configured.is_absolute() and configured.is_file():
            return configured
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass
    current = Path(sys.executable)
    return current if current.is_file() else None


def _command_check(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    environment: dict[str, str] | None = None,
) -> Check:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check(name, "fail", str(exc))
    output = f"{completed.stdout}\n{completed.stderr}".strip().splitlines()
    detail = output[-1][:500] if output else f"exit code {completed.returncode}"
    return _check(name, "ok" if completed.returncode == 0 else "fail", detail)


def check_injector(repo_root: Path) -> list[Check]:
    python = _resolve_python(repo_root)
    script = repo_root / ".agent" / "scripts" / "mcp_injector.py"
    if not python or not script.is_file():
        return [_check("injector", "fail", "runtime Python or mcp_injector.py is missing")]
    return [
        _command_check("injector", (str(python), str(script), "--help"), cwd=repo_root, timeout=30)
    ]


def _resolve_executable(name: str, common_windows_path: Path | None = None) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    if common_windows_path and common_windows_path.is_file():
        return str(common_windows_path)
    return None


def check_nexus(repo_root: Path) -> list[Check]:
    nexus_root = repo_root / "nexus-app"
    npm = _resolve_executable(
        "npm.cmd" if os.name == "nt" else "npm",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "nodejs" / "npm.cmd",
    )
    if not npm:
        return [_check("nexus-typescript", "fail", "npm was not found")]
    environment = dict(os.environ)
    node_dir = str(Path(npm).parent)
    environment["PATH"] = f"{node_dir}{os.pathsep}{environment.get('PATH', '')}"
    return [
        _command_check(
            "nexus-typescript",
            (npm, "run", "ts:app"),
            cwd=nexus_root,
            timeout=180,
            environment=environment,
        )
    ]


def check_opencodex() -> list[Check]:
    appdata = Path(os.environ.get("APPDATA", "")) if os.name == "nt" else None
    common_path = appdata / "npm" / "ocx.cmd" if appdata else None
    ocx = _resolve_executable("ocx.cmd" if os.name == "nt" else "ocx", common_path)
    if not ocx:
        return [
            _check(
                "opencodex",
                "fail",
                "ocx executable not found",
                "Install @bitkyc08/opencodex from the official package.",
            )
        ]
    running = _port_open("127.0.0.1", DEFAULT_OCX_PORT)
    return [
        _check(
            "opencodex",
            "ok",
            f"installed at {ocx}; proxy {'running' if running else 'stopped safely'}",
        )
    ]


def _read_json_utf8(path: Path) -> dict[str, Any] | None:
    """Load a JSON file forcing UTF-8.

    ``~/.claude.json`` holds Japanese characters and the Windows default codec
    (cp932) corrupts it, so the encoding is never left to the platform.

    Args:
        path: File to load.

    Returns:
        Parsed object, or ``None`` when missing or unreadable.
    """
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _claude_version() -> tuple[int, ...] | None:
    """Return the installed Claude Code version as a tuple, or ``None``."""
    executable = _resolve_executable("claude")
    if not executable:
        return None
    command = [executable, "--version"]
    if executable.lower().endswith((".cmd", ".bat")):
        # CreateProcess cannot launch batch wrappers directly.
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/c", *command]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    digits: list[int] = []
    for token in completed.stdout.split():
        parts = token.split(".")
        if len(parts) >= 3 and all(part.isdigit() for part in parts[:3]):
            digits = [int(part) for part in parts[:3]]
            break
    return tuple(digits) or None


def check_remote_control() -> list[Check]:
    """Audit the preconditions for Claude Code Remote Control (phone / claude.ai).

    Mirrors the diagnostic checklist that had to be applied by hand on
    2026-07-10, 2026-07-23 and 2026-07-26.  Read-only: every failure reports the
    repair as a hint instead of mutating client configuration.

    Returns:
        One check per precondition, all named with the ``remote-control`` prefix.
    """
    results: list[Check] = []
    home = Path.home()
    claude_json = _read_json_utf8(home / ".claude.json")
    settings = _read_json_utf8(home / ".claude" / "settings.json") or {}
    settings_env = settings.get("env") if isinstance(settings.get("env"), dict) else {}

    # 1. Local preference — lost on every PC reset, absent means false.
    if claude_json is None:
        results.append(
            _check(
                "remote-control.flag",
                "warn",
                "~/.claude.json is missing or unreadable",
                "Run `claude` once to recreate it, then enable Remote Control.",
            )
        )
    elif claude_json.get("remoteEnabled") is True:
        results.append(_check("remote-control.flag", "ok", "remoteEnabled=true in ~/.claude.json"))
    else:
        results.append(
            _check(
                "remote-control.flag",
                "fail",
                "remoteEnabled is not true in ~/.claude.json (absent counts as false)",
                "/config -> 'Enable Remote Control for all sessions', then restart Claude Code.",
            )
        )

    # 2. Proxy — mutually exclusive with Remote Control; re-injected by provider switches.
    base_url = settings_env.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
    if base_url:
        results.append(
            _check(
                "remote-control.proxy",
                "fail",
                f"ANTHROPIC_BASE_URL is set ({base_url})",
                "Delete ONLY that key from ~/.claude/settings.json (keep the rest of env) "
                "and restart Claude Code once. A provider toggle in Nexus re-injects it.",
            )
        )
    else:
        results.append(
            _check("remote-control.proxy", "ok", "ANTHROPIC_BASE_URL unset: proxy disconnected")
        )

    # 3. First-party OAuth login; API keys or third-party backends disable Remote Control.
    api_key_vars = [
        name
        for name in (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
        )
        if settings_env.get(name) or os.environ.get(name)
    ]
    if api_key_vars:
        results.append(
            _check(
                "remote-control.auth",
                "fail",
                f"non-OAuth credentials present: {', '.join(api_key_vars)}",
                "Remote Control requires the claude.ai OAuth login (first-party provider).",
            )
        )
    elif claude_json and claude_json.get("oauthAccount"):
        account = claude_json["oauthAccount"]
        email = account.get("emailAddress", "unknown") if isinstance(account, dict) else "unknown"
        results.append(_check("remote-control.auth", "ok", f"OAuth session for {email}"))
    else:
        results.append(
            _check(
                "remote-control.auth",
                "warn",
                "no oauthAccount found in ~/.claude.json",
                "Log in with `claude` using the claude.ai account paired on the phone.",
            )
        )

    # 4. Minimum CLI version that ships Remote Control.
    version = _claude_version()
    minimum = ".".join(str(part) for part in CLAUDE_MIN_VERSION)
    if version is None:
        results.append(
            _check(
                "remote-control.version",
                "warn",
                "could not resolve the `claude` executable version",
                f"Remote Control needs Claude Code >= {minimum}.",
            )
        )
    elif version >= CLAUDE_MIN_VERSION:
        results.append(
            _check(
                "remote-control.version",
                "ok",
                f"Claude Code {'.'.join(str(part) for part in version)} (>= {minimum})",
            )
        )
    else:
        results.append(
            _check(
                "remote-control.version",
                "fail",
                f"Claude Code {'.'.join(str(part) for part in version)} is older than {minimum}",
                "Update Claude Code.",
            )
        )
    return results


def build_report(
    repo_root: Path,
    *,
    gateway_url: str = DEFAULT_GATEWAY,
    skip_runtime: bool = False,
    skip_injector: bool = False,
    skip_nexus: bool = False,
    only_remote_control: bool = False,
) -> dict[str, Any]:
    checks: list[Check] = []
    if only_remote_control:
        checks.extend(check_remote_control())
    else:
        checks.extend(check_inventory(repo_root))
        checks.extend(check_environment(repo_root))
        checks.extend(check_mcp_configs(repo_root))
        checks.extend(check_opencodex())
        checks.extend(check_remote_control())
        if not skip_runtime:
            checks.extend(check_gateway(repo_root, gateway_url))
        if not skip_injector:
            checks.extend(check_injector(repo_root))
        if not skip_nexus:
            checks.extend(check_nexus(repo_root))
    counts = {
        status: sum(1 for check in checks if check.status == status)
        for status in ("ok", "warn", "fail")
    }
    return {
        "repo": str(repo_root),
        "healthy": counts["fail"] == 0,
        "summary": counts,
        "checks": [asdict(check) for check in checks],
    }


def _print_human(report: dict[str, Any]) -> None:
    icons = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
    for item in report["checks"]:
        print(f"{icons[item['status']]} {item['name']}: {item['detail']}")
        if item["hint"] and item["status"] != "ok":
            print(f"       hint: {item['hint']}")
    summary = report["summary"]
    print(f"Summary: {summary['ok']} ok, {summary['warn']} warnings, {summary['fail']} failures")


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY)
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--skip-injector", action="store_true")
    parser.add_argument("--skip-nexus", action="store_true")
    parser.add_argument(
        "--only-remote-control",
        action="store_true",
        help="run only the Remote Control preconditions (fast pre-flight before leaving the PC)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = build_report(
        args.repo_root.resolve(),
        gateway_url=args.gateway_url.rstrip("/"),
        skip_runtime=args.skip_runtime,
        skip_injector=args.skip_injector,
        skip_nexus=args.skip_nexus,
        only_remote_control=args.only_remote_control,
    )
    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human(report)
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
