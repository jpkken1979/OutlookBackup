# mypy: ignore-errors
#!/usr/bin/env python3
"""
Proactive Suggestions - Suggests improvements before being asked.

This module provides proactive intelligence that:
1. Analyzes current context and code
2. Identifies potential improvements
3. Suggests optimizations, fixes, and enhancements
4. Learns from accepted/rejected suggestions
5. Prioritizes suggestions by impact

Usage:
    from .agent.core.intelligence import ProactiveSuggester, get_suggestions

    suggester = ProactiveSuggester()

    # Get suggestions for current context
    suggestions = await suggester.suggest(
        code="def add(a, b): return a + b",
        context={"language": "python", "type": "function"}
    )

    for suggestion in suggestions:
        print(f"{suggestion.priority}: {suggestion.title}")
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.proactive_suggestions")


class SuggestionCategory(Enum):
    """Categories of suggestions."""

    PERFORMANCE = "performance"
    SECURITY = "security"
    CODE_QUALITY = "code_quality"
    BEST_PRACTICE = "best_practice"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ACCESSIBILITY = "accessibility"
    ERROR_HANDLING = "error_handling"
    REFACTORING = "refactoring"
    ARCHITECTURE = "architecture"


class SuggestionPriority(Enum):
    """Priority levels for suggestions."""

    CRITICAL = "critical"  # Must address
    HIGH = "high"  # Should address
    MEDIUM = "medium"  # Good to address
    LOW = "low"  # Nice to have
    INFO = "info"  # FYI only


@dataclass
class Suggestion:
    """A proactive suggestion."""

    suggestion_id: str
    title: str
    description: str
    category: SuggestionCategory
    priority: SuggestionPriority
    code_location: str | None = None
    current_code: str | None = None
    suggested_code: str | None = None
    rationale: str = ""
    impact: str = ""
    effort: str = "low"  # low, medium, high
    confidence: float = 0.8
    references: list[str] = field(default_factory=list)
    auto_fixable: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "code_location": self.code_location,
            "current_code": self.current_code,
            "suggested_code": self.suggested_code,
            "rationale": self.rationale,
            "impact": self.impact,
            "effort": self.effort,
            "confidence": self.confidence,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class SuggestionResult:
    """Result of suggestion generation."""

    suggestions: list[Suggestion]
    analysis_time_ms: int
    patterns_checked: int
    context_analyzed: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "analysis_time_ms": self.analysis_time_ms,
            "patterns_checked": self.patterns_checked,
            "summary": self.summary,
        }


class PatternMatcher:
    """Matches code patterns for suggestions."""

    def __init__(self):
        self.patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> list[dict[str, Any]]:
        """Initialize pattern library."""
        return [
            # Security patterns
            {
                "name": "hardcoded_secret",
                "category": SuggestionCategory.SECURITY,
                "priority": SuggestionPriority.CRITICAL,
                "pattern": r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]",
                "title": "Hardcoded Secret Detected",
                "description": "Secrets should not be hardcoded in source code",
                "suggestion": "Use environment variables or a secrets manager",
                "auto_fixable": False,
            },
            {
                "name": "sql_injection",
                "category": SuggestionCategory.SECURITY,
                "priority": SuggestionPriority.CRITICAL,
                "pattern": r"(execute|query)\s*\(\s*['\"].*\+.*['\"]|f['\"].*{.*}.*['\"]",
                "title": "Potential SQL Injection",
                "description": "String concatenation in SQL queries can lead to injection",
                "suggestion": "Use parameterized queries instead",
                "auto_fixable": False,
            },
            {
                "name": "eval_usage",
                "category": SuggestionCategory.SECURITY,
                "priority": SuggestionPriority.HIGH,
                "pattern": r"\beval\s*\(",
                "title": "Eval Usage Detected",
                "description": "eval() can execute arbitrary code and is a security risk",
                "suggestion": "Use safer alternatives like ast.literal_eval() or json.loads()",
                "auto_fixable": False,
            },
            # Performance patterns
            {
                "name": "n_plus_one",
                "category": SuggestionCategory.PERFORMANCE,
                "priority": SuggestionPriority.HIGH,
                "pattern": r"for.*in.*:\s*\n.*\.(query|fetch|get)\(",
                "title": "Potential N+1 Query",
                "description": "Queries inside loops can cause N+1 performance issues",
                "suggestion": "Batch queries or use eager loading",
                "auto_fixable": False,
            },
            {
                "name": "string_concatenation_loop",
                "category": SuggestionCategory.PERFORMANCE,
                "priority": SuggestionPriority.MEDIUM,
                "pattern": r"for.*:\s*\n.*\+=\s*['\"]",
                "title": "String Concatenation in Loop",
                "description": "String concatenation in loops is inefficient",
                "suggestion": "Use list and join(), or StringIO",
                "auto_fixable": True,
            },
            {
                "name": "sync_in_async",
                "category": SuggestionCategory.PERFORMANCE,
                "priority": SuggestionPriority.HIGH,
                "pattern": r"async\s+def.*:\s*\n(?:.*\n)*?.*\b(requests\.|urllib\.|open\()",
                "title": "Sync Call in Async Function",
                "description": "Synchronous I/O in async functions blocks the event loop",
                "suggestion": "Use async alternatives (aiohttp, aiofiles)",
                "auto_fixable": False,
            },
            # Code quality patterns
            {
                "name": "bare_except",
                "category": SuggestionCategory.ERROR_HANDLING,
                "priority": SuggestionPriority.MEDIUM,
                "pattern": r"except\s*:",
                "title": "Bare Except Clause",
                "description": "Bare except catches all exceptions including KeyboardInterrupt",
                "suggestion": "Catch specific exceptions (Exception for all errors)",
                "auto_fixable": True,
            },
            {
                "name": "unused_variable",
                "category": SuggestionCategory.CODE_QUALITY,
                "priority": SuggestionPriority.LOW,
                "pattern": r"(\w+)\s*=\s*[^=].*\n(?:(?!.*\1).*\n)*$",
                "title": "Potentially Unused Variable",
                "description": "Variable may not be used after assignment",
                "suggestion": "Remove if unused or prefix with underscore",
                "auto_fixable": False,
            },
            {
                "name": "magic_number",
                "category": SuggestionCategory.CODE_QUALITY,
                "priority": SuggestionPriority.LOW,
                "pattern": r"(?<!['\"])\b(?:1000|60|24|365|86400|3600)\b(?!['\"])",
                "title": "Magic Number Detected",
                "description": "Magic numbers reduce code readability",
                "suggestion": "Extract to named constant",
                "auto_fixable": True,
            },
            {
                "name": "todo_comment",
                "category": SuggestionCategory.CODE_QUALITY,
                "priority": SuggestionPriority.INFO,
                "pattern": r"#\s*(TODO|FIXME|HACK|XXX):",
                "title": "TODO/FIXME Comment",
                "description": "Unresolved TODO comment found",
                "suggestion": "Address the TODO or create a tracking issue",
                "auto_fixable": False,
            },
            # Best practice patterns
            {
                "name": "print_debug",
                "category": SuggestionCategory.BEST_PRACTICE,
                "priority": SuggestionPriority.MEDIUM,
                "pattern": r"\bprint\s*\([^)]*debug|print\s*\(\s*f?['\"]debug",
                "title": "Debug Print Statement",
                "description": "Debug print statements should not be in production code",
                "suggestion": "Use logging module instead",
                "auto_fixable": True,
            },
            {
                "name": "mutable_default",
                "category": SuggestionCategory.BEST_PRACTICE,
                "priority": SuggestionPriority.HIGH,
                "pattern": r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})",
                "title": "Mutable Default Argument",
                "description": "Mutable default arguments are shared between calls",
                "suggestion": "Use None as default and create inside function",
                "auto_fixable": True,
            },
            {
                "name": "no_type_hints",
                "category": SuggestionCategory.DOCUMENTATION,
                "priority": SuggestionPriority.LOW,
                "pattern": r"def\s+\w+\s*\([^:)]+\)\s*:",
                "title": "Missing Type Hints",
                "description": "Function parameters lack type hints",
                "suggestion": "Add type hints for better documentation and IDE support",
                "auto_fixable": False,
            },
            # Testing patterns
            {
                "name": "no_assertion",
                "category": SuggestionCategory.TESTING,
                "priority": SuggestionPriority.MEDIUM,
                "pattern": r"def\s+test_\w+\s*\([^)]*\)\s*:(?:(?!assert).)*$",
                "title": "Test Without Assertion",
                "description": "Test function may not have assertions",
                "suggestion": "Add assertions to verify expected behavior",
                "auto_fixable": False,
            },
            # Documentation patterns
            {
                "name": "no_docstring",
                "category": SuggestionCategory.DOCUMENTATION,
                "priority": SuggestionPriority.LOW,
                "pattern": r"def\s+\w+\s*\([^)]*\)\s*:\s*\n\s*(?!['\"])",
                "title": "Missing Docstring",
                "description": "Function lacks docstring",
                "suggestion": "Add docstring describing purpose, args, and returns",
                "auto_fixable": False,
            },
            # Error handling patterns
            {
                "name": "silent_exception",
                "category": SuggestionCategory.ERROR_HANDLING,
                "priority": SuggestionPriority.HIGH,
                "pattern": r"except.*:\s*\n\s*pass",
                "title": "Silent Exception",
                "description": "Exception is caught but silently ignored",
                "suggestion": "Log the exception or handle it appropriately",
                "auto_fixable": False,
            },
        ]

    def match(self, code: str, language: str = "python") -> list[dict[str, Any]]:
        """
        Match patterns against code.

        Args:
            code: Code to analyze
            language: Programming language

        Returns:
            List of matched patterns
        """
        matches = []

        for pattern in self.patterns:
            regex = pattern["pattern"]
            try:
                for match in re.finditer(regex, code, re.MULTILINE | re.IGNORECASE):
                    matches.append(
                        {
                            "pattern": pattern,
                            "match": match.group(0),
                            "start": match.start(),
                            "end": match.end(),
                            "line": code[: match.start()].count("\n") + 1,
                        }
                    )
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern['name']}")

        return matches


class ContextAnalyzer:
    """Analyzes context for suggestion opportunities."""

    def analyze(
        self,
        code: str,
        context: dict[str, Any],
    ) -> list[Suggestion]:
        """
        Analyze code context for suggestions.

        Args:
            code: Code to analyze
            context: Additional context

        Returns:
            List of contextual suggestions
        """
        suggestions = []

        # Check for missing error handling
        if self._needs_error_handling(code, context):
            suggestions.append(
                Suggestion(
                    suggestion_id=self._generate_id("error_handling"),
                    title="Add Error Handling",
                    description="This code section could benefit from error handling",
                    category=SuggestionCategory.ERROR_HANDLING,
                    priority=SuggestionPriority.MEDIUM,
                    rationale="External operations should handle potential failures",
                    impact="Improved reliability and debugging",
                    effort="medium",
                )
            )

        # Check for missing logging
        if self._needs_logging(code, context):
            suggestions.append(
                Suggestion(
                    suggestion_id=self._generate_id("logging"),
                    title="Add Logging",
                    description="Important operations should be logged",
                    category=SuggestionCategory.BEST_PRACTICE,
                    priority=SuggestionPriority.LOW,
                    rationale="Logging helps with debugging and monitoring",
                    impact="Better observability",
                    effort="low",
                )
            )

        # Check for complexity
        complexity = self._estimate_complexity(code)
        if complexity > 10:
            suggestions.append(
                Suggestion(
                    suggestion_id=self._generate_id("complexity"),
                    title="Reduce Complexity",
                    description=f"This code has high cyclomatic complexity (~{complexity})",
                    category=SuggestionCategory.REFACTORING,
                    priority=SuggestionPriority.MEDIUM
                    if complexity < 20
                    else SuggestionPriority.HIGH,
                    rationale="High complexity makes code harder to maintain and test",
                    impact="Better maintainability",
                    effort="high",
                )
            )

        # Check for large functions
        lines = code.count("\n")
        if lines > 50:
            suggestions.append(
                Suggestion(
                    suggestion_id=self._generate_id("large_function"),
                    title="Consider Breaking Down Large Function",
                    description=f"Function is {lines} lines - consider extracting smaller functions",
                    category=SuggestionCategory.REFACTORING,
                    priority=SuggestionPriority.MEDIUM,
                    rationale="Smaller functions are easier to understand and test",
                    impact="Better maintainability and testability",
                    effort="medium",
                )
            )

        return suggestions

    def _needs_error_handling(self, code: str, context: dict[str, Any]) -> bool:
        """Check if code needs error handling."""
        # Check for operations that commonly need error handling
        risky_patterns = [
            r"open\(",
            r"requests\.",
            r"\.connect\(",
            r"\.execute\(",
            r"json\.loads\(",
            r"int\(",
            r"float\(",
        ]

        has_risky = any(re.search(p, code) for p in risky_patterns)
        has_try = "try:" in code

        return has_risky and not has_try

    def _needs_logging(self, code: str, context: dict[str, Any]) -> bool:
        """Check if code needs logging."""
        # Important operations without logging
        important_patterns = [
            r"def\s+(create|update|delete|save|send|process)",
            r"\.commit\(",
            r"\.push\(",
            r"api\.",
        ]

        has_important = any(re.search(p, code) for p in important_patterns)
        has_logging = "logger." in code or "logging." in code

        return has_important and not has_logging

    def _estimate_complexity(self, code: str) -> int:
        """Estimate cyclomatic complexity."""
        # Count decision points
        decision_patterns = [
            r"\bif\b",
            r"\belif\b",
            r"\bfor\b",
            r"\bwhile\b",
            r"\band\b",
            r"\bor\b",
            r"\bexcept\b",
            r"\?",  # Ternary
        ]

        complexity = 1  # Base
        for pattern in decision_patterns:
            complexity += len(re.findall(pattern, code))

        return complexity

    def _generate_id(self, prefix: str) -> str:
        """Generate unique suggestion ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{prefix}_{timestamp}_{hashlib.md5(prefix.encode(), usedforsecurity=False).hexdigest()[:6]}"


class SuggestionPrioritizer:
    """Prioritizes and filters suggestions."""

    def prioritize(
        self,
        suggestions: list[Suggestion],
        max_suggestions: int = 10,
        categories: list[SuggestionCategory] | None = None,
    ) -> list[Suggestion]:
        """
        Prioritize and filter suggestions.

        Args:
            suggestions: Raw suggestions
            max_suggestions: Maximum number to return
            categories: Filter to specific categories

        Returns:
            Prioritized list of suggestions
        """
        # Filter by category if specified
        if categories:
            suggestions = [s for s in suggestions if s.category in categories]

        # Sort by priority and confidence
        priority_order = {
            SuggestionPriority.CRITICAL: 5,
            SuggestionPriority.HIGH: 4,
            SuggestionPriority.MEDIUM: 3,
            SuggestionPriority.LOW: 2,
            SuggestionPriority.INFO: 1,
        }

        sorted_suggestions = sorted(
            suggestions,
            key=lambda s: (
                priority_order.get(s.priority, 0),
                s.confidence,
                1 if s.auto_fixable else 0,
            ),
            reverse=True,
        )

        return sorted_suggestions[:max_suggestions]


class ProactiveSuggester:
    """
    Generates proactive suggestions for code improvement.

    This class:
    1. Analyzes code for patterns
    2. Identifies improvement opportunities
    3. Generates actionable suggestions
    4. Learns from feedback
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/suggestions")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.pattern_matcher = PatternMatcher()
        self.context_analyzer = ContextAnalyzer()
        self.prioritizer = SuggestionPrioritizer()

        # Track suggestion history
        self.suggestion_history: list[dict[str, Any]] = []
        self.accepted_patterns: dict[str, int] = {}
        self.rejected_patterns: dict[str, int] = {}
        self._load_history()

    def _load_history(self) -> None:
        """Load suggestion history."""
        history_file = self.memory_dir / "suggestion_history.json"
        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.accepted_patterns = data.get("accepted", {})
                    self.rejected_patterns = data.get("rejected", {})
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

    def _save_history(self) -> None:
        """Save suggestion history."""
        history_file = self.memory_dir / "suggestion_history.json"
        data = {
            "accepted": self.accepted_patterns,
            "rejected": self.rejected_patterns,
            "updated_at": datetime.now().isoformat(),
        }
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def suggest(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        max_suggestions: int = 10,
        categories: list[SuggestionCategory] | None = None,
    ) -> SuggestionResult:
        """
        Generate suggestions for code.

        Args:
            code: Code to analyze
            context: Additional context (language, type, etc.)
            max_suggestions: Maximum suggestions to return
            categories: Filter to specific categories

        Returns:
            SuggestionResult with prioritized suggestions
        """
        import time

        start_time = time.time()

        context = context or {}
        language = context.get("language", "python")
        suggestions = []

        # Pattern matching
        pattern_matches = self.pattern_matcher.match(code, language)

        for match in pattern_matches:
            pattern = match["pattern"]
            suggestion = Suggestion(
                suggestion_id=self._generate_id(pattern["name"]),
                title=pattern["title"],
                description=pattern["description"],
                category=pattern["category"],
                priority=self._adjust_priority(pattern),
                code_location=f"Line {match['line']}",
                current_code=match["match"][:100],
                rationale=pattern.get("suggestion", ""),
                confidence=self._calculate_confidence(pattern),
                auto_fixable=pattern.get("auto_fixable", False),
            )
            suggestions.append(suggestion)

        # Context analysis
        context_suggestions = self.context_analyzer.analyze(code, context)
        suggestions.extend(context_suggestions)

        # Prioritize
        prioritized = self.prioritizer.prioritize(
            suggestions,
            max_suggestions=max_suggestions,
            categories=categories,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Generate summary
        if not prioritized:
            summary = "No suggestions - code looks good!"
        else:
            critical = sum(1 for s in prioritized if s.priority == SuggestionPriority.CRITICAL)
            high = sum(1 for s in prioritized if s.priority == SuggestionPriority.HIGH)

            if critical > 0:
                summary = f"Found {critical} critical issue(s) that need immediate attention"
            elif high > 0:
                summary = f"Found {high} high-priority suggestion(s) to improve code quality"
            else:
                summary = f"Found {len(prioritized)} suggestion(s) for potential improvements"

        return SuggestionResult(
            suggestions=prioritized,
            analysis_time_ms=elapsed_ms,
            patterns_checked=len(self.pattern_matcher.patterns),
            context_analyzed=f"{len(code)} chars, {code.count(chr(10))} lines",
            summary=summary,
        )

    def _generate_id(self, name: str) -> str:
        """Generate unique suggestion ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"sug_{name}_{timestamp}"

    def _adjust_priority(self, pattern: dict[str, Any]) -> SuggestionPriority:
        """Adjust priority based on historical feedback."""
        name = pattern["name"]
        base_priority = pattern["priority"]

        # Check acceptance rate
        accepted = self.accepted_patterns.get(name, 0)
        rejected = self.rejected_patterns.get(name, 0)
        total = accepted + rejected

        if total > 5:
            acceptance_rate = accepted / total
            if acceptance_rate > 0.8:
                # Boost priority for often-accepted suggestions
                priority_order = list(SuggestionPriority)
                idx = priority_order.index(base_priority)
                if idx > 0:
                    return priority_order[idx - 1]
            elif acceptance_rate < 0.2:
                # Lower priority for often-rejected suggestions
                priority_order = list(SuggestionPriority)
                idx = priority_order.index(base_priority)
                if idx < len(priority_order) - 1:
                    return priority_order[idx + 1]

        return base_priority

    def _calculate_confidence(self, pattern: dict[str, Any]) -> float:
        """Calculate confidence based on pattern and history."""
        base_confidence = 0.8

        # Adjust based on historical acceptance
        name = pattern["name"]
        accepted = self.accepted_patterns.get(name, 0)
        rejected = self.rejected_patterns.get(name, 0)
        total = accepted + rejected

        if total > 3:
            acceptance_rate = accepted / total
            base_confidence = 0.5 + acceptance_rate * 0.4

        return min(0.95, base_confidence)

    async def record_feedback(
        self,
        suggestion_id: str,
        accepted: bool,
        feedback: str | None = None,
    ) -> None:
        """
        Record feedback on a suggestion.

        Args:
            suggestion_id: ID of the suggestion
            accepted: Whether suggestion was accepted
            feedback: Optional feedback text
        """
        # Extract pattern name from ID
        parts = suggestion_id.split("_")
        if len(parts) >= 2:
            pattern_name = parts[1]

            if accepted:
                self.accepted_patterns[pattern_name] = (
                    self.accepted_patterns.get(pattern_name, 0) + 1
                )
            else:
                self.rejected_patterns[pattern_name] = (
                    self.rejected_patterns.get(pattern_name, 0) + 1
                )

            self._save_history()
            logger.info(f"Recorded feedback for {pattern_name}: accepted={accepted}")

    async def suggest_for_file(
        self,
        file_path: Path,
        **kwargs,
    ) -> SuggestionResult:
        """
        Generate suggestions for a file.

        Args:
            file_path: Path to file
            **kwargs: Additional arguments for suggest()

        Returns:
            SuggestionResult
        """
        if not file_path.exists():
            return SuggestionResult(
                suggestions=[],
                analysis_time_ms=0,
                patterns_checked=0,
                context_analyzed="File not found",
                summary=f"File not found: {file_path}",
            )

        code = file_path.read_text(encoding="utf-8")

        # Detect language from extension
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
        }
        language = language_map.get(file_path.suffix, "unknown")

        return await self.suggest(
            code=code,
            context={"language": language, "file": str(file_path)},
            **kwargs,
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get suggestion statistics."""
        total_accepted = sum(self.accepted_patterns.values())
        total_rejected = sum(self.rejected_patterns.values())
        total = total_accepted + total_rejected

        return {
            "total_suggestions_evaluated": total,
            "acceptance_rate": total_accepted / total if total > 0 else 0,
            "most_accepted": sorted(
                self.accepted_patterns.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
            "most_rejected": sorted(
                self.rejected_patterns.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

    def export_report(self) -> str:
        """Export suggestion report as markdown."""
        stats = self.get_statistics()

        lines = [
            "# Proactive Suggestions Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Statistics",
            "",
            f"- Total suggestions evaluated: {stats['total_suggestions_evaluated']}",
            f"- Overall acceptance rate: {stats['acceptance_rate']:.0%}",
            "",
            "## Most Accepted Patterns",
            "",
        ]

        for name, count in stats["most_accepted"]:
            lines.append(f"- {name}: {count} times")

        lines.extend(
            [
                "",
                "## Most Rejected Patterns",
                "",
            ]
        )

        for name, count in stats["most_rejected"]:
            lines.append(f"- {name}: {count} times")

        return "\n".join(lines)


# Convenience function
async def get_suggestions(
    code: str,
    context: dict[str, Any] | None = None,
) -> SuggestionResult:
    """Quick function to get suggestions for code."""
    suggester = ProactiveSuggester()
    return await suggester.suggest(code, context)
