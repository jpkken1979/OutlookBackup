"""Debt detection engines for each category.

Each detector class is responsible for one debt type.
They receive file content and line number, return a list of DebtIssue.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Optional

from scripts.rules import DEBT_RULES, DebtRule, DebtSeverity, DebtType, EXT_TO_LANG


@dataclass
class DebtIssue:
    """A single debt issue found in the codebase."""

    rule_id: str
    debt_type: DebtType
    severity: DebtSeverity
    file: str
    line: int
    message: str
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        rule = DEBT_RULES.get(self.rule_id)
        if rule and not self.detail:
            self.detail = rule.description


@dataclass
class BaseDetector:
    """Base class for debt detectors."""

    file_path: str
    content: str
    language: str

    def detect(self) -> list[DebtIssue]:
        raise NotImplementedError


class PythonTypeDetector(BaseDetector):
    """Detect Python functions and variables without type hints."""

    def detect(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []
        if self.language != "python":
            return issues

        try:
            tree = ast.parse(self.content)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            # Function defs (def and async def)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_params = any(
                    getattr(arg, "annotation", None) is None
                    for arg in node.args.args + node.args.kwonlyargs
                    if getattr(arg, "name", None) != "self"
                )
                has_return = node.returns is not None

                if has_params and not has_return:
                    issues.append(
                        DebtIssue(
                            rule_id="PY001",
                            debt_type=DebtType.TYPES,
                            severity=DebtSeverity.CRITICAL,
                            file=self.file_path,
                            line=node.lineno,
                            message="function has no type hints",
                            detail=(
                                f"function {node.name} has parameters without "
                                "type annotations"
                            ),
                        )
                    )
                elif has_params and not has_return:
                    issues.append(
                        DebtIssue(
                            rule_id="PY002",
                            debt_type=DebtType.TYPES,
                            severity=DebtSeverity.CRITICAL,
                            file=self.file_path,
                            line=node.lineno,
                            message="missing return type annotation",
                            detail=f"function {node.name} has param types but no return type",
                        )
                    )

            # Module-level assignments with no type hint
            if isinstance(node, ast.AnnAssign):
                if node.annotation is None:
                    issues.append(
                        DebtIssue(
                            rule_id="PY003",
                            debt_type=DebtType.TYPES,
                            severity=DebtSeverity.HIGH,
                            file=self.file_path,
                            line=node.lineno,
                            message="variable without type hint",
                            detail="module-level variable lacks type annotation",
                        )
                    )

        return issues


class TodoDetector(BaseDetector):
    """Detect TODOs without issue reference, and FIXMEs/XXX/HACKs."""

    TODO_PATTERN = re.compile(
        r"(?i)\bTODO\b(?!\s*[,;:\-]?\s*(?:#\s*)?(?:issue|ref|l-issue|"
        r"closes?|fixes?|LIN-|#)\s*:?\s*[\w\-#/])"
    )
    FIXME_PATTERN = re.compile(r"(?i)\b(FIXME|XXX|HACK)\b")

    def detect(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []
        lines = self.content.splitlines()

        for i, line in enumerate(lines, start=1):
            # Check for TODO without issue
            if self.TODO_PATTERN.search(line):
                issues.append(
                    DebtIssue(
                        rule_id="TD001",
                        debt_type=DebtType.TODOS,
                        severity=DebtSeverity.HIGH,
                        file=self.file_path,
                        line=i,
                        message="TODO without issue reference",
                        detail=line.strip(),
                    )
                )

            # Check for FIXME/XXX/HACK
            if self.FIXME_PATTERN.search(line):
                issues.append(
                    DebtIssue(
                        rule_id="TD002",
                        debt_type=DebtType.TODOS,
                        severity=DebtSeverity.HIGH,
                        file=self.file_path,
                        line=i,
                        message="FIXME/XXX/HACK without context",
                        detail=line.strip(),
                    )
                )

        return issues


class ComplexityDetector(BaseDetector):
    """Detect overly long functions and files."""

    MAX_FUNCTION_LINES: int = 50
    MAX_FILE_LINES: int = 500

    def detect(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []

        # File-level check
        line_count = self.content.count("\n") + 1
        if line_count > self.MAX_FILE_LINES:
            issues.append(
                DebtIssue(
                    rule_id="CX002",
                    debt_type=DebtType.COMPLEXITY,
                    severity=DebtSeverity.MEDIUM,
                    file=self.file_path,
                    line=1,
                    message=f"file has {line_count} lines (max {self.MAX_FILE_LINES})",
                    detail="consider modularizing into smaller modules",
                )
            )

        if self.language != "python":
            return issues

        try:
            tree = ast.parse(self.content)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0
                if fn_lines > self.MAX_FUNCTION_LINES:
                    issues.append(
                        DebtIssue(
                            rule_id="CX001",
                            debt_type=DebtType.COMPLEXITY,
                            severity=DebtSeverity.MEDIUM,
                            file=self.file_path,
                            line=node.lineno,
                            message=f"function is {fn_lines} lines (max {self.MAX_FUNCTION_LINES})",
                            detail=f"function {node.name} is too long",
                        )
                    )
        return issues


class NamingDetector(BaseDetector):
    """Detect inconsistent naming conventions within a file."""

    SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*_[a-z][a-z0-9]*\b")
    CAMEL_RE = re.compile(r"\b[a-z]+[A-Z][a-zA-Z0-9]*\b")

    def detect(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []
        snakes = self.SNAKE_RE.findall(self.content)
        camels = self.CAMEL_RE.findall(self.content)

        if snakes and camels:
            issues.append(
                DebtIssue(
                    rule_id="NM001",
                    debt_type=DebtType.NAMING,
                    severity=DebtSeverity.LOW,
                    file=self.file_path,
                    line=1,
                    message="mixed snake_case and camelCase in same file",
                    detail=f"found {len(snakes)} snake_case and {len(camels)} camelCase names",
                )
            )
        return issues


class DuplicateDetector(BaseDetector):
    """Detect duplicate blocks of 5+ identical lines."""

    MIN_DUPLICATE_LINES: int = 5

    def detect(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []
        lines = self.content.splitlines()

        # Sliding window to find identical consecutive blocks
        seen_blocks: dict[tuple[str, ...], list[int]] = {}

        for i in range(len(lines) - self.MIN_DUPLICATE_LINES + 1):
            block = tuple(lines[i : i + self.MIN_DUPLICATE_LINES])
            # Normalize: strip whitespace, skip all-comment blocks
            normalized = tuple(l.strip() for l in block if l.strip() and not l.strip().startswith("#"))
            if len(normalized) < self.MIN_DUPLICATE_LINES:
                continue
            if normalized in seen_blocks:
                seen_blocks[normalized].append(i + 1)
            else:
                seen_blocks[normalized] = [i + 1]

        for block, line_nums in seen_blocks.items():
            if len(line_nums) > 1:
                issues.append(
                    DebtIssue(
                        rule_id="DP001",
                        debt_type=DebtType.DUPLICATES,
                        severity=DebtSeverity.MEDIUM,
                        file=self.file_path,
                        line=line_nums[0],
                        message=f"duplicate block of {self.MIN_DUPLICATE_LINES} lines appears {len(line_nums)} times",
                        detail=f"lines {line_nums}",
                    )
                )
        return issues


class UnusedDetector(BaseDetector):
    """Detect unused imports and variables."""

    def detect(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []

        if self.language == "python":
            issues.extend(self._detect_python_unused())
        elif self.language in ("typescript", "tsx"):
            issues.extend(self._detect_typescript_unused())

        return issues

    def _detect_python_unused(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []
        try:
            tree = ast.parse(self.content)
        except SyntaxError:
            return issues

        imported_names: set[str] = set()
        used_names: set[str] = set()

        for node in ast.walk(tree):
            # Collect imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

            # Collect usages
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        for name in imported_names:
            if name not in used_names:
                # Try to find import line from ast
                issues.append(
                    DebtIssue(
                        rule_id="UN001",
                        debt_type=DebtType.UNUSED,
                        severity=DebtSeverity.HIGH,
                        file=self.file_path,
                        line=1,
                        message=f"import '{name}' may be unused",
                        detail=f"imported name '{name}' not found in usage analysis",
                    )
                )
        return issues

    def _detect_typescript_unused(self) -> list[DebtIssue]:
        issues: list[DebtIssue] = []
        import_re = re.compile(
            r"^\s*import\s+(?:(?:type\s+)?(?:{\s*)?(\w+)[,\s\w]*\}?\s+from\s+['\"]([^'\"]+)['\"])"
        )
        lines = self.content.splitlines()
        for i, line in enumerate(lines, start=1):
            match = import_re.match(line)
            if match:
                imported = match.group(1)
                module = match.group(2)
                # Skip type imports and external modules
                if not module.startswith(".") and not module.startswith("@"):
                    continue
                # Rough heuristic: check if name appears later in file
                rest = "\n".join(lines[i:])
                if imported not in rest:
                    issues.append(
                        DebtIssue(
                            rule_id="UN001",
                            debt_type=DebtType.UNUSED,
                            severity=DebtSeverity.HIGH,
                            file=self.file_path,
                            line=i,
                            message=f"import '{imported}' may be unused",
                            detail=f"from {module}",
                        )
                    )
        return issues


# Detector registry
DETECTOR_REGISTRY: dict[DebtType, type[BaseDetector]] = {
    DebtType.TYPES: PythonTypeDetector,
    DebtType.TODOS: TodoDetector,
    DebtType.COMPLEXITY: ComplexityDetector,
    DebtType.NAMING: NamingDetector,
    DebtType.DUPLICATES: DuplicateDetector,
    DebtType.UNUSED: UnusedDetector,
}


def detect_debt_in_file(
    file_path: str,
    content: str,
    debt_types: Optional[list[DebtType]] = None,
) -> list[DebtIssue]:
    """Run all (or selected) detectors on a single file.

    Args:
        file_path: Path to the file (used to determine language).
        content: File content as string.
        debt_types: Optional list of DebtType to limit detection.
                   If None, runs all detectors.

    Returns:
        List of DebtIssue found.
    """
    issues: list[DebtIssue] = []

    # Determine language from extension
    ext = "." + file_path.rsplit(".", maxsplit=1)[-1]
    language = EXT_TO_LANG.get(ext, "")

    if not language:
        return issues

    if debt_types is None:
        debt_types = list(DETECTOR_REGISTRY.keys())

    for debt_type in debt_types:
        detector_cls = DETECTOR_REGISTRY.get(debt_type)
        if detector_cls:
            detector = detector_cls(file_path=file_path, content=content, language=language)
            issues.extend(detector.detect())

    return issues
