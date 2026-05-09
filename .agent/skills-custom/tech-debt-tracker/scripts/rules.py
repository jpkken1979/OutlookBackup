"""Rule definitions and metadata for tech debt detection.

Defines all debt rules with their IDs, severities, descriptions,
and language-specific patterns for matching.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DebtSeverity(str, Enum):
    """Severity levels for debt issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DebtType(str, Enum):
    """Category of debt."""

    TYPES = "types"
    TODOS = "todos"
    COMPLEXITY = "complexity"
    NAMING = "naming"
    DUPLICATES = "duplicates"
    UNUSED = "unused"


@dataclass
class DebtRule:
    """Metadata for a single debt detection rule."""

    rule_id: str
    debt_type: DebtType
    severity: DebtSeverity
    description: str
    detail: str
    max_value: Optional[int] = None  # e.g. max 50 lines per function
    min_value: Optional[int] = None

    def score_penalty(self) -> int:
        """Points deducted from health score for this rule type."""
        mapping = {
            DebtSeverity.CRITICAL: 10,
            DebtSeverity.HIGH: 5,
            DebtSeverity.MEDIUM: 2,
            DebtSeverity.LOW: 1,
        }
        return mapping.get(self.severity, 1)


# All registered debt rules
DEBT_RULES: dict[str, DebtRule] = {
    # Python type hints
    "PY001": DebtRule(
        rule_id="PY001",
        debt_type=DebtType.TYPES,
        severity=DebtSeverity.CRITICAL,
        description="Function without type hints",
        detail="Function parameters or return type missing type annotation",
    ),
    "PY002": DebtRule(
        rule_id="PY002",
        debt_type=DebtType.TYPES,
        severity=DebtSeverity.CRITICAL,
        description="Missing return type annotation",
        detail="Function has type hints on params but missing return annotation",
    ),
    "PY003": DebtRule(
        rule_id="PY003",
        debt_type=DebtType.TYPES,
        severity=DebtSeverity.HIGH,
        description="Variable without type hint",
        detail="Module-level or class variable missing type annotation",
    ),
    # TODOs without issue tracking
    "TD001": DebtRule(
        rule_id="TD001",
        debt_type=DebtType.TODOS,
        severity=DebtSeverity.HIGH,
        description="TODO without issue reference",
        detail="TODO comment found but no GitHub issue number attached",
    ),
    "TD002": DebtRule(
        rule_id="TD002",
        debt_type=DebtType.TODOS,
        severity=DebtSeverity.HIGH,
        description="FIXME or XXX without context",
        detail="FIXME/XXX/HACK found without explanation or issue link",
    ),
    # Complexity
    "CX001": DebtRule(
        rule_id="CX001",
        debt_type=DebtType.COMPLEXITY,
        severity=DebtSeverity.MEDIUM,
        description="Function exceeds max lines",
        detail="Function body is too long, consider splitting",
        max_value=50,
    ),
    "CX002": DebtRule(
        rule_id="CX002",
        debt_type=DebtType.COMPLEXITY,
        severity=DebtSeverity.MEDIUM,
        description="File exceeds max lines",
        detail="File is very large, consider modularizing",
        max_value=500,
    ),
    "CX003": DebtRule(
        rule_id="CX003",
        debt_type=DebtType.COMPLEXITY,
        severity=DebtSeverity.MEDIUM,
        description="Cyclomatic complexity high",
        detail="Function has too many branches/loops",
        max_value=10,
    ),
    # Naming conventions
    "NM001": DebtRule(
        rule_id="NM001",
        debt_type=DebtType.NAMING,
        severity=DebtSeverity.LOW,
        description="Inconsistent naming convention",
        detail="Mixed snake_case and camelCase in the same file",
    ),
    # Duplicates
    "DP001": DebtRule(
        rule_id="DP001",
        debt_type=DebtType.DUPLICATES,
        severity=DebtSeverity.MEDIUM,
        description="Duplicate code block",
        detail="Identical block of 5+ lines found elsewhere in the codebase",
        min_value=5,
    ),
    # Unused code
    "UN001": DebtRule(
        rule_id="UN001",
        debt_type=DebtType.UNUSED,
        severity=DebtSeverity.HIGH,
        description="Import not used",
        detail="import statement does not reference any used name",
    ),
    "UN002": DebtRule(
        rule_id="UN002",
        debt_type=DebtType.UNUSED,
        severity=DebtSeverity.HIGH,
        description="Variable assigned but never used",
        detail="Variable is assigned but never referenced",
    ),
    "UN003": DebtRule(
        rule_id="UN003",
        debt_type=DebtType.UNUSED,
        severity=DebtSeverity.MEDIUM,
        description="Function never called",
        detail="Function defined but never invoked",
    ),
}

# Regex patterns per language
PYTHON_PATTERNS = {
    "todo_without_issue": r"(?i)\bTODO\b(?!\s*[,;:\-]?\s*(#\s*)?(?:issue|ref|l-issue|closes?|fixes?)\s*:?\s*[\w\-#/])",
    "fixme": r"(?i)\b(FIXME|XXX|HACK)\b",
    "function_no_type_hints": r"^\s*(?:(?:async\s+)?(?:def\s+\w+))\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:",  # simplified
    "unused_import": r"^\s*(?:import\s+(\w+)|from\s+[\w.]+\s+import\s+([\w\s,*]+))",
    "snake_case": r"\b[a-z][a-z0-9]*_[a-z][a-z0-9]*\b",
    "camel_case": r"\b[a-z][a-z0-9]*[A-Z][a-zA-Z0-9]*\b",
}

TYPESCRIPT_PATTERNS = {
    "todo_without_issue": r"(?i)\bTODO\b(?!\s*[,;:\-]?\s*(//\s*)?(?:issue|ref|l-issue|closes?|fixes?)\s*:?\s*[\w\-#/])",
    "fixme": r"(?i)\b(FIXME|XXX|HACK)\b",
    "unused_import": r"^\s*(?:import\s+[^;]+from\s+['\"][^'\"]+['\"]|import\s+[^;]+from\s+['\"][^'\"]+['\"])",
    "function_no_return_type": r"^\s*(?:(?:async\s+)?function\s+\w+\s*\([^)]*\)(?!\s*:\s*[^({]+{)|\s*(?:const|let|var)\s+\w+\s*=\s*(?:(?:async\s+)?\([^)]*\)\s*(?:=>|{)))",
}

RUST_PATTERNS = {
    "todo_without_issue": r"(?i)\bTODO\b(?!\s*[,;:\-]?\s*(//\s*)?(?:issue|ref|l-issue|closes?|fixes?)\s*:?\s*[\w\-#/])",
    "fixme": r"(?i)\b(FIXME|XXX|HACK)\b",
    "unused_import": r"^\s*use\s+([\w:]+)",
    "clippy_lint": r"#\[allow\([\w_]+\)\]",
}

# Scope to language mapping
SCOPE_LANGUAGES: dict[str, list[str]] = {
    ".agent": ["py"],
    "nexus-app/src": ["ts", "tsx", "rs"],
    "nexus-app/src-tauri": ["rs"],
    "src": ["ts", "tsx"],
    "mcp-server": ["py"],
}

# File extension to language
EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
}

# Language to extensions
LANG_TO_EXTS: dict[str, list[str]] = {
    "python": [".py"],
    "typescript": [".ts", ".tsx"],
    "rust": [".rs"],
}


def get_rule(rule_id: str) -> Optional[DebtRule]:
    """Get rule metadata by ID."""
    return DEBT_RULES.get(rule_id)


def get_rules_by_type(debt_type: DebtType) -> list[DebtRule]:
    """Get all rules of a specific debt type."""
    return [r for r in DEBT_RULES.values() if r.debt_type == debt_type]


def get_rules_by_severity(severity: DebtSeverity) -> list[DebtRule]:
    """Get all rules of a specific severity."""
    return [r for r in DEBT_RULES.values() if r.severity == severity]
