#!/usr/bin/env python3
"""Instala hooks de Git para sincronizar comandos cross-IDE automaticamente.

Este instalador agrega un bloque gestionado por Antigravity en:
- .git/hooks/post-merge
- .git/hooks/post-checkout

El bloque ejecuta `.agent/scripts/sync_commands.py` despues de pulls/merges/checkouts,
para mantener exportados los comandos como skills en IDEs sin slash parser.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

START_MARKER = "# >>> antigravity-sync-commands >>>"
END_MARKER = "# <<< antigravity-sync-commands <<<"

HOOK_SNIPPET = """{start}
REPO_ROOT=\"$(git rev-parse --show-toplevel 2>/dev/null)\"
if [ -n \"$REPO_ROOT\" ] && [ -f \"$REPO_ROOT/.agent/scripts/sync_commands.py\" ]; then
  if command -v py >/dev/null 2>&1; then
    py \"$REPO_ROOT/.agent/scripts/sync_commands.py\" --all || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 \"$REPO_ROOT/.agent/scripts/sync_commands.py\" --all || true
  elif command -v python >/dev/null 2>&1; then
    python \"$REPO_ROOT/.agent/scripts/sync_commands.py\" --all || true
  fi
fi
{end}
"""


def _upsert_managed_block(content: str, block: str) -> str:
    """Inserta o reemplaza el bloque gestionado por Antigravity en un hook.

    Args:
        content: Contenido actual del archivo hook.
        block: Bloque gestionado a insertar o actualizar.

    Returns:
        Contenido final con el bloque gestionado.
    """
    if START_MARKER in content and END_MARKER in content:
        start_idx = content.index(START_MARKER)
        end_idx = content.index(END_MARKER) + len(END_MARKER)
        prefix = content[:start_idx].rstrip()
        suffix = content[end_idx:].lstrip("\n")
        merged = "\n\n".join(part for part in [prefix, block.strip(), suffix] if part)
        return f"{merged}\n"

    cleaned = content.rstrip()
    if cleaned:
        return f"{cleaned}\n\n{block.strip()}\n"
    return f"{block.strip()}\n"


def _ensure_shebang(content: str) -> str:
    """Garantiza shebang POSIX para hooks de Git."""
    if content.startswith("#!/bin/sh"):
        return content
    return f"#!/bin/sh\n\n{content.lstrip()}"


def _write_hook(hook_path: Path, dry_run: bool = False) -> None:
    """Escribe o actualiza un hook con el bloque de sincronizacion.

    Args:
        hook_path: Ruta del hook de Git.
        dry_run: Si True, no persiste cambios.
    """
    block = HOOK_SNIPPET.format(start=START_MARKER, end=END_MARKER)
    current = ""
    if hook_path.exists():
        current = hook_path.read_text(encoding="utf-8")

    updated = _ensure_shebang(_upsert_managed_block(current, block))

    if dry_run:
        logger.info("[DRY RUN] Actualizaria hook: %s", hook_path)
        return

    hook_path.write_text(updated, encoding="utf-8", newline="\n")

    # En sistemas POSIX, asegurar permiso de ejecucion.
    if os.name != "nt":
        hook_path.chmod(0o755)

    logger.info("✓ Hook actualizado: %s", hook_path)


def install_hooks(repo_root: Path, dry_run: bool = False) -> int:
    """Instala hooks post-merge y post-checkout en el repositorio actual.

    Args:
        repo_root: Ruta del repositorio.
        dry_run: Modo simulacion.

    Returns:
        Codigo de salida (0 = OK, 1 = error).
    """
    hooks_dir = repo_root / ".git" / "hooks"
    if not hooks_dir.exists():
        logger.error("No se encontro .git/hooks en %s", hooks_dir)
        return 1

    for hook_name in ["post-merge", "post-checkout"]:
        _write_hook(hooks_dir / hook_name, dry_run=dry_run)

    return 0


def main() -> int:
    """Entry point del instalador."""
    parser = argparse.ArgumentParser(
        description="Instalar hooks Git para sync_commands.py tras pull/merge.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Ruta del repositorio (default: raiz del repo actual)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar cambios sin escribir archivos",
    )
    args = parser.parse_args()

    return install_hooks(args.repo_root.resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
