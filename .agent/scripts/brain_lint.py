#!/usr/bin/env python3
"""Brain Lint — auditoria de salud del Brain Network.

Expone `Brain.lint()` como script CLI. Detecta:

- `invalid_frontmatter`: nodos con YAML corrupto
- `broken_link`: cross-refs a slugs inexistentes
- `missing_crossref`: links no reciprocos
- `index_desync`: nodos activos no presentes en `index.md`
- `orphan`: nodos sin inbound ni outbound links
- `concept_candidates`: tags que aparecen 3+ veces pero no son concept

Uso:
    python .agent/scripts/brain_lint.py
    python .agent/scripts/brain_lint.py --json
    python .agent/scripts/brain_lint.py --fail-on error
    python .agent/scripts/brain_lint.py --fail-on warning --severity warning

Exit codes:
    0 — sin issues del nivel configurado en --fail-on
    1 — hay issues del nivel configurado
    2 — error de ejecucion (brain-dir no existe, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".agent").is_dir() and (candidate / ".git").exists():
            return candidate
    return Path.cwd()


def _filter_issues(issues: list, min_severity: str) -> list:
    threshold = SEVERITY_ORDER.get(min_severity, 0)
    return [i for i in issues if SEVERITY_ORDER.get(i.severity, 0) >= threshold]


def _render_human(report, filtered, score: float) -> str:
    lines = [
        f"Brain Lint — {report.total_nodes} nodos, salud {score:.1f}/10",
        f"Issues mostrados: {len(filtered)} de {len(report.issues)} totales",
        "",
    ]
    if not filtered:
        lines.append("Sin issues del nivel pedido. OK.")
    else:
        by_category: dict[str, list] = {}
        for issue in filtered:
            by_category.setdefault(issue.category, []).append(issue)
        for category, entries in sorted(by_category.items()):
            lines.append(f"[{category}] {len(entries)} issue(s):")
            for issue in entries[:15]:
                prefix = f"  {issue.severity.upper():7s}"
                target = f" ({issue.node_slug})" if issue.node_slug else ""
                lines.append(f"{prefix} {issue.message}{target}")
                if issue.suggestion:
                    lines.append(f"          → {issue.suggestion}")
            if len(entries) > 15:
                lines.append(f"  ... y {len(entries) - 15} mas")
            lines.append("")
    if report.concept_candidates:
        lines.append(
            f"Concept candidates ({len(report.concept_candidates)}): "
            + ", ".join(report.concept_candidates[:10])
        )
    return "\n".join(lines)


def _render_json(report, filtered, score: float) -> str:
    return json.dumps(
        {
            "total_nodes": report.total_nodes,
            "score": round(score, 2),
            "total_issues": len(report.issues),
            "filtered_issues": len(filtered),
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "node_slug": i.node_slug,
                    "suggestion": i.suggestion,
                }
                for i in filtered
            ],
            "concept_candidates": report.concept_candidates,
        },
        ensure_ascii=False,
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain Network lint report")
    parser.add_argument("--brain-dir", default=None)
    parser.add_argument("--app-id", default="nexus-mother")
    parser.add_argument(
        "--severity",
        choices=("info", "warning", "error"),
        default="warning",
        help="Minimum severity to display (default: warning)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("info", "warning", "error", "never"),
        default="never",
        help="Return exit code 1 if issues of this severity or higher exist",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    repo_root = _resolve_repo_root()
    sys.path.insert(0, str(repo_root / ".agent"))

    brain_dir = Path(args.brain_dir) if args.brain_dir else repo_root / ".agent" / "brain"
    if not brain_dir.exists():
        print(json.dumps({"error": f"Brain dir not found: {brain_dir}"}), file=sys.stderr)
        return 2

    try:
        from core.brain import Brain  # type: ignore[import-not-found]
    except ImportError as exc:
        print(json.dumps({"error": f"Cannot import Brain: {exc}"}), file=sys.stderr)
        return 2

    brain = Brain(brain_dir, app_id=args.app_id)
    report = brain.lint()
    score = report.score

    filtered = _filter_issues(report.issues, args.severity)

    if args.json:
        print(_render_json(report, filtered, score))
    else:
        print(_render_human(report, filtered, score))

    if args.fail_on != "never":
        fail_filtered = _filter_issues(report.issues, args.fail_on)
        if fail_filtered:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
