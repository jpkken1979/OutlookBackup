"""Selección de estrategia de ejecución, sizing de pasos y selección de módulos.

Extraído de ``IntelligentOrchestrator`` (Plan 018 — paso 2). Funciones puras:
no dependen del estado de la instancia (antes eran ``_estimate_steps``,
``_select_strategy`` y ``_select_modules``).
"""

from __future__ import annotations

from .models import ExecutionStrategy, TaskComplexity


def estimate_steps(complexity: TaskComplexity) -> int:
    """Estima la cantidad de pasos de ejecución según la complejidad.

    Args:
        complexity: Complejidad detectada de la tarea.

    Returns:
        Número estimado de pasos (default 5 si la complejidad no está mapeada).
    """
    base_steps = {
        TaskComplexity.TRIVIAL: 1,
        TaskComplexity.SIMPLE: 3,
        TaskComplexity.MODERATE: 7,
        TaskComplexity.COMPLEX: 15,
        TaskComplexity.EXPERT: 25,
        TaskComplexity.RESEARCH: 20,
    }
    return base_steps.get(complexity, 5)


def select_strategy(
    complexity: TaskComplexity, risk_level: float, domains: list[str]
) -> ExecutionStrategy:
    """Selecciona la estrategia de ejecución óptima.

    Args:
        complexity: Complejidad de la tarea.
        risk_level: Nivel de riesgo estimado (0.0-1.0).
        domains: Dominios detectados.

    Returns:
        La ``ExecutionStrategy`` recomendada.
    """
    # High risk -> debate for consensus
    if risk_level > 0.8:
        return ExecutionStrategy.DEBATE

    # Research -> adaptive strategy
    if complexity == TaskComplexity.RESEARCH:
        return ExecutionStrategy.ADAPTIVE

    # Expert level -> composed skills
    if complexity == TaskComplexity.EXPERT:
        return ExecutionStrategy.COMPOSED

    # Complex with multiple domains -> collaborative
    if complexity == TaskComplexity.COMPLEX and len(domains) > 2:
        return ExecutionStrategy.COLLABORATIVE

    # Moderate -> think first
    if complexity in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]:
        return ExecutionStrategy.THINK_FIRST

    # Simple tasks -> direct execution
    return ExecutionStrategy.DIRECT


def select_modules(complexity: TaskComplexity, strategy: ExecutionStrategy) -> list[str]:
    """Selecciona los módulos de inteligencia a usar según estrategia y complejidad.

    Args:
        complexity: Complejidad de la tarea.
        strategy: Estrategia de ejecución seleccionada.

    Returns:
        Lista deduplicada de nombres de módulos.
    """
    # Always use these
    modules = ["reflection", "quality"]

    # Strategy-based selection
    if strategy == ExecutionStrategy.THINK_FIRST:
        modules.append("cot")
    elif strategy == ExecutionStrategy.DEBATE:
        modules.extend(["cot", "debate"])
    elif strategy == ExecutionStrategy.REACT:
        modules.append("react")
    elif strategy == ExecutionStrategy.COMPOSED:
        modules.extend(["cot", "composer"])
    elif strategy == ExecutionStrategy.COLLABORATIVE:
        modules.extend(["messenger", "collab_memory"])
    elif strategy == ExecutionStrategy.ADAPTIVE:
        modules.extend(["cot", "metacognition", "recovery"])

    # Complexity-based additions
    if complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]:
        modules.extend(["escalation", "explainer"])

    return list(set(modules))
