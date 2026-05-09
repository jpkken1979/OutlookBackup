#!/usr/bin/env python3
"""
Code Archaeologist Agent - Legacy code analysis and reverse engineering.

Usage:
    python code_archaeologist.py <file_or_directory> [--depth shallow|deep] [--json]
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
class CodeArtifact:
    """Analysis of a code artifact."""

    file_path: str
    estimated_age: str
    language: str
    lines_of_code: int
    complexity_score: int
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    side_effects: list = field(default_factory=list)
    risk_factors: list = field(default_factory=list)
    patterns_detected: list = field(default_factory=list)
    refactoring_suggestions: list = field(default_factory=list)


@dataclass
class DependencyMap:
    """Dependency analysis."""

    file_path: str
    imports: list = field(default_factory=list)
    exports: list = field(default_factory=list)
    used_by: list = field(default_factory=list)
    uses: list = field(default_factory=list)
    circular_deps: list = field(default_factory=list)


@dataclass
class ArchaeologyReport:
    """Full archaeology report."""

    target: str
    timestamp: str
    artifacts: list = field(default_factory=list)
    dependency_map: dict = field(default_factory=dict)
    global_patterns: list = field(default_factory=list)
    refactoring_plan: list = field(default_factory=list)
    risk_assessment: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


class CodeArchaeologist:
    """Legacy code analysis agent."""

    AGE_PATTERNS = {
        "pre_es6": [
            r"var\s+\w+\s*=",
            r"function\s*\(",
            r"\.prototype\.",
            r"require\s*\(",
        ],
        "jquery_era": [
            r"\$\s*\(",
            r"jQuery",
            r"\.ajax\s*\(",
            r"\.click\s*\(",
        ],
        "react_class": [
            r"extends\s+React\.Component",
            r"extends\s+Component",
            r"this\.state\s*=",
            r"componentDidMount",
        ],
        "modern": [
            r"const\s+\w+\s*=",
            r"let\s+\w+\s*=",
            r"=>",
            r"async\s+",
            r"await\s+",
            r"import\s+",
        ],
        "python2": [
            r'print\s+["\']',
            r"xrange\s*\(",
            r"raw_input\s*\(",
            r"unicode\s*\(",
        ],
        "python3": [
            r"print\s*\(",
            r'f["\']',
            r"async\s+def",
            r"from\s+typing\s+import",
        ],
    }

    RISK_PATTERNS = {
        "global_state": [
            r"global\s+\w+",
            r"window\.\w+\s*=",
            r"globalThis\.",
        ],
        "magic_numbers": [
            r"[\s\(,=]\d{3,}[\s\),;]",
            r"0x[a-fA-F0-9]+",
        ],
        "deep_nesting": None,  # Calculated separately
        "god_function": None,  # Calculated by LOC
        "hardcoded_strings": [
            r'["\'][^"\']{50,}["\']',
        ],
        "tight_coupling": [
            r"new\s+\w+\s*\(",
            r"instanceof\s+",
        ],
        "no_error_handling": [
            r"catch\s*\(\s*\w*\s*\)\s*{\s*}",
            r"except:\s*pass",
        ],
    }

    REFACTORING_PATTERNS = {
        "extract_method": "Function exceeds 30 lines",
        "rename_variable": "Single letter variable names",
        "guard_clauses": "Nested if/else exceeds 3 levels",
        "remove_dead_code": "Unreachable code detected",
        "consolidate_duplicate": "Similar code blocks found",
        "introduce_constant": "Magic numbers detected",
    }

    def __init__(self, target: str, depth: str = "deep"):
        self.target = Path(target)
        self.depth = depth
        self.artifacts: list[CodeArtifact] = []
        self.dependency_graph: dict[str, DependencyMap] = {}

    def _estimate_age(self, content: str, extension: str) -> str:
        """Estimate code age based on patterns."""
        scores = dict.fromkeys(self.AGE_PATTERNS, 0)

        for era, patterns in self.AGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    scores[era] += 1

        # Determine dominant era
        if extension in [".py"]:
            if scores["python2"] > scores["python3"]:
                return "Python 2 era (pre-2020)"
            return "Python 3 (2020+)"

        if scores["jquery_era"] > 2:
            return "jQuery era (2010-2015)"
        if scores["pre_es6"] > scores["modern"]:
            return "Pre-ES6 (pre-2015)"
        if scores["react_class"] > 0 and scores["modern"] < 3:
            return "React Class era (2015-2018)"
        if scores["modern"] > 3:
            return "Modern (2019+)"

        return "Unknown era"

    def _calculate_complexity(self, content: str) -> int:
        """Calculate cyclomatic complexity estimate."""
        complexity = 1

        # Count decision points
        complexity += len(re.findall(r"\bif\b", content))
        complexity += len(re.findall(r"\belse\b", content))
        complexity += len(re.findall(r"\bfor\b", content))
        complexity += len(re.findall(r"\bwhile\b", content))
        complexity += len(re.findall(r"\bcase\b", content))
        complexity += len(re.findall(r"\bcatch\b", content))
        complexity += len(re.findall(r"\b(and|or|&&|\|\|)\b", content))

        return complexity

    def _find_inputs_outputs(self, content: str, language: str) -> tuple:
        """Find function inputs and outputs."""
        inputs = []
        outputs = []

        if language == "python":
            # Find function parameters
            funcs = re.findall(r"def\s+\w+\s*\(([^)]*)\)", content)
            for params in funcs:
                inputs.extend(
                    [p.strip().split(":")[0].strip() for p in params.split(",") if p.strip()]
                )

            # Find returns
            returns = re.findall(r"return\s+(.+)", content)
            outputs.extend([r.strip() for r in returns[:5]])  # Limit

        elif language in ["javascript", "typescript"]:
            # Find function parameters
            funcs = re.findall(r"function\s+\w*\s*\(([^)]*)\)", content)
            funcs += re.findall(r"\(([^)]*)\)\s*=>", content)
            for params in funcs:
                inputs.extend(
                    [p.strip().split(":")[0].strip() for p in params.split(",") if p.strip()]
                )

            # Find returns
            returns = re.findall(r"return\s+(.+?)[;\n]", content)
            outputs.extend([r.strip() for r in returns[:5]])

        return list(set(inputs))[:10], list(set(outputs))[:5]

    def _detect_side_effects(self, content: str) -> list[str]:
        """Detect potential side effects."""
        side_effects = []

        patterns = {
            "Global state modification": r"(global|window\.|globalThis\.)\w+\s*=",
            "File I/O": r"(open|read|write|fs\.)",
            "Network request": r"(fetch|axios|requests\.|http\.)",
            "DOM manipulation": r"(document\.|innerHTML|appendChild)",
            "Console output": r"(console\.|print\()",
            "Database operation": r"(cursor\.|execute|query)",
            "Environment access": r"(os\.environ|process\.env)",
        }

        for effect, pattern in patterns.items():
            if re.search(pattern, content):
                side_effects.append(effect)

        return side_effects

    def _detect_risk_factors(self, content: str, lines: list[str]) -> list[str]:
        """Detect risk factors in code."""
        risks = []

        for risk_name, patterns in self.RISK_PATTERNS.items():
            if patterns:
                for pattern in patterns:
                    if re.search(pattern, content):
                        risks.append(risk_name.replace("_", " ").title())
                        break

        # Check deep nesting
        max_indent = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                max_indent = max(max_indent, indent)

        if max_indent > 20:  # More than 5 levels (4 spaces each)
            risks.append("Deep Nesting (>5 levels)")

        # Check god function (>100 lines between function definitions)
        func_positions = [
            i for i, line in enumerate(lines) if re.match(r"\s*(def |function |const \w+ = )", line)
        ]
        for i in range(len(func_positions) - 1):
            if func_positions[i + 1] - func_positions[i] > 100:
                risks.append("God Function (>100 lines)")
                break

        return list(set(risks))

    def _suggest_refactoring(self, artifact: CodeArtifact) -> list[str]:
        """Suggest refactoring based on analysis."""
        suggestions = []

        if artifact.lines_of_code > 500:
            suggestions.append("Consider splitting into multiple modules")

        if artifact.complexity_score > 50:
            suggestions.append("High complexity - extract methods and simplify conditions")

        if "Deep Nesting" in artifact.risk_factors:
            suggestions.append("Use guard clauses to reduce nesting")

        if "God Function" in artifact.risk_factors:
            suggestions.append("Extract large functions into smaller, focused functions")

        if "Global State" in artifact.risk_factors:
            suggestions.append("Encapsulate global state in a class or module")

        if "Magic Numbers" in artifact.risk_factors:
            suggestions.append("Replace magic numbers with named constants")

        if artifact.estimated_age in ["Pre-ES6 (pre-2015)", "jQuery era (2010-2015)"]:
            suggestions.append("Modernize to ES6+ syntax (const, let, arrow functions)")

        if artifact.estimated_age == "React Class era (2015-2018)":
            suggestions.append("Convert class components to functional components with hooks")

        if artifact.estimated_age == "Python 2 era (pre-2020)":
            suggestions.append("Migrate to Python 3 syntax and features")

        return suggestions

    def analyze_file(self, file_path: Path) -> CodeArtifact | None:
        """Analyze a single file."""
        try:
            content = file_path.read_text(errors="ignore")
            lines = content.split("\n")

            # Determine language
            ext_to_lang = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".jsx": "javascript",
                ".tsx": "typescript",
                ".java": "java",
                ".go": "go",
                ".rb": "ruby",
            }
            language = ext_to_lang.get(file_path.suffix, "unknown")

            inputs, outputs = self._find_inputs_outputs(content, language)

            artifact = CodeArtifact(
                file_path=str(file_path),
                estimated_age=self._estimate_age(content, file_path.suffix),
                language=language,
                lines_of_code=len([l for l in lines if l.strip()]),
                complexity_score=self._calculate_complexity(content),
                inputs=inputs,
                outputs=outputs,
                side_effects=self._detect_side_effects(content),
                risk_factors=self._detect_risk_factors(content, lines),
                patterns_detected=[],
            )

            artifact.refactoring_suggestions = self._suggest_refactoring(artifact)

            return artifact

        except Exception as e:
            logger.debug(f"Error analyzing {file_path}: {e}")
            return None

    def analyze_dependencies(self, path: Path) -> dict[str, DependencyMap]:
        """Analyze import/export dependencies."""
        dep_map = {}

        # Find all imports
        imports_by_file = {}

        for file_path in path.rglob("*"):
            if file_path.suffix not in [".py", ".js", ".ts", ".jsx", ".tsx"]:
                continue
            if any(skip in str(file_path) for skip in ["node_modules", ".git", "__pycache__"]):
                continue

            try:
                content = file_path.read_text()
                imports = []

                # Python imports
                imports.extend(re.findall(r"from\s+(\S+)\s+import", content))
                imports.extend(re.findall(r"import\s+(\S+)", content))

                # JS/TS imports
                imports.extend(re.findall(r'import\s+.*\s+from\s+["\']([^"\']+)["\']', content))
                imports.extend(re.findall(r'require\s*\(["\']([^"\']+)["\']', content))

                imports_by_file[str(file_path)] = imports

                dep_map[str(file_path)] = DependencyMap(
                    file_path=str(file_path), imports=imports, exports=[], used_by=[], uses=imports
                )

            except Exception:
                pass

        # Build reverse dependency map
        for file_path, imports in imports_by_file.items():
            for imp in imports:
                for other_file in dep_map:
                    if imp in other_file or Path(imp).stem in other_file:
                        dep_map[other_file].used_by.append(file_path)

        return dep_map

    def generate_report(self) -> ArchaeologyReport:
        """Generate comprehensive archaeology report."""
        logger.info(f"Starting code archaeology on {self.target}")

        artifacts = []

        if self.target.is_file():
            artifact = self.analyze_file(self.target)
            if artifact:
                artifacts.append(artifact)
        else:
            for file_path in self.target.rglob("*"):
                if file_path.suffix not in [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"]:
                    continue
                if any(
                    skip in str(file_path)
                    for skip in ["node_modules", ".git", "__pycache__", "venv"]
                ):
                    continue

                artifact = self.analyze_file(file_path)
                if artifact:
                    artifacts.append(artifact)

        # Analyze dependencies if deep analysis
        dep_map = {}
        if self.depth == "deep" and self.target.is_dir():
            dep_map = self.analyze_dependencies(self.target)

        # Aggregate risk assessment
        all_risks = []
        total_complexity = 0
        total_loc = 0

        for artifact in artifacts:
            all_risks.extend(artifact.risk_factors)
            total_complexity += artifact.complexity_score
            total_loc += artifact.lines_of_code

        risk_counts = {}
        for risk in all_risks:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        # Generate global refactoring plan
        refactoring_plan = []
        if risk_counts.get("Deep Nesting (>5 levels)", 0) > 3:
            refactoring_plan.append("1. [HIGH] Reduce nesting across codebase - use guard clauses")
        if risk_counts.get("God Function (>100 lines)", 0) > 0:
            refactoring_plan.append("2. [HIGH] Break down large functions - apply Extract Method")
        if risk_counts.get("Global State", 0) > 0:
            refactoring_plan.append("3. [MEDIUM] Encapsulate global state")
        refactoring_plan.append("4. [ONGOING] Add characterization tests before refactoring")
        refactoring_plan.append("5. [ONGOING] Document decisions and patterns found")

        return ArchaeologyReport(
            target=str(self.target),
            timestamp=datetime.now().isoformat(),
            artifacts=[asdict(a) for a in artifacts],
            dependency_map={k: asdict(v) for k, v in dep_map.items()} if dep_map else {},
            global_patterns=list(set(all_risks)),
            refactoring_plan=refactoring_plan,
            risk_assessment={
                "total_risk_factors": len(all_risks),
                "by_type": risk_counts,
                "overall_risk": "HIGH"
                if len(all_risks) > 10
                else "MEDIUM"
                if len(all_risks) > 5
                else "LOW",
            },
            summary={
                "files_analyzed": len(artifacts),
                "total_loc": total_loc,
                "average_complexity": round(total_complexity / max(len(artifacts), 1), 1),
                "dominant_era": max(
                    {a.estimated_age for a in artifacts},
                    key=[a.estimated_age for a in artifacts].count,
                )
                if artifacts
                else "Unknown",
            },
        )


def format_report_markdown(report: ArchaeologyReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Code Archaeology Report",
        "",
        f"**Target:** {report.target}",
        f"**Date:** {report.timestamp}",
        "",
        "## Executive Summary",
        "",
        f"- **Files Analyzed:** {report.summary.get('files_analyzed', 0)}",
        f"- **Total Lines of Code:** {report.summary.get('total_loc', 0)}",
        f"- **Average Complexity:** {report.summary.get('average_complexity', 0)}",
        f"- **Dominant Era:** {report.summary.get('dominant_era', 'Unknown')}",
        f"- **Overall Risk:** {report.risk_assessment.get('overall_risk', 'Unknown')}",
        "",
        "## Risk Assessment",
        "",
    ]

    for risk_type, count in report.risk_assessment.get("by_type", {}).items():
        lines.append(f"- **{risk_type}:** {count} occurrences")

    lines.extend(["", "## Refactoring Plan", ""])
    for step in report.refactoring_plan:
        lines.append(f"- {step}")

    lines.extend(["", "## Artifact Analysis", ""])

    for artifact in report.artifacts[:10]:  # Limit to 10
        lines.extend(
            [
                f"### {artifact.get('file_path', '')}",
                "",
                f"**Era:** {artifact.get('estimated_age', '')} | **Language:** {artifact.get('language', '')}",
                f"**LOC:** {artifact.get('lines_of_code', 0)} | **Complexity:** {artifact.get('complexity_score', 0)}",
                "",
                "**Risk Factors:**",
                "",
            ]
        )
        for risk in artifact.get("risk_factors", []):
            lines.append(f"- {risk}")

        lines.extend(["", "**Suggestions:**", ""])
        for suggestion in artifact.get("refactoring_suggestions", []):
            lines.append(f"- {suggestion}")

        lines.extend(["", "---", ""])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Code Archaeologist Agent")
    parser.add_argument("target", nargs="?", default=".", help="File or directory to analyze")
    parser.add_argument(
        "--depth", choices=["shallow", "deep"], default="deep", help="Analysis depth"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    archaeologist = CodeArchaeologist(args.target, args.depth)
    report = archaeologist.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
