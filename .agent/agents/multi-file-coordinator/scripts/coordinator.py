#!/usr/bin/env python3
"""
Multi-File Coordinator Agent - Coordina cambios en multiples archivos

Asegura consistencia y detecta referencias rotas.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileChange:
    path: str
    change_type: str  # create, modify, delete, move
    old_content: str | None = None
    new_content: str | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ImpactAnalysis:
    primary_file: str
    affected_files: list[str]
    import_references: list[dict]
    potential_breaks: list[str]
    suggested_order: list[str]


@dataclass
class CoordinationResult:
    success: bool
    operation: str
    files_analyzed: int
    changes_coordinated: int
    issues_found: list[str]
    execution_order: list[str]


class MultiFileCoordinator:
    """Coordina cambios en multiples archivos."""

    # Patrones de import por lenguaje
    IMPORT_PATTERNS = {
        "python": [
            r"^import\s+(\w+)",
            r"^from\s+(\w+(?:\.\w+)*)\s+import",
        ],
        "javascript": [
            r'import\s+.*\s+from\s+[\'"](.+?)[\'"]',
            r'require\([\'"](.+?)[\'"]\)',
        ],
        "typescript": [
            r'import\s+.*\s+from\s+[\'"](.+?)[\'"]',
            r'import\s+[\'"](.+?)[\'"]',
        ],
    }

    def __init__(self, root_path: str = "."):
        self.root = Path(root_path)
        self.dependency_graph: dict[str, list[str]] = {}

    def detect_language(self, file_path: str) -> str | None:
        """Detecta lenguaje del archivo."""
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }
        return mapping.get(ext)

    def find_imports(self, file_path: str) -> list[str]:
        """Encuentra imports en un archivo."""
        path = self.root / file_path
        if not path.exists():
            return []

        language = self.detect_language(file_path)
        if not language or language not in self.IMPORT_PATTERNS:
            return []

        imports = []
        try:
            content = path.read_text()
            for pattern in self.IMPORT_PATTERNS[language]:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
        except Exception:
            pass

        return imports

    def find_references_to(self, target: str) -> list[tuple[str, int]]:
        """Encuentra archivos que referencian al target."""
        references = []
        target_name = Path(target).stem

        for pattern in ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx"]:
            for file_path in self.root.glob(pattern):
                if any(skip in str(file_path) for skip in ["node_modules", "__pycache__", ".git"]):
                    continue

                try:
                    content = file_path.read_text()
                    # Buscar referencias al nombre
                    for i, line in enumerate(content.split("\n"), 1):
                        if target_name in line:
                            references.append((str(file_path.relative_to(self.root)), i))
                except Exception:
                    pass

        return references

    def analyze_impact(self, file_path: str, change_description: str) -> ImpactAnalysis:
        """Analiza impacto de cambio en un archivo."""
        affected = []
        imports_info = []
        potential_breaks = []

        # Encontrar quien importa este archivo
        references = self.find_references_to(file_path)
        for ref_file, line in references:
            if ref_file != file_path:
                affected.append(ref_file)
                imports_info.append({"file": ref_file, "line": line, "type": "imports"})

        # Detectar potenciales roturas
        change_lower = change_description.lower()
        if "rename" in change_lower or "delete" in change_lower or "move" in change_lower:
            for ref in affected:
                potential_breaks.append(f"{ref}: May have broken import after {change_description}")

        # Determinar orden de ejecucion
        # Regla: modificar dependencias antes que dependientes
        execution_order = [file_path] + affected

        return ImpactAnalysis(
            primary_file=file_path,
            affected_files=affected,
            import_references=imports_info,
            potential_breaks=potential_breaks,
            suggested_order=execution_order,
        )

    def verify_consistency(self, files: list[str]) -> list[str]:
        """Verifica consistencia entre archivos."""
        issues = []

        for file_path in files:
            path = self.root / file_path
            if not path.exists():
                issues.append(f"{file_path}: File does not exist")
                continue

            # Verificar imports
            imports = self.find_imports(file_path)
            for imp in imports:
                # Verificar si el import existe
                if imp.startswith("."):
                    # Relative import
                    base = path.parent
                    imp_path = (base / imp.replace(".", "/")).with_suffix(path.suffix)
                    if not imp_path.exists() and not imp_path.with_suffix("").is_dir():
                        # Puede ser directorio con index
                        index_candidates = [
                            imp_path.with_name(imp_path.stem) / "index.ts",
                            imp_path.with_name(imp_path.stem) / "index.js",
                            imp_path.with_name(imp_path.stem) / "__init__.py",
                        ]
                        if not any(c.exists() for c in index_candidates):
                            issues.append(f"{file_path}: Broken import '{imp}'")

        return issues

    def coordinate_rename(self, old_name: str, new_name: str) -> CoordinationResult:
        """Coordina renombrado de funcion/variable."""
        files_to_update = []
        changes = []

        # Buscar ocurrencias
        for pattern in ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx"]:
            for file_path in self.root.glob(pattern):
                if any(skip in str(file_path) for skip in ["node_modules", "__pycache__", ".git"]):
                    continue

                try:
                    content = file_path.read_text()
                    if old_name in content:
                        rel_path = str(file_path.relative_to(self.root))
                        files_to_update.append(rel_path)

                        # Contar ocurrencias
                        count = content.count(old_name)
                        changes.append(f"{rel_path}: {count} occurrences")
                except Exception:
                    pass

        # Orden de ejecucion: definiciones primero, usos despues
        # (simplificado - en produccion analizaria AST)
        execution_order = sorted(files_to_update)

        return CoordinationResult(
            success=True,
            operation="rename",
            files_analyzed=len(files_to_update),
            changes_coordinated=sum(1 for _ in changes),
            issues_found=[],
            execution_order=execution_order,
        )

    def execute(self, command: str) -> dict:
        """Ejecuta comando del coordinador."""
        command_lower = command.lower()

        if command_lower.startswith("impact:"):
            # Analizar impacto
            parts = command[7:].strip().split(None, 1)
            file_path = parts[0]
            description = parts[1] if len(parts) > 1 else "modify"

            analysis = self.analyze_impact(file_path, description)
            return {
                "operation": "impact",
                "primary_file": analysis.primary_file,
                "affected_files": analysis.affected_files,
                "references": analysis.import_references,
                "potential_breaks": analysis.potential_breaks,
                "suggested_order": analysis.suggested_order,
            }

        elif command_lower.startswith("verify:"):
            path = command[7:].strip() or "."
            if Path(self.root / path).is_file():
                files = [path]
            else:
                files = [
                    str(f.relative_to(self.root))
                    for f in (self.root / path).rglob("*")
                    if f.is_file() and f.suffix in [".py", ".js", ".ts", ".tsx"]
                ]

            issues = self.verify_consistency(files)
            return {
                "operation": "verify",
                "files_checked": len(files),
                "issues": issues,
                "passed": len(issues) == 0,
            }

        elif command_lower.startswith("rename:"):
            # Format: rename: old_name new_name
            parts = command[7:].strip().split()
            if len(parts) >= 2:
                result = self.coordinate_rename(parts[0], parts[1])
                return {
                    "operation": "rename",
                    "old_name": parts[0],
                    "new_name": parts[1],
                    "files_affected": result.files_analyzed,
                    "execution_order": result.execution_order,
                }
            return {"operation": "rename", "error": "Usage: rename: old_name new_name"}

        else:
            return {
                "operation": "unknown",
                "error": f"Unknown command: {command}",
                "available": [
                    "impact: <file> [description]",
                    "verify: <path>",
                    "rename: <old> <new>",
                ],
            }


def main():
    parser = argparse.ArgumentParser(
        description="Multi-File Coordinator - Coordina cambios en multiples archivos"
    )
    parser.add_argument(
        "command", nargs="?", default="verify: .", help="Comando (impact, verify, rename)"
    )
    parser.add_argument("--root", default=".", help="Directorio raiz")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    coordinator = MultiFileCoordinator(args.root)
    result = coordinator.execute(args.command)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        op = result.get("operation", "unknown")

        if op == "impact":
            print(f"Impact Analysis: {result['primary_file']}")
            print("=" * 40)
            print(f"Affected files: {len(result['affected_files'])}")
            for f in result["affected_files"][:10]:
                print(f"  - {f}")
            if result["potential_breaks"]:
                print("\nPotential breaks:")
                for b in result["potential_breaks"]:
                    print(f"  ! {b}")
            print("\nSuggested order:")
            for i, f in enumerate(result["suggested_order"][:10], 1):
                print(f"  {i}. {f}")

        elif op == "verify":
            status = "✓" if result["passed"] else "✗"
            print(f"[{status}] Consistency Check")
            print(f"Files checked: {result['files_checked']}")
            if result["issues"]:
                print("\nIssues found:")
                for issue in result["issues"]:
                    print(f"  - {issue}")
            else:
                print("No issues found!")

        elif op == "rename":
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Rename: {result['old_name']} -> {result['new_name']}")
                print(f"Files affected: {result['files_affected']}")
                print("\nExecution order:")
                for i, f in enumerate(result["execution_order"][:10], 1):
                    print(f"  {i}. {f}")

        else:
            print(f"Error: {result.get('error', 'Unknown')}")

    sys.exit(0)


if __name__ == "__main__":
    main()
