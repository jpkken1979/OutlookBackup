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
from dataclasses import dataclass, field
from pathlib import Path

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
        type_group = (
            {
                "decision": "decisions",
                "bugfix": "bugfixes",
                "discovery": "discoveries",
                "pattern": "patterns",
                "config": "configs",
                "session": "sessions",
            }.get(trigger)
            or _infer_type(path.name)
        )
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


def render_auto_block(entries: list[MemoryEntry]) -> str:
    """Render the auto-generated index block (between AUTO_BEGIN and AUTO_END)."""
    from datetime import datetime

    grouped: dict[str, list[MemoryEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.type_group, []).append(entry)

    for group in grouped.values():
        group.sort(key=lambda e: (e.date or "", e.name), reverse=True)

    lines: list[str] = [
        AUTO_BEGIN,
        "",
        f"> Auto-generado: {len(entries)} entradas.",
        f"> Ultima reconstruccion: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        ">",
        "> Este bloque se regenera con:",
        "> `python .agent/scripts/rebuild_memory_index.py`",
        "> Todo lo que este fuera de los marcadores BEGIN/END AUTO se preserva.",
        "",
    ]

    for group_key, label in TYPE_LABELS.items():
        group_entries = grouped.get(group_key, [])
        if not group_entries:
            continue
        lines.append(f"## {label}")
        lines.append("")
        for entry in group_entries:
            rel = entry.path.name
            date_prefix = f"[{entry.date}] " if entry.date else ""
            lines.append(
                f"- {date_prefix}[{entry.name}]({rel}) — {entry.description}"
            )
        lines.append("")

    # Emit "other" group if there are entries not in canonical labels
    other_groups = set(grouped.keys()) - set(TYPE_LABELS.keys())
    for key in sorted(other_groups):
        lines.append(f"## {key.title()}")
        lines.append("")
        for entry in grouped[key]:
            rel = entry.path.name
            date_prefix = f"[{entry.date}] " if entry.date else ""
            lines.append(
                f"- {date_prefix}[{entry.name}]({rel}) — {entry.description}"
            )
        lines.append("")

    lines.append(AUTO_END)
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
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    memory_dir = Path(args.dir) if args.dir else repo_root / ".claude" / "memory"

    if not memory_dir.exists():
        print(json.dumps({"error": f"Memory dir not found: {memory_dir}"}), file=sys.stderr)
        return 1

    entries = collect_entries(memory_dir)
    auto_block = render_auto_block(entries)

    index_path = memory_dir / "MEMORY.md"
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        new_content = splice_auto_block(existing, auto_block)
    else:
        new_content = render_initial_index(auto_block)

    index_path.write_text(new_content, encoding="utf-8")

    by_type: dict[str, int] = {}
    for entry in entries:
        by_type[entry.type_group] = by_type.get(entry.type_group, 0) + 1

    if not args.quiet:
        print(json.dumps({"indexed": len(entries), "by_type": by_type}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
