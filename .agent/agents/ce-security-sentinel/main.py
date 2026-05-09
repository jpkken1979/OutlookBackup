"""ce-security-sentinel agent entry point.

Security audit agent based on OWASP Top 10 2021 with structured threat modeling.
"""
import logging
import sys
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

    def get_findings_by_severity(self, severity: Severity) -> list[Finding]:
        """Filter findings by severity."""
        return [f for f in self.findings if f.severity == severity]

    def get_findings_by_category(self, category: OwaspCategory) -> list[Finding]:
        """Filter findings by OWASP category."""
        return [f for f in self.findings if f.category == category]

    @property
    def critical_count(self) -> int:
        return len(self.get_findings_by_severity(Severity.CRITICAL))

    @property
    def high_count(self) -> int:
        return len(self.get_findings_by_severity(Severity.HIGH))

    @property
    def medium_count(self) -> int:
        return len(self.get_findings_by_severity(Severity.MEDIUM))

    @property
    def low_count(self) -> int:
        return len(self.get_findings_by_severity(Severity.LOW))


def run(input_str: str) -> dict:
    """Run ce-security-sentinel audit.

    Args:
        input_str: Path al código a auditar, scope, y focus areas.
            Format: "path=<path> scope=<full|incremental> focus=<comma-separated OWASP categories>"

    Returns:
        dict con status, findings, y recommendations.
    """
    logger.info("Starting ce-security-sentinel audit")
    logger.info("Input: %s", input_str)

    # Parse input
    target_path = "."
    scope = "full"
    focus_areas: list[str] = []

    for part in input_str.split():
        if part.startswith("path="):
            target_path = part[5:]
        elif part.startswith("scope="):
            scope = part[6:]
        elif part.startswith("focus="):
            focus_areas = part[6:].split(",")

    logger.info("Target: %s, Scope: %s, Focus: %s", target_path, scope, focus_areas)

    # Import here to avoid circular imports and allow lazy loading
    try:
        # Try relative import first (when used as package)
        from .scripts.security_scan import SecurityScanner  # type: ignore[attr-defined]

        scanner = SecurityScanner(target_path)
        result = scanner.run_full_scan(scope=scope, focus_areas=focus_areas)
    except ImportError:
        # Fallback when running as standalone script
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.security_scan import SecurityScanner

        scanner = SecurityScanner(target_path)
        result = scanner.run_full_scan(scope=scope, focus_areas=focus_areas)

    return _result_to_dict(result)


def _result_to_dict(result: ScanResult) -> dict:
    """Convert ScanResult to dict for JSON serialization."""
    return {
        "status": result.status,
        "target": result.target_path,
        "summary": {
            "critical": result.critical_count,
            "high": result.high_count,
            "medium": result.medium_count,
            "low": result.low_count,
            "total": len(result.findings),
            "files_scanned": result.files_scanned,
            "duration_seconds": result.scan_duration_seconds,
        },
        "findings": [
            {
                "severity": f.severity.value,
                "category": f.category.value,
                "stride": f.stride.value,
                "title": f.title,
                "description": f.description,
                "location": f"{f.file_path}:{f.line_number}" if f.file_path else None,
                "evidence": f.evidence,
                "recommendation": f.recommendation,
                "cwe": f.cwe,
            }
            for f in result.findings
        ],
        "owasp_compliance": result.owasp_compliance,
        "errors": result.errors,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    input_data = sys.argv[1] if len(sys.argv) > 1 else "path=."
    result = run(input_data)
    import json

    print(json.dumps(result, indent=2, default=str))


def main() -> dict:
    """CLI entry point for ce-security-sentinel agent."""
    return run("path=.")
