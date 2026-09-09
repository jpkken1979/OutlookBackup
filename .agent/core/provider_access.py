"""Read-only provider access diagnostics.

This module deliberately observes authentication and bridge state without
reading token values, starting daemons, or mutating Codex configuration.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import TypedDict

_LOGIN_STATUS_TTL_S = 60.0
_login_status_cache: tuple[float, bool] | None = None


class OpenAIAccessState(TypedDict):
    """Safe, boolean-only OpenAI/Codex access state exposed to Nexus."""

    oauth_session_detected: bool
    bridge_healthy: bool
    codex_config_redirected: bool


_OPENCODEX_OAUTH_PROVIDERS = frozenset({"google-antigravity", "github-copilot"})


def reset_access_cache() -> None:
    """Clear the short-lived CLI status cache (mainly useful for tests)."""
    global _login_status_cache
    _login_status_cache = None


def codex_oauth_session_detected() -> bool:
    """Return whether the official Codex CLI reports an authenticated session.

    Only the process exit code is retained. Captured output is never returned,
    logged, or persisted because it may change across Codex versions.
    """
    global _login_status_cache
    now = time.monotonic()
    if _login_status_cache is not None and now - _login_status_cache[0] < _LOGIN_STATUS_TTL_S:
        return _login_status_cache[1]

    command = shutil.which("codex")
    if not command:
        detected = False
    else:
        try:
            result = subprocess.run(  # noqa: S603 - resolved executable, fixed args
                [command, "login", "status"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            detected = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            detected = False

    _login_status_cache = (now, detected)
    return detected


def bridge_healthy(host: str = "127.0.0.1", port: int = 10100) -> bool:
    """Probe the optional local OAuth bridge without starting it."""
    try:
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except OSError:
        return False


def codex_config_redirected(config_path: Path | None = None) -> bool:
    """Detect whether Codex is pointed at the optional loopback bridge.

    The file is inspected in memory and only a boolean is returned. Token-like
    fields and all other configuration values stay private.
    """
    if config_path is None:
        codex_home = os.environ.get("CODEX_HOME")
        config_path = (
            Path(codex_home) / "config.toml"
            if codex_home
            else Path.home() / ".codex" / "config.toml"
        )
    try:
        content = config_path.read_text(encoding="utf-8")[:262_144].casefold()
    except OSError:
        return False
    return "127.0.0.1:10100" in content or "localhost:10100" in content


def get_openai_access_state(
    *,
    config_path: Path | None = None,
) -> OpenAIAccessState:
    """Build the boolean-only access contract consumed by Nexus."""
    return {
        "oauth_session_detected": codex_oauth_session_detected(),
        "bridge_healthy": bridge_healthy(),
        "codex_config_redirected": codex_config_redirected(config_path),
    }


def opencodex_oauth_session_detected(
    provider_id: str,
    *,
    auth_path: Path | None = None,
) -> bool:
    """Return whether OpenCodex stores at least one account for ``provider_id``.

    Only the JSON structure and account count are observed. Account objects are
    never returned, logged, or copied into Nexus because they may contain OAuth
    material owned by OpenCodex.
    """
    normalized = provider_id.strip().lower()
    if normalized not in _OPENCODEX_OAUTH_PROVIDERS:
        return False
    path = auth_path or Path.home() / ".opencodex" / "auth.json"
    try:
        if path.stat().st_size > 1_048_576:
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    provider = payload.get(normalized)
    if not isinstance(provider, dict):
        return False
    accounts = provider.get("accounts")
    return isinstance(accounts, list) and bool(accounts)


def get_opencodex_provider_access_state(
    provider_id: str,
    *,
    auth_path: Path | None = None,
) -> OpenAIAccessState:
    """Build the boolean-only state for an OAuth provider served by OpenCodex."""
    return {
        "oauth_session_detected": opencodex_oauth_session_detected(
            provider_id,
            auth_path=auth_path,
        ),
        "bridge_healthy": bridge_healthy(),
        # This flag belongs only to the native Codex/OpenAI integration.
        "codex_config_redirected": False,
    }
