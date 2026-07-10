#!/usr/bin/env python3
"""Common utilities for resilient Antigravity memory hooks.

Goals:
- Avoid data loss when gateway is temporarily offline.
- Deduplicate repeated events.
- Keep hooks lightweight and safe (never crash caller).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("antigravity.memory-hooks")

GATEWAY = os.getenv("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747").rstrip("/")
# Hooks run synchronously inside Claude Code. Keep their client-side budget
# short: mem0 is an optional cache and must never delay the interactive shell.
TIMEOUT = 2.0
QUEUE_FLUSH_LIMIT = 25
SENT_IDS_LIMIT = 2000
HOOK_USER_ID = "nexus-memory-hooks"
PRIVATE_TAG_PATTERN = re.compile(r"<private>.*?</private>", re.IGNORECASE | re.DOTALL)
DEFAULT_HOOK_CONFIG: dict[str, Any] = {
    "disclosure_level": "compact",
    "session_start_limit": 5,
    "session_start_max_items": 3,
    "capture_post_tool_use": True,
    "capture_user_prompt_submit": True,
    "capture_session_end": True,
    "capture_stop_marker": True,
    "notebooklm_auto_recall": True,
    "notebooklm_auto_recall_timeout": 25,
    "post_tool_tracked_tools": ["Write", "Edit", "Bash"],
    "queue_retention_days": 30,
}


def _memory_data_dir() -> Path:
    env_dir = os.getenv("MEM0_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".antigravity" / "memory"


def _hooks_state_dir() -> Path:
    state_dir = _memory_data_dir() / "hooks"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


QUEUE_FILE = _hooks_state_dir() / "pending-events.jsonl"
SENT_IDS_FILE = _hooks_state_dir() / "sent-event-ids.json"
HOOK_CONFIG_FILE = _hooks_state_dir() / "config.json"


@dataclass
class StoreResult:
    success: bool
    queued: bool
    event_id: str


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _read_gateway_api_key() -> str:
    """Read the gateway credential without generating or logging a new key."""
    explicit = os.getenv("ANTIGRAVITY_API_KEY", "").strip()
    if explicit:
        return explicit

    candidate_roots: list[Path] = []
    antigravity_root = os.getenv("ANTIGRAVITY_ROOT", "").strip()
    if antigravity_root:
        candidate_roots.append(Path(antigravity_root) / ".agent")
    candidate_roots.append(Path(__file__).resolve().parents[2])

    for agent_root in candidate_roots:
        if not (agent_root / "mcp" / "session_key.py").exists():
            continue
        root_text = str(agent_root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        try:
            from mcp.session_key import read_session_key

            return (read_session_key() or "").strip()
        except Exception:  # noqa: BLE001
            continue

    # Los hooks se ejecutan fuera del proceso del gateway y no siempre heredan
    # el entorno de la app. Reutilizan la clave local ya configurada, sin
    # registrarla ni modificar el archivo.
    for agent_root in candidate_roots:
        env_path = agent_root.parent / ".env"
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                key, separator, value = raw_line.partition("=")
                if separator and key.strip() == "ANTIGRAVITY_API_KEY":
                    return value.strip().strip("\"'")
        except OSError:
            continue
    return ""


def _gateway_headers(*, json_body: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if json_body:
        headers["Content-Type"] = "application/json"
    api_key = _read_gateway_api_key()
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _event_id(event_key: str, content: str, metadata: dict[str, Any]) -> str:
    fingerprint = _json_dumps(
        {"event_key": event_key, "content": content, "metadata": metadata},
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"evt_{digest[:24]}"


def _request_json(method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{GATEWAY}{path}",
        data=_json_dumps(payload).encode("utf-8"),
        headers=_gateway_headers(json_body=True),
        method=method,
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body) if body.strip() else {}


def sanitize_private_content(content: str) -> str:
    """Remove content wrapped in <private>...</private> tags."""
    if not content:
        return ""
    cleaned = PRIVATE_TAG_PATTERN.sub("", content)
    return cleaned.strip()


def get_hook_config() -> dict[str, Any]:
    config = dict(DEFAULT_HOOK_CONFIG)
    if not HOOK_CONFIG_FILE.exists():
        return config
    try:
        raw = json.loads(HOOK_CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return config
    except Exception:  # noqa: BLE001
        return config

    config["disclosure_level"] = (
        raw.get("disclosure_level")
        if raw.get("disclosure_level") in {"compact", "full"}
        else config["disclosure_level"]
    )

    def _safe_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    config["session_start_limit"] = _safe_int(
        raw.get("session_start_limit", config["session_start_limit"]),
        int(config["session_start_limit"]),
    )
    config["session_start_max_items"] = _safe_int(
        raw.get("session_start_max_items", config["session_start_max_items"]),
        int(config["session_start_max_items"]),
    )
    config["capture_post_tool_use"] = bool(
        raw.get("capture_post_tool_use", config["capture_post_tool_use"])
    )
    config["capture_user_prompt_submit"] = bool(
        raw.get("capture_user_prompt_submit", config["capture_user_prompt_submit"])
    )
    config["capture_session_end"] = bool(
        raw.get("capture_session_end", config["capture_session_end"])
    )
    config["capture_stop_marker"] = bool(
        raw.get("capture_stop_marker", config["capture_stop_marker"])
    )
    config["notebooklm_auto_recall"] = bool(
        raw.get("notebooklm_auto_recall", config["notebooklm_auto_recall"])
    )
    config["notebooklm_auto_recall_timeout"] = _safe_int(
        raw.get("notebooklm_auto_recall_timeout", config["notebooklm_auto_recall_timeout"]),
        int(config["notebooklm_auto_recall_timeout"]),
    )
    config["queue_retention_days"] = _safe_int(
        raw.get("queue_retention_days", config["queue_retention_days"]),
        int(config["queue_retention_days"]),
    )

    tools = raw.get("post_tool_tracked_tools")
    if isinstance(tools, list):
        normalized = [str(item) for item in tools if str(item).strip()]
        if normalized:
            config["post_tool_tracked_tools"] = normalized

    # Basic safety clamps
    config["session_start_limit"] = max(1, min(50, int(config["session_start_limit"])))
    config["session_start_max_items"] = max(1, min(20, int(config["session_start_max_items"])))
    config["notebooklm_auto_recall_timeout"] = max(
        5,
        min(60, int(config["notebooklm_auto_recall_timeout"])),
    )
    config["queue_retention_days"] = max(1, min(365, int(config["queue_retention_days"])))
    return config


def _load_sent_ids() -> list[str]:
    if not SENT_IDS_FILE.exists():
        return []
    try:
        raw = json.loads(SENT_IDS_FILE.read_text(encoding="utf-8"))
        ids = raw.get("ids", [])
        return [str(item) for item in ids if isinstance(item, str)]
    except Exception:  # noqa: BLE001
        return []


def _save_sent_ids(ids: list[str]) -> None:
    trimmed = ids[-SENT_IDS_LIMIT:]
    SENT_IDS_FILE.write_text(
        _json_dumps({"ids": trimmed}),
        encoding="utf-8",
    )


def _is_sent(event_id: str) -> bool:
    return event_id in set(_load_sent_ids())


def _mark_sent(event_id: str) -> None:
    ids = _load_sent_ids()
    if event_id in ids:
        return
    ids.append(event_id)
    _save_sent_ids(ids)


def _read_queue() -> list[dict[str, Any]]:
    if not QUEUE_FILE.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with QUEUE_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if isinstance(event, dict):
                        events.append(event)
                except json.JSONDecodeError:
                    continue
    except Exception:  # noqa: BLE001
        return []
    return events


def _write_queue(events: list[dict[str, Any]]) -> None:
    tmp_path = QUEUE_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(_json_dumps(event))
            fh.write("\n")
    tmp_path.replace(QUEUE_FILE)


def _enqueue_event(event: dict[str, Any]) -> None:
    events = _read_queue()
    events.append(event)
    _write_queue(events)


def _send_store_event(event: dict[str, Any]) -> bool:
    metadata = dict(event["metadata"])
    # Hook events prioritize shell responsiveness over Ollama fact extraction.
    # The semantic fast path still stores the full event in ChromaDB.
    metadata.setdefault("skip_fact_extraction", True)
    payload = {
        "content": event["content"],
        "user_id": HOOK_USER_ID,
        "metadata": metadata,
    }
    result = _request_json("POST", "/v1/mem0/store", payload)
    success = bool(result.get("success", True))
    if not success:
        logger.warning(
            "Gateway rejected event %s: %s",
            event.get("event_id", "?")[:16],
            json.dumps(result, ensure_ascii=False)[:200],
        )
    return success


def flush_pending_events(max_items: int = QUEUE_FLUSH_LIMIT) -> tuple[int, int]:
    events = _read_queue()
    if not events:
        return (0, 0)

    sent_count = 0
    pending: list[dict[str, Any]] = []
    attempted = 0
    stop_flushing = False

    for event in events:
        event_id = str(event.get("event_id", ""))
        if not event_id:
            continue

        if _is_sent(event_id):
            sent_count += 1
            continue

        if attempted >= max_items or stop_flushing:
            pending.append(event)
            continue

        attempted += 1
        try:
            ok = _send_store_event(event)
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
            pending.append(event)
            stop_flushing = True
            continue
        except urllib.error.HTTPError as http_err:
            if http_err.code == 429:
                logger.warning(
                    "Rate limited (429) — stopping flush, %d events remain",
                    len(events) - attempted,
                )
            else:
                logger.warning(
                    "HTTP %d for event %s: %s", http_err.code, event_id[:16], http_err.reason
                )
            pending.append(event)
            stop_flushing = True
            continue
        except Exception:  # noqa: BLE001
            pending.append(event)
            stop_flushing = True
            continue

        if ok:
            _mark_sent(event_id)
            sent_count += 1
        else:
            pending.append(event)

    if len(pending) < len(events):
        _write_queue(pending)

    if len(pending) > 0 and attempted > 0:
        logger.info(
            "flush_pending_events: sent=%d, remaining=%d, attempted=%d/%d",
            sent_count,
            len(pending),
            attempted,
            len(events),
        )

    return (sent_count, len(pending))


def store_memory_event(
    *,
    content: str,
    metadata: dict[str, Any],
    event_key: str,
) -> StoreResult:
    if not content.strip():
        return StoreResult(success=False, queued=False, event_id="")

    normalized_metadata = dict(metadata)
    normalized_metadata.setdefault("source", "nexus-memory-hooks")
    normalized_metadata.setdefault("date", datetime.now(UTC).isoformat())

    event_id = _event_id(event_key=event_key, content=content, metadata=normalized_metadata)
    normalized_metadata["event_id"] = event_id

    if _is_sent(event_id):
        return StoreResult(success=True, queued=False, event_id=event_id)

    event = {
        "event_id": event_id,
        "content": content,
        "metadata": normalized_metadata,
    }

    try:
        _send_store_event(event)
        _mark_sent(event_id)
        flush_pending_events()
        return StoreResult(success=True, queued=False, event_id=event_id)
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
        _enqueue_event(event)
        return StoreResult(success=False, queued=True, event_id=event_id)
    except Exception:  # noqa: BLE001
        _enqueue_event(event)
        return StoreResult(success=False, queued=True, event_id=event_id)


def gateway_is_reachable(timeout: float = 1.0) -> bool:
    """Fast probe for gateway health.

    Returns True if `GET /v1/health` responds with 2xx in under `timeout` seconds.
    Uses a short timeout so hooks do not block the session start.
    """
    try:
        req = urllib.request.Request(f"{GATEWAY}/v1/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001
        return False


def pending_queue_size() -> int:
    """Returns the number of events queued locally waiting to be flushed."""
    if not QUEUE_FILE.exists():
        return 0
    try:
        with QUEUE_FILE.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except Exception:  # noqa: BLE001
        return 0


def recall_recent_context(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Recall memories from the gateway. Uses GET /v1/mem0/recall?q=...&limit=..."""
    try:
        params = urllib.parse.urlencode({"q": query, "limit": str(limit)})
        url = f"{GATEWAY}/v1/mem0/recall?{params}"
        req = urllib.request.Request(url, headers=_gateway_headers(), method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        result: dict[str, Any] = json.loads(body) if body.strip() else {}
    except Exception:  # noqa: BLE001
        return []

    data = result.get("data", {})
    if isinstance(data, dict):
        entries = data.get("results", data.get("memories", []))
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []
