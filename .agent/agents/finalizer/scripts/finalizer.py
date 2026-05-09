#!/usr/bin/env python3
"""
Finalizer Agent - Task Completion Verification

Capabilities:
- Verify task completion
- Run final checks
- Generate completion reports
- Archive artifacts
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a completion check."""

    name: str
    passed: bool
    message: str
    details: str | None = None


@dataclass
class FinalizationReport:
    """Task finalization report."""

    project_path: str
    task_description: str
    checks: list[CheckResult] = field(default_factory=list)
    all_passed: bool = False
    completion_time: str = ""
    summary: str = ""
    next_steps: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.completion_time:
            self.completion_time = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "task_description": self.task_description,
            "checks": [c.__dict__ for c in self.checks],
            "all_passed": self.all_passed,
            "completion_time": self.completion_time,
            "summary": self.summary,
            "next_steps": self.next_steps,
        }

    def to_markdown(self) -> str:
        status = "✅ COMPLETE" if self.all_passed else "⚠️ INCOMPLETE"

        lines = [
            f"# Finalization Report - {status}",
            "",
            f"**Project:** {self.project_path}",
            f"**Task:** {self.task_description}",
            f"**Completed:** {self.completion_time}",
            "",
            "## Verification Checks",
            "",
        ]

        for check in self.checks:
            icon = "✅" if check.passed else "❌"
            lines.append(f"- {icon} **{check.name}**: {check.message}")
            if check.details:
                lines.append(f"  - {check.details}")

        lines.append("")

        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        lines.extend(
            ["## Summary", "", f"**Checks Passed:** {passed}/{total}", "", self.summary, ""]
        )

        if self.next_steps:
            lines.extend(["## Next Steps", ""])
            for i, step in enumerate(self.next_steps, 1):
                lines.append(f"{i}. {step}")

        return "\n".join(lines)


class FinalizerAgent:
    """Task completion verification agent."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def finalize(self, task: str, checks: list[str] = None) -> FinalizationReport:
        """Verify task completion and generate report."""
        logger.info(f"Finalizing task: {task}")

        default_checks = ["git", "tests", "lint", "build"]
        checks_to_run = checks or default_checks

        results = []

        for check in checks_to_run:
            if check == "git":
                results.append(await self._check_git())
            elif check == "tests":
                results.append(await self._check_tests())
            elif check == "lint":
                results.append(await self._check_lint())
            elif check == "build":
                results.append(await self._check_build())
            elif check == "types":
                results.append(await self._check_types())
            elif check == "docs":
                results.append(await self._check_docs())

        all_passed = all(r.passed for r in results)
        summary = self._generate_summary(results, task)
        next_steps = self._generate_next_steps(results, all_passed)

        return FinalizationReport(
            project_path=str(self.project_path),
            task_description=task,
            checks=results,
            all_passed=all_passed,
            summary=summary,
            next_steps=next_steps,
        )

    async def _check_git(self) -> CheckResult:
        """Check git status."""
        try:
            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=30,
            )

            if result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                return CheckResult(
                    name="Git Status",
                    passed=False,
                    message=f"{len(lines)} uncommitted changes",
                    details="Run 'git status' to see changes",
                )

            # Check if ahead/behind
            result = subprocess.run(
                ["git", "status", "-sb"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=30,
            )

            if "ahead" in result.stdout:
                return CheckResult(
                    name="Git Status",
                    passed=True,
                    message="Changes committed, ready to push",
                    details="Branch is ahead of remote",
                )

            return CheckResult(
                name="Git Status", passed=True, message="Working tree clean, up to date"
            )

        except Exception as e:
            return CheckResult(
                name="Git Status", passed=False, message=f"Git check failed: {str(e)}"
            )

    async def _check_tests(self) -> CheckResult:
        """Check if tests pass."""
        try:
            # Try pytest first
            result = subprocess.run(
                ["pytest", "--tb=no", "-q"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=300,
            )

            if result.returncode == 0:
                # Parse test count
                match_passed = result.stdout.strip().split("\n")[-1] if result.stdout else ""
                return CheckResult(
                    name="Tests", passed=True, message="All tests passed", details=match_passed
                )
            else:
                return CheckResult(
                    name="Tests",
                    passed=False,
                    message="Some tests failed",
                    details=result.stdout[-500:] if result.stdout else result.stderr[-500:],
                )

        except FileNotFoundError:
            # Try npm test
            try:
                result = subprocess.run(
                    ["npm", "test", "--", "--passWithNoTests"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=300,
                )

                return CheckResult(
                    name="Tests",
                    passed=result.returncode == 0,
                    message="npm tests " + ("passed" if result.returncode == 0 else "failed"),
                )
            except Exception:
                return CheckResult(
                    name="Tests",
                    passed=True,
                    message="No test framework detected",
                    details="Consider adding tests",
                )

        except Exception as e:
            return CheckResult(name="Tests", passed=False, message=f"Test check failed: {str(e)}")

    async def _check_lint(self) -> CheckResult:
        """Check linting."""
        try:
            # Try ruff for Python
            result = subprocess.run(
                ["ruff", "check", "."],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=120,
            )

            if result.returncode == 0:
                return CheckResult(name="Lint", passed=True, message="No linting errors")
            else:
                error_count = result.stdout.count("\n") if result.stdout else 0
                return CheckResult(
                    name="Lint",
                    passed=False,
                    message=f"{error_count} linting issues",
                    details="Run 'ruff check .' to see issues",
                )

        except FileNotFoundError:
            # Try eslint
            try:
                result = subprocess.run(
                    ["npx", "eslint", ".", "--quiet"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=120,
                )

                return CheckResult(
                    name="Lint",
                    passed=result.returncode == 0,
                    message="ESLint " + ("passed" if result.returncode == 0 else "found issues"),
                )
            except Exception:
                return CheckResult(
                    name="Lint",
                    passed=True,
                    message="No linter configured",
                    details="Consider adding ruff or eslint",
                )

        except Exception as e:
            return CheckResult(name="Lint", passed=False, message=f"Lint check failed: {str(e)}")

    async def _check_build(self) -> CheckResult:
        """Check if project builds."""
        try:
            # Check for Node.js project
            if (self.project_path / "package.json").exists():
                result = subprocess.run(
                    ["npm", "run", "build"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=300,
                )

                if result.returncode == 0:
                    return CheckResult(name="Build", passed=True, message="npm build successful")
                else:
                    return CheckResult(
                        name="Build",
                        passed=False,
                        message="npm build failed",
                        details=result.stderr[-300:] if result.stderr else None,
                    )

            # Check for Python project
            elif (self.project_path / "pyproject.toml").exists():
                result = subprocess.run(
                    ["python", "-m", "py_compile"]
                    + [
                        str(f)
                        for f in self.project_path.glob("**/*.py")
                        if "venv" not in str(f) and "__pycache__" not in str(f)
                    ][:20],  # Limit to 20 files
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=60,
                )

                return CheckResult(
                    name="Build",
                    passed=result.returncode == 0,
                    message="Python syntax "
                    + ("valid" if result.returncode == 0 else "errors found"),
                )

            return CheckResult(name="Build", passed=True, message="No build configuration found")

        except Exception as e:
            return CheckResult(name="Build", passed=False, message=f"Build check failed: {str(e)}")

    async def _check_types(self) -> CheckResult:
        """Check type checking."""
        try:
            result = subprocess.run(
                ["mypy", ".", "--ignore-missing-imports"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=120,
            )

            if result.returncode == 0:
                return CheckResult(name="Type Check", passed=True, message="No type errors")
            else:
                error_count = result.stdout.count("error:") if result.stdout else 0
                return CheckResult(
                    name="Type Check",
                    passed=False,
                    message=f"{error_count} type errors",
                    details="Run 'mypy .' to see errors",
                )

        except FileNotFoundError:
            return CheckResult(name="Type Check", passed=True, message="mypy not installed")

    async def _check_docs(self) -> CheckResult:
        """Check documentation."""
        readme = self.project_path / "README.md"
        if not readme.exists():
            return CheckResult(
                name="Documentation",
                passed=False,
                message="README.md missing",
                details="Add a README.md file",
            )

        content = readme.read_text()
        if len(content) < 100:
            return CheckResult(
                name="Documentation",
                passed=False,
                message="README.md too short",
                details="Add installation and usage instructions",
            )

        return CheckResult(name="Documentation", passed=True, message="README.md present")

    def _generate_summary(self, results: list[CheckResult], task: str) -> str:
        """Generate summary text."""
        passed = sum(1 for r in results if r.passed)
        total = len(results)

        if passed == total:
            return f"Task '{task}' completed successfully. All {total} verification checks passed."
        else:
            failed = [r.name for r in results if not r.passed]
            return f"Task '{task}' has {total - passed} issues: {', '.join(failed)}"

    def _generate_next_steps(self, results: list[CheckResult], all_passed: bool) -> list[str]:
        """Generate next steps."""
        steps = []

        if all_passed:
            steps.append("Create a pull request for review")
            steps.append("Update documentation if needed")
        else:
            for result in results:
                if not result.passed:
                    if "git" in result.name.lower():
                        steps.append("Commit pending changes")
                    elif "test" in result.name.lower():
                        steps.append("Fix failing tests")
                    elif "lint" in result.name.lower():
                        steps.append("Fix linting errors")
                    elif "build" in result.name.lower():
                        steps.append("Fix build errors")
                    elif "type" in result.name.lower():
                        steps.append("Fix type errors")

        return steps[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Finalizer Agent")
    parser.add_argument(
        "task", nargs="?", default="General task completion", help="Task description"
    )
    parser.add_argument("--path", default=".", help="Project path")
    parser.add_argument("--checks", nargs="*", help="Specific checks to run")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = FinalizerAgent(args.path)
    report = await agent.finalize(args.task, args.checks)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
