"""doc-generator — Genera documentacion para funciones y clases sin docstrings."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (
    detect_languages,
    llm_summarize,
    main_wrapper,
)

AGENT_NAME = "doc-generator"

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
    ".cache",
    "_archive",
}


def _iter_files(root: Path, extensions: set[str]) -> list[Path]:
    """Walk tree collecting files, skipping heavy dirs."""
    results: list[Path] = []
    try:
        for item in root.iterdir():
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            if item.is_dir():
                results.extend(_iter_files(item, extensions))
            elif item.suffix in extensions and item.is_file():
                results.append(item)
    except (PermissionError, OSError):
        pass
    return results


def _scan_python(root: Path) -> tuple[list[dict], int, int]:
    """Scan Python files for undocumented functions/classes using AST.

    Returns:
        (undocumented_items, total_documented, total_items)
    """
    py_files = _iter_files(root, {".py"})
    undocumented: list[dict] = []
    total_documented = 0
    total_items = 0

    for fpath in py_files[:300]:  # limit to avoid timeout
        try:
            source = fpath.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(fpath))
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

        rel_path = str(fpath.relative_to(root))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private/dunder methods (less important)
                if node.name.startswith("_") and not node.name.startswith("__"):
                    continue
                total_items += 1
                docstring = ast.get_docstring(node)
                if not docstring:
                    undocumented.append(
                        {
                            "file": rel_path,
                            "line": node.lineno,
                            "type": "function",
                            "name": node.name,
                            "args": [
                                a.arg for a in node.args.args if a.arg != "self" and a.arg != "cls"
                            ],
                            "is_async": isinstance(node, ast.AsyncFunctionDef),
                        }
                    )
                else:
                    total_documented += 1

            elif isinstance(node, ast.ClassDef):
                total_items += 1
                docstring = ast.get_docstring(node)
                if not docstring:
                    # Get method names for context
                    methods = [
                        n.name
                        for n in ast.iter_child_nodes(node)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    undocumented.append(
                        {
                            "file": rel_path,
                            "line": node.lineno,
                            "type": "class",
                            "name": node.name,
                            "methods": methods[:10],
                        }
                    )
                else:
                    total_documented += 1

    return undocumented, total_documented, total_items


def _scan_typescript(root: Path) -> tuple[list[dict], int, int]:
    """Scan TypeScript files for exported functions without JSDoc.

    Returns:
        (undocumented_items, total_documented, total_items)
    """
    ts_files = _iter_files(root, {".ts", ".tsx"})
    undocumented: list[dict] = []
    total_documented = 0
    total_items = 0

    # Patterns for exported items
    export_patterns = [
        # export function name(
        re.compile(r"^export\s+(?:async\s+)?function\s+(\w+)\s*\("),
        # export const name =
        re.compile(r"^export\s+const\s+(\w+)\s*="),
        # export class name
        re.compile(r"^export\s+class\s+(\w+)"),
        # export interface name
        re.compile(r"^export\s+interface\s+(\w+)"),
    ]

    for fpath in ts_files[:300]:  # limit
        try:
            lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
        except (OSError, PermissionError):
            continue

        rel_path = str(fpath.relative_to(root))

        for i, line in enumerate(lines):
            for pat in export_patterns:
                match = pat.match(line.strip())
                if match:
                    name = match.group(1)
                    total_items += 1

                    # Check if previous non-empty line ends with */
                    has_jsdoc = False
                    for j in range(i - 1, max(i - 5, -1), -1):
                        prev = lines[j].strip()
                        if prev:
                            if prev.endswith("*/"):
                                has_jsdoc = True
                            break

                    if has_jsdoc:
                        total_documented += 1
                    else:
                        item_type = "function"
                        if "class " in line:
                            item_type = "class"
                        elif "interface " in line:
                            item_type = "interface"
                        elif "const " in line:
                            item_type = "constant"

                        undocumented.append(
                            {
                                "file": rel_path,
                                "line": i + 1,
                                "type": item_type,
                                "name": name,
                            }
                        )
                    break  # only match first pattern per line

    return undocumented, total_documented, total_items


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    all_undocumented: list[dict] = []
    total_documented = 0
    total_items = 0
    lang_stats: dict[str, dict] = {}

    # Python scan
    if "python" in languages:
        py_undoc, py_doc, py_total = _scan_python(root)
        all_undocumented.extend(py_undoc)
        total_documented += py_doc
        total_items += py_total
        lang_stats["python"] = {
            "undocumented": len(py_undoc),
            "documented": py_doc,
            "total": py_total,
            "coverage_pct": round(py_doc / py_total * 100, 1) if py_total else 100,
        }

    # TypeScript scan
    if "typescript" in languages:
        ts_undoc, ts_doc, ts_total = _scan_typescript(root)
        all_undocumented.extend(ts_undoc)
        total_documented += ts_doc
        total_items += ts_total
        lang_stats["typescript"] = {
            "undocumented": len(ts_undoc),
            "documented": ts_doc,
            "total": ts_total,
            "coverage_pct": round(ts_doc / ts_total * 100, 1) if ts_total else 100,
        }

    total_undoc = len(all_undocumented)
    coverage_pct = round(total_documented / total_items * 100, 1) if total_items else 100

    raw = {
        "total_items": total_items,
        "total_documented": total_documented,
        "total_undocumented": total_undoc,
        "coverage_pct": coverage_pct,
        "languages": languages,
        "lang_stats": lang_stats,
        "undocumented_items": all_undocumented[:100],  # limit output
    }

    # LLM: generate docstring suggestions for top 10
    top_items = all_undocumented[:10]
    items_detail = ""
    for item in top_items:
        # Read a few lines of source for context
        fpath = root / item["file"]
        context_lines = ""
        try:
            lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
            start = max(0, item["line"] - 1)
            end = min(len(lines), start + 8)
            context_lines = "\n".join(lines[start:end])
        except (OSError, PermissionError):
            pass

        items_detail += (
            f"\n--- {item['file']}:{item['line']} [{item['type']}] {item['name']} ---\n"
            f"{context_lines}\n"
        )

    data_for_llm = (
        f"Cobertura de documentacion: {coverage_pct}% ({total_documented}/{total_items})\n"
        f"Items sin documentar: {total_undoc}\n"
        f"Por lenguaje: {lang_stats}\n\n"
        f"Top 10 items sin documentar (con contexto de codigo):\n{items_detail}"
    )

    prompt = (
        "Genera docstrings/JSDoc sugeridos para los items listados. "
        "Para Python usa formato Google docstring. "
        "Para TypeScript usa formato JSDoc. "
        "Tambien da un resumen de la cobertura y recomendaciones. "
        "Responde en español para el resumen, pero los docstrings en ingles."
    )

    summary = llm_summarize(data_for_llm, prompt, max_tokens=1500)
    llm_used = "auto"

    if not summary:
        llm_used = "none"
        summary = (
            f"Cobertura de documentacion: {coverage_pct}% ({total_documented}/{total_items})\n"
            f"Items sin documentar: {total_undoc}\n\n"
        )
        for lang, stats in lang_stats.items():
            summary += (
                f"  {lang}: {stats['coverage_pct']}% ({stats['documented']}/{stats['total']})\n"
            )

        summary += "\nTop items sin documentar:\n"
        for item in all_undocumented[:15]:
            args_str = ""
            if "args" in item and item["args"]:
                args_str = f"({', '.join(item['args'])})"
            summary += (
                f"  - {item['file']}:{item['line']} [{item['type']}] {item['name']}{args_str}\n"
            )

    status = "success" if coverage_pct >= 50 else "warning"

    return {
        "status": status,
        "summary": summary,
        "raw": raw,
        "llm_used": llm_used,
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)
