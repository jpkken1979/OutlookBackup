#!/usr/bin/env python3
"""Migracion one-shot: agrega o completa frontmatter YAML en `.claude/memory/*.md`.

Para cada archivo:
- Si NO tiene frontmatter, agrega uno inferido desde el filename y la primera
  linea util del cuerpo (titulo H1 si existe, primera linea no vacia si no).
- Si tiene frontmatter parcial, completa solo las claves faltantes entre
  `name`, `description`, `date`, `type`, `trigger`.
- Nunca sobrescribe claves existentes.

Por defecto corre en `--dry-run` mostrando que haria. Pasar `--apply` para
modificar archivos.

Uso:
    python .agent/scripts/migrate_memory_frontmatter.py               # dry-run
    python .agent/scripts/migrate_memory_frontmatter.py --apply       # escribir
    python .agent/scripts/migrate_memory_frontmatter.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
DATE_IN_NAME_RE = re.compile(r"(\d{4}[-_]\d{2}[-_]\d{2})")

PREFIX_TO_TRIGGER = {
    "session_": ("session", "project"),
    "decision_": ("decision", "project"),
    "bugfix_": ("bugfix", "project"),
    "discovery_": ("discovery", "project"),
    "pattern_": ("pattern", "feedback"),
    "config_": ("config", "project"),
    "feedback_": ("feedback", "feedback"),
    "audit_": ("discovery", "reference"),
    "project_": ("session", "project"),
}


@dataclass
class MigrationPlan:
    path: Path
    added_keys: dict[str, str]
    had_frontmatter: bool
    skipped: bool = False
    reason: str = ""


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str, str]:
    """Returns (existing_keys, raw_block, body_after)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, "", text
    raw_block = match.group(1)
    body_after = text[match.end() :]
    keys: dict[str, str] = {}
    for line in raw_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key:
            keys[key] = value
    return keys, raw_block, body_after


def _first_h1_or_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:140]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "---", "```", ">", "|")):
            return stripped[:140]
    return ""


def _infer_trigger_and_type(filename: str) -> tuple[str, str]:
    for prefix, (trigger, doc_type) in PREFIX_TO_TRIGGER.items():
        if filename.startswith(prefix):
            return trigger, doc_type
    return "discovery", "reference"


def _infer_date(filename: str) -> str:
    match = DATE_IN_NAME_RE.search(filename)
    if not match:
        return ""
    return match.group(1).replace("_", "-")


def _derive_name(filename: str, body: str) -> str:
    h1 = _first_h1_or_line(body)
    if h1:
        return h1
    stem = Path(filename).stem
    stem = re.sub(r"[_-]+", " ", stem)
    return stem.strip().title()


def _derive_description(body: str, name: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith(("#", "---", "```", ">", "|"))
            and stripped != name
        ):
            return stripped[:140]
    return "(auto-inferido)"


def _render_frontmatter(keys: dict[str, str]) -> str:
    order = ["name", "description", "type", "trigger", "date"]
    lines = ["---"]
    for key in order:
        if key in keys:
            lines.append(f"{key}: {keys[key]}")
    for key, value in keys.items():
        if key not in order:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def plan_migration(path: Path) -> MigrationPlan:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return MigrationPlan(path, {}, False, skipped=True, reason=f"read error: {exc}")

    keys, _, body_after_front = _parse_frontmatter(text)
    had_frontmatter = bool(keys)
    body = body_after_front if had_frontmatter else text

    trigger, doc_type = _infer_trigger_and_type(path.name)
    inferred_date = _infer_date(path.name)
    inferred_name = _derive_name(path.name, body)
    inferred_description = _derive_description(body, inferred_name)

    to_add: dict[str, str] = {}
    if "name" not in keys and inferred_name:
        to_add["name"] = inferred_name
    if "description" not in keys and inferred_description:
        to_add["description"] = inferred_description
    if "trigger" not in keys:
        to_add["trigger"] = trigger
    if "type" not in keys:
        to_add["type"] = doc_type
    if "date" not in keys and inferred_date:
        to_add["date"] = inferred_date

    return MigrationPlan(path=path, added_keys=to_add, had_frontmatter=had_frontmatter)


def apply_migration(plan: MigrationPlan) -> None:
    if not plan.added_keys:
        return
    text = plan.path.read_text(encoding="utf-8")
    keys, _, body = _parse_frontmatter(text)
    if not keys:
        body = text

    merged = dict(plan.added_keys)
    merged.update(keys)  # existing keys win

    new_text = _render_frontmatter(merged) + body.lstrip("\n")
    plan.path.write_text(new_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate memory frontmatter")
    parser.add_argument("--dir", default=None)
    parser.add_argument("--apply", action="store_true", help="Actually write files")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    memory_dir = Path(args.dir) if args.dir else repo_root / ".claude" / "memory"
    if not memory_dir.exists():
        print(json.dumps({"error": f"Memory dir not found: {memory_dir}"}), file=sys.stderr)
        return 1

    plans: list[MigrationPlan] = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        plans.append(plan_migration(path))

    changed = [p for p in plans if p.added_keys]
    unchanged = [p for p in plans if not p.added_keys and not p.skipped]
    skipped = [p for p in plans if p.skipped]

    if args.apply:
        for plan in changed:
            apply_migration(plan)

    summary = {
        "dry_run": not args.apply,
        "total": len(plans),
        "changed": len(changed),
        "unchanged": len(unchanged),
        "skipped": len(skipped),
        "changes": [
            {"file": p.path.name, "added_keys": list(p.added_keys.keys())}
            for p in changed[:50]
        ],
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        mode = "APPLIED" if args.apply else "DRY-RUN"
        print(f"[{mode}] {len(changed)} archivo(s) a modificar, "
              f"{len(unchanged)} sin cambios, {len(skipped)} omitido(s)")
        for plan in changed[:30]:
            keys = ", ".join(sorted(plan.added_keys.keys()))
            print(f"  + {plan.path.name}: agregar {keys}")
        if len(changed) > 30:
            print(f"  ... y {len(changed) - 30} mas")
        if not args.apply and changed:
            print("\nPara aplicar: pasar --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
