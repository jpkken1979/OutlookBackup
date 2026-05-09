"""security-scanner agent — escanea codigo en busca de vulnerabilidades y patrones peligrosos."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    llm_summarize,
    main_wrapper,
)

# Patterns to scan for, with severity
DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern_regex, description, severity)
    (
        r"""(?:API_KEY|SECRET_KEY|ACCESS_TOKEN|PRIVATE_KEY)\s*=\s*["'][^"']{8,}["']""",
        "Hardcoded secret/API key",
        "critical",
    ),
    (r"""password\s*=\s*["'][^"']+["']""", "Hardcoded password", "critical"),
    (r"""token\s*=\s*["'][A-Za-z0-9_\-]{20,}["']""", "Hardcoded token", "critical"),
    (r"""-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----""", "Private key in source", "critical"),
    (r"""shell\s*=\s*True""", "subprocess with shell=True", "high"),
    (r"""\beval\s*\(""", "Use of eval()", "high"),
    (r"""\bexec\s*\(""", "Use of exec()", "high"),
    (r"""innerHTML\s*=""", "Direct innerHTML assignment (XSS risk)", "high"),
    (r"""dangerouslySetInnerHTML""", "dangerouslySetInnerHTML usage", "medium"),
    (r"""f["']SELECT\s""", "Potential SQL injection (f-string SELECT)", "high"),
    (r"""f["']INSERT\s""", "Potential SQL injection (f-string INSERT)", "high"),
    (r"""f["']UPDATE\s""", "Potential SQL injection (f-string UPDATE)", "high"),
    (r"""f["']DELETE\s""", "Potential SQL injection (f-string DELETE)", "high"),
    (r"""\.execute\s*\(\s*f["']""", "SQL execute with f-string", "high"),
    (r"""os\.system\s*\(""", "os.system() usage (use subprocess)", "medium"),
    (r"""pickle\.loads?\s*\(""", "Unsafe pickle deserialization", "medium"),
    (r"""yaml\.load\s*\((?!.*Loader)""", "Unsafe YAML load (no Loader)", "medium"),
    (r"""verify\s*=\s*False""", "SSL verification disabled", "medium"),
    (r"""CORS\s*\(\s*\*""", "Wildcard CORS", "low"),
    (r"""# ?TODO.*(?:hack|fixme|security)""", "Security TODO/FIXME", "low"),
]

# File extensions to scan
SCAN_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".rb", ".php"}

# Directories to skip
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    "dist",
    "build",
    ".next",
    "target",
    ".agent - copia",
    "_archive",
    ".bak",
}


def _should_scan(path: Path) -> bool:
    """Check if file should be scanned."""
    if path.suffix not in SCAN_EXTENSIONS:
        return False
    parts = set(path.parts)
    return not parts.intersection(SKIP_DIRS)


def _scan_patterns(root: Path) -> list[dict]:
    """Scan source files for dangerous patterns."""
    findings: list[dict] = []
    file_count = 0

    for ext in SCAN_EXTENSIONS:
        for filepath in root.rglob(f"*{ext}"):
            if not _should_scan(filepath):
                continue
            file_count += 1
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                for pattern, desc, severity in DANGEROUS_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Skip common false positives
                        stripped = line.strip()
                        if (
                            stripped.startswith("#")
                            or stripped.startswith("//")
                            or stripped.startswith("*")
                        ):
                            if severity != "critical":
                                continue
                        findings.append(
                            {
                                "file": str(filepath.relative_to(root)),
                                "line": line_num,
                                "pattern": desc,
                                "severity": severity,
                                "snippet": line.strip()[:120],
                            }
                        )

    return findings


def _check_env_files(root: Path) -> list[dict]:
    """Check for .env files that shouldn't be committed."""
    findings: list[dict] = []

    env_files = list(root.rglob(".env"))
    env_files += list(root.rglob(".env.local"))
    env_files += list(root.rglob(".env.production"))

    for env_file in env_files:
        parts = set(env_file.parts)
        if parts.intersection(SKIP_DIRS):
            continue
        findings.append(
            {
                "file": str(env_file.relative_to(root)),
                "line": 0,
                "pattern": ".env file present (should not be committed)",
                "severity": "high",
                "snippet": "",
            }
        )

    return findings


def _check_gitignore(root: Path) -> list[dict]:
    """Check if .gitignore protects sensitive files."""
    findings: list[dict] = []
    gitignore = root / ".gitignore"

    if not gitignore.exists():
        findings.append(
            {
                "file": ".gitignore",
                "line": 0,
                "pattern": "No .gitignore file found",
                "severity": "high",
                "snippet": "",
            }
        )
        return findings

    content = gitignore.read_text(encoding="utf-8", errors="ignore")
    required_patterns = [".env", "*.pem", "*.key"]
    for pat in required_patterns:
        if pat not in content:
            findings.append(
                {
                    "file": ".gitignore",
                    "line": 0,
                    "pattern": f".gitignore missing pattern: {pat}",
                    "severity": "medium",
                    "snippet": "",
                }
            )

    return findings


def execute(task: str, root: Path) -> dict:
    """Run security scan on the project."""
    all_findings: list[dict] = []

    all_findings.extend(_scan_patterns(root))
    all_findings.extend(_check_env_files(root))
    all_findings.extend(_check_gitignore(root))

    # Count by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        sev = f.get("severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    raw = {
        "total_findings": len(all_findings),
        "severity_counts": severity_counts,
        "findings": all_findings[:200],
    }

    # Build summary for LLM
    summary_parts = [
        f"Total findings: {len(all_findings)}",
        f"Critical: {severity_counts['critical']}, High: {severity_counts['high']}, "
        f"Medium: {severity_counts['medium']}, Low: {severity_counts['low']}",
        "",
    ]
    for f in all_findings[:50]:
        summary_parts.append(f"[{f['severity'].upper()}] {f['file']}:{f['line']} — {f['pattern']}")
        if f["snippet"]:
            summary_parts.append(f"  > {f['snippet']}")

    raw_text = "\n".join(summary_parts)

    llm_result = llm_summarize(
        raw_text,
        "Eres un experto en seguridad de software. Analiza estos hallazgos de un escaneo de seguridad. "
        "Clasifica cuáles son vulnerabilidades reales vs falsos positivos. "
        "Para las reales, recomienda fixes concretos priorizados por impacto. "
        "Responde en español.",
    )

    if llm_result:
        return {"status": "success", "summary": llm_result, "raw": raw, "llm_used": "auto"}

    # Fallback
    status = "success"
    if severity_counts["critical"] > 0:
        status = "warning"

    fallback_lines = [
        f"Security Scan — {len(all_findings)} hallazgos",
        f"  Critical: {severity_counts['critical']}",
        f"  High: {severity_counts['high']}",
        f"  Medium: {severity_counts['medium']}",
        f"  Low: {severity_counts['low']}",
        "",
    ]
    for f in all_findings[:30]:
        fallback_lines.append(f"[{f['severity'].upper()}] {f['file']}:{f['line']} — {f['pattern']}")
        if f["snippet"]:
            fallback_lines.append(f"  > {f['snippet']}")

    return {"status": status, "summary": "\n".join(fallback_lines), "raw": raw, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("security-scanner", execute)
