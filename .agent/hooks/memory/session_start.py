#!/usr/bin/env python3
"""Antigravity Memory Hook — SessionStart.

Resilient startup hook:
- Flushes queued unsent events first (best effort).
- Recalls relevant context for the current project.
- Never crashes caller if gateway is down.
"""

from __future__ import annotations

import json
import os
import sys

from common import (
    GATEWAY,
    flush_pending_events,
    gateway_is_reachable,
    get_hook_config,
    pending_queue_size,
    recall_recent_context,
)

DEFAULT_LIMIT = 5
DEFAULT_MAX_ITEMS = 3
DEFAULT_MAX_CHARS_COMPACT = 90
DEFAULT_MAX_CHARS_FULL = 220


def _mode() -> str:
    config_mode = str(get_hook_config().get("disclosure_level", "compact"))
    value = os.getenv("AG_MEMORY_DISCLOSURE_LEVEL", config_mode).strip().lower()
    return value if value in {"compact", "full"} else "compact"


def _to_int(env_key: str, fallback: int) -> int:
    raw = os.getenv(env_key, "")
    try:
        parsed = int(raw)
        return parsed if parsed > 0 else fallback
    except ValueError:
        return fallback


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(3, limit - 3)] + "..."


def _format_line(memory: dict[str, object], max_chars: int) -> str:
    content = str(memory.get("content", "")).strip()
    memory_id = str(memory.get("id", "")).strip()
    metadata = memory.get("metadata", {})
    kind = ""
    if isinstance(metadata, dict):
        kind = str(metadata.get("type", "")).strip()

    prefix_parts = []
    if kind:
        prefix_parts.append(kind)
    if memory_id:
        prefix_parts.append(memory_id[:8])
    prefix = f"[{' | '.join(prefix_parts)}] " if prefix_parts else ""
    return prefix + _truncate(content, max_chars)


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        cwd = data.get("cwd", "")

        # Fast offline check: if gateway is unreachable, print a single line
        # warning and exit early instead of silently doing nothing. The brain
        # and .claude/memory/ markdown layers still work — only semantic recall
        # is unavailable.
        if not gateway_is_reachable():
            queued = pending_queue_size()
            suffix = f" ({queued} evento(s) encolado(s))" if queued else ""
            print(
                f"[Antigravity Memory] gateway offline ({GATEWAY}) — recall semantico "
                f"deshabilitado{suffix}. Brain y .claude/memory/ siguen funcionando."
            )
            return

        # Best effort queue flush before recall.
        flush_pending_events()

        hook_config = get_hook_config()
        limit = _to_int(
            "AG_MEMORY_SESSION_START_LIMIT",
            int(hook_config.get("session_start_limit", DEFAULT_LIMIT)),
        )
        max_items = _to_int(
            "AG_MEMORY_SESSION_START_MAX_ITEMS",
            int(hook_config.get("session_start_max_items", DEFAULT_MAX_ITEMS)),
        )
        disclosure = _mode()
        max_chars = DEFAULT_MAX_CHARS_FULL if disclosure == "full" else DEFAULT_MAX_CHARS_COMPACT

        query = f"recent session context {cwd}" if cwd else "recent session context"
        memories = recall_recent_context(query=query, limit=limit)

        if memories:
            total_chars = sum(
                len(str(m.get("content", ""))) for m in memories if isinstance(m, dict)
            )
            print(
                f"[Antigravity Memory] {len(memories)} memoria(s) "
                f"(mode={disclosure}, chars~{total_chars})",
            )
            for memory in memories[:max_items]:
                if not isinstance(memory, dict):
                    continue
                print(f"  • {_format_line(memory, max_chars)}")
        else:
            print("[Antigravity Memory] gateway OK, sin memorias relevantes")

    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
