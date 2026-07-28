"""
Cost Awareness Module - Integra costos en decisiones del sistema

Permite que agentes y orquestadores tomen decisiones cost-aware.
"""
# mypy: ignore-errors

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CostTier(Enum):
    """Tier de costo."""

    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


@dataclass
class CostProfile:
    """Perfil de costos para una operacion."""

    operation: str
    estimated_cost: float
    tier: CostTier
    factors: dict = field(default_factory=dict)
    alternatives: list = field(default_factory=list)


@dataclass
class BudgetState:
    """Estado del presupuesto."""

    limit: float
    spent: float
    remaining: float
    session_start: datetime = field(default_factory=datetime.now)


class CostAwareness:
    """
    Modulo de awareness de costos para decisiones inteligentes.

    Permite:
    - Estimar costos antes de operaciones
    - Sugerir alternativas mas economicas
    - Mantener tracking de presupuesto
    - Integrar costos en decisiones de orquestacion
    """

    # Costos base por tipo de operacion (USD)
    OPERATION_COSTS = {
        "llm_call_premium": 0.05,
        "llm_call_standard": 0.01,
        "llm_call_economy": 0.001,
        "agent_execution": 0.02,
        "memory_operation": 0.0001,
        "external_api": 0.001,
        "file_operation": 0.0,
    }

    def __init__(self, budget_limit: float = 10.0):
        self.budget = BudgetState(limit=budget_limit, spent=0.0, remaining=budget_limit)
        self.history: list[CostProfile] = []

    def estimate_operation_cost(
        self, operation: str, tokens: int = 0, model_tier: str = "standard", multiplier: float = 1.0
    ) -> CostProfile:
        """
        Estima costo de una operacion.

        Args:
            operation: Tipo de operacion
            tokens: Tokens estimados (para LLM)
            model_tier: Tier del modelo (premium, standard, economy)
            multiplier: Multiplicador de complejidad

        Returns:
            CostProfile con estimacion
        """
        # Costo base
        base_key = f"{operation}_{model_tier}" if "llm" in operation else operation
        base_cost = self.OPERATION_COSTS.get(base_key, 0.001)

        # Ajustar por tokens si es LLM
        if tokens > 0 and "llm" in operation:
            token_cost = (tokens / 1000) * base_cost
            estimated = token_cost * multiplier
        else:
            estimated = base_cost * multiplier

        # Determinar tier de costo
        if estimated < 0.001:
            tier = CostTier.FREE
        elif estimated < 0.01:
            tier = CostTier.LOW
        elif estimated < 0.05:
            tier = CostTier.MEDIUM
        elif estimated < 0.20:
            tier = CostTier.HIGH
        else:
            tier = CostTier.PREMIUM

        # Generar alternativas si el costo es alto
        alternatives = []
        if tier in [CostTier.HIGH, CostTier.PREMIUM]:
            if model_tier == "premium":
                alternatives.append(
                    {"suggestion": "Use standard model", "estimated_savings": estimated * 0.6}
                )
            if multiplier > 1:
                alternatives.append(
                    {"suggestion": "Reduce complexity", "estimated_savings": estimated * 0.3}
                )

        return CostProfile(
            operation=operation,
            estimated_cost=estimated,
            tier=tier,
            factors={
                "base_cost": base_cost,
                "tokens": tokens,
                "model_tier": model_tier,
                "multiplier": multiplier,
            },
            alternatives=alternatives,
        )

    def check_budget(self, estimated_cost: float) -> dict:
        """
        Verifica si hay presupuesto disponible.

        Args:
            estimated_cost: Costo estimado de la operacion

        Returns:
            Dict con estado de presupuesto
        """
        will_exceed = (self.budget.spent + estimated_cost) > self.budget.limit
        usage_percent = ((self.budget.spent + estimated_cost) / self.budget.limit) * 100

        return {
            "approved": not will_exceed,
            "current_spent": self.budget.spent,
            "estimated_cost": estimated_cost,
            "remaining_after": max(0, self.budget.remaining - estimated_cost),
            "usage_percent": min(100, usage_percent),
            "warning": usage_percent > 80,
            "message": self._get_budget_message(usage_percent, will_exceed),
        }

    def _get_budget_message(self, usage: float, exceeds: bool) -> str:
        """Genera mensaje de presupuesto."""
        if exceeds:
            return "BLOCKED: Operation would exceed budget limit"
        if usage > 90:
            return "CRITICAL: Approaching budget limit"
        if usage > 80:
            return "WARNING: High budget usage"
        if usage > 50:
            return "INFO: Moderate budget usage"
        return "OK: Budget healthy"

    def record_cost(self, operation: str, actual_cost: float):
        """
        Registra costo real de una operacion.

        Args:
            operation: Nombre de la operacion
            actual_cost: Costo real incurrido
        """
        self.budget.spent += actual_cost
        self.budget.remaining = max(0, self.budget.limit - self.budget.spent)

        self.history.append(
            CostProfile(
                operation=operation,
                estimated_cost=actual_cost,
                tier=self._get_tier_for_cost(actual_cost),
            )
        )

    def _get_tier_for_cost(self, cost: float) -> CostTier:
        """Obtiene tier para un costo."""
        if cost < 0.001:
            return CostTier.FREE
        if cost < 0.01:
            return CostTier.LOW
        if cost < 0.05:
            return CostTier.MEDIUM
        if cost < 0.20:
            return CostTier.HIGH
        return CostTier.PREMIUM

    def get_cost_optimized_plan(self, steps: list[dict], max_budget: float | None = None) -> dict:
        """
        Optimiza un plan para costos.

        Args:
            steps: Lista de pasos del plan
            max_budget: Presupuesto maximo (default: remaining)

        Returns:
            Plan optimizado con estimaciones de costo
        """
        budget = max_budget or self.budget.remaining
        total_cost = 0.0
        optimized_steps = []
        warnings = []

        for step in steps:
            operation = step.get("operation", "unknown")
            model = step.get("model", "standard")
            tokens = step.get("estimated_tokens", 1000)

            # Estimar costo
            profile = self.estimate_operation_cost(
                operation=operation, tokens=tokens, model_tier=model
            )

            # Verificar si cabe en presupuesto
            if total_cost + profile.estimated_cost <= budget:
                optimized_steps.append(
                    {
                        **step,
                        "estimated_cost": profile.estimated_cost,
                        "cost_tier": profile.tier.value,
                    }
                )
                total_cost += profile.estimated_cost
            else:
                # Intentar con alternativa mas barata
                if profile.alternatives:
                    alt = profile.alternatives[0]
                    reduced_cost = profile.estimated_cost - alt["estimated_savings"]
                    if total_cost + reduced_cost <= budget:
                        optimized_steps.append(
                            {
                                **step,
                                "estimated_cost": reduced_cost,
                                "cost_tier": "optimized",
                                "optimization": alt["suggestion"],
                            }
                        )
                        total_cost += reduced_cost
                        warnings.append(f"Step {len(optimized_steps)}: {alt['suggestion']}")
                    else:
                        warnings.append(f"Step skipped due to budget: {operation}")
                else:
                    warnings.append(f"Step skipped due to budget: {operation}")

        return {
            "original_steps": len(steps),
            "optimized_steps": len(optimized_steps),
            "steps": optimized_steps,
            "total_estimated_cost": total_cost,
            "budget_remaining": budget - total_cost,
            "warnings": warnings,
            "within_budget": total_cost <= budget,
        }

    def get_summary(self) -> dict:
        """Obtiene resumen de costos."""
        return {
            "budget_limit": self.budget.limit,
            "total_spent": self.budget.spent,
            "remaining": self.budget.remaining,
            "operations_count": len(self.history),
            "cost_by_tier": self._get_cost_by_tier(),
            "session_duration_minutes": (datetime.now() - self.budget.session_start).total_seconds()
            / 60,
        }

    def _get_cost_by_tier(self) -> dict:
        """Agrupa costos por tier."""
        by_tier = {}
        for profile in self.history:
            tier = profile.tier.value
            if tier not in by_tier:
                by_tier[tier] = {"count": 0, "total": 0.0}
            by_tier[tier]["count"] += 1
            by_tier[tier]["total"] += profile.estimated_cost
        return by_tier


# Singleton para uso global
_cost_awareness: CostAwareness | None = None


def get_cost_awareness(budget: float = 10.0) -> CostAwareness:
    """Obtiene instancia singleton de CostAwareness."""
    global _cost_awareness
    if _cost_awareness is None:
        _cost_awareness = CostAwareness(budget)
    return _cost_awareness
