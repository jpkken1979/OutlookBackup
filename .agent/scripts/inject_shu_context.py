#!/usr/bin/env python3
"""Inject --shu-context argument into agent scripts/main.py files (idempotent)."""

import ast
import sys
from pathlib import Path


def has_shu_context(file_path: Path) -> bool:
    """Check if file already has shu-context argument."""
    try:
        content = file_path.read_text(encoding="utf-8")
        return "shu-context" in content or "shu_context" in content
    except Exception:
        return False


def inject_shu_context(file_path: Path) -> bool:
    """
    Inject --shu-context argument into main.py.
    Returns True if injection succeeded, False if skipped or failed.
    """
    # Skip if already has shu-context
    if has_shu_context(file_path):
        return False

    try:
        content = file_path.read_text(encoding="utf-8")

        # Safety check: file must have argparse pattern
        if "parser.add_argument" not in content:
            return False

        # Safety check: parse as valid Python
        try:
            ast.parse(content)
        except SyntaxError:
            return False

        # Find the last parser.add_argument and inject after it
        lines = content.split("\n")
        last_parser_idx = -1

        for i in range(len(lines) - 1, -1, -1):
            if "parser.add_argument" in lines[i]:
                last_parser_idx = i
                break

        if last_parser_idx == -1:
            return False

        # Find the closing parenthesis of that argument (handle multi-line)
        j = last_parser_idx
        paren_count = lines[j].count("(") - lines[j].count(")")

        while j < len(lines) - 1 and paren_count > 0:
            j += 1
            paren_count += lines[j].count("(") - lines[j].count(")")

        # Inject the new argument after the last one
        injection = "    parser.add_argument('--shu-context', type=str, default=None, help='Captured SHU context file path')"
        lines.insert(j + 1, injection)

        new_content = "\n".join(lines)
        file_path.write_text(new_content, encoding="utf-8")
        return True

    except Exception as e:
        print(f"ERROR in {file_path}: {e}", file=sys.stderr)
        return False


def main() -> None:
    """Scan all agents and inject shu-context."""
    repo_root = Path(__file__).parent.parent.parent
    agents_dir = repo_root / ".agent" / "agents"

    if not agents_dir.exists():
        print(f"ERROR: agents directory not found at {agents_dir}")
        sys.exit(1)

    # Find all main.py files in scripts/ subdirs
    main_files = sorted(agents_dir.glob("*/scripts/main.py"))

    if not main_files:
        print(f"ERROR: no main.py files found in {agents_dir}")
        sys.exit(1)

    print(f"Found {len(main_files)} agent main.py files")

    skipped = 0  # Already had shu-context
    injected = 0  # Successfully injected
    failed = 0  # Failed to inject
    errors = []

    for main_file in main_files:
        agent_name = main_file.parent.parent.name

        if has_shu_context(main_file):
            print(f"  {agent_name:40s} [SKIP - already has shu-context]")
            skipped += 1
        elif inject_shu_context(main_file):
            print(f"  {agent_name:40s} [OK - injected]")
            injected += 1
        else:
            print(f"  {agent_name:40s} [FAIL - could not inject]")
            failed += 1
            errors.append(agent_name)

    print("\n=== SUMMARY ===")
    print(f"Total agents: {len(main_files)}")
    print(f"Injected: {injected}")
    print(f"Skipped (already had): {skipped}")
    print(f"Failed: {failed}")

    if errors:
        print(f"\nFailed agents: {', '.join(errors)}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
