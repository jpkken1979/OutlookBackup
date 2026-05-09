#!/usr/bin/env python3
"""Architectural Boundary Guards — Enforcement de capas como CI checks.

Inspirado en el patrón de OpenClaw de "architecture-as-code":
scripts CI que verifican que las boundaries arquitectónicas
de 4 capas se respeten en imports y dependencias.

Capas del ecosistema Antigravity:
  1. DIRECTIVA  → SKILL.md, IDENTITY.md, rules.md (config/docs only)
  2. CONTEXTO   → .context/, memory/, data/ (estado persistente)
  3. EJECUCIÓN  → scripts/, src/, tools/ (código activo)
  4. OBSERVABILIDAD → logs/, artifacts/, dashboard/ (monitoreo)

Reglas enforced:
  R1: core/ NO puede importar de plugins/ ni agents/ (inversión de dependencia)
  R2: skills/ son documentos: NO deben tener imports de core
  R3: agents/ pueden importar core pero NO de otros agents (aislamiento)
  R4: plugins/ pueden importar core pero NO de agents directamente
  R5: mcp/ NO puede importar de plugins/ (gateway es independiente)
  R6: scripts/ pueden importar core y mcp pero NO de plugins

Exit codes:
  0 = Sin violaciones
  1 = Violaciones encontradas

Uso en CI:
    python .agent/scripts/check_boundaries.py
    python .agent/scripts/check_boundaries.py --json
    python .agent/scripts/check_boundaries.py --fix-suggestions

v1.0.0 - 2026-02-27 — Inspirado en OpenClaw architectural lint guards
"""

from __future__ import annotations

import ast
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Evita crashes por encoding en consolas Windows cp932/cp1252.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.check_boundaries")

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENT_DIR = PROJECT_ROOT / ".agent"

# Mapeo de módulos a capas
LAYER_MAP: dict[str, str] = {
    "core": "execution",
    "mcp": "execution",
    "scripts": "execution",
    "agents": "execution",
    "plugins": "execution",
    "skills": "directive",
    "workflows": "execution",
}

# =============================================================================
# BOUNDARY RULES
# =============================================================================


@dataclass
class BoundaryRule:
    """Una regla de boundary arquitectónico."""

    id: str
    source_module: str  # Módulo donde aplica (ej: "core")
    forbidden_imports: list[str]  # Módulos que NO puede importar
    description: str
    severity: str = "error"  # "error" | "warning"


# Definición de reglas
BOUNDARY_RULES: list[BoundaryRule] = [
    BoundaryRule(
        id="R1",
        source_module="core",
        forbidden_imports=["plugins", "agents"],
        description="core/ NO puede importar de plugins/ ni agents/ (inversión de dependencia)",
    ),
    BoundaryRule(
        id="R2",
        source_module="skills",
        forbidden_imports=["core", "plugins", "agents", "mcp"],
        description="skills/ son documentos: NO deben contener imports Python de core",
        severity="warning",
    ),
    BoundaryRule(
        id="R3-cross",
        source_module="agents",
        forbidden_imports=["plugins"],
        description="agents/ NO pueden importar de plugins/ directamente",
    ),
    BoundaryRule(
        id="R4",
        source_module="plugins",
        forbidden_imports=["agents"],
        description="plugins/ NO pueden importar de agents/ directamente",
    ),
    BoundaryRule(
        id="R5",
        source_module="mcp",
        forbidden_imports=["plugins"],
        description="mcp/ NO puede importar de plugins/ (gateway es independiente)",
    ),
]


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Violation:
    """Una violación de boundary detectada."""

    rule_id: str
    file: str
    line: int
    import_statement: str
    forbidden_target: str
    severity: str
    description: str

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        return {
            "rule_id": self.rule_id,
            "file": self.file,
            "line": self.line,
            "import_statement": self.import_statement,
            "forbidden_target": self.forbidden_target,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class BoundaryReport:
    """Reporte de verificación de boundaries."""

    violations: list[Violation] = field(default_factory=list)
    files_scanned: int = 0
    rules_checked: int = 0

    @property
    def has_errors(self) -> bool:
        """Tiene violaciones de severidad 'error'."""
        return any(v.severity == "error" for v in self.violations)

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        errors = [v for v in self.violations if v.severity == "error"]
        warnings = [v for v in self.violations if v.severity == "warning"]
        return {
            "files_scanned": self.files_scanned,
            "rules_checked": self.rules_checked,
            "total_violations": len(self.violations),
            "errors": len(errors),
            "warnings": len(warnings),
            "violations": [v.to_dict() for v in self.violations],
        }


# =============================================================================
# IMPORT EXTRACTOR — Extrae imports de archivos Python usando AST
# =============================================================================

# Patrones de import relativo/absoluto que referencien módulos internos
_IMPORT_FROM_PATTERN = re.compile(
    r"^\s*from\s+\.*(core|agents|plugins|skills|mcp|scripts|workflows)\b"
)
_IMPORT_PATTERN = re.compile(r"^\s*import\s+(core|agents|plugins|skills|mcp|scripts|workflows)\b")


def extract_imports_ast(file_path: Path) -> list[tuple[int, str, str]]:
    """Extrae imports de un archivo Python usando AST.

    Args:
        file_path: Ruta al archivo Python.

    Returns:
        Lista de (línea, statement, módulo_target).
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    imports: list[tuple[int, str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in LAYER_MAP:
                    stmt = f"import {alias.name}"
                    imports.append((node.lineno, stmt, module_name))

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # Resolver imports relativos
                parts = node.module.split(".")
                # Extraer el módulo raíz
                root_module = parts[0] if parts[0] in LAYER_MAP else None
                if root_module:
                    names = ", ".join(a.name for a in node.names[:3])
                    if len(node.names) > 3:
                        names += ", ..."
                    stmt = f"from {node.module} import {names}"
                    imports.append((node.lineno, stmt, root_module))

    return imports


def extract_imports_regex(file_path: Path) -> list[tuple[int, str, str]]:
    """Extrae imports usando regex (fallback para archivos con syntax errors)."""
    imports: list[tuple[int, str, str]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []

    for i, line in enumerate(lines, 1):
        match = _IMPORT_FROM_PATTERN.match(line)
        if match:
            imports.append((i, line.strip(), match.group(1)))
            continue
        match = _IMPORT_PATTERN.match(line)
        if match:
            imports.append((i, line.strip(), match.group(1)))

    return imports


# =============================================================================
# BOUNDARY CHECKER — Motor principal
# =============================================================================


def _get_module_for_file(file_path: Path) -> str | None:
    """Determina a qué módulo pertenece un archivo.

    Args:
        file_path: Ruta relativa al archivo desde .agent/.

    Returns:
        Nombre del módulo o None si no pertenece a ninguno conocido.
    """
    parts = file_path.parts
    # Buscar la primera parte que sea un módulo conocido
    for part in parts:
        if part in LAYER_MAP:
            return part
    return None


def _check_agent_cross_imports(
    file_path: Path, imports: list[tuple[int, str, str]]
) -> list[Violation]:
    """Verifica R3: agentes no pueden importar de otros agentes.

    Args:
        file_path: Ruta al archivo relativa a .agent/.
        imports: Lista de imports extraídos.

    Returns:
        Lista de violaciones R3.
    """
    violations: list[Violation] = []
    parts = file_path.parts

    # Buscar el nombre del agente actual
    if "agents" not in parts:
        return violations

    agent_idx = list(parts).index("agents")
    if agent_idx + 1 >= len(parts):
        return violations

    current_agent = parts[agent_idx + 1]

    for line_no, stmt, target in imports:
        if target == "agents":
            # Verificar si importa de otro agente
            if f"agents.{current_agent}" not in stmt and "agents" in stmt:
                violations.append(
                    Violation(
                        rule_id="R3",
                        file=str(file_path),
                        line=line_no,
                        import_statement=stmt,
                        forbidden_target=f"agents (cross-agent import from {current_agent})",
                        severity="error",
                        description="Agentes NO pueden importar de otros agentes (aislamiento)",
                    )
                )

    return violations


def check_boundaries(agent_dir: Path | None = None) -> BoundaryReport:
    """Ejecuta todas las boundary checks.

    Args:
        agent_dir: Directorio .agent/ (default: auto-detect).

    Returns:
        BoundaryReport con todas las violaciones encontradas.
    """
    if agent_dir is None:
        agent_dir = AGENT_DIR

    report = BoundaryReport(rules_checked=len(BOUNDARY_RULES))

    # Recolectar todos los archivos Python
    py_files: list[Path] = []
    for module_name in LAYER_MAP:
        module_dir = agent_dir / module_name
        if module_dir.is_dir():
            py_files.extend(module_dir.rglob("*.py"))

    report.files_scanned = len(py_files)
    logger.info("Scanning %d Python files across %d modules...", len(py_files), len(LAYER_MAP))

    for py_file in py_files:
        # Ruta relativa desde .agent/
        try:
            rel_path = py_file.relative_to(agent_dir)
        except ValueError:
            continue

        source_module = _get_module_for_file(rel_path)
        if source_module is None:
            continue

        # Extraer imports (AST preferido, regex como fallback)
        imports = extract_imports_ast(py_file)
        if not imports:
            imports = extract_imports_regex(py_file)

        # Verificar cada regla aplicable
        for rule in BOUNDARY_RULES:
            if rule.source_module != source_module:
                continue

            for line_no, stmt, target in imports:
                if target in rule.forbidden_imports:
                    report.violations.append(
                        Violation(
                            rule_id=rule.id,
                            file=str(rel_path),
                            line=line_no,
                            import_statement=stmt,
                            forbidden_target=target,
                            severity=rule.severity,
                            description=rule.description,
                        )
                    )

        # R3 especial: cross-agent imports
        if source_module == "agents":
            report.violations.extend(_check_agent_cross_imports(rel_path, imports))

    return report


# =============================================================================
# REPORTERS
# =============================================================================


def print_report(report: BoundaryReport) -> None:
    """Imprime reporte legible a stdout."""
    errors = [v for v in report.violations if v.severity == "error"]
    warnings = [v for v in report.violations if v.severity == "warning"]

    print(f"\n{'=' * 70}")
    print(f"Architectural Boundary Check — {report.files_scanned} files scanned")
    print(f"{'=' * 70}\n")

    if not report.violations:
        print("✅ No boundary violations found!\n")
        return

    if errors:
        print(f"❌ {len(errors)} ERRORS:\n")
        for v in errors:
            print(f"  [{v.rule_id}] {v.file}:{v.line}")
            print(f"         {v.import_statement}")
            print(f"         → {v.description}\n")

    if warnings:
        print(f"⚠️  {len(warnings)} WARNINGS:\n")
        for v in warnings:
            print(f"  [{v.rule_id}] {v.file}:{v.line}")
            print(f"         {v.import_statement}")
            print(f"         → {v.description}\n")

    print(f"{'=' * 70}")
    print(f"Summary: {len(errors)} errors, {len(warnings)} warnings")
    print(f"{'=' * 70}\n")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """Entry point — ejecutar como CI check."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verifica boundaries arquitectónicas del ecosistema"
    )
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")
    parser.add_argument("--strict", action="store_true", help="Warnings también causan exit code 1")
    parser.add_argument(
        "--agent-dir",
        type=str,
        default=None,
        help="Ruta a .agent/ (default: auto-detect)",
    )
    args = parser.parse_args()

    agent_dir = Path(args.agent_dir) if args.agent_dir else None
    report = check_boundaries(agent_dir)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    # Exit code
    if report.has_errors or args.strict and report.violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
