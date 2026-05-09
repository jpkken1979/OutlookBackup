#!/usr/bin/env python3
"""
Document Processor Agent - Clasifica y preprocesa documentos.

Determina el tipo de documento (Zairyū Card, pasaporte, licencia, Excel)
y prepara el archivo para procesamiento downstream.

Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class FileType(str, Enum):
    """Tipos de archivo soportados."""

    IMAGE = "image"
    PDF = "pdf"
    EXCEL = "excel"
    UNKNOWN = "unknown"


class DocumentType(str, Enum):
    """Tipos de documentos de identidad."""

    ZAIRYUCARD = "zairyucard"
    PASSPORT = "passport"
    LICENSE = "license"
    MYNUMBER = "mynumber"
    EXCEL = "excel"
    UNKNOWN = "unknown"


# Extensiones de archivo
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
PDF_EXTENSIONS = {".pdf"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}


@dataclass
class ClassificationResult:
    """Resultado de la clasificación."""

    file_path: str
    file_type: FileType
    document_type: DocumentType
    confidence: float
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type.value,
            "document_type": self.document_type.value,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


class DocumentProcessor:
    """Procesador de documentos - clasifica y preprocesa."""

    def __init__(self):
        self.supported_extensions = IMAGE_EXTENSIONS | PDF_EXTENSIONS | EXCEL_EXTENSIONS

    def classify_file(self, file_path: str) -> FileType:
        """Clasifica un archivo por su extensión."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            return FileType.IMAGE
        elif ext in PDF_EXTENSIONS:
            return FileType.PDF
        elif ext in EXCEL_EXTENSIONS:
            return FileType.EXCEL

        # Fallback a mime type
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            if mime_type.startswith("image/"):
                return FileType.IMAGE
            elif mime_type == "application/pdf":
                return FileType.PDF
            elif "spreadsheet" in mime_type or "excel" in mime_type:
                return FileType.EXCEL

        return FileType.UNKNOWN

    def detect_document_type(
        self, file_path: str, file_type: FileType
    ) -> tuple[DocumentType, float]:
        """
        Detecta el tipo de documento basándose en el contenido.

        Para una implementación completa, esto usaría OCR para detectar
        el tipo basándose en el texto detectado.

        Returns:
            (tipo_documento, confianza)
        """
        if file_type == FileType.EXCEL:
            return DocumentType.EXCEL, 1.0

        # Para imágenes/PDFs, se necesitaría OCR para determinar el tipo exacto
        # Por ahora, retornamos UNKNOWN con indicación de que necesita OCR
        if file_type in (FileType.IMAGE, FileType.PDF):
            # Heurística básica por nombre de archivo
            filename = Path(file_path).name.lower()

            if any(x in filename for x in ["zairyu", "residence", "在留"]):
                return DocumentType.ZAIRYUCARD, 0.7
            elif any(x in filename for x in ["passport", "旅券", "パスポート"]):
                return DocumentType.PASSPORT, 0.7
            elif any(x in filename for x in ["license", "免許", "driver"]):
                return DocumentType.LICENSE, 0.7
            elif any(x in filename for x in ["mynumber", "マイナンバー", "個人番号"]):
                return DocumentType.MYNUMBER, 0.7

            return DocumentType.UNKNOWN, 0.5

        return DocumentType.UNKNOWN, 0.0

    def process(self, file_path: str) -> ClassificationResult:
        """
        Procesa y clasifica un documento.

        Args:
            file_path: Ruta al archivo

        Returns:
            ClassificationResult con la clasificación
        """
        warnings = []
        path = Path(file_path)

        # Verificar que el archivo existe
        if not path.exists():
            return ClassificationResult(
                file_path=file_path,
                file_type=FileType.UNKNOWN,
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                warnings=[f"Archivo no encontrado: {file_path}"],
            )

        # Clasificar tipo de archivo
        file_type = self.classify_file(file_path)

        if file_type == FileType.UNKNOWN:
            warnings.append(f"Tipo de archivo no reconocido: {path.suffix}")

        # Detectar tipo de documento
        doc_type, confidence = self.detect_document_type(file_path, file_type)

        if doc_type == DocumentType.UNKNOWN and file_type in (FileType.IMAGE, FileType.PDF):
            warnings.append(
                "Tipo de documento no determinado - requiere OCR para clasificación precisa"
            )

        return ClassificationResult(
            file_path=file_path,
            file_type=file_type,
            document_type=doc_type,
            confidence=confidence,
            warnings=warnings,
        )

    def process_batch(self, file_paths: list[str]) -> list[ClassificationResult]:
        """Procesa múltiples archivos."""
        return [self.process(fp) for fp in file_paths]


def main():
    parser = argparse.ArgumentParser(
        description="Document Processor Agent - Clasifica y preprocesa documentos"
    )
    parser.add_argument("files", nargs="+", help="Archivos a procesar")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")

    args = parser.parse_args()

    processor = DocumentProcessor()
    results = processor.process_batch(args.files)

    if args.json:
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for result in results:
            print(f"\n{'=' * 50}")
            print(f"Archivo: {result.file_path}")
            print(f"Tipo de archivo: {result.file_type.value}")
            print(f"Tipo de documento: {result.document_type.value}")
            print(f"Confianza: {result.confidence:.0%}")
            if result.warnings:
                print("Advertencias:")
                for w in result.warnings:
                    print(f"  - {w}")


if __name__ == "__main__":
    main()
