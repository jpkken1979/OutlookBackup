#!/usr/bin/env python3
"""
Test Fixing - Systematic Test Failure Analyzer

Runs tests, parses failures, groups errors by type/module/root cause,
and generates a prioritized fix plan.

Uso:
    python test_fixing.py --dir tests/
    python test_fixing.py --dir tests/ --cmd "pytest tests/ -v"
    python test_fixing.py --dir tests/ --output report.json
    python test_fixing.py --parse pytest_output.txt
"""

import argparse
import json
import logging
import re
import subprocess
import shlex
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

# Priority order for error categories (infrastructure first, logic last)
ERROR_PRIORITY = {
    "ImportError": 1,
    "ModuleNotFoundError": 1,
    "SyntaxError": 2,
    "NameError": 2,
    "TypeError": 3,
    "AttributeError": 3,
    "ValueError": 4,
    "KeyError": 4,
    "IndexError": 4,
    "AssertionError": 5,
    "RuntimeError": 5,
    "Other": 6,
}


@dataclass
class TestFailure:
    """Represents a single test failure."""

    test_id: str
    test_file: str
    test_name: str
    error_type: str
    error_message: str
    traceback_lines: list[str] = field(default_factory=list)


@dataclass
class ErrorGroup:
    """A group of related test failures."""

    category: str
    error_type: str
    priority: int
    failures: list[TestFailure] = field(default_factory=list)
    root_cause: str = ""
    fix_suggestion: str = ""

    @property
    def impact(self) -> int:
        return len(self.failures)

    @property
    def affected_files(self) -> list[str]:
        return sorted({f.test_file for f in self.failures})


def run_tests(test_dir: Path, cmd: str | None = None) -> str:
    """Run tests and capture output."""
    if cmd:
        args = shlex.split(cmd)
    else:
        args = ["python3", "-m", "pytest", str(test_dir), "-v", "--tb=short", "--no-header"]

    logger.info(f"Ejecutando: {' '.join(args)}")

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=300,
    )

    return result.stdout + "\n" + result.stderr


def parse_pytest_output(output: str) -> list[TestFailure]:
    """Parse pytest output to extract test failures."""
    failures: list[TestFailure] = []

    # Pattern for FAILED line: FAILED tests/test_foo.py::TestClass::test_method - ErrorType: msg
    failed_pattern = re.compile(
        r"FAILED\s+(.+?)::(.+?)\s+-\s+(\w+(?:Error|Exception|Warning)?):?\s*(.*)"
    )

    # Pattern for short traceback blocks
    tb_pattern = re.compile(
        r"_{3,}\s+(.+?)\s+_{3,}\n(.*?)(?=\n_{3,}|\n={3,}|\nSHORT)",
        re.DOTALL,
    )

    # Pattern for error lines in tracebacks
    error_line_pattern = re.compile(r"^E\s+(\w+(?:Error|Exception)?):?\s*(.*)", re.MULTILINE)

    # First try to extract from FAILED summary lines
    for match in failed_pattern.finditer(output):
        test_file = match.group(1).strip()
        test_name = match.group(2).strip()
        error_type = match.group(3).strip()
        error_message = match.group(4).strip()

        failures.append(
            TestFailure(
                test_id=f"{test_file}::{test_name}",
                test_file=test_file,
                test_name=test_name,
                error_type=error_type,
                error_message=error_message,
            )
        )

    # If no FAILED lines found, try parsing traceback blocks
    if not failures:
        for tb_match in tb_pattern.finditer(output):
            test_id = tb_match.group(1).strip()
            tb_content = tb_match.group(2).strip()

            parts = test_id.split("::")
            test_file = parts[0] if parts else test_id
            test_name = "::".join(parts[1:]) if len(parts) > 1 else test_id

            error_type = "Unknown"
            error_message = ""

            for err_match in error_line_pattern.finditer(tb_content):
                error_type = err_match.group(1)
                error_message = err_match.group(2)

            failures.append(
                TestFailure(
                    test_id=test_id,
                    test_file=test_file,
                    test_name=test_name,
                    error_type=error_type,
                    error_message=error_message,
                    traceback_lines=tb_content.split("\n"),
                )
            )

    # Fallback: look for lines with FAILED status
    if not failures:
        simple_failed = re.compile(r"(.+?::[\w.]+)\s+FAILED")
        for match in simple_failed.finditer(output):
            test_id = match.group(1).strip()
            parts = test_id.split("::")
            test_file = parts[0] if parts else test_id
            test_name = "::".join(parts[1:]) if len(parts) > 1 else test_id

            failures.append(
                TestFailure(
                    test_id=test_id,
                    test_file=test_file,
                    test_name=test_name,
                    error_type="Unknown",
                    error_message="",
                )
            )

    return failures


def _categorize_error(error_type: str) -> str:
    """Categorize error into infrastructure, api_change, or logic."""
    infrastructure = {"ImportError", "ModuleNotFoundError", "SyntaxError", "FileNotFoundError"}
    api_change = {"AttributeError", "TypeError", "NameError"}

    if error_type in infrastructure:
        return "infrastructure"
    if error_type in api_change:
        return "api_change"
    return "logic"


def _suggest_fix(error_type: str, messages: list[str]) -> str:
    """Generate fix suggestion based on error type and messages."""
    suggestions = {
        "ImportError": "Verificar que el modulo exista y los imports sean correctos.",
        "ModuleNotFoundError": "Instalar dependencia faltante o corregir la ruta del modulo.",
        "SyntaxError": "Corregir errores de sintaxis en el archivo indicado.",
        "AttributeError": "Verificar que el atributo/metodo exista. Pudo haber sido renombrado.",
        "TypeError": "Verificar la firma de la funcion. Los argumentos pueden haber cambiado.",
        "NameError": "La variable o funcion no esta definida. Verificar imports y scope.",
        "AssertionError": "La asercion del test fallo. Revisar la logica del codigo bajo test.",
        "ValueError": "El valor no es valido. Verificar validaciones y transformaciones.",
        "KeyError": "La clave no existe en el diccionario. Verificar estructura de datos.",
        "IndexError": "Indice fuera de rango. Verificar longitud de listas/secuencias.",
        "FileNotFoundError": "El archivo no existe. Verificar rutas y fixtures de test.",
    }

    base = suggestions.get(error_type, "Revisar el traceback para identificar la causa raiz.")

    # Add specifics from messages
    for msg in messages[:3]:
        if "no module named" in msg.lower():
            module = msg.split("'")[-2] if "'" in msg else msg
            base += f" Modulo faltante: {module}."
            break
        if "has no attribute" in msg.lower():
            attr = msg.split("'")[-2] if "'" in msg else msg
            base += f" Atributo faltante: {attr}."
            break

    return base


def group_failures(failures: list[TestFailure]) -> list[ErrorGroup]:
    """Group failures by error type and generate fix plans."""
    by_type: dict[str, list[TestFailure]] = defaultdict(list)

    for failure in failures:
        by_type[failure.error_type].append(failure)

    groups: list[ErrorGroup] = []
    for error_type, type_failures in by_type.items():
        category = _categorize_error(error_type)
        priority = ERROR_PRIORITY.get(error_type, ERROR_PRIORITY["Other"])
        messages = [f.error_message for f in type_failures if f.error_message]

        group = ErrorGroup(
            category=category,
            error_type=error_type,
            priority=priority,
            failures=type_failures,
            root_cause=f"{len(type_failures)} tests fallan con {error_type}",
            fix_suggestion=_suggest_fix(error_type, messages),
        )
        groups.append(group)

    # Sort by priority (infrastructure first), then by impact (most failures first)
    groups.sort(key=lambda g: (g.priority, -g.impact))
    return groups


def generate_report(groups: list[ErrorGroup], total_output: str) -> dict:
    """Generate a structured report from error groups."""
    # Parse summary line
    total_tests = 0
    total_failed = 0
    total_passed = 0

    summary_match = re.search(
        r"(\d+)\s+(?:passed|failed).*?(\d+)\s+(?:passed|failed)",
        total_output,
    )
    if summary_match:
        nums = re.findall(r"(\d+)\s+(passed|failed)", total_output)
        for count, status in nums:
            if status == "passed":
                total_passed = int(count)
            elif status == "failed":
                total_failed = int(count)
        total_tests = total_passed + total_failed

    all_failures = []
    for g in groups:
        all_failures.extend(g.failures)

    if not total_failed:
        total_failed = len(all_failures)
    if not total_tests:
        total_tests = total_failed

    report = {
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "error_groups": len(groups),
        },
        "fix_order": [],
        "groups": [],
    }

    for i, group in enumerate(groups, 1):
        group_data = {
            "order": i,
            "category": group.category,
            "error_type": group.error_type,
            "priority": group.priority,
            "affected_tests": group.impact,
            "affected_files": group.affected_files,
            "root_cause": group.root_cause,
            "fix_suggestion": group.fix_suggestion,
            "tests": [
                {
                    "test_id": f.test_id,
                    "error_message": f.error_message,
                }
                for f in group.failures
            ],
        }
        report["groups"].append(group_data)
        report["fix_order"].append(
            f"{i}. [{group.category.upper()}] {group.error_type} "
            f"({group.impact} tests) - {group.fix_suggestion[:80]}"
        )

    return report


def format_report_text(report: dict) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 70)
    lines.append("TEST FAILURE ANALYSIS REPORT")
    lines.append("=" * 70)

    s = report["summary"]
    lines.append(f"\nTotal tests: {s['total_tests']}")
    lines.append(f"Passed: {s['passed']}")
    lines.append(f"Failed: {s['failed']}")
    lines.append(f"Error groups: {s['error_groups']}")

    lines.append("\n" + "-" * 70)
    lines.append("FIX ORDER (prioritized)")
    lines.append("-" * 70)

    for item in report["fix_order"]:
        lines.append(f"  {item}")

    for group in report["groups"]:
        lines.append(f"\n{'=' * 70}")
        lines.append(
            f"Group {group['order']}: {group['error_type']} "
            f"[{group['category'].upper()}] "
            f"({group['affected_tests']} tests)"
        )
        lines.append(f"Priority: {group['priority']}")
        lines.append(f"Root cause: {group['root_cause']}")
        lines.append(f"Suggestion: {group['fix_suggestion']}")
        lines.append(f"Affected files: {', '.join(group['affected_files'])}")
        lines.append("\nFailing tests:")
        for test in group["tests"]:
            msg = f" - {test['error_message']}" if test["error_message"] else ""
            lines.append(f"  - {test['test_id']}{msg}")

    lines.append(f"\n{'=' * 70}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Fixing - Systematic test failure analyzer")
    parser.add_argument("--dir", "-d", type=Path, help="Directorio de tests a ejecutar")
    parser.add_argument("--cmd", "-c", type=str, help="Comando de test personalizado")
    parser.add_argument("--parse", "-p", type=Path, help="Parsear output de pytest existente")
    parser.add_argument("--output", "-o", type=Path, help="Archivo de salida (JSON)")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Formato de salida"
    )

    args = parser.parse_args()

    output_text = ""

    if args.parse:
        output_text = args.parse.read_text(encoding="utf-8")
        logger.info(f"Parseando output de: {args.parse}")
    elif args.dir:
        output_text = run_tests(args.dir, args.cmd)
    else:
        parser.print_help()
        return

    failures = parse_pytest_output(output_text)

    if not failures:
        logger.info("No se encontraron tests fallidos.")
        print("No se encontraron tests fallidos.")
        return

    logger.info(f"Encontrados {len(failures)} tests fallidos")

    groups = group_failures(failures)
    report = generate_report(groups, output_text)

    if args.format == "json" or args.output:
        json_output = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json_output, encoding="utf-8")
            logger.info(f"Reporte guardado en: {args.output}")
        else:
            print(json_output)
    else:
        print(format_report_text(report))


if __name__ == "__main__":
    main()
