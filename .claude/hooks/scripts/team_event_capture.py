#!/usr/bin/env python3
"""Hook de Agent Teams: captura TaskCreated/TaskCompleted/TeammateIdle al daily log.

Captura pasiva y no bloqueante (exit 0 siempre): registra la actividad del team
en `.claude/memory/daily/YYYY-MM-DD.md` para que quede rastro versionable de que
tareas creo/completo cada team. No es un quality gate — no rechaza eventos.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

_INTERESTING_KEYS: tuple[str, ...] = (
    "task_subject",
    "task_description",
    "teammate_name",
    "agent_name",
    "agent_type",
    "task_id",
    "team_name",
)


def main() -> int:
    """Lee el payload del hook por stdin y appendea una linea al daily.

    Returns:
        Exit code (siempre 0: captura pasiva, nunca bloquea al team).
    """
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    event = str(payload.get("hook_event_name") or "team-event")
    bits = [
        f"{key}={payload[key]}"
        for key in _INTERESTING_KEYS
        if payload.get(key)
    ]

    now = datetime.datetime.now()
    daily = Path(__file__).resolve().parents[2] / "memory" / "daily" / f"{now:%Y-%m-%d}.md"
    line = f"- {now:%H:%M} [team:{event}] {' · '.join(bits) or 'sin detalle'}\n"
    try:
        daily.parent.mkdir(parents=True, exist_ok=True)
        with daily.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
