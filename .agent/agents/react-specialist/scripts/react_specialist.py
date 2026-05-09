#!/usr/bin/env python3
"""
React Specialist Agent - Advanced React Analysis

Capabilities:
- Analyze React patterns and hooks usage
- Check component architecture
- Validate state management
- Detect performance issues
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
class ReactComponent:
    """React component information."""

    name: str
    type: str  # functional, server, client
    file: str
    hooks: list[str] = field(default_factory=list)
    props: list[str] = field(default_factory=list)
    is_async: bool = False
    has_use_client: bool = False
    complexity: int = 0


@dataclass
class ReactIssue:
    """React-specific issue."""

    severity: str
    category: str  # hooks, performance, patterns, architecture
    file: str
    line: int | None
    description: str
    suggestion: str


@dataclass
class ReactReport:
    """React analysis report."""

    project_path: str
    react_version: str = "unknown"
    is_nextjs: bool = False
    components: list[ReactComponent] = field(default_factory=list)
    issues: list[ReactIssue] = field(default_factory=list)
    hooks_usage: dict = field(default_factory=dict)
    score: int = 100
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "react_version": self.react_version,
            "is_nextjs": self.is_nextjs,
            "components": [c.__dict__ for c in self.components],
            "issues": [i.__dict__ for i in self.issues],
            "hooks_usage": self.hooks_usage,
            "score": self.score,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# React Analysis Report",
            "",
            f"**Project:** {self.project_path}",
            f"**React Version:** {self.react_version}",
            f"**Next.js:** {'Yes' if self.is_nextjs else 'No'}",
            f"**Quality Score:** {self.score}/100",
            "",
            "## Summary",
            f"- **Components:** {len(self.components)}",
            f"- **Issues:** {len(self.issues)}",
            "",
        ]

        # Components by type
        if self.components:
            types = {}
            for c in self.components:
                types[c.type] = types.get(c.type, 0) + 1

            lines.extend(["## Components by Type", ""])
            for ctype, count in types.items():
                lines.append(f"- **{ctype}:** {count}")
            lines.append("")

        # Hooks usage
        if self.hooks_usage:
            lines.extend(["## Hooks Usage", ""])
            for hook, count in sorted(self.hooks_usage.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]:
                lines.append(f"- `{hook}`: {count}x")
            lines.append("")

        # Issues
        if self.issues:
            lines.extend(["## Issues", ""])
            for severity in ["critical", "high", "medium", "low"]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
                    lines.append(f"### {icon} {severity.title()} ({len(severity_issues)})")
                    for issue in severity_issues[:5]:
                        lines.extend(
                            [
                                f"- **{issue.category}** in `{issue.file}`",
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


class ReactSpecialist:
    """Advanced React analysis agent."""

    HOOK_RULES = {
        "rules-of-hooks": {
            "pattern": r"if\s*\([^)]+\)\s*\{[^}]*use[A-Z]\w+",
            "description": "Hook called conditionally",
            "suggestion": "Move hook call outside of conditional",
            "severity": "critical",
        },
        "missing-deps": {
            "pattern": r"useEffect\([^)]+,\s*\[\]\)[^;]*(?:props\.|state\.)",
            "description": "useEffect may have missing dependencies",
            "suggestion": "Add missing dependencies to dependency array",
            "severity": "high",
        },
        "state-in-loop": {
            "pattern": r"(?:for|while)\s*\([^)]+\)\s*\{[^}]*useState|\.map\([^)]+\)\s*=>[^}]*useState",
            "description": "useState called inside loop",
            "suggestion": "Move state declaration outside loop",
            "severity": "critical",
        },
    }

    PERFORMANCE_PATTERNS = {
        "missing-memo": {
            "pattern": r"export\s+(?:default\s+)?function\s+\w+.*\([^)]*\{[^}]+\}\s*\)",
            "description": "Component receives object props without memo",
            "suggestion": "Wrap component in React.memo() for performance",
        },
        "anonymous-callback": {
            "pattern": r"onClick=\{\s*\(\)\s*=>\s*\w+\(",
            "description": "Anonymous function in event handler",
            "suggestion": "Use useCallback or define handler outside JSX",
        },
        "inline-object": {
            "pattern": r'style=\{\{|className=\{[`\'"][^`\'"]+\+',
            "description": "Inline object/template literal creates new reference",
            "suggestion": "Use useMemo or define outside component",
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> ReactReport:
        """Analyze React project."""
        logger.info(f"Analyzing React in {self.project_path}")

        # Detect React version and Next.js
        react_version, is_nextjs = self._detect_react_setup()

        components = []
        issues = []
        hooks_usage = {}

        # Analyze React files
        for file_path in self.project_path.glob("**/*.{jsx,tsx}"):
            if any(skip in str(file_path) for skip in ["node_modules", "dist", ".next", "build"]):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))

                # Extract components
                file_components = self._extract_components(content, rel_path, is_nextjs)
                components.extend(file_components)

                # Track hooks usage
                for hook in re.findall(r"\b(use[A-Z]\w+)\(", content):
                    hooks_usage[hook] = hooks_usage.get(hook, 0) + 1

                # Check for issues
                file_issues = self._check_issues(content, rel_path)
                issues.extend(file_issues)

            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")

        # Calculate score
        score = self._calculate_score(issues, components)

        # Generate recommendations
        recommendations = self._generate_recommendations(components, issues, hooks_usage, is_nextjs)

        return ReactReport(
            project_path=str(self.project_path),
            react_version=react_version,
            is_nextjs=is_nextjs,
            components=components,
            issues=issues,
            hooks_usage=hooks_usage,
            score=score,
            recommendations=recommendations,
        )

    def _detect_react_setup(self) -> tuple[str, bool]:
        """Detect React version and if it's Next.js."""
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                react_version = deps.get("react", "unknown").lstrip("^~")
                is_nextjs = "next" in deps

                return react_version, is_nextjs
            except Exception:
                pass

        return "unknown", False

    def _extract_components(
        self, content: str, file_path: str, is_nextjs: bool
    ) -> list[ReactComponent]:
        """Extract React components from file."""
        components = []

        has_use_client = "'use client'" in content or '"use client"' in content

        # Find functional components
        patterns = [
            (r"export\s+(?:default\s+)?function\s+([A-Z]\w+)", "functional"),
            (
                r"export\s+(?:default\s+)?const\s+([A-Z]\w+)\s*(?::\s*\w+)?\s*=\s*(?:\([^)]*\)|[^=])\s*=>",
                "functional",
            ),
            (
                r"const\s+([A-Z]\w+)\s*(?::\s*\w+)?\s*=\s*(?:React\.)?(?:memo|forwardRef)\(",
                "memoized",
            ),
        ]

        for pattern, comp_type in patterns:
            for match in re.finditer(pattern, content):
                comp_name = match.group(1)

                # Determine actual type
                if has_use_client:
                    actual_type = "client"
                elif is_nextjs and not has_use_client and "/app/" in file_path:
                    actual_type = "server"
                else:
                    actual_type = comp_type

                # Extract hooks used in component
                comp_start = match.start()
                # Find component end (next function or end of file)
                comp_end = content.find("\nexport", comp_start + 1)
                if comp_end == -1:
                    comp_end = len(content)

                comp_body = content[comp_start:comp_end]
                hooks = list(set(re.findall(r"\b(use[A-Z]\w+)\(", comp_body)))

                # Check if async
                is_async = "async" in content[max(0, comp_start - 20) : comp_start]

                # Calculate complexity
                complexity = self._calculate_complexity(comp_body)

                components.append(
                    ReactComponent(
                        name=comp_name,
                        type=actual_type,
                        file=file_path,
                        hooks=hooks,
                        is_async=is_async,
                        has_use_client=has_use_client,
                        complexity=complexity,
                    )
                )

        return components

    def _calculate_complexity(self, code: str) -> int:
        """Calculate component complexity."""
        complexity = 1

        # Count branches
        complexity += len(re.findall(r"\bif\s*\(", code))
        complexity += len(re.findall(r"\bswitch\s*\(", code))
        complexity += len(re.findall(r"\?\s*[^:]+:", code))  # Ternary
        complexity += len(re.findall(r"&&\s*<", code))  # Conditional render
        complexity += len(re.findall(r"\.map\(", code))  # List render

        return complexity

    def _check_issues(self, content: str, file_path: str) -> list[ReactIssue]:
        """Check for React-specific issues."""
        issues = []

        # Check hook rules
        for _rule_name, rule in self.HOOK_RULES.items():
            for match in re.finditer(rule["pattern"], content):
                line = content[: match.start()].count("\n") + 1
                issues.append(
                    ReactIssue(
                        severity=rule["severity"],
                        category="hooks",
                        file=file_path,
                        line=line,
                        description=rule["description"],
                        suggestion=rule["suggestion"],
                    )
                )

        # Check performance patterns
        for _pattern_name, pattern in self.PERFORMANCE_PATTERNS.items():
            matches = list(re.finditer(pattern["pattern"], content))
            if len(matches) > 3:  # Only flag if excessive
                issues.append(
                    ReactIssue(
                        severity="medium",
                        category="performance",
                        file=file_path,
                        line=None,
                        description=f"{len(matches)}x: {pattern['description']}",
                        suggestion=pattern["suggestion"],
                    )
                )

        # Check for excessive state
        state_count = len(re.findall(r"\buseState\(", content))
        if state_count > 5:
            issues.append(
                ReactIssue(
                    severity="medium",
                    category="architecture",
                    file=file_path,
                    line=None,
                    description=f"Component has {state_count} useState calls",
                    suggestion="Consider using useReducer or extracting state to custom hook",
                )
            )

        # Check for excessive effects
        effect_count = len(re.findall(r"\buseEffect\(", content))
        if effect_count > 3:
            issues.append(
                ReactIssue(
                    severity="low",
                    category="architecture",
                    file=file_path,
                    line=None,
                    description=f"Component has {effect_count} useEffect calls",
                    suggestion="Consider consolidating effects or extracting to custom hooks",
                )
            )

        return issues

    def _calculate_score(self, issues: list, components: list) -> int:
        """Calculate React quality score."""
        if not components:
            return 50

        score = 100
        penalties = {"critical": 15, "high": 8, "medium": 4, "low": 2}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(0, score)

    def _generate_recommendations(
        self, components: list, issues: list, hooks: dict, is_nextjs: bool
    ) -> list[str]:
        """Generate React-specific recommendations."""
        recommendations = []

        # Hook issues
        hook_issues = [i for i in issues if i.category == "hooks"]
        if hook_issues:
            recommendations.append(f"Fix {len(hook_issues)} hooks rule violations")

        # Performance
        perf_issues = [i for i in issues if i.category == "performance"]
        if perf_issues:
            recommendations.append("Optimize re-renders with useMemo/useCallback")

        # Architecture
        complex_components = [c for c in components if c.complexity > 10]
        if complex_components:
            recommendations.append(f"Split {len(complex_components)} complex components")

        # Server components
        if is_nextjs:
            client_components = [c for c in components if c.has_use_client]
            if len(client_components) > len(components) * 0.7:
                recommendations.append("Leverage more Server Components for better performance")

        # Custom hooks
        if hooks.get("useState", 0) > 20 and not hooks.get("useReducer"):
            recommendations.append("Consider useReducer for complex state logic")

        return recommendations[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="React Specialist Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = ReactSpecialist(args.path)
    report = await agent.analyze()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
