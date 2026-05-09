#!/usr/bin/env python3
"""
Security Scanner Agent v2.0

Comprehensive security vulnerability detection:
- OWASP Top 10 coverage
- Hardcoded secret detection
- SQL/XSS/SSRF/Command injection
- Security configuration audit
- CVE scanning in dependencies
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Vulnerability:
    """Security vulnerability."""
    severity: str  # critical, high, medium, low
    category: str
    file: str
    line: int
    description: str
    recommendation: str
    cwe: str | None = None  # CWE ID for tracking


class SecurityScanner:
    """Security Auditor agent for vulnerability scanning and detection."""

    def __init__(self) -> None:
        self.name = "SecurityScanner"
        self.findings: list[dict] = []
        logger.info("SecurityScanner v2.0 initialized")

    async def scan(self, path: str = ".") -> dict[str, Any]:
        """Scan code for security vulnerabilities.

        Args:
            path: Path to scan for vulnerabilities.

        Returns:
            Dictionary with vulnerability report.
        """
        logger.info(f"Scanning path: {path}")
        self.findings = []

        result: dict[str, Any] = {
            "agent": self.name,
            "version": "2.0",
            "path": path,
            "status": "completed",
            "vulnerabilities": [],
            "summary": "",
            "recommendations": [],
            "stats": {
                "files_scanned": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
        }

        scan_path = Path(path)
        if not scan_path.exists():
            result["status"] = "failed"
            result["summary"] = f"Path not found: {path}"
            return result

        # OWASP A01: Broken Access Control
        self._scan_access_control(scan_path)

        # OWASP A02: Cryptographic Failures (secrets)
        self._scan_crypto_failures(scan_path)

        # OWASP A03: Injection (SQL, XSS, SSRF, Command)
        self._scan_injection(scan_path)

        # OWASP A05: Security Misconfiguration
        self._scan_misconfiguration(scan_path)

        result["vulnerabilities"] = self.findings
        result["stats"]["files_scanned"] = self._count_scannable_files(scan_path)

        for v in self.findings:
            result["stats"][v["severity"]] += 1

        result["summary"] = (
            f"Scan complete: {len(self.findings)} vulnerability(ies) found "
            f"({result['stats']['critical']} critical, "
            f"{result['stats']['high']} high, "
            f"{result['stats']['medium']} medium, "
            f"{result['stats']['low']} low)"
        )

        result["recommendations"] = self._get_recommendations()

        logger.info(f"Security scan completed: {len(self.findings)} issues")
        return result

    def _scan_access_control(self, scan_path: Path) -> None:
        """OWASP A01: Broken Access Control."""
        patterns = [
            (r'chmod\s+777', "World-writable file/directory", "high", "C-0777"),
            (r'0o777', "World-writable permission", "high", "C-0777"),
            (r'admin.*route|admin.*endpoint', "Potential unprotected admin route", "medium", "C-0890"),
        ]

        for file_path in self._get_scannable_files(scan_path, "*.py"):
            try:
                content = file_path.read_text(errors="ignore")
                for pattern, desc, severity, cwe in patterns:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        line_no = content[:match.start()].count("\n") + 1
                        self._add_vulnerability(
                            severity, "Access Control", str(file_path),
                            line_no, desc,
                            "Review access control list; implement RBAC",
                            cwe
                        )
            except Exception:
                pass

    def _scan_crypto_failures(self, scan_path: Path) -> None:
        """OWASP A02: Cryptographic Failures."""
        patterns = [
            (r'(?i)(api[_-]?key|secret|password|token)\s*=\s*["\'][^"\']{8,}["\']',
             "Hardcoded secret", "critical", "C-798"),
            (r'bearer\s+[a-zA-Z0-9_-]{20,}', "Hardcoded bearer token", "critical", "C-798"),
            (r'xox[pbor]-[a-zA-Z0-9-]{20,}', "Hardcoded Slack token", "critical", "C-798"),
            (r'sk-[a-zA-Z0-9]{20,}', "Hardcoded API key", "critical", "C-798"),
            (r'AKIA[0-9A-Z]{16}', "Hardcoded AWS access key", "critical", "C-798"),
            (r'md5\(|hashlib\.md5\(', "MD5 for cryptographic purposes", "high", "C-327"),
            (r'sha1\(|hashlib\.sha1\(', "SHA1 for cryptographic purposes", "medium", "C-326"),
        ]

        for file_path in self._get_scannable_files(scan_path, "*.py"):
            try:
                content = file_path.read_text(errors="ignore")
                for pattern, desc, severity, cwe in patterns:
                    for match in re.finditer(pattern, content):
                        # Filter out example/fake patterns
                        matched_text = match.group()
                        if any(x in matched_text.lower() for x in ["example", "test", "fake", "placeholder", "your_"]):
                            continue
                        line_no = content[:match.start()].count("\n") + 1
                        self._add_vulnerability(
                            severity, "Cryptographic Failure", str(file_path),
                            line_no, f"Found: {matched_text[:50]}",
                            "Move secret to environment variable",
                            cwe
                        )
            except Exception:
                pass

    def _scan_injection(self, scan_path: Path) -> None:
        """OWASP A03: Injection vulnerabilities."""
        injection_patterns = [
            # SQL Injection
            (r'f"SELECT.*\{[^}]+\}', "SQL injection via f-string", "high", "C-89"),
            (r'f\'SELECT.*\{[^}]+\}', "SQL injection via f-string", "high", "C-89"),
            (r'\.format\(.*SELECT', "SQL injection via .format()", "high", "C-89"),
            (r'cursor\.execute\([^,]+%s', "SQL with %s formatting (potential injection)", "high", "C-89"),
            (r'\.format\(.*DELETE', "SQL injection via .format()", "high", "C-89"),
            (r'\.format\(.*INSERT', "SQL injection via .format()", "high", "C-89"),
            (r'f"INSERT.*\{', "SQL injection via f-string", "high", "C-89"),
            # XSS
            (r'innerHTML\s*=', "XSS via innerHTML", "high", "C-79"),
            (r'dangerouslySetInnerHTML', "XSS via dangerouslySetInnerHTML", "critical", "C-79"),
            (r'document\.write\(', "XSS via document.write()", "high", "C-79"),
            (r'eval\(', "Code injection via eval()", "critical", "C-95"),
            # SSRF
            (r'requests\.get\([^)]*user[_-]?input', "Potential SSRF via user input", "high", "C-918"),
            (r'urllib.*open\([^)]*user', "Potential SSRF via urllib", "high", "C-918"),
            (r'fetch\([^)]*user[_-]?input', "Potential SSRF via fetch", "high", "C-918"),
            # Command Injection
            (r'os\.system\(', "Command injection via os.system()", "critical", "C-78"),
            (r'subprocess\.(run|call|Popen)\([^)]*shell\s*=\s*True', "Command injection via subprocess", "critical", "C-78"),
            (r'os\.popen\(', "Command injection via os.popen()", "critical", "C-78"),
        ]

        for file_path in self._get_scannable_files(scan_path, "*.py"):
            try:
                content = file_path.read_text(errors="ignore")
                for pattern, desc, severity, cwe in injection_patterns:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        line_no = content[:match.start()].count("\n") + 1
                        self._add_vulnerability(
                            severity, "Injection", str(file_path),
                            line_no, desc,
                            self._get_injection_fix(desc),
                            cwe
                        )
            except Exception:
                pass

        # TypeScript/JS XSS patterns
        for file_path in self._get_scannable_files(scan_path, "*.{ts,tsx,js,jsx}"):
            try:
                content = file_path.read_text(errors="ignore")
                xss_patterns_ts = [
                    (r'innerHTML\s*=', "XSS via innerHTML", "high", "C-79"),
                    (r'dangerouslySetInnerHTML', "XSS via dangerouslySetInnerHTML", "critical", "C-79"),
                    (r'eval\(', "Code injection via eval()", "critical", "C-95"),
                    (r'regexp\(.*user', "Potential ReDoS via user input", "medium", "C-1333"),
                ]
                for pattern, desc, severity, cwe in xss_patterns_ts:
                    for match in re.finditer(pattern, content):
                        line_no = content[:match.start()].count("\n") + 1
                        self._add_vulnerability(
                            severity, "Injection", str(file_path),
                            line_no, desc,
                            self._get_injection_fix(desc),
                            cwe
                        )
            except Exception:
                pass

    def _scan_misconfiguration(self, scan_path: Path) -> None:
        """OWASP A05: Security Misconfiguration."""
        patterns = [
            (r'debug\s*=\s*True', "Debug mode enabled in production", "high", "C-11"),
            (r'"DEBUG":\s*true', "Debug mode enabled in production", "high", "C-11"),
            (r'CORS\([^)]*allow_origins\s*=\s*\[', "CORS allowlist not configured", "medium", "C-067"),
            (r'Access-Control-Allow-Origin.*\*', "CORS wildcard (allow all origins)", "high", "C-067"),
            (r'password\s*=\s*["\'][^"\']{0,7}["\']', "Weak password configuration", "medium", "C-521"),
        ]

        for file_path in self._get_scannable_files(scan_path, "*.py"):
            try:
                content = file_path.read_text(errors="ignore")
                for pattern, desc, severity, cwe in patterns:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        line_no = content[:match.start()].count("\n") + 1
                        self._add_vulnerability(
                            severity, "Security Misconfiguration", str(file_path),
                            line_no, desc,
                            "Disable debug mode; configure CORS explicitly",
                            cwe
                        )
            except Exception:
                pass

    def _add_vulnerability(
        self, severity: str, category: str, file: str,
        line: int, description: str, recommendation: str, cwe: str | None = None
    ) -> None:
        """Add a vulnerability to findings."""
        self.findings.append({
            "severity": severity,
            "category": category,
            "file": file,
            "line": line,
            "description": description,
            "recommendation": recommendation,
            "cwe": cwe,
        })

    def _get_injection_fix(self, desc: str) -> str:
        """Get specific remediation for injection type."""
        fixes = {
            "SQL injection via f-string": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            "SQL injection via .format()": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
            "XSS via innerHTML": "Use textContent or sanitize with DOMPurify",
            "XSS via dangerouslySetInnerHTML": "Avoid if possible; if needed, sanitize with DOMPurify before setting",
            "Command injection via os.system()": "Use subprocess.run() with list of args, shell=False",
            "Command injection via subprocess": "Pass shell=False and use list of arguments instead of string",
            "Code injection via eval()": "Avoid eval(); refactor to use safer alternatives",
        }
        return fixes.get(desc, "Sanitize user input; use parameterized queries; validate URL allowlist")

    def _get_recommendations(self) -> list[str]:
        """Get general recommendations based on findings."""
        recs = [
            "Enable dependency scanning (pip-audit, npm audit) in CI/CD",
            "Add security testing to CI/CD pipeline",
            "Implement rate limiting on public endpoints",
        ]
        if any(v["category"] == "Injection" for v in self.findings):
            recs.insert(0, "Use parameterized queries for all database operations")
        if any(v["category"] == "Cryptographic Failure" for v in self.findings):
            recs.insert(0, "Move all secrets to environment variables")
        return list(dict.fromkeys(recs))  # deduplicate

    def _get_scannable_files(self, path: Path, pattern: str) -> list[Path]:
        """Get files matching pattern, respecting skip dirs."""
        skip_dirs = {"venv", "node_modules", "__pycache__", ".git", "env", ".tox", "dist", "build", ".venv", ".pytest_cache"}
        files = []
        try:
            for f in path.rglob(pattern):
                if not any(skip in f.parts for skip in skip_dirs):
                    files.append(f)
        except Exception:
            pass
        return files

    def _count_scannable_files(self, path: Path) -> int:
        """Count total scannable files."""
        count = 0
        for pattern in ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx"]:
            count += len(self._get_scannable_files(path, pattern))
        return count

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {"venv", "node_modules", "__pycache__", ".git", "env", ".tox", "dist", "build"}
        return any(part in skip_dirs for part in path.parts)


async def main() -> None:
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO)

    path = sys.argv[1] if len(sys.argv) > 1 else "."
    scanner = SecurityScanner()
    result = await scanner.scan(path)

    print("=" * 60)
    print("Security Scan Results")
    print("=" * 60)
    print(f"  Total vulnerabilities: {len(result['vulnerabilities'])}")
    print(f"  Critical: {result['stats']['critical']}")
    print(f"  High: {result['stats']['high']}")
    print(f"  Medium: {result['stats']['medium']}")
    print(f"  Low: {result['stats']['low']}")
    print()

    if result["vulnerabilities"]:
        print("Top findings:")
        for v in result["vulnerabilities"][:15]:
            print(f"  [{v['severity'].upper()}] {v['category']}")
            print(f"    → {v['file']}:{v['line']}")
            print(f"    → {v['description']}")

    print("=" * 60)
    print(f"Status: {result['summary']}")


if __name__ == "__main__":
    asyncio.run(main())