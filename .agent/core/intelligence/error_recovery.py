# mypy: ignore-errors
#!/usr/bin/env python3
"""
Error Recovery Library - Library of recovery strategies for common errors.

This module provides error recovery that:
1. Catalogs common errors and their solutions
2. Matches errors to recovery strategies
3. Learns from successful recoveries
4. Provides automatic retry with fixes
5. Tracks error patterns

Usage:
    from .agent.core.intelligence import ErrorRecovery, recover_from_error

    recovery = ErrorRecovery()

    # Attempt recovery
    result = await recovery.recover(
        error_type="ModuleNotFoundError",
        error_message="No module named 'pandas'",
        context={"file": "analysis.py"}
    )

    if result.strategy:
        print(f"Try: {result.strategy.steps[0]}")
"""

import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.error_recovery")


class ErrorCategory(Enum):
    """Categories of errors."""

    DEPENDENCY = "dependency"  # Missing dependencies
    SYNTAX = "syntax"  # Syntax errors
    RUNTIME = "runtime"  # Runtime errors
    CONFIGURATION = "configuration"  # Config issues
    NETWORK = "network"  # Network errors
    PERMISSION = "permission"  # Permission denied
    RESOURCE = "resource"  # Resource exhaustion
    TYPE = "type"  # Type errors
    IMPORT = "import"  # Import errors
    DATABASE = "database"  # Database errors
    API = "api"  # API errors
    UNKNOWN = "unknown"


class RecoveryDifficulty(Enum):
    """Difficulty of recovery."""

    TRIVIAL = "trivial"  # Auto-fix possible
    EASY = "easy"  # Simple manual fix
    MODERATE = "moderate"  # Some effort needed
    HARD = "hard"  # Significant effort
    EXPERT = "expert"  # Expert intervention needed


@dataclass
class RecoveryStep:
    """A step in a recovery strategy."""

    order: int
    action: str
    description: str
    command: str | None = None
    requires_restart: bool = False
    auto_applicable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "description": self.description,
            "command": self.command,
            "requires_restart": self.requires_restart,
            "auto_applicable": self.auto_applicable,
        }


@dataclass
class RecoveryStrategy:
    """A strategy for recovering from an error."""

    strategy_id: str
    name: str
    error_pattern: str
    category: ErrorCategory
    difficulty: RecoveryDifficulty
    steps: list[RecoveryStep]
    prevention_tips: list[str]
    success_rate: float = 0.0
    times_used: int = 0
    last_used: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "error_pattern": self.error_pattern,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "steps": [s.to_dict() for s in self.steps],
            "prevention_tips": self.prevention_tips,
            "success_rate": self.success_rate,
            "times_used": self.times_used,
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    found: bool
    strategy: RecoveryStrategy | None
    confidence: float
    alternative_strategies: list[RecoveryStrategy]
    error_analysis: str
    auto_recoverable: bool
    estimated_time: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "confidence": self.confidence,
            "alternative_count": len(self.alternative_strategies),
            "error_analysis": self.error_analysis,
            "auto_recoverable": self.auto_recoverable,
            "estimated_time": self.estimated_time,
        }


class ErrorPatternMatcher:
    """Matches errors to known patterns."""

    def __init__(self):
        self.patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> list[dict[str, Any]]:
        """Initialize error patterns."""
        return [
            # Python import errors
            {
                "pattern": r"ModuleNotFoundError: No module named '([^']+)'",
                "category": ErrorCategory.IMPORT,
                "extract": ["module_name"],
            },
            {
                "pattern": r"ImportError: cannot import name '([^']+)' from '([^']+)'",
                "category": ErrorCategory.IMPORT,
                "extract": ["import_name", "module_name"],
            },
            # Syntax errors
            {
                "pattern": r"SyntaxError: (.*)",
                "category": ErrorCategory.SYNTAX,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"IndentationError: (.*)",
                "category": ErrorCategory.SYNTAX,
                "extract": ["error_detail"],
            },
            # Type errors
            {
                "pattern": r"TypeError: (.*)",
                "category": ErrorCategory.TYPE,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"AttributeError: '([^']+)' object has no attribute '([^']+)'",
                "category": ErrorCategory.TYPE,
                "extract": ["object_type", "attribute"],
            },
            # Runtime errors
            {
                "pattern": r"ValueError: (.*)",
                "category": ErrorCategory.RUNTIME,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"KeyError: '([^']+)'",
                "category": ErrorCategory.RUNTIME,
                "extract": ["key_name"],
            },
            {
                "pattern": r"IndexError: (.*)",
                "category": ErrorCategory.RUNTIME,
                "extract": ["error_detail"],
            },
            # Network errors
            {
                "pattern": r"ConnectionError: (.*)",
                "category": ErrorCategory.NETWORK,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"TimeoutError: (.*)",
                "category": ErrorCategory.NETWORK,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"HTTPError: (\d+)",
                "category": ErrorCategory.API,
                "extract": ["status_code"],
            },
            # Permission errors
            {
                "pattern": r"PermissionError: (.*)",
                "category": ErrorCategory.PERMISSION,
                "extract": ["error_detail"],
            },
            # Resource errors
            {
                "pattern": r"MemoryError: (.*)",
                "category": ErrorCategory.RESOURCE,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"disk quota exceeded",
                "category": ErrorCategory.RESOURCE,
                "extract": [],
            },
            # Database errors
            {
                "pattern": r"OperationalError: (.*)",
                "category": ErrorCategory.DATABASE,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"IntegrityError: (.*)",
                "category": ErrorCategory.DATABASE,
                "extract": ["error_detail"],
            },
            # Config errors
            {
                "pattern": r"ConfigError: (.*)",
                "category": ErrorCategory.CONFIGURATION,
                "extract": ["error_detail"],
            },
            {
                "pattern": r"Invalid configuration",
                "category": ErrorCategory.CONFIGURATION,
                "extract": [],
            },
        ]

    def match(self, error_message: str) -> dict[str, Any] | None:
        """Match error message to a pattern."""
        for pattern_info in self.patterns:
            pattern = pattern_info["pattern"]
            match = re.search(pattern, error_message, re.IGNORECASE)

            if match:
                # Extract captured groups
                extracted = {}
                for i, name in enumerate(pattern_info.get("extract", []), 1):
                    if i <= len(match.groups()):
                        extracted[name] = match.group(i)

                return {
                    "category": pattern_info["category"],
                    "extracted": extracted,
                    "matched_pattern": pattern,
                }

        return None


class StrategyLibrary:
    """Library of recovery strategies."""

    def __init__(self):
        self.strategies: dict[str, RecoveryStrategy] = {}
        self._initialize_strategies()

    def _initialize_strategies(self) -> None:
        """Initialize built-in strategies."""
        strategies = [
            # Import/Dependency errors
            RecoveryStrategy(
                strategy_id="pip_install_missing",
                name="Install Missing Python Package",
                error_pattern=r"ModuleNotFoundError: No module named",
                category=ErrorCategory.IMPORT,
                difficulty=RecoveryDifficulty.TRIVIAL,
                steps=[
                    RecoveryStep(1, "identify", "Identify the missing module name"),
                    RecoveryStep(
                        2,
                        "install",
                        "Install the module",
                        "pip install {module_name}",
                        auto_applicable=True,
                    ),
                    RecoveryStep(
                        3, "verify", "Verify installation", 'python -c "import {module_name}"'
                    ),
                ],
                prevention_tips=[
                    "Use requirements.txt or pyproject.toml to track dependencies",
                    "Use virtual environments for project isolation",
                    "Run pip install -r requirements.txt after cloning",
                ],
            ),
            RecoveryStrategy(
                strategy_id="npm_install_missing",
                name="Install Missing Node Package",
                error_pattern=r"Cannot find module",
                category=ErrorCategory.IMPORT,
                difficulty=RecoveryDifficulty.TRIVIAL,
                steps=[
                    RecoveryStep(1, "identify", "Identify the missing package"),
                    RecoveryStep(
                        2,
                        "install",
                        "Install the package",
                        "npm install {package_name}",
                        auto_applicable=True,
                    ),
                    RecoveryStep(3, "verify", "Verify in package.json"),
                ],
                prevention_tips=[
                    "Always run npm install after cloning",
                    "Check for package.json and lock file",
                ],
            ),
            # Syntax errors
            RecoveryStrategy(
                strategy_id="fix_indentation",
                name="Fix Indentation Error",
                error_pattern=r"IndentationError",
                category=ErrorCategory.SYNTAX,
                difficulty=RecoveryDifficulty.EASY,
                steps=[
                    RecoveryStep(1, "locate", "Find the line number from the error"),
                    RecoveryStep(2, "inspect", "Check the indentation around that line"),
                    RecoveryStep(3, "fix", "Align indentation with surrounding code"),
                    RecoveryStep(4, "verify", "Run linter to check for remaining issues"),
                ],
                prevention_tips=[
                    "Use consistent indentation (4 spaces for Python)",
                    "Configure editor to show whitespace",
                    "Use a linter/formatter like black or prettier",
                ],
            ),
            # Type errors
            RecoveryStrategy(
                strategy_id="fix_none_attribute",
                name="Fix NoneType Attribute Error",
                error_pattern=r"'NoneType' object has no attribute",
                category=ErrorCategory.TYPE,
                difficulty=RecoveryDifficulty.MODERATE,
                steps=[
                    RecoveryStep(1, "trace", "Find where the None value originates"),
                    RecoveryStep(2, "check", "Add null/None check before the access"),
                    RecoveryStep(3, "handle", "Handle the None case appropriately"),
                    RecoveryStep(4, "test", "Test with edge cases"),
                ],
                prevention_tips=[
                    "Use Optional type hints",
                    "Add defensive None checks",
                    "Use pattern matching or walrus operator",
                ],
            ),
            # Network errors
            RecoveryStrategy(
                strategy_id="retry_connection",
                name="Retry Network Connection",
                error_pattern=r"ConnectionError|TimeoutError",
                category=ErrorCategory.NETWORK,
                difficulty=RecoveryDifficulty.EASY,
                steps=[
                    RecoveryStep(1, "check", "Verify network connectivity"),
                    RecoveryStep(2, "retry", "Implement retry with exponential backoff"),
                    RecoveryStep(3, "timeout", "Increase timeout if necessary"),
                    RecoveryStep(4, "fallback", "Implement fallback mechanism"),
                ],
                prevention_tips=[
                    "Always implement retry logic for network calls",
                    "Use connection pooling",
                    "Set appropriate timeouts",
                ],
            ),
            # Permission errors
            RecoveryStrategy(
                strategy_id="fix_permission",
                name="Fix Permission Denied",
                error_pattern=r"PermissionError|Permission denied",
                category=ErrorCategory.PERMISSION,
                difficulty=RecoveryDifficulty.MODERATE,
                steps=[
                    RecoveryStep(1, "identify", "Identify the file/directory in question"),
                    RecoveryStep(2, "check", "Check current permissions with ls -la"),
                    RecoveryStep(3, "fix", "Adjust permissions appropriately", "chmod +rw {path}"),
                    RecoveryStep(4, "verify", "Verify the operation works"),
                ],
                prevention_tips=[
                    "Run with appropriate user permissions",
                    "Check file ownership",
                    "Use sudo only when necessary",
                ],
            ),
            # Resource errors
            RecoveryStrategy(
                strategy_id="fix_memory",
                name="Fix Memory Error",
                error_pattern=r"MemoryError|Out of memory",
                category=ErrorCategory.RESOURCE,
                difficulty=RecoveryDifficulty.HARD,
                steps=[
                    RecoveryStep(1, "analyze", "Profile memory usage"),
                    RecoveryStep(2, "optimize", "Process data in smaller batches"),
                    RecoveryStep(3, "release", "Explicitly release large objects"),
                    RecoveryStep(
                        4, "stream", "Use generators/streaming instead of loading all data"
                    ),
                ],
                prevention_tips=[
                    "Use generators for large datasets",
                    "Process data in chunks",
                    "Monitor memory usage during development",
                ],
            ),
            # Database errors
            RecoveryStrategy(
                strategy_id="fix_connection_pool",
                name="Fix Database Connection Pool",
                error_pattern=r"too many connections|connection pool exhausted",
                category=ErrorCategory.DATABASE,
                difficulty=RecoveryDifficulty.MODERATE,
                steps=[
                    RecoveryStep(1, "close", "Close idle connections"),
                    RecoveryStep(2, "configure", "Adjust pool size configuration"),
                    RecoveryStep(3, "leak", "Check for connection leaks"),
                    RecoveryStep(
                        4, "restart", "Restart database if necessary", requires_restart=True
                    ),
                ],
                prevention_tips=[
                    "Use connection pooling",
                    "Always close connections in finally blocks",
                    "Set appropriate pool limits",
                ],
            ),
            # API errors
            RecoveryStrategy(
                strategy_id="handle_rate_limit",
                name="Handle API Rate Limit",
                error_pattern=r"429|Too Many Requests|rate limit",
                category=ErrorCategory.API,
                difficulty=RecoveryDifficulty.EASY,
                steps=[
                    RecoveryStep(1, "wait", "Wait for rate limit window to reset"),
                    RecoveryStep(2, "backoff", "Implement exponential backoff"),
                    RecoveryStep(3, "queue", "Queue requests to respect limits"),
                    RecoveryStep(4, "cache", "Cache responses where possible"),
                ],
                prevention_tips=[
                    "Check API rate limits in documentation",
                    "Implement client-side rate limiting",
                    "Use caching to reduce API calls",
                ],
            ),
        ]

        for strategy in strategies:
            self.strategies[strategy.strategy_id] = strategy

    def find_strategy(
        self,
        category: ErrorCategory,
        error_message: str,
    ) -> list[RecoveryStrategy]:
        """Find strategies for an error."""
        matches = []

        for strategy in self.strategies.values():
            # Match by category
            if strategy.category != category:
                continue

            # Match by pattern
            if re.search(strategy.error_pattern, error_message, re.IGNORECASE):
                matches.append(strategy)

        # Sort by success rate
        matches.sort(key=lambda s: s.success_rate, reverse=True)

        return matches

    def add_strategy(self, strategy: RecoveryStrategy) -> None:
        """Add a custom strategy."""
        self.strategies[strategy.strategy_id] = strategy

    def update_success(self, strategy_id: str, success: bool) -> None:
        """Update strategy success rate."""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.times_used += 1
            strategy.last_used = datetime.now()

            # Update success rate (exponential moving average)
            alpha = 0.3
            strategy.success_rate = (
                alpha * (1.0 if success else 0.0) + (1 - alpha) * strategy.success_rate
            )


class ErrorRecovery:
    """
    Error recovery system.

    This class:
    1. Analyzes errors
    2. Finds recovery strategies
    3. Tracks recovery success
    4. Learns from outcomes
    """

    def __init__(self, memory_dir: Path | None = None):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_ERROR_RECOVERY_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_ERROR_RECOVERY_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "error_recovery"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.pattern_matcher = ErrorPatternMatcher()
        self.strategy_library = StrategyLibrary()

        # Track error history
        self.error_history: list[dict[str, Any]] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load error history."""
        history_file = self.memory_dir / "error_history.json"
        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    self.error_history = json.load(f).get("history", [])
            except Exception:
                pass

    def _save_history(self) -> None:
        """Save error history."""
        history_file = self.memory_dir / "error_history.json"
        data = {
            "history": self.error_history[-1000:],  # Keep last 1000
            "updated_at": datetime.now().isoformat(),
        }
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def recover(
        self,
        error_type: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """
        Attempt to recover from an error.

        Args:
            error_type: Type of error (e.g., ModuleNotFoundError)
            error_message: Full error message
            context: Additional context

        Returns:
            RecoveryResult with strategy and analysis
        """
        context = context or {}
        full_error = f"{error_type}: {error_message}"

        # Match error to pattern
        match = self.pattern_matcher.match(full_error)

        if match:
            category = match["category"]
            extracted = match.get("extracted", {})
        else:
            category = ErrorCategory.UNKNOWN
            extracted = {}

        # Find strategies
        strategies = self.strategy_library.find_strategy(category, full_error)

        # Generate error analysis
        analysis = self._analyze_error(error_type, error_message, category, extracted)

        # Check if auto-recoverable
        auto_recoverable = (
            len(strategies) > 0
            and strategies[0].difficulty == RecoveryDifficulty.TRIVIAL
            and all(s.auto_applicable for s in strategies[0].steps)
        )

        # Estimate time
        estimated_time = self._estimate_recovery_time(strategies[0] if strategies else None)

        # Record in history
        self.error_history.append(
            {
                "error_type": error_type,
                "error_message": error_message[:500],
                "category": category.value,
                "strategies_found": len(strategies),
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save_history()

        # Calculate confidence
        confidence = self._calculate_confidence(strategies, match)

        return RecoveryResult(
            found=len(strategies) > 0,
            strategy=strategies[0] if strategies else None,
            confidence=confidence,
            alternative_strategies=strategies[1:4],
            error_analysis=analysis,
            auto_recoverable=auto_recoverable,
            estimated_time=estimated_time,
            metadata={"extracted": extracted, "category": category.value},
        )

    def _analyze_error(
        self,
        error_type: str,
        error_message: str,
        category: ErrorCategory,
        extracted: dict[str, Any],
    ) -> str:
        """Generate error analysis."""
        analysis_parts = [f"Error Type: {error_type}", f"Category: {category.value}"]

        if extracted:
            for key, value in extracted.items():
                analysis_parts.append(f"{key.replace('_', ' ').title()}: {value}")

        if category == ErrorCategory.IMPORT:
            analysis_parts.append(
                "This is a dependency issue - a required module is not installed."
            )
        elif category == ErrorCategory.SYNTAX:
            analysis_parts.append("This is a syntax error - check the code structure.")
        elif category == ErrorCategory.TYPE:
            analysis_parts.append("This is a type error - check variable types and None values.")
        elif category == ErrorCategory.NETWORK:
            analysis_parts.append("This is a network error - check connectivity and endpoints.")
        elif category == ErrorCategory.DATABASE:
            analysis_parts.append("This is a database error - check connection and queries.")

        return " | ".join(analysis_parts)

    def _estimate_recovery_time(self, strategy: RecoveryStrategy | None) -> str:
        """Estimate time to recover."""
        if not strategy:
            return "Unknown"

        estimates = {
            RecoveryDifficulty.TRIVIAL: "< 1 minute",
            RecoveryDifficulty.EASY: "1-5 minutes",
            RecoveryDifficulty.MODERATE: "5-30 minutes",
            RecoveryDifficulty.HARD: "30+ minutes",
            RecoveryDifficulty.EXPERT: "Requires expert help",
        }

        return estimates.get(strategy.difficulty, "Unknown")

    def _calculate_confidence(
        self,
        strategies: list[RecoveryStrategy],
        match: dict[str, Any] | None,
    ) -> float:
        """Calculate confidence in recovery."""
        if not strategies:
            return 0.1

        confidence = 0.5

        # Bonus for pattern match
        if match:
            confidence += 0.2

        # Bonus for strategy success rate
        if strategies[0].success_rate > 0.7:
            confidence += 0.2
        elif strategies[0].success_rate > 0.5:
            confidence += 0.1

        # Bonus for multiple strategies
        if len(strategies) > 1:
            confidence += 0.1

        return min(0.95, confidence)

    async def report_outcome(
        self,
        strategy_id: str,
        success: bool,
        notes: str | None = None,
    ) -> None:
        """Report the outcome of a recovery attempt."""
        self.strategy_library.update_success(strategy_id, success)

        # Update history
        self.error_history.append(
            {
                "type": "outcome",
                "strategy_id": strategy_id,
                "success": success,
                "notes": notes,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save_history()

        logger.info(
            f"Recovery outcome reported: {strategy_id} - {'success' if success else 'failed'}"
        )

    def get_common_errors(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most common errors."""
        error_counts: dict[str, int] = defaultdict(int)

        for entry in self.error_history:
            if "error_type" in entry:
                error_counts[entry["error_type"]] += 1

        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            {"error_type": error_type, "count": count}
            for error_type, count in sorted_errors[:limit]
        ]

    def add_custom_strategy(
        self,
        name: str,
        error_pattern: str,
        category: ErrorCategory,
        steps: list[dict[str, Any]],
        prevention_tips: list[str] | None = None,
    ) -> RecoveryStrategy:
        """Add a custom recovery strategy."""
        strategy_id = f"custom_{name.lower().replace(' ', '_')}"

        recovery_steps = [
            RecoveryStep(
                order=i + 1,
                action=step.get("action", ""),
                description=step.get("description", ""),
                command=step.get("command"),
                auto_applicable=step.get("auto_applicable", False),
            )
            for i, step in enumerate(steps)
        ]

        strategy = RecoveryStrategy(
            strategy_id=strategy_id,
            name=name,
            error_pattern=error_pattern,
            category=category,
            difficulty=RecoveryDifficulty.MODERATE,
            steps=recovery_steps,
            prevention_tips=prevention_tips or [],
        )

        self.strategy_library.add_strategy(strategy)
        return strategy

    def export_report(self) -> str:
        """Export error recovery report as markdown."""
        common_errors = self.get_common_errors()

        lines = [
            "# Error Recovery Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"**Total errors tracked:** {len(self.error_history)}",
            f"**Strategies available:** {len(self.strategy_library.strategies)}",
            "",
            "## Most Common Errors",
            "",
        ]

        for error in common_errors[:10]:
            lines.append(f"- {error['error_type']}: {error['count']} occurrences")

        lines.extend(["", "## Available Strategies", ""])

        for strategy in sorted(
            self.strategy_library.strategies.values(),
            key=lambda s: s.times_used,
            reverse=True,
        )[:10]:
            lines.append(
                f"- **{strategy.name}** ({strategy.category.value}): "
                f"used {strategy.times_used}x, {strategy.success_rate:.0%} success"
            )

        return "\n".join(lines)


# Convenience function
async def recover_from_error(
    error_type: str,
    error_message: str,
) -> RecoveryResult:
    """Quick function to attempt error recovery."""
    recovery = ErrorRecovery()
    return await recovery.recover(error_type, error_message)
