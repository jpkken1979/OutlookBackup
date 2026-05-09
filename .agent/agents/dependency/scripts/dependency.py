#!/usr/bin/env python3
"""
Dependency Agent - Dependency Management & Security

Capabilities:
- Audit vulnerabilities in dependencies
- Check for outdated packages
- Analyze dependency tree
- Suggest updates with breaking change warnings
"""

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Vulnerability:
    """A security vulnerability."""

    package: str
    severity: str  # critical, high, medium, low
    cve: str | None
    description: str
    fixed_in: str | None


@dataclass
class OutdatedPackage:
    """An outdated package."""

    name: str
    current: str
    latest: str
    wanted: str
    type: str  # dependencies, devDependencies


@dataclass
class DependencyReport:
    """Complete dependency analysis report."""

    project_path: str
    package_manager: str
    total_dependencies: int
    direct_dependencies: int
    dev_dependencies: int
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    outdated: list[OutdatedPackage] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "package_manager": self.package_manager,
            "total_dependencies": self.total_dependencies,
            "direct_dependencies": self.direct_dependencies,
            "dev_dependencies": self.dev_dependencies,
            "vulnerabilities": {
                "total": len(self.vulnerabilities),
                "critical": sum(1 for v in self.vulnerabilities if v.severity == "critical"),
                "high": sum(1 for v in self.vulnerabilities if v.severity == "high"),
                "medium": sum(1 for v in self.vulnerabilities if v.severity == "medium"),
                "low": sum(1 for v in self.vulnerabilities if v.severity == "low"),
                "details": [v.__dict__ for v in self.vulnerabilities],
            },
            "outdated": [o.__dict__ for o in self.outdated],
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Dependency Analysis Report",
            "",
            f"**Project:** {self.project_path}",
            f"**Package Manager:** {self.package_manager}",
            "",
            "## Summary",
            f"- Total Dependencies: {self.total_dependencies}",
            f"- Direct Dependencies: {self.direct_dependencies}",
            f"- Dev Dependencies: {self.dev_dependencies}",
            "",
        ]

        if self.vulnerabilities:
            lines.extend(
                [
                    "## Vulnerabilities",
                    "",
                    f"Found **{len(self.vulnerabilities)}** vulnerabilities:",
                    "",
                ]
            )
            for vuln in self.vulnerabilities:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(
                    vuln.severity, "⚪"
                )
                lines.append(f"### {icon} {vuln.package} ({vuln.severity.upper()})")
                if vuln.cve:
                    lines.append(f"- **CVE:** {vuln.cve}")
                lines.append(f"- **Description:** {vuln.description}")
                if vuln.fixed_in:
                    lines.append(f"- **Fixed in:** {vuln.fixed_in}")
                lines.append("")

        if self.outdated:
            lines.extend(
                [
                    "## Outdated Packages",
                    "",
                    "| Package | Current | Wanted | Latest |",
                    "|---------|---------|--------|--------|",
                ]
            )
            for pkg in self.outdated[:20]:
                lines.append(f"| {pkg.name} | {pkg.current} | {pkg.wanted} | {pkg.latest} |")
            lines.append("")

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class DependencyAgent:
    """Dependency management and security agent."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> DependencyReport:
        """Analyze project dependencies."""
        logger.info(f"Analyzing dependencies in {self.project_path}")

        # Detect package manager
        pkg_manager = self._detect_package_manager()
        logger.info(f"Detected package manager: {pkg_manager}")

        if pkg_manager == "npm":
            return await self._analyze_npm()
        elif pkg_manager == "pip":
            return await self._analyze_pip()
        elif pkg_manager == "cargo":
            return await self._analyze_cargo()
        else:
            return DependencyReport(
                project_path=str(self.project_path),
                package_manager="unknown",
                total_dependencies=0,
                direct_dependencies=0,
                dev_dependencies=0,
                recommendations=["Could not detect package manager"],
            )

    def _detect_package_manager(self) -> str:
        """Detect which package manager is used."""
        if (self.project_path / "package.json").exists():
            return "npm"
        elif (self.project_path / "requirements.txt").exists() or (
            self.project_path / "pyproject.toml"
        ).exists():
            return "pip"
        elif (self.project_path / "Cargo.toml").exists():
            return "cargo"
        elif (self.project_path / "go.mod").exists():
            return "go"
        return "unknown"

    async def _analyze_npm(self) -> DependencyReport:
        """Analyze npm/yarn dependencies."""
        vulnerabilities = []
        outdated = []
        recommendations = []

        # Read package.json
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            with open(pkg_json) as f:
                pkg_data = json.load(f)

            deps = pkg_data.get("dependencies", {})
            dev_deps = pkg_data.get("devDependencies", {})
            direct_count = len(deps)
            dev_count = len(dev_deps)

            # Run npm audit
            try:
                result = subprocess.run(
                    ["npm", "audit", "--json"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=60,
                )
                if result.stdout:
                    audit_data = json.loads(result.stdout)
                    if "vulnerabilities" in audit_data:
                        for pkg_name, vuln_info in audit_data["vulnerabilities"].items():
                            vulnerabilities.append(
                                Vulnerability(
                                    package=pkg_name,
                                    severity=vuln_info.get("severity", "unknown"),
                                    cve=vuln_info.get("via", [{}])[0].get("cve")
                                    if isinstance(vuln_info.get("via", []), list)
                                    else None,
                                    description=vuln_info.get("via", [{}])[0].get(
                                        "title", "Unknown"
                                    )
                                    if isinstance(vuln_info.get("via", []), list)
                                    else str(vuln_info.get("via", "")),
                                    fixed_in=vuln_info.get("fixAvailable", {}).get("version")
                                    if isinstance(vuln_info.get("fixAvailable"), dict)
                                    else None,
                                )
                            )
            except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"npm audit failed: {e}")

            # Check for outdated
            try:
                result = subprocess.run(
                    ["npm", "outdated", "--json"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=60,
                )
                if result.stdout:
                    outdated_data = json.loads(result.stdout)
                    for pkg_name, info in outdated_data.items():
                        outdated.append(
                            OutdatedPackage(
                                name=pkg_name,
                                current=info.get("current", "?"),
                                latest=info.get("latest", "?"),
                                wanted=info.get("wanted", "?"),
                                type=info.get("type", "dependencies"),
                            )
                        )
            except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"npm outdated failed: {e}")

            # Count total from node_modules
            node_modules = self.project_path / "node_modules"
            total = 0
            if node_modules.exists():
                total = len(
                    [d for d in node_modules.iterdir() if d.is_dir() and not d.name.startswith(".")]
                )

            # Generate recommendations
            if any(v.severity == "critical" for v in vulnerabilities):
                recommendations.append(
                    "Run `npm audit fix --force` to fix critical vulnerabilities"
                )
            if outdated:
                recommendations.append(
                    f"Update {len(outdated)} outdated packages with `npm update`"
                )
            if not (self.project_path / "package-lock.json").exists():
                recommendations.append("Generate package-lock.json for reproducible builds")

            return DependencyReport(
                project_path=str(self.project_path),
                package_manager="npm",
                total_dependencies=total or direct_count + dev_count,
                direct_dependencies=direct_count,
                dev_dependencies=dev_count,
                vulnerabilities=vulnerabilities,
                outdated=outdated,
                recommendations=recommendations,
            )

        return DependencyReport(
            project_path=str(self.project_path),
            package_manager="npm",
            total_dependencies=0,
            direct_dependencies=0,
            dev_dependencies=0,
        )

    async def _analyze_pip(self) -> DependencyReport:
        """Analyze Python dependencies."""
        vulnerabilities = []
        outdated = []
        recommendations = []
        dependencies = []

        # Parse requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            with open(req_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name
                        match = re.match(r"^([a-zA-Z0-9_-]+)", line)
                        if match:
                            dependencies.append(match.group(1))

        # Parse pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            # Simple regex to find dependencies
            deps_match = re.findall(r'"([a-zA-Z0-9_-]+)[><=!~]', content)
            dependencies.extend(deps_match)

        dependencies = list(set(dependencies))

        # Run pip-audit if available
        try:
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=120,
            )
            if result.stdout:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data:
                    vulnerabilities.append(
                        Vulnerability(
                            package=vuln.get("name", "unknown"),
                            severity=vuln.get("severity", "unknown"),
                            cve=vuln.get("id"),
                            description=vuln.get("description", ""),
                            fixed_in=vuln.get("fix_versions", [None])[0]
                            if vuln.get("fix_versions")
                            else None,
                        )
                    )
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"pip-audit not available: {e}")
            recommendations.append(
                "Install pip-audit for vulnerability scanning: `pip install pip-audit`"
            )

        # Check for outdated with pip list
        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.stdout:
                outdated_data = json.loads(result.stdout)
                for pkg in outdated_data:
                    outdated.append(
                        OutdatedPackage(
                            name=pkg.get("name", ""),
                            current=pkg.get("version", ""),
                            latest=pkg.get("latest_version", ""),
                            wanted=pkg.get("latest_version", ""),
                            type="dependencies",
                        )
                    )
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"pip list failed: {e}")

        if vulnerabilities:
            recommendations.append("Update vulnerable packages immediately")
        if not (self.project_path / "requirements.txt").exists() and not pyproject.exists():
            recommendations.append(
                "Create requirements.txt or pyproject.toml for dependency tracking"
            )

        return DependencyReport(
            project_path=str(self.project_path),
            package_manager="pip",
            total_dependencies=len(dependencies),
            direct_dependencies=len(dependencies),
            dev_dependencies=0,
            vulnerabilities=vulnerabilities,
            outdated=outdated,
            recommendations=recommendations,
        )

    async def _analyze_cargo(self) -> DependencyReport:
        """Analyze Rust/Cargo dependencies."""
        vulnerabilities = []
        recommendations = []

        cargo_toml = self.project_path / "Cargo.toml"
        if cargo_toml.exists():
            content = cargo_toml.read_text()
            deps = re.findall(r"^\s*(\w+)\s*=", content, re.MULTILINE)
            direct_count = len(
                [d for d in deps if d not in ["package", "dependencies", "dev-dependencies"]]
            )

            # Run cargo audit if available
            try:
                result = subprocess.run(
                    ["cargo", "audit", "--json"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=120,
                )
                if result.stdout:
                    audit_data = json.loads(result.stdout)
                    for vuln in audit_data.get("vulnerabilities", {}).get("list", []):
                        vulnerabilities.append(
                            Vulnerability(
                                package=vuln.get("package", {}).get("name", "unknown"),
                                severity=vuln.get("advisory", {}).get("severity", "unknown"),
                                cve=vuln.get("advisory", {}).get("id"),
                                description=vuln.get("advisory", {}).get("title", ""),
                                fixed_in=vuln.get("versions", {}).get("patched", [None])[0],
                            )
                        )
            except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
                recommendations.append("Install cargo-audit: `cargo install cargo-audit`")

            return DependencyReport(
                project_path=str(self.project_path),
                package_manager="cargo",
                total_dependencies=direct_count,
                direct_dependencies=direct_count,
                dev_dependencies=0,
                vulnerabilities=vulnerabilities,
                recommendations=recommendations,
            )

        return DependencyReport(
            project_path=str(self.project_path),
            package_manager="cargo",
            total_dependencies=0,
            direct_dependencies=0,
            dev_dependencies=0,
        )


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Dependency Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = DependencyAgent(args.path)
    report = await agent.analyze()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
