"""
Cost Analysis Skill — Estimación de costos LLM por tarea.

Uso:
    python main.py --task "Describe la tarea aqui"
    python main.py --task "..." --model-filter claude
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

# Tarifas en USD por millón de tokens (input, output) — actualizar según precios actuales
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-3.5": {"input": 0.80, "output": 4.00, "family": "claude"},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00, "family": "claude"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "family": "gpt"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "family": "gpt"},
    "groq-llama-3.1-8b": {"input": 0.05, "output": 0.08, "family": "groq"},
    "groq-llama-3.3-70b": {"input": 0.59, "output": 0.79, "family": "groq"},
}

TASK_TYPE_PATTERNS: dict[str, list[str]] = {
    "code": [
        r"\bcode\b",
        r"\bcodigo\b",
        r"\bscript\b",
        r"\bfunci[oó]n\b",
        r"\bimplementa\b",
        r"\brefactori\b",
    ],
    "analysis": [
        r"\banaliz\b",
        r"\bextraer\b",
        r"\bclasifica\b",
        r"\bresumen\b",
        r"\bcompar\b",
        r"\baudit\b",
    ],
    "structured_output": [
        r"\bjson\b",
        r"\bcsv\b",
        r"\btabla\b",
        r"\bxml\b",
        r"\bestructura\b",
        r"\bformato\b",
    ],
    "conversational": [],  # fallback
}

OUTPUT_MULTIPLIERS: dict[str, float] = {
    "code": 2.5,
    "analysis": 2.0,
    "structured_output": 1.5,
    "conversational": 1.2,
}

RECOMMENDED_MODEL: dict[str, str] = {
    "code": "claude-sonnet-4",
    "analysis": "groq-llama-3.3-70b",
    "structured_output": "gpt-4o-mini",
    "conversational": "groq-llama-3.1-8b",
}


@dataclass
class CostEstimate:
    """Estimación de costo para un modelo dado."""

    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    family: str


def estimate_tokens(text: str) -> int:
    """Estima cantidad de tokens (heurística: 1 token ≈ 4 caracteres)."""
    return max(1, math.ceil(len(text) / 4))


def detect_task_type(task: str) -> str:
    """Detecta el tipo de tarea usando patrones de keywords."""
    task_lower = task.lower()
    for task_type, patterns in TASK_TYPE_PATTERNS.items():
        if any(re.search(p, task_lower) for p in patterns):
            return task_type
    return "conversational"


def load_historical_costs() -> dict | None:
    """Intenta cargar historial de costos desde cost_tracker si existe."""
    tracker_path = Path(__file__).parents[4] / "core" / "cost_tracker.py"
    if not tracker_path.exists():
        return None
    # Solo indicamos que existe — integración real requiere importar el módulo
    return {"source": str(tracker_path), "note": "cost_tracker encontrado — integración disponible"}


def calculate_estimates(
    input_tokens: int,
    task_type: str,
    model_filter: str | None = None,
) -> list[CostEstimate]:
    """Calcula estimaciones de costo para todos los modelos."""
    output_tokens = math.ceil(input_tokens * OUTPUT_MULTIPLIERS[task_type])
    estimates: list[CostEstimate] = []

    for model, pricing in MODEL_PRICING.items():
        if model_filter and pricing["family"] != model_filter:
            continue

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        estimates.append(
            CostEstimate(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_cost_usd=input_cost,
                output_cost_usd=output_cost,
                total_cost_usd=input_cost + output_cost,
                family=pricing["family"],
            )
        )

    estimates.sort(key=lambda e: e.total_cost_usd)
    return estimates


def format_report(
    task: str,
    task_type: str,
    estimates: list[CostEstimate],
    recommended: str,
    historical: dict | None,
) -> str:
    """Formatea el reporte de análisis de costos."""
    lines: list[str] = [
        "=== COST ANALYSIS REPORT ===",
        f"Tarea: {task[:120]}{'...' if len(task) > 120 else ''}",
        f"Tipo detectado: {task_type}",
        f"Modelo recomendado: {recommended}",
        "",
        f"{'Modelo':<25} {'Tokens entrada':>14} {'Tokens salida':>13} {'Costo entrada':>14} {'Costo salida':>13} {'TOTAL USD':>10}",
        "-" * 95,
    ]

    for est in estimates:
        marker = " <-- RECOMENDADO" if est.model == recommended else ""
        lines.append(
            f"{est.model:<25} {est.input_tokens:>14,} {est.output_tokens:>13,} "
            f"${est.input_cost_usd:>12.6f} ${est.output_cost_usd:>11.6f} ${est.total_cost_usd:>9.6f}{marker}"
        )

    lines.append("")
    lines.append(
        f"Nota: estimacion heuristica — 1 token ≈ 4 caracteres, output x{OUTPUT_MULTIPLIERS[task_type]} del input."
    )

    if historical:
        lines.append(f"Historial de costos: {historical.get('source', 'disponible')}")

    return "\n".join(lines)


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(description="Estima costos LLM para una tarea dada.")
    parser.add_argument("--task", required=True, help="La tarea a analizar")
    parser.add_argument(
        "--model-filter", choices=["claude", "gpt", "groq"], help="Filtrar por familia de modelo"
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    args = parser.parse_args()

    input_tokens = estimate_tokens(args.task)
    task_type = detect_task_type(args.task)
    estimates = calculate_estimates(input_tokens, task_type, args.model_filter)
    recommended = RECOMMENDED_MODEL[task_type]

    # Ajustar recomendación si hay filtro aplicado
    if args.model_filter and estimates:
        recommended = estimates[0].model

    historical = load_historical_costs()

    if args.json:
        output = {
            "task_type": task_type,
            "recommended_model": recommended,
            "input_tokens": input_tokens,
            "estimates": [
                {
                    "model": e.model,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "total_cost_usd": round(e.total_cost_usd, 8),
                    "family": e.family,
                }
                for e in estimates
            ],
            "historical": historical,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(args.task, task_type, estimates, recommended, historical))


if __name__ == "__main__":
    main()
