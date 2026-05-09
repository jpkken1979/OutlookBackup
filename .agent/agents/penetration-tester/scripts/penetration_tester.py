#!/usr/bin/env python3
"""
Penetration Tester Agent - Offensive security and vulnerability exploitation.

Usage:
    python penetration_tester.py <target_path> [--scope <scope>] [--json]
    python penetration_tester.py --web <url> [--json]
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """Security finding from penetration test."""

    id: str
    title: str
    severity: str  # critical, high, medium, low, info
    cvss: float | None
    location: str
    description: str
    evidence: str
    impact: str
    remediation: str
    references: list = field(default_factory=list)
    cwe: str | None = None


@dataclass
class PentestReport:
    """Penetration test report."""

    target: str
    scope: str
    timestamp: str
    methodology: str = "PTES"
    findings: list = field(default_factory=list)
    attack_surface: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class PenetrationTester:
    """Offensive security analysis agent."""

    OWASP_TOP_10 = {
        "A01": "Broken Access Control",
        "A02": "Cryptographic Failures",
        "A03": "Injection",
        "A04": "Insecure Design",
        "A05": "Security Misconfiguration",
        "A06": "Vulnerable Components",
        "A07": "Auth Failures",
        "A08": "Integrity Failures",
        "A09": "Logging Failures",
        "A10": "SSRF",
    }

    DANGEROUS_PATTERNS = {
        "sql_injection": [
            r'execute\s*\(\s*["\'].*\%s',
            r'cursor\.execute\s*\(\s*f["\']',
            r'query\s*=\s*["\'].*\+\s*\w+',
            r'SELECT.*FROM.*WHERE.*=\s*["\']\s*\+',
        ],
        "command_injection": [
            r"os\.system\s*\(",
            r"subprocess\.\w+\s*\([^)]*shell\s*=\s*True",
            r"eval\s*\(",
            r"exec\s*\(",
        ],
        "xss": [
            r"innerHTML\s*=",
            r"document\.write\s*\(",
            r"v-html\s*=",
            r"dangerouslySetInnerHTML",
        ],
        "path_traversal": [
            r"open\s*\([^)]*\+",
            r"\.\./",
            r"os\.path\.join\s*\([^)]*request",
        ],
        "hardcoded_secrets": [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r"AWS_SECRET_ACCESS_KEY\s*=",
        ],
        "insecure_crypto": [
            r"md5\s*\(",
            r"sha1\s*\(",
            r"DES\.",
            r"RC4",
        ],
        "ssrf": [
            r"requests\.get\s*\([^)]*\+",
            r"urllib\.request\.urlopen\s*\(",
            r"fetch\s*\([^)]*\+",
        ],
        "xxe": [
            r"xml\.etree\.ElementTree\.parse",
            r"lxml\.etree\.parse",
            r"XMLParser\s*\(",
        ],
    }

    def __init__(self, target: str, scope: str = "full"):
        self.target = target
        self.scope = scope
        self.findings: list[Finding] = []
        self.finding_counter = 0

    def _generate_finding_id(self) -> str:
        """Generate unique finding ID."""
        self.finding_counter += 1
        return f"VULN-{self.finding_counter:03d}"

    def _calculate_cvss(self, severity: str) -> float:
        """Estimate CVSS score from severity."""
        cvss_map = {"critical": 9.5, "high": 7.5, "medium": 5.0, "low": 2.5, "info": 0.0}
        return cvss_map.get(severity, 0.0)

    def analyze_code(self, path: Path) -> list[Finding]:
        """Static analysis for vulnerabilities."""
        findings = []

        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".php", ".java", ".go", ".rb"}

        for file_path in path.rglob("*"):
            if file_path.suffix not in extensions:
                continue
            if any(
                skip in str(file_path) for skip in ["node_modules", ".git", "venv", "__pycache__"]
            ):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                lines = content.split("\n")

                for vuln_type, patterns in self.DANGEROUS_PATTERNS.items():
                    for pattern in patterns:
                        for i, line in enumerate(lines, 1):
                            if re.search(pattern, line, re.IGNORECASE):
                                severity = self._get_severity(vuln_type)
                                finding = Finding(
                                    id=self._generate_finding_id(),
                                    title=f"{vuln_type.replace('_', ' ').title()} Detected",
                                    severity=severity,
                                    cvss=self._calculate_cvss(severity),
                                    location=f"{file_path}:{i}",
                                    description=f"Potential {vuln_type.replace('_', ' ')} vulnerability detected.",
                                    evidence=line.strip()[:200],
                                    impact=self._get_impact(vuln_type),
                                    remediation=self._get_remediation(vuln_type),
                                    cwe=self._get_cwe(vuln_type),
                                )
                                findings.append(finding)
            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        return findings

    def _get_severity(self, vuln_type: str) -> str:
        """Get severity for vulnerability type."""
        critical = {"sql_injection", "command_injection", "hardcoded_secrets"}
        high = {"xss", "path_traversal", "ssrf", "xxe"}
        medium = {"insecure_crypto"}

        if vuln_type in critical:
            return "critical"
        elif vuln_type in high:
            return "high"
        elif vuln_type in medium:
            return "medium"
        return "low"

    def _get_impact(self, vuln_type: str) -> str:
        """Get impact description for vulnerability type."""
        impacts = {
            "sql_injection": "Database compromise, data exfiltration, authentication bypass",
            "command_injection": "Remote code execution, full system compromise",
            "xss": "Session hijacking, credential theft, malware distribution",
            "path_traversal": "Unauthorized file access, sensitive data exposure",
            "hardcoded_secrets": "Credential exposure, unauthorized access to services",
            "insecure_crypto": "Data decryption, integrity compromise",
            "ssrf": "Internal network scanning, cloud metadata access",
            "xxe": "File disclosure, SSRF, denial of service",
        }
        return impacts.get(vuln_type, "Security impact")

    def _get_remediation(self, vuln_type: str) -> str:
        """Get remediation for vulnerability type."""
        remediations = {
            "sql_injection": "Use parameterized queries or ORM. Never concatenate user input.",
            "command_injection": "Use subprocess with shell=False. Validate and sanitize input.",
            "xss": "Sanitize output. Use Content-Security-Policy. Avoid innerHTML.",
            "path_traversal": "Validate paths. Use os.path.realpath() and check against base directory.",
            "hardcoded_secrets": "Use environment variables or secrets manager. Never commit secrets.",
            "insecure_crypto": "Use SHA-256+ for hashing, AES-256 for encryption. Avoid MD5/SHA1.",
            "ssrf": "Validate URLs against allowlist. Block internal IP ranges.",
            "xxe": "Disable external entities in XML parser configuration.",
        }
        return remediations.get(vuln_type, "Review and fix the vulnerability")

    def _get_cwe(self, vuln_type: str) -> str:
        """Get CWE ID for vulnerability type."""
        cwes = {
            "sql_injection": "CWE-89",
            "command_injection": "CWE-78",
            "xss": "CWE-79",
            "path_traversal": "CWE-22",
            "hardcoded_secrets": "CWE-798",
            "insecure_crypto": "CWE-327",
            "ssrf": "CWE-918",
            "xxe": "CWE-611",
        }
        return cwes.get(vuln_type, "CWE-Unknown")

    def check_dependencies(self, path: Path) -> list[Finding]:
        """Check for vulnerable dependencies."""
        findings = []

        # Check package.json
        package_json = path / "package.json"
        if package_json.exists():
            try:
                result = subprocess.run(
                    ["npm", "audit", "--json"], cwd=path, capture_output=True, text=True, timeout=60
                )
                if result.stdout:
                    audit_data = json.loads(result.stdout)
                    if "vulnerabilities" in audit_data:
                        for name, vuln in audit_data.get("vulnerabilities", {}).items():
                            severity = vuln.get("severity", "medium")
                            finding = Finding(
                                id=self._generate_finding_id(),
                                title=f"Vulnerable Dependency: {name}",
                                severity=severity,
                                cvss=self._calculate_cvss(severity),
                                location="package.json",
                                description=f"Package {name} has known vulnerabilities",
                                evidence=f"Via: {vuln.get('via', 'unknown')}",
                                impact="Depends on vulnerability type",
                                remediation=f"Update to fixed version: {vuln.get('fixAvailable', 'unknown')}",
                            )
                            findings.append(finding)
            except Exception as e:
                logger.debug(f"npm audit failed: {e}")

        # Check requirements.txt / pyproject.toml
        requirements = path / "requirements.txt"
        if requirements.exists():
            try:
                result = subprocess.run(
                    ["pip-audit", "--format", "json"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.stdout:
                    audit_data = json.loads(result.stdout)
                    for vuln in audit_data:
                        finding = Finding(
                            id=self._generate_finding_id(),
                            title=f"Vulnerable Dependency: {vuln.get('name', 'unknown')}",
                            severity="high",
                            cvss=7.5,
                            location="requirements.txt",
                            description=vuln.get("description", "Known vulnerability"),
                            evidence=f"CVE: {vuln.get('id', 'unknown')}",
                            impact="Depends on vulnerability type",
                            remediation=f"Update to version {vuln.get('fix_versions', ['latest'])[0]}",
                        )
                        findings.append(finding)
            except Exception as e:
                logger.debug(f"pip-audit failed: {e}")

        return findings

    def analyze_configs(self, path: Path) -> list[Finding]:
        """Analyze configuration files for misconfigurations."""
        findings = []

        config_patterns = {
            ".env": [
                (r"DEBUG\s*=\s*[Tt]rue", "Debug mode enabled", "high"),
                (r'SECRET_KEY\s*=\s*["\']?[^"\'\n]+', "Secret key in config", "critical"),
            ],
            "docker-compose.yml": [
                (r"privileged:\s*true", "Privileged container", "high"),
                (r"network_mode:\s*host", "Host network mode", "medium"),
            ],
            "Dockerfile": [
                (r"USER\s+root", "Running as root", "medium"),
                (r"curl.*\|\s*sh", "Piped curl to shell", "high"),
            ],
        }

        for config_file, patterns in config_patterns.items():
            for file_path in path.rglob(config_file):
                try:
                    content = file_path.read_text()
                    for pattern, title, severity in patterns:
                        if re.search(pattern, content):
                            finding = Finding(
                                id=self._generate_finding_id(),
                                title=title,
                                severity=severity,
                                cvss=self._calculate_cvss(severity),
                                location=str(file_path),
                                description=f"Security misconfiguration in {config_file}",
                                evidence=f"Pattern matched: {pattern}",
                                impact="Configuration-dependent security issue",
                                remediation="Review and fix the configuration",
                            )
                            findings.append(finding)
                except Exception:
                    pass

        return findings

    def map_attack_surface(self, path: Path) -> dict:
        """Map the attack surface of the target."""
        surface = {
            "endpoints": [],
            "forms": [],
            "auth_mechanisms": [],
            "data_stores": [],
            "external_services": [],
            "file_uploads": [],
        }

        # Find API endpoints
        for file_path in path.rglob("*.py"):
            try:
                content = file_path.read_text()
                # Flask/FastAPI routes
                routes = re.findall(
                    r'@\w+\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)', content, re.IGNORECASE
                )
                surface["endpoints"].extend(
                    [f"{method.upper()} {route}" for method, route in routes]
                )
            except Exception:
                pass

        # Find auth patterns
        auth_patterns = ["jwt", "oauth", "session", "cookie", "bearer", "basic auth"]
        for file_path in path.rglob("*"):
            if file_path.suffix in {".py", ".js", ".ts"}:
                try:
                    content = file_path.read_text().lower()
                    for pattern in auth_patterns:
                        if pattern in content:
                            surface["auth_mechanisms"].append(pattern)
                except Exception:
                    pass

        surface["auth_mechanisms"] = list(set(surface["auth_mechanisms"]))

        return surface

    def generate_report(self) -> PentestReport:
        """Generate comprehensive pentest report."""
        path = Path(self.target)

        if not path.exists():
            logger.error(f"Target path does not exist: {self.target}")
            return PentestReport(
                target=self.target,
                scope=self.scope,
                timestamp=datetime.now().isoformat(),
                summary={"error": "Target not found"},
            )

        logger.info(f"Starting penetration test on {self.target}")

        # Collect findings
        code_findings = self.analyze_code(path)
        dep_findings = self.check_dependencies(path)
        config_findings = self.analyze_configs(path)

        all_findings = code_findings + dep_findings + config_findings

        # Map attack surface
        attack_surface = self.map_attack_surface(path)

        # Generate summary
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in all_findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        # Generate recommendations
        recommendations = []
        if severity_counts["critical"] > 0:
            recommendations.append(
                "IMMEDIATE: Address all critical vulnerabilities before deployment"
            )
        if severity_counts["high"] > 0:
            recommendations.append("HIGH PRIORITY: Fix high severity issues within 7 days")
        recommendations.append("Implement security scanning in CI/CD pipeline")
        recommendations.append("Conduct regular security assessments")

        return PentestReport(
            target=self.target,
            scope=self.scope,
            timestamp=datetime.now().isoformat(),
            findings=[asdict(f) for f in all_findings],
            attack_surface=attack_surface,
            recommendations=recommendations,
            summary={
                "total_findings": len(all_findings),
                "by_severity": severity_counts,
                "risk_level": "CRITICAL"
                if severity_counts["critical"] > 0
                else "HIGH"
                if severity_counts["high"] > 0
                else "MEDIUM"
                if severity_counts["medium"] > 0
                else "LOW",
            },
        )


def format_report_markdown(report: PentestReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Penetration Test Report",
        "",
        f"**Target:** {report.target}",
        f"**Scope:** {report.scope}",
        f"**Date:** {report.timestamp}",
        f"**Methodology:** {report.methodology}",
        "",
        "## Executive Summary",
        "",
        f"**Risk Level:** {report.summary.get('risk_level', 'Unknown')}",
        f"**Total Findings:** {report.summary.get('total_findings', 0)}",
        "",
        "### Findings by Severity",
        "",
    ]

    for severity, count in report.summary.get("by_severity", {}).items():
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "🔵"}.get(
                severity, "⚪"
            )
            lines.append(f"- {emoji} **{severity.upper()}**: {count}")

    lines.extend(["", "## Findings", ""])

    for finding in report.findings:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            finding.get("severity", ""), "⚪"
        )
        lines.extend(
            [
                f"### {severity_emoji} {finding.get('id', '')}: {finding.get('title', '')}",
                "",
                f"**Severity:** {finding.get('severity', '').upper()} | **CVSS:** {finding.get('cvss', 0)}",
                f"**Location:** `{finding.get('location', '')}`",
                f"**CWE:** {finding.get('cwe', 'N/A')}",
                "",
                f"**Description:** {finding.get('description', '')}",
                "",
                "**Evidence:**",
                "```",
                f"{finding.get('evidence', '')}",
                "```",
                "",
                f"**Impact:** {finding.get('impact', '')}",
                "",
                f"**Remediation:** {finding.get('remediation', '')}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["## Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Penetration Tester Agent")
    parser.add_argument("target", nargs="?", default=".", help="Target path to analyze")
    parser.add_argument("--scope", default="full", help="Scope of the test")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--web", help="Web URL to test (basic checks only)")

    args = parser.parse_args()

    if args.web:
        logger.warning(
            "Web testing requires explicit authorization. Use only on authorized targets."
        )
        print("Web penetration testing requires authorized engagement.")
        print("For web testing, use dedicated tools like OWASP ZAP or Burp Suite.")
        sys.exit(0)

    tester = PenetrationTester(args.target, args.scope)
    report = tester.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
