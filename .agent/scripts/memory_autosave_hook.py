#!/usr/bin/env python3
"""
Memory Auto-Save Hook — guarda resumen de sesion en Claude-Mem (AgentMemory).

Se ejecuta automaticamente al finalizar sesiones de Claude Code via hook Stop.
Toma las observaciones de la sesion actual y las almacena como memoria persistente
en el backend de AgentMemory (JSON fallback o ChromaDB).

Uso (configurado en .claude/settings.json):
    python3 .agent/scripts/hook_runner.py memory_autosave_hook.py

v1.0.0 - 2026-03-09
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Agregar core al path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "core"))
sys.path.insert(0, str(SCRIPT_DIR.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("antigravity.memory_autosave")

AGENT_NAME = "claude-code"


def get_project_root() -> Path:
    """Detecta el root del proyecto."""
    cwd = os.environ.get("CC_CWD", os.environ.get("PWD", str(Path.cwd())))
    return Path(cwd).resolve()


def collect_session_summary(root: Path) -> dict[str, object] | None:
    """Recopila resumen de la sesion actual desde el pipeline de observaciones."""
    try:
        from core.observation_pipeline import get_observation_pipeline

        pipeline = get_observation_pipeline(str(root))
        stats = pipeline.get_stats()

        total = stats.get("total_observations", 0)
        if total == 0:
            logger.info("Sin observaciones en esta sesion, nada que guardar")
            return None

        # Obtener observaciones recientes de esta sesion
        by_type = stats.get("by_type", {})

        # Intentar obtener resumen de sesion
        session_summaries = pipeline._store.get_recent_session_summaries(1)
        ai_summary = ""
        if session_summaries:
            ai_summary = session_summaries[0].get("ai_summary", "") or ""

        return {
            "total_observations": total,
            "by_type": by_type,
            "ai_summary": ai_summary,
            "timestamp": datetime.now().isoformat(),
            "project": root.name,
        }
    except Exception as e:
        logger.warning("No se pudo recopilar resumen de sesion: %s", e)
        return None


def save_to_agent_memory(summary: dict[str, object]) -> bool:
    """Guarda el resumen en AgentMemory como memoria persistente."""
    try:
        from core.agent_memory import get_agent_memory

        memory = get_agent_memory(AGENT_NAME)

        # Crear key descriptiva
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        project = summary.get("project", "unknown")
        total = summary.get("total_observations", 0)
        key = f"session-{project}-{ts}"

        # Crear value con resumen legible
        parts: list[str] = []
        parts.append(f"Sesion en {project} ({ts}): {total} observaciones")

        by_type = summary.get("by_type", {})
        if by_type:
            type_str = ", ".join(f"{k}: {v}" for k, v in by_type.items() if v)
            parts.append(f"Tipos: {type_str}")

        ai_summary = summary.get("ai_summary", "")
        if ai_summary:
            # Truncar si es muy largo
            if len(str(ai_summary)) > 500:
                ai_summary = str(ai_summary)[:500] + "..."
            parts.append(f"Resumen: {ai_summary}")

        value = " | ".join(parts)

        memory_id = memory.store_context(
            key=key,
            value=value,
            source_agent="session-hook",
        )
        logger.info("Memoria guardada: %s (id=%s)", key, memory_id)
        return True

    except Exception as e:
        logger.warning("No se pudo guardar en AgentMemory: %s", e)
        return False


def main() -> None:
    """Entry point del hook."""
    root = get_project_root()
    logger.info("Memory auto-save hook ejecutando para %s", root.name)

    summary = collect_session_summary(root)
    if summary:
        saved = save_to_agent_memory(summary)
        if saved:
            logger.info("Auto-save completado exitosamente")
        else:
            logger.warning("Auto-save fallo, la sesion continua normalmente")

    # Nunca bloquear la sesion
    print(json.dumps({"continue": True, "suppressOutput": True}))


if __name__ == "__main__":
    main()
