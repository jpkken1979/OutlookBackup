#!/usr/bin/env python3
"""
Performance Engineer - Performance Analyzer

Uso:
    python performance_engineer.py --file src/module.py
    python performance_engineer.py --dir src/ --output report.json
"""

import argparse
import ast
import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

PERF_PATTERNS = [
    {"pattern": r"for.*in.*range.*len", "message": "Usar enumerate()", "severity": "warning"},
    {
        "pattern": r"\+\s*=.*\+",
        "message": "String concat en loop - usar join()",
        "severity": "warning",
    },
    {"pattern": r"\bin\s+\[", "message": "List membership - usar set", "severity": "info"},
]


def analyze_performance(file_path: Path) -> list:
    """Analiza problemas de rendimiento."""
    issues = []
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        for pattern in PERF_PATTERNS:
            if re.search(pattern["pattern"], line, re.IGNORECASE):
                issues.append(
                    {
                        "file": str(file_path),
                        "line": i,
                        "severity": pattern["severity"],
                        "message": pattern["message"],
                    }
                )

    # Análisis AST
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if hasattr(node, "end_lineno"):
                    func_lines = node.end_lineno - node.lineno
                    if func_lines > 50:
                        issues.append(
                            {
                                "file": str(file_path),
                                "line": node.lineno,
                                "severity": "info",
                                "message": f"Función {node.name} muy larga ({func_lines} líneas)",
                            }
                        )
    except SyntaxError:
        pass

    return issues


def main():
    parser = argparse.ArgumentParser(description="Performance Engineer")
    parser.add_argument("--file", "-f", type=Path)
    parser.add_argument("--dir", "-d", type=Path)
    parser.add_argument("--output", "-o", type=Path)

    args = parser.parse_args()
    all_issues = []

    if args.file:
        all_issues = analyze_performance(args.file)
    elif args.dir:
        for py_file in args.dir.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                all_issues.extend(analyze_performance(py_file))
    else:
        parser.print_help()
        return

    if args.output:
        args.output.write_text(json.dumps(all_issues, indent=2))
    else:
        if all_issues:
            print(f"\n⚠ {len(all_issues)} problemas de rendimiento:\n")
            for i in all_issues:
                print(f"[{i['severity'].upper()}] {i['file']}:{i['line']}")
                print(f"  {i['message']}\n")
        else:
            print("✓ No se encontraron problemas obvios")


if __name__ == "__main__":
    main()
