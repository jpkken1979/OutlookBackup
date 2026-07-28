# mypy: ignore-errors
#!/usr/bin/env python3
"""
Tool Learning - Agents learn to use new tools by reading documentation.

This module enables agents to:
1. Parse tool documentation (README, docstrings, schemas)
2. Build mental models of how tools work
3. Generate usage examples
4. Validate tool usage before execution
5. Learn from tool execution results

Usage:
    from .agent.core.intelligence import ToolLearner, learn_tool

    learner = ToolLearner()

    # Learn a new tool
    knowledge = await learner.learn_tool(
        tool_name="grep",
        documentation="grep searches for patterns in files...",
        examples=[("grep -r 'TODO' .", "Search for TODO comments")]
    )

    # Use learned knowledge
    usage = await learner.suggest_usage("grep", "find all import statements")
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.tool_learning")


class ToolCategory(Enum):
    """Categories of tools."""

    FILE_SYSTEM = "file_system"
    TEXT_PROCESSING = "text_processing"
    VERSION_CONTROL = "version_control"
    BUILD_SYSTEM = "build_system"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    DATABASE = "database"
    NETWORK = "network"
    AI_ML = "ai_ml"
    UTILITY = "utility"
    CUSTOM = "custom"


class ParameterType(Enum):
    """Types of tool parameters."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    PATH = "path"
    ARRAY = "array"
    OBJECT = "object"
    ENUM = "enum"
    OPTIONAL = "optional"


@dataclass
class ToolParameter:
    """A tool parameter definition."""

    name: str
    param_type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    examples: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExample:
    """An example of tool usage."""

    command: str
    description: str
    expected_output: str | None = None
    context: str = ""
    success: bool = True


@dataclass
class ToolKnowledge:
    """Complete knowledge about a tool."""

    name: str
    description: str
    category: ToolCategory
    parameters: list[ToolParameter]
    examples: list[ToolExample]
    common_patterns: list[str]
    gotchas: list[str]
    related_tools: list[str]
    confidence: float  # How well we understand this tool
    last_updated: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    success_rate: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.param_type.value,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "examples": p.examples,
                }
                for p in self.parameters
            ],
            "examples": [
                {
                    "command": e.command,
                    "description": e.description,
                    "expected_output": e.expected_output,
                }
                for e in self.examples
            ],
            "common_patterns": self.common_patterns,
            "gotchas": self.gotchas,
            "related_tools": self.related_tools,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
        }


@dataclass
class UsageSuggestion:
    """A suggested way to use a tool for a task."""

    command: str
    explanation: str
    confidence: float
    alternatives: list[str]
    warnings: list[str]
    expected_result: str


@dataclass
class LearningResult:
    """Result of learning about a tool."""

    tool_name: str
    knowledge: ToolKnowledge
    learning_sources: list[str]
    gaps_identified: list[str]
    suggestions_for_more_learning: list[str]


class DocumentationParser:
    """Parses various documentation formats to extract tool knowledge."""

    @staticmethod
    def _extract_readme_description(content: str) -> str:
        """Extrae la primera descripción real (párrafo no-header de >50 chars)."""
        for p in content.split("\n\n"):
            clean = p.strip()
            if clean and not clean.startswith("#") and len(clean) > 50:
                return clean[:500]
        return ""

    @staticmethod
    def _extract_readme_examples(content: str, tool_name: str) -> list[dict[str, Any]]:
        """Extrae hasta 5 bloques de código como ejemplos de comando."""
        examples: list[dict[str, Any]] = []
        code_blocks = re.findall(r"```(?:bash|shell|sh)?\n(.*?)```", content, re.DOTALL)
        for block in code_blocks[:5]:
            for line in block.strip().split("\n"):
                if line.strip() and not line.startswith("#"):
                    examples.append(
                        {
                            "command": line.strip(),
                            "description": f"Example usage of {tool_name}",
                        }
                    )
        return examples

    @staticmethod
    def _extract_readme_parameters(content: str) -> list[dict[str, Any]]:
        """Extrae parámetros desde secciones Options/Arguments/Parameters/Flags."""
        parameters: list[dict[str, Any]] = []
        options_match = re.search(
            r"(?:Options|Arguments|Parameters|Flags)[:\s]*\n(.*?)(?:\n\n|\n#|$)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if not options_match:
            return parameters
        option_lines = re.findall(
            r"^\s*(-[\w-]+(?:,\s*--[\w-]+)?)\s+(.+)$",
            options_match.group(1),
            re.MULTILINE,
        )
        for opt, desc in option_lines[:10]:
            parameters.append(
                {
                    "name": opt.strip(),
                    "description": desc.strip(),
                    "type": "string",
                    "required": False,
                }
            )
        return parameters

    @staticmethod
    def _extract_readme_gotchas(content: str) -> list[str]:
        """Extrae warnings/gotchas (hasta 3 por patrón)."""
        gotchas: list[str] = []
        warning_patterns = [
            r"(?:Warning|Caution|Note|Important)[:\s]*(.+?)(?:\n\n|\n#|$)",
            r"(?:Be careful|Watch out|Don't forget)[:\s]*(.+?)(?:\n\n|\n#|$)",
        ]
        for pattern in warning_patterns:
            for match in re.findall(pattern, content, re.IGNORECASE | re.DOTALL)[:3]:
                gotchas.append(match.strip()[:200])
        return gotchas

    def parse_readme(self, content: str, tool_name: str) -> dict[str, Any]:
        """Parse README-style documentation."""
        return {
            "description": self._extract_readme_description(content),
            "parameters": self._extract_readme_parameters(content),
            "examples": self._extract_readme_examples(content, tool_name),
            "gotchas": self._extract_readme_gotchas(content),
        }

    def parse_docstring(self, content: str, tool_name: str) -> dict[str, Any]:
        """Parse Python docstring format."""
        result = {
            "description": "",
            "parameters": [],
            "examples": [],
            "returns": "",
        }

        # Extract main description
        desc_match = re.match(
            r'^["\']*(.*?)(?:Args:|Parameters:|Returns:|Examples:|$)', content, re.DOTALL
        )
        if desc_match:
            result["description"] = desc_match.group(1).strip()[:500]

        # Extract Args/Parameters
        args_match = re.search(
            r"(?:Args|Parameters)[:\s]*\n(.*?)(?:Returns:|Examples:|Raises:|$)",
            content,
            re.DOTALL,
        )
        if args_match:
            args_text = args_match.group(1)
            # Parse lines like: param_name (type): Description
            param_lines = re.findall(
                r"^\s*(\w+)\s*(?:\(([^)]+)\))?[:\s]+(.+)$",
                args_text,
                re.MULTILINE,
            )
            for name, ptype, desc in param_lines:
                result["parameters"].append(
                    {
                        "name": name,
                        "type": ptype or "any",
                        "description": desc.strip(),
                        "required": "optional" not in desc.lower(),
                    }
                )

        # Extract examples
        examples_match = re.search(
            r"Examples?[:\s]*\n(.*?)(?:Returns:|Raises:|$)",
            content,
            re.DOTALL,
        )
        if examples_match:
            examples_text = examples_match.group(1)
            # Find >>> lines
            example_lines = re.findall(r">>>\s*(.+)", examples_text)
            for line in example_lines[:5]:
                result["examples"].append(
                    {
                        "command": line,
                        "description": f"Example: {line[:50]}",
                    }
                )

        return result

    def parse_json_schema(self, content: str, tool_name: str) -> dict[str, Any]:
        """Parse JSON Schema tool definition."""
        result = {
            "description": "",
            "parameters": [],
            "examples": [],
        }

        try:
            schema = json.loads(content)

            result["description"] = schema.get("description", "")

            # Parse properties
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            for prop_name, prop_def in properties.items():
                result["parameters"].append(
                    {
                        "name": prop_name,
                        "type": prop_def.get("type", "string"),
                        "description": prop_def.get("description", ""),
                        "required": prop_name in required,
                        "default": prop_def.get("default"),
                        "enum": prop_def.get("enum"),
                    }
                )

            # Parse examples if present
            examples = schema.get("examples", [])
            for ex in examples[:5]:
                result["examples"].append(
                    {
                        "command": json.dumps(ex),
                        "description": "Schema example",
                    }
                )

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON schema for {tool_name}")

        return result

    def parse_man_page(self, content: str, tool_name: str) -> dict[str, Any]:
        """Parse man page style documentation."""
        result = {
            "description": "",
            "parameters": [],
            "examples": [],
            "synopsis": "",
        }

        # Extract NAME section
        name_match = re.search(r"NAME\s+(.+?)(?:\n\n|SYNOPSIS)", content, re.DOTALL)
        if name_match:
            result["description"] = name_match.group(1).strip()

        # Extract SYNOPSIS
        synopsis_match = re.search(r"SYNOPSIS\s+(.+?)(?:\n\n|DESCRIPTION)", content, re.DOTALL)
        if synopsis_match:
            result["synopsis"] = synopsis_match.group(1).strip()

        # Extract OPTIONS
        options_match = re.search(r"OPTIONS\s+(.+?)(?:\n\n[A-Z]+|$)", content, re.DOTALL)
        if options_match:
            options_text = options_match.group(1)
            # Parse options
            option_blocks = re.findall(
                r"(-[\w-]+(?:,\s*-[\w-]+)*)\s+(.+?)(?=-\w|$)",
                options_text,
                re.DOTALL,
            )
            for opt, desc in option_blocks[:15]:
                result["parameters"].append(
                    {
                        "name": opt.strip(),
                        "description": desc.strip()[:200],
                        "type": "string",
                        "required": False,
                    }
                )

        # Extract EXAMPLES
        examples_match = re.search(r"EXAMPLES?\s+(.+?)(?:\n\n[A-Z]+|$)", content, re.DOTALL)
        if examples_match:
            examples_text = examples_match.group(1)
            # Find command lines (indented or prefixed with $)
            example_lines = re.findall(r"(?:^\s{4,}|\$\s*)(.+)$", examples_text, re.MULTILINE)
            for line in example_lines[:5]:
                if tool_name in line or line.strip().startswith("-"):
                    result["examples"].append(
                        {
                            "command": line.strip(),
                            "description": "Man page example",
                        }
                    )

        return result


class ToolLearner:
    """
    Learns how to use tools from documentation and experience.

    This class enables agents to:
    1. Parse and understand tool documentation
    2. Build knowledge models of tools
    3. Suggest tool usage for tasks
    4. Learn from execution results
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/tools")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.knowledge_base: dict[str, ToolKnowledge] = {}
        self.parser = DocumentationParser()

        # Load existing knowledge
        self._load_knowledge()

        # Pre-populate with common tools
        self._initialize_common_tools()

    def _load_knowledge(self) -> None:
        """Load saved tool knowledge."""
        knowledge_file = self.memory_dir / "tool_knowledge.json"
        if knowledge_file.exists():
            try:
                with open(knowledge_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for name, tool_data in data.items():
                        self.knowledge_base[name] = self._dict_to_knowledge(tool_data)
                logger.info(f"Loaded knowledge for {len(self.knowledge_base)} tools")
            except Exception as e:
                logger.warning(f"Failed to load tool knowledge: {e}")

    def _save_knowledge(self) -> None:
        """Save tool knowledge to disk."""
        knowledge_file = self.memory_dir / "tool_knowledge.json"
        data = {name: k.to_dict() for name, k in self.knowledge_base.items()}
        with open(knowledge_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _dict_to_knowledge(self, data: dict[str, Any]) -> ToolKnowledge:
        """Convert dictionary to ToolKnowledge."""
        return ToolKnowledge(
            name=data["name"],
            description=data["description"],
            category=ToolCategory(data.get("category", "utility")),
            parameters=[
                ToolParameter(
                    name=p["name"],
                    param_type=ParameterType(p.get("type", "string")),
                    description=p["description"],
                    required=p.get("required", False),
                    default=p.get("default"),
                    examples=p.get("examples", []),
                )
                for p in data.get("parameters", [])
            ],
            examples=[
                ToolExample(
                    command=e["command"],
                    description=e["description"],
                    expected_output=e.get("expected_output"),
                )
                for e in data.get("examples", [])
            ],
            common_patterns=data.get("common_patterns", []),
            gotchas=data.get("gotchas", []),
            related_tools=data.get("related_tools", []),
            confidence=data.get("confidence", 0.5),
            usage_count=data.get("usage_count", 0),
            success_rate=data.get("success_rate", 1.0),
        )

    def _initialize_common_tools(self) -> None:
        """Pre-populate knowledge about common tools."""
        common_tools = [
            ToolKnowledge(
                name="grep",
                description="Search for patterns in files using regular expressions",
                category=ToolCategory.TEXT_PROCESSING,
                parameters=[
                    ToolParameter(
                        "pattern", ParameterType.STRING, "The pattern to search for", True
                    ),
                    ToolParameter(
                        "-r", ParameterType.BOOLEAN, "Search recursively in directories", False
                    ),
                    ToolParameter("-i", ParameterType.BOOLEAN, "Case-insensitive search", False),
                    ToolParameter("-n", ParameterType.BOOLEAN, "Show line numbers", False),
                    ToolParameter("-l", ParameterType.BOOLEAN, "Only show filenames", False),
                    ToolParameter(
                        "-v", ParameterType.BOOLEAN, "Invert match (show non-matching)", False
                    ),
                    ToolParameter("-A", ParameterType.NUMBER, "Show N lines after match", False),
                    ToolParameter("-B", ParameterType.NUMBER, "Show N lines before match", False),
                ],
                examples=[
                    ToolExample("grep -r 'TODO' .", "Find all TODO comments recursively"),
                    ToolExample("grep -n 'import' *.py", "Find imports with line numbers"),
                    ToolExample("grep -i 'error' logs/*.log", "Case-insensitive error search"),
                ],
                common_patterns=[
                    "grep -r 'pattern' . --include='*.ext'",
                    "grep -n 'function' file | head -20",
                    "grep -l 'pattern' * | xargs command",
                ],
                gotchas=[
                    "Use -r for recursive search, not -R on all systems",
                    "Quote patterns with special characters",
                    "Use --include to filter file types in recursive search",
                ],
                related_tools=["rg", "ag", "ack", "find"],
                confidence=0.95,
            ),
            ToolKnowledge(
                name="git",
                description="Distributed version control system",
                category=ToolCategory.VERSION_CONTROL,
                parameters=[
                    ToolParameter(
                        "command",
                        ParameterType.STRING,
                        "Git subcommand (status, commit, etc)",
                        True,
                    ),
                ],
                examples=[
                    ToolExample("git status", "Show working tree status"),
                    ToolExample("git diff HEAD~1", "Show changes from last commit"),
                    ToolExample("git log --oneline -10", "Show last 10 commits"),
                    ToolExample("git branch -a", "List all branches"),
                    ToolExample("git stash", "Stash current changes"),
                ],
                common_patterns=[
                    "git add . && git commit -m 'message'",
                    "git checkout -b feature/name",
                    "git fetch origin && git rebase origin/main",
                ],
                gotchas=[
                    "Never force push to shared branches",
                    "Use git stash before switching branches with uncommitted changes",
                    "Avoid git add . in favor of specific files",
                ],
                related_tools=["gh", "git-lfs", "tig"],
                confidence=0.95,
            ),
            ToolKnowledge(
                name="find",
                description="Search for files in a directory hierarchy",
                category=ToolCategory.FILE_SYSTEM,
                parameters=[
                    ToolParameter("path", ParameterType.PATH, "Starting directory", True),
                    ToolParameter("-name", ParameterType.STRING, "Base filename pattern", False),
                    ToolParameter("-type", ParameterType.ENUM, "File type (f=file, d=dir)", False),
                    ToolParameter("-mtime", ParameterType.NUMBER, "Modified time in days", False),
                    ToolParameter(
                        "-exec", ParameterType.STRING, "Execute command on results", False
                    ),
                ],
                examples=[
                    ToolExample("find . -name '*.py'", "Find all Python files"),
                    ToolExample("find . -type d -name 'test*'", "Find test directories"),
                    ToolExample("find . -mtime -7", "Files modified in last 7 days"),
                ],
                common_patterns=[
                    "find . -name '*.log' -delete",
                    "find . -type f -exec grep -l 'pattern' {} +",
                    "find . -size +100M",
                ],
                gotchas=[
                    "Use -print0 with xargs -0 for filenames with spaces",
                    "-exec {} + is more efficient than -exec {} \\;",
                    "Combine with -prune to skip directories",
                ],
                related_tools=["fd", "locate", "ls"],
                confidence=0.90,
            ),
            ToolKnowledge(
                name="npm",
                description="Node.js package manager",
                category=ToolCategory.BUILD_SYSTEM,
                parameters=[
                    ToolParameter("command", ParameterType.STRING, "npm subcommand", True),
                ],
                examples=[
                    ToolExample("npm install", "Install all dependencies"),
                    ToolExample("npm run build", "Run build script"),
                    ToolExample("npm test", "Run tests"),
                    ToolExample("npm audit", "Check for vulnerabilities"),
                ],
                common_patterns=[
                    "npm install --save-dev package",
                    "npm run script -- --arg",
                    "npm ci (clean install for CI)",
                ],
                gotchas=[
                    "Use npm ci in CI environments for reproducible builds",
                    "Lock file (package-lock.json) should be committed",
                    "Use --legacy-peer-deps if peer dependency issues",
                ],
                related_tools=["yarn", "pnpm", "npx"],
                confidence=0.90,
            ),
            ToolKnowledge(
                name="pytest",
                description="Python testing framework",
                category=ToolCategory.TESTING,
                parameters=[
                    ToolParameter("path", ParameterType.PATH, "Test file or directory", False),
                    ToolParameter("-v", ParameterType.BOOLEAN, "Verbose output", False),
                    ToolParameter(
                        "-k", ParameterType.STRING, "Run tests matching expression", False
                    ),
                    ToolParameter("-x", ParameterType.BOOLEAN, "Stop on first failure", False),
                    ToolParameter("--cov", ParameterType.PATH, "Coverage for path", False),
                ],
                examples=[
                    ToolExample("pytest tests/ -v", "Run all tests verbose"),
                    ToolExample("pytest -k 'test_login'", "Run tests with 'test_login' in name"),
                    ToolExample("pytest --cov=src --cov-report=html", "Run with coverage"),
                ],
                common_patterns=[
                    "pytest tests/ -v --tb=short",
                    "pytest -x --pdb (debug on failure)",
                    "pytest --lf (run last failed)",
                ],
                gotchas=[
                    "Test files must be named test_*.py or *_test.py",
                    "Use fixtures for setup/teardown, not setUp methods",
                    "Parametrize tests instead of loops",
                ],
                related_tools=["unittest", "nose", "tox"],
                confidence=0.90,
            ),
        ]

        for tool in common_tools:
            if tool.name not in self.knowledge_base:
                self.knowledge_base[tool.name] = tool

    async def learn_tool(
        self,
        tool_name: str,
        documentation: str,
        examples: list[tuple[str, str]] | None = None,
        doc_format: str = "auto",
    ) -> LearningResult:
        """
        Learn about a tool from its documentation.

        Args:
            tool_name: Name of the tool
            documentation: Documentation content
            examples: Optional list of (command, description) tuples
            doc_format: Format of documentation (auto, readme, docstring, json_schema, man)

        Returns:
            LearningResult with extracted knowledge
        """
        logger.info(f"Learning about tool: {tool_name}")

        # Detect format if auto
        if doc_format == "auto":
            doc_format = self._detect_format(documentation)

        # Parse documentation
        parsed = self._parse_documentation(documentation, tool_name, doc_format)

        # Build examples y parámetros a partir de la doc parseada
        tool_examples = self._build_tool_examples(examples, parsed)
        parameters = self._build_tool_parameters(parsed)

        # Detect category
        category = self._detect_category(tool_name, parsed.get("description", ""))

        # Identify gaps
        gaps = self._identify_knowledge_gaps(parsed, tool_examples, parameters)

        # Create knowledge
        knowledge = ToolKnowledge(
            name=tool_name,
            description=parsed.get("description", f"Tool: {tool_name}"),
            category=category,
            parameters=parameters,
            examples=tool_examples,
            common_patterns=self._extract_patterns(tool_examples),
            gotchas=parsed.get("gotchas", []),
            related_tools=self._find_related_tools(tool_name, category),
            confidence=self._calculate_confidence(parsed, tool_examples, parameters),
        )

        # Store knowledge
        self.knowledge_base[tool_name] = knowledge
        self._save_knowledge()

        # Suggestions for more learning
        suggestions = self._build_learning_suggestions(gaps, knowledge)

        return LearningResult(
            tool_name=tool_name,
            knowledge=knowledge,
            learning_sources=[doc_format],
            gaps_identified=gaps,
            suggestions_for_more_learning=suggestions,
        )

    def _build_tool_examples(
        self,
        examples: list[tuple[str, str]] | None,
        parsed: dict[str, Any],
    ) -> list[ToolExample]:
        """Construye la lista de ejemplos combinando los provistos y los parseados.

        Args:
            examples: Lista opcional de tuplas (comando, descripción) provistas por el caller.
            parsed: Documentación parseada que puede contener ejemplos extraídos.

        Returns:
            Lista de ToolExample con los ejemplos provistos seguidos de los parseados.
        """
        tool_examples: list[ToolExample] = []
        if examples:
            for cmd, desc in examples:
                tool_examples.append(ToolExample(command=cmd, description=desc))
        for ex in parsed.get("examples", []):
            tool_examples.append(
                ToolExample(
                    command=ex["command"],
                    description=ex["description"],
                    expected_output=ex.get("expected_output"),
                )
            )
        return tool_examples

    def _build_tool_parameters(self, parsed: dict[str, Any]) -> list[ToolParameter]:
        """Construye la lista de parámetros desde la documentación parseada.

        Args:
            parsed: Documentación parseada que puede contener parámetros.

        Returns:
            Lista de ToolParameter con el tipo normalizado a ParameterType.
        """
        parameters: list[ToolParameter] = []
        for p in parsed.get("parameters", []):
            parameters.append(
                ToolParameter(
                    name=p["name"],
                    param_type=ParameterType(p.get("type", "string"))
                    if p.get("type") in [e.value for e in ParameterType]
                    else ParameterType.STRING,
                    description=p["description"],
                    required=p.get("required", False),
                    default=p.get("default"),
                )
            )
        return parameters

    def _identify_knowledge_gaps(
        self,
        parsed: dict[str, Any],
        tool_examples: list[ToolExample],
        parameters: list[ToolParameter],
    ) -> list[str]:
        """Identifica vacíos en el conocimiento extraído de la herramienta.

        Args:
            parsed: Documentación parseada.
            tool_examples: Ejemplos construidos.
            parameters: Parámetros construidos.

        Returns:
            Lista de descripciones de vacíos detectados.
        """
        gaps: list[str] = []
        if not tool_examples:
            gaps.append("No usage examples found")
        if not parameters:
            gaps.append("No parameters documented")
        if len(parsed.get("description", "")) < 50:
            gaps.append("Description is too brief")
        return gaps

    def _build_learning_suggestions(
        self,
        gaps: list[str],
        knowledge: ToolKnowledge,
    ) -> list[str]:
        """Genera sugerencias para profundizar el aprendizaje de la herramienta.

        Args:
            gaps: Vacíos de conocimiento detectados.
            knowledge: Conocimiento construido sobre la herramienta.

        Returns:
            Lista de sugerencias accionables para aprender más.
        """
        suggestions: list[str] = []
        if gaps:
            suggestions.append(f"Find more documentation to address: {', '.join(gaps)}")
        if knowledge.confidence < 0.7:
            suggestions.append("Try the tool with different inputs to learn its behavior")
        if not knowledge.gotchas:
            suggestions.append("Look for common mistakes or edge cases")
        return suggestions

    def _detect_format(self, content: str) -> str:
        """Detect documentation format."""
        if content.strip().startswith("{"):
            return "json_schema"
        if "NAME\n" in content and "SYNOPSIS" in content:
            return "man"
        if "Args:" in content or "Parameters:" in content:
            return "docstring"
        return "readme"

    def _parse_documentation(
        self,
        content: str,
        tool_name: str,
        doc_format: str,
    ) -> dict[str, Any]:
        """Parse documentation based on format."""
        if doc_format == "readme":
            return self.parser.parse_readme(content, tool_name)
        elif doc_format == "docstring":
            return self.parser.parse_docstring(content, tool_name)
        elif doc_format == "json_schema":
            return self.parser.parse_json_schema(content, tool_name)
        elif doc_format == "man":
            return self.parser.parse_man_page(content, tool_name)
        else:
            # Try all parsers and combine results
            results = {}
            for parser_method in [
                self.parser.parse_readme,
                self.parser.parse_docstring,
            ]:
                try:
                    parsed = parser_method(content, tool_name)
                    for key, value in parsed.items():
                        if value and not results.get(key):
                            results[key] = value
                except Exception:
                    continue
            return results

    def _detect_category(self, tool_name: str, description: str) -> ToolCategory:
        """Detect tool category from name and description."""
        text = f"{tool_name} {description}".lower()

        category_keywords = {
            ToolCategory.FILE_SYSTEM: ["file", "directory", "path", "folder", "fs"],
            ToolCategory.TEXT_PROCESSING: ["text", "string", "search", "grep", "sed", "awk"],
            ToolCategory.VERSION_CONTROL: ["git", "version", "commit", "branch", "merge"],
            ToolCategory.BUILD_SYSTEM: ["build", "compile", "npm", "pip", "maven", "gradle"],
            ToolCategory.TESTING: ["test", "pytest", "jest", "mocha", "unittest"],
            ToolCategory.DEPLOYMENT: ["deploy", "docker", "kubernetes", "k8s", "helm"],
            ToolCategory.DATABASE: ["database", "sql", "mongo", "redis", "postgres"],
            ToolCategory.NETWORK: ["http", "curl", "wget", "network", "api"],
            ToolCategory.AI_ML: ["ai", "ml", "model", "train", "predict"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                return category

        return ToolCategory.UTILITY

    def _extract_patterns(self, examples: list[ToolExample]) -> list[str]:
        """Extract common usage patterns from examples."""
        patterns = []
        for ex in examples:
            # Generalize the command
            pattern = ex.command
            # Replace specific values with placeholders
            pattern = re.sub(r"'[^']*'", "'<value>'", pattern)
            pattern = re.sub(r'"[^"]*"', '"<value>"', pattern)
            pattern = re.sub(r"\d+", "<number>", pattern)
            if pattern not in patterns:
                patterns.append(pattern)
        return patterns[:5]

    def _find_related_tools(self, tool_name: str, category: ToolCategory) -> list[str]:
        """Find related tools based on category."""
        related = []
        for name, knowledge in self.knowledge_base.items():
            if name != tool_name and knowledge.category == category:
                related.append(name)
        return related[:5]

    def _calculate_confidence(
        self,
        parsed: dict[str, Any],
        examples: list[ToolExample],
        parameters: list[ToolParameter],
    ) -> float:
        """Calculate confidence in our understanding of the tool."""
        confidence = 0.3  # Base confidence

        # Add confidence for description
        if len(parsed.get("description", "")) > 100:
            confidence += 0.15
        elif len(parsed.get("description", "")) > 50:
            confidence += 0.10

        # Add confidence for examples
        if len(examples) >= 3:
            confidence += 0.20
        elif len(examples) >= 1:
            confidence += 0.10

        # Add confidence for parameters
        if len(parameters) >= 5:
            confidence += 0.20
        elif len(parameters) >= 2:
            confidence += 0.10

        # Add confidence for gotchas (shows deep understanding)
        if parsed.get("gotchas"):
            confidence += 0.15

        return min(confidence, 0.95)

    async def suggest_usage(
        self,
        tool_name: str,
        task: str,
    ) -> UsageSuggestion:
        """
        Suggest how to use a tool for a specific task.

        Args:
            tool_name: Name of the tool
            task: What the user wants to accomplish

        Returns:
            UsageSuggestion with recommended usage
        """
        if tool_name not in self.knowledge_base:
            return UsageSuggestion(
                command=f"{tool_name} --help",
                explanation=f"Tool '{tool_name}' not in knowledge base. Try running with --help to learn more.",
                confidence=0.2,
                alternatives=[],
                warnings=["Tool knowledge not available"],
                expected_result="Help output",
            )

        knowledge = self.knowledge_base[tool_name]
        task_lower = task.lower()

        best_example, best_score = self._find_best_example(knowledge, task_lower)
        command, explanation, confidence = self._build_command_suggestion(
            tool_name, knowledge, best_example, best_score, task_lower
        )
        alternatives = self._collect_alternatives(knowledge)
        warnings = self._collect_warnings(knowledge, task_lower)

        return UsageSuggestion(
            command=command,
            explanation=explanation,
            confidence=confidence,
            alternatives=alternatives,
            warnings=warnings,
            expected_result=best_example.expected_output
            if best_example and best_example.expected_output
            else "Tool output",
        )

    @staticmethod
    def _find_best_example(
        knowledge: "ToolKnowledge", task_lower: str
    ) -> tuple["ToolExample | None", int]:
        """Encuentra el ejemplo con mayor solapamiento de keywords con la tarea.

        Args:
            knowledge: Conocimiento de la herramienta.
            task_lower: Descripción de la tarea en minúsculas.

        Returns:
            Tupla (mejor ejemplo o None, score de solapamiento).
        """
        best_example: ToolExample | None = None
        best_score = 0
        task_words = set(task_lower.split())
        for example in knowledge.examples:
            desc_words = set(example.description.lower().split())
            overlap = len(desc_words & task_words)
            if overlap > best_score:
                best_score = overlap
                best_example = example
        return best_example, best_score

    @staticmethod
    def _build_command_suggestion(
        tool_name: str,
        knowledge: "ToolKnowledge",
        best_example: "ToolExample | None",
        best_score: int,
        task_lower: str,
    ) -> tuple[str, str, float]:
        """Construye comando, explicación y confianza a partir del mejor ejemplo.

        Args:
            tool_name: Nombre de la herramienta.
            knowledge: Conocimiento de la herramienta.
            best_example: Mejor ejemplo encontrado, si existe.
            best_score: Score de solapamiento del mejor ejemplo.
            task_lower: Descripción de la tarea en minúsculas.

        Returns:
            Tupla (comando, explicación, confianza).
        """
        if best_example:
            command = best_example.command
            explanation = f"Based on example: {best_example.description}"
            confidence = min(
                0.8, knowledge.confidence * (best_score / max(len(task_lower.split()), 1))
            )
            return command, explanation, confidence

        command = tool_name
        for param in knowledge.parameters[:3]:
            if param.required:
                command += f" {param.name}"
        return command, "Generic usage based on required parameters", 0.4

    def _collect_alternatives(self, knowledge: "ToolKnowledge") -> list[str]:
        """Reúne comandos alternativos desde las herramientas relacionadas.

        Args:
            knowledge: Conocimiento de la herramienta.

        Returns:
            Lista de strings con alternativas en formato "tool: command".
        """
        alternatives: list[str] = []
        for related in knowledge.related_tools[:3]:
            if related in self.knowledge_base:
                related_knowledge = self.knowledge_base[related]
                if related_knowledge.examples:
                    alternatives.append(f"{related}: {related_knowledge.examples[0].command}")
        return alternatives

    @staticmethod
    def _collect_warnings(knowledge: "ToolKnowledge", task_lower: str) -> list[str]:
        """Selecciona gotchas relevantes a la tarea como warnings.

        Args:
            knowledge: Conocimiento de la herramienta.
            task_lower: Descripción de la tarea en minúsculas.

        Returns:
            Lista de gotchas que matchean keywords de la tarea.
        """
        warnings: list[str] = []
        for gotcha in knowledge.gotchas[:2]:
            if any(word in task_lower for word in gotcha.lower().split()[:5]):
                warnings.append(gotcha)
        return warnings

    async def record_usage(
        self,
        tool_name: str,
        command: str,
        success: bool,
        output: str | None = None,
        error: str | None = None,
    ) -> None:
        """
        Record tool usage result for learning.

        Args:
            tool_name: Name of the tool
            command: Command that was executed
            success: Whether execution succeeded
            output: Command output (if available)
            error: Error message (if failed)
        """
        if tool_name not in self.knowledge_base:
            # Create minimal knowledge entry
            await self.learn_tool(
                tool_name=tool_name,
                documentation=f"Tool: {tool_name}\n\nUsed with command: {command}",
                examples=[(command, "Recorded usage")],
            )
            return

        knowledge = self.knowledge_base[tool_name]

        # Update usage statistics
        knowledge.usage_count += 1
        total = knowledge.usage_count
        current_rate = knowledge.success_rate
        knowledge.success_rate = ((current_rate * (total - 1)) + (1.0 if success else 0.0)) / total

        # Learn from failures
        if not success and error:
            # Extract lesson from error
            if error not in knowledge.gotchas:
                knowledge.gotchas.append(f"Error encountered: {error[:100]}")
                knowledge.gotchas = knowledge.gotchas[:10]  # Keep last 10

        # Learn from successes
        if success and command:
            # Add as example if unique
            existing_commands = {ex.command for ex in knowledge.examples}
            if command not in existing_commands:
                knowledge.examples.append(
                    ToolExample(
                        command=command,
                        description="Successful usage",
                        expected_output=output[:200] if output else None,
                    )
                )
                knowledge.examples = knowledge.examples[:10]  # Keep last 10

        # Update confidence based on experience
        if knowledge.usage_count > 5:
            experience_bonus = min(0.1, knowledge.usage_count * 0.01)
            knowledge.confidence = min(
                0.95, knowledge.confidence + experience_bonus * knowledge.success_rate
            )

        knowledge.last_updated = datetime.now()
        self._save_knowledge()

        logger.info(
            f"Recorded {tool_name} usage: success={success}, total_uses={knowledge.usage_count}"
        )

    def get_knowledge(self, tool_name: str) -> ToolKnowledge | None:
        """Get knowledge about a tool."""
        return self.knowledge_base.get(tool_name)

    def list_known_tools(self) -> list[str]:
        """List all known tools."""
        return list(self.knowledge_base.keys())

    def get_tools_by_category(self, category: ToolCategory) -> list[ToolKnowledge]:
        """Get all tools in a category."""
        return [k for k in self.knowledge_base.values() if k.category == category]

    def export_knowledge(self, tool_name: str | None = None) -> str:
        """Export knowledge as markdown."""
        if tool_name:
            tools = [self.knowledge_base.get(tool_name)] if tool_name in self.knowledge_base else []
        else:
            tools = list(self.knowledge_base.values())

        lines = ["# Tool Knowledge Base\n"]

        for tool in tools:
            if not tool:
                continue
            lines.extend(
                [
                    f"## {tool.name}",
                    "",
                    f"**Category:** {tool.category.value}",
                    f"**Confidence:** {tool.confidence:.0%}",
                    f"**Usage Count:** {tool.usage_count}",
                    f"**Success Rate:** {tool.success_rate:.0%}",
                    "",
                    "### Description",
                    tool.description,
                    "",
                    "### Parameters",
                ]
            )

            for param in tool.parameters:
                req = "required" if param.required else "optional"
                lines.append(
                    f"- `{param.name}` ({param.param_type.value}, {req}): {param.description}"
                )

            if tool.examples:
                lines.extend(["", "### Examples"])
                for ex in tool.examples:
                    lines.append(f"- `{ex.command}` - {ex.description}")

            if tool.gotchas:
                lines.extend(["", "### Gotchas"])
                for gotcha in tool.gotchas:
                    lines.append(f"- {gotcha}")

            if tool.related_tools:
                lines.extend(["", f"**Related:** {', '.join(tool.related_tools)}"])

            lines.extend(["", "---", ""])

        return "\n".join(lines)


# Convenience function
async def learn_tool(
    tool_name: str,
    documentation: str,
    examples: list[tuple[str, str]] | None = None,
) -> LearningResult:
    """Quick function to learn about a tool."""
    learner = ToolLearner()
    return await learner.learn_tool(tool_name, documentation, examples)
