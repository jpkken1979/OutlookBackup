"""Secret detection patterns and metadata.

This module defines all regex patterns used to detect hardcoded secrets,
API keys, tokens, passwords, and other credentials in source code.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Pattern


class Severity(Enum):
    """Severity classification for detected secrets."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


class SecretType(Enum):
    """Canonical types of secrets detected."""

    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    GITHUB_TOKEN = "github_token"
    OPENAI_KEY = "openai_key"
    ANTHROPIC_KEY = "anthropic_key"
    SLACK_TOKEN = "slack_token"
    TELEGRAM_TOKEN = "telegram_token"
    PRIVATE_KEY = "private_key"
    JWT_BEARER = "jwt_bearer"
    GENERIC_API_KEY = "generic_api_key"
    DATABASE_URL = "database_url"
    PASSWORD_IN_URL = "password_in_url"
    ENV_SECRET = "env_secret"
    MINIMAX_KEY = "minimax_key"
    ZAI_KEY = "zai_key"
    HIGH_ENTROPY = "high_entropy"


@dataclass
class SecretPattern:
    """A secret detection pattern with metadata.

    Attributes:
        name: Human-readable name of the secret type.
        secret_type: Enum value for programmatic classification.
        regex: Compiled regex pattern to match.
        severity: Severity classification.
        remediation: Suggested fix for developers.
        examples: Example matches (not real secrets).
        false_positive_indicators: Strings that suggest this is a false positive.
    """

    name: str
    secret_type: SecretType
    regex: Pattern[str]
    severity: Severity
    remediation: str
    examples: list[str] = field(default_factory=list)
    false_positive_indicators: list[str] = field(
        default_factory=lambda: [
            "example",
            "test",
            "placeholder",
            "dummy",
            "fake",
            "mock",
            "sample",
            "your_",
            "xxx",
            "000000000000",
        ]
    )

    def is_false_positive(self, context: str) -> bool:
        """Check if the match is likely a false positive.

        Args:
            context: Surrounding text of the match for heuristics.

        Returns:
            True if the match appears to be a false positive.
        """
        context_lower = context.lower()
        for indicator in self.false_positive_indicators:
            if indicator in context_lower:
                return True
        return False


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

PATTERNS: list[SecretPattern] = [
    # ---- CRITICAL ----
    SecretPattern(
        name="AWS Access Key ID",
        secret_type=SecretType.AWS_ACCESS_KEY,
        regex=re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        severity=Severity.CRITICAL,
        remediation="Remove from code. Use AWS environment variables or IAM roles.",
        examples=["AKIAIOSFODNN7EXAMPLE"],
    ),
    SecretPattern(
        name="AWS Secret Access Key",
        secret_type=SecretType.AWS_SECRET_KEY,
        regex=re.compile(
            r"(?:aws[_-]?secret[_-]?(?:access[_-]?)?key|aws[_-]?secret[_-]?key)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
            re.IGNORECASE,
        ),
        severity=Severity.CRITICAL,
        remediation="Remove from code. Use AWS environment variables or IAM roles.",
        examples=["wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"],
    ),
    SecretPattern(
        name="GitHub Personal Access Token",
        secret_type=SecretType.GITHUB_TOKEN,
        regex=re.compile(r"\b(ghp?[A-Za-z0-9_]{36,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('GH_TOKEN') or a secrets manager.",
        examples=["ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="GitHub OAuth/Personal Access Token (pat_)",
        secret_type=SecretType.GITHUB_TOKEN,
        regex=re.compile(r"\b(github_pat_[A-Za-z0-9_]{22,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('GH_TOKEN') or a secrets manager.",
        examples=["github_pat_xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="OpenAI API Key",
        secret_type=SecretType.OPENAI_KEY,
        regex=re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_-]{48,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('OPENAI_API_KEY') or a secrets manager.",
        examples=["sk-proj-xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="Anthropic API Key",
        secret_type=SecretType.ANTHROPIC_KEY,
        regex=re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{58,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('ANTHROPIC_API_KEY') or a secrets manager.",
        examples=["sk-ant-api03-xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="Slack Token",
        secret_type=SecretType.SLACK_TOKEN,
        regex=re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('SLACK_BOT_TOKEN') or a secrets manager.",
        examples=["xoxb-1234567890123-1234567890123-xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="Telegram Bot Token",
        secret_type=SecretType.TELEGRAM_TOKEN,
        regex=re.compile(r"\b(\d{8,10}:[A-Za-z0-9_-]{35})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('TELEGRAM_BOT_TOKEN') or a secrets manager.",
        examples=["123456789:ABCdefGhIJKlmnOPQRstUVWXYZxyz0123456789"],
    ),
    SecretPattern(
        name="RSA/EC/DSA/OPENSSH Private Key",
        secret_type=SecretType.PRIVATE_KEY,
        regex=re.compile(
            r"-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|PRIVATE\s+KEY)[\s\w-]*-----",
            re.IGNORECASE,
        ),
        severity=Severity.CRITICAL,
        remediation="Remove private key from codebase. Use a secrets manager.",
        examples=["-----BEGIN RSA PRIVATE KEY-----"],
    ),
    SecretPattern(
        name="Minimax API Key",
        secret_type=SecretType.MINIMAX_KEY,
        regex=re.compile(
            r"(?:minimax[_-]?api[_-]?key|minimax[_-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9_-]{20,})['\"]?",
            re.IGNORECASE,
        ),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('MINIMAX_API_KEY') or a secrets manager.",
        examples=["MINIMAX_API_KEY=xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="Minimax Key (bare token)",
        secret_type=SecretType.MINIMAX_KEY,
        regex=re.compile(r"\b(MINIMAX-[A-Za-z0-9_-]{20,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('MINIMAX_API_KEY') or a secrets manager.",
        examples=["MINIMAX-xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="ZAI API Key",
        secret_type=SecretType.ZAI_KEY,
        regex=re.compile(
            r"(?:zai[_-]?api[_-]?key|zai[_-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9_-]{20,})['\"]?",
            re.IGNORECASE,
        ),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('ZAI_API_KEY') or a secrets manager.",
        examples=["ZAI_API_KEY=xxxxxxxxxxxx"],
    ),
    SecretPattern(
        name="ZAI Key (bare token)",
        secret_type=SecretType.ZAI_KEY,
        regex=re.compile(r"\b(ZAI-[A-Za-z0-9_-]{20,})\b"),
        severity=Severity.CRITICAL,
        remediation="Use os.environ.get('ZAI_API_KEY') or a secrets manager.",
        examples=["ZAI-xxxxxxxxxxxx"],
    ),
    # ---- HIGH ----
    SecretPattern(
        name="JWT Bearer Token",
        secret_type=SecretType.JWT_BEARER,
        regex=re.compile(r"(?i)(?:bearer\s+)(eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+)"),
        severity=Severity.HIGH,
        remediation="Use secure token storage (keychain, secrets manager).",
        examples=["Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    ),
    SecretPattern(
        name="Generic API Key assignment",
        secret_type=SecretType.GENERIC_API_KEY,
        regex=re.compile(
            r"(?:api[_-]?key|api[_-]?token|apikey)\s*[=:]\s*['\"]?([A-Za-z0-9_-]{16,})['\"]?",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        remediation="Use os.environ.get() or a secrets manager.",
        examples=["api_key='xxxxxxxxxxxx'"],
    ),
    SecretPattern(
        name="PostgreSQL Connection String with credentials",
        secret_type=SecretType.DATABASE_URL,
        regex=re.compile(
            r"(?:postgres(?:ql)?|postgresql)://[A-Za-z0-9_]+:[^@]+@[A-Za-z0-9_.-]+",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        remediation="Use DATABASE_URL environment variable or a secrets manager.",
        examples=["postgresql://user:password@localhost:5432/db"],
    ),
    SecretPattern(
        name="MySQL Connection String with credentials",
        secret_type=SecretType.DATABASE_URL,
        regex=re.compile(
            r"mysql://[A-Za-z0-9_]+:[^@]+@[A-Za-z0-9_.-]+", re.IGNORECASE
        ),
        severity=Severity.HIGH,
        remediation="Use DATABASE_URL environment variable or a secrets manager.",
        examples=["mysql://user:password@localhost:3306/db"],
    ),
    SecretPattern(
        name="Password in URL",
        secret_type=SecretType.PASSWORD_IN_URL,
        regex=re.compile(r"[?&](?:password|pwd|pass)=([^&]+)", re.IGNORECASE),
        severity=Severity.HIGH,
        remediation="Remove credentials from URLs. Use headers or a secrets manager.",
        examples=["?password=secret123"],
    ),
    # ---- MEDIUM ----
    SecretPattern(
        name="Environment Secret Variable",
        secret_type=SecretType.ENV_SECRET,
        regex=re.compile(
            r"(?:export\s+)?(?:secret|token|password|private[_-]?key)\s*[=:]\s*['\"]?([A-Za-z0-9_/-]{12,})['\"]?",
            re.IGNORECASE,
        ),
        severity=Severity.MEDIUM,
        remediation="Use a secrets manager instead of hardcoded env vars.",
        examples=["SECRET='my_secret_value'"],
        false_positive_indicators=[
            "example",
            "test",
            "placeholder",
            "dummy",
            "fake",
            "mock",
            "sample",
            "your_",
            "xxx",
            "000000000000",
            "Enum",
            "_TYPE",
            "_NAME",
        ],
    ),
]


def get_pattern_by_type(secret_type: SecretType) -> SecretPattern | None:
    """Get a pattern by its secret type enum.

    Returns the first pattern matching the given type.
    """
    for p in PATTERNS:
        if p.secret_type == secret_type:
            return p
    return None


def list_all_types() -> list[tuple[str, str, str]]:
    """Return a list of all secret types for --list-types output.

    Returns:
        List of (name, severity, remediation) tuples sorted by severity.
    """
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2}
    sorted_patterns = sorted(
        PATTERNS,
        key=lambda p: (severity_order[p.severity], p.name),
    )
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    for p in sorted_patterns:
        if p.name not in seen:
            seen.add(p.name)
            result.append((p.name, p.severity.value, p.remediation))
    return result
