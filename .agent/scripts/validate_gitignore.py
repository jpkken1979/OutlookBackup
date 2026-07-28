#!/usr/bin/env python3
"""Auditar y reparar .gitignore en un proyecto que recibio inyeccion del
ecosistema Antigravity, garantizando que paths criticos no esten bloqueados.

Uso:
    # Solo reportar (no toca nada):
    python .agent/scripts/validate_gitignore.py

    # Aplicar fix (idempotente):
    python .agent/scripts/validate_gitignore.py --apply

    # Auditar otro repo:
    python .agent/scripts/validate_gitignore.py --target /ruta/a/otro/repo --apply

Salida JSON con keys:
    target          : ruta del repo auditado
    gitignore_path  : ruta del .gitignore
    health          : { git_available, blocked_paths, checked_paths, healthy }
    patch           : { action, paths_protected }  (None si --check)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
AGENT_DIR = THIS_DIR.parent
sys.path.insert(0, str(AGENT_DIR))

try:
    from core.gitignore_guard import (
        check_gitignore_health,
        patch_gitignore,
    )
except ImportError as exc:
    print(
        json.dumps(
            {"error": f"no se pudo importar gitignore_guard: {exc}"},
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    sys.exit(2)

logger = logging.getLogger(__name__)


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.cwd(),
        help="Directorio del repo a auditar (default: cwd)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar el fix al .gitignore (sin esto, dry-run + reporte)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logging DEBUG")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    target = args.target.resolve()
    if not target.is_dir():
        print(json.dumps({"error": f"target no es directorio: {target}"}, ensure_ascii=False))
        return 1

    health = check_gitignore_health(target)
    health_dict = {
        "git_available": health.git_available,
        "blocked_paths": health.blocked_paths,
        "checked_paths": health.checked_paths,
        "healthy": health.healthy,
    }

    payload: dict[str, object] = {
        "target": str(target),
        "gitignore_path": str(target / ".gitignore"),
        "health_before": health_dict,
        "patch": None,
    }

    patch = patch_gitignore(target, dry_run=not args.apply)
    payload["patch"] = {
        "action": patch.action,
        "paths_protected": patch.paths_protected,
        "reason": patch.reason,
    }

    if args.apply and patch.action != "unchanged":
        # Re-check tras aplicar
        health_after = check_gitignore_health(target)
        payload["health_after"] = {
            "git_available": health_after.git_available,
            "blocked_paths": health_after.blocked_paths,
            "checked_paths": health_after.checked_paths,
            "healthy": health_after.healthy,
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if (patch.action != "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
