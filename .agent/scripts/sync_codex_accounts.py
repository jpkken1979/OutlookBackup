#!/usr/bin/env python3
"""Sincroniza cuentas Codex entre el repositorio y el home del usuario.

Implementa el TODO documentado en `.gitignore` (sección "Cuentas Codex"):
sync bidireccional entre `.agent/accounts/codex/` (repo, portabilidad entre
PCs) y `~/.codex/accounts/` (ubicación original que lee el switcher de Nexus).

Reglas de seguridad (ver `.claude/rules/security.md` y `config-guard.md`):
- NUNCA se borra ningún archivo — el sync solo copia.
- Antes de sobreescribir un archivo existente con contenido distinto se crea
  un backup en `<dir>/.backup/<timestamp-UTC>/`.
- Los snapshots de auth (`<name>.json`, excepto `index.json`) contienen JWT
  activos: se sincronizan localmente pero están gitignorados — nunca viajan
  por git.

Uso:
    python .agent/scripts/sync_codex_accounts.py                # sync bidireccional
    python .agent/scripts/sync_codex_accounts.py --direction import   # repo -> home
    python .agent/scripts/sync_codex_accounts.py --direction export   # home -> repo
    python .agent/scripts/sync_codex_accounts.py --dry-run     # solo mostrar acciones
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(format="[%(asctime)s] [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BACKUP_DIRNAME = ".backup"
SYNCABLE_SUFFIXES = (".json", ".toml")


@dataclass
class SyncReport:
    """Resultado de una pasada de sincronización.

    Args:
        copied: Archivos copiados (rutas destino).
        backed_up: Archivos respaldados antes de sobreescribir.
        skipped: Archivos ya idénticos en ambos lados.
    """

    copied: list[Path] = field(default_factory=list)
    backed_up: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


def _file_digest(path: Path) -> str:
    """Calcula el hash SHA-256 del contenido de un archivo.

    Args:
        path: Archivo a hashear.

    Returns:
        Digest hexadecimal del contenido.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _backup_file(path: Path, timestamp: str, dry_run: bool) -> Path:
    """Respalda un archivo dentro de `<dir>/.backup/<timestamp>/` antes de pisarlo.

    Args:
        path: Archivo existente que va a ser sobreescrito.
        timestamp: Marca temporal UTC compartida por toda la corrida.
        dry_run: Si es True, solo loguea sin copiar.

    Returns:
        Ruta del backup creado (o que se crearía en dry-run).
    """
    backup_dir = path.parent / BACKUP_DIRNAME / timestamp
    backup_path = backup_dir / path.name
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
    logger.info("backup: %s -> %s", path, backup_path)
    return backup_path


def _list_account_files(directory: Path) -> list[Path]:
    """Lista los archivos de cuenta sincronizables en un directorio.

    Ignora el directorio de backups y cualquier extensión no esperada.

    Args:
        directory: Directorio de cuentas (repo o home).

    Returns:
        Archivos `.json` / `.toml` de primer nivel, orden estable.
    """
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix in SYNCABLE_SUFFIXES)


def _copy_newer(
    src_dir: Path,
    dst_dir: Path,
    timestamp: str,
    report: SyncReport,
    dry_run: bool,
    newest_wins: bool,
) -> None:
    """Copia archivos de `src_dir` a `dst_dir` con backup previo.

    Args:
        src_dir: Directorio origen.
        dst_dir: Directorio destino.
        timestamp: Marca temporal UTC compartida para los backups.
        report: Acumulador de resultados de la corrida.
        dry_run: Si es True, solo loguea sin tocar el filesystem.
        newest_wins: Si es True (modo sync), solo copia cuando el origen es
            más nuevo que el destino; si es False (import/export), el origen
            siempre gana.
    """
    for src in _list_account_files(src_dir):
        dst = dst_dir / src.name
        if dst.exists():
            if _file_digest(src) == _file_digest(dst):
                report.skipped.append(dst)
                continue
            if newest_wins and dst.stat().st_mtime >= src.stat().st_mtime:
                continue
            report.backed_up.append(_backup_file(dst, timestamp, dry_run))
        if not dry_run:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        logger.info("copy: %s -> %s", src, dst)
        report.copied.append(dst)


def sync_accounts(
    repo_dir: Path,
    home_dir: Path,
    direction: str,
    dry_run: bool = False,
) -> SyncReport:
    """Sincroniza los archivos de cuentas Codex entre repo y home.

    Args:
        repo_dir: `.agent/accounts/codex/` dentro del repositorio.
        home_dir: `~/.codex/accounts/` (ubicación que lee Nexus).
        direction: `"import"` (repo -> home), `"export"` (home -> repo) o
            `"sync"` (bidireccional, gana el más nuevo por mtime).
        dry_run: Si es True, muestra las acciones sin ejecutarlas.

    Returns:
        Reporte con archivos copiados, respaldados y omitidos.

    Raises:
        FileNotFoundError: Si el origen requerido no existe.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = SyncReport()

    if direction == "import":
        if not repo_dir.is_dir():
            raise FileNotFoundError(f"No existe el directorio de cuentas del repo: {repo_dir}")
        _copy_newer(repo_dir, home_dir, timestamp, report, dry_run, newest_wins=False)
    elif direction == "export":
        if not home_dir.is_dir():
            raise FileNotFoundError(f"No existe el directorio de cuentas del home: {home_dir}")
        _copy_newer(home_dir, repo_dir, timestamp, report, dry_run, newest_wins=False)
    else:  # sync bidireccional
        if not repo_dir.is_dir() and not home_dir.is_dir():
            raise FileNotFoundError(
                f"No existe ninguno de los dos directorios: {repo_dir} ni {home_dir}"
            )
        _copy_newer(repo_dir, home_dir, timestamp, report, dry_run, newest_wins=True)
        _copy_newer(home_dir, repo_dir, timestamp, report, dry_run, newest_wins=True)

    return report


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI.

    Args:
        argv: Argumentos de línea de comandos (para tests); None usa sys.argv.

    Returns:
        Código de salida del proceso.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--direction",
        choices=("sync", "import", "export"),
        default="sync",
        help="sync = bidireccional (default), import = repo->home, export = home->repo",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar acciones sin modificar archivos",
    )
    args = parser.parse_args(argv)

    repo_dir = Path(__file__).resolve().parent.parent / "accounts" / "codex"
    home_dir = Path.home() / ".codex" / "accounts"

    try:
        report = sync_accounts(repo_dir, home_dir, args.direction, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    logger.info(
        "%sListo: %d copiados, %d respaldados, %d sin cambios",
        prefix,
        len(report.copied),
        len(report.backed_up),
        len(report.skipped),
    )
    if report.copied:
        logger.info(
            "Recordatorio: los snapshots de auth (*.json salvo index.json) "
            "estan gitignorados y NO se versionan."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
