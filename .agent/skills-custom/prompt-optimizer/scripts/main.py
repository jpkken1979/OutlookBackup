"""
Prompt Optimizer Skill — Analiza y mejora prompts para LLMs.

Uso:
    python main.py --task "Tu prompt aqui"
    python main.py --task "..." --target-model claude --json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass


@dataclass
class HeuristicResult:
    """Resultado de evaluación de una heurística."""

    name: str
    score: int  # 0-10
    weight: float
    issues: list[str]
    suggestions: list[str]

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight

    @property
    def status(self) -> str:
        if self.score >= 7:
            return "OK"
        if self.score >= 4:
            return "WARN"
        return "FAIL"


def evaluate_clarity(prompt: str) -> HeuristicResult:
    """Evalúa claridad: ¿El prompt es claro y sin ambigüedad?"""
    issues: list[str] = []
    suggestions: list[str] = []
    score = 10

    if len(prompt) < 15:
        score -= 5
        issues.append("Prompt extremadamente corto — probablemente ambiguo")
        suggestions.append("Expandir con detalles sobre el contexto y objetivo")

    vague_words = ["esto", "eso", "aquello", "algo", "alguien", "cierto", "varios", "algunos"]
    found_vague = [w for w in vague_words if re.search(rf"\b{w}\b", prompt, re.IGNORECASE)]
    if found_vague:
        score -= min(3, len(found_vague))
        issues.append(f"Términos vagos encontrados: {', '.join(found_vague)}")
        suggestions.append("Reemplazar términos vagos con referencias específicas")

    if "?" not in prompt and len(prompt) < 50:
        score -= 2
        issues.append("Sin pregunta ni directiva clara para prompts cortos")
        suggestions.append("Añadir una directiva o pregunta explícita")

    return HeuristicResult("clarity", max(0, score), 0.20, issues, suggestions)


def evaluate_specificity(prompt: str) -> HeuristicResult:
    """Evalúa especificidad: ¿Define exactamente qué se necesita?"""
    issues: list[str] = []
    suggestions: list[str] = []
    score = 5  # base score

    # Números concretos o cantidades
    if re.search(r"\b\d+\b", prompt):
        score += 2
    else:
        issues.append("Sin cantidades o métricas específicas")
        suggestions.append(
            "Añadir restricciones numéricas (ej: '3-5 oraciones', 'máximo 200 palabras')"
        )

    # Palabras de alcance
    scope_words = [
        "específico",
        "exactamente",
        "solo",
        "únicamente",
        "limitar",
        "enfocado",
        "particular",
    ]
    if any(w in prompt.lower() for w in scope_words):
        score += 2
    else:
        suggestions.append("Añadir palabras de alcance para delimitar la tarea")

    # Menciona el dominio o contexto
    if len(prompt) > 80:
        score += 1

    return HeuristicResult("specificity", min(10, score), 0.25, issues, suggestions)


def evaluate_examples(prompt: str) -> HeuristicResult:
    """Evalúa si el prompt incluye ejemplos few-shot para tareas complejas."""
    issues: list[str] = []
    suggestions: list[str] = []
    score = 0

    example_markers = [
        "ejemplo",
        "example",
        "por ejemplo",
        "ej:",
        "e.g.",
        "input:",
        "output:",
        "entrada:",
        "salida:",
    ]
    has_examples = any(m in prompt.lower() for m in example_markers)

    if has_examples:
        score = 10
    elif len(prompt) > 200:
        # Tarea compleja sin ejemplos
        score = 2
        issues.append("Tarea compleja sin ejemplos few-shot")
        suggestions.append("Añadir 1-2 ejemplos del formato input/output esperado")
    elif len(prompt) > 80:
        score = 5
        suggestions.append("Considerar añadir un ejemplo para mayor claridad")
    else:
        score = 8  # Tarea simple — ejemplos opcionales
        suggestions.append("Para tareas simples los ejemplos son opcionales")

    return HeuristicResult("examples", score, 0.20, issues, suggestions)


def evaluate_output_format(prompt: str) -> HeuristicResult:
    """Evalúa si el prompt define el formato de salida esperado."""
    issues: list[str] = []
    suggestions: list[str] = []
    score = 0

    format_keywords = [
        "json",
        "markdown",
        "lista",
        "list",
        "tabla",
        "table",
        "csv",
        "formato",
        "format",
        "structure",
        "estructurado",
        "bullet",
        "oraciones",
        "párrafos",
        "puntos",
        "xml",
        "html",
    ]
    found = [w for w in format_keywords if w in prompt.lower()]

    if found:
        score = 9
    else:
        score = 1
        issues.append("No se especifica el formato de salida")
        suggestions.append(
            "Añadir indicación de formato: 'Responde en formato JSON', "
            "'Usa una lista con viñetas', 'Devuelve un párrafo de máximo X palabras'"
        )

    return HeuristicResult("output_format", score, 0.20, issues, suggestions)


def evaluate_role_setting(prompt: str) -> HeuristicResult:
    """Evalúa si el prompt establece el rol o contexto del asistente."""
    issues: list[str] = []
    suggestions: list[str] = []
    score = 0

    role_patterns = [
        r"\beres\b",
        r"\bact[uú]a como\b",
        r"\beres un\b",
        r"\beres una\b",
        r"\byou are\b",
        r"\bact as\b",
        r"\bpretend\b",
        r"\bexperto en\b",
        r"\bespecialista en\b",
        r"\basistente de\b",
        r"\btu rol es\b",
        r"\btu tarea es\b",
        r"\bcomo\b.*\bexperto\b",
    ]
    has_role = any(re.search(p, prompt, re.IGNORECASE) for p in role_patterns)

    if has_role:
        score = 10
    else:
        score = 0
        issues.append("Sin establecimiento de rol o contexto para el asistente")
        suggestions.append(
            "Añadir un rol al inicio: 'Eres un experto en X con Y años de experiencia. Tu tarea es...'"
        )

    return HeuristicResult("role_setting", score, 0.15, issues, suggestions)


def generate_improved_prompt(prompt: str, results: list[HeuristicResult], target_model: str) -> str:
    """Genera versión mejorada del prompt basada en los resultados de heurísticas."""
    improved_parts: list[str] = []

    # Añadir rol si falta
    role_result = next(r for r in results if r.name == "role_setting")
    if role_result.score < 5:
        improved_parts.append("Eres un asistente experto y preciso.")

    # Prompt original (limpiado)
    improved_parts.append(prompt.strip())

    # Añadir formato de salida si falta
    format_result = next(r for r in results if r.name == "output_format")
    if format_result.score < 5:
        improved_parts.append("\nResponde de forma estructurada y concisa.")

    # Añadir ejemplo placeholder si falta y la tarea es compleja
    examples_result = next(r for r in results if r.name == "examples")
    if examples_result.score < 5 and len(prompt) > 100:
        improved_parts.append(
            "\nEjemplo del formato esperado:\n"
            "  Input: [ejemplo de entrada]\n"
            "  Output: [ejemplo de salida esperado]"
        )

    # Nota especifica de modelo
    model_notes = {
        "claude": "\n[Nota para Claude: sigue las instrucciones al pie de la letra y sé conciso.]",
        "gpt": "\n[Nota para GPT: responde solo con el contenido solicitado, sin preámbulos.]",
        "groq": "\n[Nota para Groq: mantén la respuesta breve y directa.]",
    }
    if target_model in model_notes:
        improved_parts.append(model_notes[target_model])

    return "\n".join(improved_parts)


def format_report(
    prompt: str,
    results: list[HeuristicResult],
    improved_prompt: str,
    total_score: float,
) -> str:
    """Formatea el reporte completo."""
    lines: list[str] = [
        "=== PROMPT OPTIMIZER REPORT ===",
        f"Prompt original: {prompt[:100]}{'...' if len(prompt) > 100 else ''}",
        f"Score total: {total_score:.0f}/100",
        "",
        "Heurísticas:",
    ]

    for r in results:
        issues_str = " — " + "; ".join(r.issues) if r.issues else ""
        lines.append(f"  {r.name:<16} {r.score:>2}/10  [{r.status}]{issues_str}")

    if any(r.suggestions for r in results):
        lines.append("\nMejoras aplicadas:")
        for r in results:
            for s in r.suggestions:
                if r.score < 7:
                    lines.append(f"  [{r.name}] {s}")

    lines.append("\n=== PROMPT MEJORADO ===")
    lines.append(improved_prompt)

    return "\n".join(lines)


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(description="Analiza y mejora prompts para LLMs.")
    parser.add_argument("--task", required=True, help="El prompt a analizar")
    parser.add_argument("--target-model", choices=["claude", "gpt", "groq"], help="Modelo objetivo")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    args = parser.parse_args()

    prompt = args.task
    target_model = args.target_model or ""

    results: list[HeuristicResult] = [
        evaluate_clarity(prompt),
        evaluate_specificity(prompt),
        evaluate_examples(prompt),
        evaluate_output_format(prompt),
        evaluate_role_setting(prompt),
    ]

    total_score = sum(r.weighted_score * 10 for r in results)
    improved_prompt = generate_improved_prompt(prompt, results, target_model)

    if args.json:
        output = {
            "original_prompt": prompt,
            "total_score": round(total_score, 1),
            "heuristics": [
                {
                    "name": r.name,
                    "score": r.score,
                    "weight": r.weight,
                    "status": r.status,
                    "issues": r.issues,
                    "suggestions": r.suggestions,
                }
                for r in results
            ],
            "improved_prompt": improved_prompt,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(prompt, results, improved_prompt, total_score))


if __name__ == "__main__":
    main()
