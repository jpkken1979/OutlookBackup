#!/usr/bin/env python3
"""Unified ce-todo skill: create, triage, and resolve Compound Engineering todos."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path


def get_todos_dir() -> Path:
    """Return the todos directory, creating it if needed."""
    todos_dir = Path.home() / ".antigravity" / "todos"
    todos_dir.mkdir(parents=True, exist_ok=True)
    return todos_dir


def next_seq(todos_dir: Path) -> int:
    """Return the next 3-digit sequence number."""
    existing = list(todos_dir.glob("*-pending-*.md"))
    existing += list(todos_dir.glob("*-ready-*.md"))
    existing += list(todos_dir.glob("*-complete-*.md"))
    nums = []
    for f in existing:
        m = re.match(r"^(\d+)", f.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def slugify(text: str) -> str:
    """Convert text to a kebab-case slug."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text).strip("-")


def read_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from a markdown file."""
    content = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {}, content
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm, content


def write_todo(
    todos_dir: Path,
    severity: str,
    category: str,
    description: str,
    location: str,
    proposed_solution: str,
    status: str = "pending",
) -> Path:
    """Write a todo markdown file and return its path."""
    seq = next_seq(todos_dir)
    slug = slugify(description[:60])
    filename = f"{seq:03d}-{status}-p{severity[1]}-{slug}.md"
    path = todos_dir / filename
    body = f"""---
severity: {severity}
category: {category}
status: {status}
description: {description}
location: {location}
proposed_solution: {proposed_solution}
created: {date.today().isoformat()}
---

## Finding

{description}

## Location

{location}

## Proposed Solution

{proposed_solution}
"""
    path.write_text(body, encoding="utf-8")
    return path


def action_create(args: argparse.Namespace) -> None:
    """Create a new pending todo."""
    todos_dir = get_todos_dir()
    path = write_todo(
        todos_dir,
        severity=args.severity,
        category=args.category,
        description=args.description,
        location=args.location,
        proposed_solution=args.solution,
    )
    print(f"[ce-todo] Created: {path.name}")


def action_triage(args: argparse.Namespace) -> None:
    """List pending todos and update their status interactively."""
    todos_dir = get_todos_dir()
    pending = sorted(todos_dir.glob("*-pending-*.md"), key=lambda p: p.name)
    if not pending:
        print("[ce-todo] No pending todos found.")
        return

    approved = 0
    skipped = 0
    dismissed = 0

    for path in pending:
        fm, _ = read_frontmatter(path)
        severity = fm.get("severity", "p3")
        category = fm.get("category", "unknown")
        description = fm.get("description", "")
        location = fm.get("location", "")
        proposed_solution = fm.get("proposed_solution", "")

        print(f"\n[TODO {path.name}] severity={severity}")
        print(f"Category: {category}")
        print(f"Description: {description}")
        print(f"Location: {location}")
        print(f"Proposed Solution: {proposed_solution}")

        response = args.interactive_input(path.name) if args.interactive else input(
            "  > approve? (yes/delete/next/p1/p2/p3): "
        ).strip().lower()

        if response == "yes":
            new_path = write_todo(
                todos_dir,
                severity=severity,
                category=category,
                description=description,
                location=location,
                proposed_solution=proposed_solution,
                status="ready",
            )
            path.unlink()
            print(f"  -> Approved: {new_path.name}")
            approved += 1
        elif response == "delete":
            path.unlink()
            print("  -> Dismissed.")
            dismissed += 1
        elif response in ("p1", "p2", "p3"):
            new_path = write_todo(
                todos_dir,
                severity=response,
                category=category,
                description=description,
                location=location,
                proposed_solution=proposed_solution,
                status="ready",
            )
            path.unlink()
            print(f"  -> Severity overridden to {response}, marked ready: {new_path.name}")
            approved += 1
        else:
            print("  -> Skipped.")
            skipped += 1

    print("\nTRIAGE COMPLETE")
    print("===============")
    print(f"Approved (ready): {approved}")
    print(f"Skipped (pending): {skipped}")
    print(f"Dismissed: {dismissed}")
    print(f"Total processed: {approved + skipped + dismissed}")


def action_resolve(args: argparse.Namespace) -> None:
    """Mark ready todos as complete."""
    todos_dir = get_todos_dir()
    ready = sorted(todos_dir.glob("*-ready-*.md"), key=lambda p: p.name)
    if not ready:
        print("[ce-todo] No ready todos found.")
        return

    p1_resolved = 0
    p2_resolved = 0
    p3_resolved = 0
    failed = 0

    for path in ready:
        fm, content = read_frontmatter(path)
        severity = fm.get("severity", "p3")
        category = fm.get("category", "unknown")
        description = fm.get("description", "")
        location = fm.get("location", "")
        proposed_solution = fm.get("proposed_solution", "")

        print(f"\n[RESOLVING] {path.name} — {description}")

        # In a real executor, this would delegate to ce-pr-comment-resolver or similar.
        # Here we mark as complete since resolve action signals the work is done.
        new_path = write_todo(
            todos_dir,
            severity=severity,
            category=category,
            description=description,
            location=location,
            proposed_solution=proposed_solution,
            status="complete",
        )
        path.unlink()
        print(f"  -> Resolved: {new_path.name}")

        if severity == "p1":
            p1_resolved += 1
        elif severity == "p2":
            p2_resolved += 1
        else:
            p3_resolved += 1

    print("\nRESOLUTION COMPLETE")
    print("==================")
    print(f"P1 resolved: {p1_resolved}")
    print(f"P2 resolved: {p2_resolved}")
    print(f"P3 resolved: {p3_resolved}")
    print(f"Failed: {failed}")
    print(f"Total: {p1_resolved + p2_resolved + p3_resolved}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ce-todo: Compound Engineering todo workflow")
    parser.add_argument(
        "--action",
        choices=["create", "triage", "resolve"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument("--severity", choices=["p1", "p2", "p3"], default="p2")
    parser.add_argument("--category", default="general")
    parser.add_argument("--description", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--solution", default="")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.action == "create":
        if not args.description:
            print("[ce-todo] Error: --description required for create", file=sys.stderr)
            sys.exit(1)
        action_create(args)
    elif args.action == "triage":
        action_triage(args)
    elif args.action == "resolve":
        action_resolve(args)


if __name__ == "__main__":
    main()
