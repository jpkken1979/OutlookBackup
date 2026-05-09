#!/usr/bin/env python3
"""
Auth Implementation Patterns - Security Scanner

Uso:
    python auth_implementation_patterns.py --file src/app.py
    python auth_implementation_patterns.py --dir src/ --output report.json
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

SECURITY_PATTERNS = {
    "hardcoded-secret": {
        "pattern": r"(password|secret|api_key|token)\s*=\s*[\"\']((?!\{\{).+?)[\"\']",
        "severity": "critical",
        "message": "Posible secreto hardcodeado",
    },
    "sql-injection": {
        "pattern": r"(execute|query)\s*\(\s*f[\"\']",
        "severity": "critical",
        "message": "Posible SQL injection",
    },
    "eval-usage": {
        "pattern": r"\beval\s*\(",
        "severity": "high",
        "message": "Uso de eval() detectado",
    },
    "exec-usage": {
        "pattern": r"\bexec\s*\(",
        "severity": "high",
        "message": "Uso de exec() detectado",
    },
    "subprocess-shell": {
        "pattern": r"subprocess.*shell\s*=\s*True",
        "severity": "high",
        "message": "Subprocess con shell=True",
    },
}


def scan_file(file_path: Path) -> list:
    """Escanea un archivo en busca de vulnerabilidades."""
    issues = []
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    for rule_name, rule in SECURITY_PATTERNS.items():
        for i, line in enumerate(lines, 1):
            if re.search(rule["pattern"], line, re.IGNORECASE):
                issues.append(
                    {
                        "rule": rule_name,
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "file": str(file_path),
                        "line": i,
                    }
                )

    return issues


def main():
    parser = argparse.ArgumentParser(description="Auth Implementation Patterns")
    parser.add_argument("--file", "-f", type=Path, help="Archivo a escanear")
    parser.add_argument("--dir", "-d", type=Path, help="Directorio a escanear")
    parser.add_argument("--output", "-o", type=Path, help="Archivo de salida JSON")

    args = parser.parse_args()
    all_issues = []

    if args.file:
        all_issues = scan_file(args.file)
    elif args.dir:
        for py_file in args.dir.rglob("*.py"):
            if "__pycache__" not in str(py_file) and "node_modules" not in str(py_file):
                all_issues.extend(scan_file(py_file))
    else:
        parser.print_help()
        return

    if args.output:
        args.output.write_text(json.dumps(all_issues, indent=2))
        logger.info(f"Reporte: {args.output}")
    else:
        if all_issues:
            print(f"\n⚠ {len(all_issues)} vulnerabilidades encontradas:\n")
            for issue in all_issues:
                print(f"[{issue['severity'].upper()}] {issue['file']}:{issue['line']}")
                print(f"  {issue['message']}\n")
        else:
            print("✓ No se encontraron vulnerabilidades")

    sys.exit(1 if any(i["severity"] == "critical" for i in all_issues) else 0)


if __name__ == "__main__":
    main()
