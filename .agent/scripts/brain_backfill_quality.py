#!/usr/bin/env python3
"""Backfill reversible de ``content_hash`` y ``topic_key`` para Brain.

El modo predeterminado es dry-run. ``--apply`` crea un backup antes de tocar
cualquier nodo y usa reemplazos atómicos. ``--rollback`` restaura exactamente
los bytes registrados en el manifest del backup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

AGENT_DIR = Path(__file__).resolve().parent.parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from core.brain import BrainNode  # noqa: E402


def _node_files(brain_dir: Path) -> list[Path]:
    files: list[Path] = []
    for folder in ("sessions", "concepts", "connections"):
        directory = brain_dir / folder
        if directory.exists():
            files.extend(path for path in directory.glob("*.md") if not path.is_symlink())
    return sorted(files)


def _with_quality_fields(content: str, node: BrainNode) -> str:
    if not content.startswith("---"):
        raise ValueError("Nodo sin frontmatter YAML")
    parts = content.split("---", 2)
    if len(parts) != 3:
        raise ValueError("Frontmatter YAML incompleto")
    fm = yaml.safe_load(parts[1]) or {}
    if not isinstance(fm, dict):
        raise ValueError("Frontmatter YAML invalido")
    if fm.get("content_hash") == node.content_hash and fm.get("topic_key") == node.topic_key:
        return content
    fm["content_hash"] = node.content_hash
    fm["topic_key"] = node.topic_key
    serialized = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
    body = parts[2]
    if body.startswith("\r\n"):
        body = body[2:]
    elif body.startswith("\n"):
        body = body[1:]
    return f"---\n{serialized}\n---\n{body}"


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _create_backup(brain_dir: Path, files: list[Path], backup_root: Path) -> Path:
    backup_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
    backup_dir = backup_root / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, str]] = []
    for source in files:
        relative = source.relative_to(brain_dir)
        destination = backup_dir / "files" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        entries.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "schema": 1,
        "brain_dir": str(brain_dir.resolve()),
        "created_at": datetime.now(UTC).isoformat(),
        "files": entries,
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return backup_dir


def rollback_backup(backup_dir: Path, *, brain_dir: Path | None = None) -> dict[str, Any]:
    """Restaura exactamente los archivos de un backup de backfill."""
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    target_root = (brain_dir or Path(manifest["brain_dir"])).resolve()
    restored: list[str] = []
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        source = (backup_dir / "files" / relative).resolve()
        target = (target_root / relative).resolve()
        if target_root not in target.parents:
            raise ValueError(f"Ruta fuera del Brain: {relative}")
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Backup corrupto: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(target, raw)
        restored.append(relative.as_posix())
    return {"mode": "rollback", "restored": restored, "backup": str(backup_dir)}


def backfill_quality(
    brain_dir: Path,
    *,
    apply: bool = False,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    """Inspecciona o aplica campos de calidad sin reescribir nodos al leerlos."""
    brain_dir = brain_dir.resolve()
    changes: list[tuple[Path, bytes]] = []
    errors: list[dict[str, str]] = []
    for node_path in _node_files(brain_dir):
        try:
            raw = node_path.read_bytes()
            content = raw.decode("utf-8")
            node = BrainNode.from_frontmatter(content, node_path)
            updated = _with_quality_fields(content, node).encode("utf-8")
            if updated != raw:
                changes.append((node_path, updated))
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            errors.append({"path": str(node_path.relative_to(brain_dir)), "error": str(exc)})

    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "brain_dir": str(brain_dir),
        "changed_count": len(changes),
        "changed": [path.relative_to(brain_dir).as_posix() for path, _ in changes],
        "errors": errors,
        "backup": None,
    }
    if not apply or not changes:
        return report

    destination = (backup_root or brain_dir.parent / "brain-quality-backups").resolve()
    backup_dir = _create_backup(brain_dir, [path for path, _ in changes], destination)
    report["backup"] = str(backup_dir)
    try:
        for node_path, updated in changes:
            _atomic_write_bytes(node_path, updated)
    except Exception:
        rollback_backup(backup_dir, brain_dir=brain_dir)
        raise
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brain-dir", type=Path, default=AGENT_DIR / "brain")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Solo reportar (default)")
    mode.add_argument("--apply", action="store_true", help="Crear backup y aplicar")
    mode.add_argument("--rollback", type=Path, help="Restaurar un backup anterior")
    parser.add_argument("--backup-dir", type=Path, help="Raíz donde guardar el backup")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.rollback:
        report = rollback_backup(args.rollback, brain_dir=args.brain_dir)
    else:
        report = backfill_quality(
            args.brain_dir,
            apply=args.apply,
            backup_root=args.backup_dir,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
