#!/usr/bin/env python3
"""
Portable catalog builder for Frontend Design Galaxy.

This script turns curated DESIGN.md references into a reusable local catalog,
keeps a small cache of normalized markdown references, and can materialize a
project-level DESIGN.md or design-system/MASTER.md from a selected style.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("antigravity.design_galaxy")

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = REPO_ROOT / ".agent"
SKILL_ROOT = AGENT_ROOT / "skills" / "frontend-design-galaxy"
RESOURCES_DIR = SKILL_ROOT / "resources"
DESIGNS_DIR = SKILL_ROOT / "designs"
SEED_CATALOG_PATH = RESOURCES_DIR / "catalog_seed.json"
CATALOG_PATH = RESOURCES_DIR / "catalog.json"
CATALOG_SCHEMA_PATH = RESOURCES_DIR / "catalog.schema.json"

DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "OpenAntigravity-DesignGalaxy/2.0"


@dataclass(slots=True)
class DesignReference:
    """Normalized representation of a remote or cached design reference."""

    slug: str
    name: str
    category: str
    source_repo: str
    source_url: str
    remote_url: str
    vibe: str
    best_for: list[str] = field(default_factory=list)
    palette_notes: str = ""
    typography_notes: str = ""
    layout_notes: str = ""
    component_notes: str = ""
    availability: str = "seed"
    remote_excerpt: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> DesignReference:
        """Create an instance from JSON data."""
        return cls(
            slug=str(payload["slug"]),
            name=str(payload["name"]),
            category=str(payload["category"]),
            source_repo=str(payload["source_repo"]),
            source_url=str(payload["source_url"]),
            remote_url=str(payload["remote_url"]),
            vibe=str(payload["vibe"]),
            best_for=[str(item) for item in payload.get("best_for", [])],
            palette_notes=str(payload.get("palette_notes", "")),
            typography_notes=str(payload.get("typography_notes", "")),
            layout_notes=str(payload.get("layout_notes", "")),
            component_notes=str(payload.get("component_notes", "")),
            availability=str(payload.get("availability", "seed")),
            remote_excerpt=str(payload.get("remote_excerpt", "")),
            tags=[str(item) for item in payload.get("tags", [])],
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dictionary."""
        return asdict(self)


def configure_logging(verbose: bool = False) -> None:
    """Configure process logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _ensure_parent(path: Path) -> None:
    """Create parent directories for a path."""
    path.parent.mkdir(parents=True, exist_ok=True)


def load_seed_catalog(seed_path: Path | None = None) -> list[DesignReference]:
    """Load seed entries from JSON."""
    if seed_path is None:
        seed_path = SEED_CATALOG_PATH
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    return [DesignReference.from_dict(entry) for entry in payload["entries"]]


def fetch_remote_excerpt(remote_url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Fetch a short normalized excerpt from a remote design reference."""
    request = Request(
        remote_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html, text/plain, application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        LOGGER.warning("Could not fetch %s: %s", remote_url, exc)
        return ""

    text = raw
    if "<html" in raw.lower():
        patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                text = match.group(1)
                break
        else:
            text = re.sub(r"<[^>]+>", " ", raw)

    normalized = " ".join(unescape(text).split())
    return normalized[:700].strip()


def _with_availability(entry: DesignReference, has_cache: bool) -> DesignReference:
    """Clone an entry with availability resolved from cache/remote state."""
    entry_dict = entry.to_dict()
    if has_cache:
        entry_dict["availability"] = "cached"
    elif entry.remote_excerpt:
        entry_dict["availability"] = "remote"
    else:
        entry_dict["availability"] = "seed"
    return DesignReference.from_dict(entry_dict)


def build_catalog(
    entries: list[DesignReference],
    *,
    refresh_remote: bool = False,
    fetcher=fetch_remote_excerpt,
) -> list[DesignReference]:
    """Build the in-memory catalog, optionally enriching remote summaries."""
    catalog: list[DesignReference] = []

    for entry in entries:
        payload = entry.to_dict()
        if refresh_remote:
            excerpt = fetcher(entry.remote_url)
            if excerpt:
                payload["remote_excerpt"] = excerpt

        cached_file = DESIGNS_DIR / f"{entry.slug}.md"
        catalog.append(_with_availability(DesignReference.from_dict(payload), cached_file.exists()))

    return catalog


def write_catalog(entries: list[DesignReference], output_path: Path | None = None) -> Path:
    """Write the normalized catalog JSON to disk."""
    if output_path is None:
        output_path = CATALOG_PATH
    _ensure_parent(output_path)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "frontend-design-galaxy",
        "schema": str(CATALOG_SCHEMA_PATH.name),
        "entries": [entry.to_dict() for entry in entries],
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def render_reference_markdown(entry: DesignReference) -> str:
    """Render a normalized local reference markdown file."""
    best_for_lines = "\n".join(f"- {item}" for item in entry.best_for)
    tag_line = ", ".join(entry.tags) if entry.tags else "design-reference"
    remote_excerpt = (
        entry.remote_excerpt or "Remote excerpt unavailable. Use the style notes below."
    )
    return "\n".join(
        [
            f"# {entry.name}",
            "",
            f"- **Slug:** `{entry.slug}`",
            f"- **Category:** {entry.category}",
            f"- **Availability:** {entry.availability}",
            f"- **Source repo:** {entry.source_repo}",
            f"- **Source:** {entry.source_url}",
            f"- **Remote reference:** {entry.remote_url}",
            f"- **Tags:** {tag_line}",
            "",
            "## Vibe",
            "",
            entry.vibe,
            "",
            "## Best For",
            "",
            best_for_lines,
            "",
            "## Palette Notes",
            "",
            entry.palette_notes,
            "",
            "## Typography Notes",
            "",
            entry.typography_notes,
            "",
            "## Layout Notes",
            "",
            entry.layout_notes,
            "",
            "## Component Notes",
            "",
            entry.component_notes,
            "",
            "## Remote Excerpt",
            "",
            remote_excerpt,
            "",
            "## Integration Hints",
            "",
            "- Start from semantic tokens, not raw copied colors.",
            "- Keep the reference as a direction; adapt it to the product domain.",
            "- Preserve accessibility and interaction clarity over aesthetic mimicry.",
            "",
        ]
    )


def write_design_cache(
    entries: list[DesignReference], designs_dir: Path | None = None
) -> list[Path]:
    """Write normalized local markdown references."""
    if designs_dir is None:
        designs_dir = DESIGNS_DIR
    designs_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    for entry in entries:
        output_path = designs_dir / f"{entry.slug}.md"
        output_path.write_text(render_reference_markdown(entry), encoding="utf-8")
        written_paths.append(output_path)

    return written_paths


def _refresh_availability(entries: list[DesignReference]) -> list[DesignReference]:
    """Recompute availability after cache writes."""
    refreshed: list[DesignReference] = []
    for entry in entries:
        refreshed.append(_with_availability(entry, (DESIGNS_DIR / f"{entry.slug}.md").exists()))
    return refreshed


def sync_catalog(
    *,
    refresh_remote: bool = False,
    cache_slugs: set[str] | None = None,
    fetcher=fetch_remote_excerpt,
) -> list[DesignReference]:
    """Build the catalog and sync cached markdown references."""
    entries = build_catalog(load_seed_catalog(), refresh_remote=refresh_remote, fetcher=fetcher)
    selected_entries = [
        entry for entry in entries if cache_slugs is None or entry.slug in cache_slugs
    ]
    write_design_cache(selected_entries)
    refreshed_entries = _refresh_availability(entries)
    refreshed_selected_entries = [
        entry for entry in refreshed_entries if cache_slugs is None or entry.slug in cache_slugs
    ]
    write_design_cache(refreshed_selected_entries)
    write_catalog(refreshed_entries)
    return refreshed_entries


def _find_entry(entries: list[DesignReference], slug: str) -> DesignReference:
    """Find an entry by slug or raise a helpful error."""
    for entry in entries:
        if entry.slug == slug:
            return entry
    available = ", ".join(sorted(item.slug for item in entries))
    raise ValueError(f"Unknown slug '{slug}'. Available: {available}")


def render_project_design_md(entry: DesignReference, project_name: str) -> str:
    """Render a project DESIGN.md from a selected reference."""
    roles = "\n".join(f"- {item}" for item in entry.best_for)
    prompt_line = (
        entry.remote_excerpt
        or f"Use {entry.name} as the base direction without copying it literally."
    )
    return "\n".join(
        [
            f"# Design System: {project_name}",
            f"**Inspired by:** {entry.name}",
            f"**Reference slug:** `{entry.slug}`",
            f"**Reference source:** {entry.remote_url}",
            "",
            "## 1. Visual Theme & Atmosphere",
            entry.vibe,
            "",
            "## 2. Color Palette & Roles",
            entry.palette_notes,
            "",
            "## 3. Typography Rules",
            entry.typography_notes,
            "",
            "## 4. Component Stylings",
            entry.component_notes,
            "",
            "## 5. Layout Principles",
            entry.layout_notes,
            "",
            "## 6. Depth & Elevation",
            "Use restrained elevation. Favor subtle borders, layered surfaces, and shadows only when they clarify hierarchy.",
            "",
            "## 7. Do's and Don'ts",
            "- Do translate the reference into semantic tokens.",
            "- Do preserve accessibility and content clarity.",
            "- Don't clone branding blindly.",
            "- Don't let decoration reduce scannability.",
            "",
            "## 8. Responsive Behavior",
            "Maintain the same visual personality across breakpoints while simplifying density and motion on smaller screens.",
            "",
            "## 9. Agent Prompt Guide",
            "- Best for:",
            roles,
            "- Quick direction:",
            f"  {prompt_line}",
            "",
        ]
    )


def render_master_design_system(entry: DesignReference, project_name: str) -> str:
    """Render a design-system/MASTER.md file from a reference."""
    return "\n".join(
        [
            f"# {project_name} Master Design System",
            "",
            "## Source Reference",
            f"- **Primary reference:** {entry.name}",
            f"- **Slug:** `{entry.slug}`",
            "- **Catalog source:** `.agent/skills/frontend-design-galaxy/resources/catalog.json`",
            f"- **Remote source:** {entry.remote_url}",
            "",
            "## Design Direction",
            entry.vibe,
            "",
            "## Foundations",
            f"- **Palette:** {entry.palette_notes}",
            f"- **Typography:** {entry.typography_notes}",
            f"- **Layout:** {entry.layout_notes}",
            f"- **Components:** {entry.component_notes}",
            "",
            "## Tokenization Rules",
            "1. Convert raw colors into semantic tokens before implementation.",
            "2. Keep spacing and radius scales consistent across all components.",
            "3. Map emphasis and contrast to product hierarchy, not to decoration.",
            "4. Preserve accessibility when adapting the reference.",
            "",
            "## Build Rules",
            "1. Reuse this file as the visual source of truth.",
            "2. Add page-level overrides in `design-system/pages/<page>.md` only when needed.",
            "3. Keep product copy and information density aligned with the reference's intent, not its branding.",
            "",
        ]
    )


def materialize_reference(
    slug: str,
    *,
    project_dir: Path,
    project_name: str,
    output_format: str,
    refresh_remote: bool = False,
) -> list[Path]:
    """Create project artifacts from a reference slug."""
    entries = build_catalog(load_seed_catalog(), refresh_remote=refresh_remote)
    entry = _find_entry(entries, slug)
    written_paths: list[Path] = []

    if output_format in {"design-md", "both"}:
        design_md_path = project_dir / "DESIGN.md"
        _ensure_parent(design_md_path)
        design_md_path.write_text(render_project_design_md(entry, project_name), encoding="utf-8")
        written_paths.append(design_md_path)

    if output_format in {"master", "both"}:
        master_path = project_dir / "design-system" / "MASTER.md"
        _ensure_parent(master_path)
        master_path.write_text(render_master_design_system(entry, project_name), encoding="utf-8")
        written_paths.append(master_path)

    return written_paths


def _print_entries(entries: list[DesignReference]) -> None:
    """Print the catalog to stdout."""
    for entry in sorted(entries, key=lambda item: item.slug):
        LOGGER.info(
            "%s | %s | %s | %s",
            entry.slug,
            entry.category,
            entry.availability,
            entry.vibe,
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List normalized design references")

    sync_parser = subparsers.add_parser("sync", help="Build catalog and cache local references")
    sync_parser.add_argument(
        "--refresh-remote",
        action="store_true",
        help="Refresh excerpts from remote sources before writing cache",
    )
    sync_parser.add_argument(
        "--slug",
        action="append",
        default=[],
        help="Cache only selected slug(s). Catalog JSON is still written for all entries.",
    )

    fetch_parser = subparsers.add_parser("fetch", help="Refresh and cache one reference")
    fetch_parser.add_argument("--slug", required=True, help="Reference slug to fetch")

    materialize_parser = subparsers.add_parser(
        "materialize",
        help="Create DESIGN.md and/or design-system/MASTER.md from a reference",
    )
    materialize_parser.add_argument("--slug", required=True, help="Reference slug to use")
    materialize_parser.add_argument(
        "--project-dir",
        default=".",
        help="Target project directory where files will be created",
    )
    materialize_parser.add_argument(
        "--project-name",
        default="Project",
        help="Human-readable project name for generated artifacts",
    )
    materialize_parser.add_argument(
        "--format",
        choices=["design-md", "master", "both"],
        default="both",
        help="Artifact format to generate",
    )
    materialize_parser.add_argument(
        "--refresh-remote",
        action="store_true",
        help="Refresh the selected reference from the remote source first",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    command = args.command or "sync"

    if command == "list":
        _print_entries(build_catalog(load_seed_catalog()))
        return 0

    if command == "sync":
        slugs = set(args.slug) if args.slug else None
        entries = sync_catalog(refresh_remote=args.refresh_remote, cache_slugs=slugs)
        LOGGER.info("Catalog synced: %d entries -> %s", len(entries), CATALOG_PATH)
        return 0

    if command == "fetch":
        entries = sync_catalog(refresh_remote=True, cache_slugs={args.slug})
        entry = _find_entry(entries, args.slug)
        LOGGER.info("Fetched %s -> %s", entry.slug, DESIGNS_DIR / f"{entry.slug}.md")
        return 0

    if command == "materialize":
        project_dir = Path(args.project_dir).expanduser().resolve()
        written_paths = materialize_reference(
            args.slug,
            project_dir=project_dir,
            project_name=args.project_name,
            output_format=args.format,
            refresh_remote=args.refresh_remote,
        )
        for path in written_paths:
            LOGGER.info("Created %s", path)
        return 0

    parser.error(f"Unsupported command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
