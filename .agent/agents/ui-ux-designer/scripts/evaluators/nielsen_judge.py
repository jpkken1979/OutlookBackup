"""Nielsen Judge — evalúa los 10 heurísticos de Nielsen en paralelo via LLM-as-Judge."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "heuristics.json"
_MODEL = "claude-sonnet-4-6"
_APPROVAL_THRESHOLD = 7.5


@dataclass
class HeuristicScore:
    """Score de un único heurístico de Nielsen.

    Args:
        heuristic_id: Identificador numérico (1-10).
        name: Nombre descriptivo del heurístico.
        score: Puntuación de 1 a 10.
        violations: Lista de problemas detectados.
        tailwind_fixes: Sugerencias de corrección con Tailwind/aria.
    """

    heuristic_id: int
    name: str
    score: float
    violations: list[str] = field(default_factory=list)
    tailwind_fixes: list[str] = field(default_factory=list)


@dataclass
class NielsenReport:
    """Reporte completo de evaluación Nielsen.

    Args:
        scores: Lista de scores individuales (10 heurísticos).
        global_score: Score ponderado global (0-10).
        approved: True si global_score >= 7.5.
    """

    scores: list[HeuristicScore]
    global_score: float
    approved: bool


def _build_prompt(
    heuristic: dict,
    code_context: str,
    screenshot_b64: Optional[str],
) -> list[dict]:
    """Construye el mensaje para evaluar un heurístico específico.

    Args:
        heuristic: Definición del heurístico con id, name, description y rubric.
        code_context: Código fuente a evaluar (truncado a 3000 chars).
        screenshot_b64: Screenshot en base64 o None.

    Returns:
        Lista de mensajes para la API de Anthropic.
    """
    rubric_text = "\n".join(
        f"  Score {k}: {v}" for k, v in heuristic.get("rubric", {}).items()
    )
    text_content = f"""Evaluá el siguiente código UI contra el heurístico de Nielsen:

**{heuristic['id']}. {heuristic['name']}**
{heuristic['description']}

Rubric de evaluación:
{rubric_text}

Código a evaluar:
```
{code_context[:3000]}
```

Respondé ÚNICAMENTE con JSON válido (sin texto adicional):
{{
  "score": <número 1-10>,
  "violations": ["lista de problemas concretos encontrados"],
  "tailwind_fixes": ["sugerencias con clases Tailwind/aria cuando aplique"]
}}"""

    content: list[dict] = []
    if screenshot_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64},
        })
    content.append({"type": "text", "text": text_content})
    return [{"role": "user", "content": content}]


async def _evaluate_single(
    heuristic: dict,
    code_context: str,
    screenshot_b64: Optional[str],
    weight: float,
    client: anthropic.AsyncAnthropic,
) -> tuple[HeuristicScore, float]:
    """Evalúa un único heurístico y retorna (HeuristicScore, weight).

    Args:
        heuristic: Definición del heurístico.
        code_context: Código fuente a evaluar.
        screenshot_b64: Screenshot en base64 o None.
        weight: Peso para el score ponderado global.
        client: Cliente Anthropic async.

    Returns:
        Tupla de (HeuristicScore, weight).
    """
    messages = _build_prompt(heuristic, code_context, screenshot_b64)
    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=512,
            messages=messages,
        )
        raw = response.content[0].text
        data = json.loads(raw)
        h_score = HeuristicScore(
            heuristic_id=heuristic["id"],
            name=heuristic["name"],
            score=float(data.get("score", 5)),
            violations=data.get("violations", []),
            tailwind_fixes=data.get("tailwind_fixes", []),
        )
    except Exception as exc:
        logger.warning("Error evaluando heurístico %s: %s", heuristic["id"], exc)
        h_score = HeuristicScore(
            heuristic_id=heuristic["id"],
            name=heuristic["name"],
            score=5.0,
        )
    return h_score, weight


async def run_nielsen_evaluation(
    code_context: str,
    screenshot_path: Optional[Path] = None,
    platform: str = "desktop_tauri",
    config_path: Path = _DEFAULT_CONFIG,
) -> NielsenReport:
    """Evalúa los 10 heurísticos Nielsen en paralelo via asyncio.gather.

    Args:
        code_context: Código fuente del componente/página a evaluar.
        screenshot_path: Screenshot opcional para análisis visual.
        platform: Plataforma para pesos ('desktop_tauri' o 'web').
        config_path: Ruta al heuristics.json.

    Returns:
        NielsenReport con scores individuales y global ponderado.
    """
    config = json.loads(config_path.read_text(encoding="utf-8"))
    heuristics = config["heuristics"]
    platform_weights = config.get("platform_weights", {}).get(platform, {})
    default_weight = platform_weights.get("default", 1.0)

    screenshot_b64: Optional[str] = None
    if screenshot_path and screenshot_path.exists():
        import base64
        screenshot_b64 = base64.standard_b64encode(
            screenshot_path.read_bytes()
        ).decode()

    client = anthropic.AsyncAnthropic()

    tasks = [
        _evaluate_single(
            h,
            code_context,
            screenshot_b64,
            platform_weights.get(h["key"], default_weight),
            client,
        )
        for h in heuristics
    ]
    results = await asyncio.gather(*tasks)

    scores = [r[0] for r in results]
    weights = [r[1] for r in results]

    total_weight = sum(weights)
    global_score = (
        sum(s.score * w for s, w in zip(scores, weights, strict=False)) / total_weight
        if total_weight
        else 0.0
    )

    return NielsenReport(
        scores=scores,
        global_score=round(global_score, 2),
        approved=global_score >= _APPROVAL_THRESHOLD,
    )
