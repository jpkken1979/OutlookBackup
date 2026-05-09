"""Component generator — genera JSX/TSX con feedback loop interno Nielsen."""
import logging
import re
from dataclasses import dataclass
from typing import Optional

import anthropic

from evaluators.nielsen_judge import NielsenReport, run_nielsen_evaluation

logger = logging.getLogger(__name__)

_MODEL = "claude-opus-4-7"
_SCORE_THRESHOLD = 7.5
_MAX_ITERATIONS = 3

_SYSTEM_PROMPT = """Sos un experto en React/TypeScript y design systems.
Generás componentes que siguen estas reglas sin excepción:
- TypeScript strict: cero `any`, interfaces explícitas para todas las props
- Tailwind v4: usar CSS variables via @theme, no valores hardcodeados
- WCAG 2.2 AA: aria-label en elementos interactivos, contraste ≥ 4.5:1
- shadcn/ui como base cuando aplique
- Framer Motion variants SIEMPRE en archivo separado (*Variants.ts)
- Componentes de ≤ 100 líneas. Si es más complejo, dividir.
Respondé SOLO con el código TSX, sin explicaciones ni markdown."""


@dataclass
class GeneratedComponent:
    """Resultado de la generación de un componente.

    Args:
        tsx_content: Código TSX generado y aprobado.
        variants_content: Variantes Framer Motion extraídas (si existen).
        nielsen_score: Score global Nielsen del componente aprobado.
        iterations: Cantidad de iteraciones realizadas hasta aprobación.
    """

    tsx_content: str
    variants_content: Optional[str]
    nielsen_score: float
    iterations: int


async def generate_component(
    description: str,
    tokens: dict,
    violations: list,
    max_iterations: int = _MAX_ITERATIONS,
    score_threshold: float = _SCORE_THRESHOLD,  # noqa: ARG001
) -> GeneratedComponent:
    """Genera un componente React/TSX con feedback loop interno Nielsen.

    Args:
        description: Descripción del componente a generar.
        tokens: Design tokens activos del proyecto (W3C DTCG).
        violations: Violaciones detectadas en análisis previo.
        max_iterations: Máximo de reintentos si el score Nielsen es bajo.
        score_threshold: Score mínimo para aprobar el componente.

    Returns:
        GeneratedComponent con el TSX aprobado y su score final.
    """
    client = anthropic.AsyncAnthropic()

    token_summary = _summarize_tokens(tokens)
    violation_summary = "\n".join(f"- {v}" for v in violations[:10]) if violations else "Ninguna"

    tsx_content = ""
    nielsen_score = 0.0
    iteration = 0

    prev_feedback = ""
    while iteration < max_iterations:
        iteration += 1
        prompt = _build_gen_prompt(description, token_summary, violation_summary, prev_feedback)

        try:
            response = await client.messages.create(
                model=_MODEL,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            tsx_content = response.content[0].text.strip()
        except Exception as exc:
            logger.warning("Error generando componente (iter %d): %s", iteration, exc)
            break

        report: NielsenReport = await run_nielsen_evaluation(code_context=tsx_content)
        nielsen_score = report.global_score

        if report.approved:
            break

        issues = [f"{s.name}: {', '.join(s.violations[:2])}" for s in report.scores if s.violations]
        prev_feedback = (
            "Problemas encontrados en la versión anterior:\n"
            + "\n".join(f"- {i}" for i in issues[:5])
        )
        logger.info("Componente iter %d score=%.1f, reintentando...", iteration, nielsen_score)

    return GeneratedComponent(
        tsx_content=tsx_content,
        variants_content=_extract_variants(tsx_content),
        nielsen_score=nielsen_score,
        iterations=iteration,
    )


def _summarize_tokens(tokens: dict) -> str:
    """Resume los tokens más relevantes para incluir en el prompt.

    Args:
        tokens: Design tokens en formato DTCG anidado.

    Returns:
        String con las variables CSS más relevantes.
    """
    lines: list[str] = []
    for category, group in tokens.items():
        if isinstance(group, dict):
            for name, token in list(group.items())[:5]:
                if isinstance(token, dict) and "$value" in token:
                    lines.append(f"--{category}-{name}: {token['$value']}")
    return "\n".join(lines[:20]) or "Sin tokens definidos"


def _build_gen_prompt(
    description: str,
    token_summary: str,
    violation_summary: str,
    prev_feedback: str,
) -> str:
    """Construye el prompt de generación.

    Args:
        description: Descripción del componente.
        token_summary: Tokens activos resumidos.
        violation_summary: Violaciones a resolver.
        prev_feedback: Feedback de la iteración anterior (vacío en iter 1).

    Returns:
        Prompt completo para el LLM.
    """
    feedback_section = f"\n\n{prev_feedback}" if prev_feedback else ""
    return f"""Generá el componente: {description}

Design tokens activos del proyecto:
{token_summary}

Violaciones de accesibilidad a resolver:
{violation_summary}{feedback_section}

Recordá: solo el código TSX, sin markdown, sin explicaciones."""


def _extract_variants(tsx: str) -> Optional[str]:
    """Extrae variantes de Framer Motion si están inline.

    Args:
        tsx: Código TSX a analizar.

    Returns:
        Código de variantes si se detectan, None en caso contrario.
    """
    variants_match = re.search(
        r"const\s+\w+Variants\s*=\s*\{[\s\S]*?\};", tsx
    )
    return variants_match.group(0) if variants_match else None
