"""Visual analyzer — análisis de screenshots via Claude vision (multi-VLM)."""
import base64
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from PIL import Image

logger = logging.getLogger(__name__)

_ANALYSIS_PROMPT = """Analizá esta captura de pantalla de una interfaz de usuario.
Evaluá las siguientes áreas de diseño y respondé ÚNICAMENTE con un array JSON válido.
No agregues texto fuera del JSON.

Áreas a evaluar:
- hierarchy: jerarquía visual (tamaño, peso, contraste entre elementos)
- whitespace: uso del espacio en blanco y respiración visual
- affordances: claridad de elementos interactivos (botones, links, inputs)
- consistency: consistencia visual entre componentes similares
- readability: legibilidad del texto (tamaño, contraste, longitud de línea)

Formato de respuesta (array JSON):
[
  {
    "area": "hierarchy",
    "score": 8,
    "issues": ["Lista de problemas concretos"],
    "suggestions": ["Sugerencias con clases Tailwind cuando aplique"]
  }
]"""

_FAST_MODEL = "claude-haiku-4-5-20251001"
_DEEP_MODEL = "claude-opus-4-7"


@dataclass
class VisualFeedback:
    """Feedback de análisis visual para un área de diseño."""

    area: str
    score: int
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _encode_image(img_path: Path, max_size: int = 1024) -> str:
    """Redimensiona si es necesario y codifica en base64.

    Args:
        img_path: Ruta a la imagen.
        max_size: Dimensión máxima en pixels para el lado más largo.

    Returns:
        String base64 del PNG resultante.
    """
    with Image.open(img_path) as img:
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode()


def analyze_screenshot(
    img_path: Path,
    fast: bool = False,
) -> list[VisualFeedback]:
    """Analiza un screenshot con Claude vision y retorna feedback estructurado.

    Args:
        img_path: Ruta al screenshot PNG/JPG.
        fast: Si True usa el modelo rápido (Haiku) en vez de Opus.

    Returns:
        Lista de VisualFeedback por área. Vacía si el archivo no existe o hay error.
    """
    if not img_path.exists():
        logger.warning("Screenshot no encontrado: %s", img_path)
        return []

    try:
        img_b64 = _encode_image(img_path)
    except Exception as exc:
        logger.warning("No se pudo cargar imagen %s: %s", img_path, exc)
        return []

    model = _FAST_MODEL if fast else _DEEP_MODEL
    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": _ANALYSIS_PROMPT},
                    ],
                }
            ],
        )
        raw = response.content[0].text
        areas = json.loads(raw)
        return [
            VisualFeedback(
                area=a.get("area", "unknown"),
                score=int(a.get("score", 5)),
                issues=a.get("issues", []),
                suggestions=a.get("suggestions", []),
            )
            for a in areas
            if isinstance(a, dict)
        ]
    except Exception as exc:
        logger.warning("Error en análisis visual: %s", exc)
        return []
