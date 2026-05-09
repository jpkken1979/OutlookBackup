#!/usr/bin/env python3
"""
Session Hook - Claude Code lifecycle hook para sesiones.

Este script se ejecuta automaticamente via Claude Code hooks:
- SessionStart: Inicia pipeline, inyecta contexto historico
- Stop: Genera resumen AI de la sesion, persiste datos

Uso (configurado en .claude/settings.json):
    python3 .agent/scripts/session_hook.py start
    python3 .agent/scripts/session_hook.py stop

Tambien puede invocarse manualmente:
    python3 .agent/scripts/session_hook.py start --session-id custom_id
    python3 .agent/scripts/session_hook.py stop --session-id custom_id
    python3 .agent/scripts/session_hook.py status

v1.0.0 - 2026-02-22
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

# Agregar core al path
SCRIPT_DIR = Path(__file__).parent
CORE_DIR = SCRIPT_DIR.parent / "core"
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("antigravity.session_hook")
MIN_RUNTIME_VERSION = "2.1.0"
LEGACY_CLAUDE_DIRS = ("agents", "commands", "skills", "memory-engine")


def get_project_root() -> Path:
    """Detecta el root del proyecto."""
    # Intentar desde variable de entorno (Claude Code la setea)
    cwd = os.environ.get("CC_CWD", os.environ.get("PWD", str(Path.cwd())))
    return Path(cwd).resolve()


def _parse_version(version: str) -> tuple[int, int, int]:
    """Normaliza strings de versión a tupla comparable."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return (0, 0, 0)
    return tuple(int(group) for group in match.groups())


def _read_json(path: Path) -> dict:
    """Lee JSON tolerando ausencia o corrupción."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def check_runtime_health(root: Path) -> list[str]:
    """Valida coherencia de versión y rutas legacy para detectar drift post-inyección."""
    warnings: list[str] = []

    version_path = root / ".agent" / "VERSION"
    manifest_path = root / ".antigravity" / "ai_manifest.json"
    config_path = root / ".antigravity" / "config.json"

    runtime_version = (
        version_path.read_text(encoding="utf-8").strip() if version_path.exists() else ""
    )
    manifest_version = str(_read_json(manifest_path).get("version", "")).strip()
    config_version = str(_read_json(config_path).get("version", "")).strip()

    if runtime_version and _parse_version(runtime_version) < _parse_version(MIN_RUNTIME_VERSION):
        warnings.append(
            f"Runtime desactualizado: .agent/VERSION={runtime_version} < mínimo recomendado {MIN_RUNTIME_VERSION}"
        )

    if runtime_version and manifest_version and runtime_version != manifest_version:
        warnings.append(
            f"Desalineación runtime/manifest: VERSION={runtime_version}, ai_manifest={manifest_version}"
        )

    if runtime_version and config_version and runtime_version != config_version:
        warnings.append(
            f"Desalineación runtime/config: VERSION={runtime_version}, config={config_version}"
        )

    for legacy_dir in LEGACY_CLAUDE_DIRS:
        legacy_path = root / ".claude" / legacy_dir
        if legacy_path.exists():
            warnings.append(f"Legacy detectado: .claude/{legacy_dir} (debería estar eliminado)")

    return warnings


def action_start(session_id: str | None = None) -> None:
    """Ejecuta al iniciar sesion de Claude Code.

    1. Inicia ObservationPipeline con session ID
    2. Genera contexto historico para inyeccion
    3. Carga SessionBootstrap
    4. Exporta contexto a stdout para Claude Code
    """
    root = get_project_root()
    logger.info("SessionStart hook ejecutando para %s", root.name)
    runtime_warnings = check_runtime_health(root)
    for warning in runtime_warnings:
        logger.warning("[RuntimeCheck] %s", warning)

    try:
        from core.observation_pipeline import get_observation_pipeline

        pipeline = get_observation_pipeline(str(root))

        # Iniciar sesion
        sid = pipeline.start_session(session_id)
        logger.info("Sesion iniciada: %s", sid)

        # Generar contexto historico
        context = pipeline.get_context_for_injection(max_observations=15)

        # Obtener resumenes de sesiones anteriores
        try:
            from core.session_summarizer import get_session_summarizer

            summarizer = get_session_summarizer(str(root))
            summaries_context = summarizer.get_recent_summaries_context(max_sessions=3)
        except Exception:
            summaries_context = ""

        # Combinar contexto
        full_context = ""
        if context:
            full_context += context + "\n\n"
        if summaries_context:
            full_context += summaries_context + "\n\n"

        if full_context.strip():
            # Exportar como output para que Claude Code lo capture
            if runtime_warnings:
                full_context += "\n[RuntimeCheck]\n- " + "\n- ".join(runtime_warnings) + "\n"
            output = {
                "hookSpecificOutput": full_context.strip(),
            }
            print(json.dumps(output))
            logger.info("Contexto historico inyectado (%d chars)", len(full_context))
        else:
            if runtime_warnings:
                print(
                    json.dumps(
                        {"hookSpecificOutput": "[RuntimeCheck]\n- " + "\n- ".join(runtime_warnings)}
                    )
                )
            logger.info("Sin contexto historico para inyectar")

        # Cargar SessionBootstrap si esta disponible
        try:
            from core.session_bootstrap import SessionBootstrap

            bootstrap = SessionBootstrap(str(root))
            bootstrap_context = bootstrap.get_quick_context()
            if bootstrap_context:
                logger.info("SessionBootstrap cargado (%d chars)", len(bootstrap_context))
        except Exception as e:
            logger.debug("SessionBootstrap no disponible: %s", e)

    except Exception as e:
        logger.error("Error en SessionStart hook: %s", e)
        # No bloquear la sesion por un error del hook
        print(json.dumps({"continue": True}))


async def action_stop_async(session_id: str | None = None) -> None:
    """Ejecuta al terminar sesion (async)."""
    root = get_project_root()
    logger.info("Stop hook ejecutando para %s", root.name)
    runtime_warnings = check_runtime_health(root)
    for warning in runtime_warnings:
        logger.warning("[RuntimeCheck] %s", warning)

    try:
        from core.observation_pipeline import get_observation_pipeline

        pipeline = get_observation_pipeline(str(root))

        # Finalizar sesion y generar resumen
        summary = pipeline.end_session()

        if summary and summary.total_observations > 0:
            logger.info(
                "Sesion finalizada: %d observaciones, %d archivos modificados",
                summary.total_observations,
                len(summary.files_modified),
            )

            # Generar resumen AI si hay suficientes observaciones
            if summary.total_observations >= 3:
                try:
                    from core.session_summarizer import get_session_summarizer

                    summarizer = get_session_summarizer(str(root))
                    ai_summary = await summarizer.summarize_session(summary.session_id)

                    # Guardar resumen AI
                    pipeline._store.store_session_summary(summary, ai_summary)
                    try:
                        pipeline._project_store.store_session_summary(summary, ai_summary)
                    except Exception:
                        pass

                    logger.info("Resumen AI generado para sesion %s", summary.session_id)
                except Exception as e:
                    logger.warning("No se pudo generar resumen AI: %s", e)
        else:
            logger.info("Sesion sin observaciones registradas")

    except Exception as e:
        logger.error("Error en Stop hook: %s", e)

    # Siempre dejar que Claude Code continue
    print(json.dumps({"continue": True, "suppressOutput": True}))


def action_stop(session_id: str | None = None) -> None:
    """Wrapper sync para action_stop_async."""
    asyncio.run(action_stop_async(session_id))


def action_status() -> None:
    """Muestra estado del pipeline."""
    root = get_project_root()

    try:
        from core.observation_pipeline import get_observation_pipeline

        pipeline = get_observation_pipeline(str(root))
        stats = pipeline.get_stats()

        print(f"Proyecto: {root.name}")
        print(f"Total observaciones: {stats['total_observations']}")
        print(f"Total sesiones: {stats['total_sessions']}")
        print("Por tipo:")
        for t, c in stats.get("by_type", {}).items():
            print(f"  {t}: {c}")

        # Mostrar sesiones recientes
        summaries = pipeline._store.get_recent_session_summaries(5)
        if summaries:
            print("\nSesiones recientes:")
            for s in summaries:
                has_ai = "AI" if s.get("ai_summary") else "--"
                print(
                    f"  [{has_ai}] {s['session_id']}: "
                    f"{s['total_observations']} obs, "
                    f"{s.get('success_rate', 1.0):.0%} exito"
                )

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(description="Session hook para Claude Code")
    parser.add_argument(
        "action",
        choices=["start", "stop", "status"],
        help="Accion a ejecutar",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="ID de sesion personalizado",
    )

    args = parser.parse_args()

    if args.action == "start":
        action_start(args.session_id)
    elif args.action == "stop":
        action_stop(args.session_id)
    elif args.action == "status":
        action_status()


if __name__ == "__main__":
    main()
