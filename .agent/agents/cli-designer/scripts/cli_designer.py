#!/usr/bin/env python3
"""
CLI Designer Agent - Terminal Interface Design

Capabilities:
- Analyze CLI structure and UX
- Check command naming conventions
- Validate help text and documentation
- Generate CLI templates
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
class CLICommand:
    """CLI command information."""

    name: str
    description: str
    arguments: list[dict] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)
    subcommands: list[str] = field(default_factory=list)
    file: str = ""


@dataclass
class CLIIssue:
    """CLI design issue."""

    severity: str
    category: str  # naming, help, ux, accessibility
    command: str | None
    description: str
    suggestion: str


@dataclass
class CLIReport:
    """CLI analysis report."""

    project_path: str
    framework: str = "unknown"
    commands: list[CLICommand] = field(default_factory=list)
    issues: list[CLIIssue] = field(default_factory=list)
    score: int = 100
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "framework": self.framework,
            "commands": [c.__dict__ for c in self.commands],
            "issues": [i.__dict__ for i in self.issues],
            "score": self.score,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# CLI Design Report",
            "",
            f"**Project:** {self.project_path}",
            f"**Framework:** {self.framework}",
            f"**CLI Score:** {self.score}/100",
            "",
            "## Commands",
        ]

        if self.commands:
            lines.extend(
                [
                    "",
                    "| Command | Description | Args | Options |",
                    "|---------|-------------|------|---------|",
                ]
            )
            for cmd in self.commands:
                desc = (
                    cmd.description[:40] + "..." if len(cmd.description) > 40 else cmd.description
                )
                lines.append(
                    f"| `{cmd.name}` | {desc} | {len(cmd.arguments)} | {len(cmd.options)} |"
                )
            lines.append("")

            # Command details
            for cmd in self.commands[:5]:
                lines.extend([f"### {cmd.name}", "", cmd.description, ""])
                if cmd.arguments:
                    lines.append("**Arguments:**")
                    for arg in cmd.arguments:
                        lines.append(
                            f"- `{arg.get('name', 'unnamed')}`: {arg.get('help', 'No description')}"
                        )
                if cmd.options:
                    lines.append("**Options:**")
                    for opt in cmd.options:
                        lines.append(
                            f"- `{opt.get('name', 'unnamed')}`: {opt.get('help', 'No description')}"
                        )
                lines.append("")

        # Issues
        if self.issues:
            lines.extend(["## Issues", ""])
            for severity in ["critical", "high", "medium", "low"]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
                    lines.append(f"### {icon} {severity.title()} ({len(severity_issues)})")
                    for issue in severity_issues:
                        lines.extend(
                            [
                                f"- **{issue.category}**"
                                + (f" ({issue.command})" if issue.command else ""),
                                f"  - {issue.description}",
                                f"  - *Fix:* {issue.suggestion}",
                                "",
                            ]
                        )

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class CLIDesigner:
    """CLI design analysis agent."""

    NAMING_RULES = {
        "verb-noun": r"^(get|set|list|create|delete|update|add|remove|show|run|start|stop|init|build|deploy|test)\-?\w*$",
        "kebab-case": r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$",
        "no-abbreviations": ["cfg", "usr", "grp", "msg", "btn"],
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> CLIReport:
        """Analyze CLI design."""
        logger.info(f"Analyzing CLI in {self.project_path}")

        # Detect CLI framework
        framework = self._detect_framework()

        commands = []
        issues = []

        # Analyze based on framework
        if framework in ["typer", "click"]:
            commands, issues = await self._analyze_python_cli(framework)
        elif framework in ["commander", "yargs"]:
            commands, issues = await self._analyze_node_cli(framework)
        elif framework == "argparse":
            commands, issues = await self._analyze_argparse()

        # Calculate score
        score = self._calculate_score(issues, len(commands))

        # Generate recommendations
        recommendations = self._generate_recommendations(commands, issues, framework)

        return CLIReport(
            project_path=str(self.project_path),
            framework=framework,
            commands=commands,
            issues=issues,
            score=score,
            recommendations=recommendations,
        )

    def _detect_framework(self) -> str:
        """Detect CLI framework."""
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            content = pkg_json.read_text()
            if '"commander"' in content:
                return "commander"
            if '"yargs"' in content:
                return "yargs"

        # Check Python
        for py_file in self.project_path.glob("**/*.py"):
            if any(skip in str(py_file) for skip in ["venv", "node_modules"]):
                continue
            try:
                content = py_file.read_text(errors="ignore")
                if "import typer" in content or "from typer" in content:
                    return "typer"
                if "import click" in content or "from click" in content:
                    return "click"
                if "import argparse" in content:
                    return "argparse"
            except Exception:
                pass

        return "unknown"

    async def _analyze_python_cli(self, framework: str) -> tuple[list[CLICommand], list[CLIIssue]]:
        """Analyze Python CLI (Typer/Click)."""
        commands = []
        issues = []

        for py_file in self.project_path.glob("**/*.py"):
            if any(skip in str(py_file) for skip in ["venv", "node_modules", "test"]):
                continue

            try:
                content = py_file.read_text(errors="ignore")
                rel_path = str(py_file.relative_to(self.project_path))

                if framework == "typer":
                    # Find Typer commands
                    for match in re.finditer(r'@app\.command\([\'"]?([^\'")\n]*)[\'"]?\)', content):
                        cmd_name = match.group(1) or "default"

                        # Find function definition after decorator
                        func_match = re.search(
                            r"def\s+(\w+)\s*\(([^)]*)\)", content[match.end() : match.end() + 500]
                        )
                        if func_match:
                            func_name = func_match.group(1)
                            func_match.group(2)

                            # Extract docstring
                            doc_match = re.search(
                                r'"""([^"]+)"""', content[match.end() : match.end() + 1000]
                            )
                            description = doc_match.group(1).strip() if doc_match else ""

                            commands.append(
                                CLICommand(
                                    name=cmd_name or func_name.replace("_", "-"),
                                    description=description,
                                    file=rel_path,
                                )
                            )

                            # Check for issues
                            if not description:
                                issues.append(
                                    CLIIssue(
                                        severity="medium",
                                        category="help",
                                        command=cmd_name or func_name,
                                        description="Command missing docstring/help text",
                                        suggestion="Add docstring for --help output",
                                    )
                                )

                elif framework == "click":
                    # Find Click commands
                    for match in re.finditer(
                        r'@(?:cli|app|group)\.command\([\'"]?([^\'")\n]*)[\'"]?\)', content
                    ):
                        cmd_name = match.group(1) or "default"

                        func_match = re.search(
                            r"def\s+(\w+)", content[match.end() : match.end() + 200]
                        )
                        if func_match:
                            commands.append(
                                CLICommand(
                                    name=cmd_name or func_match.group(1).replace("_", "-"),
                                    description="",
                                    file=rel_path,
                                )
                            )

            except Exception as e:
                logger.warning(f"Could not analyze {py_file}: {e}")

        # Validate command names
        for cmd in commands:
            name_issues = self._validate_command_name(cmd.name)
            issues.extend(name_issues)

        return commands, issues

    async def _analyze_argparse(self) -> tuple[list[CLICommand], list[CLIIssue]]:
        """Analyze argparse CLI."""
        commands = []
        issues = []

        for py_file in self.project_path.glob("**/*.py"):
            if any(skip in str(py_file) for skip in ["venv", "node_modules"]):
                continue

            try:
                content = py_file.read_text(errors="ignore")
                rel_path = str(py_file.relative_to(self.project_path))

                if "ArgumentParser" not in content:
                    continue

                # Find parser creation
                parser_match = re.search(
                    r'ArgumentParser\([^)]*description=[\'"]([^\'"]+)[\'"]', content
                )
                description = parser_match.group(1) if parser_match else ""

                # Find subparsers
                subparsers = re.findall(r'add_parser\([\'"]([^\'"]+)[\'"]', content)

                # Find arguments
                arguments = []
                for match in re.finditer(r'add_argument\([\'"]([^\'"]+)[\'"]([^)]+)\)', content):
                    arg_name = match.group(1)
                    arg_opts = match.group(2)

                    help_match = re.search(r'help=[\'"]([^\'"]+)[\'"]', arg_opts)
                    arguments.append(
                        {"name": arg_name, "help": help_match.group(1) if help_match else ""}
                    )

                commands.append(
                    CLICommand(
                        name=py_file.stem,
                        description=description,
                        arguments=arguments,
                        subcommands=subparsers,
                        file=rel_path,
                    )
                )

                # Check for issues
                args_without_help = [a for a in arguments if not a.get("help")]
                if args_without_help:
                    issues.append(
                        CLIIssue(
                            severity="medium",
                            category="help",
                            command=py_file.stem,
                            description=f"{len(args_without_help)} arguments missing help text",
                            suggestion="Add help parameter to all arguments",
                        )
                    )

            except Exception as e:
                logger.warning(f"Could not analyze {py_file}: {e}")

        return commands, issues

    async def _analyze_node_cli(self, framework: str) -> tuple[list[CLICommand], list[CLIIssue]]:
        """Analyze Node.js CLI."""
        commands = []
        issues = []

        for file_path in self.project_path.glob("**/*.{js,ts}"):
            if any(skip in str(file_path) for skip in ["node_modules", "dist"]):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))

                if framework == "commander":
                    # Find commander commands
                    for match in re.finditer(
                        r'\.command\([\'"]([^\'"]+)[\'"](?:,\s*[\'"]([^\'"]+)[\'"])?\)', content
                    ):
                        cmd_name = match.group(1).split()[0]
                        description = match.group(2) or ""

                        commands.append(
                            CLICommand(name=cmd_name, description=description, file=rel_path)
                        )

                elif framework == "yargs":
                    # Find yargs commands
                    for match in re.finditer(
                        r'\.command\([\'"]([^\'"]+)[\'"](?:,\s*[\'"]([^\'"]+)[\'"])?\)', content
                    ):
                        cmd_name = match.group(1).split()[0]
                        description = match.group(2) or ""

                        commands.append(
                            CLICommand(name=cmd_name, description=description, file=rel_path)
                        )

            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")

        return commands, issues

    def _validate_command_name(self, name: str) -> list[CLIIssue]:
        """Validate command name against best practices."""
        issues = []

        # Check kebab-case
        if not re.match(self.NAMING_RULES["kebab-case"], name):
            issues.append(
                CLIIssue(
                    severity="low",
                    category="naming",
                    command=name,
                    description="Command name not in kebab-case",
                    suggestion="Use kebab-case for command names (e.g., my-command)",
                )
            )

        # Check for abbreviations
        for abbrev in self.NAMING_RULES["no-abbreviations"]:
            if abbrev in name.lower():
                issues.append(
                    CLIIssue(
                        severity="low",
                        category="naming",
                        command=name,
                        description=f"Command uses abbreviation '{abbrev}'",
                        suggestion="Use full words for better discoverability",
                    )
                )

        return issues

    def _calculate_score(self, issues: list, command_count: int) -> int:
        """Calculate CLI design score."""
        if command_count == 0:
            return 50

        score = 100
        penalties = {"critical": 15, "high": 8, "medium": 4, "low": 2}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(0, score)

    def _generate_recommendations(self, commands: list, issues: list, framework: str) -> list[str]:
        """Generate recommendations."""
        recommendations = []

        if not commands:
            recommendations.append(f"Set up CLI structure using {framework or 'Typer/Click'}")
            return recommendations

        # Check for help text
        no_help = [i for i in issues if i.category == "help"]
        if no_help:
            recommendations.append(f"Add help text to {len(no_help)} commands/arguments")

        # Check for global options
        if not any("--verbose" in str(c.options) for c in commands):
            recommendations.append("Consider adding --verbose/-v flag for debugging")

        if not any("--version" in str(c.options) for c in commands):
            recommendations.append("Add --version flag to show version info")

        return recommendations[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="CLI Designer Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = CLIDesigner(args.path)
    report = await agent.analyze()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
