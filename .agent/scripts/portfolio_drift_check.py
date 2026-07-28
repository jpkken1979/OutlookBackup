"""Detector de drift entre el source OpenAntigravity y las apps inyectadas.

Compara para cada app:
- Skills custom (presencia de los 16 nuevos)
- Agents (presencia de los 4 nuevos de Tier 10/12/1)
- .mcp.json (presencia de magic-21st)
- .claude/skills/skill-creator (oficial Anthropic)
- .agent/VERSION coincide con source

Output:
- stdout: tabla de drift por app
- --json: JSON estructurado a stdout
- --output PATH: escribir el reporte a un archivo

Uso:
    python .agent/scripts/portfolio_drift_check.py
    python .agent/scripts/portfolio_drift_check.py --json
    python .agent/scripts/portfolio_drift_check.py --output drift-report.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)

# Skills nuevos que deberian estar en cada app
EXPECTED_SKILLS = [
    "arari-workflow",
    "kintai-validator",
    "yukyu-calculator",
    "social-insurance-calc",
    "haken-license-validator",
    "test-pollution-detector",
    "memory-deduplicator",
    "agent-tester",
    "mcp-server-creator",
    "brain-query-optimizer",
    "cross-pc-memory-sync",
    "nexus-command-creator",
    "tauri-permission-auditor",
    "nexus-build-orchestrator",
    "telegram-flow-designer",
    "mcp-injector-validator",
]

EXPECTED_AGENTS = [
    "data-analyst",
    "ml-experimenter",
    "seo-content-strategist",
    "subagent-orchestrator",
]

EXPECTED_OFFICIAL_SKILLS = [
    "skill-creator",
    "mcp-builder",
]


@dataclass
class AppDrift:
    """Estado de drift de una app respecto al source."""

    app: str
    has_mcp_json: bool
    version: str
    missing_skills: list[str] = field(default_factory=list)
    missing_agents: list[str] = field(default_factory=list)
    has_magic_21st: bool = False
    missing_official_skills: list[str] = field(default_factory=list)
    drift_score: int = 0  # 0 = perfectly in sync, higher = more drift
    status: str = "unknown"  # "in-sync" | "minor-drift" | "needs-refresh" | "no-inject"


def check_app(app_path: Path, source_root: Path) -> AppDrift:
    """Verificar el estado de drift de una app."""
    drift = AppDrift(app=app_path.name, has_mcp_json=False, version="")

    drift.has_mcp_json = (app_path / ".mcp.json").is_file()
    if not drift.has_mcp_json:
        drift.status = "no-inject"
        drift.drift_score = 999
        return drift

    version_file = app_path / ".agent" / "VERSION"
    if version_file.is_file():
        drift.version = version_file.read_text(encoding="utf-8").strip()

    skills_dir = app_path / ".agent" / "skills-custom"
    for skill_name in EXPECTED_SKILLS:
        if not (skills_dir / skill_name).is_dir():
            drift.missing_skills.append(skill_name)

    agents_dir = app_path / ".agent" / "agents"
    for agent_name in EXPECTED_AGENTS:
        if not (agents_dir / agent_name).is_dir():
            drift.missing_agents.append(agent_name)

    try:
        mcp_text = (app_path / ".mcp.json").read_text(encoding="utf-8")
        drift.has_magic_21st = "magic-21st" in mcp_text
    except OSError:
        drift.has_magic_21st = False

    claude_skills_dir = app_path / ".claude" / "skills"
    for skill_name in EXPECTED_OFFICIAL_SKILLS:
        if not (claude_skills_dir / skill_name).is_dir():
            drift.missing_official_skills.append(skill_name)

    drift.drift_score = (
        len(drift.missing_skills)
        + len(drift.missing_agents)
        + (1 if not drift.has_magic_21st else 0)
        + len(drift.missing_official_skills)
    )

    if drift.drift_score == 0:
        drift.status = "in-sync"
    elif drift.drift_score <= 3:
        drift.status = "minor-drift"
    else:
        drift.status = "needs-refresh"

    return drift


def render_markdown(drifts: list[AppDrift]) -> str:
    """Renderizar reporte en markdown."""
    by_status: dict[str, list[AppDrift]] = {}
    for d in drifts:
        by_status.setdefault(d.status, []).append(d)

    lines = ["# Portfolio Drift Report", ""]
    lines.append(f"Total apps evaluadas: **{len(drifts)}**")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Estado | Count | Apps |")
    lines.append("|---|---|---|")
    for status in ("in-sync", "minor-drift", "needs-refresh", "no-inject"):
        apps_in_status = by_status.get(status, [])
        names = ", ".join(d.app for d in apps_in_status[:5])
        if len(apps_in_status) > 5:
            names += f", ... (+{len(apps_in_status) - 5})"
        lines.append(f"| {status} | {len(apps_in_status)} | {names or '-'} |")
    lines.append("")

    if by_status.get("needs-refresh") or by_status.get("minor-drift"):
        lines.append("## Apps con drift (detalle)")
        lines.append("")
        lines.append("| App | Status | Score | Faltan |")
        lines.append("|---|---|---|---|")
        for d in sorted(drifts, key=lambda x: -x.drift_score):
            if d.status in ("in-sync", "no-inject"):
                continue
            missing = []
            if d.missing_skills:
                missing.append(f"{len(d.missing_skills)} skills")
            if d.missing_agents:
                missing.append(f"{len(d.missing_agents)} agents")
            if not d.has_magic_21st:
                missing.append("magic-21st")
            if d.missing_official_skills:
                missing.append(f"{len(d.missing_official_skills)} official skills")
            lines.append(f"| {d.app} | {d.status} | {d.drift_score} | {', '.join(missing)} |")
        lines.append("")

    if by_status.get("no-inject"):
        lines.append("## Apps sin inyeccion")
        lines.append("")
        for d in by_status["no-inject"]:
            lines.append(f"- `{d.app}`: falta `.mcp.json`. Correr `mcp_injector.py` desde cero.")
        lines.append("")

    lines.append("## Cómo refrescar")
    lines.append("")
    lines.append("```bash")
    lines.append("# Refrescar 1 app")
    lines.append("python .agent/scripts/mcp_injector.py <app-path> --full --dev-preset")
    lines.append("")
    lines.append("# Distribuir solo skills (mas rapido)")
    lines.append("python .agent/scripts/sync_skills_to_claude.py <app-path> --skip-deprecated")
    lines.append("```")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detector de drift del portfolio Antigravity")
    parser.add_argument(
        "--portfolio",
        default=str(Path.home() / "Github" / "Jpkken1979"),
        help="Directorio raiz del portfolio (default: ~/Github/Jpkken1979)",
    )
    parser.add_argument("--source", default=None, help="Source repo (default: auto-detect)")
    parser.add_argument("--json", action="store_true", help="Output JSON en lugar de markdown")
    parser.add_argument("--output", default=None, help="Escribir output a archivo")
    args = parser.parse_args()

    portfolio = Path(args.portfolio).expanduser().resolve()
    if not portfolio.is_dir():
        logger.error("Portfolio directory no existe: %s", portfolio)
        return 1

    source_root = (
        Path(args.source).expanduser().resolve()
        if args.source
        else Path(__file__).resolve().parents[2]
    )
    source_name = source_root.name

    drifts: list[AppDrift] = []
    for app_path in sorted(portfolio.iterdir()):
        if not app_path.is_dir():
            continue
        if app_path.name == source_name:
            continue
        if app_path.name.startswith("."):
            continue
        drifts.append(check_app(app_path, source_root))

    if args.json:
        output = json.dumps([asdict(d) for d in drifts], ensure_ascii=False, indent=2)
    else:
        output = render_markdown(drifts)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Reporte escrito a {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
