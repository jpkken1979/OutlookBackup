#!/usr/bin/env python3
"""
Critic Agent - Decision Validation and Code Review

Capabilities:
- Validate architectural decisions
- Review code changes for quality
- Identify potential issues and risks
- Provide constructive feedback
- Challenge assumptions
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Severity:
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


@dataclass
class CritiqueItem:
    """A single critique point."""

    severity: str
    category: str
    title: str
    description: str
    location: str | None = None
    suggestion: str | None = None
    effort: str = "low"  # low, medium, high


@dataclass
class Critique:
    """Complete critique report."""

    subject: str
    verdict: str  # approved, needs_work, rejected
    score: int  # 0-100
    items: list[CritiqueItem] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "verdict": self.verdict,
            "score": self.score,
            "summary": self.summary,
            "strengths": self.strengths,
            "items": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "location": i.location,
                    "suggestion": i.suggestion,
                    "effort": i.effort,
                }
                for i in self.items
            ],
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        verdict_icon = (
            "✅" if self.verdict == "approved" else "⚠️" if self.verdict == "needs_work" else "❌"
        )

        lines = [
            "# Critique Report",
            "",
            f"**Subject:** {self.subject}",
            f"**Verdict:** {verdict_icon} {self.verdict.upper()}",
            f"**Score:** {self.score}/100",
            "",
            "## Summary",
            f"{self.summary}",
            "",
        ]

        if self.strengths:
            lines.append("## Strengths")
            for strength in self.strengths:
                lines.append(f"- ✓ {strength}")
            lines.append("")

        if self.items:
            lines.append("## Issues Found")
            lines.append("")

            by_severity = {}
            for item in self.items:
                if item.severity not in by_severity:
                    by_severity[item.severity] = []
                by_severity[item.severity].append(item)

            severity_order = [
                Severity.BLOCKER,
                Severity.CRITICAL,
                Severity.MAJOR,
                Severity.MINOR,
                Severity.INFO,
            ]
            severity_icons = {
                Severity.BLOCKER: "🛑",
                Severity.CRITICAL: "❌",
                Severity.MAJOR: "⚠️",
                Severity.MINOR: "📝",
                Severity.INFO: "ℹ️",
            }

            for severity in severity_order:
                if severity in by_severity:
                    lines.append(
                        f"### {severity_icons.get(severity, '')} {severity.title()} ({len(by_severity[severity])})"
                    )
                    for item in by_severity[severity]:
                        lines.append("")
                        lines.append(f"**{item.title}** [{item.category}]")
                        if item.location:
                            lines.append(f"- Location: `{item.location}`")
                        lines.append(f"- {item.description}")
                        if item.suggestion:
                            lines.append(f"- 💡 Suggestion: {item.suggestion}")
                    lines.append("")

        return "\n".join(lines)


class CriticAgent:
    """
    Critic Agent for validating decisions and reviewing code.
    """

    # Code quality rules
    CODE_RULES = {
        "no_print_statements": {
            "pattern": r"\bprint\s*\(",
            "severity": Severity.MINOR,
            "category": "code_quality",
            "title": "Print statement in code",
            "description": "Use logging instead of print statements",
            "suggestion": "Replace with logging.info() or logging.debug()",
        },
        "no_hardcoded_secrets": {
            "pattern": r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            "severity": Severity.CRITICAL,
            "category": "security",
            "title": "Hardcoded secret",
            "description": "Sensitive data should not be hardcoded",
            "suggestion": "Use environment variables or a secrets manager",
        },
        "no_todo_in_code": {
            "pattern": r"#\s*TODO",
            "severity": Severity.INFO,
            "category": "maintenance",
            "title": "TODO comment found",
            "description": "Unfinished work indicated by TODO comment",
            "suggestion": "Complete the TODO or create a ticket",
        },
        "no_bare_except": {
            "pattern": r"except\s*:",
            "severity": Severity.MAJOR,
            "category": "error_handling",
            "title": "Bare except clause",
            "description": "Catching all exceptions hides bugs",
            "suggestion": "Catch specific exceptions",
        },
        "no_mutable_default": {
            "pattern": r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})",
            "severity": Severity.MAJOR,
            "category": "bug_risk",
            "title": "Mutable default argument",
            "description": "Mutable default arguments are shared between calls",
            "suggestion": "Use None as default and initialize inside function",
        },
        "no_star_import": {
            "pattern": r"from\s+\S+\s+import\s+\*",
            "severity": Severity.MINOR,
            "category": "code_quality",
            "title": "Star import",
            "description": "Star imports pollute namespace and make code unclear",
            "suggestion": "Import specific names",
        },
        "function_too_long": {
            "pattern": None,  # Custom check
            "severity": Severity.MAJOR,
            "category": "maintainability",
            "title": "Function too long",
            "description": "Functions should be focused and concise",
            "suggestion": "Extract logic into smaller functions",
        },
        "missing_docstring": {
            "pattern": None,  # Custom check
            "severity": Severity.MINOR,
            "category": "documentation",
            "title": "Missing docstring",
            "description": "Public functions should have docstrings",
            "suggestion": "Add a docstring explaining purpose and parameters",
        },
    }

    # Architecture rules
    ARCHITECTURE_RULES = {
        "single_responsibility": {
            "description": "Each module/class should have one responsibility",
            "check": "file_size",
        },
        "dependency_inversion": {
            "description": "Depend on abstractions, not concretions",
            "check": "imports",
        },
        "separation_of_concerns": {
            "description": "Keep different concerns in separate modules",
            "check": "structure",
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def critique_code(
        self, code: str | None = None, file_path: str | None = None
    ) -> Critique:
        """
        Critique code for quality issues.

        Args:
            code: Code string to critique
            file_path: Path to file to critique

        Returns:
            Critique with findings
        """
        if file_path:
            full_path = self.project_path / file_path
            code = full_path.read_text(errors="ignore")
            subject = file_path
        else:
            subject = "provided code"

        logger.info(f"Critiquing: {subject}")

        items = []
        strengths = []

        # Apply pattern-based rules
        for _rule_name, rule in self.CODE_RULES.items():
            if rule["pattern"]:
                matches = list(re.finditer(rule["pattern"], code, re.IGNORECASE | re.MULTILINE))
                if matches:
                    for match in matches[:5]:  # Limit to 5 per rule
                        line_num = code[: match.start()].count("\n") + 1
                        items.append(
                            CritiqueItem(
                                severity=rule["severity"],
                                category=rule["category"],
                                title=rule["title"],
                                description=rule["description"],
                                location=f"Line {line_num}",
                                suggestion=rule["suggestion"],
                            )
                        )

        # Custom checks
        items.extend(self._check_function_length(code))
        items.extend(self._check_docstrings(code))
        items.extend(self._check_complexity(code))

        # Identify strengths
        strengths = self._identify_strengths(code)

        # Calculate score
        score = self._calculate_score(items)

        # Determine verdict
        verdict = self._determine_verdict(items, score)

        # Generate summary
        summary = self._generate_summary(items, strengths, score)

        return Critique(
            subject=subject,
            verdict=verdict,
            score=score,
            items=items,
            strengths=strengths,
            summary=summary,
        )

    async def critique_decision(
        self, decision: str, context: str | None = None, alternatives: list[str] | None = None
    ) -> Critique:
        """
        Critique an architectural or technical decision.

        Args:
            decision: The decision to critique
            context: Additional context
            alternatives: Alternative approaches considered

        Returns:
            Critique with analysis
        """
        logger.info(f"Critiquing decision: {decision[:50]}...")

        items = []
        strengths = []

        # Analyze decision
        analysis = self._analyze_decision(decision, context)

        items.extend(analysis["concerns"])
        strengths.extend(analysis["strengths"])

        # Check if alternatives were considered
        if not alternatives:
            items.append(
                CritiqueItem(
                    severity=Severity.MINOR,
                    category="decision_process",
                    title="No alternatives documented",
                    description="Good decisions should document considered alternatives",
                    suggestion="Document at least 2-3 alternatives and why they were rejected",
                )
            )

        # Calculate score
        score = self._calculate_score(items)
        verdict = self._determine_verdict(items, score)

        summary = (
            f"Decision analysis complete. Found {len(items)} concerns and {len(strengths)} strengths. "
            f"{'The decision appears sound.' if score >= 70 else 'The decision needs more consideration.'}"
        )

        return Critique(
            subject=f"Decision: {decision[:50]}...",
            verdict=verdict,
            score=score,
            items=items,
            strengths=strengths,
            summary=summary,
        )

    async def critique_pr(self, files_changed: list[str]) -> Critique:
        """Critique a pull request."""
        logger.info(f"Critiquing PR with {len(files_changed)} files")

        all_items = []
        all_strengths = []

        for file_path in files_changed:
            if file_path.endswith(".py"):
                try:
                    critique = await self.critique_code(file_path=file_path)
                    for item in critique.items:
                        item.location = f"{file_path}: {item.location}"
                    all_items.extend(critique.items)
                    all_strengths.extend(critique.strengths)
                except Exception as e:
                    logger.warning(f"Could not critique {file_path}: {e}")

        # Deduplicate strengths
        all_strengths = list(set(all_strengths))

        score = self._calculate_score(all_items)
        verdict = self._determine_verdict(all_items, score)

        summary = (
            f"PR review complete. Analyzed {len(files_changed)} files. "
            f"Found {len(all_items)} issues ({sum(1 for i in all_items if i.severity in [Severity.BLOCKER, Severity.CRITICAL])} critical)."
        )

        return Critique(
            subject=f"PR with {len(files_changed)} files",
            verdict=verdict,
            score=score,
            items=all_items,
            strengths=all_strengths[:10],
            summary=summary,
        )

    def _check_function_length(self, code: str) -> list[CritiqueItem]:
        """Check for overly long functions."""
        items = []
        func_pattern = r"^(?:async\s+)?def\s+(\w+)"

        lines = code.splitlines()
        in_function = False
        func_name = ""
        func_start = 0

        for i, line in enumerate(lines):
            match = re.match(func_pattern, line)
            if match:
                if in_function and (i - func_start) > 50:
                    items.append(
                        CritiqueItem(
                            severity=Severity.MAJOR,
                            category="maintainability",
                            title=f"Function '{func_name}' is too long",
                            description=f"Function has {i - func_start} lines (recommended: <50)",
                            location=f"Line {func_start + 1}",
                            suggestion="Extract logic into smaller, focused functions",
                            effort="medium",
                        )
                    )

                func_name = match.group(1)
                func_start = i
                len(line) - len(line.lstrip())
                in_function = True

        return items

    def _check_docstrings(self, code: str) -> list[CritiqueItem]:
        """Check for missing docstrings."""
        items = []

        # Check for public functions without docstrings
        func_pattern = r'^def\s+([a-z]\w*)\s*\([^)]*\):\s*\n(?!\s*["\'])'

        for match in re.finditer(func_pattern, code, re.MULTILINE):
            func_name = match.group(1)
            if not func_name.startswith("_"):
                line_num = code[: match.start()].count("\n") + 1
                items.append(
                    CritiqueItem(
                        severity=Severity.MINOR,
                        category="documentation",
                        title=f"Function '{func_name}' missing docstring",
                        description="Public functions should be documented",
                        location=f"Line {line_num}",
                        suggestion="Add a docstring explaining purpose, args, and return value",
                    )
                )

        return items[:5]  # Limit

    def _check_complexity(self, code: str) -> list[CritiqueItem]:
        """Check for high complexity indicators."""
        items = []

        # Check nesting depth
        max_indent = 0
        for line in code.splitlines():
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent // 4)

        if max_indent > 5:
            items.append(
                CritiqueItem(
                    severity=Severity.MAJOR,
                    category="complexity",
                    title="Deep nesting detected",
                    description=f"Code has {max_indent} levels of nesting",
                    suggestion="Refactor to reduce nesting using early returns or extracted functions",
                    effort="medium",
                )
            )

        # Check for too many conditions
        conditions = len(re.findall(r"\b(if|elif|and|or)\b", code))
        lines = len(code.splitlines())
        if lines > 0 and conditions / lines > 0.15:
            items.append(
                CritiqueItem(
                    severity=Severity.MINOR,
                    category="complexity",
                    title="High conditional density",
                    description="Code has many conditional statements",
                    suggestion="Consider using polymorphism or strategy pattern",
                    effort="high",
                )
            )

        return items

    def _identify_strengths(self, code: str) -> list[str]:
        """Identify positive aspects of the code."""
        strengths = []

        # Type hints
        if re.search(r"def\s+\w+\s*\([^)]*:\s*\w+", code):
            strengths.append("Uses type hints for better code clarity")

        # Docstrings present
        if re.search(r'"""[\s\S]*?"""', code):
            strengths.append("Contains documentation strings")

        # Uses logging
        if "logging" in code or "logger" in code:
            strengths.append("Uses proper logging")

        # Uses dataclasses
        if "@dataclass" in code:
            strengths.append("Uses dataclasses for clean data structures")

        # Uses async
        if "async def" in code:
            strengths.append("Uses async/await for concurrent operations")

        # Has tests
        if "def test_" in code or "pytest" in code:
            strengths.append("Includes test code")

        # Error handling
        if "try:" in code and "except" in code:
            strengths.append("Implements error handling")

        return strengths

    def _analyze_decision(self, decision: str, context: str | None) -> dict:
        """Analyze a technical decision."""
        concerns = []
        strengths = []

        decision_lower = decision.lower()

        # Check for good practices
        if any(word in decision_lower for word in ["because", "reason", "due to"]):
            strengths.append("Decision includes rationale")

        if any(word in decision_lower for word in ["tradeoff", "trade-off", "considered"]):
            strengths.append("Acknowledges tradeoffs")

        # Check for potential issues
        if "quick" in decision_lower or "fast" in decision_lower:
            concerns.append(
                CritiqueItem(
                    severity=Severity.MINOR,
                    category="sustainability",
                    title="Speed-focused decision",
                    description="Decisions prioritizing speed may create technical debt",
                    suggestion="Ensure the solution is maintainable long-term",
                )
            )

        if "temporary" in decision_lower or "workaround" in decision_lower:
            concerns.append(
                CritiqueItem(
                    severity=Severity.MAJOR,
                    category="technical_debt",
                    title="Temporary solution",
                    description="Temporary solutions often become permanent",
                    suggestion="Document when this will be replaced with proper solution",
                )
            )

        if not context:
            concerns.append(
                CritiqueItem(
                    severity=Severity.MINOR,
                    category="documentation",
                    title="Missing context",
                    description="Decision lacks documented context",
                    suggestion="Document the problem being solved and constraints",
                )
            )

        return {"concerns": concerns, "strengths": strengths}

    def _calculate_score(self, items: list[CritiqueItem]) -> int:
        """Calculate quality score."""
        score = 100

        severity_penalties = {
            Severity.BLOCKER: 25,
            Severity.CRITICAL: 15,
            Severity.MAJOR: 8,
            Severity.MINOR: 3,
            Severity.INFO: 1,
        }

        for item in items:
            score -= severity_penalties.get(item.severity, 0)

        return max(0, min(100, score))

    def _determine_verdict(self, items: list[CritiqueItem], score: int) -> str:
        """Determine overall verdict."""
        blockers = sum(1 for i in items if i.severity == Severity.BLOCKER)
        criticals = sum(1 for i in items if i.severity == Severity.CRITICAL)

        if blockers > 0:
            return "rejected"
        elif criticals > 2 or score < 50:
            return "needs_work"
        elif score >= 70:
            return "approved"
        else:
            return "needs_work"

    def _generate_summary(self, items: list[CritiqueItem], strengths: list[str], score: int) -> str:
        """Generate critique summary."""
        blockers = sum(1 for i in items if i.severity == Severity.BLOCKER)
        criticals = sum(1 for i in items if i.severity == Severity.CRITICAL)
        majors = sum(1 for i in items if i.severity == Severity.MAJOR)

        parts = [f"Quality score: {score}/100."]

        if blockers:
            parts.append(f"{blockers} blocking issues must be fixed.")
        if criticals:
            parts.append(f"{criticals} critical issues require attention.")
        if majors:
            parts.append(f"{majors} major issues should be addressed.")
        if strengths:
            parts.append(f"Identified {len(strengths)} positive aspects.")

        return " ".join(parts)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Critic Agent")
    parser.add_argument("--file", "-f", help="File to critique")
    parser.add_argument("--decision", "-d", help="Decision to critique")
    parser.add_argument("--pr", nargs="+", help="PR files to critique")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    agent = CriticAgent()

    if args.file:
        critique = await agent.critique_code(file_path=args.file)
    elif args.decision:
        critique = await agent.critique_decision(args.decision)
    elif args.pr:
        critique = await agent.critique_pr(args.pr)
    else:
        # Demo with sample code
        sample_code = """
def process_data(data=[]):
    print("Processing...")
    password = "DEMO_PASSWORD_PLACEHOLDER"  # nosec: demo bad practice
    try:
        for item in data:
            if item:
                if item.valid:
                    if item.active:
                        result = do_something(item)
    except:
        pass
    return result
"""
        critique = await agent.critique_code(code=sample_code)

    if args.json:
        print(json.dumps(critique.to_dict(), indent=2))
    else:
        print(critique.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
