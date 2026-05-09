#!/usr/bin/env python3
"""Comparador de skills locales vs skills.sh - detecta gaps y upgrades.

Escanea los skills locales en `.agent/skills/`, los agrupa por categoría
y los compara contra los resultados de `npx skills find "<category>"`
para encontrar:
  - LOCAL WINS: skills donde lo local es mejor
  - SKILLS.SH WINS: skills que existen remotamente pero no localmente
  - UPGRADE CANDIDATES: skills que podrían mejorarse con versiones remotas

Uso:
    python .agent/scripts/compare_skills.py --all
    python .agent/scripts/compare_skills.py --category security
    python .agent/scripts/compare_skills.py --category ai --top 10
    python .agent/scripts/compare_skills.py --all --output json

v1.0.0 - 2026-03-25
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Windows console encoding fix
# ---------------------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

# ---------------------------------------------------------------------------
# Logging (stderr) - report goes to stdout
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("antigravity.compare_skills")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Pattern for skill line: owner/repo@skill-name  <installs> installs
SKILL_LINE_RE = re.compile(
    r"^(?P<ref>[\w./-]+@[\w./-]+)\s+(?P<installs>[\d.]+[KkMm]?)\s+installs?$"
)

# Pattern for URL line: └ https://skills.sh/... (permissive prefix for Windows encoding)
URL_LINE_RE = re.compile(r"^.*?(?P<url>https://skills\.sh/\S+)\s*$")

# Minimum similarity ratio to consider two skill names a "match"
SIMILARITY_THRESHOLD = 0.65

# Categories and the search queries that map to them
CATEGORIES: dict[str, list[str]] = {
    "security": ["security", "authentication", "encryption"],
    "testing": ["testing", "test automation", "unit test"],
    "api": ["api design", "api security", "rest api"],
    "database": ["database", "sql", "postgresql", "mongodb"],
    "devops": ["devops", "infrastructure", "deployment"],
    "ci-cd": ["ci cd", "github actions", "pipeline"],
    "frontend": ["frontend", "css", "html", "web development"],
    "backend": ["backend", "server", "microservices"],
    "react": ["react", "nextjs", "react native"],
    "typescript": ["typescript", "type safety"],
    "python": ["python", "django", "fastapi", "flask"],
    "ui-ux": ["ui ux", "design system", "user interface"],
    "design": ["design patterns", "architecture patterns"],
    "accessibility": ["accessibility", "a11y", "wcag"],
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s", "helm"],
    "terraform": ["terraform", "iac", "infrastructure as code"],
    "ai": ["ai", "machine learning", "deep learning"],
    "llm": ["llm", "large language model", "prompt engineering"],
    "rag": ["rag", "retrieval augmented", "vector database"],
    "agents": ["ai agents", "autonomous agents", "agent orchestration"],
    "git": ["git", "version control", "branching"],
    "performance": ["performance", "optimization", "caching"],
    "monitoring": ["monitoring", "observability", "logging"],
}

# Keywords used to classify local skills into categories
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "security": [
        "security",
        "auth",
        "encryption",
        "penetration",
        "vulnerability",
        "owasp",
        "attack",
        "exploit",
        "malware",
        "forensic",
        "reversing",
        "burp",
        "fuzzing",
        "bug-bounty",
        "broken-auth",
    ],
    "testing": [
        "test",
        "jest",
        "vitest",
        "pytest",
        "cypress",
        "playwright",
        "bats",
        "tdd",
        "bdd",
        "qa",
        "quality",
    ],
    "api": [
        "api",
        "rest",
        "graphql",
        "grpc",
        "openapi",
        "swagger",
    ],
    "database": [
        "database",
        "sql",
        "postgres",
        "mysql",
        "mongo",
        "redis",
        "supabase",
        "prisma",
        "drizzle",
        "sqlite",
        "dynamo",
    ],
    "devops": [
        "devops",
        "deploy",
        "infrastructure",
        "serverless",
        "aws",
        "azure",
        "gcp",
        "cloud",
    ],
    "ci-cd": [
        "ci",
        "cd",
        "pipeline",
        "github-action",
        "jenkins",
        "vercel",
    ],
    "frontend": [
        "frontend",
        "css",
        "html",
        "tailwind",
        "sass",
        "responsive",
        "web-component",
        "canvas",
    ],
    "backend": [
        "backend",
        "server",
        "microservice",
        "express",
        "fastify",
        "nest",
        "hono",
    ],
    "react": [
        "react",
        "nextjs",
        "next-js",
        "remix",
        "gatsby",
        "jsx",
        "tsx",
    ],
    "typescript": [
        "typescript",
        "type-safety",
        "zod",
        "type",
    ],
    "python": [
        "python",
        "django",
        "fastapi",
        "flask",
        "pydantic",
        "async-python",
    ],
    "ui-ux": [
        "ui",
        "ux",
        "design-system",
        "figma",
        "component",
        "layout",
        "animation",
        "framer",
    ],
    "design": [
        "design-pattern",
        "architecture",
        "clean-code",
        "solid",
        "hexagonal",
        "ddd",
    ],
    "accessibility": [
        "accessibility",
        "a11y",
        "wcag",
        "aria",
        "screen-reader",
    ],
    "docker": [
        "docker",
        "container",
        "compose",
        "dockerfile",
    ],
    "kubernetes": [
        "kubernetes",
        "k8s",
        "helm",
        "kubectl",
    ],
    "terraform": [
        "terraform",
        "iac",
        "pulumi",
        "cloudformation",
    ],
    "ai": [
        "ai",
        "machine-learning",
        "ml",
        "deep-learning",
        "neural",
        "model",
        "training",
    ],
    "llm": [
        "llm",
        "prompt",
        "gpt",
        "claude",
        "openai",
        "anthropic",
        "langchain",
        "embedding",
    ],
    "rag": [
        "rag",
        "retrieval",
        "vector",
        "chroma",
        "pinecone",
        "search",
    ],
    "agents": [
        "agent",
        "autonomous",
        "orchestration",
        "crew",
        "swarm",
    ],
    "git": [
        "git",
        "version-control",
        "branch",
        "merge",
        "commit",
    ],
    "performance": [
        "performance",
        "optimization",
        "cache",
        "benchmark",
        "profil",
    ],
    "monitoring": [
        "monitoring",
        "observability",
        "logging",
        "tracing",
        "metric",
        "prometheus",
        "grafana",
    ],
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class LocalSkill:
    """A skill found in the local .agent/skills/ directory."""

    name: str
    path: Path
    line_count: int = 0
    categories: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class RemoteSkill:
    """A skill found on skills.sh via npx skills find."""

    name: str
    ref: str  # owner/repo@skill-name
    installs: str  # e.g. "14.1K"
    installs_numeric: float = 0.0
    url: str = ""


@dataclass
class ComparisonResult:
    """Result of comparing a local skill against remote skills."""

    local_skill: str
    verdict: str  # "local_wins", "upgrade_candidate", "match"
    remote_match: str | None = None
    remote_installs: str | None = None
    reason: str = ""


@dataclass
class CategoryReport:
    """Full comparison report for a single category."""

    category: str
    local_skills: list[LocalSkill]
    remote_skills: list[RemoteSkill]
    local_wins: list[ComparisonResult] = field(default_factory=list)
    missing_locally: list[RemoteSkill] = field(default_factory=list)
    upgrade_candidates: list[ComparisonResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Args:
        text: Raw text with potential ANSI color codes.

    Returns:
        Clean text without escape sequences.
    """
    return ANSI_RE.sub("", text)


def parse_installs(raw: str) -> float:
    """Parse install count string to numeric value.

    Args:
        raw: Install count like '14.1K', '3.2M', or '500'.

    Returns:
        Numeric value (e.g. 14100.0).
    """
    raw = raw.strip().upper()
    multiplier = 1.0
    if raw.endswith("K"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("M"):
        multiplier = 1_000_000
        raw = raw[:-1]
    try:
        return float(raw) * multiplier
    except ValueError:
        return 0.0


def skill_similarity(local_name: str, remote_name: str) -> float:
    """Compute normalized similarity between two skill names.

    Args:
        local_name: Local skill directory name.
        remote_name: Remote skill name from the ref.

    Returns:
        Float between 0.0 and 1.0.
    """
    # Normalize: lowercase, remove common prefixes/suffixes
    a = local_name.lower().replace("_", "-")
    b = remote_name.lower().replace("_", "-")
    return SequenceMatcher(None, a, b).ratio()


def read_skill_md(skill_dir: Path) -> tuple[int, str]:
    """Read SKILL.md and return (line_count, description).

    Args:
        skill_dir: Path to the skill directory.

    Returns:
        Tuple of (line count, description from frontmatter).
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return 0, ""
    try:
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        line_count = len(lines)

        # Extract description from YAML frontmatter
        description = ""
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                    break
        return line_count, description
    except OSError:
        return 0, ""


def classify_skill(skill_name: str) -> list[str]:
    """Classify a skill into categories based on its name.

    Args:
        skill_name: The directory name of the skill.

    Returns:
        List of category names that match.
    """
    normalized = skill_name.lower().replace("_", "-")
    matched: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in normalized:
                matched.append(category)
                break
    return matched or ["uncategorized"]


# ---------------------------------------------------------------------------
# Local skill scanner
# ---------------------------------------------------------------------------
def scan_local_skills() -> list[LocalSkill]:
    """Scan all local skills in .agent/skills/.

    Returns:
        List of LocalSkill objects with metadata.
    """
    if not SKILLS_DIR.exists():
        logger.error("Skills directory not found: %s", SKILLS_DIR)
        return []

    skills: list[LocalSkill] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Skip hidden directories and known non-skill entries
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue

        line_count, description = read_skill_md(entry)
        categories = classify_skill(entry.name)
        skills.append(
            LocalSkill(
                name=entry.name,
                path=entry,
                line_count=line_count,
                categories=categories,
                description=description,
            )
        )

    logger.info("Scanned %d local skills", len(skills))
    return skills


def group_by_category(
    skills: list[LocalSkill],
) -> dict[str, list[LocalSkill]]:
    """Group local skills by their categories.

    Args:
        skills: List of local skills.

    Returns:
        Dict mapping category name to list of skills.
    """
    groups: dict[str, list[LocalSkill]] = {}
    for skill in skills:
        for cat in skill.categories:
            groups.setdefault(cat, []).append(skill)
    return groups


# ---------------------------------------------------------------------------
# Remote skill fetcher
# ---------------------------------------------------------------------------
def fetch_remote_skills(query: str, top: int = 5) -> list[RemoteSkill]:
    """Fetch skills from skills.sh using npx skills find.

    Args:
        query: Search query string.
        top: Maximum number of results to return.

    Returns:
        List of RemoteSkill objects.
    """
    # Resolve npx path - on Windows, subprocess needs the .cmd extension
    npx_path = shutil.which("npx")
    if not npx_path:
        logger.error("npx not found - install Node.js to use skills.sh comparison")
        return []

    cmd = [npx_path, "skills", "find", query]
    logger.info("Running: %s", " ".join(cmd))

    try:
        # Use encoding="utf-8" + errors="replace" to handle ANSI art on Windows
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            shell=False,
            cwd=str(PROJECT_ROOT),
        )
    except FileNotFoundError:
        logger.error("npx not found at resolved path: %s", npx_path)
        return []
    except subprocess.TimeoutExpired:
        logger.warning("Timeout fetching skills for query: %s", query)
        return []

    # Decode with utf-8 + replace to survive ANSI art on cp932/cp1252 consoles
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    if result.returncode != 0:
        stderr_clean = strip_ansi(stderr).strip()
        if stderr_clean:
            logger.warning("npx skills find stderr: %s", stderr_clean[:200])
        if not stdout.strip():
            return []

    return _parse_skills_output(stdout, top)


def _parse_skills_output(raw_output: str, top: int) -> list[RemoteSkill]:
    """Parse ANSI-colored output from `npx skills find`.

    Expected format (after stripping ANSI):
        owner/repo@skill-name  14.1K installs
        └ https://skills.sh/owner/repo/skill-name

    Args:
        raw_output: Raw stdout from npx skills find.
        top: Maximum results to return.

    Returns:
        List of RemoteSkill objects.
    """
    clean = strip_ansi(raw_output)
    lines = clean.splitlines()
    skills: list[RemoteSkill] = []
    current_ref = ""
    current_name = ""
    current_installs = ""
    current_installs_numeric = 0.0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to match a skill reference line
        match = SKILL_LINE_RE.match(line)
        if match:
            current_ref = match.group("ref")
            current_installs = match.group("installs")
            current_installs_numeric = parse_installs(current_installs)
            # Extract skill name from ref (part after @)
            if "@" in current_ref:
                current_name = current_ref.split("@", 1)[1]
            else:
                current_name = current_ref
            continue

        # Try to match URL line
        url_match = URL_LINE_RE.match(line)
        if url_match and current_ref:
            skills.append(
                RemoteSkill(
                    name=current_name,
                    ref=current_ref,
                    installs=current_installs,
                    installs_numeric=current_installs_numeric,
                    url=url_match.group("url"),
                )
            )
            current_ref = ""
            if len(skills) >= top:
                break

    # Handle case where last skill has no URL line
    if current_ref and len(skills) < top:
        skills.append(
            RemoteSkill(
                name=current_name,
                ref=current_ref,
                installs=current_installs,
                installs_numeric=current_installs_numeric,
            )
        )

    return skills


# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------
def compare_category(
    category: str,
    local_skills: list[LocalSkill],
    remote_skills: list[RemoteSkill],
) -> CategoryReport:
    """Compare local skills against remote skills for a category.

    Args:
        category: Category name.
        local_skills: Local skills in this category.
        remote_skills: Remote skills found for this category.

    Returns:
        CategoryReport with classified results.
    """
    report = CategoryReport(
        category=category,
        local_skills=local_skills,
        remote_skills=remote_skills,
    )

    # Track which remote skills are matched
    matched_remote: set[str] = set()

    for local in local_skills:
        best_match: RemoteSkill | None = None
        best_similarity = 0.0

        for remote in remote_skills:
            sim = skill_similarity(local.name, remote.name)
            if sim > best_similarity:
                best_similarity = sim
                best_match = remote

        if best_match and best_similarity >= SIMILARITY_THRESHOLD:
            matched_remote.add(best_match.name)

            # Determine winner
            if local.line_count > 100:
                # Local is substantial and likely customized
                report.local_wins.append(
                    ComparisonResult(
                        local_skill=local.name,
                        verdict="local_wins",
                        remote_match=best_match.name,
                        remote_installs=best_match.installs,
                        reason=(
                            f"Local is customized for Antigravity "
                            f"({local.line_count} lines) --"
                            f"similarity {best_similarity:.0%}"
                        ),
                    )
                )
            elif best_match.installs_numeric >= 5000:
                # Remote is very popular - worth evaluating
                report.upgrade_candidates.append(
                    ComparisonResult(
                        local_skill=local.name,
                        verdict="upgrade_candidate",
                        remote_match=best_match.name,
                        remote_installs=best_match.installs,
                        reason=(
                            f"Remote has {best_match.installs} installs vs "
                            f"local {local.line_count} lines --"
                            f"similarity {best_similarity:.0%}"
                        ),
                    )
                )
            else:
                report.local_wins.append(
                    ComparisonResult(
                        local_skill=local.name,
                        verdict="local_wins",
                        remote_match=best_match.name,
                        remote_installs=best_match.installs,
                        reason=(
                            f"Local ({local.line_count} lines) vs "
                            f"remote ({best_match.installs} installs) --"
                            f"local is sufficient"
                        ),
                    )
                )
        else:
            # No match on remote - local is unique
            report.local_wins.append(
                ComparisonResult(
                    local_skill=local.name,
                    verdict="local_wins",
                    reason="No equivalent found on skills.sh",
                )
            )

    # Find remote skills not matched locally
    for remote in remote_skills:
        if remote.name not in matched_remote:
            # Double-check no local skill is similar
            has_local = False
            for local in local_skills:
                if skill_similarity(local.name, remote.name) >= SIMILARITY_THRESHOLD:
                    has_local = True
                    break
            if not has_local:
                report.missing_locally.append(remote)

    return report


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------
def format_report(reports: list[CategoryReport]) -> str:
    """Format comparison reports as human-readable text.

    Args:
        reports: List of category reports.

    Returns:
        Formatted report string.
    """
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  SKILL COMPARISON REPORT - Local vs skills.sh")
    lines.append("=" * 60)
    lines.append("")

    total_local = 0
    total_matching = 0
    total_missing = 0
    total_local_wins = 0
    total_remote_wins = 0
    total_upgrade = 0

    for report in reports:
        if not report.local_skills and not report.remote_skills:
            continue

        n_local = len(report.local_skills)
        total_local += n_local

        lines.append(f"Category: {report.category} ({n_local} local skills)")
        lines.append("-" * 50)

        # Local wins
        if report.local_wins:
            total_local_wins += len(report.local_wins)
            for result in report.local_wins[:5]:  # Cap display at 5
                if result.remote_match:
                    total_matching += 1
                    lines.append(
                        f"  LOCAL: {result.local_skill} vs "
                        f"SKILLS.SH: {result.remote_match} "
                        f"({result.remote_installs} installs)"
                    )
                    lines.append(f"  -> LOCAL WINS: {result.reason}")
                else:
                    lines.append(f"  LOCAL: {result.local_skill}")
                    lines.append(f"  -> LOCAL WINS: {result.reason}")
            if len(report.local_wins) > 5:
                lines.append(f"  ... and {len(report.local_wins) - 5} more local wins")

        # Missing locally
        if report.missing_locally:
            total_missing += len(report.missing_locally)
            total_remote_wins += len(report.missing_locally)
            lines.append("")
            for remote in report.missing_locally:
                lines.append(f"  MISSING LOCALLY: {remote.name} ({remote.installs} installs)")
                lines.append(f"  -> Consider installing: npx skills add {remote.ref}")

        # Upgrade candidates
        if report.upgrade_candidates:
            total_upgrade += len(report.upgrade_candidates)
            lines.append("")
            for result in report.upgrade_candidates:
                lines.append(
                    f"  UPGRADE CANDIDATE: {result.local_skill} -> "
                    f"{result.remote_match} ({result.remote_installs} installs)"
                )
                lines.append(f"  -> {result.reason}")

        lines.append("")

    # Summary
    lines.append("=" * 60)
    lines.append("  SUMMARY")
    lines.append("=" * 60)
    lines.append(f"  Local skills scanned:   {total_local}")
    lines.append(f"  Matching on skills.sh:  {total_matching}")
    lines.append(f"  Missing locally:        {total_missing}")
    lines.append(f"  Local wins:             {total_local_wins}")
    lines.append(f"  Skills.sh wins:         {total_remote_wins}")
    lines.append(f"  Upgrade candidates:     {total_upgrade}")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)


def format_json(reports: list[CategoryReport]) -> str:
    """Format comparison reports as JSON.

    Args:
        reports: List of category reports.

    Returns:
        JSON string.
    """
    data: dict[str, object] = {
        "categories": [],
        "summary": {
            "total_local": 0,
            "total_matching": 0,
            "total_missing": 0,
            "total_local_wins": 0,
            "total_remote_wins": 0,
            "total_upgrade_candidates": 0,
        },
    }

    categories_list: list[dict[str, object]] = []
    summary = data["summary"]
    assert isinstance(summary, dict)

    for report in reports:
        cat_data: dict[str, object] = {
            "name": report.category,
            "local_count": len(report.local_skills),
            "local_wins": [
                {
                    "skill": r.local_skill,
                    "remote_match": r.remote_match,
                    "remote_installs": r.remote_installs,
                    "reason": r.reason,
                }
                for r in report.local_wins
            ],
            "missing_locally": [
                {
                    "name": r.name,
                    "ref": r.ref,
                    "installs": r.installs,
                    "url": r.url,
                }
                for r in report.missing_locally
            ],
            "upgrade_candidates": [
                {
                    "skill": r.local_skill,
                    "remote_match": r.remote_match,
                    "remote_installs": r.remote_installs,
                    "reason": r.reason,
                }
                for r in report.upgrade_candidates
            ],
        }
        categories_list.append(cat_data)

        summary["total_local"] = int(str(summary["total_local"])) + len(report.local_skills)
        summary["total_local_wins"] = int(str(summary["total_local_wins"])) + len(report.local_wins)
        summary["total_missing"] = int(str(summary["total_missing"])) + len(report.missing_locally)
        summary["total_remote_wins"] = int(str(summary["total_remote_wins"])) + len(
            report.missing_locally
        )
        summary["total_upgrade_candidates"] = int(str(summary["total_upgrade_candidates"])) + len(
            report.upgrade_candidates
        )
        # Count matching (local wins that have a remote match)
        matching = sum(1 for r in report.local_wins if r.remote_match)
        summary["total_matching"] = int(str(summary["total_matching"])) + matching

    data["categories"] = categories_list
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_comparison(
    categories: list[str],
    top: int = 5,
    output_format: str = "text",
) -> str:
    """Run the full comparison pipeline.

    Args:
        categories: List of category names to compare.
        top: Max remote results per category query.
        output_format: 'text' or 'json'.

    Returns:
        Formatted report string.
    """
    all_local = scan_local_skills()
    grouped = group_by_category(all_local)

    reports: list[CategoryReport] = []

    for category in categories:
        local_in_category = grouped.get(category, [])
        logger.info(
            "Category '%s': %d local skills",
            category,
            len(local_in_category),
        )

        # Fetch remote skills using all search queries for this category
        search_queries = CATEGORIES.get(category, [category])
        all_remote: list[RemoteSkill] = []
        seen_refs: set[str] = set()

        for query in search_queries:
            remote = fetch_remote_skills(query, top=top)
            for skill in remote:
                if skill.ref not in seen_refs:
                    seen_refs.add(skill.ref)
                    all_remote.append(skill)

        # Sort by installs descending, cap at top * 2
        all_remote.sort(key=lambda s: s.installs_numeric, reverse=True)
        all_remote = all_remote[: top * 2]

        logger.info(
            "Category '%s': %d remote skills found",
            category,
            len(all_remote),
        )

        report = compare_category(category, local_in_category, all_remote)
        reports.append(report)

    if output_format == "json":
        return format_json(reports)
    return format_report(reports)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Compare local skills against skills.sh",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python compare_skills.py --all\n"
            "  python compare_skills.py --category security\n"
            "  python compare_skills.py --category ai --top 10\n"
            "  python compare_skills.py --all --output json\n"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Compare all categories",
    )
    group.add_argument(
        "--category",
        type=str,
        help="Compare a single category (e.g. security, ai, testing)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Max results from skills.sh per category (default: 5)",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    return parser


def main() -> int:
    """Entry point for the compare_skills script.

    Returns:
        Exit code (0 for success).
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.all:
        categories = list(CATEGORIES.keys())
    else:
        cat = args.category.lower().strip()
        if cat not in CATEGORIES:
            # Allow arbitrary categories - use the name as the search query
            logger.info("Category '%s' not predefined - using as search query", cat)
            CATEGORIES[cat] = [cat]
            CATEGORY_KEYWORDS[cat] = [cat]
        categories = [cat]

    report = run_comparison(
        categories=categories,
        top=args.top,
        output_format=args.output,
    )
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
