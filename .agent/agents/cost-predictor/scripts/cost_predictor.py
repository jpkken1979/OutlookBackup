#!/usr/bin/env python3
"""
Cost Predictor Agent - Prediccion y optimizacion de costos

Predice costos antes de ejecutar planes y optimiza para eficiencia de recursos.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum


class ModelTier(Enum):
    """Tier de modelo por costo."""

    PREMIUM = "premium"  # Opus, GPT-4
    STANDARD = "standard"  # Sonnet, GPT-4-mini
    ECONOMY = "economy"  # Haiku, GPT-3.5


@dataclass
class ModelPricing:
    """Precios de un modelo LLM."""

    name: str
    tier: ModelTier
    input_cost_per_1m: float  # USD por 1M tokens de input
    output_cost_per_1m: float  # USD por 1M tokens de output
    context_window: int  # Tokens maximos


@dataclass
class CostEstimate:
    """Estimacion de costo para una tarea."""

    task_description: str
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_api_calls: int
    estimated_cost_usd: float
    confidence: float  # 0-1
    breakdown: dict = field(default_factory=dict)


@dataclass
class CheaperAlternative:
    """Alternativa mas economica."""

    model: str
    estimated_cost_usd: float
    savings_percent: float
    tradeoffs: list[str]


@dataclass
class OptimizationSuggestion:
    """Sugerencia de optimizacion."""

    type: str
    description: str
    potential_savings_usd: float
    implementation: str


class CostPredictor:
    """Predice y optimiza costos de operaciones LLM."""

    # Precios actualizados (Febrero 2026)
    MODEL_PRICING = {
        "claude-opus-4-5": ModelPricing(
            name="Claude Opus 4.5",
            tier=ModelTier.PREMIUM,
            input_cost_per_1m=15.0,
            output_cost_per_1m=75.0,
            context_window=200000,
        ),
        "claude-sonnet-4": ModelPricing(
            name="Claude Sonnet 4",
            tier=ModelTier.STANDARD,
            input_cost_per_1m=3.0,
            output_cost_per_1m=15.0,
            context_window=200000,
        ),
        "claude-haiku-3-5": ModelPricing(
            name="Claude Haiku 3.5",
            tier=ModelTier.ECONOMY,
            input_cost_per_1m=0.25,
            output_cost_per_1m=1.25,
            context_window=200000,
        ),
        "gpt-4-turbo": ModelPricing(
            name="GPT-4 Turbo",
            tier=ModelTier.PREMIUM,
            input_cost_per_1m=10.0,
            output_cost_per_1m=30.0,
            context_window=128000,
        ),
        "gpt-4o": ModelPricing(
            name="GPT-4o",
            tier=ModelTier.STANDARD,
            input_cost_per_1m=2.5,
            output_cost_per_1m=10.0,
            context_window=128000,
        ),
        "gpt-3.5-turbo": ModelPricing(
            name="GPT-3.5 Turbo",
            tier=ModelTier.ECONOMY,
            input_cost_per_1m=0.5,
            output_cost_per_1m=1.5,
            context_window=16000,
        ),
    }

    # Estimaciones base por tipo de tarea
    TASK_TOKEN_ESTIMATES = {
        "simple_question": {"input": 500, "output": 200, "calls": 1},
        "code_review": {"input": 3000, "output": 1500, "calls": 2},
        "implement_feature": {"input": 5000, "output": 3000, "calls": 5},
        "refactor": {"input": 4000, "output": 4000, "calls": 4},
        "debug": {"input": 3000, "output": 2000, "calls": 3},
        "architecture_design": {"input": 2000, "output": 3000, "calls": 2},
        "multi_agent_plan": {"input": 10000, "output": 8000, "calls": 10},
        "full_project": {"input": 50000, "output": 30000, "calls": 50},
    }

    def __init__(self, default_model: str = "claude-sonnet-4"):
        self.default_model = default_model
        self.budget_limit = float(os.getenv("COST_BUDGET_USD", "10.0"))
        self.warning_threshold = 0.8  # 80% del limite
        self.session_cost = 0.0

    def estimate_tokens(self, text: str) -> int:
        """Estima tokens en un texto (aproximado)."""
        # Regla aproximada: ~4 caracteres por token en ingles
        # En espanol/codigo puede variar
        chars = len(text)
        words = len(text.split())

        # Usar promedio de ambas estimaciones
        char_estimate = chars / 4
        word_estimate = words * 1.3

        return int((char_estimate + word_estimate) / 2)

    def classify_task(self, task_description: str) -> str:
        """Clasifica tipo de tarea basado en descripcion."""
        task_lower = task_description.lower()

        if "proyecto" in task_lower or "crear aplicacion" in task_lower:
            return "full_project"
        if "multi-agente" in task_lower or "orquestar" in task_lower:
            return "multi_agent_plan"
        if "arquitectura" in task_lower or "diseñar" in task_lower:
            return "architecture_design"
        if "refactorizar" in task_lower or "refactor" in task_lower:
            return "refactor"
        if "debug" in task_lower or "error" in task_lower or "bug" in task_lower:
            return "debug"
        if "implementar" in task_lower or "crear" in task_lower or "agregar" in task_lower:
            return "implement_feature"
        if "revisar" in task_lower or "review" in task_lower:
            return "code_review"

        return "simple_question"

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calcula costo en USD."""
        pricing = self.MODEL_PRICING.get(model)
        if not pricing:
            pricing = self.MODEL_PRICING[self.default_model]

        input_cost = (input_tokens / 1_000_000) * pricing.input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * pricing.output_cost_per_1m

        return input_cost + output_cost

    def estimate_task_cost(
        self, task_description: str, model: str | None = None, agents_count: int = 1
    ) -> CostEstimate:
        """Estima costo de una tarea."""
        model = model or self.default_model
        task_type = self.classify_task(task_description)
        base_estimate = self.TASK_TOKEN_ESTIMATES.get(
            task_type, self.TASK_TOKEN_ESTIMATES["simple_question"]
        )

        # Ajustar por complejidad de la descripcion
        desc_tokens = self.estimate_tokens(task_description)
        complexity_factor = 1 + (desc_tokens / 1000) * 0.1

        # Ajustar por numero de agentes
        agent_factor = 1 + (agents_count - 1) * 0.5

        input_tokens = int(base_estimate["input"] * complexity_factor * agent_factor)
        output_tokens = int(base_estimate["output"] * complexity_factor * agent_factor)
        api_calls = int(base_estimate["calls"] * agent_factor)

        total_cost = self.calculate_cost(input_tokens, output_tokens, model)

        # Calcular confianza basada en tipo de tarea
        confidence = 0.7
        if task_type == "simple_question":
            confidence = 0.9
        elif task_type == "full_project":
            confidence = 0.5

        return CostEstimate(
            task_description=task_description,
            model=model,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_api_calls=api_calls,
            estimated_cost_usd=total_cost,
            confidence=confidence,
            breakdown={
                "task_type": task_type,
                "complexity_factor": complexity_factor,
                "agent_factor": agent_factor,
                "input_cost": self.calculate_cost(input_tokens, 0, model),
                "output_cost": self.calculate_cost(0, output_tokens, model),
            },
        )

    def find_cheaper_alternatives(self, estimate: CostEstimate) -> list[CheaperAlternative]:
        """Encuentra alternativas mas economicas."""
        alternatives = []
        current_cost = estimate.estimated_cost_usd
        current_pricing = self.MODEL_PRICING.get(estimate.model)

        if not current_pricing:
            return alternatives

        for model_id, pricing in self.MODEL_PRICING.items():
            if model_id == estimate.model:
                continue

            # Calcular costo con este modelo
            alt_cost = self.calculate_cost(
                estimate.estimated_input_tokens, estimate.estimated_output_tokens, model_id
            )

            if alt_cost < current_cost:
                savings = ((current_cost - alt_cost) / current_cost) * 100

                # Determinar tradeoffs
                tradeoffs = []
                if pricing.tier.value != current_pricing.tier.value:
                    if pricing.tier == ModelTier.ECONOMY:
                        tradeoffs.append("Menor calidad de razonamiento")
                        tradeoffs.append("Puede requerir mas iteraciones")
                    elif pricing.tier == ModelTier.STANDARD:
                        tradeoffs.append("Calidad ligeramente menor")

                if pricing.context_window < current_pricing.context_window:
                    tradeoffs.append(f"Context window menor ({pricing.context_window:,} tokens)")

                alternatives.append(
                    CheaperAlternative(
                        model=model_id,
                        estimated_cost_usd=alt_cost,
                        savings_percent=savings,
                        tradeoffs=tradeoffs,
                    )
                )

        # Ordenar por ahorro
        alternatives.sort(key=lambda x: x.savings_percent, reverse=True)
        return alternatives

    def get_optimization_suggestions(self, estimate: CostEstimate) -> list[OptimizationSuggestion]:
        """Genera sugerencias de optimizacion."""
        suggestions = []

        # Sugerir caching si hay muchas llamadas
        if estimate.estimated_api_calls > 5:
            suggestions.append(
                OptimizationSuggestion(
                    type="caching",
                    description="Cachear resultados de sub-tareas repetitivas",
                    potential_savings_usd=estimate.estimated_cost_usd * 0.2,
                    implementation="Activar cache en orchestrator",
                )
            )

        # Sugerir modelo mas economico para tareas simples
        if estimate.breakdown.get("task_type") == "simple_question":
            haiku_cost = self.calculate_cost(
                estimate.estimated_input_tokens,
                estimate.estimated_output_tokens,
                "claude-haiku-3-5",
            )
            if haiku_cost < estimate.estimated_cost_usd:
                suggestions.append(
                    OptimizationSuggestion(
                        type="model_downgrade",
                        description="Usar Haiku para preguntas simples",
                        potential_savings_usd=estimate.estimated_cost_usd - haiku_cost,
                        implementation="Configurar auto_model_selection: true",
                    )
                )

        # Sugerir reducir paralelismo si es muy costoso
        if estimate.breakdown.get("agent_factor", 1) > 2:
            suggestions.append(
                OptimizationSuggestion(
                    type="reduce_parallelism",
                    description="Ejecutar agentes secuencialmente en vez de paralelo",
                    potential_savings_usd=estimate.estimated_cost_usd * 0.15,
                    implementation="Configurar max_parallel_agents: 2",
                )
            )

        return suggestions

    def check_budget(self, estimate: CostEstimate) -> dict:
        """Verifica si el costo esta dentro del presupuesto."""
        remaining = self.budget_limit - self.session_cost
        will_exceed = estimate.estimated_cost_usd > remaining

        percent_of_budget = (estimate.estimated_cost_usd / self.budget_limit) * 100
        is_warning = percent_of_budget >= (self.warning_threshold * 100)

        return {
            "within_budget": not will_exceed,
            "budget_limit": self.budget_limit,
            "session_spent": self.session_cost,
            "remaining": remaining,
            "estimated_cost": estimate.estimated_cost_usd,
            "percent_of_budget": percent_of_budget,
            "is_warning": is_warning,
            "message": (
                f"ADVERTENCIA: Este plan usara {percent_of_budget:.1f}% del presupuesto"
                if is_warning
                else f"OK: Costo dentro del presupuesto ({percent_of_budget:.1f}%)"
            ),
        }

    def execute(self, task: str) -> dict:
        """Ejecuta prediccion de costos."""
        task_lower = task.lower()

        # Parsear comando
        if task_lower.startswith("estimate:"):
            description = task[9:].strip()
            estimate = self.estimate_task_cost(description)
            alternatives = self.find_cheaper_alternatives(estimate)
            suggestions = self.get_optimization_suggestions(estimate)
            budget = self.check_budget(estimate)

            return {
                "operation": "estimate",
                "estimate": {
                    "task": estimate.task_description,
                    "model": estimate.model,
                    "input_tokens": estimate.estimated_input_tokens,
                    "output_tokens": estimate.estimated_output_tokens,
                    "api_calls": estimate.estimated_api_calls,
                    "cost_usd": estimate.estimated_cost_usd,
                    "confidence": estimate.confidence,
                },
                "alternatives": [
                    {
                        "model": a.model,
                        "cost_usd": a.estimated_cost_usd,
                        "savings_percent": a.savings_percent,
                        "tradeoffs": a.tradeoffs,
                    }
                    for a in alternatives[:3]
                ],
                "optimizations": [
                    {
                        "type": s.type,
                        "description": s.description,
                        "savings_usd": s.potential_savings_usd,
                    }
                    for s in suggestions
                ],
                "budget": budget,
            }

        elif task_lower.startswith("report:"):
            period = task[7:].strip() or "session"
            return {
                "operation": "report",
                "period": period,
                "total_spent": self.session_cost,
                "budget_limit": self.budget_limit,
                "remaining": self.budget_limit - self.session_cost,
            }

        else:
            # Default: estimar tarea directa
            estimate = self.estimate_task_cost(task)
            return {
                "operation": "quick_estimate",
                "cost_usd": estimate.estimated_cost_usd,
                "confidence": estimate.confidence,
                "model": estimate.model,
            }


def main():
    parser = argparse.ArgumentParser(description="Cost Predictor - Prediccion de costos LLM")
    parser.add_argument(
        "task",
        nargs="?",
        default="estimate: simple task",
        help="Tarea a estimar (estimate: <desc>, report: <period>)",
    )
    parser.add_argument("--model", default="claude-sonnet-4", help="Modelo a usar para estimacion")
    parser.add_argument("--budget", type=float, default=10.0, help="Limite de presupuesto en USD")
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")

    args = parser.parse_args()

    predictor = CostPredictor(default_model=args.model)
    predictor.budget_limit = args.budget

    result = predictor.execute(args.task)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        op = result.get("operation", "unknown")

        if op == "estimate":
            est = result["estimate"]
            print("Estimacion de Costo")
            print("=" * 40)
            print(f"Tarea: {est['task'][:50]}...")
            print(f"Modelo: {est['model']}")
            print(f"Tokens: {est['input_tokens']:,} in / {est['output_tokens']:,} out")
            print(f"Llamadas API: {est['api_calls']}")
            print(f"Costo Estimado: ${est['cost_usd']:.4f} USD")
            print(f"Confianza: {est['confidence']:.0%}")
            print()

            budget = result["budget"]
            status = "✓" if budget["within_budget"] else "✗"
            print(f"[{status}] {budget['message']}")
            print()

            if result["alternatives"]:
                print("Alternativas mas economicas:")
                for alt in result["alternatives"]:
                    print(
                        f"  - {alt['model']}: ${alt['cost_usd']:.4f} (-{alt['savings_percent']:.0f}%)"
                    )

            if result["optimizations"]:
                print("\nSugerencias de optimizacion:")
                for opt in result["optimizations"]:
                    print(f"  - {opt['description']} (ahorro: ${opt['savings_usd']:.4f})")

        elif op == "quick_estimate":
            print(f"Costo estimado: ${result['cost_usd']:.4f} USD")
            print(f"Confianza: {result['confidence']:.0%}")

        elif op == "report":
            print(f"Reporte de Costos ({result['period']})")
            print("=" * 40)
            print(f"Total gastado: ${result['total_spent']:.4f}")
            print(f"Presupuesto: ${result['budget_limit']:.2f}")
            print(f"Restante: ${result['remaining']:.4f}")

    sys.exit(0)


if __name__ == "__main__":
    main()
