"""
Auto Verification Pipeline - Verificación automática antes de entregar

Este módulo verifica AUTOMÁTICAMENTE mi trabajo antes de entregarlo al usuario.
Es mi "segunda revisión" que previene errores tontos.
"""

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CheckType(Enum):
    """Tipo de verificación."""

    SYNTAX = "syntax"
    LINT = "lint"
    SECURITY = "security"
    STYLE = "style"
    LOGIC = "logic"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"


class Severity(Enum):
    """Severidad del problema."""

    CRITICAL = "critical"  # Bloquea entrega
    ERROR = "error"  # Debería corregir
    WARNING = "warning"  # Considerar
    INFO = "info"  # Sugerencia


@dataclass
class VerificationIssue:
    """Un problema encontrado."""

    check_type: CheckType
    severity: Severity
    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None
    suggestion: str | None = None
    auto_fixable: bool = False


@dataclass
class VerificationResult:
    """Resultado de la verificación."""

    passed: bool
    score: float  # 0.0 - 1.0
    issues: list[VerificationIssue] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    duration_ms: int = 0
    auto_fixed_count: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def should_block(self) -> bool:
        """¿Debería bloquear la entrega?"""
        return self.critical_count > 0


class AutoVerificationPipeline:
    """
    Pipeline de verificación automática.

    Ejecuta múltiples verificaciones sobre código/texto antes de entregar:
    1. Sintaxis - ¿Es código válido?
    2. Lint - ¿Sigue buenas prácticas?
    3. Seguridad - ¿Hay vulnerabilidades obvias?
    4. Estilo - ¿Es consistente?
    5. Completitud - ¿Está completo?
    6. Consistencia - ¿Es coherente con el contexto?
    """

    # Patrones de seguridad a detectar
    SECURITY_PATTERNS = {
        "hardcoded_password": (
            r'password\s*=\s*["\'][^"\']+["\']',
            Severity.CRITICAL,
            "Hardcoded password detected",
        ),
        "hardcoded_api_key": (
            r'api_key\s*=\s*["\'][^"\']+["\']',
            Severity.CRITICAL,
            "Hardcoded API key detected",
        ),
        "hardcoded_secret": (
            r'secret\s*=\s*["\'][^"\']+["\']',
            Severity.CRITICAL,
            "Hardcoded secret detected",
        ),
        "eval_usage": (
            r"\beval\s*\(",
            Severity.ERROR,
            "eval() is dangerous - consider safer alternatives",
        ),
        "exec_usage": (
            r"\bexec\s*\(",
            Severity.WARNING,
            "exec() can be dangerous - use with caution",
        ),
        "shell_true": (r"shell\s*=\s*True", Severity.WARNING, "shell=True can be a security risk"),
        "sql_injection": (
            r'execute\s*\(\s*f["\']|execute\s*\(\s*["\'].*%s',
            Severity.ERROR,
            "Potential SQL injection - use parameterized queries",
        ),
    }

    # Patrones de completitud
    INCOMPLETENESS_PATTERNS = [
        (r"TODO\s*:", Severity.WARNING, "Unresolved TODO"),
        (r"FIXME\s*:", Severity.WARNING, "Unresolved FIXME"),
        (r"XXX\s*:", Severity.WARNING, "Unresolved XXX"),
        (r"pass\s*#\s*TODO", Severity.ERROR, "Empty implementation with TODO"),
        (r"raise\s+NotImplementedError", Severity.ERROR, "NotImplementedError - incomplete"),
        (r"\.\.\.\s*$", Severity.WARNING, "Ellipsis placeholder"),
    ]

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.history: list[VerificationResult] = []

    def verify(
        self,
        content: str,
        content_type: str = "python",
        file_path: str | None = None,
        context: dict | None = None,
    ) -> VerificationResult:
        """
        Verifica contenido antes de entregarlo.

        Args:
            content: Código o texto a verificar
            content_type: Tipo ("python", "javascript", "typescript", "text", "markdown")
            file_path: Path del archivo (opcional)
            context: Contexto adicional (opcional)

        Returns:
            VerificationResult con todos los problemas encontrados
        """
        import time

        start = time.time()

        issues: list[VerificationIssue] = []
        checks_run: list[str] = []
        auto_fixed = 0

        # 1. Verificación de sintaxis
        if content_type == "python":
            syntax_issues = self._check_python_syntax(content)
            issues.extend(syntax_issues)
            checks_run.append("python_syntax")

            if not syntax_issues:  # Solo continuar si sintaxis OK
                # 2. Lint básico
                lint_issues = self._check_python_lint(content)
                issues.extend(lint_issues)
                checks_run.append("python_lint")

                # 3. Type hints
                type_issues = self._check_type_hints(content)
                issues.extend(type_issues)
                checks_run.append("type_hints")

        elif content_type in ["javascript", "typescript"]:
            js_issues = self._check_javascript(content)
            issues.extend(js_issues)
            checks_run.append("javascript_check")

        # 4. Seguridad (todos los tipos)
        security_issues = self._check_security(content)
        issues.extend(security_issues)
        checks_run.append("security")

        # 5. Completitud
        completeness_issues = self._check_completeness(content)
        issues.extend(completeness_issues)
        checks_run.append("completeness")

        # 6. Consistencia con contexto
        if context:
            consistency_issues = self._check_consistency(content, context)
            issues.extend(consistency_issues)
            checks_run.append("consistency")

        # Calcular score
        duration = int((time.time() - start) * 1000)
        score = self._calculate_score(issues)
        passed = score >= 0.7 and not any(i.severity == Severity.CRITICAL for i in issues)

        result = VerificationResult(
            passed=passed,
            score=score,
            issues=issues,
            checks_run=checks_run,
            duration_ms=duration,
            auto_fixed_count=auto_fixed,
        )

        self.history.append(result)
        return result

    def _check_python_syntax(self, code: str) -> list[VerificationIssue]:
        """Verifica sintaxis Python."""
        issues = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(
                VerificationIssue(
                    check_type=CheckType.SYNTAX,
                    severity=Severity.CRITICAL,
                    message=f"Syntax error: {e.msg}",
                    line=e.lineno,
                    column=e.offset,
                    suggestion="Fix the syntax error before proceeding",
                )
            )

        return issues

    def _check_python_lint(self, code: str) -> list[VerificationIssue]:
        """Verificación de lint básico para Python."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # Líneas muy largas
            if len(line) > 120:
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.LINT,
                        severity=Severity.WARNING,
                        message=f"Line too long ({len(line)} > 120 characters)",
                        line=i,
                        suggestion="Break into multiple lines",
                    )
                )

            # Trailing whitespace
            if line != line.rstrip():
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.STYLE,
                        severity=Severity.INFO,
                        message="Trailing whitespace",
                        line=i,
                        auto_fixable=True,
                    )
                )

            # Imports * (star imports)
            if re.match(r"from\s+\S+\s+import\s+\*", line):
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.LINT,
                        severity=Severity.WARNING,
                        message="Star import - prefer explicit imports",
                        line=i,
                        suggestion="Import specific names instead of *",
                    )
                )

            # Print statements (posible debug)
            if re.search(r"\bprint\s*\(", line) and "debug" not in line.lower():
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.LINT,
                        severity=Severity.INFO,
                        message="print() statement - is this debug code?",
                        line=i,
                        suggestion="Consider using logging instead",
                    )
                )

            # Bare except
            if re.match(r"\s*except\s*:", line):
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.LINT,
                        severity=Severity.WARNING,
                        message="Bare except clause - catches all exceptions",
                        line=i,
                        suggestion="Specify exception type: except SomeException:",
                    )
                )

        return issues

    def _check_type_hints(self, code: str) -> list[VerificationIssue]:
        """Verifica uso de type hints en Python."""
        issues = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Verificar si tiene return type hint
                    if node.returns is None and node.name != "__init__":
                        # Solo advertir para funciones públicas
                        if not node.name.startswith("_"):
                            issues.append(
                                VerificationIssue(
                                    check_type=CheckType.STYLE,
                                    severity=Severity.INFO,
                                    message=f"Function '{node.name}' missing return type hint",
                                    line=node.lineno,
                                    suggestion=f"Add return type: def {node.name}(...) -> ReturnType:",
                                )
                            )

        except Exception:
            pass

        return issues

    def _check_javascript(self, code: str) -> list[VerificationIssue]:
        """Verificaciones básicas para JavaScript/TypeScript."""
        issues = []

        # console.log
        if "console.log" in code:
            issues.append(
                VerificationIssue(
                    check_type=CheckType.LINT,
                    severity=Severity.INFO,
                    message="console.log found - is this debug code?",
                    suggestion="Remove before production",
                )
            )

        # eval()
        if re.search(r"\beval\s*\(", code):
            issues.append(
                VerificationIssue(
                    check_type=CheckType.SECURITY,
                    severity=Severity.ERROR,
                    message="eval() is dangerous",
                    suggestion="Use safer alternatives like JSON.parse()",
                )
            )

        # innerHTML
        if "innerHTML" in code:
            issues.append(
                VerificationIssue(
                    check_type=CheckType.SECURITY,
                    severity=Severity.WARNING,
                    message="innerHTML can lead to XSS",
                    suggestion="Use textContent or sanitize input",
                )
            )

        # var instead of let/const
        if re.search(r"\bvar\s+", code):
            issues.append(
                VerificationIssue(
                    check_type=CheckType.LINT,
                    severity=Severity.INFO,
                    message="'var' is outdated",
                    suggestion="Use 'let' or 'const' instead",
                )
            )

        return issues

    def _check_security(self, code: str) -> list[VerificationIssue]:
        """Verificaciones de seguridad."""
        issues = []

        for _pattern_name, (pattern, severity, message) in self.SECURITY_PATTERNS.items():
            matches = list(re.finditer(pattern, code, re.IGNORECASE))
            for match in matches:
                line_num = code[: match.start()].count("\n") + 1
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.SECURITY,
                        severity=severity,
                        message=message,
                        line=line_num,
                        suggestion="Use environment variables for sensitive data",
                    )
                )

        return issues

    def _check_completeness(self, code: str) -> list[VerificationIssue]:
        """Verifica que el código está completo."""
        issues = []

        for pattern, severity, message in self.INCOMPLETENESS_PATTERNS:
            matches = list(re.finditer(pattern, code, re.IGNORECASE))
            for match in matches:
                line_num = code[: match.start()].count("\n") + 1
                context = match.group()[:50]
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.COMPLETENESS,
                        severity=severity,
                        message=f"{message}: {context}",
                        line=line_num,
                        suggestion="Complete or remove before delivery",
                    )
                )

        return issues

    def _check_consistency(self, code: str, context: dict) -> list[VerificationIssue]:
        """Verifica consistencia con el contexto."""
        issues = []

        # Verificar naming conventions
        expected_style = context.get("naming_style", "snake_case")
        if expected_style == "snake_case":
            # Buscar camelCase en Python
            camel_funcs = re.findall(r"def\s+([a-z]+[A-Z][a-zA-Z]*)\s*\(", code)
            for func in camel_funcs:
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.CONSISTENCY,
                        severity=Severity.INFO,
                        message=f"Function '{func}' uses camelCase, expected snake_case",
                        suggestion=f"Rename to {self._to_snake_case(func)}",
                    )
                )

        # Verificar imports consistentes
        expected_imports = context.get("standard_imports", [])
        for imp in expected_imports:
            if imp not in code:
                issues.append(
                    VerificationIssue(
                        check_type=CheckType.CONSISTENCY,
                        severity=Severity.INFO,
                        message=f"Expected import '{imp}' not found",
                        suggestion=f"Add: import {imp}",
                    )
                )

        return issues

    def _to_snake_case(self, name: str) -> str:
        """Convierte camelCase a snake_case."""
        return re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")

    def _calculate_score(self, issues: list[VerificationIssue]) -> float:
        """Calcula score de la verificación."""
        if not issues:
            return 1.0

        penalties = {
            Severity.CRITICAL: 0.5,
            Severity.ERROR: 0.15,
            Severity.WARNING: 0.05,
            Severity.INFO: 0.01,
        }

        total_penalty = sum(penalties.get(i.severity, 0) for i in issues)
        return max(0.0, 1.0 - total_penalty)

    def verify_file(self, file_path: str) -> VerificationResult:
        """Verifica un archivo."""
        path = Path(file_path)

        if not path.exists():
            return VerificationResult(
                passed=False,
                score=0.0,
                issues=[
                    VerificationIssue(
                        check_type=CheckType.COMPLETENESS,
                        severity=Severity.CRITICAL,
                        message=f"File not found: {file_path}",
                    )
                ],
            )

        content = path.read_text(encoding="utf-8")
        content_type = self._detect_content_type(path)

        return self.verify(content, content_type, str(path))

    def _detect_content_type(self, path: Path) -> str:
        """Detecta tipo de contenido por extensión."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".md": "markdown",
            ".txt": "text",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        return ext_map.get(path.suffix.lower(), "text")

    def get_summary(self) -> dict:
        """Obtiene resumen de verificaciones."""
        if not self.history:
            return {"total": 0, "passed": 0, "failed": 0}

        passed = sum(1 for v in self.history if v.passed)
        failed = len(self.history) - passed
        avg_score = sum(v.score for v in self.history) / len(self.history)

        return {
            "total": len(self.history),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(self.history),
            "average_score": avg_score,
            "total_issues": sum(len(v.issues) for v in self.history),
            "critical_issues": sum(v.critical_count for v in self.history),
        }


# Singleton
_pipeline: AutoVerificationPipeline | None = None


def get_verification_pipeline(project_root: str = ".") -> AutoVerificationPipeline:
    """Obtiene instancia singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AutoVerificationPipeline(project_root)
    return _pipeline


def quick_verify(content: str, content_type: str = "python") -> VerificationResult:
    """Verificación rápida de contenido."""
    return get_verification_pipeline().verify(content, content_type)
