#!/usr/bin/env python3
"""Rebuild Brain Network index.

Reconstruye `.agent/brain/index.md` desde los nodos existentes.

Uso:
    python .agent/scripts/rebuild_brain_index.py
    python .agent/scripts/rebuild_brain_index.py --app-id nexus-mother
    python .agent/scripts/rebuild_brain_index.py --brain-dir .agent/brain

Se ejecuta automaticamente en el hook `Stop` para mantener el indice
sincronizado con los nodos. Es seguro correrlo en cualquier momento: solo
lee los nodos y reescribe `index.md`.

Salida: `{"indexed": N, "brain_dir": "..."}` en stdout como JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _resolve_repo_root() -> Path:
    """Find the repo root by walking up from this script's location."""
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".agent").is_dir() and (candidate / ".git").exists():
            return candidate
    return Path.cwd()


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
    args = parser.parse_args()

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
        from core.brain import Brain
    except ImportError as exc:
        print(json.dumps({"error": f"Cannot import Brain: {exc}"}), file=sys.stderr)
        return 1

    brain = Brain(brain_dir, app_id=args.app_id)
    count = brain.rebuild_index()

    if not args.quiet:
        print(json.dumps({"indexed": count, "brain_dir": str(brain_dir)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
