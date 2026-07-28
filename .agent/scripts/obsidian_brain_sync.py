#!/usr/bin/env python3
"""
Obsidian <-> Brain bidirectional sync.

Sincroniza notas Obsidian con nodos del Brain:
- Vault -> Brain: importa notas de Obsidian como nodos
- Brain -> Vault: exporta nodos del Brain como notas Obsidian

Heuristica:
- Notas con frontmatter `type: brain-node` se sincronizan
- Tags en Obsidian <-> tags en Brain
- Links [[wikilinks]] <-> cross-refs en Brain

Uso:
  python obsidian_brain_sync.py --vault /path/to/vault
  python obsidian_brain_sync.py --pull     # vault -> brain
  python obsidian_brain_sync.py --push     # brain -> vault
  python obsidian_brain_sync.py --both     # ambos
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, UTC
from pathlib import Path

import yaml

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_obsidian_note(path: Path) -> dict | None:
    """Parsea nota Obsidian con frontmatter YAML."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    fm_match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not fm_match:
        return None

    try:
        fm = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError:
        return None

    body = fm_match.group(2).strip()

    # Solo sincronizar si tiene marker
    if fm.get("type") != "brain-node" and fm.get("brain_sync") is not True:
        return None

    # Extraer wikilinks [[...]]
    wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", body)

    return {
        "path": path,
        "title": fm.get("title") or path.stem,
        "context": body[:2500],
        "area": fm.get("area", "docs"),
        "tags": fm.get("tags", []),
        "node_type": fm.get("node_type", "session"),
        "importance": fm.get("importance", "normal"),
        "wikilinks": wikilinks,
        "obsidian_slug": path.stem,
    }


def pull_vault_to_brain(vault_path: Path) -> int:
    """Importa notas de Obsidian al Brain."""
    try:
        from core.brain import Brain  # noqa: PLC0415
    except ImportError:
        logger.error("No se pudo cargar core.brain")
        return 0

    brain = Brain(AGENT_ROOT / "brain", app_id="nexus-mother")
    count = 0

    for md_file in vault_path.rglob("*.md"):
        if any(p.startswith(".") for p in md_file.parts):
            continue

        note = parse_obsidian_note(md_file)
        if not note:
            continue

        try:
            brain.ingest(
                title=note["title"],
                context=note["context"],
                area=note["area"],
                tags=list(note["tags"]) + ["obsidian-sync"],
                node_type=note["node_type"],
                importance=note["importance"],
                sources=[f"obsidian:{note['obsidian_slug']}"],
            )
            count += 1
        except Exception as e:
            logger.warning("Error importando %s: %s", md_file.name, e)

    logger.info("Pull: %d notas de Obsidian -> Brain", count)
    return count


def push_brain_to_vault(vault_path: Path) -> int:
    """Exporta nodos del Brain a Obsidian."""
    try:
        from core.brain import Brain  # noqa: PLC0415
    except ImportError:
        return 0

    brain = Brain(AGENT_ROOT / "brain", app_id="nexus-mother")

    # Crear carpeta Brain/ en el vault
    brain_dir = vault_path / "Brain"
    brain_dir.mkdir(exist_ok=True)

    count = 0
    for node in brain.list_nodes(status="active"):
        # Solo nodos critical/high y concept/adr (no todos)
        if node.importance not in ("critical", "high") and node.type not in ("concept", "adr"):
            continue

        note_path = brain_dir / f"{node.slug}.md"

        # Build nota Obsidian
        fm = {
            "type": "brain-node",
            "brain_sync": True,
            "title": node.title,
            "area": node.area,
            "node_type": node.type,
            "importance": node.importance,
            "tags": node.tags,
            "date": node.date,
        }

        wikilinks = "".join([f"\n[[{r}]]" for r in node.related])

        body = (
            f"---\n{yaml.dump(fm, allow_unicode=True, sort_keys=False)}---\n\n"
            f"# {node.title}\n\n"
            f"## Contexto\n{node.context}\n\n"
        )
        if node.decisions:
            body += f"## Decisiones\n{node.decisions}\n\n"
        if node.output:
            body += f"## Output\n{node.output}\n\n"
        if wikilinks:
            body += f"## Relacionado\n{wikilinks}\n\n"
        body += f"---\n*Sync desde Brain — {datetime.now(UTC).strftime('%Y-%m-%d')}*\n"

        try:
            note_path.write_text(body, encoding="utf-8")
            count += 1
        except OSError as e:
            logger.warning("Error escribiendo %s: %s", note_path.name, e)

    logger.info("Push: %d nodos Brain -> Obsidian/Brain/", count)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Obsidian <-> Brain sync")
    parser.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT_ROOT", ""))
    parser.add_argument("--pull", action="store_true", help="Vault -> Brain")
    parser.add_argument("--push", action="store_true", help="Brain -> Vault")
    parser.add_argument("--both", action="store_true", help="Ambos")
    args = parser.parse_args()

    if not args.vault:
        args.vault = str(Path.home() / "Documents" / "GitHub" / "Obsidian")

    vault = Path(args.vault)
    if not vault.exists():
        logger.error("Vault no existe: %s", vault)
        return 1

    logger.info("Vault: %s", vault)

    if args.both or (not args.pull and not args.push):
        pull_vault_to_brain(vault)
        push_brain_to_vault(vault)
    elif args.pull:
        pull_vault_to_brain(vault)
    elif args.push:
        push_brain_to_vault(vault)

    return 0


if __name__ == "__main__":
    sys.exit(main())
