#!/usr/bin/env python3
"""Busqueda unificada en las capas 1 y 2 del sistema de memoria.

Busca un termino en:
- `.claude/memory/*.md` (capa 1)
- `.agent/brain/concepts/*.md`, `.agent/brain/sessions/*.md`, `.agent/brain/patterns/*.md` (capa 2)

Matching: substring case-insensitive sobre frontmatter (name, description,
tags, title) Y primeras N lineas del cuerpo. Ranking simple por cantidad de
matches y bonus si aparece en el titulo/name.

Uso:
    python .agent/scripts/memory_search.py "gateway offline"
    python .agent/scripts/memory_search.py "brain" --layer claude
    python .agent/scripts/memory_search.py "python 3.14" --json --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
BODY_LINES_PREVIEW = 40


@dataclass
class Hit:
    path: Path
    layer: str
    title: str
    description: str
    score: float
    snippet: str
    meta: dict[str, str] = field(default_factory=dict)


def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".agent").is_dir() and (candidate / ".git").exists():
            return candidate
    return Path.cwd()


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    body = text[match.end() :]
    keys: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if key:
            keys[key] = value
    return keys, body


def _score_document(
    query_tokens: list[str],
    meta: dict[str, str],
    body_preview: str,
) -> tuple[float, str]:
    """Returns (score, best_matching_snippet)."""
    title = meta.get("title") or meta.get("name", "")
    description = meta.get("description", "")
    tags = meta.get("tags", "")

    score = 0.0
    snippet = ""
    haystack_upper = {
        "title": title.lower(),
        "description": description.lower(),
        "tags": tags.lower(),
    }

    for token in query_tokens:
        token_lower = token.lower()
        if token_lower in haystack_upper["title"]:
            score += 3.0
        if token_lower in haystack_upper["description"]:
            score += 1.5
        if token_lower in haystack_upper["tags"]:
            score += 1.0

    body_lower = body_preview.lower()
    body_matches = 0
    for token in query_tokens:
        token_lower = token.lower()
        if token_lower in body_lower:
            body_matches += 1
            if not snippet:
                idx = body_lower.find(token_lower)
                start = max(0, idx - 40)
                end = min(len(body_preview), idx + 80)
                snippet = body_preview[start:end].replace("\n", " ").strip()

    score += body_matches * 0.5

    if not snippet and description:
        snippet = description[:120]
    return score, snippet


def _body_preview(body: str) -> str:
    lines = body.splitlines()[:BODY_LINES_PREVIEW]
    return "\n".join(lines)


def search_layer(
    dir_: Path,
    layer_name: str,
    query_tokens: list[str],
) -> list[Hit]:
    hits: list[Hit] = []
    if not dir_.exists():
        return hits
    for path in dir_.rglob("*.md"):
        if path.name in {"MEMORY.md", "index.md", "log.md", "BRAIN.md", "sources.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        meta, body = _parse_frontmatter(text)
        body_preview = _body_preview(body)
        score, snippet = _score_document(query_tokens, meta, body_preview)
        if score <= 0:
            continue
        hits.append(
            Hit(
                path=path,
                layer=layer_name,
                title=meta.get("title") or meta.get("name", path.stem),
                description=meta.get("description", ""),
                score=score,
                snippet=snippet,
                meta=meta,
            )
        )
    return hits


def run_search(query: str, layers: set[str], repo_root: Path) -> list[Hit]:
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    if not tokens:
        return []

    all_hits: list[Hit] = []
    if "claude" in layers:
        all_hits.extend(
            search_layer(repo_root / ".claude" / "memory", "claude-memory", tokens)
        )
    if "brain" in layers:
        brain_dir = repo_root / ".agent" / "brain"
        for sub in ("concepts", "sessions", "patterns", "connections"):
            all_hits.extend(search_layer(brain_dir / sub, f"brain-{sub}", tokens))

    all_hits.sort(key=lambda h: h.score, reverse=True)
    return all_hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified memory search")
    parser.add_argument("query", help="Search terms (space-separated)")
    parser.add_argument(
        "--layer",
        choices=("claude", "brain", "all"),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Override repo root (default: auto-detected from this script's location)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _resolve_repo_root()
    layers = {"claude", "brain"} if args.layer == "all" else {args.layer}

    hits = run_search(args.query, layers, repo_root)
    hits = hits[: args.limit]

    if args.json:
        print(
            json.dumps(
                {
                    "query": args.query,
                    "count": len(hits),
                    "hits": [
                        {
                            "path": (
                                str(h.path.relative_to(repo_root))
                                if repo_root in h.path.parents
                                else str(h.path)
                            ),
                            "layer": h.layer,
                            "title": h.title,
                            "description": h.description,
                            "score": round(h.score, 2),
                            "snippet": h.snippet,
                        }
                        for h in hits
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Memory search — {len(hits)} resultado(s) para: {args.query}")
        print()
        for hit in hits:
            try:
                rel = hit.path.relative_to(repo_root)
            except ValueError:
                rel = hit.path
            print(f"[{hit.score:.1f}] [{hit.layer}] {hit.title}")
            print(f"    {rel}")
            if hit.description:
                print(f"    {hit.description}")
            if hit.snippet and hit.snippet != hit.description:
                print(f"    ... {hit.snippet} ...")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
