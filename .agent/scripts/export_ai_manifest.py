#!/usr/bin/env python3
"""AI/IDE manifest exporter for Antigravity ecosystem.

Features:
- Scans active agents and skills quickly
- Exports machine-readable JSON for IDEs and AI copilots
- Provides summary metrics for automation workflows
- Supports filtered exports for targeted indexing pipelines
- Generates fingerprint and insights for incremental/autonomous workflows
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"
DEFAULT_OUTPUT = PROJECT_ROOT / ".agent" / "metrics" / "ai_manifest.json"
SCHEMA_VERSION = "1.2.0"


class AgentEntry(BaseModel):
    """Machine-readable metadata for one agent."""

    name: str
    path: str
    has_identity: bool
    scripts_count: int
    is_deprecated: bool


class SkillEntry(BaseModel):
    """Machine-readable metadata for one skill."""

    name: str
    path: str
    has_skill_doc: bool
    scripts_count: int
    is_deprecated: bool


class ManifestStats(BaseModel):
    """Aggregated stats consumed by observability and indexing pipelines."""

    total_agents: int
    total_skills: int
    agents_with_identity: int
    skills_with_doc: int
    total_agent_scripts: int
    total_skill_scripts: int
    agent_doc_coverage: float
    skill_doc_coverage: float


class ManifestInsight(BaseModel):
    """Actionable recommendation derived from manifest stats."""

    level: Literal["info", "warn"]
    message: str


class Manifest(BaseModel):
    """Top-level manifest consumed by IDE/AI integrations."""

    schema_version: str
    generated_at: str
    project_root: str
    fingerprint: str
    filters: dict[str, str | int | bool] = Field(default_factory=dict)
    stats: ManifestStats
    insights: list[ManifestInsight] = Field(default_factory=list)
    agents: list[AgentEntry] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)


class ExportFilters(BaseModel):
    """Filter options for slim and fast exports."""

    include_deprecated: bool = False
    require_docs: bool = False
    min_scripts: int = 0
    only: Literal["all", "agents", "skills"] = "all"

    @field_validator("min_scripts")
    @classmethod
    def validate_min_scripts(cls, value: int) -> int:
        """Ensure filter is safe and deterministic."""
        if value < 0:
            raise ValueError("min_scripts must be >= 0")
        return value


ExportFilters.model_rebuild()
ManifestInsight.model_rebuild()
Manifest.model_rebuild()


def _count_scripts(directory: Path) -> int:
    scripts_dir = directory / "scripts"
    if not scripts_dir.exists() or not scripts_dir.is_dir():
        return 0
    return sum(1 for item in scripts_dir.iterdir() if item.is_file())


def _scan_agents(filters: ExportFilters) -> list[AgentEntry]:
    entries: list[AgentEntry] = []
    if not AGENTS_DIR.exists():
        return entries

    for candidate in sorted(AGENTS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not candidate.is_dir():
            continue

        is_deprecated = candidate.name == "_deprecated"
        if is_deprecated and not filters.include_deprecated:
            continue

        has_identity = (candidate / "IDENTITY.md").exists()
        scripts_count = _count_scripts(candidate)

        if filters.require_docs and not has_identity:
            continue
        if scripts_count < filters.min_scripts:
            continue

        entries.append(
            AgentEntry(
                name=candidate.name,
                path=str(candidate.relative_to(PROJECT_ROOT)),
                has_identity=has_identity,
                scripts_count=scripts_count,
                is_deprecated=is_deprecated,
            )
        )

    return entries


def _scan_skills(filters: ExportFilters) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    if not SKILLS_DIR.exists():
        return entries

    for candidate in sorted(SKILLS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not candidate.is_dir():
            continue

        is_deprecated = candidate.name == "_deprecated"
        if is_deprecated and not filters.include_deprecated:
            continue

        has_skill_doc = (candidate / "SKILL.md").exists()
        scripts_count = _count_scripts(candidate)

        if filters.require_docs and not has_skill_doc:
            continue
        if scripts_count < filters.min_scripts:
            continue

        entries.append(
            SkillEntry(
                name=candidate.name,
                path=str(candidate.relative_to(PROJECT_ROOT)),
                has_skill_doc=has_skill_doc,
                scripts_count=scripts_count,
                is_deprecated=is_deprecated,
            )
        )

    return entries


def _safe_percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _build_stats(agents: list[AgentEntry], skills: list[SkillEntry]) -> ManifestStats:
    agents_with_identity = sum(1 for agent in agents if agent.has_identity)
    skills_with_doc = sum(1 for skill in skills if skill.has_skill_doc)
    return ManifestStats(
        total_agents=len(agents),
        total_skills=len(skills),
        agents_with_identity=agents_with_identity,
        skills_with_doc=skills_with_doc,
        total_agent_scripts=sum(agent.scripts_count for agent in agents),
        total_skill_scripts=sum(skill.scripts_count for skill in skills),
        agent_doc_coverage=_safe_percentage(agents_with_identity, len(agents)),
        skill_doc_coverage=_safe_percentage(skills_with_doc, len(skills)),
    )


def _build_insights(stats: ManifestStats) -> list[ManifestInsight]:
    insights: list[ManifestInsight] = []

    if stats.agent_doc_coverage < 95.0:
        insights.append(
            ManifestInsight(
                level="warn",
                message=(
                    "Agent documentation coverage below 95%. Consider completing missing "
                    "IDENTITY.md files to improve autonomous agent routing quality."
                ),
            )
        )

    if stats.skill_doc_coverage < 95.0:
        insights.append(
            ManifestInsight(
                level="warn",
                message=(
                    "Skill documentation coverage below 95%. Complete missing SKILL.md files "
                    "to improve retrieval quality for IDE/AI assistants."
                ),
            )
        )

    if not insights:
        insights.append(
            ManifestInsight(
                level="info",
                message="Documentation coverage is healthy. Ecosystem ready for autonomous indexing.",
            )
        )

    return insights


def _build_fingerprint(
    filters: ExportFilters,
    agents: list[AgentEntry],
    skills: list[SkillEntry],
    stats: ManifestStats,
) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "filters": filters.model_dump(mode="json"),
        "stats": stats.model_dump(mode="json"),
        "agents": [entry.model_dump(mode="json") for entry in agents],
        "skills": [entry.model_dump(mode="json") for entry in skills],
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_manifest(filters: ExportFilters | None = None) -> Manifest:
    """Build AI/IDE-friendly ecosystem manifest."""
    active_filters = filters or ExportFilters()

    agents = _scan_agents(active_filters) if active_filters.only in {"all", "agents"} else []
    skills = _scan_skills(active_filters) if active_filters.only in {"all", "skills"} else []
    stats = _build_stats(agents=agents, skills=skills)
    insights = _build_insights(stats=stats)

    return Manifest(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(UTC).isoformat(),
        project_root=str(PROJECT_ROOT),
        fingerprint=_build_fingerprint(
            filters=active_filters,
            agents=agents,
            skills=skills,
            stats=stats,
        ),
        filters=active_filters.model_dump(mode="json"),
        stats=stats,
        insights=insights,
        agents=agents,
        skills=skills,
    )


def write_manifest(manifest: Manifest, output_path: Path, pretty: bool) -> None:
    """Write manifest JSON to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    payload = manifest.model_dump(mode="json")
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=indent)
        fp.write("\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Export AI/IDE manifest for Antigravity ecosystem")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--include-deprecated",
        action="store_true",
        help="Include _deprecated directories in the manifest",
    )
    parser.add_argument(
        "--require-docs",
        action="store_true",
        help="Only include entries that contain IDENTITY.md/SKILL.md",
    )
    parser.add_argument(
        "--min-scripts",
        type=int,
        default=0,
        help="Only include entries with at least this number of scripts",
    )
    parser.add_argument(
        "--only",
        choices=["all", "agents", "skills"],
        default="all",
        help="Limit export to a single ecosystem section",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    filters = ExportFilters(
        include_deprecated=args.include_deprecated,
        require_docs=args.require_docs,
        min_scripts=args.min_scripts,
        only=args.only,
    )
    manifest = build_manifest(filters=filters)
    write_manifest(manifest, output_path=args.output, pretty=args.pretty)

    print(
        "Manifest exported:",
        f"schema={manifest.schema_version}",
        f"fingerprint={manifest.fingerprint[:12]}",
        f"agents={manifest.stats.total_agents}",
        f"skills={manifest.stats.total_skills}",
        f"output={args.output}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
