#!/usr/bin/env python3
"""Regenerate skills inventory and update documentation.

Scans .agent/skills/ and .agent/skills-custom/ to build INVENTORY.md
and update the skill count in INDEX.md.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]  # repo root
SKILLS_DIR = REPO_ROOT / ".agent" / "skills"
CUSTOM_DIR = REPO_ROOT / ".agent" / "skills-custom"
INVENTORY_PATH = SKILLS_DIR / "INVENTORY.md"
README_PATH = SKILLS_DIR / "README.md"

SKIP_PREFIXES = ("_", ".")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from a markdown file.

    Returns:
        (frontmatter_dict, body_text)
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    raw_yaml = match.group(1)
    body = match.group(2)
    fm: dict[str, str] = {}
    for line in raw_yaml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ": " in line:
            key, _, val = line.partition(": ")
            fm[key.strip()] = val.strip().strip('"').strip("'")
        elif ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body


def scan_skill_dir(skill_path: Path) -> dict:
    """Scan a skill directory and return structured info."""
    name = skill_path.name
    skill_md = skill_path / "SKILL.md"
    has_scripts = (skill_path / "scripts").is_dir()
    has_readme = (skill_path / "README.md").is_file()

    description = ""
    if skill_md.exists():
        try:
            text = skill_md.read_text(encoding="utf-8")
            fm, _ = extract_frontmatter(text)
            description = fm.get("description", "").strip()
            if not description:
                # Fallback: first non-heading line of body
                body_lines = text.splitlines()
                for line in body_lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        description = stripped
                        break
        except Exception as e:
            logger.warning("Failed to read %s: %s", skill_md, e)

    if not description:
        description = "(no description)"

    return {
        "name": name,
        "description": description,
        "has_scripts": has_scripts,
        "has_readme": has_readme,
    }


def scan_directory(base_dir: Path, skip_prefixes: tuple[str, ...]) -> list[dict]:
    """Scan a skills directory and return list of skill info dicts."""
    if not base_dir.is_dir():
        logger.warning("Directory not found: %s", base_dir)
        return []

    results: list[dict] = []
    entries = sorted(base_dir.iterdir(), key=lambda p: p.name.lower())
    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name.startswith(skip_prefixes):
            logger.debug("Skipping %s (prefix)", entry.name)
            continue
        try:
            info = scan_skill_dir(entry)
            results.append(info)
        except Exception as e:
            logger.warning("Error scanning %s: %s", entry, e)
    return results


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_table(entries: list[dict]) -> str:
    """Format a markdown table from skill entries."""
    header = (
        "| Skill | Description | Has Scripts | Has README |\n"
        "|--------|-------------|-------------|------------|\n"
    )
    rows = []
    for e in entries:
        desc = e["description"]
        # truncate very long descriptions for the table
        if len(desc) > 90:
            desc = desc[:87] + "..."
        # Escape pipe chars in description
        desc = desc.replace("|", "\\|")
        rows.append(
            f"| `{e['name']}` | {desc} | "
            f"{'Y' if e['has_scripts'] else 'N'} | "
            f"{'Y' if e['has_readme'] else 'N'} |"
        )
    return header + "\n".join(rows)


def build_inventory(
    main_entries: list[dict],
    custom_entries: list[dict],
    today: date,
) -> str:
    """Build the INVENTORY.md content."""
    total = len(main_entries) + len(custom_entries)
    main_count = len(main_entries)
    custom_count = len(custom_entries)

    lines: list[str] = []
    lines.append(f"# Skills Inventory — Updated {today.isoformat()}\n")
    lines.append(f"Total: {total} skills ({main_count} main + {custom_count} custom)\n")
    lines.append("## Summary\n")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| main | {main_count} |")
    lines.append(f"| custom | {custom_count} |\n")
    lines.append("## Main Skills\n")
    lines.append(format_table(main_entries))
    lines.append("\n## Custom Skills\n")
    lines.append(format_table(custom_entries))
    return "\n".join(lines)


def update_index(readme_path: Path, total: int, today: date) -> None:
    """Update skill count in README.md."""
    if not readme_path.exists():
        logger.warning("README.md not found at %s, skipping update", readme_path)
        return

    try:
        text = readme_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read README.md: %s", e)
        return

    # Replace the count line — match patterns like:
    # "This is where all 179+ specialized AI skills live."
    # "This is where all NNN skills live."
    updated = re.sub(
        r"(This is where all )\d+(\+? specialized AI skills live\.)",
        rf"\g<1>{total}\g<2>",
        text,
    )
    if updated == text:
        logger.warning("Could not find skill count line in README.md — manual update needed")
    else:
        readme_path.write_text(updated, encoding="utf-8")
        logger.info("Updated README.md count to %d", total)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("Scanning main skills in %s", SKILLS_DIR)
    main_entries = scan_directory(SKILLS_DIR, SKIP_PREFIXES)
    logger.info("Found %d main skills", len(main_entries))

    logger.info("Scanning custom skills in %s", CUSTOM_DIR)
    custom_entries = scan_directory(CUSTOM_DIR, SKIP_PREFIXES)
    logger.info("Found %d custom skills", len(custom_entries))

    total = len(main_entries) + len(custom_entries)
    today = date.today()

    inventory_content = build_inventory(main_entries, custom_entries, today)
    INVENTORY_PATH.write_text(inventory_content, encoding="utf-8")
    logger.info("Written %s", INVENTORY_PATH)

    update_index(README_PATH, total, today)

    # Quick summary for stdout
    print("\n=== Skills Inventory Summary ===")
    print(f"Main skills:    {len(main_entries)}")
    print(f"Custom skills:  {len(custom_entries)}")
    print(f"Total skills:   {total}")
    print(f"INVENTORY.md:   {INVENTORY_PATH}")
    print("README.md:      updated")


if __name__ == "__main__":
    main()
