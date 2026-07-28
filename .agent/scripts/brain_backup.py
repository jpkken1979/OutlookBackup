#!/usr/bin/env python3
"""
Brain Backup — Backup automatico del Brain Network con rotacion.

Crea snapshots diarios del .agent/brain/ en .agent/brain-backups/.
Mantiene: ultimos 7 diarios + 4 semanales + 12 mensuales + 3 anuales.

Uso:
  python brain_backup.py              # crear backup ahora
  python brain_backup.py --list       # listar backups
  python brain_backup.py --restore <id>   # restaurar backup
  python brain_backup.py --clean      # rotacion automatica
  python brain_backup.py --cron       # modo programado (crear + rotar)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import tarfile
from datetime import datetime, timedelta, UTC
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

AGENT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_DIR = AGENT_ROOT / "brain"
BACKUP_DIR = AGENT_ROOT / "brain-backups"
MANIFEST = BACKUP_DIR / "manifest.json"


def load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"backups": []}


def save_manifest(manifest: dict) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def count_nodes(brain_dir: Path) -> int:
    """Cuenta nodos markdown en el brain."""
    if not brain_dir.exists():
        return 0
    return sum(1 for _ in brain_dir.rglob("*.md"))


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extrae un tarball con proteccion contra path traversal y symlinks.

    Python 3.12+ usa filter='data' que bloquea ambos vectores.
    Python <3.12 valida cada miembro manualmente antes de extraer.
    """
    major, minor = sys.version_info[:2]
    if major > 3 or (major == 3 and minor >= 12):
        tar.extractall(path=dest, filter="data")
    else:
        # Pre-3.12: validacion manual de cada miembro
        dest_resolved = dest.resolve()
        safe_members: list[tarfile.TarInfo] = []
        for member in tar.getmembers():
            member_path = (dest_resolved / member.name).resolve()
            if not str(member_path).startswith(str(dest_resolved)):
                raise ValueError(f"Path traversal detectado en backup: {member.name!r}")
            if member.issym() or member.islnk():
                raise ValueError(f"Symlink no permitido en backup: {member.name!r}")
            safe_members.append(member)
        tar.extractall(path=dest, members=safe_members)


def create_backup(label: str = "manual") -> dict:
    """Crea un backup comprimido del .agent/brain/."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    backup_id = now.strftime("%Y%m%d_%H%M%S")
    filename = f"brain_{backup_id}_{label}.tar.gz"
    filepath = BACKUP_DIR / filename

    if not BRAIN_DIR.exists():
        raise FileNotFoundError(f"Brain dir no existe: {BRAIN_DIR}")

    node_count = count_nodes(BRAIN_DIR)
    logger.info("Creando backup: %s (%d nodos)", filename, node_count)

    with tarfile.open(filepath, "w:gz") as tar:
        tar.add(BRAIN_DIR, arcname="brain")

    # SHA256 para integridad
    sha = hashlib.sha256(filepath.read_bytes()).hexdigest()
    size = filepath.stat().st_size

    entry = {
        "id": backup_id,
        "label": label,
        "file": filename,
        "timestamp": now.isoformat(),
        "nodes": node_count,
        "size_bytes": size,
        "sha256": sha,
    }

    manifest = load_manifest()
    manifest["backups"].append(entry)
    save_manifest(manifest)

    logger.info("Backup OK: %s (%.1f KB)", filename, size / 1024)
    return entry


def list_backups() -> list[dict]:
    manifest = load_manifest()
    return sorted(
        manifest.get("backups", []),
        key=lambda b: b["timestamp"],
        reverse=True,
    )


def restore_backup(backup_id: str, *, force: bool = False) -> bool:
    manifest = load_manifest()
    entry = next(
        (b for b in manifest["backups"] if b["id"] == backup_id),
        None,
    )
    if not entry:
        logger.error("Backup no encontrado: %s", backup_id)
        return False

    filepath = BACKUP_DIR / entry["file"]
    if not filepath.exists():
        logger.error("Archivo no existe: %s", filepath)
        return False

    # Verificar SHA
    sha = hashlib.sha256(filepath.read_bytes()).hexdigest()
    if sha != entry["sha256"]:
        logger.error("SHA mismatch! Backup corrupto.")
        if not force:
            return False

    # Crear pre-restore backup primero
    if BRAIN_DIR.exists():
        logger.info("Creando pre-restore snapshot...")
        create_backup(label="pre-restore")
        shutil.rmtree(BRAIN_DIR)

    # Extraer con filtro de seguridad (Python 3.12+)
    # Previene path traversal via "../" en nombres de miembro del tarball
    logger.info("Restaurando desde %s...", entry["file"])
    BRAIN_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(filepath, "r:gz") as tar:
        # Python 3.12+: filter="data" bloquea path traversal y symlinks
        # Python <3.12: fallback manual que rechaza miembros fuera del destino
        _safe_extract(tar, BRAIN_DIR.parent)

    logger.info("Restaurado: %d nodos", entry["nodes"])
    return True


def clean_old_backups() -> dict:
    """Rotacion: 7 diarios + 4 semanales + 12 mensuales + 3 anuales."""
    manifest = load_manifest()
    backups = sorted(manifest.get("backups", []), key=lambda b: b["timestamp"], reverse=True)
    now = datetime.now(UTC)
    keep: set[str] = set()

    # 7 mas recientes siempre
    for b in backups[:7]:
        keep.add(b["id"])

    # Categorias
    daily_cutoff = now - timedelta(days=7)
    weekly_cutoff = now - timedelta(days=28)
    monthly_cutoff = now - timedelta(days=365)

    seen_weeks: set[str] = set()
    seen_months: set[str] = set()
    seen_years: set[str] = set()

    for b in backups:
        try:
            bdate = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            continue

        # 4 semanales (1 por semana en las ultimas 4)
        if bdate > weekly_cutoff and bdate <= daily_cutoff:
            week_key = bdate.strftime("%Y-W%U")
            if week_key not in seen_weeks and len(seen_weeks) < 4:
                seen_weeks.add(week_key)
                keep.add(b["id"])

        # 12 mensuales
        elif bdate > monthly_cutoff and bdate <= weekly_cutoff:
            month_key = bdate.strftime("%Y-%m")
            if month_key not in seen_months and len(seen_months) < 12:
                seen_months.add(month_key)
                keep.add(b["id"])

        # 3 anuales
        elif bdate <= monthly_cutoff:
            year_key = bdate.strftime("%Y")
            if year_key not in seen_years and len(seen_years) < 3:
                seen_years.add(year_key)
                keep.add(b["id"])

    # Borrar los que no estan en keep
    deleted = 0
    new_backups = []
    for b in backups:
        if b["id"] in keep:
            new_backups.append(b)
        else:
            filepath = BACKUP_DIR / b["file"]
            if filepath.exists():
                filepath.unlink()
                deleted += 1

    manifest["backups"] = new_backups
    save_manifest(manifest)

    logger.info("Rotacion: %d borrados, %d mantenidos", deleted, len(keep))
    return {"deleted": deleted, "kept": len(keep)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain Network backups")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--restore", metavar="ID")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--cron", action="store_true", help="crear + rotar")
    parser.add_argument("--label", default="manual")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.list:
        backups = list_backups()
        print(f"Total: {len(backups)} backups")
        for b in backups[:20]:
            print(
                f"  {b['id']:25s} {b['label']:12s} {b['nodes']:4d} nodos  {b['size_bytes'] // 1024:5d} KB"
            )
        return 0

    if args.restore:
        return 0 if restore_backup(args.restore, force=args.force) else 1

    if args.clean:
        clean_old_backups()
        return 0

    if args.cron:
        label = datetime.now(UTC).strftime("%A").lower()
        create_backup(label=f"auto-{label}")
        clean_old_backups()
        return 0

    # Default: crear backup manual
    create_backup(label=args.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
