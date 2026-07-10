#!/usr/bin/env python3
"""Antigravity Memory Hook — SessionEnd.

Stores final session marker for stronger cross-session continuity.
"""

from __future__ import annotations

import datetime
import json
import sys

from common import get_hook_config, store_memory_event


def main() -> None:
    try:
        hook_config = get_hook_config()
        if not bool(hook_config.get("capture_session_end", True)):
            return

        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            return

        session_id = str(data.get("session_id", "unknown"))[:16]
        cwd = str(data.get("cwd", ""))[:300]
        now = datetime.datetime.now()
        content = (
            f"Session finalized {now.strftime('%Y-%m-%d %H:%M')} "
            f"in project: {cwd} (session: {session_id})"
        )

        store_memory_event(
            content=content,
            metadata={
                "type": "session_end_final",
                "session_id": session_id,
                "cwd": cwd,
                "date": now.isoformat(),
            },
            event_key=f"session_end_final|{session_id}|{cwd}",
        )
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
