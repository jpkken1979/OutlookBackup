#!/usr/bin/env python3
"""Log Rotation - Rotación automática de logs del ecosistema.

Rota archivos .log en .agent/logs/ cuando superan el tamaño máximo.
Mantiene un máximo de copias rotadas por archivo.

Uso:
    python .agent/scripts/rotate_logs.py
    python .agent/scripts/rotate_logs.py --max-size 5  # MB
    python .agent/scripts/rotate_logs.py --keep 3       # copias
    python .agent/scripts/rotate_logs.py --dry-run
"""

from __future__ import annotations

import argparse
import gzip
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("antigravity.log_rotation")

_DEFAULT_MAX_SIZE_MB = 10
_DEFAULT_KEEP = 5


def rotate_logs(
    log_dir: Path,
    max_size_mb: int = _DEFAULT_MAX_SIZE_MB,
    keep: int = _DEFAULT_KEEP,
    dry_run: bool = False,
) -> list[str]:
    """Rota archivos de log que superan el tamaño máximo.

    Los archivos se comprimen con gzip y se renombran con sufijo numérico.
    Ejemplo: agent.log → agent.log.1.gz → agent.log.2.gz → (se elimina)

    Args:
        log_dir: Directorio con los logs.
        max_size_mb: Tamaño máximo en MB antes de rotar.
        keep: Número de copias rotadas a mantener.
        dry_run: Si True, solo reporta sin modificar.

    Returns:
        Lista de acciones realizadas.
    """
    actions: list[str] = []
    max_bytes = max_size_mb * 1024 * 1024

    if not log_dir.is_dir():
        logger.warning("Log directory does not exist: %s", log_dir)
        return actions

    for log_file in sorted(log_dir.glob("*.log")):
        if not log_file.is_file():
            continue

        size = log_file.stat().st_size
        if size < max_bytes:
            continue

        size_mb = size / (1024 * 1024)
        action = f"Rotate {log_file.name} ({size_mb:.1f} MB)"

        if dry_run:
            actions.append(f"[DRY RUN] {action}")
            continue

        # Eliminar la copia más antigua si superamos el límite
        for i in range(keep, 0, -1):
            old = log_file.with_suffix(f".log.{i}.gz")
            new = log_file.with_suffix(f".log.{i + 1}.gz")
            if i == keep and old.exists():
                old.unlink()
                actions.append(f"Deleted {old.name}")
            elif old.exists():
                old.rename(new)

        # Comprimir el log actual como .1.gz
        rotated = log_file.with_suffix(".log.1.gz")
        with open(log_file, "rb") as f_in:
            with gzip.open(rotated, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Truncar el archivo original (no eliminar — procesos pueden tener el fd abierto)
        with open(log_file, "w") as f:
            f.truncate(0)

        actions.append(action)
        logger.info(action)

    return actions


def main() -> None:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(description="Rotar logs del ecosistema")
    parser.add_argument("--dir", default=".agent/logs", help="Directorio de logs")
    parser.add_argument(
        "--max-size", type=int, default=_DEFAULT_MAX_SIZE_MB, help="Tamaño máximo en MB"
    )
    parser.add_argument("--keep", type=int, default=_DEFAULT_KEEP, help="Copias rotadas a mantener")
    parser.add_argument("--dry-run", action="store_true", help="Solo reportar")
    args = parser.parse_args()

    log_dir = Path(args.dir).resolve()
    actions = rotate_logs(log_dir, args.max_size, args.keep, args.dry_run)

    if actions:
        for a in actions:
            print(f"  {a}")
        print(f"\n{len(actions)} actions.")
    else:
        print("No logs need rotation.")


if __name__ == "__main__":
    main()
