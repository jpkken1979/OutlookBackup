"""
Error patterns for log analysis.
Stdlib only — no external dependencies.
"""

from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class ErrorPattern:
    """A single regex-based error pattern to detect in logs."""

    code: str
    regex: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    description: str
    group_key: str  # key for deduplication — similar errors share the same key


PATTERNS: Final[list[ErrorPattern]] = [
    # ── CRITICAL ──────────────────────────────────────────────────────────────
    # Specific patterns first (they take priority in the match loop)
    ErrorPattern(
        code="E001",
        regex=r"(?i)exception|traceback|stack trace",
        severity="CRITICAL",
        description="Python exception or stack trace",
        group_key="python_exception",
    ),
    ErrorPattern(
        code="E003",
        regex=r"(?i)connection.{0,10}refused|ECONNREFUSED",
        severity="CRITICAL",
        description="Connection refused",
        group_key="connection_refused",
    ),
    ErrorPattern(
        code="E004",
        regex=r"(?i)authentication.{0,20}failed|auth.{0,20}fail|unauthorized|401|403",
        severity="CRITICAL",
        description="Authentication failure",
        group_key="auth_failure",
    ),
    ErrorPattern(
        code="E005",
        regex=r"(?i)500.{0,20}internal|internal server error",
        severity="CRITICAL",
        description="HTTP 500 Internal Server Error",
        group_key="http_500",
    ),
    ErrorPattern(
        code="E006",
        regex=r"(?i)memory.{0,10}error|out of memory|OOM|MemoryError",
        severity="CRITICAL",
        description="Out of memory error",
        group_key="oom_error",
    ),
    ErrorPattern(
        code="E007",
        regex=r"(?i)permission.{0,10}denied|access.{0,10}denied|EACCES",
        severity="CRITICAL",
        description="Permission denied",
        group_key="permission_denied",
    ),
    # Generic ERROR last — only fires when no specific pattern matched
    ErrorPattern(
        code="E002",
        regex=r"(?i)\berror\b|\[ERROR\]|^\s*ERROR\s*$",
        severity="CRITICAL",
        description="Error-level log entry",
        group_key="error_generic",
    ),
    # ── HIGH ─────────────────────────────────────────────────────────────────
    # Specific HIGH patterns first
    ErrorPattern(
        code="W002",
        regex=r"(?i)timeout|connection timeout|request timeout|ReadTimeout|TimeoutError",
        severity="HIGH",
        description="Timeout error",
        group_key="timeout_error",
    ),
    ErrorPattern(
        code="W003",
        regex=r"(?i)connection.{0,20}reset|ECONNRESET|connection.{0,10}closed",
        severity="HIGH",
        description="Connection reset by peer",
        group_key="connection_reset",
    ),
    ErrorPattern(
        code="W005",
        regex=r"(?i)503.{0,20}unavailable|ServiceUnavailable|502|504",
        severity="HIGH",
        description="HTTP 5xx gateway errors",
        group_key="http_5xx_gateway",
    ),
    ErrorPattern(
        code="W006",
        regex=r"(?i)panic|fatal error|segfault|segmentation fault",
        severity="HIGH",
        description="Panic or fatal error",
        group_key="panic_fatal",
    ),
    # Generic WARNING second
    ErrorPattern(
        code="W001",
        regex=r"(?i)\bwarning\b",
        severity="HIGH",
        description="Warning-level log entry",
        group_key="warning_generic",
    ),
    ErrorPattern(
        code="W004",
        regex=r"(?i)deprecated|deprecatedapi|DeprecationWarning",
        severity="HIGH",
        description="Deprecated API usage",
        group_key="deprecated_api",
    ),
    # ── MEDIUM ────────────────────────────────────────────────────────────────
    ErrorPattern(
        code="M001",
        regex=r"(?i)rate.{0,10}limit|rate_limit|RateLimitExceeded|429",
        severity="MEDIUM",
        description="Rate limiting detected",
        group_key="rate_limit",
    ),
    ErrorPattern(
        code="M002",
        regex=r"(?i)retry|reconnecting|attempt.{0,10}\d+",
        severity="MEDIUM",
        description="Retry attempt",
        group_key="retry_attempt",
    ),
    ErrorPattern(
        code="M003",
        regex=r"(?i)certificate.{0,10}invalid|ssl.{0,10}error|SSL.{0,10}verification",
        severity="MEDIUM",
        description="SSL / certificate error",
        group_key="ssl_error",
    ),
    ErrorPattern(
        code="M004",
        regex=r"(?i)database.{0,10}locked|DB.{0,10}locked|sqlite.{0,10}busy",
        severity="MEDIUM",
        description="Database lock / busy",
        group_key="db_locked",
    ),
    # ── LOW ───────────────────────────────────────────────────────────────────
    ErrorPattern(
        code="L001",
        regex=r"(?i)slow.{0,20}query|slow request|slow operation|latency.{0,20}high",
        severity="LOW",
        description="Slow query or request",
        group_key="slow_operation",
    ),
    ErrorPattern(
        code="L002",
        regex=r"(?i)deprecated|deprecated feature|deprecated method",
        severity="LOW",
        description="Deprecated feature notice",
        group_key="deprecated_notice",
    ),
    ErrorPattern(
        code="L003",
        regex=r"(?i)disk.{0,10}full|no space|ENOSPC|DiskFull",
        severity="LOW",
        description="Disk space warning",
        group_key="disk_full",
    ),
]

# Index by severity for fast lookup
PATTERNS_BY_SEVERITY: dict[str, list[ErrorPattern]] = {
    "CRITICAL": [p for p in PATTERNS if p.severity == "CRITICAL"],
    "HIGH": [p for p in PATTERNS if p.severity == "HIGH"],
    "MEDIUM": [p for p in PATTERNS if p.severity == "MEDIUM"],
    "LOW": [p for p in PATTERNS if p.severity == "LOW"],
}

# Level alias — maps CLI --level to a minimum severity threshold
LEVEL_MAP: dict[str, str] = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "all": "LOW",
}
