#!/usr/bin/env python3
"""Dependency Vulnerability Scanner — Auditoría de dependencias.

Ejecuta pip-audit y safety para detectar vulnerabilidades conocidas
en las dependencias del proyecto. Genera reporte JSON o texto.

Inspirado en el checker de dependencias de OpenClaw que verifica
versiones, CVEs y licencias en el monorepo.

Uso:
    python .agent/scripts/audit_deps.py
    python .agent/scripts/audit_deps.py --json
    python .agent/scripts/audit_deps.py --fix
    python .agent/scripts/audit_deps.py --requirements requirements.txt

v1.0.0 - 2026-02-27
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.audit_deps")

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Vulnerability:
    """Una vulnerabilidad detectada."""

    package: str
    installed_version: str
    affected_versions: str
    advisory_id: str  # CVE, GHSA, PYSEC
    description: str
    severity: str  # critical, high, medium, low, unknown
    fix_version: str = ""

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        return {
            "package": self.package,
            "installed_version": self.installed_version,
            "affected_versions": self.affected_versions,
            "advisory_id": self.advisory_id,
            "description": self.description,
            "severity": self.severity,
            "fix_version": self.fix_version,
        }


@dataclass
class AuditReport:
    """Reporte de auditoría de dependencias."""

    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    packages_scanned: int = 0
    tool_used: str = ""
    error: str = ""

    @property
    def critical_count(self) -> int:
        """Número de vulns críticas."""
        return sum(1 for v in self.vulnerabilities if v.severity == "critical")

    @property
    def high_count(self) -> int:
        """Número de vulns high."""
        return sum(1 for v in self.vulnerabilities if v.severity == "high")

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        return {
            "tool_used": self.tool_used,
            "packages_scanned": self.packages_scanned,
            "total_vulnerabilities": len(self.vulnerabilities),
            "by_severity": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": sum(1 for v in self.vulnerabilities if v.severity == "medium"),
                "low": sum(1 for v in self.vulnerabilities if v.severity == "low"),
            },
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "error": self.error,
        }


# =============================================================================
# pip-audit INTEGRATION
# =============================================================================


def _run_pip_audit(
    requirements: Path | None = None,
    fix: bool = False,
) -> AuditReport:
    """Ejecuta pip-audit.

    Args:
        requirements: Archivo requirements.txt específico.
        fix: Intentar auto-arreglar vulnerabilidades.

    Returns:
        AuditReport con resultados.
    """
    report = AuditReport(tool_used="pip-audit")

    if not shutil.which("pip-audit"):
        report.error = "pip-audit no instalado. Instalar con: pip install pip-audit"
        return report

    cmd = ["pip-audit", "--format", "json", "--progress-spinner", "off"]

    if requirements and requirements.is_file():
        cmd.extend(["--requirement", str(requirements)])

    if fix:
        cmd.append("--fix")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )

        # pip-audit retorna JSON incluso en exit code != 0 (cuando hay vulns)
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()

        if output.startswith("{") or output.startswith("["):
            data = json.loads(output)

            # pip-audit puede retornar dict o list según versión
            vulns_data = data if isinstance(data, list) else data.get("dependencies", [])

            for dep in vulns_data:
                pkg_name = dep.get("name", "")
                pkg_version = dep.get("version", "")
                dep_vulns = dep.get("vulns", [])

                for vuln in dep_vulns:
                    severity = _classify_severity(vuln.get("id", ""))
                    report.vulnerabilities.append(
                        Vulnerability(
                            package=pkg_name,
                            installed_version=pkg_version,
                            affected_versions=vuln.get("fix_versions", [""])[0]
                            if vuln.get("fix_versions")
                            else "",
                            advisory_id=vuln.get("id", "UNKNOWN"),
                            description=vuln.get("description", "No description"),
                            severity=severity,
                            fix_version=vuln.get("fix_versions", [""])[0]
                            if vuln.get("fix_versions")
                            else "",
                        )
                    )

            report.packages_scanned = len(vulns_data)
        else:
            # Si no hay JSON, reportar como texto
            if result.returncode == 0:
                report.packages_scanned = -1  # Desconocido pero OK
            else:
                report.error = output[:500]

    except subprocess.TimeoutExpired:
        report.error = "pip-audit timeout (120s)"
    except json.JSONDecodeError as e:
        report.error = f"Error parseando output: {e}"
    except Exception as e:
        report.error = str(e)

    return report


def _classify_severity(advisory_id: str) -> str:
    """Clasifica severidad basada en el ID del advisory.

    Heurística simple: los CVEs recientes tienden a ser más severos.
    Idealmente se consultaría la API de NVD/OSV.

    Args:
        advisory_id: Identificador del advisory (CVE, GHSA, PYSEC).

    Returns:
        Severidad estimada.
    """
    advisory_id = advisory_id.upper()
    if advisory_id.startswith("GHSA"):
        return "high"  # GitHub Security Advisories tienden a ser altos
    if advisory_id.startswith("CVE"):
        return "medium"  # Default para CVEs sin score
    if advisory_id.startswith("PYSEC"):
        return "medium"
    return "unknown"


# =============================================================================
# SAFETY CHECK (fallback)
# =============================================================================


def _run_safety_check() -> AuditReport:
    """Ejecuta safety check como fallback si pip-audit no está disponible.

    Returns:
        AuditReport con resultados.
    """
    report = AuditReport(tool_used="safety")

    if not shutil.which("safety"):
        report.error = "safety no instalado. Instalar con: pip install safety"
        return report

    try:
        result = subprocess.run(
            ["safety", "check", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )

        output = result.stdout.strip()
        if output:
            data = json.loads(output)
            vulns = data if isinstance(data, list) else data.get("vulnerabilities", [])

            for vuln_entry in vulns:
                if isinstance(vuln_entry, list) and len(vuln_entry) >= 4:
                    report.vulnerabilities.append(
                        Vulnerability(
                            package=vuln_entry[0],
                            installed_version=vuln_entry[2],
                            affected_versions=vuln_entry[1],
                            advisory_id=str(vuln_entry[4]) if len(vuln_entry) > 4 else "UNKNOWN",
                            description=vuln_entry[3] if len(vuln_entry) > 3 else "",
                            severity="medium",
                        )
                    )
                elif isinstance(vuln_entry, dict):
                    report.vulnerabilities.append(
                        Vulnerability(
                            package=vuln_entry.get("package_name", ""),
                            installed_version=vuln_entry.get("analyzed_version", ""),
                            affected_versions=vuln_entry.get("vulnerable_versions", ""),
                            advisory_id=vuln_entry.get("vulnerability_id", "UNKNOWN"),
                            description=vuln_entry.get("advisory", ""),
                            severity=vuln_entry.get("severity", "medium"),
                        )
                    )

    except Exception as e:
        report.error = str(e)

    return report


# =============================================================================
# MAIN AUDIT FUNCTION
# =============================================================================


def audit_dependencies(
    requirements: Path | None = None,
    fix: bool = False,
) -> AuditReport:
    """Audita dependencias usando pip-audit o safety como fallback.

    Args:
        requirements: Archivo requirements.txt específico.
        fix: Intentar auto-arreglar.

    Returns:
        AuditReport con todos los findings.
    """
    # Intentar pip-audit primero
    report = _run_pip_audit(requirements=requirements, fix=fix)

    if report.error and "no instalado" in report.error:
        # Fallback a safety
        logger.info("pip-audit no disponible, intentando safety...")
        report = _run_safety_check()

    if report.error and "no instalado" in report.error:
        logger.warning("Ni pip-audit ni safety disponibles")

    # Ordenar por severidad
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
    report.vulnerabilities.sort(key=lambda v: severity_order.get(v.severity, 4))

    return report


# =============================================================================
# CLI
# =============================================================================


def print_report(report: AuditReport) -> None:
    """Imprime reporte legible."""
    severity_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🔵",
        "unknown": "⚪",
    }

    print(f"\n{'=' * 70}")
    print(f"Dependency Vulnerability Audit — {report.tool_used}")
    print(f"Packages scanned: {report.packages_scanned}")
    print(f"{'=' * 70}\n")

    if report.error:
        print(f"⚠️  Error: {report.error}\n")

    if not report.vulnerabilities:
        print("✅ No known vulnerabilities found!\n")
        return

    for vuln in report.vulnerabilities:
        emoji = severity_emoji.get(vuln.severity, "⚪")
        print(f"{emoji} [{vuln.severity.upper()}] {vuln.package}=={vuln.installed_version}")
        print(f"   Advisory: {vuln.advisory_id}")
        print(f"   {vuln.description[:100]}")
        if vuln.fix_version:
            print(f"   Fix: upgrade to {vuln.fix_version}")
        print()

    print(f"{'=' * 70}")
    print(
        f"Summary: {report.critical_count} critical, {report.high_count} high, "
        f"{len(report.vulnerabilities) - report.critical_count - report.high_count} other"
    )
    print(f"{'=' * 70}\n")


def main() -> None:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Auditar dependencias por vulnerabilidades")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fix", action="store_true", help="Intentar auto-arreglar")
    parser.add_argument(
        "--requirements",
        type=str,
        default=None,
        help="Archivo requirements.txt específico",
    )
    args = parser.parse_args()

    req_path = Path(args.requirements) if args.requirements else None
    report = audit_dependencies(requirements=req_path, fix=args.fix)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    # Exit code: 1 si hay vulns críticas
    if report.critical_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
