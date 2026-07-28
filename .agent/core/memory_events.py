"""Typed memory event store for operational auditing.

This module provides a small JSONL-backed event ledger used by gateway handlers
and other runtime components to persist normalized events such as
``error.detected`` and ``fix.applied``.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.log_rotation import rotate_jsonl_if_needed

ALLOWED_EVENT_TYPES: set[str] = {
    "error.detected",
    "fix.applied",
    "decision.made",
    "provider.switched",
    "memory.stored",
    "memory.recalled",
    "planner.executed",
    "planner.failed",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def events_log_path() -> Path:
    """Return the canonical JSONL file used to store typed events."""
    return _repo_root() / ".agent" / "memory" / "events.jsonl"


def _normalize_type(event_type: str) -> str:
    value = str(event_type or "").strip()
    return value if value in ALLOWED_EVENT_TYPES else "decision.made"


def record_event(
    *,
    event_type: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
    source: str = "gateway",
    severity: str = "info",
    user_id: str = "antigravity",
) -> dict[str, Any]:
    """Persist a typed event in JSONL and return the stored payload.

    Args:
        event_type: Canonical event type string.
        summary: Human-readable event summary.
        metadata: Optional structured context.
        source: Producer system.
        severity: info|warning|error.
        user_id: Logical user identity.

    Returns:
        Stored event payload.
    """
    clean_summary = str(summary or "").strip()
    if not clean_summary:
        raise ValueError("summary is required")

    now = datetime.now(UTC).isoformat()
    event = {
        "id": uuid.uuid4().hex,
        "type": _normalize_type(event_type),
        "summary": clean_summary,
        "metadata": dict(metadata or {}),
        "source": str(source or "gateway"),
        "severity": str(severity or "info"),
        "user_id": str(user_id or "antigravity"),
        "created_at": now,
    }

    target = events_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    rotate_jsonl_if_needed(target, max_lines=5000)

    return event


def list_events(*, limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
    """Return latest typed events from JSONL ledger."""
    path = events_log_path()
    if not path.exists():
        return []

    try:
        capped = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        capped = 50

    normalized_type = _normalize_type(event_type) if event_type else None

    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if normalized_type and item.get("type") != normalized_type:
            continue
        rows.append(item)

    return rows[-capped:][::-1]
