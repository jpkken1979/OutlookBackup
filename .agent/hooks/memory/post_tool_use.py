#!/usr/bin/env python3
"""Antigravity Memory Hook — PostToolUse.

Captures significant tool use events and stores them in mem0.
If gateway is down, events are queued and retried later.
Called by Claude Code after each tool execution.
Input (stdin): {"tool_name": "...", "tool_input": {...}, "tool_response": {...}}
"""

from __future__ import annotations

import json
import sys

from common import (
    get_hook_config,
    sanitize_private_content,
    store_memory_event,
)


def build_content(tool_name: str, tool_input: dict) -> str | None:
    if tool_name == "Write":
        path = tool_input.get("file_path", "")
        preview = sanitize_private_content(str(tool_input.get("content", "")))[:80]
        return f"Wrote file: {path} — {preview}"
    if tool_name == "Edit":
        path = tool_input.get("file_path", "")
        old = sanitize_private_content(str(tool_input.get("old_string", "")))[:40]
        return f"Edited file: {path} — replaced: {old}"
    if tool_name == "Bash":
        cmd = sanitize_private_content(str(tool_input.get("command", "")))[:120]
        return f"Ran command: {cmd}"
    return None


def main() -> None:
    try:
        hook_config = get_hook_config()
        if not bool(hook_config.get("capture_post_tool_use", True)):
            return

        tracked_tools = {
            str(tool).strip()
            for tool in hook_config.get("post_tool_tracked_tools", [])
            if str(tool).strip()
        } or {"Write", "Edit", "Bash"}

        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        tool_name = data.get("tool_name", "")

        if tool_name not in tracked_tools:
            return

        tool_input = data.get("tool_input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}

        content = build_content(tool_name, tool_input)
        if not content.strip():
            return

        session_id = str(data.get("session_id", ""))[:16]
        cwd = str(data.get("cwd", ""))[:300]
        event_key = f"{tool_name}|{session_id}|{content[:120]}"

        store_memory_event(
            content=content,
            metadata={
                "type": "tool_use",
                "tool": tool_name,
                "session_id": session_id,
                "cwd": cwd,
            },
            event_key=event_key,
        )
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
