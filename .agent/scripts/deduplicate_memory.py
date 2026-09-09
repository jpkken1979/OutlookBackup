#!/usr/bin/env python3
"""Deduplicate memory entries across the 3-layer memory system.

Scans .claude/memory/ for duplicate entries (markdown layer), identifies
similar entries in .agent/brain/ (Brain Network layer), and reports
candidates for deduplication or merging.

Uso:
    python .agent/scripts/deduplicate_memory.py
    python .agent/scripts/deduplicate_memory.py --dry-run
    python .agent/scripts/deduplicate_memory.py --similarity 0.80
    python .agent/scripts/deduplicate_memory.py --remove-redundant
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.memory.models import MemoryEntry, MemoryType, MemoryLayer, MemoryDeduplicator
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def discover_memory_entries(memory_dir: Path) -> list[MemoryEntry]:
    """Discover all memory entries from markdown files.

    Args:
        memory_dir: Ruta a .claude/memory.

    Returns:
        Lista de MemoryEntry.
    """
    entries: list[MemoryEntry] = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.name in ("MEMORY.md", "MEMORY_ARCHIVE.md"):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            continue

        # Computar hash y extraer metadatos básicos
        content_hash = MemoryDeduplicator.compute_hash(content)
        name = path.stem.replace("_", " ")

        # Extraer descripción de la primera línea no vacía
        description = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                description = stripped[:150]
                break

        # Inferred type desde el prefijo del nombre
        inferred_type = MemoryType.OTHER
        for prefix, mem_type in [
            ("decision_", MemoryType.DECISION),
            ("bugfix_", MemoryType.BUGFIX),
            ("discovery_", MemoryType.DISCOVERY),
            ("pattern_", MemoryType.PATTERN),
            ("config_", MemoryType.CONFIG),
            ("session_", MemoryType.SESSION),
            ("project_", MemoryType.PROJECT),
            ("audit_", MemoryType.AUDIT),
        ]:
            if path.name.startswith(prefix):
                inferred_type = mem_type
                break

        # Crear entrada
        entry_id = path.stem
        now = datetime.utcnow().isoformat()
        entry = MemoryEntry(
            id=entry_id,
            path=path,
            name=name,
            description=description,
            content_hash=content_hash,
            memory_type=inferred_type,
            created_at=now,
            updated_at=now,
            layer=[MemoryLayer.MARKDOWN],
            confidence=1.0,
        )
        entries.append(entry)

    logger.info(f"Discovered {len(entries)} memory entries")
    return entries


def discover_brain_entries(brain_dir: Path) -> list[MemoryEntry]:
    """Discover entries from Brain Network (via index.md or concept files).

    Args:
        brain_dir: Ruta a .agent/brain.

    Returns:
        Lista de MemoryEntry desde Brain.
    """
    entries: list[MemoryEntry] = []

    # Buscar en archivos del brain (~128K conceptos, pueden estar en .md o .json)
    if not brain_dir.exists():
        return entries

    for path in sorted(brain_dir.glob("**/*.md")):
        if path.name == "index.md":
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read brain file {path}: {e}")
            continue

        content_hash = MemoryDeduplicator.compute_hash(content)
        name = path.stem
        description = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped[:150]
                break

        entry_id = f"brain_{path.stem}"
        now = datetime.utcnow().isoformat()
        entry = MemoryEntry(
            id=entry_id,
            path=path,
            name=name,
            description=description,
            content_hash=content_hash,
            memory_type=MemoryType.OTHER,
            created_at=now,
            updated_at=now,
            layer=[MemoryLayer.BRAIN],
            confidence=0.9,
        )
        entries.append(entry)

    logger.info(f"Discovered {len(entries)} Brain entries")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate memory entries across layers")
    parser.add_argument(
        "--memory-dir",
        default=None,
        help="Ruta a .claude/memory (default: <repo>/.claude/memory)",
    )
    parser.add_argument(
        "--brain-dir",
        default=None,
        help="Ruta a .agent/brain (default: <repo>/.agent/brain)",
    )
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.85,
        help="Jaccard similarity threshold [0.0, 1.0] (default: 0.85)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only, don't modify files",
    )
    parser.add_argument(
        "--remove-redundant",
        action="store_true",
        help="Actually delete redundant files (dangerous!)",
    )
    parser.add_argument(
        "--output-report",
        default=None,
        help="Guardar reporte JSON (default: .antigravity/dedup_report.json)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    memory_dir = Path(args.memory_dir) if args.memory_dir else repo_root / ".claude" / "memory"
    brain_dir = Path(args.brain_dir) if args.brain_dir else repo_root / ".agent" / "brain"

    if not memory_dir.exists():
        logger.error(f"Memory dir not found: {memory_dir}")
        return 1

    logger.info(f"Scanning {memory_dir} and {brain_dir}...")
    entries = discover_memory_entries(memory_dir)
    if brain_dir.exists():
        brain_entries = discover_brain_entries(brain_dir)
        entries.extend(brain_entries)

    logger.info(f"Total entries: {len(entries)}")

    # Deduplicar
    deduplicator = MemoryDeduplicator(similarity_threshold=args.similarity)
    result = deduplicator.deduplicate(entries)

    # Mostrar resultados
    logger.info("\n=== Deduplication Results ===")
    logger.info(f"Total entries: {result.total_entries}")
    logger.info(f"Duplicates found: {result.duplicates_found}")
    logger.info(f"Canonical entries: {result.canonical_entries}")
    logger.info(f"Redundant entries: {len(result.redundant_entries)}")

    if result.redundant_entries:
        logger.info("\nRedundant entries:")
        for entry_id in result.redundant_entries:
            logger.info(f"  - {entry_id}")

    if result.merge_operations:
        logger.info(f"\nMerge operations ({len(result.merge_operations)}):")
        for src, tgt, reason in result.merge_operations:
            logger.info(f"  {src} -> {tgt}: {reason}")

    # Guardar reporte
    report_path = (
        Path(args.output_report)
        if args.output_report
        else repo_root / ".antigravity" / "dedup_report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    deduplicator.save_dedup_report(result, report_path)

    # Acción: eliminar redundantes si se pide (y no es dry-run)
    if args.remove_redundant and not args.dry_run:
        for entry_id in result.redundant_entries:
            # Buscar la entrada original
            for entry in entries:
                if entry.id == entry_id:
                    try:
                        if entry.path.exists():
                            entry.path.unlink()
                            logger.info(f"Deleted: {entry.path}")
                    except Exception as e:
                        logger.error(f"Could not delete {entry.path}: {e}")
                    break

    if args.dry_run:
        logger.info("\n[DRY RUN] No files were modified")

    return 0


if __name__ == "__main__":
    sys.exit(main())
