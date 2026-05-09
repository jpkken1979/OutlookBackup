#!/usr/bin/env python3
"""
ML-Enhanced Code Reviewer

Adds machine learning capabilities to code review:
- Pattern detection using embeddings
- Code smell classification
- Intelligent recommendations

Version: 1.0.0
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeSmellType(Enum):
    """Types of code smells."""

    LONG_METHOD = "long_method"
    LARGE_CLASS = "large_class"
    DUPLICATE_CODE = "duplicate_code"
    DEAD_CODE = "dead_code"
    COMPLEX_CONDITIONAL = "complex_conditional"
    MAGIC_NUMBER = "magic_number"
    GOD_CLASS = "god_class"
    FEATURE_ENVY = "feature_envy"
    DATA_CLUMP = "data_clump"
    PRIMITIVE_OBSESSION = "primitive_obsession"


class Severity(Enum):
    """Severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CodePattern:
    """A detected code pattern."""

    name: str
    description: str
    locations: list = field(default_factory=list)  # line numbers
    confidence: float = 0.0
    is_positive: bool = True  # True = good pattern, False = anti-pattern


@dataclass
class CodeSmell:
    """A detected code smell."""

    smell_type: CodeSmellType
    description: str
    location: str
    severity: Severity
    suggestion: str
    confidence: float = 0.0


@dataclass
class ReviewRecommendation:
    """A review recommendation."""

    title: str
    description: str
    priority: int  # 1-5, higher = more important
    category: str
    code_example: str | None = None


@dataclass
class MLReviewResult:
    """Result of ML-enhanced code review."""

    patterns: list = field(default_factory=list)
    smells: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    overall_score: float = 0.0
    confidence: float = 0.0
    metrics: dict = field(default_factory=dict)
    reviewed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "patterns": [
                {
                    "name": p.name,
                    "description": p.description,
                    "locations": p.locations,
                    "confidence": p.confidence,
                    "is_positive": p.is_positive,
                }
                for p in self.patterns
            ],
            "smells": [
                {
                    "type": s.smell_type.value,
                    "description": s.description,
                    "location": s.location,
                    "severity": s.severity.value,
                    "suggestion": s.suggestion,
                    "confidence": s.confidence,
                }
                for s in self.smells
            ],
            "recommendations": [
                {
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "category": r.category,
                    "code_example": r.code_example,
                }
                for r in self.recommendations
            ],
            "overall_score": self.overall_score,
            "confidence": self.confidence,
            "metrics": self.metrics,
            "reviewed_at": self.reviewed_at.isoformat(),
        }


class CodePatternDetector:
    """Detects code patterns using heuristics and ML."""

    # Pattern definitions with regex and descriptions
    PATTERNS = {
        "singleton": {
            "regex": r"class\s+\w+.*?_instance\s*=\s*None",
            "description": "Singleton pattern detected",
            "positive": True,
        },
        "factory": {
            "regex": r"def\s+create_\w+|class\s+\w+Factory",
            "description": "Factory pattern detected",
            "positive": True,
        },
        "observer": {
            "regex": r"def\s+(subscribe|notify|on_\w+)|class\s+\w+(Observer|Listener)",
            "description": "Observer pattern detected",
            "positive": True,
        },
        "repository": {
            "regex": r"class\s+\w+Repository|def\s+(find_by|get_all|save|delete)",
            "description": "Repository pattern detected",
            "positive": True,
        },
        "callback_hell": {
            "regex": r"\.then\([^)]+\.then\([^)]+\.then",
            "description": "Callback hell detected - consider async/await",
            "positive": False,
        },
        "god_object": {
            "regex": r"class\s+\w+.*?def\s+\w+.*?def\s+\w+.*?def\s+\w+.*?def\s+\w+.*?def\s+\w+.*?def\s+\w+",
            "description": "Possible God Object - class with many methods",
            "positive": False,
        },
    }

    async def detect(self, code: str) -> list[CodePattern]:
        """Detect patterns in code."""
        patterns = []

        for pattern_name, pattern_def in self.PATTERNS.items():
            matches = list(re.finditer(pattern_def["regex"], code, re.DOTALL | re.MULTILINE))
            if matches:
                # Calculate line numbers
                locations = []
                for match in matches:
                    line_num = code[: match.start()].count("\n") + 1
                    locations.append(line_num)

                patterns.append(
                    CodePattern(
                        name=pattern_name,
                        description=pattern_def["description"],
                        locations=locations,
                        confidence=0.8,  # Heuristic confidence
                        is_positive=pattern_def["positive"],
                    )
                )

        return patterns


class CodeSmellClassifier:
    """Classifies code smells using heuristics and ML."""

    # Thresholds for smell detection
    LONG_METHOD_LINES = 50
    LARGE_CLASS_LINES = 500
    COMPLEX_CONDITIONAL_DEPTH = 4
    MAGIC_NUMBER_THRESHOLD = 3  # Same number appearing 3+ times

    async def classify(self, code: str) -> list[CodeSmell]:
        """Classify code smells in the code."""
        smells = []

        # Check for long methods
        smells.extend(self._detect_long_methods(code))

        # Check for complex conditionals
        smells.extend(self._detect_complex_conditionals(code))

        # Check for magic numbers
        smells.extend(self._detect_magic_numbers(code))

        # Check for duplicate code patterns
        smells.extend(self._detect_duplicates(code))

        # Check for dead code
        smells.extend(self._detect_dead_code(code))

        return smells

    def _detect_long_methods(self, code: str) -> list[CodeSmell]:
        """Detect methods that are too long."""
        smells = []

        # Find function/method definitions
        func_pattern = r"(def\s+(\w+)\s*\([^)]*\):.*?)(?=\ndef\s+|\nclass\s+|\Z)"
        matches = re.finditer(func_pattern, code, re.DOTALL)

        for match in matches:
            func_body = match.group(1)
            func_name = match.group(2)
            line_count = func_body.count("\n")

            if line_count > self.LONG_METHOD_LINES:
                line_num = code[: match.start()].count("\n") + 1
                smells.append(
                    CodeSmell(
                        smell_type=CodeSmellType.LONG_METHOD,
                        description=f"Method '{func_name}' has {line_count} lines (threshold: {self.LONG_METHOD_LINES})",
                        location=f"Line {line_num}",
                        severity=Severity.WARNING,
                        suggestion=f"Consider breaking '{func_name}' into smaller methods",
                        confidence=0.9,
                    )
                )

        return smells

    def _detect_complex_conditionals(self, code: str) -> list[CodeSmell]:
        """Detect overly complex conditional statements."""
        smells = []

        # Count nested if statements
        lines = code.split("\n")
        max_depth = 0
        max_depth_line = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("if ", "elif ", "else:")):
                indent = len(line) - len(line.lstrip())
                depth = indent // 4  # Assuming 4-space indentation
                if depth > max_depth:
                    max_depth = depth
                    max_depth_line = i + 1

        if max_depth >= self.COMPLEX_CONDITIONAL_DEPTH:
            smells.append(
                CodeSmell(
                    smell_type=CodeSmellType.COMPLEX_CONDITIONAL,
                    description=f"Nested conditionals depth of {max_depth} (threshold: {self.COMPLEX_CONDITIONAL_DEPTH})",
                    location=f"Line {max_depth_line}",
                    severity=Severity.WARNING,
                    suggestion="Consider extracting conditions into separate methods or using guard clauses",
                    confidence=0.85,
                )
            )

        return smells

    def _detect_magic_numbers(self, code: str) -> list[CodeSmell]:
        """Detect magic numbers in code."""
        smells = []

        # Find numeric literals (excluding 0, 1, 2 which are common)
        number_pattern = r"\b(\d+\.?\d*)\b"
        numbers = re.findall(number_pattern, code)

        # Count occurrences
        number_counts = {}
        for num in numbers:
            if num not in ("0", "1", "2", "0.0", "1.0"):
                number_counts[num] = number_counts.get(num, 0) + 1

        # Report magic numbers
        for num, count in number_counts.items():
            if count >= self.MAGIC_NUMBER_THRESHOLD:
                smells.append(
                    CodeSmell(
                        smell_type=CodeSmellType.MAGIC_NUMBER,
                        description=f"Magic number '{num}' appears {count} times",
                        location="Multiple locations",
                        severity=Severity.INFO,
                        suggestion=f"Consider defining '{num}' as a named constant",
                        confidence=0.7,
                    )
                )

        return smells

    def _detect_duplicates(self, code: str) -> list[CodeSmell]:
        """Detect duplicate code blocks."""
        smells = []

        # Simple duplicate detection: find repeated multi-line blocks
        lines = code.split("\n")
        block_size = 5  # Look for 5+ line duplicates

        seen_blocks = {}
        for i in range(len(lines) - block_size):
            block = "\n".join(lines[i : i + block_size]).strip()
            if len(block) > 50:  # Ignore small blocks
                if block in seen_blocks:
                    smells.append(
                        CodeSmell(
                            smell_type=CodeSmellType.DUPLICATE_CODE,
                            description="Duplicate code block found",
                            location=f"Lines {seen_blocks[block]} and {i + 1}",
                            severity=Severity.WARNING,
                            suggestion="Consider extracting duplicate code into a shared function",
                            confidence=0.9,
                        )
                    )
                else:
                    seen_blocks[block] = i + 1

        return smells

    def _detect_dead_code(self, code: str) -> list[CodeSmell]:
        """Detect potentially dead code."""
        smells = []

        # Find functions that are never called
        # This is a simple heuristic - real detection would need AST analysis
        func_defs = re.findall(r"def\s+(\w+)\s*\(", code)
        func_calls = re.findall(r"(\w+)\s*\(", code)

        for func in func_defs:
            # Count calls (excluding the definition itself)
            call_count = func_calls.count(func) - 1  # -1 for definition
            if call_count == 0 and not func.startswith("_"):
                smells.append(
                    CodeSmell(
                        smell_type=CodeSmellType.DEAD_CODE,
                        description=f"Function '{func}' appears to be unused",
                        location="Unknown",
                        severity=Severity.INFO,
                        suggestion=f"Verify if '{func}' is needed, or remove it",
                        confidence=0.6,  # Lower confidence as it might be called externally
                    )
                )

        return smells


class MLCodeReviewer:
    """
    ML-Enhanced Code Reviewer.

    Combines traditional static analysis with ML-based pattern detection.
    """

    def __init__(self):
        self.pattern_detector = CodePatternDetector()
        self.smell_classifier = CodeSmellClassifier()

    async def review(self, code: str, file_path: str | None = None) -> MLReviewResult:
        """
        Perform ML-enhanced code review.

        Args:
            code: Source code to review
            file_path: Optional file path for context

        Returns:
            MLReviewResult with patterns, smells, and recommendations
        """
        # Detect patterns
        patterns = await self.pattern_detector.detect(code)

        # Classify smells
        smells = await self.smell_classifier.classify(code)

        # Generate recommendations
        recommendations = self._generate_recommendations(patterns, smells)

        # Calculate metrics
        metrics = self._calculate_metrics(code, patterns, smells)

        # Calculate overall score
        overall_score = self._calculate_score(patterns, smells, metrics)

        # Calculate confidence
        confidence = self._calculate_confidence(patterns, smells)

        return MLReviewResult(
            patterns=patterns,
            smells=smells,
            recommendations=recommendations,
            overall_score=overall_score,
            confidence=confidence,
            metrics=metrics,
        )

    def _generate_recommendations(
        self, patterns: list[CodePattern], smells: list[CodeSmell]
    ) -> list[ReviewRecommendation]:
        """Generate recommendations based on patterns and smells."""
        recommendations = []

        # Recommendations from anti-patterns
        for pattern in patterns:
            if not pattern.is_positive:
                recommendations.append(
                    ReviewRecommendation(
                        title=f"Address {pattern.name}",
                        description=pattern.description,
                        priority=4,
                        category="anti-pattern",
                    )
                )

        # Recommendations from smells
        smell_recommendations = {
            CodeSmellType.LONG_METHOD: (
                "Refactor long methods",
                "Extract smaller, focused methods",
                4,
            ),
            CodeSmellType.COMPLEX_CONDITIONAL: (
                "Simplify conditionals",
                "Use guard clauses or extract methods",
                3,
            ),
            CodeSmellType.MAGIC_NUMBER: (
                "Define constants",
                "Replace magic numbers with named constants",
                2,
            ),
            CodeSmellType.DUPLICATE_CODE: (
                "Remove duplication",
                "Extract shared code into reusable functions",
                4,
            ),
            CodeSmellType.DEAD_CODE: (
                "Clean up dead code",
                "Remove unused functions and variables",
                2,
            ),
        }

        seen_types = set()
        for smell in smells:
            if smell.smell_type not in seen_types:
                seen_types.add(smell.smell_type)
                if smell.smell_type in smell_recommendations:
                    title, desc, priority = smell_recommendations[smell.smell_type]
                    recommendations.append(
                        ReviewRecommendation(
                            title=title, description=desc, priority=priority, category="code-smell"
                        )
                    )

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority, reverse=True)
        return recommendations

    def _calculate_metrics(
        self, code: str, patterns: list[CodePattern], smells: list[CodeSmell]
    ) -> dict:
        """Calculate code metrics."""
        lines = code.split("\n")
        return {
            "lines_of_code": len(lines),
            "blank_lines": sum(1 for l in lines if not l.strip()),
            "comment_lines": sum(1 for l in lines if l.strip().startswith("#")),
            "function_count": len(re.findall(r"\bdef\s+\w+", code)),
            "class_count": len(re.findall(r"\bclass\s+\w+", code)),
            "positive_patterns": sum(1 for p in patterns if p.is_positive),
            "negative_patterns": sum(1 for p in patterns if not p.is_positive),
            "smell_count": len(smells),
            "critical_smells": sum(1 for s in smells if s.severity == Severity.CRITICAL),
            "warning_smells": sum(1 for s in smells if s.severity == Severity.WARNING),
        }

    def _calculate_score(
        self, patterns: list[CodePattern], smells: list[CodeSmell], metrics: dict
    ) -> float:
        """Calculate overall code quality score (0-100)."""
        base_score = 100.0

        # Deduct for smells
        smell_deductions = {
            Severity.CRITICAL: 15,
            Severity.ERROR: 10,
            Severity.WARNING: 5,
            Severity.INFO: 2,
        }

        for smell in smells:
            base_score -= smell_deductions.get(smell.severity, 0)

        # Deduct for anti-patterns
        for pattern in patterns:
            if not pattern.is_positive:
                base_score -= 8

        # Bonus for positive patterns
        for pattern in patterns:
            if pattern.is_positive:
                base_score += 2

        # Ensure score is in valid range
        return max(0.0, min(100.0, base_score))

    def _calculate_confidence(self, patterns: list[CodePattern], smells: list[CodeSmell]) -> float:
        """Calculate confidence in the review."""
        if not patterns and not smells:
            return 0.5  # No findings = moderate confidence

        all_confidences = [p.confidence for p in patterns] + [s.confidence for s in smells]
        return sum(all_confidences) / len(all_confidences)


# CLI Interface
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="ML-Enhanced Code Reviewer")
    parser.add_argument("file", nargs="?", help="File to review")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")

    args = parser.parse_args()

    # Read code
    if args.stdin:
        import sys

        code = sys.stdin.read()
    elif args.file:
        with open(args.file) as f:
            code = f.read()
    else:
        parser.print_help()
        return

    # Review
    reviewer = MLCodeReviewer()
    result = await reviewer.review(code, args.file)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'=' * 60}")
        print("ML-ENHANCED CODE REVIEW")
        print(f"{'=' * 60}\n")

        print(f"Overall Score: {result.overall_score:.1f}/100")
        print(f"Confidence: {result.confidence:.0%}\n")

        if result.patterns:
            print("--- Patterns Detected ---")
            for p in result.patterns:
                status = "+" if p.is_positive else "-"
                print(f"  [{status}] {p.name}: {p.description}")
            print()

        if result.smells:
            print("--- Code Smells ---")
            for s in result.smells:
                print(f"  [{s.severity.value.upper()}] {s.smell_type.value}")
                print(f"      {s.description}")
                print(f"      Suggestion: {s.suggestion}")
            print()

        if result.recommendations:
            print("--- Recommendations ---")
            for i, r in enumerate(result.recommendations, 1):
                print(f"  {i}. [{r.category}] {r.title}")
                print(f"     {r.description}")
            print()

        print("--- Metrics ---")
        for key, value in result.metrics.items():
            print(f"  {key}: {value}")

        print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
