# mypy: ignore-errors
"""Radar AST: análisis estructural de archivos Python sin ejecución.

Parsea código fuente usando el módulo `ast` de la librería estándar y extrae
la estructura fundamental (imports, clases, funciones, llamadas) en forma de
diccionario JSON-serializable. Incluye un mecanismo de reparación heurística
para archivos con errores de indentación comunes.
"""

import ast
import json
from pathlib import Path
from typing import Any


class ASTRadar:
    """
    AST Code Radar: Visión de Rayos X para el código.
    Parsea código Python sin necesidad de leer todo el texto plano,
    extrayendo su estructura fundamental (Imports, Clases, Funciones, Llamadas).
    """

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)

    @staticmethod
    def _repair_common_indentation_issues(content: str) -> str:
        """Intenta reparar errores simples de indentación tras `def ...:`.

        Este fallback solo ajusta el caso más común: una definición de función
        cuyo primer statement tiene igual o menor indentación.
        """
        lines = content.splitlines()
        repaired = lines[:]

        for index, line in enumerate(lines[:-1]):
            stripped = line.strip()
            if not stripped.startswith("def ") or not stripped.endswith(":"):
                continue

            current_indent = len(line) - len(line.lstrip())
            next_index = index + 1

            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1

            if next_index >= len(lines):
                continue

            next_line = repaired[next_index]
            next_indent = len(next_line) - len(next_line.lstrip())
            if next_indent <= current_indent:
                repaired[next_index] = " " * (current_indent + 4) + next_line.lstrip()

        return "\n".join(repaired)

    def analyze_python_file(self, rel_path: str) -> dict[str, Any]:
        """Analiza un archivo Python y devuelve su estructura."""
        target_path = self.root_path / rel_path
        if not target_path.exists() or not target_path.is_file():
            return {"error": f"File not found: {rel_path}"}

        try:
            content = target_path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(content)
            except SyntaxError:
                repaired_content = self._repair_common_indentation_issues(content)
                tree = ast.parse(repaired_content)

            imports, classes, functions = self._extract_ast_structure(tree)

            return {
                "file": rel_path,
                "status": "success",
                "imports": imports,
                "classes": classes,
                "global_functions": functions,
            }
        except Exception as e:
            return {"error": f"Failed to parse AST for {rel_path}: {str(e)}"}

    @staticmethod
    def _extract_ast_structure(tree: ast.AST) -> tuple[list, list, list]:
        """Extrae imports, clases y funciones globales de un árbol AST.

        Args:
            tree: Árbol AST parseado.

        Returns:
            Tupla (imports, classes, global_functions). Las funciones que son
            métodos de clase se excluyen de global_functions.
        """
        imports: list = []
        classes: list = []
        functions: list = []
        method_node_ids: set[int] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module if node.module else ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.ClassDef):
                class_methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                methods = [method.name for method in class_methods]
                method_node_ids.update(id(method) for method in class_methods)
                classes.append({"name": node.name, "line": node.lineno, "methods": methods})

            if isinstance(node, ast.FunctionDef) and id(node) not in method_node_ids:
                functions.append({"name": node.name, "line": node.lineno})

        return imports, classes, functions

    def scan_for_usages(self, target_function_or_class: str, directory: str = ".") -> list[str]:
        """
        Escanea el directorio buscando en qué scripts se invoca una clase o función.
        Retorna la lista de archivos que dependen de ese elemento.
        """
        search_dir = self.root_path / directory
        affected_files = []

        if not search_dir.exists():
            return [f"Error: Directory {directory} not found."]

        for py_file in search_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Name)
                        and node.id == target_function_or_class
                        or isinstance(node, ast.Attribute)
                        and node.attr == target_function_or_class
                    ):
                        affected_files.append(str(py_file.relative_to(self.root_path)))
                        break
            except Exception:
                pass  # Ignorar archivos no parseables silenciosamente

        return affected_files


def run_ast_radar(action: str, target: str, path: str = ".") -> str:
    radar = ASTRadar(path)
    if action == "analyze_file":
        result = radar.analyze_python_file(target)
        return json.dumps(result, indent=2)
    elif action == "find_usages":
        result = radar.scan_for_usages(target)
        return json.dumps({"target": target, "affected_files": result}, indent=2)
    return json.dumps({"error": "Invalid action. Use 'analyze_file' or 'find_usages'."})
