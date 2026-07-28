"""Analizador de complejidad de tareas (funcion pura).

Extraido de IntelligentOrchestrator._detect_complexity (Plan 018 — paso 2).
La funcion es pura: no depende de self ni de estado externo.
IntelligentOrchestrator._detect_complexity delega aqui preservando la firma
original del metodo para que todos los callers internos sigan funcionando igual.
"""

from __future__ import annotations

from .models import TaskComplexity


def detect_complexity(task: str) -> TaskComplexity:
    """Detecta el nivel de complejidad de una tarea.

    Funcion pura extraida de IntelligentOrchestrator._detect_complexity.
    Aplica reglas de keyword-matching y heuristicas de longitud.

    Args:
        task: Descripcion de la tarea a analizar.

    Returns:
        Nivel de complejidad correspondiente a la tarea.
    """
    task_lower = task.lower()

    # Research indicators
    research_keywords = ["research", "investigate", "explore", "analyze", "study", "compare"]
    if any(kw in task_lower for kw in research_keywords):
        return TaskComplexity.RESEARCH

    # Expert indicators
    expert_keywords = [
        "architect",
        "design system",
        "security audit",
        "performance optimization",
        "migrate",
    ]
    if any(kw in task_lower for kw in expert_keywords):
        return TaskComplexity.EXPERT

    # Complex indicators
    complex_keywords = ["implement", "create", "build", "develop", "refactor", "integrate"]
    if any(kw in task_lower for kw in complex_keywords):
        return TaskComplexity.COMPLEX

    # Moderate indicators
    moderate_keywords = ["update", "modify", "add", "change", "fix bug", "improve"]
    if any(kw in task_lower for kw in moderate_keywords):
        return TaskComplexity.MODERATE

    # Simple indicators
    simple_keywords = ["rename", "move", "delete", "copy", "format", "lint"]
    if any(kw in task_lower for kw in simple_keywords):
        return TaskComplexity.SIMPLE

    # Length-based heuristic
    if len(task.split()) < 5:
        return TaskComplexity.TRIVIAL
    elif len(task.split()) < 15:
        return TaskComplexity.SIMPLE
    elif len(task.split()) < 30:
        return TaskComplexity.MODERATE
    else:
        return TaskComplexity.COMPLEX
