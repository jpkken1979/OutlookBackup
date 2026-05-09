#!/usr/bin/env python3
"""
Face Detection & Extraction - Detección y recorte de fotos en documentos.

Detecta la región de la foto/rostro en documentos de identidad y la recorta.
NO realiza reconocimiento facial (identificación de personas).

Métodos soportados:
- Haar Cascade (rápido)
- DNN (deep learning, más preciso)
- Template matching (para posiciones conocidas)

Version: 1.0.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

# Imports opcionales con fallback
try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# Enums y Constantes
# =============================================================================


class DetectionMethod(str, Enum):
    """Métodos de detección disponibles."""

    HAAR = "haar"
    DNN = "dnn"
    TEMPLATE = "template"


class DocumentType(str, Enum):
    """Tipos de documentos para optimizar detección."""

    ZAIRYUCARD = "zairyucard"
    PASSPORT = "passport"
    LICENSE = "license"
    GENERIC = "generic"


# Posiciones aproximadas de fotos en documentos (porcentaje del documento)
# Formato: (x_start%, y_start%, width%, height%)
PHOTO_REGIONS = {
    DocumentType.ZAIRYUCARD: {
        "primary": (0.02, 0.15, 0.28, 0.55),  # Lado izquierdo
        "fallback": (0.0, 0.1, 0.35, 0.6),
    },
    DocumentType.PASSPORT: {
        "primary": (0.02, 0.25, 0.30, 0.50),
        "fallback": (0.0, 0.2, 0.35, 0.55),
    },
    DocumentType.LICENSE: {
        "primary": (0.02, 0.20, 0.25, 0.50),
        "fallback": (0.0, 0.15, 0.30, 0.55),
    },
    DocumentType.GENERIC: {"primary": (0.0, 0.0, 0.40, 0.60), "fallback": (0.0, 0.0, 0.50, 0.70)},
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DetectedFace:
    """Rostro/foto detectado en un documento."""

    bbox: tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    image_bytes: bytes
    image_mime: str = "image/png"

    def to_dict(self, include_bytes: bool = False) -> dict[str, Any]:
        result = {
            "bbox": f"{self.bbox[0]},{self.bbox[1]},{self.bbox[2]},{self.bbox[3]}",
            "confidence": self.confidence,
            "image_mime": self.image_mime,
            "size_bytes": len(self.image_bytes),
        }
        if include_bytes:
            result["image_bytes"] = self.image_bytes
        return result


@dataclass
class DetectionResult:
    """Resultado de la detección de rostros."""

    success: bool
    faces: list[DetectedFace] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: int = 0

    def to_dict(self, include_bytes: bool = False) -> dict[str, Any]:
        return {
            "success": self.success,
            "faces": [f.to_dict(include_bytes) for f in self.faces],
            "warnings": self.warnings,
            "processing_time_ms": self.processing_time_ms,
            "face_count": len(self.faces),
        }


# =============================================================================
# Face Detector
# =============================================================================


class FaceDetector:
    """
    Detector de fotos/rostros en documentos de identidad.

    Uso:
        detector = FaceDetector(method="haar")
        result = detector.detect_and_extract("document.jpg")
    """

    # Ruta al clasificador Haar por defecto de OpenCV
    HAAR_CASCADE_PATH = None  # Se detecta automáticamente

    def __init__(
        self, method: str | DetectionMethod = DetectionMethod.HAAR, min_confidence: float = 0.5
    ):
        """
        Inicializa el detector.

        Args:
            method: Método de detección (haar, dnn, template)
            min_confidence: Confianza mínima para aceptar detección
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV requerido: pip install opencv-python")

        if isinstance(method, str):
            method = DetectionMethod(method.lower())

        self.method = method
        self.min_confidence = min_confidence

        # Inicializar clasificador según método
        if method == DetectionMethod.HAAR:
            self._init_haar()
        elif method == DetectionMethod.DNN:
            self._init_dnn()

    def _init_haar(self):
        """Inicializa el clasificador Haar Cascade."""
        # Buscar el archivo del clasificador
        cascade_paths = [
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
            "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        ]

        self.face_cascade = None
        for path in cascade_paths:
            if Path(path).exists():
                self.face_cascade = cv2.CascadeClassifier(path)
                break

        if self.face_cascade is None or self.face_cascade.empty():
            # Intentar cargar desde cv2.data
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )

    def _init_dnn(self):
        """Inicializa el detector DNN de OpenCV."""
        # El detector DNN requiere archivos de modelo
        # Por simplicidad, usamos Haar como fallback
        logger.warning("DNN detector no disponible, usando Haar Cascade")
        self._init_haar()
        self.method = DetectionMethod.HAAR

    def _load_image(
        self, image_path: str | None = None, image_bytes: bytes | None = None
    ) -> np.ndarray:
        """Carga imagen desde path o bytes."""
        if image_bytes:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif image_path:
            img = cv2.imread(str(image_path))
        else:
            raise ValueError("Debe proporcionar image_path o image_bytes")

        if img is None:
            raise ValueError("No se pudo cargar la imagen")

        return img

    def _crop_and_encode(
        self, img: np.ndarray, bbox: tuple[int, int, int, int], output_format: str = "png"
    ) -> tuple[bytes, str]:
        """
        Recorta una región y la codifica como bytes.

        Args:
            img: Imagen original
            bbox: (x, y, width, height)
            output_format: Formato de salida (png, jpeg)

        Returns:
            (bytes, mime_type)
        """
        x, y, w, h = bbox

        # Asegurar que las coordenadas están dentro de la imagen
        h_img, w_img = img.shape[:2]
        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        w = min(w, w_img - x)
        h = min(h, h_img - y)

        # Recortar
        cropped = img[y : y + h, x : x + w]

        # Codificar
        if output_format.lower() == "jpeg":
            encode_param = [cv2.IMWRITE_JPEG_QUALITY, 95]
            success, buffer = cv2.imencode(".jpg", cropped, encode_param)
            mime = "image/jpeg"
        else:
            success, buffer = cv2.imencode(".png", cropped)
            mime = "image/png"

        if not success:
            raise RuntimeError("Error al codificar imagen")

        return buffer.tobytes(), mime

    def _detect_haar(
        self, img: np.ndarray, search_region: tuple[int, int, int, int] | None = None
    ) -> list[tuple[int, int, int, int]]:
        """
        Detecta rostros usando Haar Cascade.

        Args:
            img: Imagen en BGR
            search_region: Región donde buscar (x, y, w, h)

        Returns:
            Lista de bounding boxes
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Si hay región de búsqueda, recortar
        offset_x, offset_y = 0, 0
        if search_region:
            x, y, w, h = search_region
            gray = gray[y : y + h, x : x + w]
            offset_x, offset_y = x, y

        # Detectar rostros
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE
        )

        # Ajustar coordenadas si había región de búsqueda
        result = []
        for x, y, w, h in faces:
            result.append((x + offset_x, y + offset_y, w, h))

        return result

    def _detect_by_region(
        self, img: np.ndarray, document_type: DocumentType
    ) -> list[tuple[tuple[int, int, int, int], float]]:
        """
        Detecta rostros basándose en regiones típicas del documento.

        Args:
            img: Imagen del documento
            document_type: Tipo de documento

        Returns:
            Lista de (bbox, confidence)
        """
        h_img, w_img = img.shape[:2]
        results = []

        regions = PHOTO_REGIONS.get(document_type, PHOTO_REGIONS[DocumentType.GENERIC])

        for region_name in ["primary", "fallback"]:
            if region_name not in regions:
                continue

            rx, ry, rw, rh = regions[region_name]

            # Convertir porcentajes a píxeles
            search_x = int(w_img * rx)
            search_y = int(h_img * ry)
            search_w = int(w_img * rw)
            search_h = int(h_img * rh)

            search_region = (search_x, search_y, search_w, search_h)

            # Buscar rostros en esta región
            faces = self._detect_haar(img, search_region)

            for bbox in faces:
                # La confianza es mayor si está en la región primaria
                confidence = 0.9 if region_name == "primary" else 0.7
                results.append((bbox, confidence))

        return results

    def detect_and_extract(
        self,
        image_path: str | None = None,
        image_bytes: bytes | None = None,
        document_type: str | DocumentType = DocumentType.GENERIC,
        output_format: str = "png",
        expand_margin: float = 0.1,
    ) -> DetectionResult:
        """
        Detecta y extrae fotos/rostros del documento.

        Args:
            image_path: Ruta a la imagen
            image_bytes: Bytes de la imagen
            document_type: Tipo de documento para optimizar búsqueda
            output_format: Formato de salida (png, jpeg)
            expand_margin: Margen extra alrededor del rostro (0.1 = 10%)

        Returns:
            DetectionResult con fotos detectadas
        """
        import time

        start_time = time.time()

        warnings = []

        if isinstance(document_type, str):
            try:
                document_type = DocumentType(document_type.lower())
            except ValueError:
                document_type = DocumentType.GENERIC

        try:
            # Cargar imagen
            img = self._load_image(image_path, image_bytes)
            h_img, w_img = img.shape[:2]

            # Intentar detección por región primero
            detections = self._detect_by_region(img, document_type)

            # Si no se encontró nada, buscar en toda la imagen
            if not detections:
                logger.info("No se encontró en regiones típicas, buscando en toda la imagen")
                faces = self._detect_haar(img)

                for bbox in faces:
                    # Confianza más baja porque no está en región esperada
                    detections.append((bbox, 0.6))

            if not detections:
                return DetectionResult(
                    success=False,
                    warnings=["No se detectó ningún rostro/foto en el documento"],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )

            # Extraer las fotos
            faces = []
            for bbox, confidence in detections:
                if confidence < self.min_confidence:
                    continue

                x, y, w, h = bbox

                # Expandir margen
                if expand_margin > 0:
                    margin_x = int(w * expand_margin)
                    margin_y = int(h * expand_margin)

                    x = max(0, x - margin_x)
                    y = max(0, y - margin_y)
                    w = min(w + 2 * margin_x, w_img - x)
                    h = min(h + 2 * margin_y, h_img - y)

                # Recortar y codificar
                try:
                    image_bytes_out, mime = self._crop_and_encode(img, (x, y, w, h), output_format)

                    faces.append(
                        DetectedFace(
                            bbox=(x, y, w, h),
                            confidence=confidence,
                            image_bytes=image_bytes_out,
                            image_mime=mime,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error al recortar foto: {e}")
                    warnings.append(f"Error al recortar una foto: {e}")

            # Ordenar por confianza
            faces.sort(key=lambda f: f.confidence, reverse=True)

            # Advertencia si se detectaron múltiples rostros
            if len(faces) > 1:
                warnings.append(
                    f"Se detectaron {len(faces)} rostros/fotos. Revisar si son correctas."
                )

            processing_time = int((time.time() - start_time) * 1000)

            return DetectionResult(
                success=len(faces) > 0,
                faces=faces,
                warnings=warnings,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Error en detección: {e}")
            return DetectionResult(
                success=False,
                warnings=[f"Error en detección: {str(e)}"],
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    def detect_best_face(
        self,
        image_path: str | None = None,
        image_bytes: bytes | None = None,
        document_type: str | DocumentType = DocumentType.GENERIC,
    ) -> DetectedFace | None:
        """
        Detecta y retorna solo la mejor foto (mayor confianza).

        Args:
            image_path: Ruta a la imagen
            image_bytes: Bytes de la imagen
            document_type: Tipo de documento

        Returns:
            DetectedFace o None
        """
        result = self.detect_and_extract(
            image_path=image_path, image_bytes=image_bytes, document_type=document_type
        )

        if result.success and result.faces:
            return result.faces[0]  # Ya está ordenado por confianza

        return None


# =============================================================================
# Convenience Functions
# =============================================================================


def detect_face_in_document(
    image_path: str | None = None, image_bytes: bytes | None = None, document_type: str = "generic"
) -> DetectionResult:
    """
    Función de conveniencia para detectar rostros.

    Args:
        image_path: Ruta a la imagen
        image_bytes: Bytes de la imagen
        document_type: Tipo de documento (zairyucard, passport, license, generic)

    Returns:
        DetectionResult
    """
    detector = FaceDetector(method="haar")
    return detector.detect_and_extract(
        image_path=image_path, image_bytes=image_bytes, document_type=document_type
    )


def extract_face_bytes(
    image_path: str | None = None, image_bytes: bytes | None = None, document_type: str = "generic"
) -> tuple[bytes, str, str] | None:
    """
    Extrae solo los bytes de la foto principal.

    Returns:
        (image_bytes, mime_type, bbox) o None
    """
    detector = FaceDetector(method="haar")
    face = detector.detect_best_face(
        image_path=image_path, image_bytes=image_bytes, document_type=document_type
    )

    if face:
        bbox_str = f"{face.bbox[0]},{face.bbox[1]},{face.bbox[2]},{face.bbox[3]}"
        return (face.image_bytes, face.image_mime, bbox_str)

    return None


# =============================================================================
# CLI
# =============================================================================


def main():
    import sys
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Detección y extracción de fotos en documentos de identidad"
    )
    parser.add_argument("image", help="Ruta a la imagen del documento")
    parser.add_argument(
        "--type",
        choices=["zairyucard", "passport", "license", "generic"],
        default="generic",
        help="Tipo de documento",
    )
    parser.add_argument("--output", help="Directorio para guardar fotos extraídas")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")

    args = parser.parse_args()

    try:
        detector = FaceDetector(method="haar")
        result = detector.detect_and_extract(image_path=args.image, document_type=args.type)

        if args.output and result.success:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            for i, face in enumerate(result.faces):
                ext = "png" if face.image_mime == "image/png" else "jpg"
                output_path = output_dir / f"face_{i}.{ext}"
                output_path.write_bytes(face.image_bytes)
                print(f"Guardado: {output_path}")

        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"Detección exitosa: {result.success}")
            print(f"Rostros encontrados: {len(result.faces)}")
            print(f"Tiempo: {result.processing_time_ms}ms")

            for i, face in enumerate(result.faces):
                print(f"\nRostro {i + 1}:")
                print(f"  BBox: {face.bbox}")
                print(f"  Confianza: {face.confidence:.2%}")
                print(f"  Tamaño: {len(face.image_bytes)} bytes")

            if result.warnings:
                print("\nAdvertencias:")
                for w in result.warnings:
                    print(f"  - {w}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
