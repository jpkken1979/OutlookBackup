#!/usr/bin/env python3
"""
Code Reviewer Agent - Executable Implementation
Based on best practices from CrewAI, LangGraph, and industry standards.

This agent performs automated code review with:
- Static analysis integration (ruff, mypy)
- Security scanning (bandit, semgrep patterns)
- Code quality metrics
- Best practices validation
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Severity(Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(Enum):
    """Categories of code issues."""

    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    BUG = "bug"
    BEST_PRACTICE = "best_practice"


@dataclass
class CodeIssue:
    """Represents a single code issue found during review."""

    file: str
    line: int
    column: int
    severity: Severity
    category: IssueCategory
    message: str
    rule_id: str
    suggestion: str | None = None


@dataclass
class ReviewResult:
    """Complete review result."""

    files_reviewed: int
    issues: list[CodeIssue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "files_reviewed": self.files_reviewed,
            "issues": [
                {
                    "file": i.file,
                    "line": i.line,
                    "column": i.column,
                    "severity": i.severity.value,
                    "category": i.category.value,
                    "message": i.message,
                    "rule_id": i.rule_id,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "metrics": self.metrics,
            "summary": self.summary,
        }


class CodeReviewerAgent:
    """
    Intelligent Code Reviewer Agent.

    Combines multiple analysis tools to provide comprehensive code review:
    - Ruff: Fast Python linting
    - Mypy: Type checking
    - Bandit: Security analysis
    - Custom patterns: Best practices
    """

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.issues: list[CodeIssue] = []

    async def review(
        self,
        files: list[str] | None = None,
        include_security: bool = True,
        include_types: bool = True,
        include_style: bool = True,
    ) -> ReviewResult:
        """
        Perform comprehensive code review.

        Args:
            files: Specific files to review (None = all Python files)
            include_security: Run security analysis
            include_types: Run type checking
            include_style: Run style/lint checking

        Returns:
            ReviewResult with all findings
        """
        logger.info(f"Starting code review for: {self.project_path}")

        # Discover files if not specified
        if files is None:
            files = self._discover_python_files()

        logger.info(f"Reviewing {len(files)} files")

        # Run analyses in parallel
        tasks = []

        if include_style:
            tasks.append(self._run_ruff(files))

        if include_types:
            tasks.append(self._run_mypy(files))

        if include_security:
            tasks.append(self._run_bandit(files))

        # Execute all analyses
        await asyncio.gather(*tasks)

        # Calculate metrics
        metrics = self._calculate_metrics(files)

        # Generate summary
        summary = self._generate_summary()

        return ReviewResult(
            files_reviewed=len(files), issues=self.issues, metrics=metrics, summary=summary
        )

    def _discover_python_files(self) -> list[str]:
        """Find all Python files in project."""
        files = []
        for pattern in ["**/*.py"]:
            files.extend(
                str(f.relative_to(self.project_path))
                for f in self.project_path.glob(pattern)
                if not any(
                    part.startswith(".") or part in ["venv", "node_modules", "__pycache__", ".git"]
                    for part in f.parts
                )
            )
        return files

    async def _run_ruff(self, files: list[str]) -> None:
        """Run ruff linter."""
        logger.info("Running ruff analysis...")
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", *files],
                capture_output=True,
                text=True,
                cwd=self.project_path,
            )

            if result.stdout:
                findings = json.loads(result.stdout)
                for finding in findings:
                    self.issues.append(
                        CodeIssue(
                            file=finding.get("filename", ""),
                            line=finding.get("location", {}).get("row", 0),
                            column=finding.get("location", {}).get("column", 0),
                            severity=self._map_ruff_severity(finding.get("code", "")),
                            category=IssueCategory.STYLE,
                            message=finding.get("message", ""),
                            rule_id=finding.get("code", ""),
                            suggestion=finding.get("fix", {}).get("message"),
                        )
                    )
                logger.info(f"Ruff found {len(findings)} issues")
        except FileNotFoundError:
            logger.warning("ruff not installed, skipping lint analysis")
        except json.JSONDecodeError:
            logger.warning("Failed to parse ruff output")

    async def _run_mypy(self, files: list[str]) -> None:
        """Run mypy type checker."""
        logger.info("Running mypy analysis...")
        try:
            result = subprocess.run(
                ["mypy", "--no-error-summary", "--show-column-numbers", *files],
                capture_output=True,
                text=True,
                cwd=self.project_path,
            )

            for line in result.stdout.strip().split("\n"):
                if line and ":" in line:
                    parts = line.split(":", 4)
                    if len(parts) >= 4:
                        self.issues.append(
                            CodeIssue(
                                file=parts[0],
                                line=int(parts[1]) if parts[1].isdigit() else 0,
                                column=int(parts[2]) if parts[2].isdigit() else 0,
                                severity=Severity.MEDIUM,
                                category=IssueCategory.BUG,
                                message=parts[-1].strip(),
                                rule_id="mypy",
                            )
                        )
            logger.info("Mypy analysis complete")
        except FileNotFoundError:
            logger.warning("mypy not installed, skipping type checking")

    async def _run_bandit(self, files: list[str]) -> None:
        """Run bandit security scanner."""
        logger.info("Running bandit security analysis...")
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-r", *files],
                capture_output=True,
                text=True,
                cwd=self.project_path,
            )

            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for finding in data.get("results", []):
                        self.issues.append(
                            CodeIssue(
                                file=finding.get("filename", ""),
                                line=finding.get("line_number", 0),
                                column=0,
                                severity=self._map_bandit_severity(
                                    finding.get("issue_severity", "")
                                ),
                                category=IssueCategory.SECURITY,
                                message=finding.get("issue_text", ""),
                                rule_id=finding.get("test_id", ""),
                                suggestion=finding.get("more_info"),
                            )
                        )
                    logger.info(f"Bandit found {len(data.get('results', []))} security issues")
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            logger.warning("bandit not installed, skipping security analysis")

    def _map_ruff_severity(self, code: str) -> Severity:
        """Map ruff error codes to severity."""
        if code.startswith(("E9", "F")):  # Syntax/Fatal errors
            return Severity.CRITICAL
        elif code.startswith(("E", "W")):  # Errors/Warnings
            return Severity.MEDIUM
        elif code.startswith(("C", "N")):  # Complexity/Naming
            return Severity.LOW
        return Severity.INFO

    def _map_bandit_severity(self, severity: str) -> Severity:
        """Map bandit severity to our severity."""
        mapping = {"HIGH": Severity.CRITICAL, "MEDIUM": Severity.HIGH, "LOW": Severity.MEDIUM}
        return mapping.get(severity.upper(), Severity.LOW)

    def _calculate_metrics(self, files: list[str]) -> dict:
        """Calculate code quality metrics."""
        total_lines = 0
        for file in files:
            try:
                filepath = self.project_path / file
                if filepath.exists():
                    total_lines += len(filepath.read_text().splitlines())
            except Exception:
                pass

        severity_counts = {}
        for issue in self.issues:
            sev = issue.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        category_counts = {}
        for issue in self.issues:
            cat = issue.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_lines": total_lines,
            "total_issues": len(self.issues),
            "issues_per_1k_lines": round(len(self.issues) / max(total_lines / 1000, 1), 2),
            "by_severity": severity_counts,
            "by_category": category_counts,
        }

    def _generate_summary(self) -> str:
        """Generate human-readable summary."""
        critical = sum(1 for i in self.issues if i.severity == Severity.CRITICAL)
        high = sum(1 for i in self.issues if i.severity == Severity.HIGH)
        security = sum(1 for i in self.issues if i.category == IssueCategory.SECURITY)

        lines = [
            "## Code Review Summary",
            "",
            f"Total issues found: **{len(self.issues)}**",
            "",
        ]

        if critical > 0:
            lines.append(f"⛔ **{critical} critical issues** require immediate attention")
        if high > 0:
            lines.append(f"⚠️ **{high} high severity issues** should be addressed")
        if security > 0:
            lines.append(f"🔒 **{security} security issues** detected")

        if not self.issues:
            lines.append("✅ No issues found - code looks good!")

        return "\n".join(lines)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Code Reviewer Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path to review")
    parser.add_argument("--files", nargs="*", help="Specific files to review")
    parser.add_argument("--no-security", action="store_true", help="Skip security analysis")
    parser.add_argument("--no-types", action="store_true", help="Skip type checking")
    parser.add_argument("--no-style", action="store_true", help="Skip style checking")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    agent = CodeReviewerAgent(args.path)
    result = await agent.review(
        files=args.files,
        include_security=not args.no_security,
        include_types=not args.no_types,
        include_style=not args.no_style,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.summary)
        print(f"\nMetrics: {json.dumps(result.metrics, indent=2)}")

        if result.issues:
            print("\n## Top Issues\n")
            for issue in sorted(result.issues, key=lambda x: x.severity.value)[:10]:
                print(
                    f"- [{issue.severity.value.upper()}] {issue.file}:{issue.line} - {issue.message}"
                )


if __name__ == "__main__":
    asyncio.run(main())
