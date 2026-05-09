#!/usr/bin/env python3
"""Generate INDEX.md from all README.md files in the awesome-design-md collection.

Scans .agent/tmp/awesome-design/design-md/ and produces INDEX.md in the skill root.
Output format: table with columns Name | Category | Tags | Summary
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

COLLECTION_ROOT = Path(__file__).resolve().parents[3] / "tmp" / "awesome-design" / "design-md"
SKILL_ROOT = Path(__file__).resolve().parents[2] / "design-md-collection"
INDEX_PATH = SKILL_ROOT / "INDEX.md"

# Canonical categories matching MCP/Rust parser expectations
CATEGORIES = [
    ("AI / LLM", [
        "claude", "cohere", "elevenlabs", "minimax", "mistral.ai",
        "ollama", "opencode.ai", "replicate", "runwayml", "together.ai",
        "voltagent", "x.ai",
    ]),
    ("Dev Tools / IDEs", [
        "cursor", "expo", "lovable", "raycast", "superhuman", "vercel", "warp",
    ]),
    ("Backend / DevOps", [
        "clickhouse", "ibm", "mongodb", "supabase",
    ]),
    ("Productivity / SaaS", [
        "airbnb", "airtable", "cal", "clay", "hashicorp", "intercom",
        "linear.app", "mintlify", "notion", "posthog", "semrush", "sentry",
        "spacex", "stripe", "uber", "zapier",
    ]),
    ("Diseño / Creatividad", [
        "figma", "framer", "miro", "sanity", "webflow",
    ]),
    ("Fintech / Crypto", [
        "coinbase", "kraken", "revolut", "wise",
    ]),
    ("E-commerce", []),
    ("Media / Tech", [
        "pinterest", "spotify",
    ]),
    ("Automotive", [
        "apple", "bmw", "ferrari", "lamborghini", "nvidia", "renault", "tesla",
    ]),
]


def slug_from_path(path: Path) -> str:
    return path.name


def extract_title_and_description(readme_path: Path) -> tuple[str, str]:
    """Extract title and description from a README.md."""
    try:
        text = readme_path.read_text(encoding="utf-8")
    except Exception:
        return slug_from_path(readme_path), "No description available"

    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else slug_from_path(readme_path)

    text_clean = re.sub(r"Design system details have been moved to:.*", "", text, flags=re.IGNORECASE)

    lines = text_clean.strip().split("\n")
    description = ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("[!"):
            continue
        description = line.strip()
        description = re.sub(r"\s*\[.*?\]\(.*?\)\s*", "", description)
        if description:
            break

    if not description:
        description = "Design system inspired by " + title.replace(" Inspired Design System", "")

    return title, description


def extract_tags(readme_path: Path) -> list[str]:
    """Extract visual tags from a README.md by scanning for design keywords."""
    try:
        text = readme_path.read_text(encoding="utf-8").lower()
    except Exception:
        return []

    tags: list[str] = []
    if "gradient" in text:
        tags.append("gradient")
    if "dark mode" in text or "dark-mode" in text:
        tags.append("dark-mode")
    if "monospace" in text or " mono " in text or "mono " in text or " mono" in text:
        tags.append("monospace")
    if "minimal" in text:
        tags.append("minimal")
    if "colorful" in text or "vibrant" in text:
        tags.append("colorful")
    if "glass" in text or "glassmorphism" in text:
        tags.append("glass")
    if "shadow" in text:
        tags.append("shadows")
    if "rounded" in text:
        tags.append("rounded")
    if "black" in text and "white" in text:
        tags.append("bw")

    return tags[:5]


def guess_category(design_slug: str) -> str:
    """Guess category from design slug."""
    for category, slugs in CATEGORIES:
        if design_slug in slugs:
            return category
    return "Other"


def generate_index() -> int:
    """Generate INDEX.md from all READMEs. Returns number of designs processed."""
    if not COLLECTION_ROOT.exists():
        print(f"ERROR: Collection root not found: {COLLECTION_ROOT}")
        sys.exit(1)

    designs = []

    for entry in sorted(COLLECTION_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        readme_path = entry / "README.md"
        if not readme_path.exists():
            continue

        slug = entry.name
        title, description = extract_title_and_description(readme_path)
        category = guess_category(slug)
        tags = extract_tags(readme_path)

        designs.append({
            "slug": slug,
            "title": title,
            "description": description,
            "category": category,
            "tags": tags,
        })

    header = "| Name | Category | Tags | Summary |"
    separator = "|---|---|---|---|"

    lines: list[str] = []
    lines.append("# Index of Design Systems")
    lines.append("")
    lines.append(f"Auto-generated from {len(designs)} designs in the awesome-design-md collection.")
    lines.append("")
    lines.append(header)
    lines.append(separator)

    for d in designs:
        tags_str = ", ".join(d["tags"]) if d["tags"] else ""
        desc = d["description"].replace("|", "\\|")
        lines.append(f"| `{d['slug']}` | {d['category']} | {tags_str} | {desc} |")

    INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    return len(designs)


if __name__ == "__main__":
    count = generate_index()
    print(f"Generated INDEX.md with {count} designs")
