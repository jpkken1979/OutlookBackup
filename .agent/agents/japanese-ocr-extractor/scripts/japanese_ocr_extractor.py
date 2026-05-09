#!/usr/bin/env python3
"""
Japanese OCR Extractor Agent - Extrae texto de documentos japoneses.

Wrapper del skill japanese-document-ocr que proporciona una interfaz
de agente para extracción de OCR de documentos japoneses.

Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add skills path
SKILLS_PATH = Path(__file__).parent.parent.parent.parent / "skills"
sys.path.insert(0, str(SKILLS_PATH / "japanese-document-ocr" / "scripts"))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class JapaneseOcrExtractorAgent:
    """Agente especializado en extracción de texto de documentos japoneses."""

    def __init__(self, engine: str = "easyocr"):
        self.engine = engine

    def extract(
        self, image_path: str, preprocess: bool = True, output_format: str = "dict"
    ) -> dict[str, Any]:
        """
        Extrae texto de un documento japonés.

        Args:
            image_path: Ruta a la imagen
            preprocess: Aplicar preprocesamiento
            output_format: Formato de salida (dict, json, text)

        Returns:
            Diccionario con el resultado de la extracción
        """
        return extract_text(image_path, self.engine, preprocess, output_format)


def extract_text(
    image_path: str, engine: str = "easyocr", preprocess: bool = True, output_format: str = "dict"
) -> dict[str, Any]:
    """
    Extrae texto de un documento japonés.

    Args:
        image_path: Ruta a la imagen
        engine: Motor OCR (easyocr, tesseract, paddleocr)
        preprocess: Aplicar preprocesamiento
        output_format: Formato de salida (dict, json, text)

    Returns:
        Diccionario con el resultado de la extracción
    """
    try:
        from japanese_document_ocr import JapaneseDocumentOCR
    except ImportError as e:
        return {
            "success": False,
            "error": f"OCR module not available: {e}",
            "hint": "Install required packages: pip install easyocr opencv-python",
        }

    try:
        ocr = JapaneseDocumentOCR(engine=engine)
        result = ocr.extract(image_path=image_path, preprocess=preprocess)

        if output_format == "text":
            return {
                "success": result.success,
                "text": result.raw_text,
                "document_type": result.document_type.value,
            }
        elif output_format == "json":
            return result.to_dict()
        else:  # dict
            return {
                "success": result.success,
                "document_type": result.document_type.value,
                "fields": {
                    pair.label: {
                        "value": pair.value,
                        "confidence": pair.confidence,
                        "original_label": pair.label_japanese,
                    }
                    for pair in result.layout_pairs
                },
                "raw_text": result.raw_text,
                "warnings": result.warnings,
                "processing_time_ms": result.processing_time_ms,
            }

    except Exception as e:
        logger.error(f"Error en OCR: {e}")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Japanese OCR Extractor Agent - Extrae texto de documentos japoneses"
    )
    parser.add_argument("image", help="Ruta a la imagen del documento")
    parser.add_argument(
        "--engine",
        choices=["easyocr", "tesseract", "paddleocr"],
        default="easyocr",
        help="Motor OCR a usar (default: easyocr)",
    )
    parser.add_argument(
        "--no-preprocess", action="store_true", help="Desactivar preprocesamiento de imagen"
    )
    parser.add_argument(
        "--format", choices=["dict", "json", "text"], default="dict", help="Formato de salida"
    )
    parser.add_argument(
        "--json", action="store_true", help="Salida en formato JSON (equivalente a --format json)"
    )

    args = parser.parse_args()

    output_format = "json" if args.json else args.format

    result = extract_text(
        image_path=args.image,
        engine=args.engine,
        preprocess=not args.no_preprocess,
        output_format=output_format,
    )

    if args.json or output_format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif output_format == "text":
        if result.get("success"):
            print(f"Tipo: {result.get('document_type', 'unknown')}\n")
            print(result.get("text", ""))
        else:
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
    else:
        if result.get("success"):
            print(f"Tipo de documento: {result.get('document_type', 'unknown')}")
            print(f"Tiempo: {result.get('processing_time_ms', 0)}ms")
            print("\n=== Campos extraídos ===")
            for field, data in result.get("fields", {}).items():
                print(f"  {data.get('original_label', field)} ({field}): {data.get('value')}")
                print(f"    Confianza: {data.get('confidence', 0):.2%}")
            if result.get("warnings"):
                print("\n=== Advertencias ===")
                for w in result["warnings"]:
                    print(f"  - {w}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
