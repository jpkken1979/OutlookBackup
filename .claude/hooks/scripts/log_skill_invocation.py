"""Hook: registra invocaciones de Skill y Agent (Task) tools.

Configurar en .claude/settings.json bajo PreToolUse o PostToolUse.

Output: ~/.antigravity/telemetry/invocations.jsonl (append-only JSON Lines).

Cada linea es un evento con: timestamp, tool, skill_name, agent_type, app, success.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Si stdin no tiene JSON valido, salir silenciosamente (no romper la session)
        return 0

    tool = event.get("tool_name") or event.get("tool") or ""
    if tool not in ("Skill", "Agent", "Task"):
        return 0

    tool_input = event.get("tool_input", {}) or {}
    skill_name = tool_input.get("skill", "")
    agent_type = tool_input.get("subagent_type", "")
    description = tool_input.get("description", "")[:80]

    # Determinar la app a partir del cwd
    cwd_str = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("PWD") or os.getcwd()
    app = Path(cwd_str).name

    log_dir = Path.home() / ".antigravity" / "telemetry"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "invocations.jsonl"

    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "tool": tool,
        "skill": skill_name,
        "agent": agent_type,
        "app": app,
        "description": description,
    }

    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Si no podemos escribir, fail silently — no bloquear la session
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
