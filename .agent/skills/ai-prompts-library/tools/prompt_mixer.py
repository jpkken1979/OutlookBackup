#!/usr/bin/env python3
"""
Prompt Mixer - Combina y mezcla prompts de diferentes IAs
Crea prompts híbridos con lo mejor de cada proveedor

Uso:
    python prompt_mixer.py --list-templates
    python prompt_mixer.py --analyze anthropic/claude-code.md
    python prompt_mixer.py --mix anthropic/claude-code.md openai/codex-cli.md --output hybrid.md
    python prompt_mixer.py --extract-patterns openai/
"""

import json
import re
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict

BASE_PATH = Path(__file__).parent.parent


@dataclass
class PromptSection:
    """Una sección extraída de un prompt."""

    name: str
    content: str
    section_type: str  # identity, rules, tools, examples, constraints
    source_file: str
    priority: int = 5


@dataclass
class PromptPattern:
    """Un patrón detectado en prompts."""

    pattern_type: str
    description: str
    examples: list[str]
    frequency: int
    providers: list[str]


# Patrones comunes detectados en prompts de IA
SECTION_PATTERNS = {
    "identity": [
        r"^you are\s",
        r"^i am\s",
        r"^as an? \w+ ai",
        r"^your (role|purpose|name)",
    ],
    "rules": [
        r"^(rules?|guidelines?|principles?)\s*:",
        r"^you (must|should|will|cannot|must not)",
        r"^(always|never)\s",
        r"^(important|critical|note)\s*:",
    ],
    "tools": [
        r"^(tools?|functions?|capabilities)\s*:",
        r"^you (have access to|can use)",
        r"^available (tools|functions)",
        r"^## tools",
    ],
    "examples": [
        r"^(examples?|e\.g\.|for (example|instance))",
        r"^<example",
        r"^```",
    ],
    "constraints": [
        r"^(constraints?|limitations?|restrictions?)",
        r"^(do not|don't|avoid|refrain)",
        r"^you (cannot|are not able)",
    ],
    "format": [
        r"^(format|output|response)\s*:",
        r"^(when|how to) respond",
        r"^structure your",
    ],
}


def detect_section_type(text: str) -> str:
    """Detecta el tipo de sección basado en patrones."""
    text_lower = text.lower().strip()

    for section_type, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, text_lower):
                return section_type

    return "general"


def extract_sections(content: str, source_file: str) -> list[PromptSection]:
    """Extrae secciones de un prompt."""
    sections = []
    current_section = []
    current_type = "general"

    lines = content.split("\n")

    for line in lines:
        # Detectar inicio de nueva sección (headers markdown o patrones)
        if line.startswith("#") or detect_section_type(line) != "general":
            # Guardar sección anterior si existe
            if current_section:
                sections.append(
                    PromptSection(
                        name=current_section[0][:50].strip("#").strip(),
                        content="\n".join(current_section),
                        section_type=current_type,
                        source_file=source_file,
                    )
                )
            current_section = [line]
            current_type = detect_section_type(line)
        else:
            current_section.append(line)

    # Añadir última sección
    if current_section:
        sections.append(
            PromptSection(
                name=current_section[0][:50].strip("#").strip(),
                content="\n".join(current_section),
                section_type=current_type,
                source_file=source_file,
            )
        )

    return sections


def analyze_prompt(file_path: str) -> dict:
    """Analiza un prompt y extrae sus componentes."""
    path = BASE_PATH / file_path if not Path(file_path).is_absolute() else Path(file_path)

    if not path.exists():
        return {"error": f"Archivo no encontrado: {file_path}"}

    content = path.read_text(encoding="utf-8")
    sections = extract_sections(content, str(path.name))

    # Estadísticas
    section_counts = defaultdict(int)
    for s in sections:
        section_counts[s.section_type] += 1

    # Detectar características
    features = {
        "has_tools": any(s.section_type == "tools" for s in sections),
        "has_examples": any(s.section_type == "examples" for s in sections),
        "has_constraints": any(s.section_type == "constraints" for s in sections),
        "has_identity": any(s.section_type == "identity" for s in sections),
        "word_count": len(content.split()),
        "line_count": len(content.split("\n")),
        "section_count": len(sections),
    }

    return {
        "file": file_path,
        "features": features,
        "section_breakdown": dict(section_counts),
        "sections": [asdict(s) for s in sections],
    }


def mix_prompts(file_paths: list[str], strategy: str = "balanced") -> str:
    """Mezcla múltiples prompts en uno híbrido."""
    all_sections = []

    for file_path in file_paths:
        path = BASE_PATH / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            sections = extract_sections(content, str(path.name))
            all_sections.extend(sections)

    # Agrupar por tipo
    by_type = defaultdict(list)
    for s in all_sections:
        by_type[s.section_type].append(s)

    # Construir prompt híbrido según estrategia
    hybrid_parts = []

    # Header
    sources = list({s.source_file for s in all_sections})
    hybrid_parts.append(f"""# Hybrid AI System Prompt

> Generated by Prompt Mixer
> Sources: {", ".join(sources)}
> Strategy: {strategy}

---
""")

    # Orden de secciones
    section_order = ["identity", "rules", "tools", "format", "examples", "constraints", "general"]

    for section_type in section_order:
        if section_type in by_type:
            sections = by_type[section_type]

            if strategy == "balanced":
                # Tomar una sección de cada fuente
                seen_sources = set()
                for s in sections:
                    if s.source_file not in seen_sources:
                        hybrid_parts.append(f"\n## {section_type.title()} (from {s.source_file})\n")
                        hybrid_parts.append(s.content)
                        seen_sources.add(s.source_file)

            elif strategy == "merge":
                # Combinar todas las secciones del mismo tipo
                hybrid_parts.append(f"\n## {section_type.title()}\n")
                for s in sections:
                    hybrid_parts.append(f"\n### From {s.source_file}:\n")
                    hybrid_parts.append(s.content)

            elif strategy == "first":
                # Tomar solo la primera sección de cada tipo
                hybrid_parts.append(f"\n## {section_type.title()}\n")
                hybrid_parts.append(sections[0].content)

    return "\n".join(hybrid_parts)


def extract_patterns(directory: str) -> list[PromptPattern]:
    """Extrae patrones comunes de un directorio de prompts."""
    path = BASE_PATH / directory if not Path(directory).is_absolute() else Path(directory)
    patterns_found = defaultdict(lambda: {"count": 0, "examples": [], "providers": set()})

    for prompt_file in path.rglob("*.md"):
        try:
            content = prompt_file.read_text(encoding="utf-8").lower()
            provider = prompt_file.parent.name

            # Buscar patrones comunes
            common_patterns = [
                ("chain_of_thought", r"(think step by step|let'?s think|reason through)"),
                ("role_play", r"(you are|act as|behave as|pretend to be)"),
                ("tool_use", r"(you have access to|available tools|can use the following)"),
                ("output_format", r"(format your (response|output)|respond (in|with|using))"),
                ("safety", r"(do not|never|avoid|refuse to|cannot)"),
                ("memory", r"(remember|recall|previous|context|history)"),
                ("reasoning", r"(explain your|show your|reasoning|thinking)"),
                ("examples", r"(<example|for example|e\.g\.|such as)"),
                ("xml_tags", r"<[a-z_]+>"),
                ("markdown", r"(```|##|###|\*\*|\*)"),
            ]

            for pattern_name, regex in common_patterns:
                matches = re.findall(regex, content)
                if matches:
                    patterns_found[pattern_name]["count"] += len(matches)
                    patterns_found[pattern_name]["examples"].extend(matches[:2])
                    patterns_found[pattern_name]["providers"].add(provider)

        except Exception:
            pass

    # Convertir a lista de PatternPrompt
    result = []
    for name, data in patterns_found.items():
        result.append(
            PromptPattern(
                pattern_type=name,
                description=f"Pattern: {name.replace('_', ' ').title()}",
                examples=list(set(data["examples"]))[:5],
                frequency=data["count"],
                providers=list(data["providers"]),
            )
        )

    return sorted(result, key=lambda x: x.frequency, reverse=True)


def list_templates() -> None:
    """Lista templates predefinidos para crear prompts."""
    templates = {
        "coding_assistant": {
            "sections": ["identity", "tools", "rules", "examples"],
            "personality": "professional",
            "sources": ["anthropic/claude-code.md", "openai/codex-cli.md"],
        },
        "research_agent": {
            "sections": ["identity", "tools", "format", "constraints"],
            "personality": "nerdy",
            "sources": ["openai/tool-deep-research.md"],
        },
        "creative_writer": {
            "sections": ["identity", "rules", "examples"],
            "personality": "quirky",
            "sources": ["misc/Notion AI.md"],
        },
        "customer_support": {
            "sections": ["identity", "rules", "format", "constraints"],
            "personality": "friendly",
            "sources": ["perplexity/voice-assistant.md"],
        },
        "code_reviewer": {
            "sections": ["identity", "rules", "examples", "format"],
            "personality": "cynical",
            "sources": ["anthropic/claude-code.md"],
        },
    }

    print("\n" + "=" * 60)
    print("📋 TEMPLATES DE PROMPTS DISPONIBLES")
    print("=" * 60 + "\n")

    for name, config in templates.items():
        print(f"  [{name}]")
        print(f"    Personalidad: {config['personality']}")
        print(f"    Secciones: {', '.join(config['sections'])}")
        print(f"    Fuentes: {', '.join(config['sources'])}")
        print()


def create_from_template(template_name: str, customizations: dict = None) -> str:
    """Crea un prompt desde un template."""
    templates = {
        "coding_assistant": """
# Coding Assistant

You are an expert coding assistant specialized in helping developers write, debug, and improve code.

## Core Capabilities
- Write clean, efficient code in multiple languages
- Debug and fix issues
- Explain complex concepts clearly
- Suggest best practices and optimizations

## Response Format
1. Understand the request
2. Provide working code
3. Explain key decisions
4. Suggest improvements if applicable

## Rules
- Always include comments for complex logic
- Follow language-specific conventions
- Consider edge cases
- Prioritize readability over cleverness

## Example Interaction
User: "Write a Python function to check if a number is prime"

Response:
```python
def is_prime(n: int) -> bool:
    \"\"\"Check if a number is prime.\"\"\"
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
```
""",
        "research_agent": """
# Research Agent

You are a thorough research agent specialized in gathering, analyzing, and synthesizing information.

## Methodology
1. Understand the research question
2. Break into sub-questions
3. Gather relevant information
4. Analyze and synthesize
5. Present findings clearly

## Output Format
- Executive Summary
- Key Findings
- Detailed Analysis
- Sources & Confidence Level
- Follow-up Questions

## Principles
- Accuracy over speed
- Cite sources
- Acknowledge uncertainty
- Present multiple perspectives
""",
    }

    template = templates.get(template_name, templates["coding_assistant"])

    if customizations:
        for key, value in customizations.items():
            template = template.replace(f"{{{key}}}", value)

    return template


def main():
    parser = argparse.ArgumentParser(description="Prompt Mixer - Combina y analiza prompts de IA")

    parser.add_argument("--analyze", "-a", metavar="FILE", help="Analizar un prompt")
    parser.add_argument("--mix", "-m", nargs="+", metavar="FILE", help="Mezclar múltiples prompts")
    parser.add_argument(
        "--strategy",
        "-s",
        choices=["balanced", "merge", "first"],
        default="balanced",
        help="Estrategia de mezcla",
    )
    parser.add_argument("--output", "-o", help="Archivo de salida")
    parser.add_argument(
        "--extract-patterns", "-e", metavar="DIR", help="Extraer patrones de un directorio"
    )
    parser.add_argument(
        "--list-templates", "-l", action="store_true", help="Listar templates disponibles"
    )
    parser.add_argument("--create", "-c", metavar="TEMPLATE", help="Crear prompt desde template")
    parser.add_argument("--compare", nargs=2, metavar="FILE", help="Comparar dos prompts")

    args = parser.parse_args()

    if args.list_templates:
        list_templates()
        return

    if args.analyze:
        analysis = analyze_prompt(args.analyze)
        print("\n" + "=" * 60)
        print(f"📊 ANÁLISIS DE PROMPT: {args.analyze}")
        print("=" * 60)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return

    if args.mix:
        result = mix_prompts(args.mix, args.strategy)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"✅ Prompt híbrido guardado en: {args.output}")
        else:
            print(result)
        return

    if args.extract_patterns:
        patterns = extract_patterns(args.extract_patterns)
        print("\n" + "=" * 60)
        print(f"🔍 PATRONES EN: {args.extract_patterns}")
        print("=" * 60 + "\n")
        for p in patterns:
            print(f"  [{p.pattern_type}] - {p.frequency} ocurrencias")
            print(f"    Proveedores: {', '.join(p.providers)}")
            if p.examples:
                print(f"    Ejemplos: {p.examples[:2]}")
            print()
        return

    if args.create:
        result = create_from_template(args.create)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"✅ Prompt creado en: {args.output}")
        else:
            print(result)
        return

    if args.compare:
        a1 = analyze_prompt(args.compare[0])
        a2 = analyze_prompt(args.compare[1])
        print("\n" + "=" * 60)
        print("📊 COMPARACIÓN DE PROMPTS")
        print("=" * 60)
        print(f"\nArchivo 1: {args.compare[0]}")
        print(f"  Palabras: {a1.get('features', {}).get('word_count', 0)}")
        print(f"  Secciones: {a1.get('features', {}).get('section_count', 0)}")
        print(f"\nArchivo 2: {args.compare[1]}")
        print(f"  Palabras: {a2.get('features', {}).get('word_count', 0)}")
        print(f"  Secciones: {a2.get('features', {}).get('section_count', 0)}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
