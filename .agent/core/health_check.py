#!/usr/bin/env python3
"""
Health Check - Verificación completa del ecosistema

Ejecutar: python .agent/core/health_check.py
          python .agent/core/health_check.py --json
          python .agent/core/health_check.py --fix
"""

import json
import logging
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

try:
    from . import security_utils as _security_utils
except ImportError:
    import security_utils as _security_utils  # type: ignore[no-redef]

validate_url_for_ssrf = _security_utils.validate_url_for_ssrf

logger = logging.getLogger(__name__)


def _configure_console_encoding() -> None:
    """Prefer UTF-8 output when the Windows console defaults to cp932/cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


class Status(Enum):
    """Estado de un componente."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    """Resultado de una verificación."""

    name: str
    status: Status
    message: str
    details: dict = field(default_factory=dict)
    duration_ms: int = 0
    fix_available: bool = False
    fix_command: str | None = None


@dataclass
class HealthReport:
    """Reporte completo de salud."""

    timestamp: str
    overall_status: Status
    score: float
    checks: list[CheckResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "score": self.score,
            "summary": self.summary,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                    "duration_ms": c.duration_ms,
                    "fix_available": c.fix_available,
                    "fix_command": c.fix_command,
                }
                for c in self.checks
            ],
        }

    def to_markdown(self) -> str:
        status_emoji = {
            Status.HEALTHY: "🟢",
            Status.DEGRADED: "🟡",
            Status.UNHEALTHY: "🔴",
            Status.UNKNOWN: "⚪",
        }

        lines = [
            "# 🏥 Antigravity Ecosystem Health Report",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Overall Status:** {status_emoji[self.overall_status]} {self.overall_status.value.upper()}",
            f"**Health Score:** {self.score:.0f}%",
            "",
            "## Summary",
            "",
            f"- Total checks: {self.summary.get('total', 0)}",
            f"- Healthy: {self.summary.get('healthy', 0)}",
            f"- Degraded: {self.summary.get('degraded', 0)}",
            f"- Unhealthy: {self.summary.get('unhealthy', 0)}",
            "",
            "## Checks",
            "",
        ]

        for check in self.checks:
            emoji = status_emoji[check.status]
            lines.append(f"### {emoji} {check.name}")
            lines.append(f"**Status:** {check.status.value}")
            lines.append(f"**Message:** {check.message}")
            if check.duration_ms:
                lines.append(f"**Duration:** {check.duration_ms}ms")
            if check.fix_available:
                lines.append(f"**Fix:** `{check.fix_command}`")
            lines.append("")

        return "\n".join(lines)


class HealthChecker:
    """Verificador de salud del ecosistema."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.checks: list[CheckResult] = []

    def run_all_checks(self) -> HealthReport:
        """Ejecuta todas las verificaciones."""
        self.checks = []

        # Verificaciones
        self._check_python()
        self._check_dependencies()
        self._check_core_modules()
        self._check_critical_agents()
        self._check_memory_system()
        self._check_directory_structure()
        self._check_git_status()
        self._check_config_files()
        self._check_network_connectivity()
        self._check_mcp_servers()

        # Calcular resumen
        summary = {
            "total": len(self.checks),
            "healthy": sum(1 for c in self.checks if c.status == Status.HEALTHY),
            "degraded": sum(1 for c in self.checks if c.status == Status.DEGRADED),
            "unhealthy": sum(1 for c in self.checks if c.status == Status.UNHEALTHY),
            "unknown": sum(1 for c in self.checks if c.status == Status.UNKNOWN),
        }

        # Calcular score
        weights = {
            Status.HEALTHY: 1.0,
            Status.DEGRADED: 0.5,
            Status.UNHEALTHY: 0,
            Status.UNKNOWN: 0.25,
        }
        total_weight = sum(weights[c.status] for c in self.checks)
        score = (total_weight / len(self.checks)) * 100 if self.checks else 0.0

        # Estado general
        if score >= 80:
            overall = Status.HEALTHY
        elif score >= 50:
            overall = Status.DEGRADED
        else:
            overall = Status.UNHEALTHY

        return HealthReport(
            timestamp=datetime.now().isoformat(),
            overall_status=overall,
            score=score,
            checks=self.checks,
            summary=summary,
        )

    def _add_check(self, result: CheckResult):
        """Agrega resultado de verificación."""
        self.checks.append(result)

    def _run_command(self, cmd: list, timeout: int = 30) -> tuple[int, str, str]:
        """Ejecuta comando."""
        try:
            run_cmd = cmd
            if os.name == "nt":
                run_cmd = ["cmd", "/c", *cmd]

            result = subprocess.run(
                run_cmd, capture_output=True, text=True, timeout=timeout, cwd=self.project_root
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timeout"
        except Exception as e:
            return -1, "", str(e)

    def _check_python(self):
        """Verifica versión de Python."""
        start = time.time()
        version = sys.version_info

        if version.major >= 3 and version.minor >= 11:
            status = Status.HEALTHY
            message = f"Python {version.major}.{version.minor}.{version.micro}"
        elif version.major >= 3 and version.minor >= 9:
            status = Status.DEGRADED
            message = f"Python {version.major}.{version.minor} (3.11+ recomendado)"
        else:
            status = Status.UNHEALTHY
            message = f"Python {version.major}.{version.minor} (3.11+ requerido)"

        self._add_check(
            CheckResult(
                name="Python Version",
                status=status,
                message=message,
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def _check_dependencies(self):
        """Verifica dependencias instaladas."""
        start = time.time()

        deps = {
            "pydantic": "Core validation",
            "httpx": "HTTP client",
            "rich": "Terminal UI",
            "typer": "CLI framework",
        }

        installed = []
        missing = []

        for dep, _desc in deps.items():
            try:
                __import__(dep)
                installed.append(dep)
            except ImportError:
                missing.append(dep)

        if not missing:
            status = Status.HEALTHY
            message = f"All {len(deps)} core dependencies installed"
        elif len(missing) <= 1:
            status = Status.DEGRADED
            message = f"Missing: {', '.join(missing)}"
        else:
            status = Status.UNHEALTHY
            message = f"Missing {len(missing)} dependencies"

        self._add_check(
            CheckResult(
                name="Core Dependencies",
                status=status,
                message=message,
                details={"installed": installed, "missing": missing},
                duration_ms=int((time.time() - start) * 1000),
                fix_available=bool(missing),
                fix_command="python setup_ecosystem.py --minimal" if missing else None,
            )
        )

    def _check_core_modules(self):
        """Verifica módulos core."""
        start = time.time()

        modules = [
            "session_bootstrap.py",
            "claude_core.py",
            "auto_verification_pipeline.py",
            "learning_loop.py",
            "quick_actions.py",
        ]

        existing = []
        missing = []
        working = []

        for mod in modules:
            path = self.project_root / ".agent" / "core" / mod
            if path.exists():
                existing.append(mod)
                # Verificar que se puede compilar (sin ejecutar código arbitrario)
                code, _, _ = self._run_command(
                    [sys.executable, "-m", "py_compile", str(path)], timeout=10
                )
                if code == 0:
                    working.append(mod)
            else:
                missing.append(mod)

        if len(working) == len(modules):
            status = Status.HEALTHY
            message = f"All {len(modules)} core modules working"
        elif len(working) >= len(modules) * 0.7:
            status = Status.DEGRADED
            message = f"{len(working)}/{len(modules)} modules working"
        else:
            status = Status.UNHEALTHY
            message = f"Only {len(working)}/{len(modules)} modules working"

        self._add_check(
            CheckResult(
                name="Core Modules",
                status=status,
                message=message,
                details={"working": working, "missing": missing},
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def _check_critical_agents(self):
        """Verifica agentes críticos."""
        start = time.time()

        agents = {
            "explorer": ".agent/agents/explorer/scripts/explorer.py",
            "memory": ".agent/agents/memory/scripts/memory_agent.py",
            "planner": ".agent/agents/planner/scripts/planner.py",
            "security-auditor": ".agent/agents/security-auditor/scripts/security_scanner.py",
        }

        working = []
        broken = []

        for name, path in agents.items():
            full_path = self.project_root / path
            if full_path.exists():
                code, _, _ = self._run_command(
                    [sys.executable, str(full_path), "--help"], timeout=10
                )
                if code == 0:
                    working.append(name)
                else:
                    broken.append(name)
            else:
                broken.append(name)

        if len(working) == len(agents):
            status = Status.HEALTHY
            message = f"All {len(agents)} critical agents operational"
        elif len(working) >= 2:
            status = Status.DEGRADED
            message = f"{len(working)}/{len(agents)} agents operational"
        else:
            status = Status.UNHEALTHY
            message = f"Only {len(working)}/{len(agents)} agents operational"

        self._add_check(
            CheckResult(
                name="Critical Agents",
                status=status,
                message=message,
                details={"working": working, "broken": broken},
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def _check_memory_system(self):
        """Verifica sistema de memoria."""
        start = time.time()

        memory_dir = self.project_root / ".agent" / "memory"
        memories_file = memory_dir / "memories.json"

        if not memory_dir.exists():
            status = Status.DEGRADED
            message = "Memory directory missing"
            fix = "mkdir -p .agent/memory"
        elif not memories_file.exists():
            status = Status.HEALTHY
            message = "Memory system ready (no memories yet)"
            fix = None
        else:
            try:
                data = json.loads(memories_file.read_text(encoding="utf-8"))
                entries = len(data.get("entries", []))
                status = Status.HEALTHY
                message = f"Memory system active ({entries} entries)"
                fix = None
            except Exception as e:
                status = Status.DEGRADED
                message = f"Memory file corrupted: {e}"
                fix = "rm .agent/memory/memories.json"

        self._add_check(
            CheckResult(
                name="Memory System",
                status=status,
                message=message,
                duration_ms=int((time.time() - start) * 1000),
                fix_available=fix is not None,
                fix_command=fix,
            )
        )

    def _check_directory_structure(self):
        """Verifica estructura de directorios."""
        start = time.time()

        required_dirs = [
            ".agent/core",
            ".agent/agents",
            ".agent/skills",
        ]

        optional_dirs = [
            ".agent/memory",
            ".agent/logs",
            ".agent/cache",
        ]

        missing_required = []
        missing_optional = []

        for d in required_dirs:
            if not (self.project_root / d).exists():
                missing_required.append(d)

        for d in optional_dirs:
            if not (self.project_root / d).exists():
                missing_optional.append(d)

        if not missing_required:
            if not missing_optional:
                status = Status.HEALTHY
                message = "All directories present"
            else:
                status = Status.HEALTHY
                message = f"Structure OK (optional missing: {len(missing_optional)})"
        else:
            status = Status.UNHEALTHY
            message = f"Missing required: {', '.join(missing_required)}"

        self._add_check(
            CheckResult(
                name="Directory Structure",
                status=status,
                message=message,
                details={
                    "missing_required": missing_required,
                    "missing_optional": missing_optional,
                },
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def _check_git_status(self):
        """Verifica estado de git."""
        start = time.time()

        code, out, err = self._run_command(["git", "status", "--porcelain"])

        if code != 0:
            status = Status.UNKNOWN
            err_lower = err.lower()
            if "not recognized" in err_lower or "not found" in err_lower:
                message = "Git command unavailable in PATH"
            elif "not a git repository" in err_lower:
                message = "Not a git repository"
            else:
                message = "Git status unavailable"
        else:
            changes = len([l for l in out.strip().split("\n") if l])
            if changes == 0:
                status = Status.HEALTHY
                message = "Working tree clean"
            elif changes < 10:
                status = Status.HEALTHY
                message = f"{changes} uncommitted changes"
            else:
                status = Status.DEGRADED
                message = f"{changes} uncommitted changes (consider committing)"

        self._add_check(
            CheckResult(
                name="Git Status",
                status=status,
                message=message,
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def _check_config_files(self):
        """Verifica archivos de configuración."""
        start = time.time()

        configs = {
            "CLAUDE.md": True,  # Required
            ".env": False,  # Optional
            "pyproject.toml": True,
        }

        missing_required = []
        missing_optional = []

        for config, required in configs.items():
            if not (self.project_root / config).exists():
                if required:
                    missing_required.append(config)
                else:
                    missing_optional.append(config)

        if not missing_required:
            status = Status.HEALTHY
            message = "All config files present"
        else:
            status = Status.DEGRADED
            message = f"Missing: {', '.join(missing_required)}"

        self._add_check(
            CheckResult(
                name="Config Files",
                status=status,
                message=message,
                details={
                    "missing_required": missing_required,
                    "missing_optional": missing_optional,
                },
                duration_ms=int((time.time() - start) * 1000),
                fix_available=".env" in missing_optional,
                fix_command="cp .env.example .env" if ".env" in missing_optional else None,
            )
        )

    def _check_network_connectivity(self):
        """Verifica conectividad de red a servicios clave."""
        start = time.time()
        import urllib.request

        endpoints = {
            "PyPI": "https://pypi.org/simple/",
            "GitHub": "https://api.github.com",
        }

        # APIs opcionales basadas en env vars
        if os.environ.get("ANTHROPIC_API_KEY"):
            endpoints["Anthropic API"] = "https://api.anthropic.com"
        if os.environ.get("OPENAI_API_KEY"):
            endpoints["OpenAI API"] = "https://api.openai.com/v1/models"

        reachable = []
        unreachable = []

        for name, url in endpoints.items():
            try:
                # SSRF: validar URL antes de hacer request
                valid, reason = validate_url_for_ssrf(url)
                if not valid:
                    unreachable.append(f"{name} (SSRF bloqueado: {reason})")
                    continue
                req = urllib.request.Request(url, method="HEAD")
                urllib.request.urlopen(req, timeout=5)
                reachable.append(name)
            except Exception:
                unreachable.append(name)

        if not unreachable:
            status = Status.HEALTHY
            message = f"All {len(reachable)} endpoints reachable"
        elif len(unreachable) < len(endpoints):
            status = Status.DEGRADED
            message = f"Unreachable: {', '.join(unreachable)}"
        else:
            status = Status.UNHEALTHY
            message = "No network connectivity"

        self._add_check(
            CheckResult(
                name="Network Connectivity",
                status=status,
                message=message,
                details={
                    "reachable": reachable,
                    "unreachable": unreachable,
                },
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def _check_mcp_servers(self):
        """Verifica que los MCP servers locales responden."""
        start = time.time()
        import urllib.request

        servers = {
            "Gateway (4747)": "http://127.0.0.1:4747/health",
        }

        responsive = []
        unresponsive = []

        for name, url in servers.items():
            try:
                # SSRF: validar URL (localhost se rechaza porque es loopback,
                # pero en este caso es un health check local legitimo)
                valid, reason = validate_url_for_ssrf(url)
                if not valid:
                    # Health check local - continuar aunque loopback sea bloqueado
                    logger.debug("SSRF check for local health endpoint: %s", reason)
                    continue
                urllib.request.urlopen(url, timeout=3)
                responsive.append(name)
            except Exception:
                unresponsive.append(name)

        if responsive:
            status = Status.HEALTHY
            message = f"{len(responsive)} MCP servers running"
        elif not servers:
            status = Status.UNKNOWN
            message = "No MCP servers configured"
        else:
            status = Status.DEGRADED
            message = f"MCP servers down: {', '.join(unresponsive)}"

        self._add_check(
            CheckResult(
                name="MCP Servers",
                status=status,
                message=message,
                details={
                    "responsive": responsive,
                    "unresponsive": unresponsive,
                },
                duration_ms=int((time.time() - start) * 1000),
            )
        )

    def fix_issues(self, report: HealthReport) -> int:
        """Intenta arreglar issues automáticamente."""
        fixed = 0

        for check in report.checks:
            if check.fix_available and check.fix_command:
                print(f"Fixing: {check.name}")
                print(f"  Running: {check.fix_command}")

                code, out, err = self._run_command(shlex.split(check.fix_command), timeout=60)

                if code == 0:
                    print("  ✅ Fixed")
                    fixed += 1
                else:
                    print(f"  ❌ Failed: {err}")

        return fixed


def main():
    """Función principal."""
    import argparse

    _configure_console_encoding()

    parser = argparse.ArgumentParser(description="Health Check del ecosistema")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fix", action="store_true", help="Intentar arreglar issues")
    parser.add_argument("--quiet", "-q", action="store_true", help="Solo mostrar resumen")
    args = parser.parse_args()

    checker = HealthChecker()
    report = checker.run_all_checks()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.quiet:
        print(f"Health: {report.overall_status.value} ({report.score:.0f}%)")
    else:
        print(report.to_markdown())

    if args.fix:
        print("\n" + "=" * 50)
        print("Attempting to fix issues...")
        fixed = checker.fix_issues(report)
        print(f"Fixed {fixed} issues")

    # Exit code
    if report.overall_status == Status.HEALTHY:
        sys.exit(0)
    elif report.overall_status == Status.DEGRADED:
        sys.exit(0)  # Degraded is OK
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
