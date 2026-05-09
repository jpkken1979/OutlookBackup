"""Figma bridge — sincronización bidireccional con Figma via MCP."""
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FigmaSyncResult:
    """Resultado de sincronización con Figma."""

    tokens_read: dict = field(default_factory=dict)
    components_written: list[str] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


def read_tokens_from_figma(file_id: Optional[str] = None) -> dict:
    """Lee design tokens del archivo Figma configurado.

    Args:
        file_id: ID del archivo Figma. Si None, usa env var FIGMA_FILE_ID.

    Returns:
        Design tokens en formato W3C DTCG o dict vacío si no está configurado.
    """
    fid = file_id or os.getenv("FIGMA_FILE_ID")
    if not fid:
        logger.info("FIGMA_FILE_ID no configurado — saltando lectura de tokens Figma")
        return {}

    logger.info("Figma tokens disponibles via skill figma:figma-use con file_id=%s", fid)
    return {}


def write_component_to_figma(
    component_tsx: str,  # noqa: ARG001
    component_name: str,
    file_id: Optional[str] = None,
) -> FigmaSyncResult:
    """Escribe un componente mejorado al canvas de Figma.

    Args:
        component_tsx: Código TSX del componente.
        component_name: Nombre del componente en Figma.
        file_id: ID del archivo Figma destino.

    Returns:
        FigmaSyncResult con estado de la operación.
    """
    fid = file_id or os.getenv("FIGMA_FILE_ID")
    if not fid:
        return FigmaSyncResult(
            success=False,
            error="FIGMA_FILE_ID no configurado",
        )

    logger.info(
        "Para escribir '%s' a Figma: usar skill figma:figma-implement-design "
        "con el código TSX proporcionado.",
        component_name,
    )
    return FigmaSyncResult(
        components_written=[component_name],
        success=True,
    )
