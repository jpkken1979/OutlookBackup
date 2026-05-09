#!/usr/bin/env python3
"""Archiva memorias viejas en `.claude/memory/archive/`.

Mueve archivos `session_*.md` (y otros con trigger=session en frontmatter)
cuya `date` sea mas vieja que `--days` (default 90) a un subdirectorio
`.claude/memory/archive/YYYY/`. No toca decisions, patterns, bugfixes ni
discoveries — esos son conocimiento reutilizable.

Uso:
    python .agent/scripts/archive_old_memories.py               # dry-run
    python .agent/scripts/archive_old_memories.py --apply       # mover archivos
    python .agent/scripts/archive_old_memories.py --days 180 --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
DATE_IN_NAME_RE = re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})")


@dataclass
class ArchivePlan:
    path: Path
    target: Path
    file_date: date
    reason: str


def _extract_date(path: Path) -> date | None:
    # Try frontmatter first
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    match = FRONTMATTER_RE.match(text)
    if match:
        for line in match.group(1).splitlines():
            if line.lower().startswith("date:"):
                raw = line.split(":", 1)[1].strip().strip("\"'")
                try:
                    return datetime.strptime(raw[:10], "%Y-%m-%d").date()
                except ValueError:
                    break

    # Fallback: date in filename
    m = DATE_IN_NAME_RE.search(path.name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _is_archivable(path: Path, text: str) -> bool:
    """Only archive session memories. Keep decisions/patterns/bugfixes forever."""
    match = FRONTMATTER_RE.match(text)
    trigger = ""
    if match:
        for line in match.group(1).splitlines():
            if line.lower().startswith("trigger:"):
                trigger = line.split(":", 1)[1].strip().strip("\"'")
                break
    if trigger:
        return trigger == "session"
    # No trigger → fall back to filename prefix
    return path.name.startswith("session_")


def plan_archive(memory_dir: Path, days: int) -> list[ArchivePlan]:
    cutoff = date.today() - timedelta(days=days)
    plans: list[ArchivePlan] = []

    for path in sorted(memory_dir.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        if not _is_archivable(path, text):
            continue
        file_date = _extract_date(path)
        if not file_date:
            continue
        if file_date > cutoff:
            continue
        target = memory_dir / "archive" / str(file_date.year) / path.name
        plans.append(
            ArchivePlan(
                path=path,
                target=target,
                file_date=file_date,
                reason=f"session > {days}d ({file_date.isoformat()})",
            )
        )
    return plans


def apply_archive(plans: list[ArchivePlan]) -> None:
    for plan in plans:
        plan.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(plan.path), str(plan.target))


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive old session memories")
    parser.add_argument("--dir", default=None)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    default_root = Path(__file__).resolve().parents[2]
    if args.dir:
        memory_dir = Path(args.dir).resolve()
        # Use the memory dir as anchor when it is outside the main repo
        repo_root = memory_dir.parent
    else:
        repo_root = default_root
        memory_dir = repo_root / ".claude" / "memory"
    if not memory_dir.exists():
        print(json.dumps({"error": f"Memory dir not found: {memory_dir}"}), file=sys.stderr)
        return 1

    plans = plan_archive(memory_dir, args.days)

    if args.apply:
        apply_archive(plans)

    def _safe_rel(path: Path) -> str:
        try:
            return str(path.relative_to(repo_root))
        except ValueError:
            return str(path)

    summary = {
        "dry_run": not args.apply,
        "days": args.days,
        "to_archive": len(plans),
        "items": [
            {
                "file": _safe_rel(p.path),
                "target": _safe_rel(p.target),
                "date": p.file_date.isoformat(),
            }
            for p in plans[:50]
        ],
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        mode = "APPLIED" if args.apply else "DRY-RUN"
        print(f"[{mode}] {len(plans)} session(es) para archivar (mas vieja que {args.days}d)")
        for plan in plans[:30]:
            print(
                f"  {plan.file_date.isoformat()}  "
                f"{plan.path.name}  →  archive/{plan.file_date.year}/"
            )
        if len(plans) > 30:
            print(f"  ... y {len(plans) - 30} mas")
        if not args.apply and plans:
            print("\nPara aplicar: pasar --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
