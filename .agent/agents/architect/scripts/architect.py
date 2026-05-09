#!/usr/bin/env python3
"""
Architect Agent - System Design and Architecture Analysis

Capabilities:
- Analyze codebase architecture
- Generate architecture diagrams (Mermaid)
- Identify architectural patterns and anti-patterns
- Recommend improvements
- Design new system components
"""

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
class Component:
    """A system component."""

    name: str
    type: str  # service, module, class, function
    path: str
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


@dataclass
class ArchitecturePattern:
    """An identified architecture pattern."""

    name: str
    description: str
    locations: list[str] = field(default_factory=list)
    quality: str = "good"  # good, warning, bad


@dataclass
class ArchitectureAnalysis:
    """Complete architecture analysis."""

    project_name: str
    components: list[Component] = field(default_factory=list)
    patterns: list[ArchitecturePattern] = field(default_factory=list)
    layers: dict = field(default_factory=dict)
    dependencies_graph: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    mermaid_diagram: str = ""

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "components_count": len(self.components),
            "patterns": [
                {"name": p.name, "quality": p.quality, "locations": p.locations}
                for p in self.patterns
            ],
            "layers": self.layers,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Architecture Analysis: {self.project_name}",
            "",
            "## Overview",
            f"- **Components:** {len(self.components)}",
            f"- **Patterns Identified:** {len(self.patterns)}",
            f"- **Layers:** {len(self.layers)}",
            "",
            "## Architecture Diagram",
            "```mermaid",
            self.mermaid_diagram,
            "```",
            "",
            "## Patterns Identified",
        ]

        for pattern in self.patterns:
            icon = (
                "✅" if pattern.quality == "good" else "⚠️" if pattern.quality == "warning" else "❌"
            )
            lines.append(f"### {icon} {pattern.name}")
            lines.append(f"{pattern.description}")
            if pattern.locations:
                lines.append(f"- Locations: {', '.join(pattern.locations[:5])}")
            lines.append("")

        if self.recommendations:
            lines.append("## Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)


class ArchitectAgent:
    """
    System Architect Agent.

    Analyzes codebases to understand and improve architecture.
    """

    # Common architectural patterns
    PATTERNS = {
        "mvc": {
            "indicators": ["controller", "model", "view", "routes"],
            "description": "Model-View-Controller pattern for separation of concerns",
        },
        "layered": {
            "indicators": ["service", "repository", "controller", "domain", "infrastructure"],
            "description": "Layered architecture with clear separation",
        },
        "microservices": {
            "indicators": ["service", "gateway", "api", "grpc", "kafka", "rabbitmq"],
            "description": "Microservices architecture with distributed services",
        },
        "clean_architecture": {
            "indicators": ["domain", "usecase", "entity", "repository", "presenter"],
            "description": "Clean Architecture with dependency inversion",
        },
        "hexagonal": {
            "indicators": ["port", "adapter", "domain", "application"],
            "description": "Hexagonal/Ports and Adapters architecture",
        },
        "event_driven": {
            "indicators": ["event", "handler", "listener", "publisher", "subscriber"],
            "description": "Event-driven architecture",
        },
        "cqrs": {
            "indicators": ["command", "query", "handler", "read_model", "write_model"],
            "description": "Command Query Responsibility Segregation",
        },
    }

    # Anti-patterns
    ANTI_PATTERNS = {
        "god_class": {
            "check": lambda lines: lines > 500,
            "description": "Class with too many responsibilities (>500 lines)",
        },
        "circular_dependency": {
            "check": lambda deps: len(deps) > 10,
            "description": "Circular or excessive dependencies",
        },
        "deep_nesting": {
            "check": lambda depth: depth > 4,
            "description": "Deeply nested directory structure",
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> ArchitectureAnalysis:
        """Analyze the project architecture."""
        logger.info(f"Analyzing architecture of: {self.project_path}")

        # Discover components
        components = await self._discover_components()
        logger.info(f"Found {len(components)} components")

        # Identify patterns
        patterns = self._identify_patterns(components)

        # Identify layers
        layers = self._identify_layers(components)

        # Build dependency graph
        dep_graph = self._build_dependency_graph(components)

        # Calculate metrics
        metrics = self._calculate_metrics(components, dep_graph)

        # Generate recommendations
        recommendations = self._generate_recommendations(components, patterns, metrics)

        # Generate Mermaid diagram
        mermaid = self._generate_mermaid_diagram(components, layers)

        return ArchitectureAnalysis(
            project_name=self.project_path.name,
            components=components,
            patterns=patterns,
            layers=layers,
            dependencies_graph=dep_graph,
            metrics=metrics,
            recommendations=recommendations,
            mermaid_diagram=mermaid,
        )

    async def _discover_components(self) -> list[Component]:
        """Discover project components."""
        components = []

        # Find Python modules
        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip(py_file):
                continue

            rel_path = str(py_file.relative_to(self.project_path))

            # Determine component type
            comp_type = self._classify_component(py_file)

            # Extract dependencies (imports)
            deps = self._extract_imports(py_file)

            # Calculate metrics
            metrics = self._file_metrics(py_file)

            components.append(
                Component(
                    name=py_file.stem,
                    type=comp_type,
                    path=rel_path,
                    dependencies=deps,
                    metrics=metrics,
                )
            )

        return components

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {"venv", "node_modules", "__pycache__", ".git", "dist", "build", ".tox"}
        return any(part in skip_dirs for part in path.parts)

    def _classify_component(self, path: Path) -> str:
        """Classify component type based on path and content."""
        path_str = str(path).lower()

        if "test" in path_str:
            return "test"
        elif "model" in path_str or "schema" in path_str:
            return "model"
        elif "controller" in path_str or "route" in path_str or "view" in path_str:
            return "controller"
        elif "service" in path_str:
            return "service"
        elif "repository" in path_str or "dao" in path_str:
            return "repository"
        elif "util" in path_str or "helper" in path_str:
            return "utility"
        elif "config" in path_str:
            return "config"
        elif "middleware" in path_str:
            return "middleware"
        else:
            return "module"

    def _extract_imports(self, path: Path) -> list[str]:
        """Extract imports from Python file."""
        imports = []
        try:
            content = path.read_text(errors="ignore")

            # Match import statements
            import_pattern = r"^(?:from\s+(\S+)|import\s+(\S+))"
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module.split(".")[0])
        except Exception:
            pass

        return list(set(imports))

    def _file_metrics(self, path: Path) -> dict:
        """Calculate file metrics."""
        try:
            content = path.read_text(errors="ignore")
            lines = content.splitlines()

            return {
                "lines": len(lines),
                "code_lines": len(
                    [l for l in lines if l.strip() and not l.strip().startswith("#")]
                ),
                "classes": len(re.findall(r"^class\s+", content, re.MULTILINE)),
                "functions": len(re.findall(r"^(?:async\s+)?def\s+", content, re.MULTILINE)),
            }
        except Exception:
            return {}

    def _identify_patterns(self, components: list[Component]) -> list[ArchitecturePattern]:
        """Identify architectural patterns."""
        patterns = []
        all_paths = [c.path.lower() for c in components]
        all_names = [c.name.lower() for c in components]
        combined = all_paths + all_names

        for pattern_name, pattern_info in self.PATTERNS.items():
            matches = []
            for indicator in pattern_info["indicators"]:
                for item in combined:
                    if indicator in item:
                        matches.append(item)

            if len(matches) >= 2:
                patterns.append(
                    ArchitecturePattern(
                        name=pattern_name.replace("_", " ").title(),
                        description=pattern_info["description"],
                        locations=list(set(matches))[:5],
                        quality="good",
                    )
                )

        # Check for anti-patterns
        for comp in components:
            if comp.metrics.get("lines", 0) > 500:
                patterns.append(
                    ArchitecturePattern(
                        name="God Class Warning",
                        description=f"Large file detected: {comp.path} ({comp.metrics['lines']} lines)",
                        locations=[comp.path],
                        quality="warning",
                    )
                )

        return patterns

    def _identify_layers(self, components: list[Component]) -> dict:
        """Identify architectural layers."""
        layers = defaultdict(list)

        layer_mapping = {
            "presentation": ["controller", "view", "route", "api"],
            "application": ["service", "usecase", "handler"],
            "domain": ["model", "entity", "domain"],
            "infrastructure": ["repository", "database", "external"],
            "common": ["utility", "helper", "config", "middleware"],
        }

        for comp in components:
            assigned = False
            for layer, keywords in layer_mapping.items():
                if any(kw in comp.path.lower() or kw in comp.type.lower() for kw in keywords):
                    layers[layer].append(comp.name)
                    assigned = True
                    break

            if not assigned:
                layers["other"].append(comp.name)

        return dict(layers)

    def _build_dependency_graph(self, components: list[Component]) -> dict:
        """Build dependency graph."""
        graph = {}
        comp_names = {c.name for c in components}

        for comp in components:
            internal_deps = [d for d in comp.dependencies if d in comp_names]
            graph[comp.name] = internal_deps

        return graph

    def _calculate_metrics(self, components: list[Component], dep_graph: dict) -> dict:
        """Calculate architecture metrics."""
        total_lines = sum(c.metrics.get("lines", 0) for c in components)
        total_classes = sum(c.metrics.get("classes", 0) for c in components)
        total_functions = sum(c.metrics.get("functions", 0) for c in components)

        # Calculate coupling
        total_deps = sum(len(deps) for deps in dep_graph.values())
        avg_coupling = total_deps / len(components) if components else 0

        return {
            "total_components": len(components),
            "total_lines": total_lines,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "average_coupling": round(avg_coupling, 2),
            "largest_component": max((c.metrics.get("lines", 0) for c in components), default=0),
        }

    def _generate_recommendations(
        self, components: list[Component], patterns: list[ArchitecturePattern], metrics: dict
    ) -> list[str]:
        """Generate architecture recommendations."""
        recommendations = []

        # Check for large components
        large_components = [c for c in components if c.metrics.get("lines", 0) > 300]
        if large_components:
            recommendations.append(
                f"Consider refactoring {len(large_components)} large files (>300 lines) "
                "into smaller, focused modules"
            )

        # Check coupling
        if metrics.get("average_coupling", 0) > 5:
            recommendations.append(
                "High average coupling detected. Consider introducing interfaces "
                "or dependency injection to reduce coupling"
            )

        # Check for missing patterns
        has_service_layer = any("service" in c.type for c in components)
        has_repository = any("repository" in c.type for c in components)

        if not has_service_layer:
            recommendations.append("Consider adding a service layer to encapsulate business logic")

        if not has_repository:
            recommendations.append("Consider using the repository pattern to abstract data access")

        # Check for tests
        test_count = sum(1 for c in components if c.type == "test")
        if test_count < len(components) * 0.3:
            recommendations.append("Test coverage appears low. Consider adding more tests")

        return recommendations

    def _generate_mermaid_diagram(self, components: list[Component], layers: dict) -> str:
        """Generate Mermaid architecture diagram."""
        lines = ["graph TB"]

        # Add subgraphs for layers
        for layer, comps in layers.items():
            if comps:
                lines.append(f"    subgraph {layer.title()}")
                for comp in comps[:10]:  # Limit for readability
                    lines.append(f"        {comp}[{comp}]")
                lines.append("    end")

        # Add some key dependencies
        dep_count = 0
        for comp in components[:20]:
            for dep in comp.dependencies[:3]:
                if dep in [c.name for c in components]:
                    lines.append(f"    {comp.name} --> {dep}")
                    dep_count += 1
                    if dep_count > 30:
                        break
            if dep_count > 30:
                break

        return "\n".join(lines)

    async def design_component(
        self, name: str, requirements: str, integration_points: list[str] | None = None
    ) -> dict:
        """Design a new component."""
        logger.info(f"Designing component: {name}")

        design = {
            "name": name,
            "type": "service",
            "responsibilities": [
                f"Handle {name} related operations",
                "Validate input data",
                "Coordinate with dependent services",
            ],
            "interfaces": {
                "public": [
                    f"create_{name.lower()}(data: dict) -> {name}",
                    f"get_{name.lower()}(id: str) -> Optional[{name}]",
                    f"update_{name.lower()}(id: str, data: dict) -> {name}",
                    f"delete_{name.lower()}(id: str) -> bool",
                ],
                "internal": [],
            },
            "dependencies": integration_points or [],
            "data_model": {"entity": name, "fields": ["id", "created_at", "updated_at"]},
            "patterns": ["Repository", "Service Layer", "DTO"],
            "file_structure": [
                f"{name.lower()}/",
                "  __init__.py",
                "  model.py",
                "  service.py",
                "  repository.py",
                "  schema.py",
                "  tests/",
                f"    test_{name.lower()}.py",
            ],
        }

        return design


class Architect(ArchitectAgent):
    """Compatibility facade used by legacy tests/integrations."""

    async def design(self, prompt: str) -> dict:
        return await self.design_component(prompt, "")

    async def evaluate_pattern(self, pattern_name: str) -> dict:
        normalized = pattern_name.lower().strip().replace("-", "_")
        pattern = self.PATTERNS.get(normalized)
        if pattern is None:
            return {
                "pattern": pattern_name,
                "status": "unknown",
                "description": "Pattern not recognized",
            }
        return {
            "pattern": pattern_name,
            "status": "known",
            "description": pattern["description"],
            "indicators": pattern["indicators"],
        }


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Architect Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--design", help="Design a new component")

    args = parser.parse_args()

    agent = ArchitectAgent(args.path)

    if args.design:
        design = await agent.design_component(args.design, "")
        print(json.dumps(design, indent=2))
    else:
        analysis = await agent.analyze()

        if args.json:
            print(json.dumps(analysis.to_dict(), indent=2))
        else:
            print(analysis.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
