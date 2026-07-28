#!/usr/bin/env python3
"""Archive stub skills (directories in skills/ or skills-custom/ that lack a scripts/ folder or active code)."""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = REPO_ROOT / ".agent" / "skills"
SKILLS_CUSTOM_DIR = REPO_ROOT / ".agent" / "skills-custom"


def archive_stubs_in_dir(target_dir: Path) -> None:
    if not target_dir.exists():
        return

    archive_dir = target_dir / "_archive_stubs"
    archive_dir.mkdir(exist_ok=True)

    print(f"\nScanning stubs in: {target_dir.name}/")

    stubs_count = 0
    for path in target_dir.iterdir():
        if not path.is_dir():
            continue

        # Skip special/archived directories
        if path.name.startswith("_") or path.name.startswith("."):
            continue

        scripts_dir = path / "scripts"
        has_scripts = scripts_dir.exists() and any(scripts_dir.iterdir())

        # If it has no scripts/ directory or scripts directory is empty, it is a stub
        if not has_scripts:
            dst = archive_dir / path.name
            print(f"  [ARCHIVING] {path.name}/ -> _archive_stubs/{path.name}/")
            try:
                shutil.move(str(path), str(dst))
                stubs_count += 1
            except Exception as e:
                print(f"  [ERROR] Could not move {path.name}: {e}")

    print(f"Archived {stubs_count} stub skills in {target_dir.name}/")


def main():
    archive_stubs_in_dir(SKILLS_DIR)
    archive_stubs_in_dir(SKILLS_CUSTOM_DIR)
    print("\nWorkspace skills decluttered successfully.")


if __name__ == "__main__":
    main()
