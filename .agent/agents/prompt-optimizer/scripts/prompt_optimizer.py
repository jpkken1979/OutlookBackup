#!/usr/bin/env python3
"""
Prompt Optimizer Agent - Analiza y mejora prompts para LLMs
"""

import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PromptAnalysis:
    """Resultado del análisis de un prompt"""

    original: str
    score: float  # 0-100
    clarity: float
    specificity: float
    context: float
    structure: float
    conciseness: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    optimized: str = ""


@dataclass
class PromptTemplate:
    """Template reutilizable de prompt"""

    name: str
    template: str
    variables: list[str]
    domain: str
    effectiveness_score: float = 0.0


class PromptOptimizer:
    """Optimizador inteligente de prompts"""

    # Patrones problemáticos
    VAGUE_WORDS = [
        "algo",
        "cosa",
        "stuff",
        "thing",
        "maybe",
        "quizás",
        "algunos",
        "some",
        "etc",
        "etcétera",
        "y eso",
    ]

    WEAK_INSTRUCTIONS = [
        "intenta",
        "try to",
        "podrías",
        "could you",
        "tal vez",
        "if possible",
        "si puedes",
        "when you can",
    ]

    # Patrones de mejora
    ENHANCEMENT_PATTERNS = {
        "add_role": "Actúa como un experto en {domain}. ",
        "add_context": "\n\nContexto: {context}",
        "add_format": "\n\nFormato de respuesta: {format}",
        "add_constraints": "\n\nRestricciones:\n{constraints}",
        "add_examples": "\n\nEjemplos:\n{examples}",
        "add_steps": "\n\nPasos a seguir:\n{steps}",
    }

    def __init__(self, history_file: Path | None = None):
        self.history_file = history_file or Path(".agent/memory/prompt_history.json")
        self.history: list[dict] = []
        self._load_history()

    def _load_history(self):
        """Cargar historial de optimizaciones"""
        if self.history_file.exists():
            try:
                self.history = json.loads(self.history_file.read_text())
            except Exception:
                self.history = []

    def _save_history(self):
        """Guardar historial"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file.write_text(json.dumps(self.history, indent=2, default=str))

    def analyze(self, prompt: str) -> PromptAnalysis:
        """Analizar un prompt y devolver métricas"""
        issues = []
        suggestions = []

        # Métricas base
        clarity = self._evaluate_clarity(prompt, issues, suggestions)
        specificity = self._evaluate_specificity(prompt, issues, suggestions)
        context = self._evaluate_context(prompt, issues, suggestions)
        structure = self._evaluate_structure(prompt, issues, suggestions)
        conciseness = self._evaluate_conciseness(prompt, issues, suggestions)

        # Score ponderado
        score = (
            clarity * 0.25
            + specificity * 0.25
            + context * 0.20
            + structure * 0.15
            + conciseness * 0.15
        )

        analysis = PromptAnalysis(
            original=prompt,
            score=round(score, 1),
            clarity=round(clarity, 1),
            specificity=round(specificity, 1),
            context=round(context, 1),
            structure=round(structure, 1),
            conciseness=round(conciseness, 1),
            issues=issues,
            suggestions=suggestions,
        )

        # Generar versión optimizada
        analysis.optimized = self.optimize(prompt, analysis)

        return analysis

    def _evaluate_clarity(self, prompt: str, issues: list, suggestions: list) -> float:
        """Evaluar claridad del prompt"""
        score = 100.0

        # Penalizar palabras vagas
        for word in self.VAGUE_WORDS:
            if word.lower() in prompt.lower():
                score -= 10
                issues.append(f"Palabra vaga detectada: '{word}'")

        # Penalizar instrucciones débiles
        for weak in self.WEAK_INSTRUCTIONS:
            if weak.lower() in prompt.lower():
                score -= 8
                issues.append(f"Instrucción débil: '{weak}'")
                suggestions.append(f"Cambiar '{weak}' por instrucción directa")

        # Verificar si hay objetivo claro
        action_words = [
            "crea",
            "genera",
            "escribe",
            "analiza",
            "explica",
            "create",
            "generate",
            "write",
            "analyze",
            "explain",
            "implementa",
            "diseña",
            "revisa",
            "optimiza",
        ]
        has_action = any(w in prompt.lower() for w in action_words)
        if not has_action:
            score -= 15
            issues.append("No hay verbo de acción claro")
            suggestions.append("Agregar verbo de acción al inicio (crea, genera, analiza...)")

        return max(0, min(100, score))

    def _evaluate_specificity(self, prompt: str, issues: list, suggestions: list) -> float:
        """Evaluar especificidad del prompt"""
        score = 100.0

        # Longitud mínima para especificidad
        word_count = len(prompt.split())
        if word_count < 10:
            score -= 20
            issues.append(f"Prompt muy corto ({word_count} palabras)")
            suggestions.append("Agregar más detalles sobre el resultado esperado")

        # Verificar si hay especificaciones técnicas
        has_tech_spec = any(
            [
                re.search(r"\b(python|javascript|typescript|react|sql)\b", prompt, re.I),
                re.search(r"\b(función|function|clase|class|api|endpoint)\b", prompt, re.I),
                re.search(r"\b(formato|format|estructura|structure)\b", prompt, re.I),
            ]
        )
        if not has_tech_spec and word_count > 5:
            score -= 10
            suggestions.append("Considerar agregar especificaciones técnicas")

        # Verificar números/cantidades específicas
        has_numbers = bool(re.search(r"\d+", prompt))
        if not has_numbers:
            score -= 5
            suggestions.append("Agregar cantidades específicas si aplica")

        return max(0, min(100, score))

    def _evaluate_context(self, prompt: str, issues: list, suggestions: list) -> float:
        """Evaluar contexto proporcionado"""
        score = 70.0  # Base más bajo, contexto es opcional

        # Buscar indicadores de contexto
        context_indicators = [
            "contexto:",
            "context:",
            "background:",
            "situación:",
            "dado que",
            "given that",
            "considerando",
            "considering",
            "el proyecto",
            "the project",
            "actualmente",
            "currently",
        ]

        has_context = any(ind in prompt.lower() for ind in context_indicators)
        if has_context:
            score += 30
        else:
            suggestions.append("Considerar agregar contexto de fondo")

        # Verificar si menciona restricciones
        constraint_words = [
            "no debe",
            "must not",
            "evitar",
            "avoid",
            "límite",
            "limit",
            "máximo",
            "maximum",
            "sin",
        ]
        has_constraints = any(w in prompt.lower() for w in constraint_words)
        if has_constraints:
            score += 10

        return max(0, min(100, score))

    def _evaluate_structure(self, prompt: str, issues: list, suggestions: list) -> float:
        """Evaluar estructura del prompt"""
        score = 100.0

        # Verificar uso de listas o numeración
        has_structure = any(
            [
                "\n-" in prompt or "\n•" in prompt,
                re.search(r"\n\d+\.", prompt),
                "```" in prompt,
                "\n\n" in prompt,  # Párrafos separados
            ]
        )

        if not has_structure and len(prompt) > 200:
            score -= 20
            issues.append("Prompt largo sin estructura clara")
            suggestions.append("Dividir en secciones o usar listas")

        # Verificar formato de salida especificado
        output_indicators = [
            "devuelve",
            "return",
            "output",
            "formato:",
            "responde con",
            "respond with",
            "genera un",
        ]
        has_output_spec = any(ind in prompt.lower() for ind in output_indicators)
        if not has_output_spec:
            score -= 10
            suggestions.append("Especificar formato de salida esperado")

        return max(0, min(100, score))

    def _evaluate_conciseness(self, prompt: str, issues: list, suggestions: list) -> float:
        """Evaluar concisión del prompt"""
        score = 100.0

        # Detectar repetición de palabras
        words = prompt.lower().split()
        word_freq = {}
        for w in words:
            if len(w) > 4:
                word_freq[w] = word_freq.get(w, 0) + 1

        repeated = [w for w, c in word_freq.items() if c > 3]
        if repeated:
            score -= len(repeated) * 5
            issues.append(f"Palabras repetidas: {', '.join(repeated[:3])}")

        # Detectar frases redundantes
        redundant_patterns = [
            r"por favor[,]? por favor",
            r"muy muy",
            r"realmente realmente",
            r"básicamente[,]? básicamente",
        ]
        for pattern in redundant_patterns:
            if re.search(pattern, prompt, re.I):
                score -= 10
                issues.append("Redundancia detectada")

        return max(0, min(100, score))

    def optimize(self, prompt: str, analysis: PromptAnalysis | None = None) -> str:
        """Optimizar un prompt basado en análisis"""
        if analysis is None:
            analysis = self.analyze(prompt)

        optimized = prompt

        # Aplicar mejoras según issues

        # 1. Agregar verbo de acción si falta
        if "No hay verbo de acción" in str(analysis.issues):
            # Detectar intención y agregar verbo
            if "?" in prompt:
                optimized = "Explica: " + optimized
            else:
                optimized = "Genera: " + optimized

        # 2. Reemplazar palabras vagas
        replacements = {
            "algo": "específicamente",
            "cosa": "elemento",
            "cosas": "elementos",
            "stuff": "components",
            "thing": "element",
            "etc": "(listar elementos específicos)",
        }
        for vague, specific in replacements.items():
            pattern = rf"\b{vague}\b"
            if re.search(pattern, optimized, re.I):
                optimized = re.sub(pattern, f"[{specific}]", optimized, flags=re.I)

        # 3. Fortalecer instrucciones débiles
        strength_map = {
            "intenta": "debes",
            "try to": "must",
            "podrías": "debes",
            "could you": "you must",
            "tal vez": "",
            "if possible": "",
            "si puedes": "",
        }
        for weak, strong in strength_map.items():
            optimized = re.sub(rf"\b{weak}\b", strong, optimized, flags=re.I)

        # 4. Agregar estructura si es largo
        if len(optimized) > 200 and "\n" not in optimized:
            parts = optimized.split(". ")
            if len(parts) > 3:
                optimized = ".\n".join(parts)

        # 5. Agregar formato de salida si falta
        if analysis.structure < 70 and "formato" not in optimized.lower():
            optimized += "\n\nFormato de respuesta: [especificar formato deseado]"

        return optimized.strip()

    def compare(self, prompt_a: str, prompt_b: str) -> dict:
        """Comparar dos versiones de prompt"""
        analysis_a = self.analyze(prompt_a)
        analysis_b = self.analyze(prompt_b)

        return {
            "prompt_a": {
                "text": prompt_a[:100] + "..." if len(prompt_a) > 100 else prompt_a,
                "score": analysis_a.score,
                "metrics": {
                    "clarity": analysis_a.clarity,
                    "specificity": analysis_a.specificity,
                    "context": analysis_a.context,
                    "structure": analysis_a.structure,
                    "conciseness": analysis_a.conciseness,
                },
            },
            "prompt_b": {
                "text": prompt_b[:100] + "..." if len(prompt_b) > 100 else prompt_b,
                "score": analysis_b.score,
                "metrics": {
                    "clarity": analysis_b.clarity,
                    "specificity": analysis_b.specificity,
                    "context": analysis_b.context,
                    "structure": analysis_b.structure,
                    "conciseness": analysis_b.conciseness,
                },
            },
            "winner": "A" if analysis_a.score > analysis_b.score else "B",
            "score_diff": abs(analysis_a.score - analysis_b.score),
            "recommendation": self._generate_recommendation(analysis_a, analysis_b),
        }

    def _generate_recommendation(self, a: PromptAnalysis, b: PromptAnalysis) -> str:
        """Generar recomendación basada en comparación"""
        if a.score > b.score:
            better, worse = a, b
            label = "A"
        else:
            better, worse = b, a
            label = "B"

        recs = [f"Prompt {label} es mejor (score: {better.score} vs {worse.score})"]

        # Identificar fortalezas
        if better.clarity > worse.clarity + 10:
            recs.append("- Mayor claridad en las instrucciones")
        if better.specificity > worse.specificity + 10:
            recs.append("- Más específico en los requerimientos")
        if better.structure > worse.structure + 10:
            recs.append("- Mejor estructurado")

        return "\n".join(recs)

    def create_template(
        self, name: str, base_prompt: str, domain: str = "general"
    ) -> PromptTemplate:
        """Crear template reutilizable desde un prompt"""
        # Detectar variables potenciales
        variables = re.findall(r"\[([^\]]+)\]", base_prompt)

        # Si no hay variables marcadas, intentar detectarlas
        if not variables:
            # Buscar sustantivos específicos que podrían ser variables
            potential_vars = re.findall(
                r"\b(proyecto|archivo|función|módulo|componente)\b", base_prompt, re.I
            )
            for var in set(potential_vars):
                base_prompt = re.sub(rf"\b{var}\b", f"[{var}]", base_prompt, count=1)
            variables = list(set(potential_vars))

        template = PromptTemplate(
            name=name, template=base_prompt, variables=variables, domain=domain
        )

        return template

    def enhance_with_cot(self, prompt: str) -> str:
        """Mejorar prompt con Chain-of-Thought"""
        cot_addition = """

Antes de responder, piensa paso a paso:
1. Analiza qué se está pidiendo
2. Identifica los componentes necesarios
3. Considera posibles problemas
4. Formula tu respuesta

Muestra tu razonamiento brevemente antes de la respuesta final."""

        return prompt + cot_addition

    def enhance_with_examples(self, prompt: str, examples: list[tuple[str, str]]) -> str:
        """Mejorar prompt con few-shot examples"""
        examples_text = "\n\nEjemplos:\n"
        for i, (inp, out) in enumerate(examples, 1):
            examples_text += f"\nEjemplo {i}:\nEntrada: {inp}\nSalida: {out}\n"

        return prompt + examples_text

    def record_result(self, prompt: str, optimized: str, success: bool, feedback: str = ""):
        """Registrar resultado para aprendizaje"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "original": prompt,
            "optimized": optimized,
            "success": success,
            "feedback": feedback,
        }
        self.history.append(record)
        self._save_history()

        # Mantener solo últimos 1000 registros
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            self._save_history()


def main():
    parser = argparse.ArgumentParser(
        description="Prompt Optimizer - Analiza y mejora prompts para LLMs"
    )
    parser.add_argument("prompt", nargs="?", help="Prompt a analizar/optimizar")
    parser.add_argument("--file", "-f", help="Leer prompt desde archivo")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("A", "B"), help="Comparar dos prompts")
    parser.add_argument("--cot", action="store_true", help="Agregar Chain-of-Thought")
    parser.add_argument("--json", action="store_true", help="Output en JSON")
    parser.add_argument(
        "--optimize-only", "-o", action="store_true", help="Solo mostrar versión optimizada"
    )

    args = parser.parse_args()
    optimizer = PromptOptimizer()

    # Modo comparación
    if args.compare:
        result = optimizer.compare(args.compare[0], args.compare[1])
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("\n=== Comparación de Prompts ===\n")
            print(f"Prompt A (score: {result['prompt_a']['score']}):")
            print(f"  {result['prompt_a']['text']}\n")
            print(f"Prompt B (score: {result['prompt_b']['score']}):")
            print(f"  {result['prompt_b']['text']}\n")
            print(f"Ganador: Prompt {result['winner']} (+{result['score_diff']:.1f} puntos)")
            print(f"\n{result['recommendation']}")
        return

    # Obtener prompt
    prompt = args.prompt
    if args.file:
        prompt = Path(args.file).read_text()

    if not prompt:
        parser.print_help()
        return

    # Analizar
    analysis = optimizer.analyze(prompt)

    # Agregar CoT si se solicita
    if args.cot:
        analysis.optimized = optimizer.enhance_with_cot(analysis.optimized)

    # Output
    if args.json:
        output = {
            "original": analysis.original,
            "score": analysis.score,
            "metrics": {
                "clarity": analysis.clarity,
                "specificity": analysis.specificity,
                "context": analysis.context,
                "structure": analysis.structure,
                "conciseness": analysis.conciseness,
            },
            "issues": analysis.issues,
            "suggestions": analysis.suggestions,
            "optimized": analysis.optimized,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.optimize_only:
        print(analysis.optimized)
    else:
        print("\n" + "=" * 50)
        print("ANÁLISIS DE PROMPT")
        print("=" * 50)
        print(f"\nScore Total: {analysis.score}/100")
        print("\nMétricas:")
        print(f"  • Claridad:      {analysis.clarity}/100")
        print(f"  • Especificidad: {analysis.specificity}/100")
        print(f"  • Contexto:      {analysis.context}/100")
        print(f"  • Estructura:    {analysis.structure}/100")
        print(f"  • Concisión:     {analysis.conciseness}/100")

        if analysis.issues:
            print("\nProblemas detectados:")
            for issue in analysis.issues:
                print(f"  ⚠ {issue}")

        if analysis.suggestions:
            print("\nSugerencias:")
            for sug in analysis.suggestions:
                print(f"  → {sug}")

        print(f"\n{'=' * 50}")
        print("PROMPT OPTIMIZADO")
        print("=" * 50)
        print(analysis.optimized)
        print()


if __name__ == "__main__":
    main()
