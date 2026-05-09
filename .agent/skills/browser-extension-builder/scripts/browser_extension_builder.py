#!/usr/bin/env python3
"""
Browser Extension Builder - Frontend Analyzer

Uso:
    python browser_extension_builder.py --check-a11y src/
    python browser_extension_builder.py --check-perf public/
"""

import argparse
import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

A11Y_RULES = [
    {"pattern": r"<img[^>]*(?!alt=)[^>]*>", "message": "Imagen sin alt", "wcag": "1.1.1"},
    {"pattern": r"<a[^>]*>\s*</a>", "message": "Enlace vacío", "wcag": "2.4.4"},
    {"pattern": r"onClick=[^>]*(?!onKeyDown)", "message": "onClick sin keyboard", "wcag": "2.1.1"},
]


def check_accessibility(file_path: Path) -> list:
    """Verifica accesibilidad."""
    issues = []
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        for rule in A11Y_RULES:
            if re.search(rule["pattern"], line):
                issues.append(
                    {
                        "file": str(file_path),
                        "line": i,
                        "message": rule["message"],
                        "wcag": rule["wcag"],
                    }
                )

    return issues


def check_performance(file_path: Path) -> list:
    """Verifica problemas de rendimiento."""
    issues = []
    content = file_path.read_text(encoding="utf-8")

    size_kb = len(content.encode("utf-8")) / 1024
    if size_kb > 100:
        issues.append(
            {"message": f"Archivo grande: {size_kb:.1f} KB", "suggestion": "Code splitting"}
        )

    large_deps = [("moment", "date-fns"), ("lodash", "lodash-es"), ("jquery", "vanilla JS")]
    for dep, alt in large_deps:
        if re.search(f"import.*['\"']{dep}", content):
            issues.append({"message": f"Dependencia pesada: {dep}", "suggestion": f"Usar {alt}"})

    return issues


def main():
    parser = argparse.ArgumentParser(description="Browser Extension Builder")
    parser.add_argument("--check-a11y", type=Path)
    parser.add_argument("--check-perf", type=Path)
    parser.add_argument("--output", "-o", type=Path)

    args = parser.parse_args()
    all_issues = []

    if args.check_a11y:
        for f in args.check_a11y.rglob("*.tsx"):
            if "node_modules" not in str(f):
                all_issues.extend(check_accessibility(f))
        for f in args.check_a11y.rglob("*.jsx"):
            if "node_modules" not in str(f):
                all_issues.extend(check_accessibility(f))

        if all_issues:
            print(f"\n⚠ {len(all_issues)} problemas de accesibilidad:")
            for i in all_issues[:20]:
                print(f"  {i['file']}:{i['line']} - {i['message']} (WCAG {i['wcag']})")
        else:
            print("✓ Sin problemas de accesibilidad")

    elif args.check_perf:
        for f in args.check_perf.rglob("*.js"):
            if "node_modules" not in str(f):
                all_issues.extend(check_performance(f))

        if all_issues:
            print(f"\n⚠ {len(all_issues)} problemas de rendimiento:")
            for i in all_issues:
                print(f"  {i['message']}")
                if "suggestion" in i:
                    print(f"    → {i['suggestion']}")
    else:
        parser.print_help()

    if args.output:
        args.output.write_text(json.dumps(all_issues, indent=2, default=str))


if __name__ == "__main__":
    main()
