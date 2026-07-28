#!/usr/bin/env python3
"""
Antigravity Ecosystem Healthcheck Script.

Comprehensive health verification for the entire agent ecosystem.
Can be run standalone or integrated into CI/CD pipelines.

Exit codes:
    0 = All checks passed (HEALTHY)
    1 = Some checks failed (DEGRADED)
    2 = Critical checks failed (UNHEALTHY)

Usage:
    python healthcheck.py              # Run all checks
    python healthcheck.py --json       # JSON output for pipelines
    python healthcheck.py --verbose    # Detailed output
    python healthcheck.py --fix        # Attempt auto-repair
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Setup paths
SCRIPT_DIR = Path(__file__).parent
AGENT_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = AGENT_DIR.parent

sys.path.insert(0, str(AGENT_DIR))


class CheckStatus(Enum):
    """Status of a health check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class Severity(Enum):
    """Severity level of a check."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: CheckStatus
    message: str
    severity: Severity
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health report."""

    timestamp: str
    overall_status: str
    total_checks: int
    passed: int
    warnings: int
    failed: int
    skipped: int
    checks: list[CheckResult]
    duration_ms: float


class HealthChecker:
    """Comprehensive health checker for Antigravity ecosystem."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[CheckResult] = []

    def log(self, message: str) -> None:
        """Print message if verbose mode."""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def run_check(self, name: str, check_fn, severity: Severity = Severity.MEDIUM) -> CheckResult:
        """Run a single check and record result."""
        start = time.time()
        try:
            status, message, details = check_fn()
            duration = (time.time() - start) * 1000
            result = CheckResult(
                name=name,
                status=status,
                message=message,
                severity=severity,
                duration_ms=round(duration, 2),
                details=details,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = CheckResult(
                name=name,
                status=CheckStatus.FAIL,
                message=f"Check raised exception: {e}",
                severity=severity,
                duration_ms=round(duration, 2),
                details={"exception": str(e)},
            )

        self.results.append(result)
        return result

    # =========================================================================
    # DIRECTORY STRUCTURE CHECKS
    # =========================================================================

    def check_directory_structure(self) -> tuple[CheckStatus, str, dict]:
        """Verify essential directory structure exists."""
        required_dirs = [
            AGENT_DIR / "agents",
            AGENT_DIR / "core",
            AGENT_DIR / "skills",
            AGENT_DIR / "scripts",
            AGENT_DIR / "workflows",
        ]

        missing = []
        for d in required_dirs:
            if not d.exists():
                missing.append(str(d.relative_to(PROJECT_ROOT)))

        if not missing:
            return CheckStatus.PASS, "All required directories exist", {"dirs": len(required_dirs)}
        elif len(missing) < len(required_dirs) / 2:
            return CheckStatus.WARN, f"Missing directories: {missing}", {"missing": missing}
        else:
            return (
                CheckStatus.FAIL,
                f"Critical directories missing: {missing}",
                {"missing": missing},
            )

    # =========================================================================
    # CORE MODULES CHECKS
    # =========================================================================

    def check_core_modules(self) -> tuple[CheckStatus, str, dict]:
        """Verify core Python modules are importable."""
        core_modules = [
            "orchestrator",
            "shared_memory",
            "agent_base",
            "a2a",
            "execution_engine",
        ]

        importable = []
        failed = []

        for module in core_modules:
            try:
                __import__(f"core.{module}")
                importable.append(module)
                self.log(f"Module {module}: OK")
            except ImportError as e:
                failed.append({"module": module, "error": str(e)})
                self.log(f"Module {module}: FAILED - {e}")

        if not failed:
            return (
                CheckStatus.PASS,
                f"All {len(core_modules)} core modules importable",
                {"modules": importable},
            )
        elif len(failed) < len(core_modules) / 2:
            return (
                CheckStatus.WARN,
                f"{len(failed)} modules failed to import",
                {"failed": failed, "ok": importable},
            )
        else:
            return CheckStatus.FAIL, f"Critical: {len(failed)} modules failed", {"failed": failed}

    def check_core_init(self) -> tuple[CheckStatus, str, dict]:
        """Verify core __init__.py exports work."""
        try:
            from core import (
                SharedMemory,
                AntigravityOrchestrator,
                AgentCard,
            )

            exports = []
            if SharedMemory:
                exports.append("SharedMemory")
            if AntigravityOrchestrator:
                exports.append("AntigravityOrchestrator")
            if AgentCard:
                exports.append("AgentCard")

            if len(exports) >= 2:
                return CheckStatus.PASS, f"Core exports working: {exports}", {"exports": exports}
            else:
                return CheckStatus.WARN, f"Limited exports: {exports}", {"exports": exports}
        except ImportError as e:
            return CheckStatus.FAIL, f"Core init failed: {e}", {"error": str(e)}

    # =========================================================================
    # AGENTS CHECKS
    # =========================================================================

    def check_agents_count(self) -> tuple[CheckStatus, str, dict]:
        """Verify minimum number of agents exist."""
        agents_dir = AGENT_DIR / "agents"
        if not agents_dir.exists():
            return CheckStatus.FAIL, "Agents directory missing", {}

        agents = [
            d for d in agents_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))
        ]

        count = len(agents)
        if count >= 50:
            return CheckStatus.PASS, f"{count} agents available", {"count": count}
        elif count >= 20:
            return CheckStatus.WARN, f"Only {count} agents (expected 50+)", {"count": count}
        else:
            return CheckStatus.FAIL, f"Too few agents: {count}", {"count": count}

    def check_agents_identity(self) -> tuple[CheckStatus, str, dict]:
        """Verify agents have identity files."""
        agents_dir = AGENT_DIR / "agents"
        if not agents_dir.exists():
            return CheckStatus.SKIP, "Agents directory missing", {}

        with_identity = 0
        without_identity = []

        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith((".", "_")):
                continue

            has_identity = (agent_dir / "IDENTITY.md").exists() or (
                agent_dir / "SYSTEM_PROMPT.md"
            ).exists()

            if has_identity:
                with_identity += 1
            else:
                without_identity.append(agent_dir.name)

        total = with_identity + len(without_identity)
        if not without_identity:
            return (
                CheckStatus.PASS,
                f"All {total} agents have identity",
                {"with_identity": with_identity},
            )
        elif len(without_identity) < total * 0.1:
            return (
                CheckStatus.WARN,
                f"{len(without_identity)} agents missing identity",
                {"missing": without_identity[:10]},
            )
        else:
            return (
                CheckStatus.FAIL,
                f"{len(without_identity)} agents missing identity",
                {"missing": without_identity[:10]},
            )

    def check_agents_scripts(self) -> tuple[CheckStatus, str, dict]:
        """Verify agents have executable scripts."""
        agents_dir = AGENT_DIR / "agents"
        if not agents_dir.exists():
            return CheckStatus.SKIP, "Agents directory missing", {}

        with_scripts = 0
        without_scripts = []

        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith((".", "_")):
                continue

            scripts_dir = agent_dir / "scripts"
            if scripts_dir.exists() and list(scripts_dir.glob("*.py")):
                with_scripts += 1
            else:
                without_scripts.append(agent_dir.name)

        total = with_scripts + len(without_scripts)
        percentage = (with_scripts / total * 100) if total > 0 else 0

        if percentage >= 90:
            return (
                CheckStatus.PASS,
                f"{with_scripts}/{total} agents have scripts ({percentage:.0f}%)",
                {"with_scripts": with_scripts},
            )
        elif percentage >= 70:
            return (
                CheckStatus.WARN,
                f"{with_scripts}/{total} agents have scripts ({percentage:.0f}%)",
                {"without": without_scripts[:5]},
            )
        else:
            return (
                CheckStatus.FAIL,
                f"Only {percentage:.0f}% agents have scripts",
                {"without": without_scripts[:10]},
            )

    # =========================================================================
    # SKILLS CHECKS
    # =========================================================================

    def check_skills_count(self) -> tuple[CheckStatus, str, dict]:
        """Verify minimum number of skills exist."""
        skills_dir = AGENT_DIR / "skills"
        if not skills_dir.exists():
            return CheckStatus.WARN, "Skills directory missing", {}

        skills = [
            d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))
        ]

        count = len(skills)
        if count >= 100:
            return CheckStatus.PASS, f"{count} skills available", {"count": count}
        elif count >= 50:
            return CheckStatus.WARN, f"Only {count} skills (expected 100+)", {"count": count}
        else:
            return CheckStatus.FAIL, f"Too few skills: {count}", {"count": count}

    # =========================================================================
    # DEPENDENCIES CHECKS
    # =========================================================================

    def check_required_deps(self) -> tuple[CheckStatus, str, dict]:
        """Verify required dependencies are installed."""
        required = ["pydantic", "httpx", "aiohttp", "rich"]
        installed = []
        missing = []

        for dep in required:
            try:
                __import__(dep)
                installed.append(dep)
            except ImportError:
                missing.append(dep)

        if not missing:
            return (
                CheckStatus.PASS,
                f"All {len(required)} required deps installed",
                {"installed": installed},
            )
        else:
            return (
                CheckStatus.FAIL,
                f"Missing required deps: {missing}",
                {"missing": missing, "installed": installed},
            )

    def check_optional_deps(self) -> tuple[CheckStatus, str, dict]:
        """Check optional dependencies status."""
        optional = {
            "chromadb": "vector memory",
            "opentelemetry": "observability",
            "anthropic": "Claude API",
            "openai": "OpenAI API",
        }

        installed = []
        missing = []

        for dep, purpose in optional.items():
            try:
                __import__(dep.replace("-", "_"))
                installed.append(f"{dep} ({purpose})")
            except ImportError:
                missing.append(f"{dep} ({purpose})")

        if len(installed) >= len(optional) / 2:
            return (
                CheckStatus.PASS,
                f"{len(installed)} optional deps available",
                {"installed": installed, "missing": missing},
            )
        else:
            return (
                CheckStatus.WARN,
                f"Limited optional deps: {installed}",
                {"installed": installed, "missing": missing},
            )

    # =========================================================================
    # CONFIGURATION CHECKS
    # =========================================================================

    def check_pyproject(self) -> tuple[CheckStatus, str, dict]:
        """Verify pyproject.toml exists and is valid."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        if not pyproject.exists():
            return CheckStatus.FAIL, "pyproject.toml missing", {}

        try:
            content = pyproject.read_text(encoding="utf-8")
            if "[project]" in content and "name" in content:
                return CheckStatus.PASS, "pyproject.toml valid", {"size": len(content)}
            else:
                return CheckStatus.WARN, "pyproject.toml may be incomplete", {}
        except Exception as e:
            return CheckStatus.FAIL, f"Cannot read pyproject.toml: {e}", {}

    def check_env_file(self) -> tuple[CheckStatus, str, dict]:
        """Check for environment configuration."""
        env_file = PROJECT_ROOT / ".env"
        env_example = PROJECT_ROOT / ".env.example"

        if env_file.exists():
            return CheckStatus.PASS, ".env file exists", {}
        elif env_example.exists():
            return CheckStatus.WARN, ".env missing but .env.example exists", {}
        else:
            return CheckStatus.WARN, "No .env configuration found", {}

    # =========================================================================
    # WORKFLOWS CHECKS
    # =========================================================================

    def check_workflows(self) -> tuple[CheckStatus, str, dict]:
        """Verify workflows exist."""
        workflows_dir = AGENT_DIR / "workflows"
        if not workflows_dir.exists():
            return CheckStatus.WARN, "Workflows directory missing", {}

        workflows = list(workflows_dir.glob("*.md"))
        count = len(workflows)

        if count >= 10:
            return CheckStatus.PASS, f"{count} workflows available", {"count": count}
        elif count >= 5:
            return CheckStatus.WARN, f"Only {count} workflows", {"count": count}
        else:
            return CheckStatus.WARN, f"Few workflows: {count}", {"count": count}

    # =========================================================================
    # MCP CHECKS
    # =========================================================================

    def check_mcp_servers(self) -> tuple[CheckStatus, str, dict]:
        """Verify MCP servers exist."""
        mcp_dir = AGENT_DIR / "mcp"
        if not mcp_dir.exists():
            return CheckStatus.WARN, "MCP directory missing", {}

        servers = list(mcp_dir.glob("*-server*.py"))
        count = len(servers)

        if count >= 2:
            return (
                CheckStatus.PASS,
                f"{count} MCP servers available",
                {"servers": [s.name for s in servers]},
            )
        elif count >= 1:
            return (
                CheckStatus.WARN,
                f"Only {count} MCP server",
                {"servers": [s.name for s in servers]},
            )
        else:
            return CheckStatus.WARN, "No MCP servers found", {}

    # =========================================================================
    # TEST INFRASTRUCTURE CHECKS
    # =========================================================================

    def check_gitignore_guard(self) -> tuple[CheckStatus, str, dict]:
        """Verify .gitignore no esta bloqueando paths criticos del ecosistema.

        Si git esta accesible, corre `git check-ignore` sobre paths como
        `.agent/brain/index.md` y `.claude/memory/MEMORY.md`. Si alguno esta
        bloqueado, la sincronizacion del Brain entre PCs se rompe silenciosamente.
        """
        try:
            sys.path.insert(0, str(PROJECT_ROOT / ".agent"))
            from core.gitignore_guard import check_gitignore_health
        except ImportError as exc:
            return CheckStatus.SKIP, f"gitignore_guard no importable: {exc}", {}

        report = check_gitignore_health(PROJECT_ROOT)
        if not report.git_available:
            return CheckStatus.SKIP, "git no accesible en PATH", {}
        if not report.checked_paths:
            return CheckStatus.SKIP, "target no es git repo", {}
        if report.blocked_paths:
            return (
                CheckStatus.FAIL,
                f"{len(report.blocked_paths)} paths bloqueados: "
                f"{', '.join(report.blocked_paths[:3])}"
                + (
                    f" (+{len(report.blocked_paths) - 3} mas)"
                    if len(report.blocked_paths) > 3
                    else ""
                ),
                {"blocked": report.blocked_paths, "checked": report.checked_paths},
            )
        return (
            CheckStatus.PASS,
            f"{len(report.checked_paths)} paths criticos sin bloqueos",
            {"checked": report.checked_paths},
        )

    def check_tests_exist(self) -> tuple[CheckStatus, str, dict]:
        """Verify test infrastructure exists."""
        tests_dir = PROJECT_ROOT / "tests"
        if not tests_dir.exists():
            return CheckStatus.WARN, "Tests directory missing", {}

        test_files = list(tests_dir.glob("test_*.py"))
        conftest = tests_dir / "conftest.py"

        if len(test_files) >= 10 and conftest.exists():
            return (
                CheckStatus.PASS,
                f"{len(test_files)} test files with conftest",
                {"count": len(test_files)},
            )
        elif len(test_files) >= 5:
            return (
                CheckStatus.WARN,
                f"Only {len(test_files)} test files",
                {"count": len(test_files)},
            )
        else:
            return CheckStatus.WARN, f"Few tests: {len(test_files)}", {"count": len(test_files)}

    # =========================================================================
    # RUN ALL CHECKS
    # =========================================================================

    def run_all_checks(self) -> HealthReport:
        """Run all health checks and generate report."""
        start = time.time()
        self.results = []

        # Critical checks
        self.run_check("Directory Structure", self.check_directory_structure, Severity.CRITICAL)
        self.run_check("Core Modules", self.check_core_modules, Severity.CRITICAL)
        self.run_check("Core Exports", self.check_core_init, Severity.CRITICAL)
        self.run_check("Required Dependencies", self.check_required_deps, Severity.CRITICAL)

        # High priority checks
        self.run_check("Agents Count", self.check_agents_count, Severity.HIGH)
        self.run_check("Agents Identity", self.check_agents_identity, Severity.HIGH)
        self.run_check("Agents Scripts", self.check_agents_scripts, Severity.HIGH)
        self.run_check("pyproject.toml", self.check_pyproject, Severity.HIGH)

        # Medium priority checks
        self.run_check("Skills Count", self.check_skills_count, Severity.MEDIUM)
        self.run_check("Workflows", self.check_workflows, Severity.MEDIUM)
        self.run_check("MCP Servers", self.check_mcp_servers, Severity.MEDIUM)
        self.run_check("Test Infrastructure", self.check_tests_exist, Severity.MEDIUM)
        self.run_check("Gitignore Guard", self.check_gitignore_guard, Severity.HIGH)

        # Low priority checks
        self.run_check("Optional Dependencies", self.check_optional_deps, Severity.LOW)
        self.run_check("Environment Config", self.check_env_file, Severity.LOW)

        duration = (time.time() - start) * 1000

        # Calculate stats
        passed = sum(1 for r in self.results if r.status == CheckStatus.PASS)
        warnings = sum(1 for r in self.results if r.status == CheckStatus.WARN)
        failed = sum(1 for r in self.results if r.status == CheckStatus.FAIL)
        skipped = sum(1 for r in self.results if r.status == CheckStatus.SKIP)

        # Determine overall status
        critical_failed = any(
            r.status == CheckStatus.FAIL and r.severity == Severity.CRITICAL for r in self.results
        )

        if critical_failed:
            overall = "UNHEALTHY"
        elif failed > 0 or warnings > 2:
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"

        return HealthReport(
            timestamp=datetime.now().isoformat(),
            overall_status=overall,
            total_checks=len(self.results),
            passed=passed,
            warnings=warnings,
            failed=failed,
            skipped=skipped,
            checks=self.results,
            duration_ms=round(duration, 2),
        )


def print_report(report: HealthReport, verbose: bool = False) -> None:
    """Print health report to console."""
    # Status symbols
    symbols = {
        CheckStatus.PASS: "✓",
        CheckStatus.WARN: "⚠",
        CheckStatus.FAIL: "✗",
        CheckStatus.SKIP: "○",
    }

    colors = {
        CheckStatus.PASS: "\033[92m",  # Green
        CheckStatus.WARN: "\033[93m",  # Yellow
        CheckStatus.FAIL: "\033[91m",  # Red
        CheckStatus.SKIP: "\033[90m",  # Gray
    }
    reset = "\033[0m"

    print("\n" + "=" * 60)
    print("       ANTIGRAVITY ECOSYSTEM HEALTH CHECK")
    print("=" * 60)
    print(f"  Timestamp: {report.timestamp}")
    print(f"  Duration:  {report.duration_ms}ms")
    print("-" * 60)

    # Print each check
    for check in report.checks:
        symbol = symbols[check.status]
        color = colors[check.status]
        severity_tag = f"[{check.severity.value.upper()}]" if verbose else ""

        print(f"  {color}{symbol}{reset} {check.name} {severity_tag}")
        print(f"    {check.message}")

        if verbose and check.details:
            for key, value in check.details.items():
                if isinstance(value, list) and len(value) > 5:
                    value = value[:5] + ["..."]
                print(f"      {key}: {value}")

    # Summary
    print("-" * 60)
    print(f"  Total: {report.total_checks} checks")
    print(f"  {colors[CheckStatus.PASS]}Passed:   {report.passed}{reset}")
    print(f"  {colors[CheckStatus.WARN]}Warnings: {report.warnings}{reset}")
    print(f"  {colors[CheckStatus.FAIL]}Failed:   {report.failed}{reset}")
    print(f"  {colors[CheckStatus.SKIP]}Skipped:  {report.skipped}{reset}")
    print("-" * 60)

    # Overall status
    status_color = {
        "HEALTHY": "\033[92m",
        "DEGRADED": "\033[93m",
        "UNHEALTHY": "\033[91m",
    }

    print(f"  Status: {status_color.get(report.overall_status, '')}{report.overall_status}{reset}")
    print("=" * 60 + "\n")


def report_to_json(report: HealthReport) -> str:
    """Convert report to JSON string."""
    return json.dumps(
        {
            "timestamp": report.timestamp,
            "overall_status": report.overall_status,
            "summary": {
                "total": report.total_checks,
                "passed": report.passed,
                "warnings": report.warnings,
                "failed": report.failed,
                "skipped": report.skipped,
            },
            "duration_ms": report.duration_ms,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "severity": c.severity.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                    "details": c.details,
                }
                for c in report.checks
            ],
        },
        indent=2,
    )


def main():
    """Main entry point."""
    # Forzar UTF-8 en stdout para evitar UnicodeEncodeError en Windows japones
    # (cp932 default no codifica unicode chars como check marks unicode).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Antigravity Ecosystem Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 = HEALTHY (all checks pass)
  1 = DEGRADED (some warnings or non-critical failures)
  2 = UNHEALTHY (critical checks failed)
        """,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    checker = HealthChecker(verbose=args.verbose)
    report = checker.run_all_checks()

    if args.json:
        print(report_to_json(report))
    else:
        print_report(report, verbose=args.verbose)

    # Return appropriate exit code
    if report.overall_status == "HEALTHY":
        return 0
    elif report.overall_status == "DEGRADED":
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
