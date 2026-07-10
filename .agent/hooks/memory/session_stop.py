#!/usr/bin/env python3
"""Antigravity Memory Hook — Stop.

Stores a session-end marker in mem0 so future sessions can recall what was worked on.
Also writes a session node to `.agent/brain/` as a git-versioned fallback so the
session is captured even if the gateway is offline.

Called by Claude Code when the session ends.
Input (stdin): {"session_id": "...", "cwd": "...", "stop_hook_active": bool}
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

from common import (
    flush_pending_events,
    get_hook_config,
    store_memory_event,
)


def _ingest_brain_fallback(session_id: str, cwd: str, now: datetime.datetime) -> None:
    """Write a minimal `session` node to `.agent/brain/` as a git-versioned fallback.

    Runs only if the cwd looks like an Antigravity repo (has `.agent/brain/`) so
    the hook does not pollute unrelated projects. Fails silently on any error
    to keep the Stop hook non-disruptive.
    """
    if not cwd:
        return
    try:
        cwd_path = Path(cwd)
    except Exception:  # noqa: BLE001
        return

    brain_dir = cwd_path / ".agent" / "brain"
    if not brain_dir.exists():
        return

    repo_root = cwd_path
    agent_root = repo_root / ".agent"
    if not agent_root.exists():
        return

    try:
        # Prefer the local .agent/ runtime so we use the same Brain version.
        if str(agent_root) not in sys.path:
            sys.path.insert(0, str(agent_root))
        from core.brain import Brain  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return

    app_id = os.getenv("AG_BRAIN_APP_ID", "nexus-mother")
    try:
        brain = Brain(brain_dir, app_id=app_id)
    except Exception:  # noqa: BLE001
        return

    title = f"Sesion {now.strftime('%Y-%m-%d %H:%M')}"
    context = (
        f"Session fin automatica registrada por session_stop hook. "
        f"cwd={cwd}, session_id={session_id[:16]}."
    )

    try:
        brain.ingest(
            title=title,
            context=context,
            area="session-hooks",
            tags=["hook", "session-end", "auto"],
            node_type="session",
            importance="low",
        )
    except Exception:  # noqa: BLE001
        # Non-fatal: mem0 path still ran, git still captures manual ingests.
        return


def main() -> None:
    try:
        hook_config = get_hook_config()
        if not bool(hook_config.get("capture_stop_marker", True)):
            return

        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        session_id = data.get("session_id", "unknown")
        cwd = data.get("cwd", "")

        now = datetime.datetime.now()
        content = (
            f"Session ended {now.strftime('%Y-%m-%d %H:%M')} "
            f"in project: {cwd} (session: {session_id[:12]})"
        )

        store_memory_event(
            content=content,
            metadata={
                "type": "session_end",
                "session_id": session_id[:16],
                "cwd": cwd[:300],
                "date": now.isoformat(),
            },
            event_key=f"session_end|{session_id[:16]}|{cwd}",
        )

        # Git-versioned fallback: siempre guardar en brain al cerrar sesion.
        # El brain es la memoria primaria del usuario y DEBE persistirse.
        # Even if gateway is healthy, brain must be updated (git sync between PCs).
        if bool(hook_config.get("capture_brain_fallback", True)):
            _ingest_brain_fallback(session_id, cwd, now)

        # Last chance to flush the queue before process exits.
        # Drain ALL pending events (not just QUEUE_FLUSH_LIMIT=25) to prevent backlog.
        flushed_sent = 0
        flushed_pending = 0
        while True:
            s, p = flush_pending_events(max_items=100)
            flushed_sent += s
            flushed_pending += p
            if p == 0 or s == 0:
                break
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
