"""Small per-client adapters that point AI applications at Nexus via MCP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .io_utils import write_json_file


@dataclass(frozen=True)
class ClientProfile:
    id: str
    name: str
    mcp_config: str
    rules_file: str


_CLIENT_PROFILES = (
    ClientProfile("claude", "Claude Code", ".mcp.json", "CLAUDE.md"),
    ClientProfile("codex", "Codex", ".codex/config.toml", "AGENTS.md"),
    ClientProfile("opencode", "OpenCode", "opencode.json", "AGENTS.md"),
    ClientProfile("cursor", "Cursor", ".cursor/mcp.json", ".cursorrules"),
    ClientProfile("windsurf", "Windsurf", ".windsurf/mcp.json", ".windsurfrules"),
    ClientProfile(
        "vscode",
        "VS Code / Copilot",
        ".vscode/mcp.json",
        ".github/copilot-instructions.md",
    ),
    ClientProfile("zed", "Zed", ".zed/settings.json", "AGENTS.md"),
    ClientProfile("continue", "Continue", ".continue/config.json", "AGENTS.md"),
    ClientProfile("gemini", "Gemini CLI", ".gemini/settings.json", "GEMINI.md"),
    ClientProfile("generic", "Generic MCP client", ".mcp.json", "AGENTS.md"),
)
_PROFILES_BY_ID = {profile.id: profile for profile in _CLIENT_PROFILES}
DEFAULT_CLIENT_IDS = tuple(profile.id for profile in _CLIENT_PROFILES)


def get_client_profiles() -> tuple[ClientProfile, ...]:
    """Return the canonical client profiles used by the workspace injector."""

    return _CLIENT_PROFILES


def _normalize_gateway_url(gateway_url: str) -> str:
    parsed = urlsplit(gateway_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("gateway_url must be an absolute HTTP(S) URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/mcp"):
        path = path[: -len("/mcp")]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _resolve_profiles(clients: tuple[str, ...] | list[str]) -> list[ClientProfile]:
    requested = set(clients)
    unknown = sorted(requested.difference(_PROFILES_BY_ID))
    if unknown:
        raise ValueError(f"unsupported Nexus client profile(s): {', '.join(unknown)}")
    return [profile for profile in _CLIENT_PROFILES if profile.id in requested]


def build_client_adapter(
    *,
    clients: tuple[str, ...] | list[str],
    gateway_url: str,
) -> dict[str, object]:
    """Build a secret-free adapter; agents and skills stay behind the broker."""

    base_url = _normalize_gateway_url(gateway_url)
    profiles = _resolve_profiles(clients)
    return {
        "schema_version": "nexus-client-adapter-v1",
        "nexus": {
            "id": "openantigravity.nexus",
            "base_url": base_url,
            "manifest_url": f"{base_url}/v1/nexus/manifest",
            "health_url": f"{base_url}/v1/health",
            "mcp_url": f"{base_url}/mcp",
            "authentication": {
                "scheme": "api_key",
                "header": "X-API-Key",
                "credential_ref": "env:ANTIGRAVITY_API_KEY",
            },
        },
        "discovery": {
            "agents": "/v1/agents",
            "skills": "/v1/skills",
            "mcp_catalog": "/v1/mcp/catalog",
            "brain": "/v1/brain/query",
            "memory": "/v1/memory/recall",
            "providers": "/v1/provider/status",
            "rules": "/v1/rules/global",
        },
        "materialization": {
            "agents": "mcp_on_demand",
            "skills": "mcp_on_demand",
            "bulk_copy_default": False,
            "offline_bundle_opt_in": True,
        },
        "managed_rules": {
            "strategy": "marked_block_only",
            "optimistic_concurrency": "external_sha256",
        },
        "clients": [asdict(profile) for profile in profiles],
    }


def install_client_adapter(
    target_dir: Path,
    *,
    clients: tuple[str, ...] | list[str] = DEFAULT_CLIENT_IDS,
    gateway_url: str,
) -> Path:
    """Write the fully managed adapter file and return its path."""

    path = target_dir / ".antigravity" / "nexus-client.json"
    payload = build_client_adapter(clients=clients, gateway_url=gateway_url)
    if not write_json_file(path, payload):
        raise OSError(f"could not write Nexus client adapter: {path}")
    return path
