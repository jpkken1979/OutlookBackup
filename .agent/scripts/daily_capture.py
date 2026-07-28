#!/usr/bin/env python3
"""Daily Capture Inbox — Logseq-style daily note creation.

Creates `.claude/memory/daily/YYYY-MM-DD.md` if it doesn't exist for today.
Idempotent: skips if file already exists.
Auto-detects active project from ESTADO_PROYECTO.md.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Add .agent to path for imports
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import logging

from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DailyCaptureConfig:
    """Configuration for daily capture generation."""

    daily_dir: Path
    estado_path: Path
    date_today: date


def get_active_project(estado_path: Path) -> str:
    """Detect active project from ESTADO_PROYECTO.md.

    Args:
        estado_path: Path to ESTADO_PROYECTO.md.

    Returns:
        Project name or 'general' if detection fails.
    """
    if not estado_path.exists():
        return "general"

    try:
        content = estado_path.read_text(encoding="utf-8")
        # Look for most recent session header
        for line in content.splitlines()[:50]:
            line = line.strip()
            if line.startswith("## Sesion ") or line.startswith("## Sesión "):
                # Extract project context from session name
                rest = line[2:].strip()  # Remove ##
                if " — " in rest:
                    project = rest.split(" — ", 1)[1].split(" ")[0].lower()
                    return project.replace("-", "_").replace(".", "")
                elif " — " not in rest:
                    return "general"
        return "general"
    except Exception as e:
        logger.warning("Failed to detect project from ESTADO_PROYECTO.md: %s", e)
        return "general"


DAILY_TEMPLATE = """---
name: daily-{date}
description: Capture inbox para el día {date}
type: daily-capture
date: {date}
tags: [capture, daily, {project}]
---

# {date} — Daily Capture

## Context
> ¿En qué proyecto estás trabajando hoy?

## Objectives
> - [ ] Objetivo 1
> - [ ] Objetivo 2

## Notes
> Capturas del día...

## Reflections
> Al cerrar la sesión: ¿qué aprendiste? ¿qué funcionó?
"""


def create_daily_capture(config: DailyCaptureConfig) -> Path | None:
    """Create daily capture file for today.

    Args:
        config: Daily capture configuration.

    Returns:
        Path to created file, or None if already exists.
    """
    daily_dir = config.daily_dir
    daily_dir.mkdir(parents=True, exist_ok=True)

    date_str = config.date_today.isoformat()
    daily_file = daily_dir / f"{date_str}.md"

    if daily_file.exists():
        logger.info("Daily capture already exists: %s", daily_file)
        return None

    project = get_active_project(config.estado_path)

    content = DAILY_TEMPLATE.format(date=date_str, project=project)
    daily_file.write_text(content, encoding="utf-8")
    logger.info("Created daily capture: %s (project: %s)", daily_file, project)
    return daily_file


def _sanitize_for_cp932(s: str) -> str:
    """Replace Unicode chars that cp932 cannot encode."""
    replacements = {
        "—": "--",  # em-dash
        "–": "-",  # en-dash
        "‘": "'",  # left single quote
        "’": "'",  # right single quote
        "“": '"',  # left double quote
        "”": '"',  # right double quote
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s


def get_last_session_from_brain(brain_dir: Path) -> str | None:
    """Get last session node from Brain Network.

    Args:
        brain_dir: Path to .agent/brain/.

    Returns:
        Title of last session node or None.
    """
    if not brain_dir.exists():
        return None

    sessions_dir = brain_dir / "sessions"
    if not sessions_dir.exists():
        return None

    try:
        # Get most recent session by modification time
        sessions = sorted(
            sessions_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if sessions:
            content = sessions[0].read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("title:"):
                    return line.split("title:", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning("Failed to read last session from brain: %s", e)

    return None


def main() -> int:
    """Main entry point for daily capture script."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )

    repo_root = _ROOT
    daily_dir = repo_root / ".claude" / "memory" / "daily"
    estado_path = repo_root / "ESTADO_PROYECTO.md"
    brain_dir = repo_root / ".agent" / "brain"

    today = date.today()

    config = DailyCaptureConfig(
        daily_dir=daily_dir,
        estado_path=estado_path,
        date_today=today,
    )

    created = create_daily_capture(config)

    # Brain status summary
    last_session = get_last_session_from_brain(brain_dir)

    print()
    print("=" * 60)
    print(f"  DAILY CAPTURE -- {today.isoformat()}")
    print("=" * 60)

    if created:
        print("  [NEW] Created: " + str(created.relative_to(repo_root)))
    else:
        print("  [SKIP] Already exists for today")

    if last_session:
        print("  [BRAIN] Last session: " + _sanitize_for_cp932(last_session))
    else:
        print("  [BRAIN] No recent sessions found")

    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
