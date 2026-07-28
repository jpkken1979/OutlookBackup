#!/usr/bin/env python3
"""Rebuild Brain Network index.

Reconstruye `.agent/brain/index.md` desde los nodos existentes.

Uso:
    python .agent/scripts/rebuild_brain_index.py
    python .agent/scripts/rebuild_brain_index.py --check --json
    python .agent/scripts/rebuild_brain_index.py --app-id nexus-mother
    python .agent/scripts/rebuild_brain_index.py --brain-dir .agent/brain

Se ejecuta automaticamente en el hook `Stop` (via .claude/settings.json) y
al cerrar sesion con la skill `session-closer` para mantener el indice
sincronizado con los nodos. Es seguro correrlo en cualquier momento: solo
lee los nodos y reescribe `index.md`, salvo en `--check`.

Salida: `{"indexed": N, "brain_dir": "..."}` en stdout como JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _resolve_repo_root() -> Path:
    """Find the repo root by walking up from this script's location."""
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".agent").is_dir() and (candidate / ".git").exists():
            return candidate
    return Path.cwd()


def _node_files(brain_dir: Path) -> list[Path]:
    """Return Brain node files without constructing Brain (no writes)."""
    files: list[Path] = []
    for child in ("sessions", "concepts", "connections"):
        directory = brain_dir / child
        if directory.exists():
            files.extend(directory.glob("*.md"))
    return files


def _count_active_nodes(brain_node_cls: Any, brain_dir: Path) -> tuple[int, int]:
    """Count active nodes without touching Brain side effects."""
    active_count = 0
    invalid_count = 0
    for md_file in _node_files(brain_dir):
        try:
            node = brain_node_cls.from_frontmatter(
                md_file.read_text(encoding="utf-8", errors="ignore"),
                md_file,
            )
        except (OSError, ValueError):
            invalid_count += 1
            continue
        if node.status == "active":
            active_count += 1
    return active_count, invalid_count


def _check_index(brain_node_cls: Any, brain_dir: Path) -> tuple[dict[str, object], int]:
    """Check index health without rewriting index.md."""
    active_count, invalid_count = _count_active_nodes(brain_node_cls, brain_dir)
    index_path = brain_dir / "index.md"
    reasons: list[str] = []
    declared_count: int | None = None
    line_count = 0

    if not index_path.exists():
        reasons.append("index_missing")
    else:
        content = index_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())
        match = re.search(r"(\d+)\s+nodos activos", content)
        if match:
            declared_count = int(match.group(1))
        else:
            reasons.append("active_count_marker_missing")

    if invalid_count:
        reasons.append("invalid_node_files")
    if line_count < 50 and active_count > 0:
        reasons.append("index_too_small")
    if declared_count is not None and declared_count != active_count:
        reasons.append("active_count_mismatch")

    needs_rebuild = bool(reasons)
    payload: dict[str, object] = {
        "ok": not needs_rebuild,
        "needs_rebuild": needs_rebuild,
        "indexed": active_count,
        "declared_indexed": declared_count,
        "index_lines": line_count,
        "invalid_nodes": invalid_count,
        "brain_dir": str(brain_dir),
        "reasons": reasons,
    }
    return payload, 1 if needs_rebuild else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild Brain Network index")
    parser.add_argument(
        "--brain-dir",
        default=None,
        help="Path to brain dir (default: <repo>/.agent/brain)",
    )
    parser.add_argument(
        "--app-id",
        default="nexus-mother",
        help="App ID for the brain instance",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress JSON output (still returns exit code)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check index health without writing index.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output (kept for explicit CLI compatibility)",
    )
    parser.add_argument(
        "--skip-if-ephemeral",
        action="store_true",
        help=(
            "Salir sin reconstruir en entornos efimeros (IS_SANDBOX/CCR): el "
            "contenedor puede tener estado parcial del brain y el rebuild "
            "generaria un index.md incompleto que ensucia git."
        ),
    )
    args = parser.parse_args()

    if args.skip_if_ephemeral and (
        os.environ.get("IS_SANDBOX") == "yes" or os.environ.get("CCR_AGENT_PROXY_ENABLED") == "1"
    ):
        if not args.quiet:
            print(json.dumps({"skipped": "entorno efimero — rebuild omitido"}))
        return 0

    repo_root = _resolve_repo_root()
    sys.path.insert(0, str(repo_root / ".agent"))

    brain_dir = Path(args.brain_dir) if args.brain_dir else repo_root / ".agent" / "brain"
    if not brain_dir.exists():
        print(
            json.dumps({"error": f"Brain dir not found: {brain_dir}"}),
            file=sys.stderr,
        )
        return 1

    try:
        from core.brain import Brain, BrainNode
    except ImportError as exc:
        print(json.dumps({"error": f"Cannot import Brain: {exc}"}), file=sys.stderr)
        return 1

    if args.check:
        payload, exit_code = _check_index(BrainNode, brain_dir)
        if not args.quiet:
            print(json.dumps(payload))
        return exit_code

    brain = Brain(brain_dir, app_id=args.app_id)
    count = brain.rebuild_index()

    if not args.quiet:
        print(json.dumps({"indexed": count, "brain_dir": str(brain_dir)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
