#!/usr/bin/env python3
"""
Prompt Optimizer - Mejora automática de prompts según la IA destino
Ecosistema Antigravity v2.0

Usa los patrones extraídos de los system prompts de cada IA para
optimizar tus prompts y obtener mejores resultados.

Uso:
    python prompt_optimizer.py "tu prompt aquí" --target claude
    python prompt_optimizer.py "tu prompt" --target gpt --task code
    python prompt_optimizer.py --interactive
    python prompt_optimizer.py --file mi_prompt.txt --target gemini
"""

import argparse
import json
import re
from dataclasses import dataclass, asdict


@dataclass
class OptimizedPrompt:
    """Resultado de la optimización."""

    original: str
    optimized: str
    target_ai: str
    task_type: str
    enhancements: list[str]
    tips: list[str]
    confidence: str


# Patrones de optimización por IA (extraídos de los system prompts)
AI_PATTERNS = {
    "claude": {
        "name": "Claude (Anthropic)",
        "models": ["claude-3", "claude-4", "opus", "sonnet", "haiku"],
        "style": {
            "format": "xml_tags",  # Claude responde bien a XML tags
            "thinking": True,  # Beneficia de "think step by step"
            "concise": True,  # Prefiere respuestas concisas
            "structured": True,  # Responde bien a estructura clara
        },
        "best_practices": [
            "Usar XML tags para estructurar (<context>, <task>, <constraints>)",
            "Pedir 'think step by step' para tareas complejas",
            "Ser específico sobre el formato de salida esperado",
            "Incluir ejemplos cuando sea posible",
            "Especificar restricciones claramente",
        ],
        "template": """<context>
{context}
</context>

<task>
{task}
</task>

<constraints>
{constraints}
</constraints>

<output_format>
{output_format}
</output_format>""",
        "prefixes": {
            "code": "Write clean, well-documented code that:",
            "analysis": "Analyze the following carefully, considering multiple perspectives:",
            "creative": "Create original content that:",
            "explanation": "Explain clearly and concisely:",
        },
    },
    "gpt": {
        "name": "GPT (OpenAI)",
        "models": ["gpt-4", "gpt-4o", "gpt-5", "o3", "o4"],
        "style": {
            "format": "markdown",
            "thinking": True,  # Thinking mode en GPT-5
            "personality": True,  # Responde bien a personalidades
            "step_by_step": True,
        },
        "best_practices": [
            "Usar Markdown para estructura (# headers, - bullets)",
            "Definir el rol/personalidad del asistente",
            "Pedir razonamiento paso a paso para precisión",
            "Ser explícito sobre el nivel de detalle deseado",
            "Incluir ejemplos de entrada/salida",
        ],
        "template": """# Role
{role}

# Task
{task}

# Context
{context}

# Requirements
{requirements}

# Output Format
{output_format}""",
        "prefixes": {
            "code": "You are an expert programmer. Write production-ready code that:",
            "analysis": "Analyze thoroughly, showing your reasoning step by step:",
            "creative": "Be creative and original while:",
            "explanation": "Explain in detail, using examples where helpful:",
        },
    },
    "gemini": {
        "name": "Gemini (Google)",
        "models": ["gemini-2", "gemini-3", "gemini-pro", "gemini-flash"],
        "style": {
            "format": "clear_sections",
            "examples": True,  # Responde muy bien a ejemplos
            "multimodal": True,  # Capacidad multimodal
            "grounded": True,  # Prefiere info verificable
        },
        "best_practices": [
            "Proporcionar ejemplos claros de entrada/salida",
            "Estructurar en secciones con títulos claros",
            "Ser específico sobre fuentes si se requiere verificación",
            "Aprovechar capacidades multimodales si hay imágenes",
            "Pedir citaciones para información factual",
        ],
        "template": """## Objective
{objective}

## Context
{context}

## Instructions
{instructions}

## Examples
{examples}

## Expected Output
{output_format}""",
        "prefixes": {
            "code": "Generate well-structured code following best practices:",
            "analysis": "Provide a thorough analysis with supporting evidence:",
            "creative": "Generate creative content that is:",
            "explanation": "Explain clearly with relevant examples:",
        },
    },
    "grok": {
        "name": "Grok (xAI)",
        "models": ["grok-3", "grok-4"],
        "style": {
            "format": "direct",
            "unfiltered": True,  # Más directo
            "humor": True,  # Puede usar humor
            "current": True,  # Tiene info actualizada
        },
        "best_practices": [
            "Ser directo, sin rodeos innecesarios",
            "Pedir opiniones honestas si se desean",
            "Aprovechar conocimiento actualizado (real-time)",
            "No preocuparse por ser demasiado formal",
            "Pedir perspectivas no convencionales si se desean",
        ],
        "template": """Task: {task}

Context: {context}

What I need: {requirements}

Format: {output_format}""",
        "prefixes": {
            "code": "Write efficient, no-nonsense code:",
            "analysis": "Give me a straight analysis, no hedging:",
            "creative": "Be creative and don't hold back:",
            "explanation": "Explain directly, skip the fluff:",
        },
    },
    "local": {
        "name": "Local/Open Source (Llama, Mistral, etc.)",
        "models": ["llama", "mistral", "mixtral", "phi", "qwen"],
        "style": {
            "format": "simple",
            "explicit": True,  # Necesita instrucciones más explícitas
            "examples": True,  # Muy dependiente de ejemplos
            "constraints": True,  # Necesita límites claros
        },
        "best_practices": [
            "Ser muy explícito y detallado en instrucciones",
            "Proporcionar múltiples ejemplos",
            "Definir límites claros de respuesta",
            "Usar formato simple y consistente",
            "Evitar instrucciones ambiguas",
        ],
        "template": """### Instruction
{instruction}

### Input
{input}

### Context
{context}

### Output Format
{output_format}

### Response""",
        "prefixes": {
            "code": "Write code following these exact requirements:",
            "analysis": "Analyze the following, listing each point:",
            "creative": "Create content matching these criteria:",
            "explanation": "Explain step by step:",
        },
    },
}

# Tipos de tareas y cómo optimizarlas
TASK_PATTERNS = {
    "code": {
        "keywords": [
            "code",
            "function",
            "class",
            "api",
            "script",
            "program",
            "implement",
            "código",
            "función",
        ],
        "enhancements": [
            "Especificar lenguaje de programación",
            "Mencionar manejo de errores",
            "Pedir comentarios/documentación",
            "Especificar estilo de código",
        ],
        "additions": [
            "Include error handling",
            "Add inline comments for complex logic",
            "Follow best practices for {language}",
        ],
    },
    "analysis": {
        "keywords": [
            "analyze",
            "review",
            "evaluate",
            "assess",
            "compare",
            "analizar",
            "evaluar",
            "comparar",
        ],
        "enhancements": [
            "Pedir estructura de análisis",
            "Solicitar pros y contras",
            "Pedir conclusiones accionables",
        ],
        "additions": [
            "Consider multiple perspectives",
            "Provide actionable conclusions",
            "Support claims with reasoning",
        ],
    },
    "creative": {
        "keywords": [
            "write",
            "create",
            "generate",
            "design",
            "story",
            "escribir",
            "crear",
            "diseñar",
        ],
        "enhancements": [
            "Definir tono y estilo",
            "Especificar audiencia",
            "Dar ejemplos de referencia",
        ],
        "additions": [
            "Match the tone to the target audience",
            "Be original and avoid clichés",
        ],
    },
    "explanation": {
        "keywords": [
            "explain",
            "describe",
            "what is",
            "how does",
            "why",
            "explicar",
            "qué es",
            "cómo",
        ],
        "enhancements": [
            "Especificar nivel de detalle",
            "Pedir ejemplos",
            "Definir audiencia (técnica/general)",
        ],
        "additions": [
            "Use examples to illustrate",
            "Adjust complexity for the audience",
        ],
    },
}


def detect_task_type(prompt: str) -> str:
    """Detecta el tipo de tarea basado en palabras clave."""
    prompt_lower = prompt.lower()

    for task_type, config in TASK_PATTERNS.items():
        for keyword in config["keywords"]:
            if keyword in prompt_lower:
                return task_type

    return "general"


def detect_language(prompt: str) -> str | None:
    """Detecta el lenguaje de programación mencionado."""
    languages = {
        "python": ["python", "py", "django", "flask", "fastapi"],
        "javascript": ["javascript", "js", "node", "react", "vue", "next"],
        "typescript": ["typescript", "ts", "angular"],
        "java": ["java", "spring", "kotlin"],
        "csharp": ["c#", "csharp", ".net", "unity"],
        "go": ["golang", "go "],
        "rust": ["rust"],
        "sql": ["sql", "query", "database"],
    }

    prompt_lower = prompt.lower()
    for lang, keywords in languages.items():
        for kw in keywords:
            if kw in prompt_lower:
                return lang
    return None


def extract_context(prompt: str) -> dict:
    """Extrae contexto del prompt original."""
    return {
        "has_code": bool(re.search(r"```|`[^`]+`", prompt)),
        "has_question": "?" in prompt,
        "word_count": len(prompt.split()),
        "is_spanish": bool(re.search(r"\b(que|como|para|por|una|con)\b", prompt.lower())),
        "detected_language": detect_language(prompt),
    }


def optimize_prompt(
    prompt: str,
    target_ai: str = "claude",
    task_type: str | None = None,
    add_examples: bool = False,
    verbose: bool = False,
) -> OptimizedPrompt:
    """Optimiza un prompt para una IA específica."""

    # Normalizar target
    target = target_ai.lower()
    if target not in AI_PATTERNS:
        # Intentar match parcial
        for key in AI_PATTERNS:
            if key in target or target in key:
                target = key
                break
        else:
            target = "claude"  # Default

    ai_config = AI_PATTERNS[target]

    # Detectar tipo de tarea si no se especifica
    if not task_type:
        task_type = detect_task_type(prompt)

    # Extraer contexto
    context = extract_context(prompt)

    # Construir prompt optimizado
    enhancements = []
    tips = []

    # 1. Añadir prefijo según tipo de tarea
    prefix = ai_config["prefixes"].get(task_type, "")

    # 2. Estructurar según el formato preferido de la IA
    if ai_config["style"]["format"] == "xml_tags":
        optimized = f"""<task>
{prefix}
{prompt}
</task>

<requirements>
- Provide clear, actionable output
- Be specific and precise
</requirements>"""
        enhancements.append("Añadida estructura XML (preferida por Claude)")

    elif ai_config["style"]["format"] == "markdown":
        optimized = f"""# Task
{prefix}

{prompt}

## Requirements
- Provide clear, actionable output
- Show reasoning when helpful"""
        enhancements.append("Añadida estructura Markdown (preferida por GPT)")

    elif ai_config["style"]["format"] == "direct":
        optimized = f"""{prefix}

{prompt}

Be direct and give me a real answer."""
        enhancements.append("Formato directo (estilo Grok)")

    else:
        optimized = f"""{prefix}

{prompt}"""

    # 3. Añadir thinking mode si aplica
    if ai_config["style"].get("thinking") and task_type in ["code", "analysis"]:
        if target == "claude":
            optimized += "\n\nThink through this step by step before responding."
        else:
            optimized += "\n\nReason through this carefully, step by step."
        enhancements.append("Añadido 'step by step' para mejor razonamiento")

    # 4. Añadir formato de salida si es código
    if task_type == "code":
        lang = context.get("detected_language", "")
        if lang:
            optimized += f"\n\nProvide the code in {lang} with proper formatting."
            enhancements.append(f"Especificado lenguaje: {lang}")

    # 5. Añadir ejemplos si se pide
    if add_examples and ai_config["style"].get("examples"):
        optimized += """

Example format:
Input: [example input]
Output: [example output]"""
        enhancements.append("Añadida sección de ejemplos")

    # Generar tips
    tips = ai_config["best_practices"][:3]  # Top 3 tips

    # Determinar confianza
    if len(enhancements) >= 3:
        confidence = "high"
    elif len(enhancements) >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return OptimizedPrompt(
        original=prompt,
        optimized=optimized.strip(),
        target_ai=ai_config["name"],
        task_type=task_type,
        enhancements=enhancements,
        tips=tips,
        confidence=confidence,
    )


def compare_optimizations(prompt: str) -> dict:
    """Compara el prompt optimizado para diferentes IAs."""
    results = {}
    for ai in ["claude", "gpt", "gemini", "grok"]:
        result = optimize_prompt(prompt, target_ai=ai)
        results[ai] = {
            "optimized": result.optimized,
            "enhancements": result.enhancements,
        }
    return results


def interactive_mode():
    """Modo interactivo para optimizar prompts."""
    print("\n" + "=" * 60)
    print("🚀 PROMPT OPTIMIZER - Modo Interactivo")
    print("=" * 60)
    print("\nEscribe 'exit' para salir\n")

    while True:
        print("\n" + "-" * 40)
        prompt = input("📝 Tu prompt: ").strip()

        if prompt.lower() in ["exit", "quit", "salir"]:
            print("👋 ¡Hasta luego!")
            break

        if not prompt:
            continue

        target = input("🎯 IA destino (claude/gpt/gemini/grok) [claude]: ").strip() or "claude"

        result = optimize_prompt(prompt, target_ai=target)

        print("\n" + "=" * 60)
        print(f"✨ PROMPT OPTIMIZADO para {result.target_ai}")
        print("=" * 60)
        print(f"\n{result.optimized}")
        print("\n" + "-" * 40)
        print(f"📊 Tipo de tarea: {result.task_type}")
        print(f"🎯 Confianza: {result.confidence}")
        print("\n🔧 Mejoras aplicadas:")
        for e in result.enhancements:
            print(f"   • {e}")
        print("\n💡 Tips adicionales:")
        for t in result.tips:
            print(f"   • {t}")


def main():
    parser = argparse.ArgumentParser(
        description="Prompt Optimizer - Mejora prompts según la IA destino",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python prompt_optimizer.py "Crea una función que ordene una lista" --target claude
  python prompt_optimizer.py "Explica qué es machine learning" --target gpt --task explanation
  python prompt_optimizer.py --compare "Analiza este código"
  python prompt_optimizer.py --interactive
        """,
    )

    parser.add_argument("prompt", nargs="?", help="El prompt a optimizar")
    parser.add_argument(
        "--target",
        "-t",
        default="claude",
        choices=["claude", "gpt", "gemini", "grok", "local"],
        help="IA destino",
    )
    parser.add_argument(
        "--task",
        choices=["code", "analysis", "creative", "explanation"],
        help="Tipo de tarea (auto-detectado si no se especifica)",
    )
    parser.add_argument("--examples", "-e", action="store_true", help="Incluir sección de ejemplos")
    parser.add_argument(
        "--compare", "-c", action="store_true", help="Comparar optimización para todas las IAs"
    )
    parser.add_argument("--file", "-f", help="Leer prompt desde archivo")
    parser.add_argument("--output", "-o", help="Guardar resultado en archivo")
    parser.add_argument("--json", "-j", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo interactivo")
    parser.add_argument("--list-ais", "-l", action="store_true", help="Listar IAs soportadas")

    args = parser.parse_args()

    if args.list_ais:
        print("\n🤖 IAs Soportadas:\n")
        for key, config in AI_PATTERNS.items():
            print(f"  [{key}] {config['name']}")
            print(f"      Modelos: {', '.join(config['models'])}")
            print(f"      Formato: {config['style']['format']}")
            print()
        return

    if args.interactive:
        interactive_mode()
        return

    # Obtener prompt
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            prompt = f.read().strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        return

    # Comparar todas las IAs
    if args.compare:
        results = compare_optimizations(prompt)
        print("\n" + "=" * 60)
        print("📊 COMPARACIÓN DE OPTIMIZACIONES")
        print("=" * 60)
        for ai, data in results.items():
            print(f"\n### {ai.upper()} ###")
            print(
                data["optimized"][:300] + "..."
                if len(data["optimized"]) > 300
                else data["optimized"]
            )
        return

    # Optimizar
    result = optimize_prompt(
        prompt, target_ai=args.target, task_type=args.task, add_examples=args.examples
    )

    if args.json:
        output = json.dumps(asdict(result), indent=2, ensure_ascii=False)
    else:
        output = f"""
{"=" * 60}
✨ PROMPT OPTIMIZADO para {result.target_ai}
{"=" * 60}

{result.optimized}

{"-" * 60}
📊 Tipo de tarea: {result.task_type}
🎯 Confianza: {result.confidence}

🔧 Mejoras aplicadas:
{chr(10).join(f"   • {e}" for e in result.enhancements)}

💡 Tips para {result.target_ai}:
{chr(10).join(f"   • {t}" for t in result.tips)}
"""

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ Guardado en: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
