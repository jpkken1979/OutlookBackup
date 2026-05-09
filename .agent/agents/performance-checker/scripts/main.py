"""performance-checker — Detecta problemas de rendimiento en el código."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    detect_languages,
    llm_summarize,
    main_wrapper,
    run_command,
)

# Directories to skip during scanning
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
    "_archive",
    ".agent - copia",
    "Compilacion",
}


def _iter_source_files(root: Path, extensions: set[str], max_files: int = 500) -> list[Path]:
    """Walk source files, skipping irrelevant directories."""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if any(fn.endswith(ext) for ext in extensions):
                files.append(Path(dirpath) / fn)
                if len(files) >= max_files:
                    return files
    return files


def _check_large_files(root: Path, extensions: set[str]) -> list[dict]:
    """Find source files over 500 lines."""
    findings: list[dict] = []
    for f in _iter_source_files(root, extensions):
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").count("\n")
            if lines > 500:
                findings.append(
                    {
                        "file": str(f.relative_to(root)),
                        "lines": lines,
                        "issue": "large_file",
                        "severity": "high" if lines > 1000 else "medium",
                    }
                )
        except OSError:
            pass
    findings.sort(key=lambda x: x["lines"], reverse=True)
    return findings[:20]


def _check_python_issues(root: Path) -> list[dict]:
    """Check Python-specific performance issues."""
    findings: list[dict] = []
    for f in _iter_source_files(root, {".py"}):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            rel = str(f.relative_to(root))

            # Too many imports
            import_count = sum(1 for l in lines[:100] if l.startswith(("import ", "from ")))
            if import_count > 20:
                findings.append(
                    {
                        "file": rel,
                        "issue": "too_many_imports",
                        "detail": f"{import_count} imports",
                        "severity": "medium",
                    }
                )

            # Global-scope heavy operations
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Heavy operations at module level (not inside def/class)
                indent = len(line) - len(line.lstrip())
                if indent == 0 and not stripped.startswith(
                    ("#", "import", "from", "def ", "class ", "@", '"""', "'''", "")
                ):
                    if re.search(r"\b(requests\.get|urlopen|subprocess\.run|open\()", stripped):
                        findings.append(
                            {
                                "file": rel,
                                "issue": "global_scope_io",
                                "detail": f"line {i + 1}: {stripped[:80]}",
                                "severity": "high",
                            }
                        )

            # Nested loops (potential O(n^2))
            for i, line in enumerate(lines):
                if re.match(r"\s+for .+ in .+:", line):
                    # Check if next for-loop is further indented
                    indent1 = len(line) - len(line.lstrip())
                    for j in range(i + 1, min(i + 15, len(lines))):
                        if re.match(r"\s+for .+ in .+:", lines[j]):
                            indent2 = len(lines[j]) - len(lines[j].lstrip())
                            if indent2 > indent1:
                                findings.append(
                                    {
                                        "file": rel,
                                        "issue": "nested_loop",
                                        "detail": f"lines {i + 1}-{j + 1}",
                                        "severity": "low",
                                    }
                                )
                                break
                        elif lines[j].strip() and not lines[j].strip().startswith("#"):
                            inner_indent = len(lines[j]) - len(lines[j].lstrip())
                            if inner_indent <= indent1:
                                break
        except OSError:
            pass
    return findings[:30]


def _check_typescript_issues(root: Path) -> list[dict]:
    """Check TypeScript/React performance issues."""
    findings: list[dict] = []
    for f in _iter_source_files(root, {".ts", ".tsx"}):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            rel = str(f.relative_to(root))

            # Too many useEffect hooks
            use_effect_count = len(re.findall(r"\buseEffect\s*\(", content))
            if use_effect_count > 4:
                findings.append(
                    {
                        "file": rel,
                        "issue": "too_many_useEffect",
                        "detail": f"{use_effect_count} useEffect hooks",
                        "severity": "high" if use_effect_count > 6 else "medium",
                    }
                )

            # Large inline objects/arrays in JSX (re-render risk)
            inline_objects = len(re.findall(r"(?:style|className)=\{\{", content))
            if inline_objects > 5:
                findings.append(
                    {
                        "file": rel,
                        "issue": "inline_style_objects",
                        "detail": f"{inline_objects} inline style/class objects",
                        "severity": "low",
                    }
                )

            # Sync I/O in async context
            if re.search(r"readFileSync|writeFileSync|execSync", content):
                findings.append(
                    {
                        "file": rel,
                        "issue": "sync_io_in_ts",
                        "detail": "synchronous I/O found",
                        "severity": "medium",
                    }
                )
        except OSError:
            pass
    return findings[:30]


def _check_large_binaries(root: Path) -> list[dict]:
    """Find large files tracked by git (>1MB)."""
    findings: list[dict] = []
    result = run_command(
        ["git", "ls-files", "-z"],
        cwd=root,
        timeout=30,
    )
    if not result["ok"]:
        return findings

    binary_exts = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".zip",
        ".tar",
        ".gz",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".woff",
        ".woff2",
        ".ttf",
        ".pdf",
        ".psd",
        ".ai",
        ".sketch",
    }

    for filepath in result["stdout"].split("\0"):
        if not filepath:
            continue
        full = root / filepath
        try:
            size = full.stat().st_size
            if size > 1_000_000:  # >1MB
                ext = Path(filepath).suffix.lower()
                findings.append(
                    {
                        "file": filepath,
                        "issue": "large_binary" if ext in binary_exts else "large_file_in_git",
                        "size_mb": round(size / 1_000_000, 2),
                        "severity": "high" if size > 10_000_000 else "medium",
                    }
                )
        except OSError:
            pass

    findings.sort(key=lambda x: x.get("size_mb", 0), reverse=True)
    return findings[:20]


def _format_findings(findings: list[dict]) -> str:
    """Format findings as readable text."""
    if not findings:
        return "No performance issues found."

    lines = ["Issue | File | Detail | Severity", "------|------|--------|--------"]
    for f in findings:
        detail = f.get("detail", f.get("size_mb", f.get("lines", "")))
        lines.append(f"{f['issue']} | {f['file']} | {detail} | {f['severity']}")
    return "\n".join(lines)


def execute(task: str, root: Path) -> dict:
    """Execute performance checks."""
    langs = detect_languages(root)
    all_findings: list[dict] = []

    # Determine extensions to scan
    extensions: set[str] = set()
    if "python" in langs:
        extensions.add(".py")
    if "typescript" in langs or "javascript" in langs:
        extensions.update({".ts", ".tsx", ".js", ".jsx"})
    if "rust" in langs:
        extensions.add(".rs")
    if not extensions:
        extensions = {".py", ".ts", ".tsx", ".js"}

    # Run checks
    large_files = _check_large_files(root, extensions)
    all_findings.extend(large_files)

    if "python" in langs:
        all_findings.extend(_check_python_issues(root))
    if "typescript" in langs or "javascript" in langs:
        all_findings.extend(_check_typescript_issues(root))

    large_binaries = _check_large_binaries(root)
    all_findings.extend(large_binaries)

    # Deduplicate by file+issue
    seen = set()
    unique: list[dict] = []
    for f in all_findings:
        key = (f["file"], f["issue"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    all_findings = unique

    raw_data = {
        "languages": langs,
        "total_findings": len(all_findings),
        "by_severity": {
            "high": sum(1 for f in all_findings if f.get("severity") == "high"),
            "medium": sum(1 for f in all_findings if f.get("severity") == "medium"),
            "low": sum(1 for f in all_findings if f.get("severity") == "low"),
        },
        "findings": all_findings,
    }

    table = _format_findings(all_findings)
    llm_result = llm_summarize(
        table,
        "Eres un experto en rendimiento de software. Analiza estos hallazgos de rendimiento. "
        "Prioriza las mejoras más impactantes. Sugiere acciones concretas. "
        "Responde en español, conciso.",
    )

    if llm_result:
        return {"status": "success", "summary": llm_result, "raw": raw_data, "llm_used": "auto"}

    fallback = (
        f"Performance Check — {len(all_findings)} issues encontrados "
        f"({raw_data['by_severity']['high']} high, "
        f"{raw_data['by_severity']['medium']} medium, "
        f"{raw_data['by_severity']['low']} low)\n\n{table}"
    )
    return {"status": "success", "summary": fallback, "raw": raw_data, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("performance-checker", execute)
