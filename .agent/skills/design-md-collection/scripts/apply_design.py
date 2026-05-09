#!/usr/bin/env python3
"""Apply a design from the collection to a target project.

Copies DESIGN.md from the collection to a target directory.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

COLLECTION_ROOT = Path(__file__).resolve().parents[3] / "tmp" / "awesome-design" / "design-md"


def apply_design(design_slug: str, target_dir: Path, force: bool = False) -> int:
    """Copy a design's DESIGN.md to a target directory.

    Args:
        design_slug: directory name in the collection (e.g. 'figma', 'vercel')
        target_dir:  target project directory
        force:       overwrite if DESIGN.md already exists

    Returns:
        0 on success, 1 on error
    """
    collection_dir = COLLECTION_ROOT / design_slug

    if not collection_dir.exists():
        print(f"ERROR: Design '{design_slug}' not found in collection")
        print(f"  Looked in: {collection_dir}")
        sys.exit(1)

    design_md = collection_dir / "DESIGN.md"
    if not design_md.exists():
        # Fallback: README.md if no DESIGN.md exists
        readme_md = collection_dir / "README.md"
        if not readme_md.exists():
            print(f"ERROR: Neither DESIGN.md nor README.md found for '{design_slug}'")
            sys.exit(1)
        source = readme_md
        dest_name = "DESIGN.md"
    else:
        source = design_md
        dest_name = "DESIGN.md"

    target_path = target_dir / dest_name

    if target_path.exists() and not force:
        print(f"WARNING: {target_path} already exists.")
        print("  Use --force to overwrite.")
        sys.exit(1)

    shutil.copy2(source, target_path)
    print(f"Applied design '{design_slug}' -> {target_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a design system from the collection to a target project."
    )
    parser.add_argument(
        "design_slug",
        help="Design slug (directory name, e.g. figma, vercel, stripe)",
    )
    parser.add_argument(
        "target_dir",
        help="Target project directory",
        type=Path,
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing DESIGN.md",
    )
    args = parser.parse_args()

    sys.exit(apply_design(args.design_slug, args.target_dir, args.force))


if __name__ == "__main__":
    main()
