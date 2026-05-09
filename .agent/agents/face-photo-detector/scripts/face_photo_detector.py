#!/usr/bin/env python3
"""
Face Photo Detector Agent - Detecta y extrae fotos de rostros.

Wrapper del skill face-detection-extraction que proporciona una interfaz
de agente para detección de fotos en documentos de identidad.

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
sys.path.insert(0, str(SKILLS_PATH / "face-detection-extraction" / "scripts"))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class FacePhotoDetectorAgent:
    """Agente especializado en detección y extracción de rostros en documentos."""

    def __init__(self, method: str = "haar"):
        self.method = method

    def detect(
        self,
        image_path: str,
        document_type: str = "generic",
        output_dir: str | None = None,
        output_format: str = "png",
    ) -> dict[str, Any]:
        """
        Detecta y extrae foto de rostro de un documento.

        Args:
            image_path: Ruta a la imagen del documento
            document_type: Tipo de documento
            output_dir: Directorio para guardar fotos extraídas
            output_format: Formato de salida

        Returns:
            Diccionario con el resultado de la detección
        """
        return detect_face(image_path, document_type, output_dir, output_format)


def detect_face(
    image_path: str,
    document_type: str = "generic",
    output_dir: str | None = None,
    output_format: str = "png",
) -> dict[str, Any]:
    """
    Detecta y extrae foto de rostro de un documento.

    Args:
        image_path: Ruta a la imagen del documento
        document_type: Tipo de documento (zairyucard, passport, license, generic)
        output_dir: Directorio para guardar fotos extraídas
        output_format: Formato de salida (png, jpeg)

    Returns:
        Diccionario con el resultado de la detección
    """
    try:
        from face_detection_extraction import FaceDetector
    except ImportError as e:
        return {
            "success": False,
            "error": f"Face detection module not available: {e}",
            "hint": "Install required packages: pip install opencv-python",
        }

    try:
        detector = FaceDetector(method="haar")
        result = detector.detect_and_extract(
            image_path=image_path, document_type=document_type, output_format=output_format
        )

        output = {
            "success": result.success,
            "face_count": len(result.faces),
            "faces": [],
            "warnings": result.warnings,
            "processing_time_ms": result.processing_time_ms,
        }

        for i, face in enumerate(result.faces):
            face_info = {
                "index": i,
                "bbox": f"{face.bbox[0]},{face.bbox[1]},{face.bbox[2]},{face.bbox[3]}",
                "confidence": face.confidence,
                "size_bytes": len(face.image_bytes),
                "mime": face.image_mime,
            }

            # Save if output_dir specified
            if output_dir and result.success:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                ext = "png" if face.image_mime == "image/png" else "jpg"
                file_path = output_path / f"face_{i}.{ext}"
                file_path.write_bytes(face.image_bytes)
                face_info["saved_path"] = str(file_path)

            output["faces"].append(face_info)

        return output

    except Exception as e:
        logger.error(f"Error en detección: {e}")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Face Photo Detector Agent - Detecta y extrae fotos de rostros"
    )
    parser.add_argument("image", help="Ruta a la imagen del documento")
    parser.add_argument(
        "--type",
        choices=["zairyucard", "passport", "license", "generic"],
        default="generic",
        help="Tipo de documento (ayuda a optimizar la búsqueda)",
    )
    parser.add_argument("--output", help="Directorio para guardar fotos extraídas")
    parser.add_argument(
        "--format", choices=["png", "jpeg"], default="png", help="Formato de imagen de salida"
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")

    args = parser.parse_args()

    result = detect_face(
        image_path=args.image,
        document_type=args.type,
        output_dir=args.output,
        output_format=args.format,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("success"):
            print(f"Detección exitosa: {result['face_count']} rostro(s) encontrado(s)")
            print(f"Tiempo: {result.get('processing_time_ms', 0)}ms")

            for face in result.get("faces", []):
                print(f"\n  Rostro #{face['index'] + 1}:")
                print(f"    BBox: {face['bbox']}")
                print(f"    Confianza: {face['confidence']:.2%}")
                print(f"    Tamaño: {face['size_bytes']} bytes")
                if face.get("saved_path"):
                    print(f"    Guardado en: {face['saved_path']}")

            if result.get("warnings"):
                print("\nAdvertencias:")
                for w in result["warnings"]:
                    print(f"  - {w}")
        else:
            print(f"Error: {result.get('error', 'No faces detected')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
