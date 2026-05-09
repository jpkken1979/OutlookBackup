"""dead-code-finder — Encuentra codigo muerto e imports sin usar."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (
    detect_languages,
    llm_summarize,
    main_wrapper,
    run_command,
)

AGENT_NAME = "dead-code-finder"

# Directories to skip when scanning
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    ".next",
    ".nuxt",
}


def _iter_files(root: Path, extensions: set[str]) -> list[Path]:
    """Walk the tree collecting files, skipping heavy dirs."""
    results: list[Path] = []
    for item in root.iterdir():
        if item.name in SKIP_DIRS or item.name.startswith("."):
            continue
        if item.is_dir():
            results.extend(_iter_files(item, extensions))
        elif item.suffix in extensions:
            results.append(item)
    return results


def _run_vulture(root: Path) -> list[dict]:
    """Run vulture and parse output."""
    result = run_command(["python", "-m", "vulture", "."], cwd=root, timeout=120)
    findings: list[dict] = []
    if result["stdout"]:
        for line in result["stdout"].strip().splitlines():
            # Format: file.py:10: unused function 'foo' (60% confidence)
            match = re.match(
                r"(.+?):(\d+):\s+unused\s+(function|import|variable|class|attribute|property)\s+'(.+?)'\s+\((\d+)%",
                line,
            )
            if match:
                findings.append(
                    {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "type": f"unused_{match.group(3)}",
                        "name": match.group(4),
                        "confidence": int(match.group(5)),
                    }
                )
            else:
                # Catch generic lines
                generic = re.match(r"(.+?):(\d+):\s+(.+)", line)
                if generic:
                    findings.append(
                        {
                            "file": generic.group(1),
                            "line": int(generic.group(2)),
                            "type": "unused_other",
                            "name": generic.group(3),
                            "confidence": 0,
                        }
                    )
    return findings


def _run_ts_prune(root: Path) -> list[dict]:
    """Run ts-prune and parse output."""
    result = run_command(["npx", "-y", "ts-prune"], cwd=root, timeout=120)
    findings: list[dict] = []
    if result["stdout"]:
        for line in result["stdout"].strip().splitlines():
            # Format: src/file.ts:10 - exportName
            match = re.match(r"(.+?):(\d+)\s+-\s+(.+)", line)
            if match:
                name = match.group(3).strip()
                if name == "default":
                    continue  # default exports are often used dynamically
                findings.append(
                    {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "type": "unused_export",
                        "name": name,
                        "confidence": 70,
                    }
                )
    return findings


def _find_debt_markers(root: Path) -> list[dict]:
    """Grep for TODO, FIXME, HACK markers."""
    markers: list[dict] = []
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs"}
    files = _iter_files(root, extensions)

    for fpath in files[:500]:  # limit to avoid timeout
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for i, line in enumerate(content.splitlines(), 1):
            for tag in ("TODO", "FIXME", "HACK"):
                if f"# {tag}" in line or f"// {tag}" in line:
                    markers.append(
                        {
                            "file": str(fpath.relative_to(root)),
                            "line": i,
                            "type": f"marker_{tag.lower()}",
                            "name": line.strip()[:120],
                            "confidence": 100,
                        }
                    )
                    break  # one marker per line
    return markers


def _count_by_type(findings: list[dict]) -> dict[str, int]:
    """Count findings by type."""
    counts: dict[str, int] = {}
    for f in findings:
        t = f["type"]
        counts[t] = counts.get(t, 0) + 1
    return counts


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    all_findings: list[dict] = []
    tool_results: dict[str, str] = {}

    # Python: vulture
    if "python" in languages:
        py_files = _iter_files(root, {".py"})
        if py_files:
            vulture = _run_vulture(root)
            all_findings.extend(vulture)
            tool_results["vulture"] = f"{len(vulture)} findings"

    # TypeScript: ts-prune
    if "typescript" in languages:
        tsconfigs = list(root.rglob("tsconfig.json"))
        tsconfigs = [t for t in tsconfigs if "node_modules" not in str(t)]
        if tsconfigs:
            ts_findings = _run_ts_prune(root)
            all_findings.extend(ts_findings)
            tool_results["ts-prune"] = f"{len(ts_findings)} findings"

    # Debt markers
    debt = _find_debt_markers(root)
    all_findings.extend(debt)
    tool_results["debt_markers"] = f"{len(debt)} markers"

    counts = _count_by_type(all_findings)
    total = len(all_findings)

    # Build raw data
    raw = {
        "total_findings": total,
        "counts_by_type": counts,
        "tools_run": tool_results,
        "languages_detected": languages,
        "top_findings": all_findings[:50],  # limit for output size
    }

    # LLM summary
    data_for_llm = f"Total findings: {total}\nBy type: {counts}\n\nSample findings (first 30):\n"
    for f in all_findings[:30]:
        data_for_llm += (
            f"  {f['file']}:{f['line']} [{f['type']}] {f['name']} ({f['confidence']}% confidence)\n"
        )

    prompt = (
        "Analiza estos hallazgos de codigo muerto e imports sin usar. "
        "Clasifica cuales son seguros de eliminar vs cuales podrian usarse dinamicamente "
        "(ej: callbacks, plugins, __getattr__, decoradores). "
        "Resume en español con recomendaciones concretas."
    )

    summary = llm_summarize(data_for_llm, prompt)
    llm_used = "auto"

    if not summary:
        llm_used = "none"
        summary = f"Encontrados {total} hallazgos de codigo muerto.\n"
        summary += f"Desglose: {', '.join(f'{k}: {v}' for k, v in sorted(counts.items()))}\n"
        if all_findings:
            summary += "\nTop hallazgos:\n"
            for f in all_findings[:15]:
                summary += f"  - {f['file']}:{f['line']} [{f['type']}] {f['name']}\n"

    status = "success" if total < 50 else "warning"

    return {
        "status": status,
        "summary": summary,
        "raw": raw,
        "llm_used": llm_used,
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)
