#!/usr/bin/env python3
"""
Accessibility (a11y) Agent - WCAG Compliance Checker

Capabilities:
- Check HTML for WCAG 2.1/2.2 compliance
- Validate ARIA usage
- Check color contrast
- Identify keyboard navigation issues
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
class A11yIssue:
    """An accessibility issue."""

    rule: str
    severity: str  # critical, serious, moderate, minor
    wcag: str
    element: str
    description: str
    fix: str
    location: str | None = None


@dataclass
class A11yReport:
    """Accessibility audit report."""

    file: str
    issues: list[A11yIssue] = field(default_factory=list)
    score: int = 100
    wcag_level: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "score": self.score,
            "wcag_level": self.wcag_level,
            "total_issues": len(self.issues),
            "by_severity": {
                "critical": sum(1 for i in self.issues if i.severity == "critical"),
                "serious": sum(1 for i in self.issues if i.severity == "serious"),
                "moderate": sum(1 for i in self.issues if i.severity == "moderate"),
                "minor": sum(1 for i in self.issues if i.severity == "minor"),
            },
            "issues": [i.__dict__ for i in self.issues],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Accessibility Report: {self.file}",
            "",
            f"**Score:** {self.score}/100",
            f"**WCAG Level:** {self.wcag_level}",
            f"**Total Issues:** {len(self.issues)}",
            "",
            "## Issues by Severity",
        ]

        for severity in ["critical", "serious", "moderate", "minor"]:
            severity_issues = [i for i in self.issues if i.severity == severity]
            if severity_issues:
                icon = {"critical": "🔴", "serious": "🟠", "moderate": "🟡", "minor": "🔵"}[
                    severity
                ]
                lines.append(f"### {icon} {severity.title()} ({len(severity_issues)})")
                for issue in severity_issues:
                    lines.extend(
                        [
                            f"#### {issue.rule}",
                            f"- **WCAG:** {issue.wcag}",
                            f"- **Element:** `{issue.element}`",
                            f"- **Issue:** {issue.description}",
                            f"- **Fix:** {issue.fix}",
                            "",
                        ]
                    )
        return "\n".join(lines)


class A11yAgent:
    """Accessibility checking agent."""

    # WCAG Rules
    RULES = {
        "img-alt": {
            "pattern": r"<img(?![^>]*alt=)[^>]*>",
            "severity": "critical",
            "wcag": "1.1.1 Non-text Content (Level A)",
            "description": "Image missing alt attribute",
            "fix": "Add alt attribute with descriptive text",
        },
        "empty-alt": {
            "pattern": r'<img[^>]*alt=""[^>]*(?!role="presentation")[^>]*>',
            "severity": "serious",
            "wcag": "1.1.1 Non-text Content (Level A)",
            "description": "Empty alt on non-decorative image",
            "fix": "Add descriptive alt text or role='presentation'",
        },
        "form-label": {
            "pattern": r'<input(?![^>]*aria-label)[^>]*(?!type="hidden"|type="submit"|type="button")[^>]*>(?!</label>)',
            "severity": "critical",
            "wcag": "1.3.1 Info and Relationships (Level A)",
            "description": "Form input missing label",
            "fix": "Add <label> element or aria-label attribute",
        },
        "button-name": {
            "pattern": r"<button[^>]*>\s*</button>",
            "severity": "critical",
            "wcag": "4.1.2 Name, Role, Value (Level A)",
            "description": "Button has no accessible name",
            "fix": "Add text content or aria-label",
        },
        "link-name": {
            "pattern": r"<a[^>]*>\s*</a>",
            "severity": "serious",
            "wcag": "2.4.4 Link Purpose (Level A)",
            "description": "Link has no text",
            "fix": "Add descriptive link text",
        },
        "html-lang": {
            "pattern": r"<html(?![^>]*lang=)",
            "severity": "serious",
            "wcag": "3.1.1 Language of Page (Level A)",
            "description": "HTML element missing lang attribute",
            "fix": "Add lang attribute (e.g., lang='en')",
        },
        "heading-order": {
            "pattern": r"<h1[^>]*>.*?</h1>.*?<h[3-6]",
            "severity": "moderate",
            "wcag": "1.3.1 Info and Relationships (Level A)",
            "description": "Heading levels skipped",
            "fix": "Use sequential heading levels (h1, h2, h3...)",
        },
        "color-contrast": {
            "pattern": r"color:\s*#([0-9a-f]{3}){1,2}\s*;[^}]*background",
            "severity": "serious",
            "wcag": "1.4.3 Contrast (Level AA)",
            "description": "Potential color contrast issue",
            "fix": "Ensure 4.5:1 contrast ratio for text",
        },
        "focus-visible": {
            "pattern": r"outline:\s*none|outline:\s*0",
            "severity": "serious",
            "wcag": "2.4.7 Focus Visible (Level AA)",
            "description": "Focus indicator removed",
            "fix": "Provide visible focus indicator",
        },
        "aria-hidden-focus": {
            "pattern": r'aria-hidden="true"[^>]*(?:tabindex="0"|<button|<a\s)',
            "severity": "critical",
            "wcag": "4.1.2 Name, Role, Value (Level A)",
            "description": "Focusable element inside aria-hidden",
            "fix": "Remove from tab order or aria-hidden",
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def audit(self, file_path: str) -> A11yReport:
        """Audit file for accessibility issues."""
        logger.info(f"Auditing {file_path}")

        full_path = self.project_path / file_path
        content = full_path.read_text(errors="ignore")

        issues = []

        for rule_id, rule in self.RULES.items():
            matches = re.finditer(rule["pattern"], content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                line_num = content[: match.start()].count("\n") + 1
                element = (
                    match.group(0)[:50] + "..." if len(match.group(0)) > 50 else match.group(0)
                )

                issues.append(
                    A11yIssue(
                        rule=rule_id,
                        severity=rule["severity"],
                        wcag=rule["wcag"],
                        element=element,
                        description=rule["description"],
                        fix=rule["fix"],
                        location=f"Line {line_num}",
                    )
                )

        # Calculate score
        score = self._calculate_score(issues)
        wcag_level = self._determine_wcag_level(issues)

        return A11yReport(file=file_path, issues=issues, score=score, wcag_level=wcag_level)

    async def audit_directory(self, patterns: list[str] = None) -> list[A11yReport]:
        """Audit all HTML/JSX files."""
        patterns = patterns or ["**/*.html", "**/*.jsx", "**/*.tsx"]
        reports = []

        for pattern in patterns:
            for file_path in self.project_path.glob(pattern):
                if not any(skip in str(file_path) for skip in ["node_modules", "dist", "build"]):
                    rel_path = str(file_path.relative_to(self.project_path))
                    try:
                        report = await self.audit(rel_path)
                        reports.append(report)
                    except Exception as e:
                        logger.warning(f"Could not audit {rel_path}: {e}")

        return reports

    def _calculate_score(self, issues: list[A11yIssue]) -> int:
        """Calculate accessibility score."""
        score = 100
        penalties = {"critical": 15, "serious": 8, "moderate": 4, "minor": 2}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(0, score)

    def _determine_wcag_level(self, issues: list[A11yIssue]) -> str:
        """Determine WCAG compliance level."""
        level_a_issues = [
            i for i in issues if "Level A" in i.wcag and i.severity in ["critical", "serious"]
        ]
        level_aa_issues = [
            i for i in issues if "Level AA" in i.wcag and i.severity in ["critical", "serious"]
        ]

        if not level_a_issues and not level_aa_issues:
            return "AA Compliant"
        elif not level_a_issues:
            return "A Compliant"
        else:
            return "Non-Compliant"


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="A11y Agent")
    parser.add_argument("file", nargs="?", help="File to audit")
    parser.add_argument("--all", action="store_true", help="Audit all HTML files")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = A11yAgent()

    if args.all:
        reports = await agent.audit_directory()
        for report in reports:
            print(f"\n{report.file}: {report.score}/100 ({len(report.issues)} issues)")
    elif args.file:
        report = await agent.audit(args.file)
        print(report.to_markdown() if not args.json else json.dumps(report.to_dict(), indent=2))
    else:
        print("Usage: python accessibility.py <file> or --all")


if __name__ == "__main__":
    asyncio.run(main())
