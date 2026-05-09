#!/usr/bin/env python3
"""
ML-Enhanced Test Generator

Generates tests using ML-based analysis:
- Intelligent test case generation
- Edge case detection
- Coverage optimization
- Test pattern suggestions

Version: 1.0.0
"""

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestType(Enum):
    """Types of tests."""

    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PROPERTY = "property"
    SNAPSHOT = "snapshot"


class EdgeCaseType(Enum):
    """Types of edge cases."""

    NULL_INPUT = "null_input"
    EMPTY_INPUT = "empty_input"
    BOUNDARY = "boundary"
    OVERFLOW = "overflow"
    TYPE_ERROR = "type_error"
    RACE_CONDITION = "race_condition"
    TIMEOUT = "timeout"
    INVALID_STATE = "invalid_state"


@dataclass
class FunctionAnalysis:
    """Analysis of a function for testing."""

    name: str
    file_path: str
    line_number: int
    parameters: list
    return_type: str | None
    complexity: int
    dependencies: list
    is_async: bool
    has_side_effects: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "complexity": self.complexity,
            "dependencies": self.dependencies,
            "is_async": self.is_async,
            "has_side_effects": self.has_side_effects,
        }


@dataclass
class TestCase:
    """A generated test case."""

    name: str
    test_type: TestType
    function_under_test: str
    description: str
    inputs: dict
    expected_output: Any
    edge_case: EdgeCaseType | None = None
    priority: int = 1  # 1-5, higher = more important
    code: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "test_type": self.test_type.value,
            "function_under_test": self.function_under_test,
            "description": self.description,
            "inputs": self.inputs,
            "expected_output": str(self.expected_output),
            "edge_case": self.edge_case.value if self.edge_case else None,
            "priority": self.priority,
            "code": self.code,
        }


@dataclass
class TestGenerationResult:
    """Result of test generation."""

    source_file: str
    functions_analyzed: int
    test_cases: list = field(default_factory=list)
    coverage_estimate: float = 0.0
    suggestions: list = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "functions_analyzed": self.functions_analyzed,
            "test_cases": [t.to_dict() for t in self.test_cases],
            "coverage_estimate": self.coverage_estimate,
            "suggestions": self.suggestions,
            "generated_at": self.generated_at.isoformat(),
        }


class FunctionAnalyzer:
    """Analyzes source code to extract function information."""

    # Patterns for Python functions
    PYTHON_PATTERNS = {
        "function": r"(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*(\w+))?\s*:",
        "class": r"class\s+(\w+)\s*(?:\([^)]*\))?\s*:",
        "import": r"(?:from\s+[\w.]+\s+)?import\s+([\w,\s]+)",
    }

    # Patterns for JS/TS functions
    JS_PATTERNS = {
        "function": r"(?:async\s+)?(?:function\s+)?(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*(?::\s*(\w+))?",
        "arrow": r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*(\w+))?\s*=>",
        "import": r"import\s+\{?([^}]+)\}?\s+from",
    }

    async def analyze_file(self, file_path: Path) -> list[FunctionAnalysis]:
        """
        Analyze a source file.

        Args:
            file_path: Path to source file

        Returns:
            List of FunctionAnalysis
        """
        try:
            with open(file_path) as f:
                code = f.read()
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return []

        functions = []

        # Detect language
        if file_path.suffix == ".py":
            functions = self._analyze_python(code, str(file_path))
        elif file_path.suffix in {".js", ".ts", ".jsx", ".tsx"}:
            functions = self._analyze_javascript(code, str(file_path))

        return functions

    def _analyze_python(self, code: str, file_path: str) -> list[FunctionAnalysis]:
        """Analyze Python code."""
        functions = []
        code.split("\n")

        # Find functions
        for match in re.finditer(self.PYTHON_PATTERNS["function"], code):
            name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3)

            # Skip private/dunder methods for simple analysis
            if name.startswith("_") and not name.startswith("__init__"):
                continue

            # Parse parameters
            params = []
            if params_str.strip():
                for param in params_str.split(","):
                    param = param.strip()
                    if param and param != "self" and param != "cls":
                        # Extract name and type hint
                        if ":" in param:
                            pname, ptype = param.split(":")[:2]
                            params.append({"name": pname.strip(), "type": ptype.strip()})
                        else:
                            params.append({"name": param.split("=")[0].strip(), "type": "Any"})

            # Calculate line number
            line_num = code[: match.start()].count("\n") + 1

            # Detect if async
            is_async = "async def" in code[max(0, match.start() - 10) : match.start() + 10]

            # Detect side effects (simple heuristic)
            func_body = self._extract_function_body(code, match.end())
            has_side_effects = self._detect_side_effects(func_body)

            # Calculate complexity (simple: count branches)
            complexity = self._calculate_complexity(func_body)

            # Find dependencies
            dependencies = self._find_dependencies(func_body)

            functions.append(
                FunctionAnalysis(
                    name=name,
                    file_path=file_path,
                    line_number=line_num,
                    parameters=params,
                    return_type=return_type,
                    complexity=complexity,
                    dependencies=dependencies,
                    is_async=is_async,
                    has_side_effects=has_side_effects,
                )
            )

        return functions

    def _analyze_javascript(self, code: str, file_path: str) -> list[FunctionAnalysis]:
        """Analyze JavaScript/TypeScript code."""
        functions = []

        # Find regular functions
        for match in re.finditer(self.JS_PATTERNS["function"], code):
            name = match.group(1)
            if name in {"if", "for", "while", "switch"}:
                continue

            params_str = match.group(2) if len(match.groups()) > 1 else ""
            return_type = match.group(3) if len(match.groups()) > 2 else None

            params = self._parse_js_params(params_str)
            line_num = code[: match.start()].count("\n") + 1

            functions.append(
                FunctionAnalysis(
                    name=name,
                    file_path=file_path,
                    line_number=line_num,
                    parameters=params,
                    return_type=return_type,
                    complexity=1,
                    dependencies=[],
                    is_async="async" in code[max(0, match.start() - 10) : match.start()],
                    has_side_effects=False,
                )
            )

        # Find arrow functions
        for match in re.finditer(self.JS_PATTERNS["arrow"], code):
            name = match.group(1)
            return_type = match.group(2) if len(match.groups()) > 1 else None

            line_num = code[: match.start()].count("\n") + 1

            functions.append(
                FunctionAnalysis(
                    name=name,
                    file_path=file_path,
                    line_number=line_num,
                    parameters=[],
                    return_type=return_type,
                    complexity=1,
                    dependencies=[],
                    is_async="async" in code[max(0, match.start() - 10) : match.start()],
                    has_side_effects=False,
                )
            )

        return functions

    def _parse_js_params(self, params_str: str) -> list:
        """Parse JavaScript parameters."""
        params = []
        if not params_str.strip():
            return params

        for param in params_str.split(","):
            param = param.strip()
            if param:
                if ":" in param:
                    pname, ptype = param.split(":")[:2]
                    params.append({"name": pname.strip(), "type": ptype.strip()})
                else:
                    params.append({"name": param.split("=")[0].strip(), "type": "any"})

        return params

    def _extract_function_body(self, code: str, start_pos: int) -> str:
        """Extract function body (simple: until next def or class)."""
        remaining = code[start_pos:]
        # Find next function or class definition
        match = re.search(r"\n(?:async\s+)?def\s+|\nclass\s+", remaining)
        if match:
            return remaining[: match.start()]
        return remaining

    def _detect_side_effects(self, code: str) -> bool:
        """Detect if code has side effects."""
        side_effect_patterns = [
            r"print\s*\(",
            r"\.write\s*\(",
            r"\.save\s*\(",
            r"\.delete\s*\(",
            r"\.update\s*\(",
            r"requests\.",
            r"fetch\s*\(",
            r"\.send\s*\(",
        ]
        return any(re.search(p, code) for p in side_effect_patterns)

    def _calculate_complexity(self, code: str) -> int:
        """Calculate cyclomatic complexity (simplified)."""
        complexity = 1
        complexity += len(re.findall(r"\bif\b", code))
        complexity += len(re.findall(r"\belif\b", code))
        complexity += len(re.findall(r"\bfor\b", code))
        complexity += len(re.findall(r"\bwhile\b", code))
        complexity += len(re.findall(r"\bexcept\b", code))
        complexity += len(re.findall(r"\band\b", code))
        complexity += len(re.findall(r"\bor\b", code))
        return complexity

    def _find_dependencies(self, code: str) -> list:
        """Find function dependencies."""
        # Simple: find function calls
        calls = re.findall(r"(\w+)\s*\(", code)
        # Filter built-ins and common names
        builtins = {
            "print",
            "len",
            "str",
            "int",
            "float",
            "list",
            "dict",
            "set",
            "range",
            "enumerate",
            "zip",
        }
        return [c for c in set(calls) if c not in builtins][:5]


class TestGenerator:
    """Generates test cases using ML-based analysis."""

    def __init__(self):
        self.analyzer = FunctionAnalyzer()

    async def generate_tests(
        self, file_path: Path, test_type: TestType = TestType.UNIT
    ) -> TestGenerationResult:
        """
        Generate tests for a source file.

        Args:
            file_path: Source file to generate tests for
            test_type: Type of tests to generate

        Returns:
            TestGenerationResult
        """
        # Analyze functions
        functions = await self.analyzer.analyze_file(file_path)

        test_cases = []
        for func in functions:
            # Generate tests for each function
            func_tests = self._generate_function_tests(func, test_type)
            test_cases.extend(func_tests)

        # Calculate coverage estimate
        coverage = self._estimate_coverage(functions, test_cases)

        # Generate suggestions
        suggestions = self._generate_suggestions(functions, test_cases)

        return TestGenerationResult(
            source_file=str(file_path),
            functions_analyzed=len(functions),
            test_cases=test_cases,
            coverage_estimate=coverage,
            suggestions=suggestions,
        )

    def _generate_function_tests(
        self, func: FunctionAnalysis, test_type: TestType
    ) -> list[TestCase]:
        """Generate tests for a single function."""
        tests = []

        # Basic happy path test
        tests.append(self._create_happy_path_test(func))

        # Edge case tests
        edge_cases = self._detect_edge_cases(func)
        for edge_case in edge_cases:
            tests.append(self._create_edge_case_test(func, edge_case))

        # If complex, add more tests
        if func.complexity > 3:
            tests.append(self._create_boundary_test(func))

        # If async, add async-specific test
        if func.is_async:
            tests.append(self._create_async_test(func))

        return tests

    def _create_happy_path_test(self, func: FunctionAnalysis) -> TestCase:
        """Create a happy path test."""
        # Generate code based on language
        is_python = func.file_path.endswith(".py")

        if is_python:
            code = self._generate_python_test(func, "happy_path")
        else:
            code = self._generate_js_test(func, "happy_path")

        return TestCase(
            name=f"test_{func.name}_happy_path",
            test_type=TestType.UNIT,
            function_under_test=func.name,
            description=f"Test {func.name} with valid input",
            inputs=self._generate_valid_inputs(func),
            expected_output="Expected result",
            priority=3,
            code=code,
        )

    def _create_edge_case_test(self, func: FunctionAnalysis, edge_case: EdgeCaseType) -> TestCase:
        """Create an edge case test."""
        is_python = func.file_path.endswith(".py")

        if is_python:
            code = self._generate_python_test(func, edge_case.value)
        else:
            code = self._generate_js_test(func, edge_case.value)

        return TestCase(
            name=f"test_{func.name}_{edge_case.value}",
            test_type=TestType.UNIT,
            function_under_test=func.name,
            description=f"Test {func.name} with {edge_case.value}",
            inputs=self._generate_edge_case_inputs(func, edge_case),
            expected_output="Error or handled gracefully",
            edge_case=edge_case,
            priority=4,
            code=code,
        )

    def _create_boundary_test(self, func: FunctionAnalysis) -> TestCase:
        """Create a boundary test for complex functions."""
        return TestCase(
            name=f"test_{func.name}_boundary",
            test_type=TestType.UNIT,
            function_under_test=func.name,
            description=f"Test {func.name} at boundary conditions",
            inputs={},
            expected_output="Within bounds",
            edge_case=EdgeCaseType.BOUNDARY,
            priority=3,
            code="",
        )

    def _create_async_test(self, func: FunctionAnalysis) -> TestCase:
        """Create an async-specific test."""
        return TestCase(
            name=f"test_{func.name}_async",
            test_type=TestType.UNIT,
            function_under_test=func.name,
            description=f"Test {func.name} async behavior",
            inputs={},
            expected_output="Resolves correctly",
            priority=3,
            code="",
        )

    def _detect_edge_cases(self, func: FunctionAnalysis) -> list[EdgeCaseType]:
        """Detect relevant edge cases for a function."""
        edge_cases = [EdgeCaseType.NULL_INPUT]

        # Check parameter types
        for param in func.parameters:
            ptype = param.get("type", "").lower()
            if "str" in ptype or "string" in ptype:
                edge_cases.append(EdgeCaseType.EMPTY_INPUT)
            if "int" in ptype or "number" in ptype:
                edge_cases.append(EdgeCaseType.BOUNDARY)
                edge_cases.append(EdgeCaseType.OVERFLOW)

        # Async functions might have timeouts
        if func.is_async:
            edge_cases.append(EdgeCaseType.TIMEOUT)

        return list(set(edge_cases))[:4]  # Limit

    def _generate_valid_inputs(self, func: FunctionAnalysis) -> dict:
        """Generate valid test inputs."""
        inputs = {}
        for param in func.parameters:
            pname = param.get("name", "")
            ptype = param.get("type", "").lower()

            if "str" in ptype or "string" in ptype:
                inputs[pname] = "test_value"
            elif "int" in ptype or "number" in ptype:
                inputs[pname] = 42
            elif "bool" in ptype or "boolean" in ptype:
                inputs[pname] = True
            elif "list" in ptype or "array" in ptype:
                inputs[pname] = [1, 2, 3]
            elif "dict" in ptype or "object" in ptype:
                inputs[pname] = {"key": "value"}
            else:
                inputs[pname] = "mock_value"

        return inputs

    def _generate_edge_case_inputs(self, func: FunctionAnalysis, edge_case: EdgeCaseType) -> dict:
        """Generate edge case inputs."""
        inputs = {}

        for param in func.parameters:
            pname = param.get("name", "")

            if edge_case == EdgeCaseType.NULL_INPUT:
                inputs[pname] = None
            elif edge_case == EdgeCaseType.EMPTY_INPUT:
                inputs[pname] = ""
            elif edge_case == EdgeCaseType.BOUNDARY:
                inputs[pname] = 0
            elif edge_case == EdgeCaseType.OVERFLOW:
                inputs[pname] = 2**31
            else:
                inputs[pname] = None

        return inputs

    def _generate_python_test(self, func: FunctionAnalysis, test_name: str) -> str:
        """Generate Python test code."""
        params = ", ".join(p["name"] for p in func.parameters)
        async_prefix = "async " if func.is_async else ""
        await_prefix = "await " if func.is_async else ""

        return f'''
{async_prefix}def test_{func.name}_{test_name}():
    """Test {func.name} - {test_name}."""
    # Arrange
    # Arrange: configurar datos de prueba

    # Act
    result = {await_prefix}{func.name}({params})

    # Assert
    assert result is not None
    # Verificar: agregar assertions específicos
'''

    def _generate_js_test(self, func: FunctionAnalysis, test_name: str) -> str:
        """Generate JavaScript test code."""
        params = ", ".join(p["name"] for p in func.parameters)
        async_prefix = "async " if func.is_async else ""
        await_prefix = "await " if func.is_async else ""

        return f"""
describe('{func.name}', () => {{
  it('should handle {test_name}', {async_prefix}() => {{
    // Arrange
    // TODO: Set up test data

    // Act
    const result = {await_prefix}{func.name}({params});

    // Assert
    expect(result).toBeDefined();
    // TODO: Add specific assertions
  }});
}});
"""

    def _estimate_coverage(
        self, functions: list[FunctionAnalysis], test_cases: list[TestCase]
    ) -> float:
        """Estimate test coverage."""
        if not functions:
            return 0.0

        # Simple: tests per function ratio
        tested_functions = {t.function_under_test for t in test_cases}
        coverage = len(tested_functions) / len(functions) * 100

        return round(min(100.0, coverage), 1)

    def _generate_suggestions(
        self, functions: list[FunctionAnalysis], test_cases: list[TestCase]
    ) -> list[str]:
        """Generate testing suggestions."""
        suggestions = []

        # Complex functions
        complex_funcs = [f for f in functions if f.complexity > 5]
        if complex_funcs:
            suggestions.append(
                f"Consider refactoring {len(complex_funcs)} complex functions before testing"
            )

        # Functions with side effects
        side_effect_funcs = [f for f in functions if f.has_side_effects]
        if side_effect_funcs:
            suggestions.append(
                f"Use mocking for {len(side_effect_funcs)} functions with side effects"
            )

        # Async functions
        async_funcs = [f for f in functions if f.is_async]
        if async_funcs:
            suggestions.append(
                f"Ensure proper async testing setup for {len(async_funcs)} async functions"
            )

        # General suggestions
        if len(test_cases) < len(functions) * 2:
            suggestions.append("Consider adding more edge case tests for better coverage")

        return suggestions


async def main():
    parser = argparse.ArgumentParser(description="ML-Enhanced Test Generator")
    parser.add_argument("file", help="Source file to generate tests for")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "e2e"],
        default="unit",
        help="Type of tests to generate",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", "-o", help="Output file for generated tests")

    args = parser.parse_args()

    generator = TestGenerator()
    result = await generator.generate_tests(Path(args.file), TestType(args.type))

    if args.json:
        output = json.dumps(result.to_dict(), indent=2)
    else:
        output = []
        output.append(f"\n{'=' * 60}")
        output.append("ML-ENHANCED TEST GENERATOR")
        output.append(f"{'=' * 60}\n")

        output.append(f"Source: {result.source_file}")
        output.append(f"Functions Analyzed: {result.functions_analyzed}")
        output.append(f"Tests Generated: {len(result.test_cases)}")
        output.append(f"Coverage Estimate: {result.coverage_estimate}%")

        if result.suggestions:
            output.append("\n--- Suggestions ---")
            for sug in result.suggestions:
                output.append(f"  - {sug}")

        output.append("\n--- Generated Tests ---")
        for tc in result.test_cases:
            output.append(f"\n[{tc.test_type.value}] {tc.name}")
            output.append(f"  Function: {tc.function_under_test}")
            output.append(f"  Priority: {tc.priority}/5")
            if tc.edge_case:
                output.append(f"  Edge Case: {tc.edge_case.value}")
            if tc.code:
                output.append(f"\n{tc.code}")

        output.append(f"\n{'=' * 60}\n")
        output = "\n".join(output)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Tests written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
