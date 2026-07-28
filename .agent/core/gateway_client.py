"""Shared authenticated Python client for the local Antigravity gateway.

Hooks, stdio shims and SDK entrypoints resolve the encrypted credential through
one function. Secrets are never included in exceptions, logs or persisted
configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_GATEWAY_URL = "http://127.0.0.1:4747"
RETRYABLE_STATUSES = frozenset({502, 503, 504})


class GatewayClientError(RuntimeError):
    """Redacted gateway failure safe to display in hooks and CLIs."""


def resolve_gateway_token() -> str:
    """Resolve an explicit token or decrypt the per-user local session key."""

    explicit = os.environ.get("ANTIGRAVITY_API_KEY", "").strip()
    if explicit:
        return explicit
    try:
        from core.session_key import read_session_key

        return read_session_key() or ""
    except (ImportError, OSError, ValueError):
        return ""


def _normalize_base_url(raw: str) -> str:
    value = raw.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid gateway URL")
    return value


def _validate_path(path: str) -> str:
    if (
        not path.startswith("/")
        or "://" in path
        or ".." in path.split("/")
        or "\r" in path
        or "\n" in path
    ):
        raise ValueError("Invalid gateway path")
    return path


class GatewayClient:
    """Small synchronous client with auth rotation, timeout and safe retries."""

    def __init__(self, base_url: str = DEFAULT_GATEWAY_URL, timeout: float = 10.0):
        self.base_url = _normalize_base_url(base_url)
        self.timeout = max(0.1, min(float(timeout), 130.0))

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        endpoint = f"{self.base_url}{_validate_path(path)}"
        encoded = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        retryable_request = method in {"GET", "HEAD"} or bool(idempotency_key)
        for attempt in range(3):
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Request-Id": f"python-{time.time_ns():x}",
            }
            token = resolve_gateway_token()
            if token:
                headers["X-API-Key"] = token
            if idempotency_key:
                headers["X-Idempotency-Key"] = idempotency_key
            request = urllib.request.Request(
                endpoint,
                data=encoded,
                headers=headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                label = {
                    401: "AUTH_REQUIRED",
                    403: "FORBIDDEN",
                    429: "RATE_LIMITED",
                }.get(exc.code, "GATEWAY_ERROR" if exc.code >= 500 else "REQUEST_REJECTED")
                if retryable_request and exc.code in RETRYABLE_STATUSES and attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise GatewayClientError(f"Gateway HTTP {exc.code} ({label})") from None
            except (urllib.error.URLError, TimeoutError):
                if retryable_request and attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise GatewayClientError("Gateway unavailable; retry exhausted") from None
            except json.JSONDecodeError:
                raise GatewayClientError("Gateway returned invalid JSON") from None
        raise GatewayClientError("Gateway unavailable")

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            path,
            payload=payload,
            idempotency_key=idempotency_key,
        )


def _session_report_payload() -> tuple[dict[str, Any], str]:
    hook_input: dict[str, Any] = {}
    if not sys.stdin.isatty():
        try:
            incoming = json.load(sys.stdin)
            if isinstance(incoming, dict):
                hook_input = incoming
        except (json.JSONDecodeError, OSError):
            pass
    project_dir = Path(text if (text := str(hook_input.get("cwd") or "").strip()) else Path.cwd())
    project = project_dir.name or "unknown"
    session_id = str(hook_input.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "")
    summary = str(
        hook_input.get("summary")
        or os.environ.get("CLAUDE_SESSION_SUMMARY")
        or "Session ended"
    )[:20_000]
    payload = {
        "project": project,
        "summary": summary,
        "files_changed": [],
        "decisions": [],
        "errors": [],
    }
    stable = json.dumps(
        {"project": project, "session_id": session_id, "summary": summary},
        sort_keys=True,
        separators=(",", ":"),
    )
    return payload, f"hook_{hashlib.sha256(stable.encode('utf-8')).hexdigest()}"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI used by the frozen portable executable and source-mode hooks."""

    parser = argparse.ArgumentParser(prog="antigravity-gateway-client")
    parser.add_argument("operation", choices=("session-report",))
    parser.add_argument(
        "--gateway",
        default=os.environ.get("ANTIGRAVITY_GATEWAY_URL", DEFAULT_GATEWAY_URL),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.operation == "session-report":
        payload, key = _session_report_payload()
        try:
            GatewayClient(args.gateway, timeout=5).post(
                "/v1/hooks/session-report",
                payload,
                idempotency_key=key,
            )
        except GatewayClientError:
            # Session finalization must never block or break the IDE.
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
