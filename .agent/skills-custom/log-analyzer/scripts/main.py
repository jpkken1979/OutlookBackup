#!/usr/bin/env python3
"""
Log Analyzer — CLI entry point for the log-analyzer skill.

    py .agent/skills-custom/log-analyzer/scripts/main.py --path gateway.log
    py .agent/skills-custom/log-analyzer/scripts/main.py --path /tmp/nexus.log --level error
    py .agent/skills-custom/log-analyzer/scripts/main.py --path .agent/logs/ --format json
    py .agent/skills-custom/log-analyzer/scripts/main.py --path /tmp/app.log --analyze --output report.md
    py .agent/skills-custom/log-analyzer/scripts/main.py --list-patterns
    py .agent/skills-custom/log-analyzer/scripts/main.py --help
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Make the skill's scripts/ directory importable when running main.py directly.
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPT_DIR.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from analyzer import AnalysisResult, run_analysis, top_frequent
from patterns import PATTERNS, PATTERNS_BY_SEVERITY

# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="log-analyzer",
        description="Analiza archivos de log para detectar patrones de errores y anomalias.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--path",
        type=str,
        required=False,
        help="Ruta al archivo o directorio de logs (.log).",
    )
    p.add_argument(
        "--level",
        type=str,
        choices=["all", "low", "medium", "high", "critical"],
        default="all",
        help="Nivel minimo de severidad a reportar (default: all).",
    )
    p.add_argument(
        "--format",
        type=str,
        choices=["text", "markdown", "json"],
        default="text",
        help="Formato de salida (default: text).",
    )
    p.add_argument(
        "--analyze",
        action="store_true",
        help="Ejecuta el analisis completo (implicito si --path esta presente).",
    )
    p.add_argument(
        "--output",
        type=str,
        help="Guarda el reporte en el archivo especificado en vez de stdout.",
    )
    p.add_argument(
        "--list-patterns",
        action="store_true",
        help="Lista todos los patrones de deteccion disponibles.",
    )
    p.add_argument(
        "--burst-window",
        type=int,
        default=300,
        help="Ventana en segundos para deteccion de bursts (default: 300).",
    )
    p.add_argument(
        "--burst-threshold",
        type=int,
        default=5,
        help="Minimo de errores en ventana para considerar burst (default: 5).",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Salida verbose (debug).",
    )
    return p


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _severity_icon(sev: str) -> str:
    return {"CRITICAL": "[!]", "HIGH": "[W]", "MEDIUM": "[=]", "LOW": "[i]"}[sev]


def format_text(result: AnalysisResult, path_label: str) -> str:
    """Format result as plain text report."""
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"LOG ANALYSIS REPORT — {path_label}")
    lines.append("=" * 60)
    lines.append(f"Scan date: {now}")
    lines.append(f"Files scanned: {result.files_scanned}")
    lines.append(f"Lines scanned: {result.total_lines:,}")
    lines.append(f"Total errors/warnings detected: {result.total_errors}")
    lines.append("")

    # ── Groups by severity ────────────────────────────────────────────────
    for sev in _SEVERITY_ORDER:
        sev_groups = [g for g in result.groups if g.severity == sev]
        if not sev_groups:
            continue
        lines.append(f"{sev} ({len(sev_groups)})")
        for g in sev_groups:
            icon = _severity_icon(sev)
            lines.append(f"  {icon} [{g.code}] {g.count}x {g.description}")
            if g.first_seen and g.last_seen:
                lines.append(f"       First: {g.first_seen}  Last: {g.last_seen}")
            if g.files:
                lines.append(f"       Files: {', '.join(g.files)}")
            lines.append("")

    # ── Time bursts ──────────────────────────────────────────────────────
    if result.bursts:
        lines.append("TIME BURST DETECTED")
        for b in result.bursts:
            lines.append(
                f"  [{b.severity}] {b.error_count} errors in {b.window_seconds}s "
                f"({b.start} → {b.end})"
            )
        lines.append("")

    # ── Top frequency ─────────────────────────────────────────────────────
    top = top_frequent(result.groups, 5)
    if top:
        lines.append("TOP 5 MOST FREQUENT")
        for idx, g in enumerate(top, start=1):
            lines.append(f"  {idx}. {g.description} ({g.count})")
        lines.append("")

    # ── Health score ───────────────────────────────────────────────────────
    score = result.health_score
    if score >= 80:
        label = "HEALTHY"
    elif score >= 50:
        label = "NEEDS ATTENTION"
    else:
        label = "CRITICAL"
    lines.append(f"HEALTH SCORE: {score}/100 ({label})")
    lines.append("")

    # ── Recommendations ───────────────────────────────────────────────────
    recommendations = _build_recommendations(result)
    if recommendations:
        lines.append("RECOMMENDATIONS:")
        for rec in recommendations:
            lines.append(f"  - {rec}")

    return "\n".join(lines)


def format_markdown(result: AnalysisResult, path_label: str) -> str:
    """Format result as Markdown report."""
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"# Log Analysis Report — {path_label}")
    lines.append("")
    lines.append(f"**Scan date:** {now}")
    lines.append(f"**Files scanned:** {result.files_scanned}")
    lines.append(f"**Lines scanned:** {result.total_lines:,}")
    lines.append(f"**Total issues:** {result.total_errors}")
    lines.append("")

    # ── Summary badge ─────────────────────────────────────────────────────
    score = result.health_score
    badge = f"`{score}/100`"
    if score >= 80:
        lines.append(f"**Health:** {badge} — HEALTHY")
    elif score >= 50:
        lines.append(f"**Health:** {badge} — NEEDS ATTENTION")
    else:
        lines.append(f"**Health:** {badge} — CRITICAL")
    lines.append("")

    # ── Findings table ────────────────────────────────────────────────────
    lines.append("## Findings")
    lines.append("")
    lines.append("| Severity | Code | Count | Description | First seen | Last seen |")
    lines.append("|---|---|---|---|---|---|")
    for g in result.groups:
        lines.append(
            f"| {g.severity} | `{g.code}` | {g.count} | {g.description} | "
            f"{g.first_seen or '-'} | {g.last_seen or '-'} |"
        )
    lines.append("")

    # ── Bursts ────────────────────────────────────────────────────────────
    if result.bursts:
        lines.append("## Time Bursts")
        lines.append("")
        for b in result.bursts:
            lines.append(
                f"- **[{b.severity}]** {b.error_count} errors in "
                f"{b.window_seconds}s — `{b.start}` → `{b.end}`"
            )
        lines.append("")

    # ── Recommendations ───────────────────────────────────────────────────
    recommendations = _build_recommendations(result)
    if recommendations:
        lines.append("## Recommendations")
        lines.append("")
        for rec in recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # ── Patterns reference ────────────────────────────────────────────────
    lines.append("## Patterns Reference")
    lines.append("")
    lines.append("| Code | Severity | Pattern |")
    lines.append("|---|---|---|")
    for p in PATTERNS:
        lines.append(f"| `{p.code}` | {p.severity} | {p.description} |")

    return "\n".join(lines)


def format_json(result: AnalysisResult, path_label: str) -> str:
    """Format result as JSON."""
    payload = result.to_dict()
    payload["_meta"] = {
        "path": path_label,
        "generated_at": datetime.now().isoformat(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _build_recommendations(result: AnalysisResult) -> list[str]:
    """Generate actionable recommendations based on findings."""
    recs: list[str] = []
    critical_keys = {g.group_key for g in result.groups if g.severity == "CRITICAL"}

    if "connection_refused" in critical_keys:
        recs.append(
            "Investigate Connection refused pattern — gateway may be overloaded "
            "or a service may be down."
        )
    if "oom_error" in critical_keys:
        recs.append("Check for memory leaks — OOM errors in brain.py or gateway.")
    if "http_500" in critical_keys:
        recs.append("Inspect HTTP 500 errors — likely a bug in request handlers.")
    if "python_exception" in critical_keys:
        recs.append("Review stack traces — Python exceptions indicate code bugs.")
    if "auth_failure" in critical_keys:
        recs.append("Audit authentication flow — failed auth may indicate attack or misconfig.")
    if "timeout_error" in critical_keys:
        recs.append("Review timeout settings — agents or network may be overloaded.")
    if not recs:
        recs.append("No critical issues found — system appears healthy.")
    return recs


# ---------------------------------------------------------------------------
# Patterns listing
# ---------------------------------------------------------------------------

def list_patterns() -> str:
    """Print all available patterns as a formatted table."""
    lines: list[str] = [
        "LOG ANALYZER — Available Patterns",
        "=" * 60,
        "",
    ]
    for sev in _SEVERITY_ORDER:
        pats = PATTERNS_BY_SEVERITY[sev]
        if not pats:
            continue
        lines.append(f"{sev} ({len(pats)})")
        lines.append("-" * 40)
        for p in pats:
            lines.append(f"  [{p.code}] {p.description}")
            lines.append(f"       regex: {p.regex}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # Fallback if stdout is not a TTY
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

    # ── --list-patterns ───────────────────────────────────────────────────
    if args.list_patterns:
        print(list_patterns())
        return 0

    # ── --path required ───────────────────────────────────────────────────
    if not args.path:
        parser.error("--path is required unless --list-patterns is used")

    target = Path(args.path).expanduser().resolve()

    if not target.exists():
        print(f"Error: path does not exist: {target}", file=sys.stderr)
        return 1

    # ── Run analysis ──────────────────────────────────────────────────────
    min_severity: str | None = {
        "all": None,  # None = no filtering, report everything
        "low": "LOW",
        "medium": "MEDIUM",
        "high": "HIGH",
        "critical": "CRITICAL",
    }.get(args.level, None)

    try:
        result = run_analysis(
            target,
            min_severity=min_severity,
            window_seconds=args.burst_window,
            burst_threshold=args.burst_threshold,
        )
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # ── Format ────────────────────────────────────────────────────────────
    path_label = str(target)
    if args.format == "markdown":
        output = format_markdown(result, path_label)
    elif args.format == "json":
        output = format_json(result, path_label)
    else:
        output = format_text(result, path_label)

    # ── Write output ──────────────────────────────────────────────────────
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Report saved to: {out_path}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
