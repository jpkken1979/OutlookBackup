#!/usr/bin/env python3
"""
Japanese Document OCR - Extracción de texto de documentos japoneses.

NOTE: Using `from __future__ import annotations` to allow forward references
in type hints, so np.ndarray works even when numpy is not installed.

Soporta:
- 在留カード (Zairyū Card)
- Pasaporte japonés
- Licencia de conducir
- Otros documentos con texto japonés

Motores: EasyOCR (default), PaddleOCR, Tesseract

Version: 1.0.0
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any
from enum import Enum
import json

# Imports opcionales con fallback
try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None  # type: ignore
    np = None  # type: ignore

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    from paddleocr import PaddleOCR

    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

try:
    import pytesseract

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path, convert_from_bytes

    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    convert_from_path = None  # type: ignore
    convert_from_bytes = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# Enums y Constantes
# =============================================================================


class OCREngine(str, Enum):
    """Motores OCR disponibles."""

    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"
    TESSERACT = "tesseract"


class DocumentType(str, Enum):
    """Tipos de documentos japoneses."""

    ZAIRYUCARD = "zairyucard"
    PASSPORT = "passport"
    LICENSE = "license"
    MYNUMBER = "mynumber"
    UNKNOWN = "unknown"


# Mapeo de etiquetas japonesas a campos normalizados
JAPANESE_FIELD_MAPPING = {
    # Zairyū Card
    "氏名": "nombre",
    "NAME": "nombre",
    "生年月日": "fecha_nacimiento",
    "DATE OF BIRTH": "fecha_nacimiento",
    "性別": "genero",
    "SEX": "genero",
    "国籍・地域": "nacionalidad",
    "NATIONALITY/REGION": "nacionalidad",
    "国籍": "nacionalidad",
    "住居地": "direccion",
    "ADDRESS": "direccion",
    "住所": "direccion",
    "在留資格": "estado_residencia",
    "STATUS OF RESIDENCE": "estado_residencia",
    "在留期間": "periodo_estancia",
    "PERIOD OF STAY": "periodo_estancia",
    "就労制限の有無": "permiso_trabajo",
    "WORK PERMISSION": "permiso_trabajo",
    "就労不可": "permiso_trabajo",
    "在留カード番号": "numero_tarjeta",
    "RESIDENCE CARD NUMBER": "numero_tarjeta",
    "有効期限": "fecha_expiracion",
    "DATE OF EXPIRY": "fecha_expiracion",
    "交付年月日": "fecha_emision",
    "DATE OF ISSUE": "fecha_emision",
    # Pasaporte
    "旅券番号": "numero_pasaporte",
    "PASSPORT NO": "numero_pasaporte",
    "発行年月日": "fecha_emision",
    # Licencia
    "免許証番号": "numero_licencia",
    "免許の条件等": "condiciones_licencia",
}

# Patrones de fechas japonesas
DATE_PATTERNS = [
    # 令和5年12月25日
    r"(令和|平成|昭和|大正|明治)(\d+)年(\d+)月(\d+)日",
    # 2023年12月25日
    r"(\d{4})年(\d{1,2})月(\d{1,2})日",
    # 2023/12/25 o 2023-12-25
    r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})",
]

# Era japonesa a año gregoriano
ERA_START_YEARS = {
    "明治": 1868,
    "大正": 1912,
    "昭和": 1926,
    "平成": 1989,
    "令和": 2019,
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TextBlock:
    """Bloque de texto detectado."""

    text: str
    bbox: tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    is_vertical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "bbox": f"{self.bbox[0]},{self.bbox[1]},{self.bbox[2]},{self.bbox[3]}",
            "confidence": self.confidence,
            "is_vertical": self.is_vertical,
        }


@dataclass
class LayoutPair:
    """Par etiqueta-valor detectado."""

    label: str
    label_japanese: str
    value: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "label_japanese": self.label_japanese,
            "value": self.value,
            "confidence": self.confidence,
            "bbox": f"{self.bbox[0]},{self.bbox[1]},{self.bbox[2]},{self.bbox[3]}"
            if self.bbox
            else None,
        }


@dataclass
class OCRResult:
    """Resultado completo de OCR."""

    success: bool
    text_blocks: list[TextBlock] = field(default_factory=list)
    layout_pairs: list[LayoutPair] = field(default_factory=list)
    raw_text: str = ""
    document_type: DocumentType = DocumentType.UNKNOWN
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "text_blocks": [b.to_dict() for b in self.text_blocks],
            "layout_pairs": [p.to_dict() for p in self.layout_pairs],
            "raw_text": self.raw_text,
            "document_type": self.document_type.value,
            "warnings": self.warnings,
            "processing_time_ms": self.processing_time_ms,
        }


# =============================================================================
# Image Preprocessing
# =============================================================================


class ImagePreprocessor:
    """Preprocesador de imágenes para mejorar OCR."""

    @staticmethod
    def load_image(
        image_path: str | None = None,
        image_bytes: bytes | None = None,
        pdf_page: int = 0,
        pdf_dpi: int = 300,
    ) -> np.ndarray:
        """
        Carga imagen desde path o bytes.

        Soporta:
        - Imágenes (jpg, png, bmp, etc.)
        - PDFs (convierte la primera página a imagen)

        Args:
            image_path: Ruta al archivo
            image_bytes: Bytes del archivo
            pdf_page: Página del PDF a extraer (default: 0 = primera)
            pdf_dpi: Resolución para conversión PDF (default: 300)

        Returns:
            Imagen como numpy array
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV (cv2) requerido para preprocesamiento")

        # Detectar si es PDF
        is_pdf = False
        if image_path:
            is_pdf = str(image_path).lower().endswith(".pdf")
        elif image_bytes:
            # Detectar PDF por magic bytes (%PDF-)
            is_pdf = image_bytes[:5] == b"%PDF-"

        if is_pdf:
            # Convertir PDF a imagen
            if not PDF2IMAGE_AVAILABLE:
                raise ImportError(
                    "pdf2image requerido para PDFs: pip install pdf2image\n"
                    "También necesita poppler instalado en el sistema"
                )

            if image_path:
                pages = convert_from_path(
                    str(image_path), dpi=pdf_dpi, first_page=pdf_page + 1, last_page=pdf_page + 1
                )
            else:
                pages = convert_from_bytes(
                    image_bytes, dpi=pdf_dpi, first_page=pdf_page + 1, last_page=pdf_page + 1
                )

            if not pages:
                raise ValueError(f"No se pudo extraer página {pdf_page} del PDF")

            # Convertir PIL Image a numpy array
            pil_image = pages[0]
            img = np.array(pil_image)
            # Convertir RGB a BGR (OpenCV format)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        elif image_bytes:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif image_path:
            img = cv2.imread(str(image_path))
        else:
            raise ValueError("Debe proporcionar image_path o image_bytes")

        if img is None:
            raise ValueError("No se pudo cargar la imagen")

        return img

    @staticmethod
    def to_grayscale(img: np.ndarray) -> np.ndarray:
        """Convierte a escala de grises."""
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    @staticmethod
    def enhance_contrast(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
        """Mejora el contraste usando CLAHE."""
        if len(img.shape) == 3:
            img = ImagePreprocessor.to_grayscale(img)

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        return clahe.apply(img)

    @staticmethod
    def denoise(img: np.ndarray) -> np.ndarray:
        """Reduce ruido."""
        if len(img.shape) == 3:
            return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        return cv2.fastNlMeansDenoising(img, None, 10, 7, 21)

    @staticmethod
    def deskew(img: np.ndarray) -> np.ndarray:
        """Endereza imagen rotada."""
        gray = ImagePreprocessor.to_grayscale(img) if len(img.shape) == 3 else img

        # Detectar bordes
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Detectar líneas con Hough
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return img

        # Calcular ángulo promedio
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle = (theta * 180 / np.pi) - 90
            if -45 < angle < 45:
                angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)

        if abs(median_angle) < 0.5:
            return img

        # Rotar imagen
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

        return rotated

    @staticmethod
    def binarize(img: np.ndarray, adaptive: bool = True) -> np.ndarray:
        """Binariza imagen (blanco/negro)."""
        gray = ImagePreprocessor.to_grayscale(img) if len(img.shape) == 3 else img

        if adaptive:
            return cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary

    @staticmethod
    def preprocess_for_ocr(
        img: np.ndarray, deskew: bool = True, enhance: bool = True, denoise: bool = True
    ) -> np.ndarray:
        """Pipeline completo de preprocesamiento."""
        result = img.copy()

        if deskew:
            result = ImagePreprocessor.deskew(result)

        if denoise:
            result = ImagePreprocessor.denoise(result)

        if enhance:
            result = ImagePreprocessor.enhance_contrast(result)

        return result


# =============================================================================
# OCR Engines
# =============================================================================


class BaseOCREngine:
    """Clase base para motores OCR."""

    def extract(self, img: np.ndarray) -> list[TextBlock]:
        """Extrae texto de imagen."""
        raise NotImplementedError


class EasyOCREngine(BaseOCREngine):
    """Motor EasyOCR para japonés."""

    def __init__(self, languages: list[str] = None):
        if not EASYOCR_AVAILABLE:
            raise ImportError("EasyOCR no instalado: pip install easyocr")

        self.languages = languages or ["ja", "en"]
        self.reader = easyocr.Reader(self.languages, gpu=False)

    def extract(self, img: np.ndarray) -> list[TextBlock]:
        """Extrae texto usando EasyOCR."""
        results = self.reader.readtext(img)

        blocks = []
        for bbox, text, conf in results:
            # bbox es [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            x = int(min(x_coords))
            y = int(min(y_coords))
            w = int(max(x_coords) - x)
            h = int(max(y_coords) - y)

            # Detectar texto vertical
            is_vertical = h > w * 2

            blocks.append(
                TextBlock(text=text, bbox=(x, y, w, h), confidence=conf, is_vertical=is_vertical)
            )

        return blocks


class TesseractEngine(BaseOCREngine):
    """Motor Tesseract para japonés."""

    def __init__(self, languages: list[str] = None):
        if not TESSERACT_AVAILABLE:
            raise ImportError("pytesseract no instalado: pip install pytesseract")

        self.languages = languages or ["jpn", "eng"]
        self.lang_str = "+".join(self.languages)

    def extract(self, img: np.ndarray) -> list[TextBlock]:
        """Extrae texto usando Tesseract."""
        # Obtener datos con bounding boxes
        data = pytesseract.image_to_data(
            img, lang=self.lang_str, output_type=pytesseract.Output.DICT
        )

        blocks = []
        n_boxes = len(data["text"])

        for i in range(n_boxes):
            text = data["text"][i].strip()
            if not text:
                continue

            conf = float(data["conf"][i]) / 100 if data["conf"][i] != -1 else 0.5

            blocks.append(
                TextBlock(
                    text=text,
                    bbox=(data["left"][i], data["top"][i], data["width"][i], data["height"][i]),
                    confidence=conf,
                )
            )

        return blocks


class PaddleOCREngine(BaseOCREngine):
    """Motor PaddleOCR para japonés."""

    def __init__(self, languages: list[str] = None):
        if not PADDLEOCR_AVAILABLE:
            raise ImportError("PaddleOCR no instalado: pip install paddlepaddle paddleocr")

        self.ocr = PaddleOCR(use_angle_cls=True, lang="japan")

    def extract(self, img: np.ndarray) -> list[TextBlock]:
        """Extrae texto usando PaddleOCR."""
        result = self.ocr.ocr(img, cls=True)

        blocks = []
        if result and result[0]:
            for line in result[0]:
                bbox = line[0]
                text = line[1][0]
                conf = line[1][1]

                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                x = int(min(x_coords))
                y = int(min(y_coords))
                w = int(max(x_coords) - x)
                h = int(max(y_coords) - y)

                blocks.append(TextBlock(text=text, bbox=(x, y, w, h), confidence=conf))

        return blocks


# =============================================================================
# Date Parser
# =============================================================================


class JapaneseDateParser:
    """Parser de fechas japonesas."""

    @staticmethod
    def parse(text: str) -> str | None:
        """
        Parsea fecha japonesa a formato ISO (YYYY-MM-DD).

        Args:
            text: Texto con fecha

        Returns:
            Fecha en formato YYYY-MM-DD o None
        """
        text = text.strip()

        # Patrón 1: Era japonesa (令和5年12月25日)
        match = re.search(r"(令和|平成|昭和|大正|明治)(\d+)年(\d+)月(\d+)日", text)
        if match:
            era = match.group(1)
            era_year = int(match.group(2))
            month = int(match.group(3))
            day = int(match.group(4))

            if era in ERA_START_YEARS:
                year = ERA_START_YEARS[era] + era_year - 1
                return f"{year:04d}-{month:02d}-{day:02d}"

        # Patrón 2: Año occidental (2023年12月25日)
        match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"

        # Patrón 3: Formato numérico (2023/12/25 o 2023-12-25)
        match = re.search(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"

        return None


# =============================================================================
# Layout Analyzer
# =============================================================================


class LayoutAnalyzer:
    """Analiza el layout para detectar pares etiqueta-valor."""

    @staticmethod
    def detect_document_type(blocks: list[TextBlock]) -> DocumentType:
        """Detecta el tipo de documento basado en el texto."""
        all_text = " ".join(b.text for b in blocks).lower()

        if "在留カード" in all_text or "residence card" in all_text.lower():
            return DocumentType.ZAIRYUCARD
        elif "旅券" in all_text or "passport" in all_text.lower():
            return DocumentType.PASSPORT
        elif "運転免許" in all_text or "license" in all_text.lower():
            return DocumentType.LICENSE
        elif "マイナンバー" in all_text or "個人番号" in all_text:
            return DocumentType.MYNUMBER

        return DocumentType.UNKNOWN

    @staticmethod
    def find_label_value_pairs(blocks: list[TextBlock]) -> list[LayoutPair]:
        """
        Detecta pares etiqueta-valor basándose en proximidad espacial.

        Estrategia:
        1. Identificar bloques que coinciden con etiquetas conocidas
        2. Buscar el bloque más cercano a la derecha o abajo como valor
        """
        pairs = []

        # Ordenar bloques por posición (arriba-abajo, izquierda-derecha)
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))

        used_indices = set()

        for i, block in enumerate(sorted_blocks):
            if i in used_indices:
                continue

            text = block.text.strip()

            # Verificar si es una etiqueta conocida
            normalized_label = None
            original_label = None

            for jp_label, norm_label in JAPANESE_FIELD_MAPPING.items():
                if jp_label in text or text in jp_label:
                    normalized_label = norm_label
                    original_label = jp_label
                    break

            if not normalized_label:
                continue

            # Buscar el valor más cercano
            best_value_block = None
            best_distance = float("inf")

            for j, other in enumerate(sorted_blocks):
                if j == i or j in used_indices:
                    continue

                # El valor debe estar a la derecha o debajo
                dx = other.bbox[0] - (block.bbox[0] + block.bbox[2])
                dy = other.bbox[1] - block.bbox[1]

                # Priorizar bloques a la derecha en la misma línea
                if abs(dy) < block.bbox[3]:  # Misma línea aproximadamente
                    if dx > 0 and dx < 500:  # A la derecha, no muy lejos
                        distance = dx
                        if distance < best_distance:
                            best_distance = distance
                            best_value_block = (j, other)

                # También considerar bloques debajo
                elif dy > 0 and dy < 100 and abs(dx) < 50:
                    distance = dy + abs(dx)
                    if distance < best_distance:
                        best_distance = distance
                        best_value_block = (j, other)

            if best_value_block:
                j, value_block = best_value_block
                used_indices.add(i)
                used_indices.add(j)

                # Normalizar fechas si es un campo de fecha
                value = value_block.text.strip()
                if "fecha" in normalized_label or "expiracion" in normalized_label:
                    parsed_date = JapaneseDateParser.parse(value)
                    if parsed_date:
                        value = parsed_date

                pairs.append(
                    LayoutPair(
                        label=normalized_label,
                        label_japanese=original_label,
                        value=value,
                        confidence=min(block.confidence, value_block.confidence),
                        bbox=value_block.bbox,
                    )
                )

        return pairs


# =============================================================================
# Main OCR Class
# =============================================================================


class JapaneseDocumentOCR:
    """
    Clase principal para OCR de documentos japoneses.

    Uso:
        ocr = JapaneseDocumentOCR(engine="easyocr")
        result = ocr.extract("document.jpg")
    """

    def __init__(
        self, engine: str | OCREngine = OCREngine.EASYOCR, languages: list[str] | None = None
    ):
        """
        Inicializa el OCR.

        Args:
            engine: Motor OCR a usar (easyocr, paddleocr, tesseract)
            languages: Lista de idiomas (default: ['ja', 'en'])
        """
        if isinstance(engine, str):
            engine = OCREngine(engine.lower())

        self.engine_type = engine
        self.languages = languages

        # Inicializar motor
        if engine == OCREngine.EASYOCR:
            self.engine = EasyOCREngine(languages)
        elif engine == OCREngine.PADDLEOCR:
            self.engine = PaddleOCREngine(languages)
        elif engine == OCREngine.TESSERACT:
            self.engine = TesseractEngine(languages)
        else:
            raise ValueError(f"Motor no soportado: {engine}")

        self.preprocessor = ImagePreprocessor()
        self.layout_analyzer = LayoutAnalyzer()

    def extract(
        self,
        image_path: str | None = None,
        image_bytes: bytes | None = None,
        preprocess: bool = True,
        detect_layout: bool = True,
    ) -> OCRResult:
        """
        Extrae texto y datos de un documento.

        Args:
            image_path: Ruta a la imagen
            image_bytes: Bytes de la imagen
            preprocess: Aplicar preprocesamiento
            detect_layout: Detectar pares etiqueta-valor

        Returns:
            OCRResult con texto y layout detectado
        """
        import time

        start_time = time.time()

        warnings = []

        try:
            # Cargar imagen
            img = self.preprocessor.load_image(image_path, image_bytes)

            # Preprocesar si es necesario
            if preprocess:
                img = self.preprocessor.preprocess_for_ocr(img)

            # Ejecutar OCR
            text_blocks = self.engine.extract(img)

            if not text_blocks:
                return OCRResult(success=False, warnings=["No se detectó texto en la imagen"])

            # Detectar tipo de documento
            doc_type = self.layout_analyzer.detect_document_type(text_blocks)

            # Detectar pares etiqueta-valor
            layout_pairs = []
            if detect_layout:
                layout_pairs = self.layout_analyzer.find_label_value_pairs(text_blocks)

            # Texto completo
            raw_text = "\n".join(b.text for b in text_blocks)

            # Advertencias de baja confianza
            low_conf_blocks = [b for b in text_blocks if b.confidence < 0.7]
            if low_conf_blocks:
                warnings.append(f"{len(low_conf_blocks)} bloques con confianza < 70%")

            processing_time = int((time.time() - start_time) * 1000)

            return OCRResult(
                success=True,
                text_blocks=text_blocks,
                layout_pairs=layout_pairs,
                raw_text=raw_text,
                document_type=doc_type,
                warnings=warnings,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Error en OCR: {e}")
            return OCRResult(success=False, warnings=[f"Error en OCR: {str(e)}"])

    def extract_to_dict(
        self,
        image_path: str | None = None,
        image_bytes: bytes | None = None,
        preprocess: bool = True,
    ) -> dict[str, Any]:
        """
        Extrae y retorna como diccionario con campos mapeados.

        Returns:
            Diccionario con campos normalizados
        """
        result = self.extract(image_path, image_bytes, preprocess, detect_layout=True)

        if not result.success:
            return {
                "success": False,
                "error": result.warnings[0] if result.warnings else "Error desconocido",
            }

        # Construir diccionario de campos
        fields = {}
        for pair in result.layout_pairs:
            fields[pair.label] = {
                "value": pair.value,
                "confidence": pair.confidence,
                "original_label": pair.label_japanese,
            }

        return {
            "success": True,
            "document_type": result.document_type.value,
            "fields": fields,
            "raw_text": result.raw_text,
            "warnings": result.warnings,
        }


# =============================================================================
# CLI
# =============================================================================


def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="OCR de documentos japoneses")
    parser.add_argument("image", help="Ruta a la imagen")
    parser.add_argument(
        "--engine",
        choices=["easyocr", "paddleocr", "tesseract"],
        default="easyocr",
        help="Motor OCR a usar",
    )
    parser.add_argument("--no-preprocess", action="store_true", help="Desactivar preprocesamiento")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")

    args = parser.parse_args()

    try:
        ocr = JapaneseDocumentOCR(engine=args.engine)
        result = ocr.extract(image_path=args.image, preprocess=not args.no_preprocess)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"Tipo de documento: {result.document_type.value}")
            print(f"Tiempo de proceso: {result.processing_time_ms}ms")
            print("\n=== Campos detectados ===")
            for pair in result.layout_pairs:
                print(f"  {pair.label_japanese} ({pair.label}): {pair.value}")
                print(f"    Confianza: {pair.confidence:.2%}")
            if result.warnings:
                print("\n=== Advertencias ===")
                for w in result.warnings:
                    print(f"  - {w}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
