"""Canva bridge — crea prototipos rápidos via Canva MCP."""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CanvaPrototype:
    """Resultado de creación de prototipo en Canva."""

    design_url: Optional[str]
    thumbnail_url: Optional[str]
    success: bool
    error: Optional[str] = None


def create_prototype(
    component_tsx: str,
    design_title: str = "UI Prototype",
) -> CanvaPrototype:
    """Crea un prototipo visual en Canva a partir de un componente TSX.

    En sesiones Claude Code, usa directamente los MCP tools de Canva.
    Este módulo provee la lógica de preparación del contenido.

    Args:
        component_tsx: Código TSX del componente a prototipar.
        design_title: Título del diseño en Canva.

    Returns:
        CanvaPrototype con URL del diseño si fue exitoso.
    """
    prompt = _build_canva_prompt(component_tsx, design_title)
    logger.info("Canva prompt preparado para: %s", design_title)
    logger.info("Invocar mcp__claude_ai_Canva__generate-design con prompt:\n%s", prompt[:200])

    return CanvaPrototype(
        design_url=None,
        thumbnail_url=None,
        success=False,
        error="Canva MCP solo disponible dentro de sesión Claude Code",
    )


def _build_canva_prompt(tsx: str, title: str) -> str:
    """Prepara el prompt para la generación del diseño en Canva.

    Args:
        tsx: Código TSX del componente.
        title: Título del diseño.

    Returns:
        Prompt listo para usar con mcp__claude_ai_Canva__generate-design.
    """
    elements = re.findall(r"<(\w+)[^>]*>", tsx)
    unique_elements = list(dict.fromkeys(elements))[:8]
    return (
        f"Diseño UI moderno para: {title}. "
        f"Elementos: {', '.join(unique_elements)}. "
        "Estilo: minimalista, profesional, paleta neutral con acento primario. "
        "Layout: desktop app, fondo claro, tipografía Inter."
    )
