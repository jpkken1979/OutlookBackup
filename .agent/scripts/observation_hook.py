#!/usr/bin/env python3
"""
Observation Hook - Claude Code PostToolUse hook para captura de observaciones.

Este script se ejecuta AUTOMATICAMENTE despues de cada tool use en Claude Code.
Recibe datos via stdin en formato JSON y los captura en el ObservationPipeline.

Formato de entrada (stdin de Claude Code PostToolUse):
{
    "session_id": "...",
    "cwd": "/path/to/project",
    "tool_name": "Edit",
    "tool_input": {"file_path": "...", "old_string": "...", "new_string": "..."},
    "tool_response": "File edited successfully"
}

Uso (configurado en .claude/settings.json):
    Automatico via PostToolUse hook

Tambien puede invocarse manualmente para testing:
    echo '{"tool_name":"Edit","tool_input":{"file_path":"test.py"},...}' | \\
        python3 .agent/scripts/observation_hook.py

v1.0.0 - 2026-02-22
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Agregar core al path
SCRIPT_DIR = Path(__file__).parent
CORE_DIR = SCRIPT_DIR.parent / "core"
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))

logging.basicConfig(
    level=logging.WARNING,  # Silencioso para no interferir con Claude Code
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("antigravity.observation_hook")

# Tools que NO vale la pena capturar (demasiado ruido)
SKIP_TOOLS = {
    "TodoWrite",  # Solo tracking interno
    "AskUserQuestion",  # Interaccion con usuario
    "ExitPlanMode",  # Control de flujo
    "Skill",  # Invocacion de skills
}


def read_stdin() -> dict:
    """Lee datos de stdin en formato JSON."""
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read().strip()
        if not raw:
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def capture_observation(data: dict) -> None:
    """Captura la observacion en el pipeline.

    Args:
        data: Datos del PostToolUse hook de Claude Code
    """
    tool_name = data.get("tool_name", "")

    # Skip tools que no aportan
    if tool_name in SKIP_TOOLS:
        return

    # Extraer datos
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", "")
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd", os.getcwd())

    # Detectar errores
    success = True
    error_message = None
    if isinstance(tool_response, str):
        lower_response = tool_response.lower()
        if "error" in lower_response or "failed" in lower_response:
            success = False
            error_message = tool_response[:200]

    # Truncar tool_response para no almacenar demasiado
    if isinstance(tool_response, str) and len(tool_response) > 500:
        tool_response = tool_response[:500] + "..."

    try:
        from core.observation_pipeline import get_observation_pipeline

        pipeline = get_observation_pipeline(cwd)

        obs = pipeline.capture(
            tool_name=tool_name,
            tool_input=tool_input if isinstance(tool_input, dict) else {"raw": str(tool_input)},
            tool_output=str(tool_response),
            session_id=session_id,
            success=success,
            error_message=error_message,
        )

        # Indexar en ChromaDB para busqueda semantica
        try:
            from core.hybrid_search import get_hybrid_search

            search = get_hybrid_search(cwd)
            search.index_observation(
                obs_id=obs.id,
                content=obs.to_context_string(),
                metadata={
                    "tool_name": obs.tool_name,
                    "observation_type": obs.observation_type,
                    "session_id": obs.session_id,
                    "timestamp": obs.timestamp,
                    "success": str(obs.success),
                },
            )
        except Exception:
            pass  # ChromaDB es opcional

        logger.debug(
            "Observacion capturada: %s [%s] %s",
            obs.id,
            tool_name,
            obs.tool_input_summary[:50],
        )

    except Exception as e:
        logger.debug("Error capturando observacion: %s", e)


def main() -> None:
    """Entry point del hook."""
    start = time.monotonic()

    # Leer datos de stdin
    data = read_stdin()

    if data:
        capture_observation(data)

    # Output para Claude Code (no bloquear)
    print(json.dumps({"continue": True, "suppressOutput": True}))

    elapsed = (time.monotonic() - start) * 1000
    if elapsed > 500:
        logger.warning("Observation hook lento: %.0fms", elapsed)


if __name__ == "__main__":
    main()
