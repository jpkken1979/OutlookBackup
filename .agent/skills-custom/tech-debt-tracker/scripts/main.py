"""Tech Debt Tracker — CLI entry point.

Usage:
    py .agent/skills-custom/tech-debt-tracker/scripts/main.py [options]
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

# Ensure skill scripts are on path for direct invocation
if __name__ == "__main__" and __package__ is None:
    _SKILL_ROOT = Path(__file__).parent.parent
    if str(_SKILL_ROOT) not in sys.path:
        sys.path.insert(0, str(_SKILL_ROOT))

from scripts.detectors import DebtIssue, detect_debt_in_file  # type: ignore[attr-defined]
from scripts.rules import DEBT_RULES, DebtSeverity, DebtType  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

# Supported surfaces and their directories
SURFACES: dict[str, list[str]] = {
    ".agent": [".agent"],
    "nexus-app/src": ["nexus-app/src"],
    "src": ["src"],
    "mcp-server": ["mcp-server"],
}


@dataclass
class TechDebtReport:
    """Aggregated report for a scan."""

    scan_date: str
    scope: str
    issues: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DebtSeverity.CRITICAL)

    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DebtSeverity.HIGH)

    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DebtSeverity.MEDIUM)

    def low_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DebtSeverity.LOW)

    def score(self) -> int:
        return max(
            0,
            100
            - self.critical_count() * 10
            - self.high_count() * 5
            - self.medium_count() * 2,
        )

    def to_dict(self) -> dict:
        return {
            "scan_date": self.scan_date,
            "scope": self.scope,
            "summary": {
                "critical": self.critical_count(),
                "high": self.high_count(),
                "medium": self.medium_count(),
                "low": self.low_count(),
                "score": self.score(),
            },
            "issues": [
                {
                    "type": i.debt_type.value,
                    "severity": i.severity.value,
                    "rule": i.rule_id,
                    "file": i.file,
                    "line": i.line,
                    "message": i.message,
                    "detail": i.detail,
                }
                for i in self.issues
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Tech Debt Report - {self.scope}",
            f"Generated: {self.scan_date}",
            "",
            f"**Score: {self.score()}/100**",
            f"| Severity | Count |",
            f"|---|---|",
            f"| Critical | {self.critical_count()} |",
            f"| High | {self.high_count()} |",
            f"| Medium | {self.medium_count()} |",
            f"| Low | {self.low_count()} |",
            "",
            "## Critical (arreglar ASAP)",
            "",
        ]

        criticals = [i for i in self.issues if i.severity == DebtSeverity.CRITICAL]
        if not criticals:
            lines.append("_None_")
        else:
            for i in criticals:
                lines.append(
                    f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}"
                )

        lines += [
            "",
            "## High (resolver en sprint)",
            "",
        ]
        highs = [i for i in self.issues if i.severity == DebtSeverity.HIGH]
        if not highs:
            lines.append("_None_")
        else:
            for i in highs:
                lines.append(
                    f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}"
                )

        lines += [
            "",
            "## Medium (trackear)",
            "",
        ]
        mediums = [i for i in self.issues if i.severity == DebtSeverity.MEDIUM]
        if not mediums:
            lines.append("_None_")
        else:
            for i in mediums:
                lines.append(
                    f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}"
                )

        lines += [
            "",
            "## Low (considerar)",
            "",
        ]
        lows = [i for i in self.issues if i.severity == DebtSeverity.LOW]
        if not lows:
            lines.append("_None_")
        else:
            for i in lows:
                lines.append(
                    f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}"
                )

        lines += [
            "",
            "---",
            f"Total files scanned: {len(set(i.file for i in self.issues))}",
            f"Total issues: {len(self.issues)}",
        ]

        return "\n".join(lines)


def get_files_for_scope(scope: str) -> list[Path]:
    """Walk directories to find Python/TS/RS files."""
    if scope == "full":
        roots = [".agent", "nexus-app/src", "src", "mcp-server"]
    elif scope in SURFACES:
        roots = SURFACES[scope]
    else:
        roots = [scope]

    files: list[Path] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            logger.warning("Scope %s does not exist, skipping", root)
            continue
        # If scope is a single file, add it directly
        if root_path.is_file():
            files.append(root_path)
            continue
        for ext in (".py", ".ts", ".tsx", ".rs"):
            files.extend(root_path.rglob(f"*{ext}"))

    # Filter out common non-source dirs
    skip_dirs = {".git", "node_modules", "target", "dist", "build", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    return [f for f in files if not any(part in f.parts for part in skip_dirs)]


def run_scan(
    scope: str,
    debt_types: Optional[list[str]] = None,
    debt_filter: Optional[str] = None,
) -> TechDebtReport:
    """Perform a full tech debt scan on the given scope.

    Args:
        scope: One of .agent, nexus-app/src, src, full, or a path.
        debt_types: List of DebtType values to run (default: all).
        debt_filter: Only run detectors matching this substring (e.g. 'types').

    Returns:
        TechDebtReport with all issues found.
    """
    # Resolve debt types
    if debt_filter:
        selected_types: list[DebtType] = [
            t for t in DebtType
            if debt_filter.lower() in t.value
        ]
    elif debt_types:
        selected_types = [DebtType(t) for t in debt_types]
    else:
        selected_types = list(DebtType)

    files = get_files_for_scope(scope)
    logger.info("Scanning %d files in scope '%s'", len(files), scope)

    all_issues: list[DebtIssue] = []
    scanned = 0

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug("Could not read %s: %s", file_path, exc)
            continue

        issues = detect_debt_in_file(
            file_path=str(file_path),
            content=content,
            debt_types=selected_types if selected_types else None,
        )
        all_issues.extend(issues)
        scanned += 1

    report = TechDebtReport(
        scan_date=str(date.today()),
        scope=scope,
        issues=all_issues,
    )
    report.summary = {
        "total_files_scanned": scanned,
        "critical": report.critical_count(),
        "high": report.high_count(),
        "medium": report.medium_count(),
        "low": report.low_count(),
        "score": report.score(),
    }

    logger.info(
        "Scan complete: %d files, %d issues (score=%d)",
        scanned,
        len(all_issues),
        report.score(),
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tech-debt-tracker",
        description="Identify and track technical debt in the codebase.",
    )
    parser.add_argument(
        "--scope",
        default="full",
        help="Scope to scan: .agent | nexus-app/src | src | full | or a path",
    )
    parser.add_argument(
        "--debt",
        dest="debt_filter",
        default=None,
        help="Filter by debt type: types | todos | complexity | naming | duplicates | unused",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        default="text",
        choices=["text", "json", "markdown"],
        help="Output format",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )

    try:
        report = run_scan(
            scope=args.scope,
            debt_filter=args.debt_filter,
        )
    except Exception as exc:
        logger.error("Scan failed: %s", exc)
        sys.exit(1)

    # Output
    if args.output_format == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif args.output_format == "markdown":
        print(report.to_markdown())
    else:
        # Plain text
        print(f"TECH DEBT REPORT - {report.scope}")
        print(f"Generated: {report.scan_date}")
        print()
        print(f"Score: {report.score()}/100")
        print()
        print("CRITICAL (arreglar ASAP)")
        for i in [x for x in report.issues if x.severity == DebtSeverity.CRITICAL]:
            print(f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}")
        print()
        print("HIGH (resolver en sprint)")
        for i in [x for x in report.issues if x.severity == DebtSeverity.HIGH]:
            print(f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}")
        print()
        print("MEDIUM (trackear)")
        for i in [x for x in report.issues if x.severity == DebtSeverity.MEDIUM]:
            print(f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}")
        print()
        print("LOW (considerar)")
        for i in [x for x in report.issues if x.severity == DebtSeverity.LOW]:
            print(f"  [{i.rule_id}] {i.file}:{i.line} - {i.message}")
        print()
        print("SUMMARY")
        print(f"  Total files scanned: {report.summary.get('total_files_scanned', 0)}")
        print(f"  Critical: {report.critical_count()}")
        print(f"  High: {report.high_count()}")
        print(f"  Medium: {report.medium_count()}")
        print(f"  Low: {report.low_count()}")


if __name__ == "__main__":
    main()
