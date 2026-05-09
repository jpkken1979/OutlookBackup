#!/usr/bin/env python3
"""
Excel Parser Agent - Parsea archivos Excel con estructuras complejas.

Wrapper del skill excel-smart-parser que proporciona una interfaz
de agente para parsing avanzado de Excel.

Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add skills path
SKILLS_PATH = Path(__file__).parent.parent.parent.parent / "skills"
sys.path.insert(0, str(SKILLS_PATH / "excel-smart-parser" / "scripts"))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ExcelParserAgent:
    """Agente especializado en el parsing inteligente de archivos Excel."""

    def __init__(self):
        pass

    def parse(
        self,
        file_path: str,
        sheets: list[str] | None = None,
        schema_path: str | None = None,
        detect_tables: bool = True,
    ) -> dict[str, Any]:
        """Parsea un archivo Excel."""
        return parse_excel(file_path, sheets, schema_path, detect_tables)


def parse_excel(
    file_path: str,
    sheets: list[str] | None = None,
    schema_path: str | None = None,
    detect_tables: bool = True,
) -> dict[str, Any]:
    """
    Parsea un archivo Excel.

    Args:
        file_path: Ruta al archivo Excel
        sheets: Hojas específicas a procesar
        schema_path: Ruta al archivo JSON con schema de campos
        detect_tables: Auto-detectar tablas

    Returns:
        Diccionario con el resultado del parsing
    """
    try:
        from excel_smart_parser import ExcelSmartParser
    except ImportError as e:
        return {
            "success": False,
            "error": f"Excel parser module not available: {e}",
            "hint": "Install required packages: pip install openpyxl pandas",
        }

    # Load schema if provided
    form_schema = None
    if schema_path:
        try:
            with open(schema_path) as f:
                form_schema = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Error loading schema: {e}"}

    try:
        parser = ExcelSmartParser()
        result = parser.parse(
            file_path=file_path,
            sheet_names=sheets,
            form_schema=form_schema,
            detect_tables=detect_tables,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Error parseando Excel: {e}")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Excel Parser Agent - Parsea archivos Excel con estructuras complejas"
    )
    parser.add_argument("file", help="Ruta al archivo Excel")
    parser.add_argument("--sheets", nargs="+", help="Hojas específicas a procesar")
    parser.add_argument("--schema", help="Archivo JSON con schema de campos")
    parser.add_argument(
        "--no-detect", action="store_true", help="Desactivar auto-detección de tablas"
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--verbose", action="store_true", help="Mostrar datos de las tablas")

    args = parser.parse_args()

    result = parse_excel(
        file_path=args.file,
        sheets=args.sheets,
        schema_path=args.schema,
        detect_tables=not args.no_detect,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        if result.get("success"):
            print("Parsing exitoso")
            print(f"Hojas procesadas: {result.get('sheets', [])}")

            tables = result.get("tables", [])
            print(f"\n=== Tablas detectadas: {len(tables)} ===")

            for table in tables:
                print(f"\n  {table['sheet_name']}: {table['start_cell']} -> {table['end_cell']}")
                print(f"    Headers: {table['headers']}")
                print(f"    Filas: {table['row_count']}")

            fields = result.get("extracted_fields", [])
            if fields:
                print(f"\n=== Campos extraídos: {len(fields)} ===")
                for f in fields:
                    print(f"  {f['field']}: {f['value']} ({f['location']})")

            warnings = result.get("warnings", [])
            if warnings:
                print("\n=== Advertencias ===")
                for w in warnings:
                    print(f"  - {w}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
