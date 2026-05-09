#!/usr/bin/env python3
"""
Ab Test Setup - Testing Utilities

Uso:
    python ab_test_setup.py --file src/module.py
    python ab_test_setup.py --dir src/ --output report.json
"""

import argparse
import ast
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def analyze_testability(file_path: Path) -> dict:
    """Analiza la testabilidad del código."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    functions = [
        n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

    return {
        "file": str(file_path),
        "functions": len(functions),
        "classes": len(classes),
        "testable": len(functions) > 0,
    }


def generate_test_skeleton(file_path: Path) -> str:
    """Genera esqueleto de tests."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    module_name = file_path.stem

    tests = [
        f'"""Tests para {module_name}."""',
        "import pytest",
        f"from {module_name} import *",
        "",
    ]

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            tests.append(f"""
def test_{node.name}_basic():
    \"\"\"Test básico para {node.name}.\"\"\"
    # Arrange
    # Arrange: configurar datos de prueba

    # Act
    # result = {node.name}(...)

    # Assert
    # assert result is not None
    pass
""")

    return "\n".join(tests)


def main():
    parser = argparse.ArgumentParser(description="Ab Test Setup")
    parser.add_argument("--file", "-f", type=Path, help="Archivo a analizar")
    parser.add_argument("--dir", "-d", type=Path, help="Directorio a analizar")
    parser.add_argument("--generate", "-g", action="store_true", help="Generar tests")
    parser.add_argument("--output", "-o", type=Path, help="Archivo de salida")

    args = parser.parse_args()

    if args.file:
        if args.generate:
            tests = generate_test_skeleton(args.file)
            if args.output:
                args.output.write_text(tests)
                logger.info(f"Tests generados: {args.output}")
            else:
                print(tests)
        else:
            result = analyze_testability(args.file)
            print(json.dumps(result, indent=2))

    elif args.dir:
        results = []
        for py_file in args.dir.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                results.append(analyze_testability(py_file))

        if args.output:
            args.output.write_text(json.dumps(results, indent=2))
        else:
            for r in results:
                print(f"{r['file']}: {r['functions']} funciones")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
