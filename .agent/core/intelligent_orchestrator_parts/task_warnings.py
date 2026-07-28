"""Generación de warnings de una tarea según su riesgo y complejidad.

Extraído de ``IntelligentOrchestrator`` (Plan 018 — paso 2 / cierre de helpers de
análisis). Función pura: no depende del estado de la instancia (antes era
``_generate_warnings``).
"""

from __future__ import annotations

from .models import TaskComplexity


def generate_warnings(task: str, risk_level: float, complexity: TaskComplexity) -> list[str]:
    """Genera warnings legibles para una tarea según riesgo, complejidad y keywords.

    Args:
        task: Descripción de la tarea.
        risk_level: Nivel de riesgo estimado (0.0-1.0).
        complexity: Complejidad detectada.

    Returns:
        Lista de warnings (posiblemente vacía).
    """
    warnings = []

    if risk_level > 0.7:
        warnings.append("⚠️ High-risk task - extra verification recommended")

    if complexity == TaskComplexity.EXPERT:
        warnings.append("⚠️ Expert-level task - may require human review")

    task_lower = task.lower()
    if "production" in task_lower:
        warnings.append("⚠️ Production environment detected - proceed with caution")

    if "delete" in task_lower or "remove" in task_lower:
        warnings.append("⚠️ Destructive operation - ensure backups exist")

    return warnings
