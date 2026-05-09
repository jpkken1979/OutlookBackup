#!/usr/bin/env python3
"""
Script principal de la skill.

Este script sigue los estándares Antigravity:
- Logging con timestamp
- Type hints obligatorios
- Validación con Pydantic
- Manejo de errores estructurado
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Intentar importar Pydantic (opcional pero recomendado)
try:
    from pydantic import BaseModel, Field, ValidationError

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# Configuración de logging estándar Antigravity
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================================
# MODELOS DE DATOS
# ============================================================================


@dataclass
class SkillResult:
    """Resultado estándar de ejecución de skill."""

    status: str  # "success" | "error"
    data: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convierte a JSON formateado."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


if PYDANTIC_AVAILABLE:

    class InputConfig(BaseModel):
        """Configuración de entrada validada con Pydantic."""

        input_data: str = Field(..., description="Datos de entrada")
        format: str = Field(default="json", description="Formato de salida")
        verbose: bool = Field(default=False, description="Modo detallado")

        class Config:
            extra = "forbid"  # No permite campos extra


# ============================================================================
# LÓGICA PRINCIPAL
# ============================================================================


def process_data(input_data: str, format: str = "json", verbose: bool = False) -> SkillResult:
    """
    Procesa los datos de entrada y retorna el resultado.

    Args:
        input_data: Datos a procesar
        format: Formato de salida (json, text, markdown)
        verbose: Si debe incluir información detallada

    Returns:
        SkillResult con el resultado del procesamiento

    Raises:
        ValueError: Si el input es inválido
    """
    start_time = datetime.now()
    logger.info(f"Procesando datos (formato: {format}, verbose: {verbose})")

    try:
        # ====================================================================
        # AQUÍ VA LA LÓGICA DE TU SKILL
        # ====================================================================

        # Ejemplo: procesamiento simple
        result_data = {
            "input_length": len(input_data),
            "processed": input_data.upper(),  # Ejemplo: convertir a mayúsculas
            "word_count": len(input_data.split()),
        }

        if verbose:
            result_data["details"] = {
                "original": input_data,
                "encoding": "utf-8",
            }

        # ====================================================================

        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"Procesamiento completado en {elapsed:.2f}ms")

        return SkillResult(
            status="success",
            data=result_data,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "duration_ms": round(elapsed, 2),
                "format": format,
            },
        )

    except Exception as e:
        logger.error(f"Error en procesamiento: {e}")
        return SkillResult(
            status="error",
            data={"error": str(e)},
            metadata={
                "timestamp": datetime.now().isoformat(),
                "duration_ms": 0,
            },
        )


def validate_input(args: argparse.Namespace) -> str | None:
    """
    Valida los argumentos de entrada.

    Args:
        args: Argumentos parseados

    Returns:
        Mensaje de error si hay problemas, None si todo está bien
    """
    if not args.input:
        return "Se requiere --input o datos por stdin"

    valid_formats = ["json", "text", "markdown"]
    if args.format not in valid_formats:
        return f"Formato inválido. Opciones: {valid_formats}"

    return None


# ============================================================================
# CLI
# ============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Crea el parser de argumentos."""
    parser = argparse.ArgumentParser(
        description="[Nombre de la Skill] - [Descripción breve]",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s --input "texto a procesar"
  %(prog)s --input "texto" --format markdown --verbose
  echo "texto" | %(prog)s
        """,
    )

    parser.add_argument("--input", "-i", type=str, help="Datos de entrada a procesar")

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        default="json",
        choices=["json", "text", "markdown"],
        help="Formato de salida (default: json)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Modo detallado con información adicional"
    )

    parser.add_argument("--output", "-o", type=Path, help="Archivo de salida (default: stdout)")

    return parser


def main() -> int:
    """
    Punto de entrada principal.

    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Leer de stdin si no hay --input
    if not args.input and not sys.stdin.isatty():
        args.input = sys.stdin.read().strip()

    # Validar entrada
    error = validate_input(args)
    if error:
        logger.error(error)
        parser.print_help()
        return 1

    # Procesar
    logger.info("Iniciando skill")
    result = process_data(input_data=args.input, format=args.format, verbose=args.verbose)

    # Formatear salida
    if args.format == "json":
        output = result.to_json()
    elif args.format == "text":
        output = str(result.data)
    else:  # markdown
        output = f"## Resultado\n\n```json\n{result.to_json()}\n```"

    # Escribir salida
    if args.output:
        args.output.write_text(output, encoding="utf-8")
        logger.info(f"Resultado guardado en: {args.output}")
    else:
        print(output)

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
