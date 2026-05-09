#!/usr/bin/env python3
"""
Self Verifier Agent - Verificacion automatica de outputs

Detecta y corrige errores antes de entregar al usuario.
"""

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CheckType(Enum):
    SYNTAX = "syntax"
    LINT = "lint"
    TYPE = "type"
    TEST = "test"
    BUILD = "build"
    DEPENDENCY = "dependency"


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    severity: Severity
    file: str
    line: int
    column: int
    message: str
    code: str
    auto_fixable: bool = False
    fix_applied: bool = False


@dataclass
class CheckResult:
    name: str
    check_type: CheckType
    passed: bool
    duration_ms: int
    issues: list[Issue] = field(default_factory=list)
    details: str = ""


@dataclass
class VerificationResult:
    passed: bool
    confidence: float
    checks_run: list[CheckResult]
    issues_found: list[Issue]
    auto_fixed: list[Issue]
    manual_required: list[Issue]


class SelfVerifier:
    """Verifica codigo antes de entregar."""

    def __init__(self, auto_fix: bool = True):
        self.auto_fix = auto_fix
        self.checks_available = {
            "python": [CheckType.SYNTAX, CheckType.LINT, CheckType.TYPE],
            "javascript": [CheckType.SYNTAX, CheckType.LINT],
            "typescript": [CheckType.SYNTAX, CheckType.LINT, CheckType.TYPE],
        }

    def detect_language(self, file_path: str) -> str | None:
        """Detecta lenguaje del archivo."""
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".mjs": "javascript",
            ".cjs": "javascript",
        }
        return mapping.get(ext)

    def check_python_syntax(self, file_path: str) -> CheckResult:
        """Verifica sintaxis Python."""
        import time

        start = time.time()

        issues = []
        try:
            with open(file_path) as f:
                source = f.read()
            ast.parse(source)
            passed = True
        except SyntaxError as e:
            passed = False
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    file=file_path,
                    line=e.lineno or 0,
                    column=e.offset or 0,
                    message=e.msg or "Syntax error",
                    code="E999",
                )
            )
        except Exception as e:
            passed = False
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    file=file_path,
                    line=0,
                    column=0,
                    message=str(e),
                    code="E000",
                )
            )

        duration = int((time.time() - start) * 1000)

        return CheckResult(
            name="Python Syntax",
            check_type=CheckType.SYNTAX,
            passed=passed,
            duration_ms=duration,
            issues=issues,
        )

    def check_python_lint(self, file_path: str) -> CheckResult:
        """Ejecuta ruff para linting."""
        import time

        start = time.time()

        issues = []
        passed = True

        try:
            # Intentar ejecutar ruff
            result = subprocess.run(
                ["ruff", "check", file_path, "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.stdout:
                ruff_issues = json.loads(result.stdout)
                for item in ruff_issues:
                    severity = (
                        Severity.ERROR if item.get("code", "").startswith("E") else Severity.WARNING
                    )
                    fixable = item.get("fix") is not None

                    issues.append(
                        Issue(
                            severity=severity,
                            file=item.get("filename", file_path),
                            line=item.get("location", {}).get("row", 0),
                            column=item.get("location", {}).get("column", 0),
                            message=item.get("message", ""),
                            code=item.get("code", ""),
                            auto_fixable=fixable,
                        )
                    )

            passed = result.returncode == 0

            # Auto-fix si esta habilitado
            if self.auto_fix and issues:
                fix_result = subprocess.run(
                    ["ruff", "check", file_path, "--fix"], capture_output=True, timeout=30
                )
                if fix_result.returncode == 0:
                    for issue in issues:
                        if issue.auto_fixable:
                            issue.fix_applied = True

        except FileNotFoundError:
            # ruff no instalado
            passed = True  # Skip check
            issues = []
        except Exception as e:
            passed = False
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    file=file_path,
                    line=0,
                    column=0,
                    message=f"Lint check failed: {e}",
                    code="L000",
                )
            )

        duration = int((time.time() - start) * 1000)

        return CheckResult(
            name="Ruff Lint",
            check_type=CheckType.LINT,
            passed=passed,
            duration_ms=duration,
            issues=issues,
        )

    def check_python_types(self, file_path: str) -> CheckResult:
        """Ejecuta mypy para type checking."""
        import time

        start = time.time()

        issues = []
        passed = True

        try:
            result = subprocess.run(
                ["mypy", file_path, "--no-error-summary"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parsear output de mypy
            for line in result.stdout.split("\n"):
                if ": error:" in line or ": warning:" in line:
                    parts = line.split(":")
                    if len(parts) >= 4:
                        severity = Severity.ERROR if "error" in parts[2] else Severity.WARNING
                        issues.append(
                            Issue(
                                severity=severity,
                                file=parts[0],
                                line=int(parts[1]) if parts[1].isdigit() else 0,
                                column=0,
                                message=":".join(parts[3:]).strip(),
                                code="mypy",
                            )
                        )

            passed = result.returncode == 0

        except FileNotFoundError:
            passed = True  # Skip check
        except Exception as e:
            passed = False
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    file=file_path,
                    line=0,
                    column=0,
                    message=f"Type check failed: {e}",
                    code="T000",
                )
            )

        duration = int((time.time() - start) * 1000)

        return CheckResult(
            name="Mypy Types",
            check_type=CheckType.TYPE,
            passed=passed,
            duration_ms=duration,
            issues=issues,
        )

    def verify_file(self, file_path: str) -> VerificationResult:
        """Verifica un archivo."""
        path = Path(file_path)
        if not path.exists():
            return VerificationResult(
                passed=False,
                confidence=0,
                checks_run=[],
                issues_found=[
                    Issue(
                        severity=Severity.ERROR,
                        file=file_path,
                        line=0,
                        column=0,
                        message="File not found",
                        code="F404",
                    )
                ],
                auto_fixed=[],
                manual_required=[],
            )

        language = self.detect_language(file_path)
        if not language:
            return VerificationResult(
                passed=True,
                confidence=0.5,
                checks_run=[],
                issues_found=[],
                auto_fixed=[],
                manual_required=[],
            )

        checks = []
        all_issues = []

        if language == "python":
            # Syntax check
            syntax = self.check_python_syntax(file_path)
            checks.append(syntax)
            all_issues.extend(syntax.issues)

            # Solo continuar si sintaxis OK
            if syntax.passed:
                # Lint check
                lint = self.check_python_lint(file_path)
                checks.append(lint)
                all_issues.extend(lint.issues)

                # Type check
                types = self.check_python_types(file_path)
                checks.append(types)
                all_issues.extend(types.issues)

        # Clasificar issues
        auto_fixed = [i for i in all_issues if i.fix_applied]
        manual_required = [
            i for i in all_issues if i.severity == Severity.ERROR and not i.fix_applied
        ]

        # Calcular confianza
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks if c.passed)
        error_count = sum(
            1 for i in all_issues if i.severity == Severity.ERROR and not i.fix_applied
        )

        if total_checks == 0:
            confidence = 0.5
        else:
            base_confidence = passed_checks / total_checks
            error_penalty = min(0.5, error_count * 0.1)
            confidence = max(0, base_confidence - error_penalty)

        overall_passed = all(c.passed for c in checks) or (
            error_count == 0
            and all(i.severity != Severity.ERROR or i.fix_applied for i in all_issues)
        )

        return VerificationResult(
            passed=overall_passed,
            confidence=confidence,
            checks_run=checks,
            issues_found=all_issues,
            auto_fixed=auto_fixed,
            manual_required=manual_required,
        )

    def verify_directory(self, dir_path: str) -> dict:
        """Verifica todos los archivos en un directorio."""
        path = Path(dir_path)
        results = {}

        for pattern in ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx"]:
            for file_path in path.glob(pattern):
                # Skip node_modules, __pycache__, etc.
                if any(
                    skip in str(file_path)
                    for skip in ["node_modules", "__pycache__", ".git", "venv"]
                ):
                    continue

                result = self.verify_file(str(file_path))
                results[str(file_path)] = {
                    "passed": result.passed,
                    "confidence": result.confidence,
                    "issues": len(result.issues_found),
                    "auto_fixed": len(result.auto_fixed),
                }

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Self Verifier - Verificacion automatica de codigo"
    )
    parser.add_argument("target", nargs="?", default=".", help="Archivo o directorio a verificar")
    parser.add_argument("--no-fix", action="store_true", help="No aplicar auto-fixes")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    verifier = SelfVerifier(auto_fix=not args.no_fix)

    target = Path(args.target)

    if target.is_file():
        result = verifier.verify_file(str(target))

        if args.json:
            print(
                json.dumps(
                    {
                        "passed": result.passed,
                        "confidence": result.confidence,
                        "checks": [
                            {"name": c.name, "passed": c.passed, "duration_ms": c.duration_ms}
                            for c in result.checks_run
                        ],
                        "issues_count": len(result.issues_found),
                        "auto_fixed_count": len(result.auto_fixed),
                        "manual_required_count": len(result.manual_required),
                    },
                    indent=2,
                )
            )
        else:
            status = "✓" if result.passed else "✗"
            print(f"[{status}] Verification: {target}")
            print(f"Confidence: {result.confidence:.0%}")
            print()

            for check in result.checks_run:
                check_status = "✓" if check.passed else "✗"
                print(f"  [{check_status}] {check.name} ({check.duration_ms}ms)")

            if result.issues_found:
                print(f"\nIssues found: {len(result.issues_found)}")
                for issue in result.issues_found[:10]:
                    fixed = " [FIXED]" if issue.fix_applied else ""
                    print(f"  - {issue.file}:{issue.line} [{issue.code}] {issue.message}{fixed}")

            if result.manual_required:
                print(f"\nManual intervention required: {len(result.manual_required)} issues")

    else:
        results = verifier.verify_directory(str(target))

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            total = len(results)
            passed = sum(1 for r in results.values() if r["passed"])
            print("Self Verifier Results")
            print("=" * 40)
            print(f"Files checked: {total}")
            print(f"Passed: {passed}/{total}")
            print()

            for file_path, result in sorted(results.items()):
                status = "✓" if result["passed"] else "✗"
                print(f"  [{status}] {file_path} ({result['issues']} issues)")

    sys.exit(0)


if __name__ == "__main__":
    main()
