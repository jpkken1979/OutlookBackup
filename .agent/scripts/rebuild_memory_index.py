#!/usr/bin/env python3
"""Rebuild `.claude/memory/MEMORY.md` from the markdown files in the folder.

Lee todos los archivos `.md` en `.claude/memory/` (excepto MEMORY.md), extrae
el frontmatter YAML si existe, y reconstruye un indice agrupado por tipo
(sessions, decisions, bugfixes, discoveries, patterns, configs, feedback).

Si un archivo no tiene frontmatter, el script infiere el tipo desde el
prefijo del filename (`decision_`, `bugfix_`, `session_`, etc.) y usa la
primera linea no vacia del cuerpo como descripcion.

Uso:
    python .agent/scripts/rebuild_memory_index.py
    python .agent/scripts/rebuild_memory_index.py --dir .claude/memory

Salida: JSON con `{"indexed": N, "by_type": {...}}`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from datetime import UTC

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
AUTO_BEGIN = "<!-- BEGIN AUTO -->"
AUTO_END = "<!-- END AUTO -->"
AUTO_BLOCK_RE = re.compile(
    rf"{re.escape(AUTO_BEGIN)}.*?{re.escape(AUTO_END)}",
    re.DOTALL,
)
TYPE_PREFIXES = {
    "session_": "sessions",
    "decision_": "decisions",
    "bugfix_": "bugfixes",
    "discovery_": "discoveries",
    "pattern_": "patterns",
    "config_": "configs",
    "feedback_": "feedback",
    "project_": "projects",
    "audit_": "audits",
}

TYPE_LABELS = {
    "sessions": "Sesiones",
    "decisions": "Decisiones",
    "bugfixes": "Bugfixes",
    "discoveries": "Discoveries",
    "patterns": "Patterns",
    "configs": "Config",
    "feedback": "Feedback",
    "projects": "Proyectos",
    "audits": "Auditorias",
    "other": "Otros",
}

# Cuantas entradas mostrar por grupo en el indice activo (MEMORY.md). El resto
# se vuelca a MEMORY_ARCHIVE.md para que MEMORY.md cargue completo en el
# contexto de Claude Code sin truncarse.
DEFAULT_MAX_PER_GROUP = 30
ARCHIVE_FILENAME = "MEMORY_ARCHIVE.md"


@dataclass
class MemoryEntry:
    path: Path
    name: str
    description: str
    type_group: str
    date: str = ""


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract key-value pairs from YAML frontmatter (simple parser)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    body = match.group(1)
    result: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if key and value:
            result[key] = value
    return result


def _infer_type(filename: str) -> str:
    for prefix, group in TYPE_PREFIXES.items():
        if filename.startswith(prefix):
            return group
    return "other"


def _first_content_line(text: str) -> str:
    body = FRONTMATTER_RE.sub("", text, count=1)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:140]
    return ""


def collect_entries(memory_dir: Path) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue

        meta = _parse_frontmatter(text)
        name = meta.get("name") or path.stem.replace("_", " ")
        description = meta.get("description") or _first_content_line(text) or "(sin descripcion)"
        date = meta.get("date", "")
        trigger = meta.get("trigger", "")
        type_group = {
            "decision": "decisions",
            "bugfix": "bugfixes",
            "discovery": "discoveries",
            "pattern": "patterns",
            "config": "configs",
            "session": "sessions",
        }.get(trigger) or _infer_type(path.name)
        entries.append(
            MemoryEntry(
                path=path,
                name=name,
                description=description,
                type_group=type_group,
                date=date,
            )
        )
    return entries


def _group_and_sort(entries: list[MemoryEntry]) -> dict[str, list[MemoryEntry]]:
    """Group entries by type and sort each group by date desc (newest first)."""
    grouped: dict[str, list[MemoryEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.type_group, []).append(entry)
    for group in grouped.values():
        group.sort(key=lambda e: (e.date or "", e.name), reverse=True)
    return grouped


def _ordered_groups(grouped: dict[str, list[MemoryEntry]]) -> list[tuple[str, str]]:
    """Yield (group_key, label) pairs: canonical labels first, then extras."""
    pairs = [(k, lbl) for k, lbl in TYPE_LABELS.items() if grouped.get(k)]
    extras = sorted(set(grouped.keys()) - set(TYPE_LABELS.keys()))
    pairs.extend((key, key.title()) for key in extras)
    return pairs


def _render_entry(entry: MemoryEntry) -> str:
    """Render a single index line for an entry."""
    date_prefix = f"[{entry.date}] " if entry.date else ""
    return f"- {date_prefix}[{entry.name}]({entry.path.name}) — {entry.description}"


def render_auto_block(
    entries: list[MemoryEntry],
    max_per_group: int = DEFAULT_MAX_PER_GROUP,
    archive_name: str = ARCHIVE_FILENAME,
) -> str:
    """Render the auto-generated index block (between AUTO_BEGIN and AUTO_END).

    Solo muestra hasta ``max_per_group`` entradas por grupo (las mas recientes).
    Si un grupo excede el limite, agrega una nota que linkea al archivo historico
    ``archive_name``. Con ``max_per_group <= 0`` no se trunca (comportamiento
    legacy).
    """
    from datetime import datetime

    grouped = _group_and_sort(entries)
    archived_total = (
        sum(max(0, len(g) - max_per_group) for g in grouped.values()) if max_per_group > 0 else 0
    )

    lines: list[str] = [
        AUTO_BEGIN,
        "",
        f"> Auto-generado: {len(entries)} entradas.",
        f"> Ultima reconstruccion: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC",
        ">",
        "> Este bloque se regenera con:",
        "> `python .agent/scripts/rebuild_memory_index.py`",
        "> Todo lo que este fuera de los marcadores BEGIN/END AUTO se preserva.",
    ]
    if archived_total:
        lines.append(
            f"> Mostrando las ultimas {max_per_group} por grupo; "
            f"{archived_total} entradas historicas en [{archive_name}]({archive_name})."
        )
    lines.append("")

    for group_key, label in _ordered_groups(grouped):
        group_entries = grouped[group_key]
        shown = group_entries[:max_per_group] if max_per_group > 0 else group_entries
        hidden = len(group_entries) - len(shown)
        lines.append(f"## {label}")
        lines.append("")
        lines.extend(_render_entry(entry) for entry in shown)
        if hidden > 0:
            lines.append(f"- _…{hidden} mas en [{archive_name}]({archive_name})_")
        lines.append("")

    lines.append(AUTO_END)
    return "\n".join(lines)


def render_archive(
    entries: list[MemoryEntry],
    max_per_group: int = DEFAULT_MAX_PER_GROUP,
) -> str:
    """Render MEMORY_ARCHIVE.md with the entries that overflow the active index.

    Contiene, por grupo, las entradas que pasan de ``max_per_group`` (las mas
    viejas). El archivo es 100% generado: se sobreescribe entero en cada rebuild.
    """
    from datetime import datetime

    grouped = _group_and_sort(entries)
    overflow = {
        key: group[max_per_group:]
        for key, group in grouped.items()
        if max_per_group > 0 and len(group) > max_per_group
    }

    lines: list[str] = [
        "# Memoria del Proyecto — Archivo Historico",
        "",
        "> **Archivo 100% auto-generado por `rebuild_memory_index.py` — no editar a mano.**",
        f"> Ultima reconstruccion: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC",
        ">",
        "> Indice de las memorias mas antiguas. Las recientes viven en `MEMORY.md`.",
        "> Las memorias individuales siguen en sus archivos `.md`; esto es solo el indice.",
        "",
    ]

    total = 0
    for group_key, label in _ordered_groups(grouped):
        group_overflow = overflow.get(group_key, [])
        if not group_overflow:
            continue
        lines.append(f"## {label}")
        lines.append("")
        lines.extend(_render_entry(entry) for entry in group_overflow)
        lines.append("")
        total += len(group_overflow)

    if total == 0:
        lines.append("_Sin entradas archivadas todavia._")
        lines.append("")

    return "\n".join(lines)


def render_initial_index(auto_block: str) -> str:
    """Build the whole file when MEMORY.md does not exist yet."""
    return (
        "# Memoria del Proyecto — OpenAntigravity\n"
        "\n"
        "Edita este archivo libremente. El bloque entre los marcadores BEGIN/END AUTO\n"
        "es reescrito por `rebuild_memory_index.py`; el resto se preserva.\n"
        "\n"
        f"{auto_block}\n"
    )


def splice_auto_block(existing: str, auto_block: str) -> str:
    """Replace the AUTO block in `existing` with `auto_block`, preserving the rest.

    If no markers are present, append the AUTO block at the end of the file so
    manual content on top is preserved.
    """
    if AUTO_BEGIN in existing and AUTO_END in existing:
        return AUTO_BLOCK_RE.sub(lambda _m: auto_block, existing, count=1)
    stripped = existing.rstrip() + "\n\n" if existing.strip() else ""
    return f"{stripped}{auto_block}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild MEMORY.md index")
    parser.add_argument(
        "--dir",
        default=None,
        help="Memory dir (default: <repo>/.claude/memory)",
    )
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--max-per-group",
        type=int,
        default=DEFAULT_MAX_PER_GROUP,
        help=(
            "Entradas a mostrar por grupo en MEMORY.md; el resto va a "
            f"{ARCHIVE_FILENAME}. 0 = sin limite (legacy). "
            f"Default: {DEFAULT_MAX_PER_GROUP}"
        ),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    memory_dir = Path(args.dir) if args.dir else repo_root / ".claude" / "memory"

    if not memory_dir.exists():
        print(json.dumps({"error": f"Memory dir not found: {memory_dir}"}), file=sys.stderr)
        return 1

    entries = collect_entries(memory_dir)
    auto_block = render_auto_block(entries, max_per_group=args.max_per_group)

    index_path = memory_dir / "MEMORY.md"
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        new_content = splice_auto_block(existing, auto_block)
    else:
        new_content = render_initial_index(auto_block)

    index_path.write_text(new_content, encoding="utf-8")

    # Escribir el archivo historico con el overflow (entradas mas viejas).
    archive_path = memory_dir / ARCHIVE_FILENAME
    archived = 0
    if args.max_per_group > 0:
        archive_content = render_archive(entries, max_per_group=args.max_per_group)
        archive_path.write_text(archive_content.rstrip() + "\n", encoding="utf-8")
        grouped = _group_and_sort(entries)
        archived = sum(max(0, len(g) - args.max_per_group) for g in grouped.values())

    by_type: dict[str, int] = {}
    for entry in entries:
        by_type[entry.type_group] = by_type.get(entry.type_group, 0) + 1

    if not args.quiet:
        print(
            json.dumps(
                {
                    "indexed": len(entries),
                    "archived": archived,
                    "by_type": by_type,
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
