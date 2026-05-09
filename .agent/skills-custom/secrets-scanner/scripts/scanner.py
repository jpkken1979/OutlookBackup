"""File scanning engine for secrets detection.

Handles file discovery, content reading, pattern matching,
and git diff scanning.
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from entropy import EntropyMatch, get_high_entropy_strings
from patterns import PATTERNS, Severity, SecretPattern, SecretType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SecretFinding:
    """A single secret detected in a file."""

    id: str
    severity: Severity
    secret_type: SecretType
    file_path: str
    line: int
    matched: str
    context: str
    remediation: str
    is_entropy: bool = False
    suppressed: bool = False

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "type": self.secret_type.value,
            "file": self.file_path,
            "line": self.line,
            "matched": self.matched[:8] + "***",
            "context": self.context.strip(),
            "remediation": self.remediation,
            "is_entropy": self.is_entropy,
            "suppressed": self.suppressed,
        }


@dataclass
class ScanResult:
    """Result of a secrets scan."""

    scan_date: str
    scope: str
    files_scanned: int
    files_with_secrets: int
    findings: list[SecretFinding] = field(default_factory=list)

    @property
    def secrets_found(self) -> int:
        return sum(1 for f in self.findings if not f.suppressed)

    @property
    def critical_count(self) -> int:
        return sum(
            1
            for f in self.findings
            if f.severity == Severity.CRITICAL and not f.suppressed
        )

    @property
    def high_count(self) -> int:
        return sum(
            1
            for f in self.findings
            if f.severity == Severity.HIGH and not f.suppressed
        )

    @property
    def medium_count(self) -> int:
        return sum(
            1
            for f in self.findings
            if f.severity == Severity.MEDIUM and not f.suppressed
        )

    @property
    def has_critical(self) -> bool:
        return any(
            f.severity == Severity.CRITICAL and not f.suppressed
            for f in self.findings
        )

    @property
    def has_secrets(self) -> bool:
        return any(not f.suppressed for f in self.findings)

    def to_dict(self) -> dict:
        return {
            "scan_date": self.scan_date,
            "scope": self.scope,
            "files_scanned": self.files_scanned,
            "secrets_found": self.secrets_found,
            "files_with_secrets": self.files_with_secrets,
            "findings": [f.to_dict() for f in self.findings if not f.suppressed],
            "summary": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
            },
        }


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        ".svn",
        ".hg",
        "vendor",
        "venv",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        ".tox",
        ".eggs",
        "*.egg-info",
    }
)

SCANNABLE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".go",
        ".java",
        ".rb",
        ".php",
        ".cs",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".swift",
        ".kt",
        ".scala",
        ".rs",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".psm1",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".config",
        ".env",
        ".example",
        ".tf",
        ".tfvars",
        ".dockerfile",
        ".gradle",
        ".properties",
        ".xml",
        ".sql",
        ".md",
        ".rst",
        "Makefile",
        "Dockerfile",
        "Vagrantfile",
        "Brewfile",
        "Gemfile",
        "Rakefile",
    }
)


def is_scannable_file(path: Path) -> bool:
    """Check if a file should be scanned."""
    name = path.name
    if name.startswith(".") and name not in (".env", ".env.example"):
        return False
    suffix = "".join(path.suffixes).lower()
    if suffix in SCANNABLE_EXTENSIONS:
        return True
    if path.suffix.lower() in SCANNABLE_EXTENSIONS:
        return True
    if name in SCANNABLE_EXTENSIONS:
        return True
    return False


def walk_files(
    root: Path,
    exclude_dirs: Optional[frozenset[str]] = None,
    exclude_names: Optional[frozenset[str]] = None,
) -> Iterator[Path]:
    """Walk a directory tree yielding scannable files."""
    if exclude_dirs is None:
        exclude_dirs = DEFAULT_EXCLUDE_DIRS
    if exclude_names is None:
        exclude_names = frozenset()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in exclude_dirs
            and not any(d.startswith(p) for p in exclude_names)
        ]
        for filename in filenames:
            if filename in exclude_names:
                continue
            file_path = Path(dirpath) / filename
            if is_scannable_file(file_path):
                yield file_path


# ---------------------------------------------------------------------------
# Content scanning
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = 1 * 1024 * 1024
BINARY_SIGNATURES = (b"\x00", b"\xfe\xff", b"\xff\xfe")


def is_binary(path: Path) -> bool:
    """Check if a file appears to be binary."""
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return True
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
            return any(chunk.startswith(sig) for sig in BINARY_SIGNATURES)
    except (OSError, IOError):
        return True


def _is_masked(text: str) -> bool:
    """Check if a string is already masked/redacted."""
    masked_indicators = (
        "***",
        "xxxx",
        "XXXX",
        "REDACTED",
        "MASKED",
        "HIDDEN",
        "<secret>",
        "${",
        "$ENV_",
    )
    return any(text.upper().startswith(ind.upper()) for ind in masked_indicators)


_counter = 0


def _get_finding_counter() -> Iterator[int]:
    """Yield incrementing finding IDs."""
    global _counter
    while True:
        _counter += 1
        yield _counter


def reset_finding_counter() -> None:
    """Reset the finding counter."""
    global _counter
    _counter = 0


def scan_content(
    content: str,
    file_path: str,
    entropy_threshold: float = 4.5,
    entropy_enabled: bool = True,
) -> list[SecretFinding]:
    """Scan file content for secrets using patterns and entropy."""
    findings: list[SecretFinding] = []
    lines = content.split("\n")
    finding_counter = _get_finding_counter()
    entropy_counter = 1000

    for pattern in PATTERNS:
        for match in pattern.regex.finditer(content):
            matched_text = match.group(0)
            line_num = content[: match.start()].count("\n") + 1
            context = ""
            if 0 < line_num <= len(lines):
                context = lines[line_num - 1]
            if pattern.is_false_positive(context):
                continue
            if _is_masked(matched_text):
                continue
            findings.append(
                SecretFinding(
                    id=f"S{next(finding_counter):03d}",
                    severity=pattern.severity,
                    secret_type=pattern.secret_type,
                    file_path=file_path,
                    line=line_num,
                    matched=matched_text,
                    context=context.strip(),
                    remediation=pattern.remediation,
                    is_entropy=False,
                )
            )

    if entropy_enabled:
        entropy_matches = get_high_entropy_strings(content, threshold=entropy_threshold)
        for em in entropy_matches:
            if any(f.line == em.line_number and not f.is_entropy for f in findings):
                continue
            ctx = ""
            if 0 < em.line_number <= len(lines):
                ctx = lines[em.line_number - 1]
            findings.append(
                SecretFinding(
                    id=f"S{entropy_counter}",
                    severity=Severity.HIGH,
                    secret_type=SecretType.HIGH_ENTROPY,
                    file_path=file_path,
                    line=em.line_number,
                    matched=em.value[:8] + "...",
                    context=ctx.strip(),
                    remediation="Review: high-entropy string may be a secret. "
                    "Ensure it is not a real credential.",
                    is_entropy=True,
                )
            )
            entropy_counter += 1

    return findings


# ---------------------------------------------------------------------------
# Git integration
# ---------------------------------------------------------------------------


def get_git_diff_files() -> Iterator[tuple[str, str]]:
    """Get files that have been modified (staged or unstaged) in git."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import subprocess; "
                "r1=subprocess.run(['git','diff','--no-color'],"
                "capture_output=True,text=True); "
                "r2=subprocess.run(['git','diff','--cached','--no-color'],"
                "capture_output=True,text=True); "
                "print(r1.stdout + r2.stdout)",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
            shell=False,
        )
        if result.returncode != 0:
            logger.warning("git diff failed: %s", result.stderr)
            return

        diff = result.stdout
        if not diff.strip():
            return

        current_file: Optional[str] = None
        content_lines: list[str] = []

        for line in diff.splitlines():
            if line.startswith("diff --git"):
                if current_file and content_lines:
                    new_content = "\n".join(
                        l[1:] for l in content_lines if l.startswith("+")
                    )
                    yield current_file, new_content
                parts = line.split(" b/", 1)
                if len(parts) == 2:
                    current_file = parts[1]
                content_lines = []
            elif line.startswith("+") and not line.startswith("+++"):
                content_lines.append(line)
            elif line.startswith(" "):
                content_lines.append(line)

        if current_file and content_lines:
            new_content = "\n".join(
                l[1:] for l in content_lines if l.startswith("+")
            )
            yield current_file, new_content

    except Exception as e:
        logger.error("Error running git diff: %s", e)


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------


def scan_path(
    scope: str | Path,
    exclude_patterns: Optional[list[str]] = None,
    entropy_threshold: float = 4.5,
    entropy_enabled: bool = True,
    git_diff: bool = False,
) -> ScanResult:
    """Scan a path for secrets."""
    exclude_names: frozenset[str] = frozenset(exclude_patterns or [])
    scope_path = Path(scope)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    result = ScanResult(
        scan_date=now,
        scope=str(scope),
        files_scanned=0,
        files_with_secrets=0,
    )

    if git_diff:
        seen_files: set[str] = set()
        for file_path, diff_content in get_git_diff_files():
            if file_path in seen_files:
                continue
            seen_files.add(file_path)
            if not is_scannable_file(Path(file_path)):
                continue
            result.files_scanned += 1
            findings = scan_content(
                diff_content,
                file_path,
                entropy_threshold=entropy_threshold,
                entropy_enabled=entropy_enabled,
            )
            if findings:
                result.files_with_secrets += 1
                result.findings.extend(findings)
    else:
        target = Path(scope)
        if target.is_file():
            files = [target]
        elif target.is_dir():
            files = list(walk_files(target, exclude_names=exclude_names))
        else:
            logger.error("Path does not exist: %s", scope)
            return result

        for file_path in files:
            if is_binary(file_path):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except (OSError, IOError) as e:
                logger.warning("Could not read %s: %s", file_path, e)
                continue

            result.files_scanned += 1
            findings = scan_content(
                content,
                str(file_path),
                entropy_threshold=entropy_threshold,
                entropy_enabled=entropy_enabled,
            )
            if findings:
                result.files_with_secrets += 1
                result.findings.extend(findings)

    return result


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_text(result: ScanResult, show_fix: bool = False) -> str:
    """Format scan result as human-readable text."""
    lines: list[str] = []
    divider = "=" * 60

    lines.append(f"SECRETS SCAN REPORT — {result.scope}")
    lines.append(divider)
    lines.append(f"Scan date: {result.scan_date}")
    lines.append(f"Files scanned: {result.files_scanned:,}")
    lines.append(f"Secrets found: {result.secrets_found}")

    if result.secrets_found == 0:
        lines.append("\nNo secrets detected.")
        lines.append(divider)
        return "\n".join(lines)

    lines.append("")

    by_severity: dict[Severity, list[SecretFinding]] = {
        Severity.CRITICAL: [],
        Severity.HIGH: [],
        Severity.MEDIUM: [],
    }
    for f in result.findings:
        if not f.suppressed:
            by_severity[f.severity].append(f)

    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM]:
        findings = by_severity[severity]
        if not findings:
            continue
        lines.append(f"{severity.value} ({len(findings)})")
        for finding in findings:
            mask = finding.matched[:8] + "***" if len(finding.matched) > 8 else "***"
            lines.append(
                f"  [{finding.id}] {finding.file_path}:{finding.line} — {mask}"
            )
            lines.append(f"     -> {finding.remediation}")
        lines.append("")

    lines.append("RECOMMENDATIONS:")
    lines.append("  1. Run secrets-scanner in CI/CD pipeline")
    lines.append("  2. Enable pre-commit hook: secrets-scanner --git-hooks")
    lines.append("  3. Rotate exposed credentials immediately")
    lines.append("")
    lines.append("SECRETS FOUND — DO NOT COMMIT")

    return "\n".join(lines)


def format_json(result: ScanResult) -> str:
    """Format scan result as JSON."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
