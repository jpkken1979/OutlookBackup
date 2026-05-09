#!/usr/bin/env python3
"""
Skill-local wrapper for the Frontend Design Galaxy catalog utility.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

LOGGER = logging.getLogger("antigravity.skill.design_galaxy")
SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "create_design_galaxy.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("create_design_galaxy_main", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    """Delegate execution to the shared catalog utility."""
    module = _load_module()
    return module.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
