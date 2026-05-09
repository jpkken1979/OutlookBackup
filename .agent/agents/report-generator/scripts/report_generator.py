#!/usr/bin/env python3
"""
Report Generator Agent - Automated project report generation.

Usage:
    python report_generator.py <project_path> [--type status|health|summary] [--json]
"""

import argparse
import contextlib
import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ProjectMetrics:
    """Project metrics."""

    total_files: int = 0
    total_lines: int = 0
    languages: dict = field(default_factory=dict)
    test_count: int = 0
    dependency_count: int = 0


@dataclass
class HealthStatus:
    """Health check status."""

    name: str
    status: str  # healthy, warning, critical
    message: str


@dataclass
class ProjectReport:
    """Project report."""

    project_path: str
    report_type: str
    timestamp: str
    metrics: dict = field(default_factory=dict)
    health_checks: list = field(default_factory=list)
    recent_activity: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    summary: str = ""


class ReportGenerator:
    """Automated report generation agent."""

    def __init__(self, project_path: str, report_type: str = "status"):
        self.project_path = Path(project_path)
        self.report_type = report_type

    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        try:
            return len(file_path.read_text().splitlines())
        except Exception:
            return 0

    def _get_git_log(self, limit: int = 10) -> list[str]:
        """Get recent git commits."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{limit}"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip().split("\n") if result.stdout else []
        except Exception:
            return []

    def _get_git_status(self) -> dict:
        """Get git status."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = result.stdout.strip().split("\n") if result.stdout else []
            return {
                "modified": len([l for l in lines if l.startswith(" M")]),
                "added": len([l for l in lines if l.startswith("A")]),
                "untracked": len([l for l in lines if l.startswith("??")]),
                "deleted": len([l for l in lines if l.startswith(" D")]),
            }
        except Exception:
            return {}

    def collect_metrics(self) -> ProjectMetrics:
        """Collect project metrics."""
        metrics = ProjectMetrics()

        # Count files by extension
        extensions = {}
        for file_path in self.project_path.rglob("*"):
            if file_path.is_file():
                if any(
                    skip in str(file_path)
                    for skip in ["node_modules", ".git", "venv", "__pycache__"]
                ):
                    continue
                metrics.total_files += 1
                ext = file_path.suffix.lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1
                    if ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"]:
                        metrics.total_lines += self._count_lines(file_path)

        metrics.languages = dict(sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10])

        # Count tests
        test_files = (
            list(self.project_path.rglob("test_*.py"))
            + list(self.project_path.rglob("*.test.ts"))
            + list(self.project_path.rglob("*.spec.ts"))
        )
        metrics.test_count = len(test_files)

        # Count dependencies
        if (self.project_path / "package.json").exists():
            try:
                pkg = json.loads((self.project_path / "package.json").read_text())
                metrics.dependency_count = len(pkg.get("dependencies", {}))
            except Exception:
                pass
        elif (self.project_path / "requirements.txt").exists():
            with contextlib.suppress(Exception):
                metrics.dependency_count = len(
                    (self.project_path / "requirements.txt").read_text().splitlines()
                )

        return metrics

    def run_health_checks(self) -> list[HealthStatus]:
        """Run health checks."""
        checks = []

        # Check for README
        has_readme = (self.project_path / "README.md").exists()
        checks.append(
            HealthStatus(
                name="Documentation",
                status="healthy" if has_readme else "warning",
                message="README.md exists" if has_readme else "Missing README.md",
            )
        )

        # Check for tests
        test_count = len(list(self.project_path.rglob("test_*.py"))) + len(
            list(self.project_path.rglob("*.test.ts"))
        )
        checks.append(
            HealthStatus(
                name="Tests",
                status="healthy" if test_count > 5 else "warning" if test_count > 0 else "critical",
                message=f"{test_count} test files found",
            )
        )

        # Check for .env.example
        has_env_example = (self.project_path / ".env.example").exists()
        has_env = (self.project_path / ".env").exists()
        if has_env and not has_env_example:
            checks.append(
                HealthStatus(
                    name="Environment",
                    status="warning",
                    message=".env exists but .env.example missing",
                )
            )
        else:
            checks.append(
                HealthStatus(
                    name="Environment", status="healthy", message="Environment configuration OK"
                )
            )

        # Check for CI/CD
        has_ci = (self.project_path / ".github" / "workflows").exists() or (
            self.project_path / ".gitlab-ci.yml"
        ).exists()
        checks.append(
            HealthStatus(
                name="CI/CD",
                status="healthy" if has_ci else "warning",
                message="CI/CD configured" if has_ci else "No CI/CD configuration",
            )
        )

        # Check for security files
        has_gitignore = (self.project_path / ".gitignore").exists()
        checks.append(
            HealthStatus(
                name="Security",
                status="healthy" if has_gitignore else "critical",
                message=".gitignore configured" if has_gitignore else "Missing .gitignore",
            )
        )

        return checks

    def generate_summary(self, metrics: ProjectMetrics, health_checks: list[HealthStatus]) -> str:
        """Generate executive summary."""
        health_score = (
            sum(1 for h in health_checks if h.status == "healthy") / len(health_checks) * 100
        )

        top_language = list(metrics.languages.keys())[0] if metrics.languages else "Unknown"

        warnings = [h for h in health_checks if h.status == "warning"]
        critical = [h for h in health_checks if h.status == "critical"]

        summary_lines = [
            f"Project contains {metrics.total_files} files with {metrics.total_lines:,} lines of code.",
            f"Primary language: {top_language}.",
            f"Health score: {health_score:.0f}%.",
        ]

        if critical:
            summary_lines.append(f"CRITICAL: {len(critical)} issues require immediate attention.")
        if warnings:
            summary_lines.append(f"Warnings: {len(warnings)} items need review.")

        return " ".join(summary_lines)

    def generate_report(self) -> ProjectReport:
        """Generate project report."""
        logger.info(f"Generating {self.report_type} report for {self.project_path}")

        metrics = self.collect_metrics()
        health_checks = self.run_health_checks()
        git_log = self._get_git_log()
        git_status = self._get_git_status()
        summary = self.generate_summary(metrics, health_checks)

        return ProjectReport(
            project_path=str(self.project_path),
            report_type=self.report_type,
            timestamp=datetime.now().isoformat(),
            metrics={
                "files": metrics.total_files,
                "lines": metrics.total_lines,
                "languages": metrics.languages,
                "tests": metrics.test_count,
                "dependencies": metrics.dependency_count,
                "git_status": git_status,
            },
            health_checks=[asdict(h) for h in health_checks],
            recent_activity=git_log,
            issues=[h.message for h in health_checks if h.status in ["warning", "critical"]],
            summary=summary,
        )


def format_report_markdown(report: ProjectReport) -> str:
    """Format report as markdown."""
    lines = [
        f"# Project {report.report_type.title()} Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Generated:** {report.timestamp}",
        "",
        "## Executive Summary",
        "",
        report.summary,
        "",
        "## Project Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Files | {report.metrics.get('files', 0)} |",
        f"| Lines of Code | {report.metrics.get('lines', 0):,} |",
        f"| Test Files | {report.metrics.get('tests', 0)} |",
        f"| Dependencies | {report.metrics.get('dependencies', 0)} |",
        "",
        "### Languages",
        "",
    ]

    for lang, count in report.metrics.get("languages", {}).items():
        lines.append(f"- **{lang}**: {count} files")

    lines.extend(["", "## Health Checks", ""])

    for check in report.health_checks:
        emoji = {"healthy": "✅", "warning": "⚠️", "critical": "❌"}.get(
            check.get("status", ""), "❓"
        )
        lines.append(f"- {emoji} **{check.get('name', '')}**: {check.get('message', '')}")

    if report.recent_activity:
        lines.extend(["", "## Recent Activity", ""])
        for commit in report.recent_activity[:5]:
            lines.append(f"- `{commit}`")

    git_status = report.metrics.get("git_status", {})
    if git_status:
        lines.extend(["", "## Git Status", ""])
        lines.append(f"- Modified: {git_status.get('modified', 0)}")
        lines.append(f"- Added: {git_status.get('added', 0)}")
        lines.append(f"- Untracked: {git_status.get('untracked', 0)}")

    if report.issues:
        lines.extend(["", "## Issues to Address", ""])
        for issue in report.issues:
            lines.append(f"- ⚠️ {issue}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Report Generator Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument(
        "--type",
        dest="report_type",
        default="status",
        choices=["status", "health", "summary"],
        help="Report type",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    generator = ReportGenerator(args.project, args.report_type)
    report = generator.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
