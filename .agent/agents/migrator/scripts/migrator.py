#!/usr/bin/env python3
"""
Migrator Agent - Framework & Technology Migration

Capabilities:
- Analyze migration complexity
- Detect breaking changes
- Generate migration plans
- Track migration progress
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BreakingChange:
    """A breaking change that needs attention."""

    severity: str  # critical, high, medium, low
    type: str  # api, dependency, config, syntax
    file: str
    line: int | None
    description: str
    migration_path: str


@dataclass
class MigrationStep:
    """A step in the migration plan."""

    order: int
    title: str
    description: str
    files_affected: list[str] = field(default_factory=list)
    estimated_effort: str = "unknown"
    automated: bool = False


@dataclass
class MigrationReport:
    """Migration analysis report."""

    project_path: str
    from_version: str
    to_version: str
    framework: str
    breaking_changes: list[BreakingChange] = field(default_factory=list)
    migration_steps: list[MigrationStep] = field(default_factory=list)
    complexity: str = "unknown"  # low, medium, high, extreme
    estimated_effort: str = "unknown"
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "framework": self.framework,
            "breaking_changes": [b.__dict__ for b in self.breaking_changes],
            "migration_steps": [s.__dict__ for s in self.migration_steps],
            "complexity": self.complexity,
            "estimated_effort": self.estimated_effort,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Migration Analysis Report",
            "",
            f"**Project:** {self.project_path}",
            f"**Framework:** {self.framework}",
            f"**Migration:** {self.from_version} → {self.to_version}",
            f"**Complexity:** {self.complexity.upper()}",
            f"**Estimated Effort:** {self.estimated_effort}",
            "",
        ]

        # Breaking changes summary
        if self.breaking_changes:
            lines.extend(
                [
                    "## Breaking Changes",
                    "",
                    f"Found **{len(self.breaking_changes)}** breaking changes:",
                    "",
                ]
            )

            for severity in ["critical", "high", "medium", "low"]:
                changes = [c for c in self.breaking_changes if c.severity == severity]
                if changes:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
                    lines.append(f"### {icon} {severity.title()} ({len(changes)})")
                    for change in changes:
                        lines.extend(
                            [
                                f"- **{change.type}** in `{change.file}`"
                                + (f":{change.line}" if change.line else ""),
                                f"  - {change.description}",
                                f"  - *Migration:* {change.migration_path}",
                                "",
                            ]
                        )

        # Migration steps
        if self.migration_steps:
            lines.extend(["## Migration Plan", ""])
            for step in self.migration_steps:
                auto = "🤖 (automated)" if step.automated else "👤 (manual)"
                lines.extend(
                    [
                        f"### Step {step.order}: {step.title} {auto}",
                        "",
                        step.description,
                        "",
                        f"**Effort:** {step.estimated_effort}",
                        "",
                    ]
                )
                if step.files_affected:
                    lines.append("**Files affected:**")
                    for f in step.files_affected[:5]:
                        lines.append(f"- `{f}`")
                    if len(step.files_affected) > 5:
                        lines.append(f"- ... and {len(step.files_affected) - 5} more")
                    lines.append("")

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class MigratorAgent:
    """Migration analysis agent."""

    # Common migration patterns
    MIGRATIONS = {
        "react": {
            "17-18": {
                "breaking_changes": [
                    {
                        "pattern": r"ReactDOM\.render\(",
                        "description": "ReactDOM.render is deprecated",
                        "migration": "Use createRoot from react-dom/client",
                    },
                    {
                        "pattern": r"import.*from\s+['\"]react['\"]",
                        "description": "Automatic JSX runtime",
                        "migration": "Update to new JSX transform (optional)",
                    },
                ]
            },
            "18-19": {
                "breaking_changes": [
                    {
                        "pattern": r"useEffect\([^)]+,\s*\[\]\)",
                        "description": "useEffect cleanup timing changed",
                        "migration": "Review effect dependencies",
                    },
                    {
                        "pattern": r"forwardRef",
                        "description": "ref prop now passed directly",
                        "migration": "Remove forwardRef wrapper",
                    },
                ]
            },
        },
        "next": {
            "13-14": {
                "breaking_changes": [
                    {
                        "pattern": r"getServerSideProps|getStaticProps",
                        "description": "Data fetching patterns changed",
                        "migration": "Use async Server Components",
                    },
                    {
                        "pattern": r"next/image",
                        "description": "Image component updated",
                        "migration": "Review image optimization props",
                    },
                ]
            },
            "14-15": {
                "breaking_changes": [
                    {
                        "pattern": r"@next/font",
                        "description": "Font package renamed",
                        "migration": "Use next/font instead",
                    }
                ]
            },
        },
        "python": {
            "3.9-3.10": {
                "breaking_changes": [
                    {
                        "pattern": r"Union\[|Optional\[",
                        "description": "Type hints can use | operator",
                        "migration": "Use X | Y instead of Union[X, Y]",
                    }
                ]
            },
            "3.11-3.12": {
                "breaking_changes": [
                    {
                        "pattern": r"asyncio\.get_event_loop\(\)",
                        "description": "get_event_loop deprecated",
                        "migration": "Use asyncio.get_running_loop() or asyncio.run()",
                    }
                ]
            },
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self, from_version: str = None, to_version: str = None) -> MigrationReport:
        """Analyze project for migration."""
        logger.info(f"Analyzing migration in {self.project_path}")

        # Detect framework and versions
        framework, current_version = self._detect_framework()

        if not from_version:
            from_version = current_version
        if not to_version:
            to_version = "latest"

        breaking_changes = []
        migration_steps = []

        # Analyze based on framework
        if framework in ["react", "next"]:
            breaking_changes, migration_steps = await self._analyze_react_migration(
                framework, from_version, to_version
            )
        elif framework == "python":
            breaking_changes, migration_steps = await self._analyze_python_migration(
                from_version, to_version
            )

        # Calculate complexity
        complexity = self._calculate_complexity(breaking_changes)
        effort = self._estimate_effort(breaking_changes, migration_steps)

        # Generate recommendations
        recommendations = self._generate_recommendations(framework, breaking_changes)

        return MigrationReport(
            project_path=str(self.project_path),
            from_version=from_version,
            to_version=to_version,
            framework=framework,
            breaking_changes=breaking_changes,
            migration_steps=migration_steps,
            complexity=complexity,
            estimated_effort=effort,
            recommendations=recommendations,
        )

    def _detect_framework(self) -> tuple[str, str]:
        """Detect framework and version."""
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            content = json.loads(pkg_json.read_text())
            deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}

            if "next" in deps:
                version = deps["next"].lstrip("^~")
                return "next", version.split(".")[0]
            if "react" in deps:
                version = deps["react"].lstrip("^~")
                return "react", version.split(".")[0]

        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            match = re.search(r'python\s*=\s*["\']>=?(\d+\.\d+)', content)
            if match:
                return "python", match.group(1)

        return "unknown", "unknown"

    async def _analyze_react_migration(
        self, framework: str, from_ver: str, to_ver: str
    ) -> tuple[list, list]:
        """Analyze React/Next.js migration."""
        breaking_changes = []
        migration_steps = []

        # Get migration rules
        migration_key = f"{from_ver}-{to_ver}"
        rules = self.MIGRATIONS.get(framework, {}).get(migration_key, {})

        for file_path in self.project_path.glob("**/*.{js,jsx,ts,tsx}"):
            if any(skip in str(file_path) for skip in ["node_modules", "dist", ".next"]):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))

                for rule in rules.get("breaking_changes", []):
                    for match in re.finditer(rule["pattern"], content):
                        line = content[: match.start()].count("\n") + 1
                        breaking_changes.append(
                            BreakingChange(
                                severity="high",
                                type="api",
                                file=rel_path,
                                line=line,
                                description=rule["description"],
                                migration_path=rule["migration"],
                            )
                        )

            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")

        # Generate migration steps
        if breaking_changes:
            migration_steps = [
                MigrationStep(
                    order=1,
                    title="Update dependencies",
                    description=f"Update {framework} and related packages to {to_ver}",
                    estimated_effort="15 minutes",
                    automated=True,
                ),
                MigrationStep(
                    order=2,
                    title="Fix breaking API changes",
                    description="Update deprecated APIs and patterns",
                    files_affected=list({c.file for c in breaking_changes}),
                    estimated_effort=f"{len(breaking_changes) * 10} minutes",
                ),
                MigrationStep(
                    order=3,
                    title="Run tests",
                    description="Verify all tests pass after migration",
                    estimated_effort="30 minutes",
                    automated=True,
                ),
                MigrationStep(
                    order=4,
                    title="Manual testing",
                    description="Test critical user flows manually",
                    estimated_effort="1-2 hours",
                ),
            ]

        return breaking_changes, migration_steps

    async def _analyze_python_migration(self, from_ver: str, to_ver: str) -> tuple[list, list]:
        """Analyze Python version migration."""
        breaking_changes = []
        migration_steps = []

        migration_key = f"{from_ver}-{to_ver}"
        rules = self.MIGRATIONS.get("python", {}).get(migration_key, {})

        for file_path in self.project_path.glob("**/*.py"):
            if any(skip in str(file_path) for skip in ["venv", "__pycache__", ".git"]):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))

                for rule in rules.get("breaking_changes", []):
                    for match in re.finditer(rule["pattern"], content):
                        line = content[: match.start()].count("\n") + 1
                        breaking_changes.append(
                            BreakingChange(
                                severity="medium",
                                type="syntax",
                                file=rel_path,
                                line=line,
                                description=rule["description"],
                                migration_path=rule["migration"],
                            )
                        )

            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")

        if breaking_changes:
            migration_steps = [
                MigrationStep(
                    order=1,
                    title="Update Python version",
                    description=f"Update Python from {from_ver} to {to_ver}",
                    estimated_effort="30 minutes",
                    automated=True,
                ),
                MigrationStep(
                    order=2,
                    title="Update dependencies",
                    description="Update all dependencies to compatible versions",
                    estimated_effort="1 hour",
                ),
                MigrationStep(
                    order=3,
                    title="Fix deprecated patterns",
                    description="Update code to use new APIs",
                    files_affected=list({c.file for c in breaking_changes}),
                    estimated_effort=f"{len(breaking_changes) * 5} minutes",
                ),
            ]

        return breaking_changes, migration_steps

    def _calculate_complexity(self, breaking_changes: list) -> str:
        """Calculate migration complexity."""
        critical = sum(1 for c in breaking_changes if c.severity == "critical")
        high = sum(1 for c in breaking_changes if c.severity == "high")
        total = len(breaking_changes)

        if critical > 5 or total > 50:
            return "extreme"
        elif critical > 0 or high > 10 or total > 20:
            return "high"
        elif high > 5 or total > 10:
            return "medium"
        else:
            return "low"

    def _estimate_effort(self, breaking_changes: list, steps: list) -> str:
        """Estimate migration effort."""
        total = len(breaking_changes)

        if total > 50:
            return "1-2 weeks"
        elif total > 20:
            return "2-5 days"
        elif total > 10:
            return "1-2 days"
        elif total > 5:
            return "4-8 hours"
        else:
            return "1-4 hours"

    def _generate_recommendations(self, framework: str, breaking_changes: list) -> list[str]:
        """Generate migration recommendations."""
        recommendations = [
            "Create a backup branch before starting migration",
            "Run full test suite before and after migration",
            "Consider incremental migration for large codebases",
        ]

        if len(breaking_changes) > 20:
            recommendations.append("Use automated codemods where available")

        if any(c.severity == "critical" for c in breaking_changes):
            recommendations.insert(0, "Address critical breaking changes first")

        return recommendations[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrator Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--from", dest="from_version", help="Source version")
    parser.add_argument("--to", dest="to_version", help="Target version")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = MigratorAgent(args.path)
    report = await agent.analyze(args.from_version, args.to_version)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
