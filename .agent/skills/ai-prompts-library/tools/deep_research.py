#!/usr/bin/env python3
"""
Deep Research Agent - Agente de Investigación Profunda
Basado en el sistema de deep research de OpenAI

Uso:
    python deep_research.py "¿Cuál es el estado actual de la IA en 2025?"
    python deep_research.py --topic "quantum computing" --depth comprehensive
    python deep_research.py --file questions.txt --output research_results.json
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class ResearchQuery:
    """Define una consulta de investigación."""

    topic: str
    depth: str  # quick, standard, comprehensive
    focus_areas: list[str]
    constraints: list[str]
    output_format: str


@dataclass
class ResearchResult:
    """Resultado de una investigación."""

    query: str
    summary: str
    key_findings: list[str]
    sources_analyzed: int
    methodology: str
    confidence_level: str
    follow_up_questions: list[str]
    timestamp: str
    raw_data: dict


# Plantilla de investigación basada en OpenAI Deep Research
RESEARCH_SYSTEM_PROMPT = """
You are a Deep Research Agent specialized in comprehensive investigation and analysis.

## Research Methodology

### Phase 1: Query Analysis
- Decompose the research question into sub-questions
- Identify key concepts and relationships
- Determine scope and boundaries
- Identify potential sources and verification methods

### Phase 2: Information Gathering
- Systematic search across multiple source types
- Cross-reference information for accuracy
- Track source reliability and potential biases
- Document methodology and search strategies

### Phase 3: Analysis & Synthesis
- Identify patterns and themes across sources
- Evaluate evidence quality and reliability
- Synthesize findings into coherent narrative
- Note contradictions, gaps, and uncertainties

### Phase 4: Output Generation
- Executive summary for quick understanding
- Detailed findings with supporting evidence
- Confidence levels for each conclusion
- Recommendations for further investigation

## Output Structure

Always structure your research output as:

1. **Executive Summary** (2-3 sentences)
2. **Key Findings** (bullet points)
3. **Detailed Analysis** (organized by theme)
4. **Methodology Notes** (how information was gathered)
5. **Confidence Assessment** (high/medium/low with justification)
6. **Follow-up Questions** (for deeper investigation)
7. **Sources & References**

## Research Principles

- Prioritize accuracy over speed
- Acknowledge uncertainty explicitly
- Distinguish facts from interpretations
- Consider multiple perspectives
- Update conclusions based on new evidence
- Maintain intellectual honesty
"""

DEPTH_CONFIGS = {
    "quick": {
        "description": "Respuesta rápida con puntos clave",
        "max_sources": 3,
        "analysis_depth": "surface",
        "time_estimate": "1-2 minutos",
        "output_length": "brief",
    },
    "standard": {
        "description": "Análisis balanceado con buena cobertura",
        "max_sources": 10,
        "analysis_depth": "moderate",
        "time_estimate": "5-10 minutos",
        "output_length": "standard",
    },
    "comprehensive": {
        "description": "Investigación exhaustiva y detallada",
        "max_sources": 25,
        "analysis_depth": "deep",
        "time_estimate": "15-30 minutos",
        "output_length": "extensive",
    },
}


def create_research_prompt(query: ResearchQuery) -> str:
    """Crea el prompt de investigación completo."""
    depth_config = DEPTH_CONFIGS.get(query.depth, DEPTH_CONFIGS["standard"])

    focus_section = ""
    if query.focus_areas:
        focus_section = "\n### Focus Areas:\n" + "\n".join(
            [f"- {area}" for area in query.focus_areas]
        )

    constraints_section = ""
    if query.constraints:
        constraints_section = "\n### Constraints:\n" + "\n".join(
            [f"- {c}" for c in query.constraints]
        )

    return f"""
{RESEARCH_SYSTEM_PROMPT}

## Current Research Task

**Topic:** {query.topic}

**Research Depth:** {query.depth}
- {depth_config["description"]}
- Maximum sources to analyze: {depth_config["max_sources"]}
- Analysis depth: {depth_config["analysis_depth"]}
- Expected output: {depth_config["output_length"]}
{focus_section}
{constraints_section}

**Output Format:** {query.output_format}

Begin your research now. Structure your response according to the output guidelines above.
"""


def parse_research_result(raw_output: str, query: str) -> ResearchResult:
    """Parsea la salida de investigación en estructura."""
    # Extraer secciones (simplificado - en producción sería más robusto)
    lines = raw_output.strip().split("\n")

    key_findings = []
    follow_up = []
    summary = ""

    current_section = None
    for line in lines:
        line_lower = line.lower().strip()

        if "executive summary" in line_lower or "resumen" in line_lower:
            current_section = "summary"
        elif "key findings" in line_lower or "hallazgos" in line_lower:
            current_section = "findings"
        elif "follow-up" in line_lower or "preguntas" in line_lower:
            current_section = "followup"
        elif line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            if current_section == "findings":
                key_findings.append(content)
            elif current_section == "followup":
                follow_up.append(content)
        elif current_section == "summary" and line.strip():
            summary += line.strip() + " "

    return ResearchResult(
        query=query,
        summary=summary.strip() or "Investigación completada",
        key_findings=key_findings or ["Ver análisis detallado"],
        sources_analyzed=0,
        methodology="AI-assisted deep research",
        confidence_level="medium",
        follow_up_questions=follow_up or ["¿Cómo profundizar más en este tema?"],
        timestamp=datetime.now().isoformat(),
        raw_data={"output": raw_output},
    )


def research_with_local_resources(query: ResearchQuery) -> ResearchResult:
    """Realiza investigación usando recursos locales del proyecto."""
    base_path = Path(__file__).parent.parent

    # Buscar en los prompts de IA por información relevante
    relevant_files = []
    search_terms = query.topic.lower().split()

    for prompt_file in base_path.rglob("*.md"):
        try:
            content = prompt_file.read_text(encoding="utf-8").lower()
            if any(term in content for term in search_terms):
                relevant_files.append(prompt_file)
        except Exception:
            pass

    # Generar resultado basado en archivos encontrados
    findings = []
    for f in relevant_files[:10]:
        rel_path = f.relative_to(base_path)
        findings.append(f"Información relevante encontrada en: {rel_path}")

    if not findings:
        findings = ["No se encontraron recursos locales relevantes para esta consulta"]

    return ResearchResult(
        query=query.topic,
        summary=f"Investigación sobre '{query.topic}' usando recursos locales del proyecto.",
        key_findings=findings,
        sources_analyzed=len(relevant_files),
        methodology="Local file analysis + AI prompt library search",
        confidence_level="medium" if relevant_files else "low",
        follow_up_questions=[
            "¿Buscar en fuentes externas?",
            "¿Profundizar en algún archivo específico?",
            "¿Comparar con otros proveedores de IA?",
        ],
        timestamp=datetime.now().isoformat(),
        raw_data={"files_found": [str(f) for f in relevant_files], "search_terms": search_terms},
    )


def generate_research_report(result: ResearchResult, format: str = "markdown") -> str:
    """Genera un reporte de investigación formateado."""
    if format == "json":
        return json.dumps(asdict(result), indent=2, ensure_ascii=False)

    # Formato Markdown
    report = f"""
# 🔬 Reporte de Investigación

**Consulta:** {result.query}
**Fecha:** {result.timestamp}
**Confianza:** {result.confidence_level}

---

## 📋 Resumen Ejecutivo

{result.summary}

## 🎯 Hallazgos Clave

"""
    for finding in result.key_findings:
        report += f"- {finding}\n"

    report += f"""
## 📊 Metodología

- **Método:** {result.methodology}
- **Fuentes analizadas:** {result.sources_analyzed}

## ❓ Preguntas de Seguimiento

"""
    for q in result.follow_up_questions:
        report += f"- {q}\n"

    report += """
---
*Generado por Deep Research Agent - Antigravity Ecosystem*
"""
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Deep Research Agent - Investigación profunda automatizada"
    )
    parser.add_argument("topic", nargs="?", help="Tema a investigar")
    parser.add_argument(
        "--depth",
        "-d",
        choices=["quick", "standard", "comprehensive"],
        default="standard",
        help="Profundidad de investigación",
    )
    parser.add_argument("--focus", "-f", nargs="+", help="Áreas de enfoque específicas")
    parser.add_argument("--output", "-o", help="Archivo de salida")
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown", help="Formato de salida"
    )
    parser.add_argument("--local", "-l", action="store_true", help="Usar solo recursos locales")
    parser.add_argument(
        "--show-prompt", action="store_true", help="Mostrar el prompt de investigación generado"
    )

    args = parser.parse_args()

    if not args.topic:
        parser.print_help()
        print('\n💡 Ejemplo: python deep_research.py "Estado de la IA en 2025"')
        return

    # Crear query de investigación
    query = ResearchQuery(
        topic=args.topic,
        depth=args.depth,
        focus_areas=args.focus or [],
        constraints=[],
        output_format=args.format,
    )

    if args.show_prompt:
        print("\n📝 PROMPT DE INVESTIGACIÓN GENERADO:")
        print("=" * 60)
        print(create_research_prompt(query))
        print("=" * 60)
        return

    print(f"\n🔬 Iniciando investigación: {args.topic}")
    print(f"   Profundidad: {args.depth}")
    print(f"   Modo: {'local' if args.local else 'completo'}")
    print()

    # Realizar investigación
    if args.local:
        result = research_with_local_resources(query)
    else:
        # En modo completo, primero buscar local, luego generar prompt para IA externa
        result = research_with_local_resources(query)
        print("💡 Para investigación externa, usa el prompt generado con --show-prompt")

    # Generar reporte
    report = generate_research_report(result, args.format)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ Reporte guardado en: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
