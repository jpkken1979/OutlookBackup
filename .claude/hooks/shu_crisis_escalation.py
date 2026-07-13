"""Hook: shu_crisis_escalation — Escalada de crisis en /shu.

Este hook se dispara DESPUÉS de post_shu_execution.py y maneja la escalada
a un agente especializado cuando se detectan condiciones de crisis
(errores, timeouts, palabras clave de urgencia).

Flujo:
    /shu execution → post_shu_execution.py → shu_crisis_escalation.py
                                              ↓
                                    ShuCrisisEscalator.should_escalate()
                                              ↓
                                    ¿Escalar?
                                    ├─ YES → EscalationContext
                                    │        ↓
                                    │     escalate_to_crisis_handler()
                                    │        ↓
                                    │     CrisisHandler agent (async)
                                    │        ↓
                                    │     Brain Network (nodo escalation_handled)
                                    │
                                    └─ NO → silent return
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run(
    goal: str,
    category_detected: str,
    user_responses: list[str],
    execution_result: str,
    execution_time_ms: float,
) -> None:
    """Escala a crisis handler si se detectan condiciones de crisis.

    Lógica:
    1. Instancia ShuCrisisEscalator
    2. Verifica should_escalate(execution_result, goal, execution_time_ms)
    3. Si YES:
       - Crea EscalationContext
       - Invoca escalate_to_crisis_handler() (async)
       - Ingesta resultado en Brain Network (nodo tipo escalation_handled)
    4. Si NO: retorna silenciosamente

    Args:
        goal: Goal text from shu execution.
        category_detected: Detected category.
        user_responses: List of responses from the execution.
        execution_result: Result of execution (success/error).
        execution_time_ms: Execution time in milliseconds.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".agent"))

    try:
        from core.shu_crisis_escalation import (
            EscalationContext,
            ShuCrisisEscalator,
        )
        from core.shu_brain_integration import ShuBrainIntegrator

        # Crear instancia del escalador
        escalator = ShuCrisisEscalator(verbose=False)

        # Verificar si debe escalar
        if not escalator.should_escalate(execution_result, goal, execution_time_ms):
            logger.debug(
                f"[DEBUG] Crisis escalation not triggered for goal: {goal[:50]}..."
            )
            return

        # Log de escalada
        logger.warning(f"[WARN] SHU escalation triggered: {goal[:50]}...")

        # Construir contexto de escalada
        error_message = ""
        if execution_result == "error":
            error_message = f"SHU execution failed for goal: {goal}"

        escalation_context = EscalationContext(
            goal=goal,
            category=category_detected,
            responses=user_responses,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
        )

        # Invocar escalada (async) de forma sincrónica
        try:
            handler_response = asyncio.run(
                escalator.escalate_to_crisis_handler(escalation_context)
            )
        except RuntimeError:
            # Si asyncio.run falla (ej: hay un event loop activo), usar fallback
            try:
                loop = asyncio.get_event_loop()
                handler_response = loop.run_until_complete(
                    escalator.escalate_to_crisis_handler(escalation_context)
                )
            except Exception as e:
                logger.warning(
                    f"[WARNING] Failed to execute async escalation: {e}, "
                    "using fallback sync response"
                )
                handler_response = {
                    "success": False,
                    "action": "fallback_sync_mode",
                    "reasoning": str(e),
                    "recommendation": "Check logs and investigate manually.",
                }

        # Ingestar escalada en Brain Network
        try:
            integrator = ShuBrainIntegrator()

            # Construir contexto de escalada para Brain
            brain_context = {
                "goal": goal,
                "category": category_detected,
                "user_responses": user_responses,
                "execution_result": execution_result,
                "execution_time_ms": execution_time_ms,
                "handler_response": handler_response,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            context_json = json.dumps(brain_context, ensure_ascii=False, indent=2)

            # Crear título descriptivo
            goal_short = goal[:50] if goal else "unnamed"
            title = f"Crisis escalation: {goal_short}..."

            # Tags para Brain Network
            tags = ["shu", "escalation", "crisis-handler", category_detected.lower()]

            # Ingestar nodo de escalada
            node = integrator.brain.ingest(
                title=title,
                context=context_json,
                area="intelligence",
                tags=tags,
                node_type="escalation_handled",
                importance="high",
            )

            logger.info(f"[INFO] SHU crisis escalation recorded: {node.slug}")

        except Exception as e:
            logger.warning(f"[WARNING] Failed to ingest escalation to Brain: {e}")

    except Exception as e:
        logger.error(
            f"[ERROR] SHU crisis escalation hook failed: {type(e).__name__}: {e}"
        )


if __name__ == "__main__":
    # For testing: python shu_crisis_escalation.py
    run(
        goal="Test goal that will timeout",
        category_detected="test",
        user_responses=["Response 1", "Response 2"],
        execution_result="error",
        execution_time_ms=35000.0,
    )
