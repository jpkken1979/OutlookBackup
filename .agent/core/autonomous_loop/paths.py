# mypy: ignore-errors
"""Helpers de WRITABLE_ROOTS para el motor autonomo.

Duplicados aca a proposito para que autonomous_loop quede self-contained (sin
dependencia dura de agent_tool_manager). Extraido del monolito
``autonomous_loop.py`` (refactor 2026-05-31). Sin cambios de comportamiento;
solo se ajusto la profundidad de ``__file__`` (el modulo bajo un nivel).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("antigravity.autonomous")


def _get_writable_roots() -> list[Path]:
    """Parse WRITABLE_ROOTS env var into a list of resolved Path objects."""
    env_val = os.environ.get("WRITABLE_ROOTS", "").strip()
    if not env_val:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        return [repo_root]
    roots = []
    for part in env_val.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            roots.append(Path(part).resolve())
        except (ValueError, OSError):
            logger.warning("WRITABLE_ROOTS: invalid path ignored: %s", part)
    return roots


def _is_path_in_writable_roots(path: Path, writable_roots: list[Path]) -> bool:
    """Check if resolved path is contained in any of the writable_roots."""
    try:
        resolved = path.resolve()
    except (ValueError, OSError):
        return False
    for root in writable_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False
