"""Security scan script implementing the 6-phase OWASP audit protocol.

This module performs static analysis security scans targeting OWASP Top 10 2021.
"""
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Finding severity classification."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class OwaspCategory(str, Enum):
    """OWASP Top 10 2021 categories."""

    A01_BROKEN_ACCESS_CONTROL = "A01:2021 - Broken Access Control"
    A02_CRYPTOGRAPHIC_FAILURES = "A02:2021 - Cryptographic Failures"
    A03_INJECTION = "A03:2021 - Injection"
    A04_INSECURE_DESIGN = "A04:2021 - Insecure Design"
    A05_SECURITY_MISCONFIGURATION = "A05:2021 - Security Misconfiguration"
    A06_VULNERABLE_COMPONENTS = "A06:2021 - Vulnerable and Outdated Components"
    A07_AUTH_FAILURES = "A07:2021 - Identification and Authentication Failures"
    A08_DATA_INTEGRITY_FAILURES = "A08:2021 - Software and Data Integrity Failures"
    A09_SECURITY_LOGGING_FAILURES = "A09:2021 - Security Logging and Monitoring Failures"
    A10_SSRF = "A10:2021 - Server-Side Request Forgery"


class StrideCategory(str, Enum):
    """STRIDE threat modeling categories."""

    SPOOFING = "Spoofing"
    TAMPERING = "Tampering"
    REPUDIATION = "Repudiation"
    INFORMATION_DISCLOSURE = "Information Disclosure"
    DENIAL_OF_SERVICE = "Denial of Service"
    ELEVATION_OF_PRIVILEGE = "Elevation of Privilege"


@dataclass
class Finding:
    """Represents a security finding."""

    severity: Severity
    category: OwaspCategory
    stride: StrideCategory
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    evidence: str = ""
    recommendation: str = ""
    cwe: str | None = None


@dataclass
class ScanResult:
    """Result of a security scan."""

    target_path: str
    status: str
    findings: list[Finding] = field(default_factory=list)
    owasp_compliance: dict[str, str] = field(default_factory=dict)
    scan_duration_seconds: float = 0.0
    files_scanned: int = 0
    errors: list[str] = field(default_factory=list)


class SecurityScanner:
    """Implements the 6-phase OWASP security scan protocol."""

    # File extensions to scan
    CODE_EXTENSIONS = ["*.ts", "*.tsx", "*.js", "*.jsx", "*.py", "*.java", "*.go", "*.rs"]

    # Patterns for secret detection (false positive keywords to exclude)
    SAFE_PATTERNS = [
        "process.env",
        "import.meta.env",
        "os.environ",
        "os.getenv",
        "os.getenvb",
        "process.argv",
        "placeholder",
        "example",
        "YOUR_",
        "[YOUR_",
        "# TODO",
        "TODO:",
        "REPLACE_WITH",
    ]

    def __init__(self, target_path: str) -> None:
        """Initialize scanner.

        Args:
            target_path: Root path to scan.
        """
        self.target_path = Path(target_path)
        self.findings: list[Finding] = []
        self.files_scanned = 0
        self.errors: list[str] = []

        # Initialize OWASP compliance matrix
        self.owasp_compliance = {
            cat.value: "NOT_CHECKED" for cat in OwaspCategory
        }

    def run_full_scan(
        self, scope: str = "full", focus_areas: list[str] | None = None
    ) -> ScanResult:
        """Run complete security scan.

        Args:
            scope: 'full' or 'incremental'.
            focus_areas: Optional list of specific OWASP categories to focus on.

        Returns:
            ScanResult with all findings.
        """
        start_time = time.time()

        logger.info("Starting full security scan on %s", self.target_path)

        # Phase 1: Input Validation Analysis
        self._scan_input_validation()

        # Phase 2: SQL Injection Risk Assessment
        self._scan_sql_injection()

        # Phase 3: XSS Vulnerability Detection
        self._scan_xss()

        # Phase 4: Authentication & Authorization Audit
        self._scan_auth()

        # Phase 5: Secret Detection
        self._scan_secrets()

        # Phase 6: OWASP Top 10 Compliance Check
        self._scan_owasp_compliance()

        duration = time.time() - start_time

        result = ScanResult(
            target_path=str(self.target_path),
            status="completed",
            findings=self.findings,
            owasp_compliance=self.owasp_compliance,
            scan_duration_seconds=duration,
            files_scanned=self.files_scanned,
            errors=self.errors,
        )

        logger.info(
            "Scan completed: %d findings in %.2fs",
            len(self.findings),
            duration,
        )

        return result

    def _run_grep(
        self, pattern: str, extensions: list[str] | None = None
    ) -> list[tuple[str, int, str]]:
        """Run grep-like search on target path.

        Args:
            pattern: Regex pattern.
            extensions: List of glob patterns like ['*.ts', '*.js'].

        Returns:
            List of (file_path, line_number, line_content).
        """
        results: list[tuple[str, int, str]] = []

        try:
            # Build find command
            find_cmd = ["find", str(self.target_path), "-type", "f"]

            if extensions:
                ext_args = []
                for ext in extensions:
                    ext_args.extend(["-name", ext])
                find_cmd.extend(["(",] + ext_args + [")"])

            find_proc = subprocess.run(
                find_cmd,
                capture_output=True,
                text=True,
                shell=False,
            )

            if find_proc.returncode != 0:
                logger.warning("find command failed: %s", find_proc.stderr)
                return []

            files = [
                f.strip()
                for f in find_proc.stdout.strip().split("\n")
                if f.strip()
            ]
            self.files_scanned += len(files)

            # Search each file with grep
            for file_path in files:
                try:
                    grep_cmd = ["grep", "-n", "-E", pattern, file_path]
                    grep_proc = subprocess.run(
                        grep_cmd,
                        capture_output=True,
                        text=True,
                        shell=False,
                    )

                    if grep_proc.returncode == 0:
                        for line in grep_proc.stdout.strip().split("\n"):
                            if not line.strip():
                                continue
                            parts = line.split(":", 2)
                            if len(parts) >= 3:
                                line_no = int(parts[0])
                                content = parts[2]
                                results.append((file_path, line_no, content))
                except Exception as e:
                    logger.debug("Error grepping %s: %s", file_path, e)
                    continue

        except Exception as e:
            logger.error("Error running grep: %s", e)
            self.errors.append(f"grep error: {e}")

        return results

    def _scan_input_validation(self) -> None:
        """Phase 1: Scan for input validation issues."""
        logger.info("Phase 1: Input Validation Analysis")

        # Patterns that suggest missing input validation
        patterns = [
            # Request handlers without body parsing validation
            (r"req\.(body|params|query)\s*[.[]", "Potential unvalidated input access", Severity.MEDIUM),
            # Express route handlers accepting raw body
            (r"app\.(post|put|patch)\([^)]*\)", "Route handler without visible input validation", Severity.LOW),
            # FastAPI route without dependency injection for validation
            (r"@app\.(post|put|patch)\([^)]*def\s+\w+\([^)]*\):", "FastAPI route may lack validation", Severity.LOW),
        ]

        for pattern, description, severity in patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A03_INJECTION,
                        stride=StrideCategory.TAMPERING,
                        title=f"Input Validation: {description}",
                        description=f"Potential input validation issue at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Implement input validation using a validation library (e.g., Zod, Yup, Pydantic). Never trust user input.",
                        cwe="CWE-20: Improper Input Validation",
                    )
                )

        self.owasp_compliance[OwaspCategory.A03_INJECTION.value] = (
            "FAIL" if self._has_finding_category(OwaspCategory.A03_INJECTION) else "PASS"
        )

    def _scan_sql_injection(self) -> None:
        """Phase 2: Scan for SQL injection vulnerabilities."""
        logger.info("Phase 2: SQL Injection Risk Assessment")

        sql_patterns = [
            # String interpolation in SQL queries
            (r'f["\'].*SELECT.*\{', "SQL query with string interpolation", Severity.CRITICAL),
            (r'f["\'].*INSERT.*\{', "SQL query with string interpolation", Severity.CRITICAL),
            (r'f["\'].*UPDATE.*\{', "SQL query with string interpolation", Severity.CRITICAL),
            (r'f["\'].*DELETE.*\{', "SQL query with string interpolation", Severity.CRITICAL),
            (r'f["\'].*WHERE.*\{', "SQL query with string interpolation", Severity.CRITICAL),
            # execute() with format string
            (r"execute\([^)]*%s[^)]*\+", "Potential SQL concatenation", Severity.HIGH),
            (r"execute\([^)]*format\(", "SQL execute with format()", Severity.HIGH),
            # Raw SQL without ORM
            (r"cursor\.execute\([^)]f[\"\'", "Raw cursor.execute with f-string", Severity.CRITICAL),
        ]

        for pattern, description, severity in sql_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A03_INJECTION,
                        stride=StrideCategory.TAMPERING,
                        title=f"SQL Injection: {description}",
                        description=f"SQL injection risk at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Use parameterized queries (prepared statements). Never concatenate user input into SQL strings.",
                        cwe="CWE-89: SQL Injection",
                    )
                )

        self.owasp_compliance[OwaspCategory.A03_INJECTION.value] = (
            "FAIL" if self._has_finding_category(OwaspCategory.A03_INJECTION) else "PASS"
        )

    def _scan_xss(self) -> None:
        """Phase 3: Scan for XSS vulnerabilities."""
        logger.info("Phase 3: XSS Vulnerability Detection")

        xss_patterns = [
            # innerHTML usage (XSS in JavaScript)
            (r"innerHTML\s*=", "innerHTML assignment (XSS risk)", Severity.HIGH),
            (r"outerHTML\s*=", "outerHTML assignment (XSS risk)", Severity.HIGH),
            # React dangerous patterns
            (r"dangerouslySetInnerHTML", "React dangerouslySetInnerHTML (XSS risk)", Severity.HIGH),
            # eval and similar
            (r"\beval\(", "eval() usage (Code Injection risk)", Severity.CRITICAL),
            (r"new Function\(", "new Function() usage (Code Injection risk)", Severity.HIGH),
            (r"setTimeout\([^,]+,\s*[^\)]*\)", "setTimeout with string (XSS risk)", Severity.HIGH),
            (r"setInterval\([^,]+,\s*[^\)]*\)", "setInterval with string (XSS risk)", Severity.HIGH),
            # Template literals with user input
            (r"`.*\$\{.*\}.*`", "Template literal with expression (verify escaping)", Severity.MEDIUM),
        ]

        for pattern, description, severity in xss_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A03_INJECTION,
                        stride=StrideCategory.INFORMATION_DISCLOSURE,
                        title=f"XSS: {description}",
                        description=f"XSS vulnerability at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Use textContent instead of innerHTML. For HTML, use DOMPurify. Avoid eval().",
                        cwe="CWE-79: Cross-site Scripting (XSS)",
                    )
                )

        self.owasp_compliance[OwaspCategory.A03_INJECTION.value] = (
            "FAIL" if self._has_finding_category(OwaspCategory.A03_INJECTION) else "PASS"
        )

    def _scan_auth(self) -> None:
        """Phase 4: Scan for authentication and authorization issues."""
        logger.info("Phase 4: Authentication & Authorization Audit")

        auth_patterns = [
            # Missing auth checks
            (r"app\.(get|post|put|patch|delete)\([^)]*\);", "Route without visible auth check", Severity.HIGH),
            (r"@app\.route\([^)]*methods=\[", "Flask route without @login_required", Severity.MEDIUM),
            # Token handling issues
            (r"localStorage\.setItem\(['\"]token", "Token stored in localStorage (XSS risk)", Severity.HIGH),
            (r"sessionStorage\.setItem\(['\"]token", "Token stored in sessionStorage (XSS risk)", Severity.HIGH),
            # Weak session management
            (r"cookie\s*=\s*[^;]*;?\s*expires\s*=\s*0", "Cookie with expire=0 (session not persisted)", Severity.LOW),
        ]

        for pattern, description, severity in auth_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A01_BROKEN_ACCESS_CONTROL,
                        stride=StrideCategory.ELEVATION_OF_PRIVILEGE,
                        title=f"Auth: {description}",
                        description=f"Authentication issue at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Implement proper authentication middleware. Use HttpOnly cookies for tokens. Never store tokens in localStorage.",
                        cwe="CWE-284: Access Control Not Enforced",
                    )
                )

        # Check for auth middleware presence
        auth_middleware = self._run_grep(
            r"requireAuth|@login_required|authenticate|isAuthenticated",
            extensions=self.CODE_EXTENSIONS,
        )
        if not auth_middleware:
            self.findings.append(
                Finding(
                    severity=Severity.INFO,
                    category=OwaspCategory.A01_BROKEN_ACCESS_CONTROL,
                    stride=StrideCategory.ELEVATION_OF_PRIVILEGE,
                    title="Auth: No authentication middleware detected",
                    description="No authentication decorators or middleware found in scanned code",
                    recommendation="Implement authentication middleware and apply to all protected routes.",
                )
            )

        self.owasp_compliance[OwaspCategory.A01_BROKEN_ACCESS_CONTROL.value] = (
            "FAIL" if self._has_finding_category(OwaspCategory.A01_BROKEN_ACCESS_CONTROL) else "PASS"
        )

    def _scan_secrets(self) -> None:
        """Phase 5: Scan for hardcoded secrets."""
        logger.info("Phase 5: Secret Detection")

        secret_patterns = [
            r"api[_-]?key",
            r"secret[_-]?key",
            r"access[_-]?token",
            r"auth[_-]?token",
            r"private[_-]?key",
            r"password\s*=\s*['\"][^'\"]+['\"]",
            r"passwd\s*=\s*['\"][^'\"]+['\"]",
            r"pwd\s*=\s*['\"][^'\"]+['\"]",
            r"Bearer\s+[A-Za-z0-9_-]{20,}",
            r"ghp_[A-Za-z0-9]{36,}",
            r"AKIA[A-Za-z0-9]{16,}",
        ]

        for pattern in secret_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                # Check if line is a safe pattern (env var, import, etc.)
                if any(safe in content for safe in self.SAFE_PATTERNS):
                    continue

                self.findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category=OwaspCategory.A02_CRYPTOGRAPHIC_FAILURES,
                        stride=StrideCategory.INFORMATION_DISCLOSURE,
                        title="Hardcoded Secret Detected",
                        description=f"Potential hardcoded secret at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Move secrets to environment variables. Use secret management service (e.g., AWS Secrets Manager, HashiCorp Vault). Never hardcode secrets in source code.",
                        cwe="CWE-798: Use of Hard-coded Credentials",
                    )
                )

        self.owasp_compliance[OwaspCategory.A02_CRYPTOGRAPHIC_FAILURES.value] = (
            "FAIL" if self._has_finding_category(OwaspCategory.A02_CRYPTOGRAPHIC_FAILURES) else "PASS"
        )

    def _scan_owasp_compliance(self) -> None:
        """Phase 6: Check OWASP Top 10 compliance."""
        logger.info("Phase 6: OWASP Top 10 2021 Compliance Check")

        # A04: Insecure Design - Check for missing business logic validation
        insecure_design_patterns = [
            (r"if\s*\([^)]*role\s*==\s*['\"]admin", "Hardcoded role check (should use policy)", Severity.MEDIUM),
            (r"eval\(", "Dynamic code execution", Severity.HIGH),
        ]

        for pattern, description, severity in insecure_design_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A04_INSECURE_DESIGN,
                        stride=StrideCategory.TAMPERING,
                        title=f"Insecure Design: {description}",
                        description=f"Insecure design pattern at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Use policy-based access control. Implement server-side validation for all business logic.",
                    )
                )

        # A05: Security Misconfiguration
        cors_patterns = [
            (r"CORS\([^)]*origin\s*:\s*['\"]\*['\"]", "CORS wildcard origin", Severity.HIGH),
            (r"accessControlAllowOrigin\s*:\s*['\"]\*['\"]", "CORS wildcard origin", Severity.HIGH),
        ]

        for pattern, description, severity in cors_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A05_SECURITY_MISCONFIGURATION,
                        stride=StrideCategory.INFORMATION_DISCLOSURE,
                        title=f"Misconfiguration: {description}",
                        description=f"Security misconfiguration at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Never use wildcard CORS (*). Specify exact origins that need access.",
                        cwe="CWE-942: Permissive Cross-domain White List",
                    )
                )

        # A10: Server-Side Request Forgery (SSRF)
        ssrf_patterns = [
            (r"fetch\([^)]*userInput", "Fetch with user input (SSRF risk)", Severity.HIGH),
            (r"axios\([^)]*url\s*:\s*[^,)]*user", "Axios request with user URL (SSRF risk)", Severity.HIGH),
            (r"requests\.get\([^)]*\(", "Python requests with user input (SSRF risk)", Severity.HIGH),
        ]

        for pattern, description, severity in ssrf_patterns:
            matches = self._run_grep(pattern, extensions=self.CODE_EXTENSIONS)
            for file_path, line_no, content in matches:
                self.findings.append(
                    Finding(
                        severity=severity,
                        category=OwaspCategory.A10_SSRF,
                        stride=StrideCategory.ELEVATION_OF_PRIVILEGE,
                        title=f"SSRF: {description}",
                        description=f"Server-Side Request Forgery risk at {file_path}:{line_no}",
                        file_path=file_path,
                        line_number=line_no,
                        evidence=content[:200],
                        recommendation="Validate and sanitize all URLs. Use URL allowlists. Never trust user input for URL construction.",
                        cwe="CWE-918: Server-Side Request Forgery",
                    )
                )

        # Update compliance matrix
        # Categories with dedicated scanners: A04, A05, A10
        # Categories without dedicated scanners (A06-A09): mark as NOT_SCANNED
        categories_with_scanner = {
            OwaspCategory.A04_INSECURE_DESIGN,
            OwaspCategory.A05_SECURITY_MISCONFIGURATION,
            OwaspCategory.A10_SSRF,
        }
        categories_without_scanner = {
            OwaspCategory.A06_VULNERABLE_COMPONENTS,
            OwaspCategory.A07_AUTH_FAILURES,
            OwaspCategory.A08_DATA_INTEGRITY_FAILURES,
            OwaspCategory.A09_SECURITY_LOGGING_FAILURES,
        }

        for cat in categories_with_scanner:
            self.owasp_compliance[cat.value] = (
                "FAIL" if self._has_finding_category(cat) else "PASS"
            )

        for cat in categories_without_scanner:
            self.owasp_compliance[cat.value] = "NOT_SCANNED"

    def _has_finding_category(self, category: OwaspCategory) -> bool:
        """Check if any findings exist for given category."""
        return any(f.category == category for f in self.findings)


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    scanner = SecurityScanner(target)
    result = scanner.run_full_scan()

    print(json.dumps({
        "status": result.status,
        "target": result.target_path,
        "findings_count": len(result.findings),
        "files_scanned": result.files_scanned,
        "duration_seconds": result.scan_duration_seconds,
        "owasp_compliance": result.owasp_compliance,
        "errors": result.errors,
    }, indent=2, default=str))


def main() -> ScanResult:
    """CLI entry point for ce-security-sentinel agent."""
    target = "."
    scanner = SecurityScanner(target)
    return scanner.run_full_scan()
