#!/usr/bin/env python3
"""Reporte simple de ahorro de contexto para prompts inyectados."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / ".agent") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / ".agent"))
if str(REPO_ROOT / ".agent" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

from core.context_injection import build_injection_context, measure_prompt_footprint
from core.injection_intelligence import get_injection_config


def _load_mcp_injector():
    script_path = REPO_ROOT / ".agent" / "scripts" / "mcp_injector.py"
    spec = importlib.util.spec_from_file_location("context_budget_mcp_injector", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se pudo cargar mcp_injector.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mcp_injector = _load_mcp_injector()


def publish_metric_to_estado(
    estado_path: Path,
    report: dict[str, object],
    *,
    session_date: str,
) -> bool:
    """Publica o actualiza la métrica dentro de ESTADO_PROYECTO.md por sesión."""
    if not estado_path.exists():
        return False

    start_marker = f"<!-- CONTEXT_BUDGET:{session_date}:START -->"
    end_marker = f"<!-- CONTEXT_BUDGET:{session_date}:END -->"
    block = _render_estado_metric_block(report, session_date, start_marker, end_marker)
    content = estado_path.read_text(encoding="utf-8")

    if start_marker in content and end_marker in content:
        start_idx = content.index(start_marker)
        end_idx = content.index(end_marker) + len(end_marker)
        updated = content[:start_idx].rstrip() + "\n\n" + block
        if end_idx < len(content):
            updated += "\n\n" + content[end_idx:].lstrip("\n")
        estado_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return True

    heading = f"## Sesión {session_date}"
    if heading in content:
        start_idx = content.index(heading) + len(heading)
        updated = content[:start_idx] + "\n\n" + block + content[start_idx:]
        estado_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return True

    session_stub = f"{heading} — Métrica automática de contexto\n\n{block}\n\n"
    estado_path.write_text(session_stub + content.lstrip(), encoding="utf-8")
    return True


def _render_estado_metric_block(
    report: dict[str, object],
    session_date: str,
    start_marker: str,
    end_marker: str,
) -> str:
    recommendations = report.get("recommendations", {})
    sync_surface = report.get("injector_sync_surface", {})
    enabled_features = sync_surface.get("enabled_features", [])
    features_text = ", ".join(enabled_features) if enabled_features else "ninguna"

    return "\n".join(
        [
            start_marker,
            f"### Métrica automática de contexto ({session_date})",
            f"- legado: {report['legacy_chars']} chars / {report['legacy_tokens_approx']} tokens aprox",
            f"- compacto: {report['compact_chars']} chars / {report['compact_tokens_approx']} tokens aprox",
            f"- ahorro: {report['saved_chars']} chars / {report['saved_tokens_approx']} tokens aprox",
            f"- recomendaciones: {recommendations.get('agent_count', 0)} agentes / {recommendations.get('skill_count', 0)} skills",
            f"- sync surface activa: {features_text}",
            f"- reinyección tocaría: {report.get('reinjection_surface', {}).get('touchedCount', 0)} rutas",
            end_marker,
        ]
    )


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Mide ahorro de contexto/tokens aproximados.")
    parser.add_argument("task", help="Tarea usada para construir el contexto.")
    parser.add_argument(
        "--project-dir",
        default=str(REPO_ROOT),
        help="Ruta del proyecto a analizar.",
    )
    parser.add_argument(
        "--current-file",
        default="",
        help="Archivo actual opcional para enriquecer el contexto.",
    )
    parser.add_argument(
        "--open-file",
        action="append",
        default=[],
        help="Archivo abierto adicional. Se puede repetir.",
    )
    parser.add_argument("--sync-skills", action="store_true")
    parser.add_argument("--no-sync-skills", action="store_true")
    parser.add_argument("--sync-codex-skills", action="store_true")
    parser.add_argument("--no-sync-codex-skills", action="store_true")
    parser.add_argument("--sync-minimax-skills", action="store_true")
    parser.add_argument("--no-sync-minimax-skills", action="store_true")
    parser.add_argument("--sync-external-skills-pack", action="store_true")
    parser.add_argument("--no-sync-external-skills-pack", action="store_true")
    parser.add_argument("--sync-superpowers", action="store_true")
    parser.add_argument("--no-sync-superpowers", action="store_true")
    parser.add_argument("--sync-brainstorming-planning", action="store_true")
    parser.add_argument("--no-sync-brainstorming-planning", action="store_true")
    parser.add_argument("--sync-oh-my-claudecode", action="store_true")
    parser.add_argument("--no-sync-oh-my-claudecode", action="store_true")
    parser.add_argument(
        "--codex-skills-profile",
        choices=["smart", "all-curated", "none"],
        default="smart",
    )
    parser.add_argument(
        "--estado-path",
        default="ESTADO_PROYECTO.md",
        help="Ruta al archivo ESTADO_PROYECTO.md que se actualizará.",
    )
    parser.add_argument(
        "--session-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Fecha de sesión para publicar la métrica.",
    )
    parser.add_argument(
        "--no-update-project-state",
        action="store_true",
        help="No actualizar ESTADO_PROYECTO.md automáticamente.",
    )
    args = parser.parse_args()

    context = await build_injection_context(
        args.task,
        project_dir=args.project_dir,
        current_file=args.current_file or None,
        open_files=args.open_file or None,
    )
    report = measure_prompt_footprint(context)
    injection_config = get_injection_config(Path(args.project_dir))
    sync_plan = mcp_injector.resolve_sync_plan(
        SimpleNamespace(
            sync_skills=args.sync_skills,
            no_sync_skills=args.no_sync_skills,
            sync_codex_skills=args.sync_codex_skills,
            no_sync_codex_skills=args.no_sync_codex_skills,
            sync_minimax_skills=args.sync_minimax_skills,
            no_sync_minimax_skills=args.no_sync_minimax_skills,
            sync_external_skills_pack=args.sync_external_skills_pack,
            no_sync_external_skills_pack=args.no_sync_external_skills_pack,
            sync_superpowers=args.sync_superpowers,
            no_sync_superpowers=args.no_sync_superpowers,
            sync_brainstorming_planning=args.sync_brainstorming_planning,
            no_sync_brainstorming_planning=args.no_sync_brainstorming_planning,
            sync_oh_my_claudecode=args.sync_oh_my_claudecode,
            no_sync_oh_my_claudecode=args.no_sync_oh_my_claudecode,
            codex_skills_profile=args.codex_skills_profile,
        )
    )
    enabled_sync_features = [
        name
        for name, enabled in {
            "sync_skills": sync_plan["sync_skills"],
            "sync_codex_skills": sync_plan["sync_codex_skills"],
            "sync_minimax_skills": sync_plan["sync_minimax_skills"],
            "sync_superpowers": sync_plan["sync_superpowers"],
            "sync_brainstorming_planning": sync_plan["sync_brainstorming_planning"],
            "sync_oh_my_claudecode": sync_plan["sync_oh_my_claudecode"],
        }.items()
        if enabled
    ]
    report["project_dir"] = args.project_dir
    report["task"] = args.task
    report["recommendations"] = {
        "agents": injection_config["recommendations"]["agents"],
        "skills": injection_config["recommendations"]["skills"],
        "agent_count": len(injection_config["recommendations"]["agents"]),
        "skill_count": len(injection_config["recommendations"]["skills"]),
    }
    report["injector_sync_surface"] = {
        "enabled_features": enabled_sync_features,
        "enabled_feature_count": len(enabled_sync_features),
        "default_external_pack": sync_plan["default_external_pack"],
        "force_external_pack": sync_plan["force_external_pack"],
    }
    reinjection_analysis = mcp_injector.inspect_installation(
        Path(args.project_dir),
        REPO_ROOT,
        enable_dev_preset=True,
        include_mcp=True,
    )
    report["reinjection_surface"] = mcp_injector.summarize_reinjection_targets(reinjection_analysis)
    if not args.no_update_project_state:
        publish_metric_to_estado(
            Path(args.estado_path),
            report,
            session_date=args.session_date,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
