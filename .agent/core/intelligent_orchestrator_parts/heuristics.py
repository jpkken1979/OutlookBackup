"""Heurísticas puras de fallback para riesgo y confianza.

Extraído de ``IntelligentOrchestrator`` (Plan 018). Son los fallbacks que
``_predict_risk``/``_assess_confidence`` usan cuando los módulos de inteligencia
(``escalation``/``metacognition``) no están disponibles. Funciones puras: no
dependen del estado de la instancia ni de los módulos.
"""

from __future__ import annotations


def heuristic_risk(task: str) -> float:
    """Estima el riesgo (0.3-1.0) por presencia de keywords sensibles en la tarea.

    Args:
        task: Descripción de la tarea.

    Returns:
        Riesgo estimado: ``0.3`` base + ``0.15`` por keyword, tope ``1.0``.
    """
    risk_keywords = [
        "delete",
        "remove",
        "production",
        "deploy",
        "security",
        "password",
        "credential",
    ]
    task_lower = task.lower()
    risk_count = sum(1 for kw in risk_keywords if kw in task_lower)
    return min(0.3 + (risk_count * 0.15), 1.0)


def heuristic_confidence(domains: list[str]) -> float:
    """Estima la confianza (0.5-0.95) por familiaridad con los dominios detectados.

    Args:
        domains: Dominios detectados de la tarea.

    Returns:
        Confianza estimada: ``0.5`` base + ``0.15`` por dominio familiar, tope ``0.95``.
    """
    familiar_domains = ["frontend", "backend", "database", "testing"]
    familiarity = sum(1 for d in domains if d in familiar_domains)
    return min(0.5 + (familiarity * 0.15), 0.95)
