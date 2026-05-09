#!/usr/bin/env python3
"""
Clean Code Principles - Analizador de Código
Herramienta para detectar violaciones de principios de código limpio.
"""

import logging
import re
import ast
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class CodeIssue:
    """Representa un problema encontrado en el código."""

    rule: str
    message: str
    line: int
    severity: Severity
    suggestion: str | None = None


@dataclass
class AnalysisResult:
    """Resultado del análisis de código limpio."""

    file_path: str
    issues: list[CodeIssue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def score(self) -> int:
        """Calcula un score de 0-100 basado en issues encontrados."""
        if not self.issues:
            return 100
        error_count = sum(1 for i in self.issues if i.severity == Severity.ERROR)
        warning_count = sum(1 for i in self.issues if i.severity == Severity.WARNING)
        penalty = (error_count * 10) + (warning_count * 3)
        return max(0, 100 - penalty)


class CleanCodeAnalyzer:
    """Analizador de principios de código limpio."""

    # Configuración de reglas
    MAX_LINE_LENGTH = 120
    MAX_FUNCTION_LENGTH = 30
    MAX_FUNCTION_PARAMS = 5
    MAX_COMPLEXITY = 10
    MIN_VARIABLE_LENGTH = 3
    RESERVED_SINGLE_CHARS = {"i", "j", "k", "n", "x", "y", "z"}

    def analyze(self, code: str, file_path: str = "<string>") -> AnalysisResult:
        """Analiza código Python en busca de violaciones de código limpio."""
        result = AnalysisResult(file_path=file_path)

        # Análisis basado en texto
        self._check_line_length(code, result)
        self._check_naming_conventions(code, result)
        self._check_comments(code, result)

        # Análisis basado en AST
        try:
            tree = ast.parse(code)
            self._check_function_length(tree, code, result)
            self._check_function_params(tree, result)
            self._check_complexity(tree, result)
            self._check_dead_code(tree, result)
            self._calculate_metrics(tree, code, result)
        except SyntaxError as e:
            result.issues.append(
                CodeIssue(
                    rule="SYNTAX",
                    message=f"Syntax error: {e}",
                    line=e.lineno or 1,
                    severity=Severity.ERROR,
                )
            )

        return result

    def _check_line_length(self, code: str, result: AnalysisResult) -> None:
        """Verifica longitud de líneas (KISS)."""
        for i, line in enumerate(code.split("\n"), 1):
            if len(line) > self.MAX_LINE_LENGTH:
                result.issues.append(
                    CodeIssue(
                        rule="LINE_LENGTH",
                        message=f"Line too long ({len(line)} > {self.MAX_LINE_LENGTH})",
                        line=i,
                        severity=Severity.WARNING,
                        suggestion="Break into multiple lines or extract to variable",
                    )
                )

    def _check_naming_conventions(self, code: str, result: AnalysisResult) -> None:
        """Verifica convenciones de nombres."""
        # Detectar variables de una sola letra (excepto en loops)
        single_char_pattern = r"\b([a-zA-Z])\s*="
        for i, line in enumerate(code.split("\n"), 1):
            if "for " in line or "lambda" in line:
                continue
            matches = re.findall(single_char_pattern, line)
            for match in matches:
                if match.lower() not in self.RESERVED_SINGLE_CHARS:
                    result.issues.append(
                        CodeIssue(
                            rule="NAMING_SHORT",
                            message=f"Single character variable '{match}' is not descriptive",
                            line=i,
                            severity=Severity.WARNING,
                            suggestion="Use descriptive names that reveal intent",
                        )
                    )

        # Detectar nombres muy largos
        long_name_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]{40,})\b"
        for i, line in enumerate(code.split("\n"), 1):
            matches = re.findall(long_name_pattern, line)
            for match in matches:
                result.issues.append(
                    CodeIssue(
                        rule="NAMING_LONG",
                        message=f"Name '{match[:20]}...' is too long ({len(match)} chars)",
                        line=i,
                        severity=Severity.INFO,
                        suggestion="Consider shorter but still descriptive names",
                    )
                )

    def _check_comments(self, code: str, result: AnalysisResult) -> None:
        """Verifica calidad de comentarios."""
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Comentarios obvios
            if stripped.startswith("#"):
                comment = stripped[1:].strip().lower()
                obvious_patterns = [
                    r"^increment",
                    r"^add \d+ to",
                    r"^set .+ to",
                    r"^initialize",
                    r"^declare",
                    r"^loop through",
                    r"^return the",
                ]
                for pattern in obvious_patterns:
                    if re.match(pattern, comment):
                        result.issues.append(
                            CodeIssue(
                                rule="OBVIOUS_COMMENT",
                                message="Comment states the obvious",
                                line=i,
                                severity=Severity.INFO,
                                suggestion="Remove or replace with 'why' not 'what'",
                            )
                        )
                        break

    def _check_function_length(self, tree: ast.AST, code: str, result: AnalysisResult) -> None:
        """Verifica longitud de funciones (SRP)."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calcular líneas de la función
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                func_length = end_line - start_line + 1

                if func_length > self.MAX_FUNCTION_LENGTH:
                    result.issues.append(
                        CodeIssue(
                            rule="FUNCTION_LENGTH",
                            message=f"Function '{node.name}' is too long ({func_length} lines)",
                            line=start_line,
                            severity=Severity.WARNING,
                            suggestion="Extract methods to follow Single Responsibility Principle",
                        )
                    )

    def _check_function_params(self, tree: ast.AST, result: AnalysisResult) -> None:
        """Verifica número de parámetros (menos es más)."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Contar parámetros (excluyendo self/cls)
                params = node.args.args
                param_count = len([p for p in params if p.arg not in ("self", "cls")])

                if param_count > self.MAX_FUNCTION_PARAMS:
                    result.issues.append(
                        CodeIssue(
                            rule="TOO_MANY_PARAMS",
                            message=f"Function '{node.name}' has {param_count} parameters",
                            line=node.lineno,
                            severity=Severity.WARNING,
                            suggestion="Consider using a data class or builder pattern",
                        )
                    )

    def _check_complexity(self, tree: ast.AST, result: AnalysisResult) -> None:
        """Verifica complejidad ciclomática."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._calculate_cyclomatic_complexity(node)
                if complexity > self.MAX_COMPLEXITY:
                    result.issues.append(
                        CodeIssue(
                            rule="HIGH_COMPLEXITY",
                            message=f"Function '{node.name}' has complexity {complexity}",
                            line=node.lineno,
                            severity=Severity.ERROR,
                            suggestion="Simplify logic, extract conditions, use polymorphism",
                        )
                    )

    def _calculate_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calcula complejidad ciclomática de una función."""
        complexity = 1  # Base
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                complexity += sum(1 for _ in child.generators)
        return complexity

    def _check_dead_code(self, tree: ast.AST, result: AnalysisResult) -> None:
        """Detecta código muerto potencial."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Verificar si hay código después de return
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Return) and i < len(node.body) - 1:
                        result.issues.append(
                            CodeIssue(
                                rule="DEAD_CODE",
                                message=f"Unreachable code after return in '{node.name}'",
                                line=node.body[i + 1].lineno,
                                severity=Severity.ERROR,
                                suggestion="Remove unreachable code",
                            )
                        )

    def _calculate_metrics(self, tree: ast.AST, code: str, result: AnalysisResult) -> None:
        """Calcula métricas del código."""
        result.metrics = {
            "total_lines": len(code.split("\n")),
            "blank_lines": sum(1 for line in code.split("\n") if not line.strip()),
            "comment_lines": sum(1 for line in code.split("\n") if line.strip().startswith("#")),
            "functions": sum(
                1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            "classes": sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef)),
        }


def format_report(result: AnalysisResult) -> str:
    """Formatea el resultado del análisis."""
    lines = [
        "=" * 60,
        "CLEAN CODE ANALYSIS REPORT",
        "=" * 60,
        f"File: {result.file_path}",
        f"Score: {result.score}/100",
        "",
        "METRICS:",
        f"  Total lines: {result.metrics.get('total_lines', 0)}",
        f"  Blank lines: {result.metrics.get('blank_lines', 0)}",
        f"  Comment lines: {result.metrics.get('comment_lines', 0)}",
        f"  Functions: {result.metrics.get('functions', 0)}",
        f"  Classes: {result.metrics.get('classes', 0)}",
        "",
    ]

    if result.issues:
        lines.append("ISSUES FOUND:")
        for issue in sorted(result.issues, key=lambda x: (x.severity.value, x.line)):
            severity_icon = {Severity.ERROR: "X", Severity.WARNING: "!", Severity.INFO: "i"}[
                issue.severity
            ]
            lines.append(f"  [{severity_icon}] Line {issue.line}: [{issue.rule}] {issue.message}")
            if issue.suggestion:
                lines.append(f"      Suggestion: {issue.suggestion}")
    else:
        lines.append("No issues found! Great job!")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# =============================================================================
# DEMO
# =============================================================================

SAMPLE_CODE = """
# This is a sample code with various clean code violations

def c(x):  # Bad naming
    # increment x by 1
    x = x + 1
    return x
    print("unreachable")  # Dead code

def process_user_data_and_send_email_notification_to_admin(a, b, c, d, e, f, g):
    # Too many parameters
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return True  # High complexity
    return False

class MyClass:
    def very_long_method_that_does_too_many_things_and_violates_srp(self):
        print("line 1")
        print("line 2")
        print("line 3")
        print("line 4")
        print("line 5")
        print("line 6")
        print("line 7")
        print("line 8")
        print("line 9")
        print("line 10")
        print("line 11")
        print("line 12")
        print("line 13")
        print("line 14")
        print("line 15")
        print("line 16")
        print("line 17")
        print("line 18")
        print("line 19")
        print("line 20")
        print("line 21")
        print("line 22")
        print("line 23")
        print("line 24")
        print("line 25")
        print("line 26")
        print("line 27")
        print("line 28")
        print("line 29")
        print("line 30")
        print("line 31")
        return None
"""


def main() -> None:
    """Demostración del analizador de código limpio."""
    print("\n" + "=" * 60)
    print("CLEAN CODE PRINCIPLES - Analizador")
    print("=" * 60)

    analyzer = CleanCodeAnalyzer()
    result = analyzer.analyze(SAMPLE_CODE, "sample.py")

    print(format_report(result))

    # Ejemplo de código limpio
    print("\n--- EJEMPLO DE CÓDIGO LIMPIO ---")
    clean_code = '''
def calculate_discount(price: float, discount_percentage: float) -> float:
    """Calculate the discounted price.

    Args:
        price: Original price in dollars
        discount_percentage: Discount as a percentage (0-100)

    Returns:
        The price after applying the discount
    """
    if not 0 <= discount_percentage <= 100:
        raise ValueError("Discount must be between 0 and 100")

    discount_amount = price * (discount_percentage / 100)
    return price - discount_amount
'''

    clean_result = analyzer.analyze(clean_code, "clean_example.py")
    print(format_report(clean_result))


if __name__ == "__main__":
    main()
