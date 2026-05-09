"""
Output Verification Module - Verificacion de outputs antes de entrega

Asegura calidad de outputs mediante verificaciones automaticas.
"""

import ast
import re
from dataclasses import dataclass, field
from enum import Enum


class VerificationType(Enum):
    """Tipo de verificacion."""

    SYNTAX = "syntax"
    LINT = "lint"
    TYPE_CHECK = "type_check"
    SECURITY = "security"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"


class Severity(Enum):
    """Severidad de issue."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class VerificationIssue:
    """Issue encontrado durante verificacion."""

    verification_type: VerificationType
    severity: Severity
    message: str
    location: str | None = None
    line: int | None = None
    suggestion: str | None = None
    auto_fixable: bool = False


@dataclass
class VerificationResult:
    """Resultado de verificacion."""

    passed: bool
    score: float  # 0-1
    issues: list[VerificationIssue] = field(default_factory=list)
    checks_performed: list[str] = field(default_factory=list)
    auto_fixed: int = 0
    duration_ms: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)


class OutputVerification:
    """
    Motor de verificacion de outputs.

    Verifica codigo, texto, y otros outputs antes de entregarlos.
    """

    def __init__(self, auto_fix: bool = True):
        self.auto_fix = auto_fix
        self.verification_history: list[VerificationResult] = []

    def verify_code(
        self, code: str, language: str = "python", file_path: str | None = None
    ) -> VerificationResult:
        """
        Verifica codigo.

        Args:
            code: Codigo a verificar
            language: Lenguaje del codigo
            file_path: Path opcional del archivo

        Returns:
            VerificationResult
        """
        import time

        start = time.time()

        issues = []
        checks = []
        auto_fixed = 0

        if language == "python":
            # Verificacion de sintaxis
            syntax_issues = self._check_python_syntax(code)
            issues.extend(syntax_issues)
            checks.append("python_syntax")

            if not syntax_issues:
                # Verificaciones adicionales solo si sintaxis OK
                lint_issues, fixed = self._check_python_lint(code)
                issues.extend(lint_issues)
                auto_fixed += fixed
                checks.append("python_lint")

                type_issues = self._check_python_imports(code)
                issues.extend(type_issues)
                checks.append("python_imports")

        elif language in ["javascript", "typescript"]:
            js_issues = self._check_javascript(code)
            issues.extend(js_issues)
            checks.append("javascript_check")

        # Verificaciones generales
        security_issues = self._check_security_patterns(code)
        issues.extend(security_issues)
        checks.append("security_patterns")

        completeness_issues = self._check_completeness(code, language)
        issues.extend(completeness_issues)
        checks.append("completeness")

        duration = int((time.time() - start) * 1000)

        # Calcular score
        score = self._calculate_score(issues)

        result = VerificationResult(
            passed=score >= 0.7 and not any(i.severity == Severity.CRITICAL for i in issues),
            score=score,
            issues=issues,
            checks_performed=checks,
            auto_fixed=auto_fixed,
            duration_ms=duration,
        )

        self.verification_history.append(result)
        return result

    def _check_python_syntax(self, code: str) -> list[VerificationIssue]:
        """Verifica sintaxis Python."""
        issues = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.SYNTAX,
                    severity=Severity.CRITICAL,
                    message=f"Syntax error: {e.msg}",
                    line=e.lineno,
                    suggestion="Fix the syntax error before proceeding",
                )
            )

        return issues

    def _check_python_lint(self, code: str) -> tuple[list[VerificationIssue], int]:
        """Ejecuta linting en Python."""
        issues = []
        fixed = 0

        # Verificaciones basicas sin herramientas externas
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # Lineas muy largas
            if len(line) > 120:
                issues.append(
                    VerificationIssue(
                        verification_type=VerificationType.LINT,
                        severity=Severity.WARNING,
                        message=f"Line too long ({len(line)} > 120)",
                        line=i,
                        suggestion="Break line into multiple lines",
                    )
                )

            # Trailing whitespace
            if line.endswith(" ") or line.endswith("\t"):
                issues.append(
                    VerificationIssue(
                        verification_type=VerificationType.LINT,
                        severity=Severity.INFO,
                        message="Trailing whitespace",
                        line=i,
                        auto_fixable=True,
                    )
                )
                if self.auto_fix:
                    fixed += 1

            # Print statements (podrian ser debug)
            if re.search(r"\bprint\s*\(", line):
                issues.append(
                    VerificationIssue(
                        verification_type=VerificationType.LINT,
                        severity=Severity.INFO,
                        message="Print statement found (debug code?)",
                        line=i,
                        suggestion="Consider using logging instead",
                    )
                )

        return issues, fixed

    def _check_python_imports(self, code: str) -> list[VerificationIssue]:
        """Verifica imports en Python."""
        issues = []

        try:
            tree = ast.parse(code)

            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Verificar imports sospechosos
            suspicious = ["pickle", "eval", "exec", "os.system", "subprocess"]
            for imp in imports:
                if any(s in imp for s in suspicious):
                    issues.append(
                        VerificationIssue(
                            verification_type=VerificationType.SECURITY,
                            severity=Severity.WARNING,
                            message=f"Potentially unsafe import: {imp}",
                            suggestion="Review security implications",
                        )
                    )

        except Exception:
            pass

        return issues

    def _check_javascript(self, code: str) -> list[VerificationIssue]:
        """Verificaciones basicas para JavaScript."""
        issues = []

        # Console.log
        if "console.log" in code:
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.LINT,
                    severity=Severity.INFO,
                    message="console.log found (debug code?)",
                    suggestion="Remove before production",
                )
            )

        # eval()
        if re.search(r"\beval\s*\(", code):
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.SECURITY,
                    severity=Severity.ERROR,
                    message="eval() is dangerous",
                    suggestion="Use safer alternatives",
                )
            )

        # innerHTML
        if "innerHTML" in code:
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.SECURITY,
                    severity=Severity.WARNING,
                    message="innerHTML can lead to XSS",
                    suggestion="Use textContent or sanitize input",
                )
            )

        return issues

    def _check_security_patterns(self, code: str) -> list[VerificationIssue]:
        """Verifica patrones de seguridad."""
        issues = []

        # Passwords/secrets hardcodeados
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'token\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']', "Hardcoded token"),
        ]

        for pattern, message in secret_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(
                    VerificationIssue(
                        verification_type=VerificationType.SECURITY,
                        severity=Severity.CRITICAL,
                        message=message,
                        suggestion="Use environment variables instead",
                    )
                )

        # SQL Injection patterns
        sql_patterns = [
            r'execute\s*\(\s*["\'].*%s',
            r'execute\s*\(\s*f["\']',
            r'cursor\.execute\s*\(\s*["\'].*\+',
        ]

        for pattern in sql_patterns:
            if re.search(pattern, code):
                issues.append(
                    VerificationIssue(
                        verification_type=VerificationType.SECURITY,
                        severity=Severity.ERROR,
                        message="Potential SQL injection",
                        suggestion="Use parameterized queries",
                    )
                )

        return issues

    def _check_completeness(self, code: str, language: str) -> list[VerificationIssue]:
        """Verifica completitud del codigo."""
        issues = []

        # TODO/FIXME sin resolver
        todo_matches = re.finditer(r"(TODO|FIXME|XXX|HACK)\s*:?\s*(.+)", code, re.IGNORECASE)
        for match in todo_matches:
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.COMPLETENESS,
                    severity=Severity.WARNING,
                    message=f"Unresolved {match.group(1)}: {match.group(2)[:50]}",
                    suggestion="Complete or remove before delivery",
                )
            )

        # Placeholders
        placeholders = ["...", "pass  # TODO", "raise NotImplementedError"]
        for ph in placeholders:
            if ph in code:
                issues.append(
                    VerificationIssue(
                        verification_type=VerificationType.COMPLETENESS,
                        severity=Severity.WARNING,
                        message=f"Placeholder found: {ph}",
                        suggestion="Implement the missing code",
                    )
                )

        return issues

    def _calculate_score(self, issues: list[VerificationIssue]) -> float:
        """Calcula score de verificacion."""
        if not issues:
            return 1.0

        # Penalizaciones por severidad
        penalties = {
            Severity.CRITICAL: 0.4,
            Severity.ERROR: 0.2,
            Severity.WARNING: 0.05,
            Severity.INFO: 0.01,
        }

        total_penalty = sum(penalties.get(i.severity, 0) for i in issues)
        return max(0.0, 1.0 - total_penalty)

    def verify_text(self, text: str, expected_language: str | None = None) -> VerificationResult:
        """
        Verifica texto.

        Args:
            text: Texto a verificar
            expected_language: Idioma esperado

        Returns:
            VerificationResult
        """
        _ = expected_language  # hook reservado para detector de idioma
        issues = []
        checks = []

        # Verificar que no este vacio
        if not text.strip():
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.COMPLETENESS,
                    severity=Severity.ERROR,
                    message="Text is empty",
                )
            )

        # Verificar longitud minima
        if len(text.strip()) < 10:
            issues.append(
                VerificationIssue(
                    verification_type=VerificationType.COMPLETENESS,
                    severity=Severity.WARNING,
                    message="Text is very short",
                )
            )

        checks.append("text_completeness")

        score = self._calculate_score(issues)

        return VerificationResult(
            passed=score >= 0.7, score=score, issues=issues, checks_performed=checks
        )

    def get_verification_summary(self) -> dict:
        """Obtiene resumen de verificaciones."""
        if not self.verification_history:
            return {"total": 0, "passed": 0, "failed": 0}

        passed = sum(1 for v in self.verification_history if v.passed)
        failed = len(self.verification_history) - passed

        avg_score = sum(v.score for v in self.verification_history) / len(self.verification_history)

        return {
            "total": len(self.verification_history),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(self.verification_history),
            "average_score": avg_score,
            "total_issues": sum(len(v.issues) for v in self.verification_history),
            "total_auto_fixed": sum(v.auto_fixed for v in self.verification_history),
        }


# Singleton
_output_verification: OutputVerification | None = None


def get_output_verification(auto_fix: bool = True) -> OutputVerification:
    """Obtiene instancia singleton."""
    global _output_verification
    if _output_verification is None:
        _output_verification = OutputVerification(auto_fix)
    return _output_verification
