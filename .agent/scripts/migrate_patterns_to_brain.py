"""Migra archivos pattern_*.md de .claude/memory/ al Brain Network.

Lee todos los archivos de patrones, extrae frontmatter YAML y contenido,
y los ingiere como nodos con node_type='pattern'. Idempotente: no duplica.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.brain import Brain

logger = logging.getLogger(__name__)

BRAIN_DIR = Path(__file__).resolve().parent.parent / "brain"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parsea frontmatter YAML simple (solo key: value) de un markdown.

    Args:
        text: Contenido completo del archivo markdown.

    Returns:
        Tupla (frontmatter_dict, body_content).
    """
    lines = text.split("\n")
    start_idx: int | None = None
    end_idx: int | None = None

    for i, line in enumerate(lines):
        if line.strip() == "---":
            if start_idx is None:
                start_idx = i + 1
            else:
                end_idx = i
                break

    if start_idx is None or end_idx is None:
        return {}, text

    frontmatter: dict[str, str] = {}
    for i in range(start_idx, end_idx):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([^:]+):\s*(.+)$", line)
        if match:
            frontmatter[match.group(1).strip()] = match.group(2).strip()

    body = "\n".join(lines[end_idx + 1 :]).strip()
    return frontmatter, body


def migrate_patterns(memory_dir: Path, brain_dir: Path) -> dict[str, int]:
    """Migra pattern_*.md de memoria al Brain Network.

    Args:
        memory_dir: Directorio .claude/memory/.
        brain_dir: Directorio .agent/brain/.

    Returns:
        Estadísticas: total, migrated, skipped, errors.
    """
    stats: dict[str, int] = {"total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    if not memory_dir.exists():
        logger.error("Directorio no encontrado: %s", memory_dir)
        return stats

    pattern_files = sorted(memory_dir.glob("pattern_*.md"))
    stats["total"] = len(pattern_files)
    logger.info("Encontrados %d archivos de patrones", stats["total"])

    if not pattern_files:
        return stats

    brain = Brain(brain_dir, app_id="pattern-migrator")

    for pattern_file in pattern_files:
        try:
            content = pattern_file.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(content)

            title = frontmatter.get("name", pattern_file.stem)
            description = frontmatter.get("description", "")

            logger.info("Procesando: %s -> %s", pattern_file.name, title)

            # Verificar duplicados por título en concepts/
            slug = title.lower().replace(" ", "-").replace("_", "-")[:60]
            existing = (brain_dir / "concepts" / f"{slug}.md").exists()
            if not existing:
                # También buscar en sessions/
                existing = (brain_dir / "sessions" / f"{slug}.md").exists()

            if existing:
                logger.info("  Saltado: ya existe nodo '%s'", slug)
                stats["skipped"] += 1
                continue

            context_parts: list[str] = []
            if description:
                context_parts.append(f"**Descripcion:** {description}")
            if body:
                context_parts.append(body)

            full_context = "\n\n".join(context_parts)

            brain.ingest(
                title=title,
                context=full_context,
                node_type="pattern",
                tags=["pattern", "migrated"],
                importance="medium",
                area="patterns",
            )

            logger.info("  Migrado exitosamente")
            stats["migrated"] += 1

        except Exception as exc:  # noqa: BLE001
            logger.error("  Error procesando %s: %s", pattern_file.name, exc)
            stats["errors"] += 1

    return stats


def main() -> None:
    """Entry point del script."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    repo_base = Path(__file__).resolve().parent.parent.parent
    memory_dir = repo_base / ".claude" / "memory"

    logger.info("Migracion de patterns a brain")
    logger.info("Repo: %s", repo_base)
    logger.info("Memory: %s", memory_dir)
    logger.info("Brain: %s", BRAIN_DIR)

    stats = migrate_patterns(memory_dir, BRAIN_DIR)

    logger.info("Resumen: total=%d, migrated=%d, skipped=%d, errors=%d",
                stats["total"], stats["migrated"], stats["skipped"], stats["errors"])

    if stats["migrated"] > 0:
        logger.info("Migracion completada: %d patrones nuevos en brain", stats["migrated"])
    elif stats["total"] == 0:
        logger.warning("No se encontraron archivos pattern_*.md")
    else:
        logger.info("Todos los patrones ya estaban migrados")


if __name__ == "__main__":
    main()
