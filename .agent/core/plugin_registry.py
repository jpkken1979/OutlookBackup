#!/usr/bin/env python3
"""
Antigravity Plugin Registry - Local index and search for plugins.

Provides:
- JSON-based registry index with fast lookups
- Full-text search across plugin metadata
- Category and tag taxonomies
- Version tracking with semver support
- Registry import/export for sharing

Usage:
    from core.plugin_registry import PluginRegistry

    registry = PluginRegistry()
    registry.build_index()
    results = registry.search("data engineering")
    registry.export_index("registry-export.json")
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("antigravity.plugin_registry")


# =============================================================================
# MODELS
# =============================================================================


class RegistryEntry(BaseModel):
    """A single entry in the plugin registry index."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "Unknown"
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    path: str = ""
    indexed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    search_text: str = ""  # Pre-computed searchable text


class RegistryIndex(BaseModel):
    """The complete registry index."""

    version: str = "1.0.0"
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_plugins: int = 0
    total_skills: int = 0
    total_agents: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    tags: dict[str, int] = Field(default_factory=dict)
    entries: dict[str, RegistryEntry] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """A search result with relevance score."""

    entry: RegistryEntry
    score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)


# =============================================================================
# VERSION UTILITIES
# =============================================================================


def parse_semver(version: str) -> tuple[int, int, int]:
    """
    Parse a semantic version string into a tuple.

    Args:
        version: Version string (e.g., "1.2.3").

    Returns:
        Tuple of (major, minor, patch).
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return 0, 0, 0


def version_satisfies(version: str, constraint: str) -> bool:
    """
    Check if a version satisfies a constraint.

    Supports: exact (1.2.3), >= (>=1.2.0), ^caret (^1.2.0), ~tilde (~1.2.0).

    Args:
        version: The version to check.
        constraint: The version constraint.

    Returns:
        True if version satisfies the constraint.
    """
    v = parse_semver(version)

    if constraint.startswith(">="):
        c = parse_semver(constraint[2:])
        return v >= c
    elif constraint.startswith("^"):
        c = parse_semver(constraint[1:])
        return v[0] == c[0] and v >= c
    elif constraint.startswith("~"):
        c = parse_semver(constraint[1:])
        return v[0] == c[0] and v[1] == c[1] and v >= c
    else:
        c = parse_semver(constraint)
        return v == c


# =============================================================================
# PLUGIN REGISTRY
# =============================================================================


class PluginRegistry:
    """
    Local plugin registry with JSON index and search capabilities.

    Scans the plugins directory to build a searchable index of all
    plugins, their skills, agents, and metadata. Persists the index
    to disk for fast subsequent loads.
    """

    def __init__(
        self,
        plugins_dir: Path | None = None,
        index_file: Path | None = None,
    ) -> None:
        self._plugins_dir = plugins_dir or Path(__file__).parent.parent / "plugins"
        self._index_file = index_file or self._plugins_dir / ".registry-index.json"
        self._index = RegistryIndex()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def index(self) -> RegistryIndex:
        """Current registry index."""
        return self._index

    @property
    def entries(self) -> dict[str, RegistryEntry]:
        """All registry entries."""
        return self._index.entries

    # -------------------------------------------------------------------------
    # Index Building
    # -------------------------------------------------------------------------

    def build_index(self) -> RegistryIndex:
        """
        Scan plugins directory and build the complete registry index.

        Returns:
            The built RegistryIndex.
        """
        if not self._plugins_dir.exists():
            logger.warning("Plugins directory not found: %s", self._plugins_dir)
            return self._index

        entries: dict[str, RegistryEntry] = {}
        all_categories: dict[str, int] = {}
        all_tags: dict[str, int] = {}
        total_skills = 0
        total_agents = 0

        for entry_dir in sorted(self._plugins_dir.iterdir()):
            if not entry_dir.is_dir() or entry_dir.name.startswith("."):
                continue

            entry = self._index_plugin(entry_dir)
            if entry is not None:
                entries[entry.name] = entry
                total_skills += len(entry.skills)
                total_agents += len(entry.agents)

                # Track categories
                cat = entry.category or "general"
                all_categories[cat] = all_categories.get(cat, 0) + 1

                # Track tags
                for tag in entry.tags:
                    all_tags[tag] = all_tags.get(tag, 0) + 1

        self._index = RegistryIndex(
            updated_at=datetime.now().isoformat(),
            total_plugins=len(entries),
            total_skills=total_skills,
            total_agents=total_agents,
            categories=all_categories,
            tags=all_tags,
            entries=entries,
        )

        self._save_index()
        logger.info(
            "Built registry index: %d plugins, %d skills, %d agents",
            len(entries),
            total_skills,
            total_agents,
        )
        return self._index

    def _index_plugin(self, plugin_dir: Path) -> RegistryEntry | None:
        """Index a single plugin directory."""
        metadata = self._read_metadata(plugin_dir)

        # Collect skills
        skills: list[str] = []
        skills_dir = plugin_dir / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    skills.append(skill_dir.name)

        # Collect agents
        agents: list[str] = []
        agents_dir = plugin_dir / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                    agents.append(agent_dir.name)

        # Infer category from directory structure or tags
        category = metadata.get("category", "")
        if not category:
            category = self._infer_category(plugin_dir.name, metadata)

        # Build search text for fast full-text search
        search_parts = [
            metadata.get("name", plugin_dir.name),
            metadata.get("description", ""),
            " ".join(metadata.get("tags", [])),
            " ".join(metadata.get("capabilities", [])),
            " ".join(skills),
            " ".join(agents),
            category,
        ]
        search_text = " ".join(search_parts).lower()

        # Extract author name
        author = metadata.get("author", {})
        author_name = author.get("name", "Unknown") if isinstance(author, dict) else str(author)

        entry = RegistryEntry(
            name=metadata.get("name", plugin_dir.name),
            version=metadata.get("version", "1.0.0"),
            description=metadata.get("description", ""),
            author=author_name,
            category=category,
            tags=metadata.get("tags", []),
            capabilities=metadata.get("capabilities", []),
            skills=skills,
            agents=agents,
            dependencies=metadata.get("dependencies", []),
            path=str(plugin_dir),
            search_text=search_text,
        )

        return entry

    def _read_metadata(self, plugin_dir: Path) -> dict[str, Any]:
        """Read plugin metadata from JSON file."""
        candidates = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
        ]

        for candidate in candidates:
            if candidate.exists():
                try:
                    return json.loads(candidate.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    logger.warning("Bad JSON in %s: %s", candidate, e)

        return {"name": plugin_dir.name}

    def _infer_category(self, dir_name: str, metadata: dict[str, Any]) -> str:
        """Infer plugin category from its name, description, and tags."""
        text = f"{dir_name} {metadata.get('description', '')} {' '.join(metadata.get('tags', []))}".lower()

        category_keywords = {
            "security": ["security", "audit", "vulnerability", "penetration", "compliance"],
            "devops": ["devops", "cicd", "ci/cd", "pipeline", "deploy", "docker", "kubernetes"],
            "data": ["data", "database", "sql", "etl", "analytics", "excel", "csv"],
            "frontend": ["frontend", "ui", "ux", "react", "css", "design", "component"],
            "backend": ["backend", "api", "rest", "graphql", "server", "microservice"],
            "testing": ["test", "qa", "quality", "coverage", "e2e", "unit"],
            "ai-ml": ["ai", "ml", "machine learning", "llm", "rag", "agent", "model"],
            "infrastructure": ["cloud", "aws", "gcp", "azure", "infrastructure", "terraform"],
            "documentation": ["doc", "documentation", "readme", "markdown", "wiki"],
            "business": ["business", "startup", "marketing", "sales", "analytics"],
            "mobile": ["mobile", "ios", "android", "react native", "flutter"],
        }

        best_category = "general"
        best_score = 0

        for category, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_category = category

        return best_category

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        category: str | None = None,
        tag: str | None = None,
        min_version: str | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        """
        Search the registry with full-text matching and filters.

        Args:
            query: Search query string.
            category: Filter by category.
            tag: Filter by tag.
            min_version: Minimum version constraint.
            limit: Maximum results to return.

        Returns:
            List of SearchResult sorted by relevance.
        """
        query_terms = query.lower().split()
        results: list[SearchResult] = []

        for entry in self._index.entries.values():
            # Apply filters first
            if category and entry.category != category:
                continue
            if tag and tag.lower() not in [t.lower() for t in entry.tags]:
                continue
            if min_version and not version_satisfies(entry.version, f">={min_version}"):
                continue

            # Score the entry
            score = 0.0
            reasons: list[str] = []

            for term in query_terms:
                # Exact name match
                if entry.name.lower() == term:
                    score += 20.0
                    reasons.append(f"exact name: {term}")

                # Name contains
                elif term in entry.name.lower():
                    score += 10.0
                    reasons.append(f"name contains: {term}")

                # Description match
                if term in entry.description.lower():
                    score += 5.0
                    reasons.append(f"description: {term}")

                # Tag match
                for t in entry.tags:
                    if term in t.lower():
                        score += 4.0
                        reasons.append(f"tag: {t}")
                        break

                # Skill name match
                for skill in entry.skills:
                    if term in skill.lower():
                        score += 3.0
                        reasons.append(f"skill: {skill}")
                        break

                # Capability match
                for cap in entry.capabilities:
                    if term in cap.lower():
                        score += 2.0
                        reasons.append(f"capability: {cap}")
                        break

                # Full-text fallback
                if term in entry.search_text:
                    score += 1.0

            if score > 0:
                results.append(SearchResult(entry=entry, score=score, match_reasons=reasons))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def get_by_category(self, category: str) -> list[RegistryEntry]:
        """Get all plugins in a category."""
        return [e for e in self._index.entries.values() if e.category == category]

    def get_by_tag(self, tag: str) -> list[RegistryEntry]:
        """Get all plugins with a specific tag."""
        tag_lower = tag.lower()
        return [e for e in self._index.entries.values() if tag_lower in [t.lower() for t in e.tags]]

    def get_categories(self) -> dict[str, int]:
        """Get all categories with counts."""
        return dict(self._index.categories)

    def get_tags(self) -> dict[str, int]:
        """Get all tags with counts."""
        return dict(self._index.tags)

    def find_by_skill(self, skill_name: str) -> list[RegistryEntry]:
        """Find plugins that provide a specific skill."""
        skill_lower = skill_name.lower()
        return [
            e
            for e in self._index.entries.values()
            if any(skill_lower in s.lower() for s in e.skills)
        ]

    def find_by_agent(self, agent_name: str) -> list[RegistryEntry]:
        """Find plugins that provide a specific agent."""
        agent_lower = agent_name.lower()
        return [
            e
            for e in self._index.entries.values()
            if any(agent_lower in a.lower() for a in e.agents)
        ]

    # -------------------------------------------------------------------------
    # Dependency Resolution
    # -------------------------------------------------------------------------

    def resolve_dependencies(self, plugin_name: str) -> list[str]:
        """
        Resolve the dependency tree for a plugin.

        Returns a topologically sorted list of plugin names
        that need to be activated (dependencies first).

        Args:
            plugin_name: The plugin to resolve dependencies for.

        Returns:
            Ordered list of plugin names (dependencies first, target last).

        Raises:
            KeyError: If plugin not found.
            ValueError: If circular dependency detected.
        """
        entry = self._index.entries.get(plugin_name)
        if entry is None:
            raise KeyError(f"Plugin not found in registry: {plugin_name}")

        resolved: list[str] = []
        seen: set[str] = set()
        visiting: set[str] = set()

        def _visit(name: str) -> None:
            if name in resolved:
                return
            if name in visiting:
                raise ValueError(f"Circular dependency detected involving: {name}")

            visiting.add(name)

            dep_entry = self._index.entries.get(name)
            if dep_entry:
                for dep in dep_entry.dependencies:
                    if dep in self._index.entries:
                        _visit(dep)

            visiting.discard(name)
            seen.add(name)
            resolved.append(name)

        _visit(plugin_name)
        return resolved

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _save_index(self) -> None:
        """Save registry index to disk."""
        self._index_file.parent.mkdir(parents=True, exist_ok=True)
        self._index_file.write_text(
            self._index.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Registry index saved to %s", self._index_file)

    def load_index(self) -> RegistryIndex:
        """
        Load registry index from disk.

        Returns:
            The loaded RegistryIndex.
        """
        if not self._index_file.exists():
            logger.info("No index file found, building fresh index")
            return self.build_index()

        try:
            raw = self._index_file.read_text(encoding="utf-8")
            self._index = RegistryIndex.model_validate_json(raw)
            logger.info("Loaded registry index: %d plugins", self._index.total_plugins)
            return self._index
        except Exception as e:
            logger.warning("Failed to load index, rebuilding: %s", e)
            return self.build_index()

    def export_index(self, output_path: str | Path) -> Path:
        """
        Export registry index to a file.

        Args:
            output_path: Path to write the exported index.

        Returns:
            Path to the exported file.
        """
        output = Path(output_path)
        output.write_text(
            self._index.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Exported registry index to %s", output)
        return output

    def import_index(self, input_path: str | Path) -> RegistryIndex:
        """
        Import registry entries from an external index file.

        Merges with existing entries (external entries don't overwrite local).

        Args:
            input_path: Path to the index file to import.

        Returns:
            Updated RegistryIndex.
        """
        raw = Path(input_path).read_text(encoding="utf-8")
        external = RegistryIndex.model_validate_json(raw)

        for name, entry in external.entries.items():
            if name not in self._index.entries:
                self._index.entries[name] = entry
                logger.info("Imported plugin entry: %s", name)

        # Recount
        self._index.total_plugins = len(self._index.entries)
        self._index.updated_at = datetime.now().isoformat()
        self._save_index()

        return self._index

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_plugins": self._index.total_plugins,
            "total_skills": self._index.total_skills,
            "total_agents": self._index.total_agents,
            "categories": len(self._index.categories),
            "tags": len(self._index.tags),
            "top_categories": dict(
                sorted(
                    self._index.categories.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
            "top_tags": dict(
                sorted(
                    self._index.tags.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
        }
