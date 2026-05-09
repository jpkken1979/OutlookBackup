#!/usr/bin/env python3
"""
Refactor Agent - Code Refactoring Without Changing Behavior

Capabilities:
- Identify code smells
- Suggest refactoring patterns
- Extract methods/classes
- Rename with consistency
- Simplify complex code
"""

import ast
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CodeSmell:
    """A detected code smell."""

    name: str
    severity: str
    location: str
    description: str
    refactoring: str
    effort: str = "medium"


@dataclass
class RefactoringPlan:
    """Plan for refactoring code."""

    file: str
    smells: list[CodeSmell] = field(default_factory=list)
    total_issues: int = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "total_issues": len(self.smells),
            "smells": [s.__dict__ for s in self.smells],
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Refactoring Plan: {self.file}",
            "",
            f"**Issues Found:** {len(self.smells)}",
            "",
            "## Code Smells",
        ]
        for smell in self.smells:
            lines.extend(
                [
                    f"### {smell.name}",
                    f"- **Severity:** {smell.severity}",
                    f"- **Location:** {smell.location}",
                    f"- **Issue:** {smell.description}",
                    f"- **Refactoring:** {smell.refactoring}",
                    f"- **Effort:** {smell.effort}",
                    "",
                ]
            )
        if self.recommendations:
            lines.append("## Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
        return "\n".join(lines)


class RefactorAgent:
    """Refactoring Agent."""

    CODE_SMELLS = {
        "long_method": {
            "check": lambda lines: lines > 30,
            "severity": "major",
            "description": "Method is too long and does too much",
            "refactoring": "Extract Method - break into smaller, focused functions",
        },
        "long_parameter_list": {
            "check": lambda params: params > 4,
            "severity": "minor",
            "description": "Too many parameters make function hard to use",
            "refactoring": "Introduce Parameter Object or use keyword arguments",
        },
        "duplicate_code": {
            "check": lambda dup: dup > 0,
            "severity": "major",
            "description": "Duplicated code violates DRY principle",
            "refactoring": "Extract Method or Extract Class",
        },
        "god_class": {
            "check": lambda methods: methods > 15,
            "severity": "critical",
            "description": "Class has too many responsibilities",
            "refactoring": "Extract Class - split into focused classes",
        },
        "feature_envy": {
            "check": lambda ext_calls: ext_calls > 5,
            "severity": "minor",
            "description": "Method uses more features of other classes",
            "refactoring": "Move Method to the class it envies",
        },
        "magic_numbers": {
            "check": lambda count: count > 0,
            "severity": "minor",
            "description": "Unexplained numeric literals in code",
            "refactoring": "Replace Magic Number with Named Constant",
        },
        "nested_conditionals": {
            "check": lambda depth: depth > 3,
            "severity": "major",
            "description": "Deeply nested conditionals are hard to follow",
            "refactoring": "Replace Nested Conditional with Guard Clauses",
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self, file_path: str) -> RefactoringPlan:
        """Analyze file for refactoring opportunities."""
        logger.info(f"Analyzing {file_path} for refactoring")

        full_path = self.project_path / file_path
        content = full_path.read_text(errors="ignore")

        smells = []

        # Analyze with AST
        try:
            tree = ast.parse(content)
            smells.extend(self._analyze_ast(tree, file_path))
        except SyntaxError:
            logger.warning("Could not parse file")

        # Pattern-based analysis
        smells.extend(self._analyze_patterns(content, file_path))

        # Generate recommendations
        recommendations = self._generate_recommendations(smells)

        return RefactoringPlan(
            file=file_path, smells=smells, total_issues=len(smells), recommendations=recommendations
        )

    def _analyze_ast(self, tree: ast.AST, file_path: str) -> list[CodeSmell]:
        """Analyze AST for code smells."""
        smells = []

        for node in ast.walk(tree):
            # Long methods
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 0
                if lines > 30:
                    smells.append(
                        CodeSmell(
                            name="Long Method",
                            severity="major",
                            location=f"{file_path}:{node.lineno}",
                            description=f"Function '{node.name}' has {lines} lines",
                            refactoring="Extract smaller functions for each responsibility",
                        )
                    )

                # Long parameter list
                params = len(node.args.args)
                if params > 4:
                    smells.append(
                        CodeSmell(
                            name="Long Parameter List",
                            severity="minor",
                            location=f"{file_path}:{node.lineno}",
                            description=f"Function '{node.name}' has {params} parameters",
                            refactoring="Use a parameter object or dataclass",
                        )
                    )

            # God class
            if isinstance(node, ast.ClassDef):
                methods = sum(
                    1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                if methods > 15:
                    smells.append(
                        CodeSmell(
                            name="God Class",
                            severity="critical",
                            location=f"{file_path}:{node.lineno}",
                            description=f"Class '{node.name}' has {methods} methods",
                            refactoring="Split into multiple focused classes",
                            effort="high",
                        )
                    )

        return smells

    def _analyze_patterns(self, content: str, file_path: str) -> list[CodeSmell]:
        """Pattern-based smell detection."""
        smells = []
        lines = content.splitlines()

        # Magic numbers
        magic_pattern = r'(?<!["\'])\b(\d{2,})\b(?!["\'])'
        for i, line in enumerate(lines, 1):
            if not line.strip().startswith("#") and re.search(magic_pattern, line):
                if not re.search(r"(range|sleep|timeout|port|year|month|day)", line, re.I):
                    smells.append(
                        CodeSmell(
                            name="Magic Number",
                            severity="minor",
                            location=f"{file_path}:{i}",
                            description="Unexplained numeric literal",
                            refactoring="Extract to named constant",
                        )
                    )
                    break  # Only report first

        # Nested conditionals
        max_indent = 0
        for line in lines:
            if "if " in line or "elif " in line:
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent // 4)

        if max_indent > 3:
            smells.append(
                CodeSmell(
                    name="Deep Nesting",
                    severity="major",
                    location=file_path,
                    description=f"Code has {max_indent} levels of nesting",
                    refactoring="Use guard clauses and early returns",
                )
            )

        return smells

    def _generate_recommendations(self, smells: list[CodeSmell]) -> list[str]:
        """Generate prioritized recommendations."""
        recommendations = []

        critical = [s for s in smells if s.severity == "critical"]
        major = [s for s in smells if s.severity == "major"]

        if critical:
            recommendations.append(f"🔴 Address {len(critical)} critical issues first (God Class)")
        if major:
            recommendations.append(
                f"🟡 Then fix {len(major)} major issues (Long Method, Deep Nesting)"
            )

        recommendations.append("Run tests after each refactoring step")
        recommendations.append("Commit frequently to enable easy rollback")

        return recommendations


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Refactor Agent")
    parser.add_argument("file", help="File to analyze")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = RefactorAgent()
    plan = await agent.analyze(args.file)
    print(plan.to_markdown() if not args.json else json.dumps(plan.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
