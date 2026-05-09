#!/usr/bin/env python3
"""
Database Admin - Database Utilities

Uso:
    python database_admin.py --analyze schema.sql
    python database_admin.py --check-models models.py
"""

import argparse
import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_sql_tables(content: str) -> list:
    """Parsea tablas de SQL."""
    tables = []
    pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?\s*\(([^;]+)\)'

    for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
        tables.append(
            {
                "name": match.group(1),
                "columns": len([l for l in match.group(2).split(",") if l.strip()]),
            }
        )

    return tables


def analyze_schema(file_path: Path) -> dict:
    """Analiza esquema SQL."""
    content = file_path.read_text(encoding="utf-8")
    tables = parse_sql_tables(content)
    issues = []

    for table in tables:
        if "created_at" not in content.lower():
            issues.append(f"{table['name']}: Falta created_at")
        if "id" not in content.lower():
            issues.append(f"{table['name']}: Falta PRIMARY KEY")

    return {"tables": len(tables), "table_names": [t["name"] for t in tables], "issues": issues}


def main():
    parser = argparse.ArgumentParser(description="Database Admin")
    parser.add_argument("--analyze", "-a", type=Path, help="Archivo SQL")
    parser.add_argument("--output", "-o", type=Path)

    args = parser.parse_args()

    if args.analyze:
        result = analyze_schema(args.analyze)

        print(f"\nTablas encontradas: {result['tables']}")
        for t in result["table_names"]:
            print(f"  - {t}")

        if result["issues"]:
            print("\nProblemas:")
            for i in result["issues"]:
                print(f"  ⚠ {i}")

        if args.output:
            args.output.write_text(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
