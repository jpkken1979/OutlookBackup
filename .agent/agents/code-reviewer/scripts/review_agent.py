#!/usr/bin/env python3
"""
Code Reviewer Agent - Code Quality Specialist

Agente especializado en code review automatizado y mejora de calidad.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ReviewCategory(Enum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    READABILITY = "readability"
    TESTING = "testing"


class Severity(Enum):
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


@dataclass
class ReviewComment:
    """Comentario de code review."""

    line: int | None
    category: ReviewCategory
    severity: Severity
    message: str
    suggestion: str | None = None
    code_snippet: str | None = None


@dataclass
class ReviewResult:
    """Resultado completo del code review."""

    timestamp: datetime
    file_path: str
    comments: list[ReviewComment]
    strengths: list[str]
    summary: dict[ReviewCategory, str]  # pass/fail per category
    approved: bool


class CodeReviewerAgent:
    """Agente que realiza code review automatizado."""

    def __init__(self):
        self.memory_file = Path(__file__).parent.parent / "memory" / "review_history.json"
        self.memory = self._load_memory()

        # Patrones de problemas
        self.patterns = {
            # Security
            ("SECURITY", Severity.CRITICAL): [
                (r"eval\(", "Avoid eval() - code injection risk"),
                (r"exec\(", "Avoid exec() - code injection risk"),
                (r"os\.system\(", "Use subprocess with shell=False instead"),
                (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected"),
                (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key detected"),
            ],
            # Performance
            ("PERFORMANCE", Severity.MAJOR): [
                (r"for\s+\w+\s+in\s+range\(len\(", "Use enumerate() instead of range(len())"),
                (r'\+\s*=\s*["\']', "String concatenation in loop - use join()"),
                (r"\.read\(\)", "Reading entire file at once - consider streaming"),
            ],
            # Maintainability
            ("MAINTAINABILITY", Severity.MINOR): [
                (r"^.{120,}$", "Line too long (>120 chars)"),
                (r"#\s*TODO", "TODO comment found - track in issue tracker"),
                (r"#\s*FIXME", "FIXME comment found - needs attention"),
                (r"print\(", "Use logging instead of print"),
            ],
            # Readability
            ("READABILITY", Severity.INFO): [
                (r"\w{30,}", "Very long identifier - consider shorter name"),
                (r"[a-z]+ = lambda", "Consider using def for complex lambdas"),
            ],
        }

        logger.info("Code Reviewer Agent inicializado")

    def _load_memory(self) -> dict[str, Any]:
        if self.memory_file.exists():
            with open(self.memory_file) as f:
                return json.load(f)
        return {"reviews_performed": 0, "issues_found": 0, "history": []}

    def _save_memory(self) -> None:
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w") as f:
            json.dump(self.memory, f, indent=2, default=str)

    def review_code(self, code: str, file_path: str = "unknown") -> ReviewResult:
        """Realiza code review del código dado."""
        logger.info(f"Reviewing: {file_path}")

        comments = []
        lines = code.split("\n")

        # Analizar cada línea
        for line_num, line in enumerate(lines, 1):
            for (category_name, severity), patterns in self.patterns.items():
                category = ReviewCategory[category_name]
                for pattern, message in patterns:
                    if re.search(pattern, line, re.MULTILINE):
                        comments.append(
                            ReviewComment(
                                line=line_num,
                                category=category,
                                severity=severity,
                                message=message,
                                code_snippet=line.strip()[:80],
                            )
                        )

        # Detectar fortalezas
        strengths = self._detect_strengths(code)

        # Generar resumen por categoría
        summary = self._generate_summary(comments)

        # Determinar si aprobar
        blockers = [c for c in comments if c.severity == Severity.BLOCKER]
        criticals = [c for c in comments if c.severity == Severity.CRITICAL]
        approved = len(blockers) == 0 and len(criticals) <= 2

        result = ReviewResult(
            timestamp=datetime.now(),
            file_path=file_path,
            comments=comments,
            strengths=strengths,
            summary=summary,
            approved=approved,
        )

        self.memory["reviews_performed"] += 1
        self.memory["issues_found"] += len(comments)
        self._save_memory()

        return result

    def _detect_strengths(self, code: str) -> list[str]:
        """Detecta buenas prácticas en el código."""
        strengths = []

        if "def " in code and '"""' in code:
            strengths.append("Good: Functions have docstrings")

        if re.search(r":\s*(int|str|float|bool|List|Dict|Optional)", code):
            strengths.append("Good: Type hints are used")

        if "try:" in code and "except" in code:
            strengths.append("Good: Error handling present")

        if "import logging" in code or "from logging" in code:
            strengths.append("Good: Using logging module")

        if "@pytest" in code or "def test_" in code or "unittest" in code:
            strengths.append("Good: Tests are included")

        if not re.search(r'password|secret|key\s*=\s*["\'][^"\']+', code, re.I):
            strengths.append("Good: No hardcoded secrets detected")

        return strengths if strengths else ["No notable strengths detected"]

    def _generate_summary(self, comments: list[ReviewComment]) -> dict[ReviewCategory, str]:
        """Genera resumen por categoría."""
        summary = {}

        for category in ReviewCategory:
            category_comments = [c for c in comments if c.category == category]
            blockers = len(
                [
                    c
                    for c in category_comments
                    if c.severity in [Severity.BLOCKER, Severity.CRITICAL]
                ]
            )

            if blockers > 0:
                summary[category] = f"⚠️ {blockers} critical issues"
            elif len(category_comments) > 0:
                summary[category] = f"✅ {len(category_comments)} minor issues"
            else:
                summary[category] = "✅ Pass"

        return summary

    def result_to_markdown(self, result: ReviewResult) -> str:
        """Convierte resultado a Markdown."""
        md = f"# Code Review: {result.file_path}\n\n"
        md += f"**Date:** {result.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
        md += f"**Status:** {'✅ Approved' if result.approved else '❌ Changes Requested'}\n\n"

        md += "## Strengths\n\n"
        for strength in result.strengths:
            md += f"- {strength}\n"

        md += "\n## Summary\n\n"
        md += "| Category | Status |\n"
        md += "|----------|--------|\n"
        for category, status in result.summary.items():
            md += f"| {category.value.title()} | {status} |\n"

        if result.comments:
            md += "\n## Issues Found\n\n"

            # Agrupar por severidad
            for severity in Severity:
                severity_comments = [c for c in result.comments if c.severity == severity]
                if severity_comments:
                    severity_emoji = {
                        Severity.BLOCKER: "🔴",
                        Severity.CRITICAL: "🔴",
                        Severity.MAJOR: "🟠",
                        Severity.MINOR: "🟡",
                        Severity.INFO: "ℹ️",
                    }
                    md += f"### {severity_emoji.get(severity, '')} {severity.value.upper()}\n\n"
                    for c in severity_comments:
                        md += f"- **Line {c.line}**: {c.message}\n"
                        if c.code_snippet:
                            md += f"  ```\n  {c.code_snippet}\n  ```\n"

        return md


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Code Reviewer Agent")
    parser.add_argument("--file", "-f", help="File to review")
    parser.add_argument("--code", "-c", help="Code string to review")

    args = parser.parse_args()

    agent = CodeReviewerAgent()

    code = ""
    file_path = "stdin"

    if args.file:
        with open(args.file) as f:
            code = f.read()
        file_path = args.file
    elif args.code:
        code = args.code
    else:
        code = """
password = "DEMO_PASSWORD_PLACEHOLDER"  # nosec: demo bad practice
api_key = "DEMO_API_KEY_PLACEHOLDER"    # nosec: demo bad practice

def process_data(data):
    result = ""
    for item in range(len(data)):
        result += str(data[item])
        # eval() removed — was demo bad practice for pattern detection testing
    print(result)
    return result
"""

    result = agent.review_code(code, file_path)
    print(agent.result_to_markdown(result))


if __name__ == "__main__":
    main()
