#!/usr/bin/env python3
"""
Api Documentation Generator - Documentation Generator

Uso:
    python api_documentation_generator.py --file src/module.py --output docs/
    python api_documentation_generator.py --dir src/ --format markdown
"""

import argparse
import ast
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def extract_documentation(file_path: Path) -> dict:
    """Extrae documentación de un archivo Python."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    module_doc = ast.get_docstring(tree)
    functions = []
    classes = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions.append(
                {
                    "name": node.name,
                    "args": [a.arg for a in node.args.args if a.arg != "self"],
                    "docstring": ast.get_docstring(node),
                    "returns": ast.unparse(node.returns) if node.returns else None,
                }
            )
        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(
                        {
                            "name": item.name,
                            "args": [a.arg for a in item.args.args if a.arg != "self"],
                            "docstring": ast.get_docstring(item),
                        }
                    )
            classes.append(
                {"name": node.name, "docstring": ast.get_docstring(node), "methods": methods}
            )

    return {
        "module": file_path.stem,
        "module_doc": module_doc,
        "functions": functions,
        "classes": classes,
    }


def generate_markdown(doc: dict) -> str:
    """Genera documentación en Markdown."""
    lines = [f"# {doc['module']}\n"]

    if doc["module_doc"]:
        lines.append(f"{doc['module_doc']}\n")

    if doc["functions"]:
        lines.append("## Funciones\n")
        for func in doc["functions"]:
            args = ", ".join(func["args"])
            ret = f" -> {func['returns']}" if func["returns"] else ""
            lines.append(f"### `{func['name']}({args}){ret}`\n")
            if func["docstring"]:
                lines.append(f"{func['docstring']}\n")

    if doc["classes"]:
        lines.append("## Clases\n")
        for cls in doc["classes"]:
            lines.append(f"### class `{cls['name']}`\n")
            if cls["docstring"]:
                lines.append(f"{cls['docstring']}\n")
            if cls["methods"]:
                lines.append("**Métodos:**\n")
                for m in cls["methods"]:
                    if not m["name"].startswith("_") or m["name"] == "__init__":
                        lines.append(f"- `{m['name']}({', '.join(m['args'])})`")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Api Documentation Generator")
    parser.add_argument("--file", "-f", type=Path, help="Archivo a documentar")
    parser.add_argument("--dir", "-d", type=Path, help="Directorio a documentar")
    parser.add_argument("--output", "-o", type=Path, help="Directorio de salida")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")

    args = parser.parse_args()

    if args.file:
        doc = extract_documentation(args.file)
        output = generate_markdown(doc) if args.format == "markdown" else json.dumps(doc, indent=2)

        if args.output:
            out_file = args.output / f"{doc['module']}.md"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(output)
            logger.info(f"Generado: {out_file}")
        else:
            print(output)

    elif args.dir:
        for py_file in args.dir.rglob("*.py"):
            if "__pycache__" not in str(py_file) and not py_file.name.startswith("_"):
                try:
                    doc = extract_documentation(py_file)
                    if args.output:
                        out_file = args.output / f"{doc['module']}.md"
                        out_file.parent.mkdir(parents=True, exist_ok=True)
                        out_file.write_text(generate_markdown(doc))
                        logger.info(f"Generado: {out_file}")
                except SyntaxError:
                    logger.warning(f"Syntax error: {py_file}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
