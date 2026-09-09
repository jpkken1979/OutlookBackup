"""Portable, secret-free discovery contract for OpenAntigravity Nexus clients."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from typing import Final

SCHEMA_VERSION: Final = "nexus-manifest-v1"
SCHEMA_REVISION: Final = 2
MCP_PROTOCOL_VERSION: Final = "2025-11-25"
MINIMUM_NEXUS_VERSION: Final = "2.8.7"
_VALID_STATES: Final = frozenset({"ready", "degraded", "unavailable"})
_VALID_CHANNELS: Final = frozenset({"stable", "canary", "development"})

_ENDPOINTS: Final = {
    "manifest": {"method": "GET", "path": "/v1/nexus/manifest"},
    "health": {"method": "GET", "path": "/v1/health"},
    "readiness": {"method": "GET", "path": "/v1/ready"},
    "mcp": {
        "method": "POST",
        "path": "/mcp",
        "transport": "streamable_http",
    },
    "mcp_catalog": {"method": "GET", "path": "/v1/mcp/catalog"},
    "agents": {"method": "GET", "path": "/v1/agents"},
    "skills": {"method": "GET", "path": "/v1/skills"},
    "brain": {"method": "GET", "path": "/v1/brain/query"},
    "memory": {"method": "POST", "path": "/v1/memory/recall"},
    "providers": {"method": "GET", "path": "/v1/provider/status"},
    "turn_continuity": {"method": "GET", "path": "/v1/routing/turns"},
    "rules": {"method": "GET", "path": "/v1/rules/global"},
}

_CAPABILITY_DISCOVERY: Final = {
    "agents": "/v1/agents",
    "skills": "/v1/skills",
    "mcp": "/v1/mcp/catalog",
    "brain": "/v1/brain/query",
    "memory": "/v1/memory/recall",
    "providers": "/v1/provider/status",
    "rules": "/v1/rules/global",
}


def _normalize_state(value: object) -> str:
    if isinstance(value, str) and value in _VALID_STATES:
        return value
    return "degraded"


def _runtime_identity() -> dict[str, object]:
    """Build a redacted identity for the runtime that serves this process."""

    channel = os.environ.get("ANTIGRAVITY_RUNTIME_CHANNEL", "development").strip().lower()
    if channel not in _VALID_CHANNELS:
        channel = "development"
    build_sha = os.environ.get("ANTIGRAVITY_BUILD_SHA", "unknown").strip() or "unknown"
    root_fingerprint = (
        os.environ.get("ANTIGRAVITY_RUNTIME_ROOT_FINGERPRINT", "unknown").strip() or "unknown"
    )
    return {
        "channel": channel,
        "build_sha": build_sha,
        "root_fingerprint": root_fingerprint,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "schema_revision": SCHEMA_REVISION,
    }


def _fingerprint_manifest(manifest: Mapping[str, object]) -> str:
    canonical = json.dumps(
        manifest,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def build_nexus_manifest(
    *,
    gateway_version: str,
    ecosystem_version: str,
    authentication_required: bool,
    capability_states: Mapping[str, object] | None = None,
    effective_rules: list[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build the client discovery manifest without reading environment secrets."""

    supplied_states = capability_states or {}
    capabilities = {
        capability_id: {
            "status": _normalize_state(supplied_states.get(capability_id)),
            "discovery": discovery,
        }
        for capability_id, discovery in _CAPABILITY_DISCOVERY.items()
    }
    status = (
        "ready" if all(item["status"] == "ready" for item in capabilities.values()) else "degraded"
    )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "id": "openantigravity.nexus",
            "name": "OpenAntigravity Nexus",
            "gateway_version": gateway_version,
            "ecosystem_version": ecosystem_version,
        },
        "runtime": _runtime_identity(),
        "compatibility": {
            "minimum_nexus_version": MINIMUM_NEXUS_VERSION,
            "supported_manifest_schemas": [SCHEMA_VERSION],
            "mcp_protocol_version": MCP_PROTOCOL_VERSION,
        },
        "status": status,
        "authentication": {
            "required": authentication_required,
            "scheme": "api_key",
            "header": "X-API-Key",
            "credential_ref": "env:ANTIGRAVITY_API_KEY",
        },
        "endpoints": {name: dict(endpoint) for name, endpoint in _ENDPOINTS.items()},
        "capabilities": capabilities,
        "rules": {
            "status": capabilities["rules"]["status"],
            "discovery": _CAPABILITY_DISCOVERY["rules"],
            "effective": [dict(rule) for rule in effective_rules or ()],
        },
    }
    manifest["manifest_fingerprint"] = _fingerprint_manifest(manifest)
    return manifest
