"""file-organizer — Encuentra archivos duplicados, temporales y candidatos a limpieza."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    llm_summarize,
    main_wrapper,
    run_command,
)

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
}

TEMP_PATTERNS = {
    "*.bak",
    "*.tmp",
    "*.orig",
    "*~",
    "*.swp",
    "*.swo",
    "*.bak.*",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
}


def _find_duplicates(root: Path) -> list[dict]:
    """Find files with the same name in different directories."""
    name_map: dict[str, list[str]] = defaultdict(list)
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            full = Path(dirpath) / fn
            try:
                rel = str(full.relative_to(root))
            except ValueError:
                rel = str(full)
            name_map[fn].append(rel)
            count += 1
            if count > 10000:
                break
        if count > 10000:
            break

    duplicates: list[dict] = []
    for name, paths in name_map.items():
        if len(paths) > 1:
            # Skip common legitimate duplicates
            if name in {
                "__init__.py",
                "index.ts",
                "index.js",
                "README.md",
                "package.json",
                "tsconfig.json",
                "mod.rs",
                "main.rs",
                ".gitignore",
                "Cargo.toml",
            }:
                continue
            duplicates.append(
                {
                    "name": name,
                    "count": len(paths),
                    "paths": paths[:5],
                    "category": "duplicate",
                }
            )
    duplicates.sort(key=lambda x: x["count"], reverse=True)
    return duplicates[:20]


def _find_temp_files(root: Path) -> list[dict]:
    """Find temporary and backup files."""
    findings: list[dict] = []
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            is_temp = False
            for pat in TEMP_PATTERNS:
                if pat.startswith("*"):
                    if fn.endswith(pat[1:]) or fn == pat[1:]:
                        is_temp = True
                        break
                elif fn == pat:
                    is_temp = True
                    break
            # Also check for tilde and .orig suffix
            if fn.endswith("~") or fn.endswith(".orig") or fn.endswith(".swp"):
                is_temp = True

            if is_temp:
                full = Path(dirpath) / fn
                try:
                    size = full.stat().st_size
                    rel = str(full.relative_to(root))
                except (OSError, ValueError):
                    continue
                total_size += size
                findings.append(
                    {
                        "file": rel,
                        "size_kb": round(size / 1024, 1),
                        "category": "temp_file",
                    }
                )
    findings.sort(key=lambda x: x["size_kb"], reverse=True)
    return findings[:30]


def _find_large_files(root: Path, threshold_mb: float = 5.0) -> list[dict]:
    """Find large files that might not belong in the repo."""
    findings: list[dict] = []
    threshold = int(threshold_mb * 1_000_000)

    # Use git ls-files to check tracked files
    result = run_command(["git", "ls-files", "-z"], cwd=root, timeout=30)
    if result["ok"]:
        for filepath in result["stdout"].split("\0"):
            if not filepath:
                continue
            full = root / filepath
            try:
                size = full.stat().st_size
                if size > threshold:
                    findings.append(
                        {
                            "file": filepath,
                            "size_mb": round(size / 1_000_000, 2),
                            "category": "large_file",
                        }
                    )
            except OSError:
                pass
    else:
        # Fallback: walk filesystem
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                full = Path(dirpath) / fn
                try:
                    size = full.stat().st_size
                    if size > threshold:
                        findings.append(
                            {
                                "file": str(full.relative_to(root)),
                                "size_mb": round(size / 1_000_000, 2),
                                "category": "large_file",
                            }
                        )
                except OSError:
                    pass

    findings.sort(key=lambda x: x["size_mb"], reverse=True)
    return findings[:20]


def _find_empty_dirs(root: Path) -> list[dict]:
    """Find empty directories."""
    findings: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        dp = Path(dirpath)
        try:
            contents = list(dp.iterdir())
            if not contents:
                findings.append(
                    {
                        "dir": str(dp.relative_to(root)),
                        "category": "empty_dir",
                    }
                )
        except (OSError, ValueError):
            pass
    return findings[:20]


def _find_untracked_files(root: Path) -> list[dict]:
    """Find untracked files (not ignored by git)."""
    result = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        timeout=30,
    )
    if not result["ok"]:
        return []

    findings: list[dict] = []
    total_size = 0
    for filepath in result["stdout"].strip().split("\n"):
        filepath = filepath.strip()
        if not filepath:
            continue
        full = root / filepath
        try:
            size = full.stat().st_size
        except OSError:
            size = 0
        total_size += size
        findings.append(
            {
                "file": filepath,
                "size_kb": round(size / 1024, 1),
                "category": "untracked",
            }
        )

    findings.sort(key=lambda x: x["size_kb"], reverse=True)
    return findings[:30]


def _format_findings(categories: dict[str, list[dict]]) -> str:
    """Format findings by category."""
    lines: list[str] = []
    for cat, items in categories.items():
        if not items:
            continue
        lines.append(f"\n## {cat.upper()} ({len(items)} found)")
        for item in items[:10]:
            if "paths" in item:
                lines.append(
                    f"  - {item['name']} ({item['count']}x): {', '.join(item['paths'][:3])}"
                )
            elif "size_mb" in item:
                lines.append(f"  - {item['file']} ({item['size_mb']} MB)")
            elif "size_kb" in item:
                lines.append(f"  - {item['file']} ({item['size_kb']} KB)")
            elif "dir" in item:
                lines.append(f"  - {item['dir']}/")
            else:
                lines.append(f"  - {item.get('file', item.get('name', '?'))}")
    return "\n".join(lines) if lines else "No cleanup candidates found."


def execute(task: str, root: Path) -> dict:
    """Execute file organization analysis."""
    duplicates = _find_duplicates(root)
    temp_files = _find_temp_files(root)
    large_files = _find_large_files(root)
    empty_dirs = _find_empty_dirs(root)
    untracked = _find_untracked_files(root)

    categories = {
        "duplicates": duplicates,
        "temp_files": temp_files,
        "large_files": large_files,
        "empty_dirs": empty_dirs,
        "untracked": untracked,
    }

    total_findings = sum(len(v) for v in categories.values())
    potential_savings_mb = sum(f.get("size_mb", 0) for f in large_files) + sum(
        f.get("size_kb", 0) / 1024 for f in temp_files
    )

    raw_data = {
        "total_findings": total_findings,
        "potential_savings_mb": round(potential_savings_mb, 2),
        "by_category": {k: len(v) for k, v in categories.items()},
        "findings": categories,
    }

    text = _format_findings(categories)
    llm_result = llm_summarize(
        text,
        "Eres un experto en DevOps. Analiza estos hallazgos de organización de archivos. "
        "Recomienda qué es SEGURO eliminar vs qué revisar primero. "
        "Calcula el ahorro potencial. Responde en español, conciso.",
    )

    if llm_result:
        return {"status": "success", "summary": llm_result, "raw": raw_data, "llm_used": "auto"}

    fallback = (
        f"File Organizer — {total_findings} hallazgos, "
        f"~{raw_data['potential_savings_mb']} MB recuperables\n{text}"
    )
    return {"status": "success", "summary": fallback, "raw": raw_data, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("file-organizer", execute)
