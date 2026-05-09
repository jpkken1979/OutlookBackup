#!/usr/bin/env python3
"""
Mobile Developer Agent - React Native and Flutter analysis.

Usage:
    python mobile_developer.py <project_path> [--framework auto|rn|flutter] [--json]
"""

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class MobileIssue:
    """Mobile development issue."""

    id: str
    category: str  # performance, security, ux, best-practice
    severity: str  # critical, high, medium, low
    title: str
    location: str
    description: str
    fix: str


@dataclass
class MobileReport:
    """Mobile project analysis report."""

    project_path: str
    framework: str
    timestamp: str
    issues: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class MobileDeveloper:
    """Mobile development analysis agent."""

    RN_ANTI_PATTERNS = {
        "scrollview_for_lists": {
            "pattern": r"<ScrollView[^>]*>[\s\S]*?{.*\.map\s*\(",
            "title": "ScrollView used for lists",
            "description": "Using ScrollView with .map() causes memory issues. Use FlatList instead.",
            "severity": "high",
            "fix": "Replace ScrollView + .map() with FlatList component",
        },
        "inline_render_item": {
            "pattern": r"renderItem\s*=\s*{\s*\(\s*{\s*item\s*}\s*\)\s*=>",
            "title": "Inline renderItem function",
            "description": "Inline renderItem causes re-renders. Use useCallback + memo.",
            "severity": "medium",
            "fix": "Extract renderItem to useCallback and wrap item component with React.memo",
        },
        "async_storage_tokens": {
            "pattern": r'AsyncStorage\.(setItem|getItem)\s*\([^)]*["\']?(token|password|secret|key)["\']?',
            "title": "Sensitive data in AsyncStorage",
            "description": "Tokens and secrets should use SecureStore/Keychain, not AsyncStorage.",
            "severity": "critical",
            "fix": "Use expo-secure-store or react-native-keychain for sensitive data",
        },
        "missing_key_extractor": {
            "pattern": r"<FlatList[^>]*(?!keyExtractor)",
            "title": "FlatList missing keyExtractor",
            "description": "FlatList without keyExtractor causes poor performance.",
            "severity": "medium",
            "fix": "Add keyExtractor prop: keyExtractor={(item) => item.id}",
        },
        "console_log_production": {
            "pattern": r"console\.(log|warn|error)\s*\(",
            "title": "Console statements in code",
            "description": "Console statements should be removed for production.",
            "severity": "low",
            "fix": "Remove console statements or use babel-plugin-transform-remove-console",
        },
        "native_driver_false": {
            "pattern": r"useNativeDriver\s*:\s*false",
            "title": "Animation not using native driver",
            "description": "Animations should use native driver for 60fps performance.",
            "severity": "medium",
            "fix": "Set useNativeDriver: true (note: not all animations support this)",
        },
    }

    FLUTTER_ANTI_PATTERNS = {
        "setState_in_build": {
            "pattern": r"@override\s+Widget\s+build[^}]*setState\s*\(",
            "title": "setState called during build",
            "description": "Calling setState during build causes infinite loops.",
            "severity": "critical",
            "fix": "Move setState to lifecycle methods or callbacks",
        },
        "list_view_without_builder": {
            "pattern": r"ListView\s*\(\s*children\s*:",
            "title": "ListView without builder",
            "description": "ListView with children loads all items. Use ListView.builder for large lists.",
            "severity": "high",
            "fix": "Use ListView.builder with itemBuilder for better performance",
        },
        "missing_const": {
            "pattern": r"(?<!const\s)(?:Text|Icon|SizedBox|Padding)\s*\(",
            "title": "Widget missing const constructor",
            "description": "Const constructors prevent unnecessary rebuilds.",
            "severity": "low",
            "fix": "Add const keyword before static widgets",
        },
    }

    def __init__(self, project_path: str, framework: str = "auto"):
        self.project_path = Path(project_path)
        self.framework = self._detect_framework() if framework == "auto" else framework
        self.issues: list[MobileIssue] = []
        self.issue_counter = 0

    def _detect_framework(self) -> str:
        """Detect mobile framework from project files."""
        if (self.project_path / "pubspec.yaml").exists():
            return "flutter"
        if (self.project_path / "package.json").exists():
            try:
                package = json.loads((self.project_path / "package.json").read_text())
                deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
                if "react-native" in deps:
                    return "react-native"
                if "expo" in deps:
                    return "expo"
            except Exception:
                pass
        return "unknown"

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"MOB-{self.issue_counter:03d}"

    def analyze_react_native(self) -> list[MobileIssue]:
        """Analyze React Native project."""
        issues = []

        extensions = {".js", ".jsx", ".ts", ".tsx"}

        for file_path in self.project_path.rglob("*"):
            if file_path.suffix not in extensions:
                continue
            if any(skip in str(file_path) for skip in ["node_modules", ".git", "android", "ios"]):
                continue

            try:
                content = file_path.read_text()

                for pattern_name, pattern_info in self.RN_ANTI_PATTERNS.items():
                    if re.search(pattern_info["pattern"], content, re.MULTILINE | re.DOTALL):
                        issues.append(
                            MobileIssue(
                                id=self._generate_issue_id(),
                                category="performance"
                                if "render" in pattern_name or "scroll" in pattern_name
                                else "security"
                                if "token" in pattern_name or "storage" in pattern_name
                                else "best-practice",
                                severity=pattern_info["severity"],
                                title=pattern_info["title"],
                                location=str(file_path.relative_to(self.project_path)),
                                description=pattern_info["description"],
                                fix=pattern_info["fix"],
                            )
                        )
            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        return issues

    def analyze_flutter(self) -> list[MobileIssue]:
        """Analyze Flutter project."""
        issues = []

        for file_path in self.project_path.rglob("*.dart"):
            if any(skip in str(file_path) for skip in [".dart_tool", "build", ".git"]):
                continue

            try:
                content = file_path.read_text()

                for pattern_name, pattern_info in self.FLUTTER_ANTI_PATTERNS.items():
                    if re.search(pattern_info["pattern"], content, re.MULTILINE):
                        issues.append(
                            MobileIssue(
                                id=self._generate_issue_id(),
                                category="performance"
                                if "build" in pattern_name or "list" in pattern_name
                                else "best-practice",
                                severity=pattern_info["severity"],
                                title=pattern_info["title"],
                                location=str(file_path.relative_to(self.project_path)),
                                description=pattern_info["description"],
                                fix=pattern_info["fix"],
                            )
                        )
            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        return issues

    def analyze_touch_targets(self) -> list[MobileIssue]:
        """Check for proper touch target sizes."""
        issues = []

        # Check React Native
        for file_path in self.project_path.rglob("*.tsx"):
            if "node_modules" in str(file_path):
                continue
            try:
                content = file_path.read_text()
                # Look for small touch targets
                small_targets = re.findall(
                    r"(TouchableOpacity|Pressable)[^>]*style={{[^}]*(?:width|height)\s*:\s*(\d+)",
                    content,
                )
                for match in small_targets:
                    size = int(match[1])
                    if size < 44:
                        issues.append(
                            MobileIssue(
                                id=self._generate_issue_id(),
                                category="ux",
                                severity="medium",
                                title=f"Touch target too small ({size}px)",
                                location=str(file_path.relative_to(self.project_path)),
                                description=f"Touch target is {size}px, minimum recommended is 44px (iOS) / 48px (Android).",
                                fix="Increase touch target to at least 44px, or add hitSlop prop",
                            )
                        )
            except Exception:
                pass

        return issues

    def get_metrics(self) -> dict:
        """Gather project metrics."""
        metrics = {
            "framework": self.framework,
            "files": {"js": 0, "ts": 0, "dart": 0, "native": 0},
            "dependencies": 0,
            "screens": 0,
            "components": 0,
        }

        # Count files
        for ext, key in [
            (".js", "js"),
            (".jsx", "js"),
            (".ts", "ts"),
            (".tsx", "ts"),
            (".dart", "dart"),
        ]:
            metrics["files"][key] += len(list(self.project_path.rglob(f"*{ext}")))

        # Count native files
        metrics["files"]["native"] = (
            len(list(self.project_path.rglob("*.swift")))
            + len(list(self.project_path.rglob("*.kt")))
            + len(list(self.project_path.rglob("*.java")))
        )

        # Count dependencies
        if (self.project_path / "package.json").exists():
            try:
                package = json.loads((self.project_path / "package.json").read_text())
                metrics["dependencies"] = len(package.get("dependencies", {}))
            except Exception:
                pass
        elif (self.project_path / "pubspec.yaml").exists():
            try:
                content = (self.project_path / "pubspec.yaml").read_text()
                metrics["dependencies"] = content.count(":")  # Rough estimate
            except Exception:
                pass

        return metrics

    def generate_report(self) -> MobileReport:
        """Generate comprehensive mobile analysis report."""
        logger.info(f"Analyzing mobile project: {self.project_path}")
        logger.info(f"Detected framework: {self.framework}")

        # Collect issues
        issues = []

        if self.framework in ["react-native", "expo"]:
            issues.extend(self.analyze_react_native())
        elif self.framework == "flutter":
            issues.extend(self.analyze_flutter())

        issues.extend(self.analyze_touch_targets())

        # Get metrics
        metrics = self.get_metrics()

        # Generate recommendations
        recommendations = []

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        if severity_counts["critical"] > 0:
            recommendations.append("Fix critical security issues immediately (token storage)")
        if severity_counts["high"] > 0:
            recommendations.append("Address high priority performance issues (FlatList usage)")

        if self.framework in ["react-native", "expo"]:
            recommendations.extend(
                [
                    "Use FlashList for better list performance",
                    "Implement React.memo for frequently rendered components",
                    "Use expo-secure-store for sensitive data",
                    "Test on low-end Android devices for performance",
                ]
            )
        elif self.framework == "flutter":
            recommendations.extend(
                [
                    "Use const constructors for static widgets",
                    "Implement ListView.builder for large lists",
                    "Profile with Flutter DevTools",
                    "Test on low-end devices",
                ]
            )

        return MobileReport(
            project_path=str(self.project_path),
            framework=self.framework,
            timestamp=datetime.now().isoformat(),
            issues=[asdict(i) for i in issues],
            metrics=metrics,
            recommendations=recommendations,
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "by_category": {
                    "performance": len([i for i in issues if i.category == "performance"]),
                    "security": len([i for i in issues if i.category == "security"]),
                    "ux": len([i for i in issues if i.category == "ux"]),
                    "best-practice": len([i for i in issues if i.category == "best-practice"]),
                },
            },
        )


def format_report_markdown(report: MobileReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Mobile Project Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Framework:** {report.framework}",
        f"**Date:** {report.timestamp}",
        "",
        "## Summary",
        "",
        f"**Total Issues:** {report.summary.get('total_issues', 0)}",
        "",
        "### By Severity",
    ]

    for severity, count in report.summary.get("by_severity", {}).items():
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                severity, "⚪"
            )
            lines.append(f"- {emoji} {severity.upper()}: {count}")

    lines.extend(["", "### By Category", ""])
    for category, count in report.summary.get("by_category", {}).items():
        if count > 0:
            lines.append(f"- **{category}**: {count}")

    lines.extend(["", "## Issues", ""])

    for issue in report.issues:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            issue.get("severity", ""), "⚪"
        )
        lines.extend(
            [
                f"### {severity_emoji} {issue.get('id', '')}: {issue.get('title', '')}",
                "",
                f"**Category:** {issue.get('category', '')} | **Severity:** {issue.get('severity', '')}",
                f"**Location:** `{issue.get('location', '')}`",
                "",
                f"{issue.get('description', '')}",
                "",
                f"**Fix:** {issue.get('fix', '')}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["## Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    lines.extend(["", "## Metrics", ""])
    for key, value in report.metrics.items():
        lines.append(f"- **{key}**: {value}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Mobile Developer Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument(
        "--framework",
        default="auto",
        choices=["auto", "rn", "flutter", "expo"],
        help="Mobile framework",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    framework_map = {"rn": "react-native", "flutter": "flutter", "expo": "expo", "auto": "auto"}

    analyzer = MobileDeveloper(args.project, framework_map.get(args.framework, "auto"))
    report = analyzer.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
