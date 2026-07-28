"""Helpers shared by the frozen gateway and its portable script runner."""

from __future__ import annotations

import json
import os
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path

PORTABLE_RUNTIME_ENV = "ANTIGRAVITY_PORTABLE_RUNTIME"
PROJECT_ROOT_ENV = "ANTIGRAVITY_HOME"
PORTABLE_SCRIPT_FLAG = "--portable-run-script"


def is_portable_runtime() -> bool:
    """Return whether the current process is a frozen portable runtime."""

    return os.environ.get(PORTABLE_RUNTIME_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def project_root() -> Path:
    """Resolve the project that owns the portable runtime."""

    configured = os.environ.get(PROJECT_ROOT_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _safe_agent_name(agent_name: str) -> bool:
    return bool(agent_name) and not any(
        marker in agent_name for marker in ("/", "\\", "..")
    )


def resolve_agent_script(agent_name: str, root: Path | None = None) -> Path | None:
    """Resolve the preferred executable script for one bundled agent."""

    if not _safe_agent_name(agent_name):
        return None
    base = (root or project_root()).resolve()
    agent_dir = base / ".agent" / "agents" / agent_name
    if not agent_dir.is_dir():
        return None

    candidates: list[Path] = []
    metadata_path = agent_dir / "agent.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        configured = metadata.get("scripts", {}).get("main")
        if isinstance(configured, str) and configured.strip():
            configured_path = Path(configured)
            candidates.extend(
                [
                    agent_dir / configured_path,
                    agent_dir / "scripts" / configured_path,
                ]
            )
    except (OSError, TypeError, ValueError):
        pass

    normalized_name = agent_name.replace("-", "_")
    candidates.extend(
        [
            agent_dir / "main.py",
            agent_dir / "scripts" / "main.py",
            agent_dir / "scripts" / f"{normalized_name}.py",
        ]
    )
    scripts_dir = agent_dir / "scripts"
    if scripts_dir.is_dir():
        candidates.extend(sorted(scripts_dir.glob("*.py")))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved.is_relative_to(agent_dir.resolve()):
            return resolved
    return None


def _allowed_script_roots(root: Path) -> tuple[Path, ...]:
    return tuple(
        path.resolve()
        for path in (
            root / ".agent" / "agents",
            root / ".agent" / "skills",
            root / ".agent" / "skills-custom",
            root / ".agents" / "skills",
        )
    )


def run_portable_script_cli(argv: Sequence[str] | None = None) -> int | None:
    """Run an explicitly requested project script inside the frozen interpreter.

    Returns ``None`` when the process was not launched in script-runner mode.
    """

    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] != PORTABLE_SCRIPT_FLAG:
        return None
    if len(arguments) < 2:
        return 2

    root = project_root()
    script = Path(arguments[1]).expanduser().resolve()
    if not script.is_file() or not any(
        script.is_relative_to(allowed_root)
        for allowed_root in _allowed_script_roots(root)
    ):
        return 2

    previous_argv = sys.argv[:]
    previous_path = sys.path[:]
    sys.argv = [str(script), *arguments[2:]]
    sys.path.insert(0, str(script.parent))
    sys.path.insert(0, str(root / ".agent"))
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        return 1
    except Exception as exc:
        print(
            f"Portable script failed: {type(exc).__name__}: {str(exc)[:500]}",
            file=sys.stderr,
        )
        return 1
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_path
    return 0
