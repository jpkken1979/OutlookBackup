#!/usr/bin/env python3
"""
Explorer Agent - Deep Codebase Investigation

Capabilities:
- Search code by pattern, function, class, or concept
- Trace function calls and dependencies
- Find related code across the codebase
- Analyze code flow and data flow
- Generate code maps and summaries
"""

import ast
import asyncio
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CodeLocation:
    """A location in the codebase."""

    file: str
    line: int
    column: int = 0
    snippet: str = ""
    context: str = ""


@dataclass
class CodeEntity:
    """A code entity (function, class, variable)."""

    name: str
    type: str  # function, class, method, variable
    location: CodeLocation
    signature: str = ""
    docstring: str = ""
    calls: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Search result."""

    query: str
    total_matches: int
    entities: list[CodeEntity] = field(default_factory=list)
    locations: list[CodeLocation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total_matches": self.total_matches,
            "entities": [
                {
                    "name": e.name,
                    "type": e.type,
                    "file": e.location.file,
                    "line": e.location.line,
                    "signature": e.signature,
                }
                for e in self.entities
            ],
            "locations": [
                {"file": l.file, "line": l.line, "snippet": l.snippet} for l in self.locations
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Search Results: `{self.query}`",
            "",
            f"**Total Matches:** {self.total_matches}",
            "",
        ]

        if self.entities:
            lines.append("## Code Entities")
            for entity in self.entities[:20]:
                lines.append(f"### {entity.type}: `{entity.name}`")
                lines.append(f"- **File:** {entity.location.file}:{entity.location.line}")
                if entity.signature:
                    lines.append(f"- **Signature:** `{entity.signature}`")
                if entity.docstring:
                    lines.append(f"- **Doc:** {entity.docstring[:100]}...")
                lines.append("")

        if self.locations:
            lines.append("## All Matches")
            for loc in self.locations[:30]:
                lines.append(f"- `{loc.file}:{loc.line}` - {loc.snippet[:60]}...")

        return "\n".join(lines)


@dataclass
class DependencyTrace:
    """Trace of dependencies for a function/class."""

    target: str
    direct_deps: list[str] = field(default_factory=list)
    transitive_deps: list[str] = field(default_factory=list)
    callers: list[str] = field(default_factory=list)
    call_graph: dict = field(default_factory=dict)


class ExplorerAgent:
    """
    Deep Codebase Explorer Agent.

    Provides powerful code search and analysis capabilities.
    """

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self._index: dict = {}
        self._call_graph: dict = defaultdict(list)

    async def search(
        self,
        query: str,
        search_type: str = "all",  # all, function, class, text
        file_pattern: str = "*.py",
    ) -> SearchResult:
        """
        Search the codebase.

        Args:
            query: Search query (name, pattern, or text)
            search_type: Type of search
            file_pattern: File pattern to search

        Returns:
            SearchResult with matches
        """
        logger.info(f"Searching for: {query} (type: {search_type})")

        entities = []
        locations = []

        for file_path in self.project_path.rglob(file_pattern):
            if self._should_skip(file_path):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))

                # Search based on type
                if search_type in ["all", "function", "class"]:
                    file_entities = self._extract_entities(content, rel_path)
                    for entity in file_entities:
                        if query.lower() in entity.name.lower():
                            entities.append(entity)

                # Text search
                if search_type in ["all", "text"]:
                    for i, line in enumerate(content.splitlines(), 1):
                        if query.lower() in line.lower():
                            locations.append(
                                CodeLocation(file=rel_path, line=i, snippet=line.strip())
                            )

            except Exception as e:
                logger.debug(f"Error processing {file_path}: {e}")

        return SearchResult(
            query=query,
            total_matches=len(entities) + len(locations),
            entities=entities,
            locations=locations,
        )

    async def find_function(self, name: str) -> CodeEntity | None:
        """Find a function by name."""
        result = await self.search(name, search_type="function")
        functions = [e for e in result.entities if e.type in ["function", "method"]]
        return functions[0] if functions else None

    async def find_class(self, name: str) -> CodeEntity | None:
        """Find a class by name."""
        result = await self.search(name, search_type="class")
        classes = [e for e in result.entities if e.type == "class"]
        return classes[0] if classes else None

    async def trace_dependencies(self, target: str) -> DependencyTrace:
        """Trace dependencies for a function or class."""
        logger.info(f"Tracing dependencies for: {target}")

        # Build index if not done
        if not self._index:
            await self._build_index()

        direct_deps = []
        transitive_deps = []
        callers = []

        # Find direct dependencies
        if target in self._call_graph:
            direct_deps = self._call_graph[target]

            # Find transitive dependencies (depth 2)
            for dep in direct_deps:
                if dep in self._call_graph:
                    for trans_dep in self._call_graph[dep]:
                        if trans_dep not in direct_deps and trans_dep != target:
                            transitive_deps.append(trans_dep)

        # Find callers
        for name, calls in self._call_graph.items():
            if target in calls:
                callers.append(name)

        return DependencyTrace(
            target=target,
            direct_deps=list(set(direct_deps)),
            transitive_deps=list(set(transitive_deps)),
            callers=callers,
            call_graph={target: direct_deps},
        )

    async def find_related_code(self, query: str, max_results: int = 20) -> list[CodeLocation]:
        """Find code related to a concept or pattern."""
        logger.info(f"Finding code related to: {query}")

        # Expand query with synonyms
        expanded_queries = self._expand_query(query)

        all_locations = []
        for exp_query in expanded_queries:
            result = await self.search(exp_query, search_type="text")
            all_locations.extend(result.locations)

        # Deduplicate and rank
        seen = set()
        unique_locations = []
        for loc in all_locations:
            key = f"{loc.file}:{loc.line}"
            if key not in seen:
                seen.add(key)
                unique_locations.append(loc)

        return unique_locations[:max_results]

    async def get_code_map(self) -> dict:
        """Generate a map of the codebase structure."""
        logger.info("Generating code map")

        code_map = {
            "modules": [],
            "classes": [],
            "functions": [],
            "files_by_type": defaultdict(list),
        }

        for file_path in self.project_path.rglob("*.py"):
            if self._should_skip(file_path):
                continue

            rel_path = str(file_path.relative_to(self.project_path))

            # Categorize by directory
            parts = Path(rel_path).parts
            category = parts[0] if len(parts) > 1 else "root"

            code_map["files_by_type"][category].append(rel_path)

            try:
                content = file_path.read_text(errors="ignore")
                entities = self._extract_entities(content, rel_path)

                for entity in entities:
                    if entity.type == "class":
                        code_map["classes"].append(
                            {"name": entity.name, "file": rel_path, "line": entity.location.line}
                        )
                    elif entity.type in ["function", "method"]:
                        code_map["functions"].append(
                            {"name": entity.name, "file": rel_path, "line": entity.location.line}
                        )

            except Exception:
                pass

        code_map["files_by_type"] = dict(code_map["files_by_type"])
        return code_map

    async def analyze_file(self, file_path: str) -> dict:
        """Analyze a specific file."""
        full_path = self.project_path / file_path

        if not full_path.exists():
            return {"error": f"File not found: {file_path}"}

        content = full_path.read_text(errors="ignore")
        entities = self._extract_entities(content, file_path)

        lines = content.splitlines()
        imports = [l for l in lines if l.strip().startswith(("import ", "from "))]

        return {
            "file": file_path,
            "lines": len(lines),
            "imports": imports,
            "classes": [e.name for e in entities if e.type == "class"],
            "functions": [e.name for e in entities if e.type in ["function", "method"]],
            "entities": [
                {
                    "name": e.name,
                    "type": e.type,
                    "line": e.location.line,
                    "signature": e.signature,
                    "docstring": e.docstring[:100] if e.docstring else None,
                }
                for e in entities
            ],
        }

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {"venv", "node_modules", "__pycache__", ".git", "dist", "build", ".tox", "env"}
        return any(part in skip_dirs for part in path.parts)

    def _extract_entities(self, content: str, file_path: str) -> list[CodeEntity]:
        """Extract code entities using AST."""
        entities = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    entities.append(
                        CodeEntity(
                            name=node.name,
                            type="class",
                            location=CodeLocation(file=file_path, line=node.lineno),
                            docstring=ast.get_docstring(node) or "",
                        )
                    )

                elif isinstance(node, ast.FunctionDef):
                    # Determine if method or function
                    func_type = "method" if self._is_method(node, tree) else "function"

                    # Build signature
                    args = [a.arg for a in node.args.args]
                    signature = f"{node.name}({', '.join(args)})"

                    # Extract calls
                    calls = self._extract_calls(node)

                    entities.append(
                        CodeEntity(
                            name=node.name,
                            type=func_type,
                            location=CodeLocation(file=file_path, line=node.lineno),
                            signature=signature,
                            docstring=ast.get_docstring(node) or "",
                            calls=calls,
                        )
                    )

                elif isinstance(node, ast.AsyncFunctionDef):
                    args = [a.arg for a in node.args.args]
                    signature = f"async {node.name}({', '.join(args)})"

                    entities.append(
                        CodeEntity(
                            name=node.name,
                            type="async_function",
                            location=CodeLocation(file=file_path, line=node.lineno),
                            signature=signature,
                            docstring=ast.get_docstring(node) or "",
                        )
                    )

        except SyntaxError:
            # Fall back to regex for non-parseable files
            entities.extend(self._extract_entities_regex(content, file_path))

        return entities

    def _extract_entities_regex(self, content: str, file_path: str) -> list[CodeEntity]:
        """Extract entities using regex (fallback)."""
        entities = []
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            # Classes
            class_match = re.match(r"^class\s+(\w+)", line)
            if class_match:
                entities.append(
                    CodeEntity(
                        name=class_match.group(1),
                        type="class",
                        location=CodeLocation(file=file_path, line=i),
                    )
                )

            # Functions
            func_match = re.match(r"^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", line)
            if func_match:
                entities.append(
                    CodeEntity(
                        name=func_match.group(1),
                        type="function",
                        location=CodeLocation(file=file_path, line=i),
                        signature=f"{func_match.group(1)}({func_match.group(2)})",
                    )
                )

        return entities

    def _is_method(self, node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Check if function is a method."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in parent.body:
                    if child is node:
                        return True
        return False

    def _extract_calls(self, node: ast.FunctionDef) -> list[str]:
        """Extract function calls from a function."""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return list(set(calls))

    def _expand_query(self, query: str) -> list[str]:
        """Expand query with related terms."""
        expansions = [query]

        # Common expansions
        synonyms = {
            "auth": ["authentication", "login", "session", "token", "jwt"],
            "db": ["database", "query", "model", "repository"],
            "api": ["endpoint", "route", "controller", "handler"],
            "test": ["spec", "unittest", "pytest", "mock"],
            "config": ["settings", "env", "environment", "configuration"],
            "error": ["exception", "raise", "try", "catch", "handle"],
        }

        query_lower = query.lower()
        for key, values in synonyms.items():
            if key in query_lower:
                expansions.extend(values)

        return list(set(expansions))

    async def _build_index(self) -> None:
        """Build search index."""
        logger.info("Building code index")

        for file_path in self.project_path.rglob("*.py"):
            if self._should_skip(file_path):
                continue

            try:
                content = file_path.read_text(errors="ignore")
                rel_path = str(file_path.relative_to(self.project_path))
                entities = self._extract_entities(content, rel_path)

                for entity in entities:
                    self._index[entity.name] = entity
                    if entity.calls:
                        self._call_graph[entity.name] = entity.calls

            except Exception:
                pass


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Explorer Agent")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--path", default=".", help="Project path")
    parser.add_argument("--type", choices=["all", "function", "class", "text"], default="all")
    parser.add_argument("--trace", help="Trace dependencies for a function/class")
    parser.add_argument("--map", action="store_true", help="Generate code map")
    parser.add_argument("--analyze", help="Analyze a specific file")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    agent = ExplorerAgent(args.path)

    if args.trace:
        trace = await agent.trace_dependencies(args.trace)
        print(json.dumps(trace.__dict__, indent=2))

    elif args.map:
        code_map = await agent.get_code_map()
        print(json.dumps(code_map, indent=2, default=list))

    elif args.analyze:
        analysis = await agent.analyze_file(args.analyze)
        print(json.dumps(analysis, indent=2))

    elif args.query:
        result = await agent.search(args.query, args.type)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.to_markdown())

    else:
        # Default: show code map summary
        code_map = await agent.get_code_map()
        print(f"Classes: {len(code_map['classes'])}")
        print(f"Functions: {len(code_map['functions'])}")
        print(f"Directories: {list(code_map['files_by_type'].keys())}")


if __name__ == "__main__":
    asyncio.run(main())
