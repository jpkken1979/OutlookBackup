#!/usr/bin/env python3
"""
Document Data Extraction - Orquestador Principal.

Coordina la extracción completa de datos de:
- Documentos de identidad japoneses (Zairyū Card, pasaporte, licencia)
- Archivos Excel
- Fotos de rostros

Almacena TODO en SQLite incluyendo fotos como BLOB.

Flujo:
1. Clasificar archivos
2. OCR + Layout (documentos)
3. Excel parsing
4. Schema mapping
5. Persistencia SQLite
6. Output final

Version: 1.0.0
"""

from __future__ import annotations

import sys
import json
import logging
import mimetypes
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

# Agregar paths de los otros skills
SKILLS_PATH = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_PATH / "sqlite-blob-storage" / "scripts"))
sys.path.insert(0, str(SKILLS_PATH / "japanese-document-ocr" / "scripts"))
sys.path.insert(0, str(SKILLS_PATH / "face-detection-extraction" / "scripts"))
sys.path.insert(0, str(SKILLS_PATH / "excel-smart-parser" / "scripts"))

# Imports de skills
try:
    from sqlite_blob_storage import SQLiteBlobStorage

    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

try:
    from japanese_document_ocr import JapaneseDocumentOCR, OCREngine

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from face_detection_extraction import FaceDetector, DocumentType as FaceDocType

    FACE_AVAILABLE = True
except ImportError:
    FACE_AVAILABLE = False

try:
    from excel_smart_parser import ExcelSmartParser

    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# Enums y Constantes
# =============================================================================


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


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FieldSchema:
    """Schema de un campo."""

    name: str
    type: str = "string"
    required: bool = False
    aliases: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    """Evidencia de extracción."""

    field: str
    source: str  # ocr, excel, face
    location: str
    raw: str
    confidence: float


@dataclass
class ExtractionResult:
    """Resultado de extracción."""

    document_id: int
    result: dict[str, Any]
    evidence: list[Evidence]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "result": self.result,
            "evidence": [
                {
                    "field": e.field,
                    "source": e.source,
                    "location": e.location,
                    "raw": e.raw,
                    "confidence": e.confidence,
                }
                for e in self.evidence
            ],
            "warnings": self.warnings,
        }


# =============================================================================
# File Classifier
# =============================================================================


class FileClassifier:
    """Clasifica archivos por tipo."""

    @staticmethod
    def classify(file_path: str | Path) -> FileType:
        """Clasifica un archivo por su extensión/mime type."""
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


# =============================================================================
# Schema Mapper
# =============================================================================


class SchemaMapper:
    """Mapea datos extraídos al schema del usuario."""

    def __init__(self, form_schema: dict[str, Any]):
        """
        Inicializa con el schema.

        Args:
            form_schema: Schema de campos
        """
        self.fields = {}
        for name, config in form_schema.items():
            if isinstance(config, dict):
                self.fields[name] = FieldSchema(
                    name=name,
                    type=config.get("type", "string"),
                    required=config.get("required", False),
                    aliases=config.get("aliases", [name]),
                )
            else:
                self.fields[name] = FieldSchema(name=name, aliases=[name])

    def map_fields(self, extracted_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """
        Mapea datos extraídos al schema.

        Args:
            extracted_data: Datos extraídos (label -> value)

        Returns:
            (datos_mapeados, warnings)
        """
        result = {}
        warnings = []

        for field_name, field_schema in self.fields.items():
            value = None

            # Buscar por aliases
            for alias in field_schema.aliases:
                alias_lower = alias.lower()

                for key, val in extracted_data.items():
                    key_lower = key.lower() if isinstance(key, str) else str(key)

                    if alias_lower in key_lower or key_lower in alias_lower:
                        value = val
                        break

                if value is not None:
                    break

            # Validar tipo si es necesario
            if value is not None:
                if field_schema.type == "date":
                    # Verificar formato de fecha
                    if not self._is_valid_date(value):
                        warnings.append(
                            f"Campo '{field_name}' tiene formato de fecha inválido: {value}"
                        )

            # Advertir si campo requerido falta
            if value is None and field_schema.required:
                warnings.append(f"Campo requerido '{field_name}' no encontrado")

            result[field_name] = value

        return result, warnings

    @staticmethod
    def _is_valid_date(value: str) -> bool:
        """Verifica si es una fecha válida."""
        if not isinstance(value, str):
            return False

        import re

        return bool(re.match(r"\d{4}-\d{2}-\d{2}", value))


# =============================================================================
# Document Data Extractor (Orquestador Principal)
# =============================================================================


class DocumentDataExtractor:
    """
    Orquestador principal de extracción de datos.

    Coordina OCR, detección de rostros, parsing de Excel
    y persistencia en SQLite.
    """

    def __init__(self, db_path: str | Path, ocr_engine: str = "easyocr"):
        """
        Inicializa el extractor.

        Args:
            db_path: Ruta al archivo SQLite
            ocr_engine: Motor OCR (easyocr, tesseract, paddleocr)
        """
        self.db_path = Path(db_path)
        self.ocr_engine = ocr_engine

        # Inicializar storage
        if SQLITE_AVAILABLE:
            self.storage = SQLiteBlobStorage(db_path)
            self.storage.init()
        else:
            logger.warning("SQLite storage no disponible")
            self.storage = None

        # Inicializar OCR
        if OCR_AVAILABLE:
            try:
                self.ocr = JapaneseDocumentOCR(engine=ocr_engine)
            except Exception as e:
                logger.warning(f"OCR no disponible: {e}")
                self.ocr = None
        else:
            self.ocr = None

        # Inicializar detector de rostros
        if FACE_AVAILABLE:
            try:
                self.face_detector = FaceDetector()
            except Exception as e:
                logger.warning(f"Detector de rostros no disponible: {e}")
                self.face_detector = None
        else:
            self.face_detector = None

        # Inicializar parser de Excel
        if EXCEL_AVAILABLE:
            try:
                self.excel_parser = ExcelSmartParser()
            except Exception as e:
                logger.warning(f"Parser de Excel no disponible: {e}")
                self.excel_parser = None
        else:
            self.excel_parser = None

        self.classifier = FileClassifier()

    def process(
        self, files: list[str | Path], form_schema: dict[str, Any]
    ) -> list[ExtractionResult]:
        """
        Procesa una lista de archivos.

        Args:
            files: Lista de rutas a archivos
            form_schema: Schema de campos a extraer

        Returns:
            Lista de resultados de extracción
        """
        results = []
        schema_mapper = SchemaMapper(form_schema)

        for file_path in files:
            try:
                result = self._process_file(Path(file_path), form_schema, schema_mapper)
                results.append(result)
            except Exception as e:
                logger.error(f"Error procesando {file_path}: {e}")
                # Crear resultado de error
                results.append(
                    ExtractionResult(
                        document_id=-1,
                        result={},
                        evidence=[],
                        warnings=[f"Error procesando archivo: {str(e)}"],
                    )
                )

        return results

    def _process_file(
        self, file_path: Path, form_schema: dict[str, Any], schema_mapper: SchemaMapper
    ) -> ExtractionResult:
        """Procesa un archivo individual."""
        warnings = []
        evidence = []
        extracted_data = {}

        # Clasificar archivo
        file_type = self.classifier.classify(file_path)
        logger.info(f"Procesando {file_path.name} como {file_type.value}")

        # Determinar tipo de documento
        doc_type = DocumentType.UNKNOWN
        if file_type == FileType.EXCEL:
            doc_type = DocumentType.EXCEL
        elif file_type in (FileType.IMAGE, FileType.PDF):
            # Se determinará después del OCR
            doc_type = DocumentType.UNKNOWN

        # Procesar según tipo de archivo
        if file_type == FileType.EXCEL:
            extracted_data, evidence, warnings = self._process_excel(file_path, form_schema)
        elif file_type in (FileType.IMAGE, FileType.PDF):
            extracted_data, evidence, doc_type, face_data, ocr_warnings = self._process_document(
                file_path
            )
            warnings.extend(ocr_warnings)
        else:
            warnings.append(f"Tipo de archivo no soportado: {file_type.value}")

        # Mapear al schema
        mapped_result, mapping_warnings = schema_mapper.map_fields(extracted_data)
        warnings.extend(mapping_warnings)

        # Persistir en SQLite
        document_id = -1
        if self.storage:
            try:
                # Insertar documento
                document_id = self.storage.insert_document(
                    doc_type=doc_type.value, source_filename=file_path.name, warnings=warnings
                )

                # Insertar campos
                for field_name, field_value in mapped_result.items():
                    if field_value is not None:
                        # Determinar tipo
                        value_type = "string"
                        if isinstance(field_value, (int, float)):
                            value_type = "number"
                        elif self._is_date(field_value):
                            value_type = "date"

                        # Buscar confianza en evidencia
                        confidence = 1.0
                        for ev in evidence:
                            if ev.field == field_name:
                                confidence = ev.confidence
                                break

                        field_id = self.storage.insert_field(
                            document_id=document_id,
                            field_name=field_name,
                            field_value=str(field_value) if field_value else None,
                            value_type=value_type,
                            confidence=confidence,
                        )

                        # Insertar evidencia
                        for ev in evidence:
                            if ev.field == field_name:
                                self.storage.insert_evidence(
                                    field_id=field_id,
                                    source=ev.source,
                                    location=ev.location,
                                    raw_text=ev.raw,
                                    confidence=ev.confidence,
                                )

                # Insertar foto si existe
                if file_type in (FileType.IMAGE, FileType.PDF) and "face_data" in dir():
                    if face_data and face_data.get("image_bytes"):
                        self.storage.insert_face_photo(
                            document_id=document_id,
                            image_bytes=face_data["image_bytes"],
                            bbox=face_data.get("bbox"),
                            image_mime=face_data.get("mime", "image/png"),
                            confidence=face_data.get("confidence", 0.9),
                        )

            except Exception as e:
                logger.error(f"Error persistiendo en SQLite: {e}")
                warnings.append(f"Error guardando en base de datos: {str(e)}")

        return ExtractionResult(
            document_id=document_id, result=mapped_result, evidence=evidence, warnings=warnings
        )

    def _process_document(
        self, file_path: Path
    ) -> tuple[dict, list[Evidence], DocumentType, dict | None, list[str]]:
        """
        Procesa un documento de identidad (imagen/PDF).

        Returns:
            (datos_extraidos, evidencias, tipo_documento, datos_foto, warnings)
        """
        extracted_data = {}
        evidence = []
        warnings = []
        doc_type = DocumentType.UNKNOWN
        face_data = None

        # OCR
        if self.ocr:
            try:
                ocr_result = self.ocr.extract(image_path=str(file_path))

                if ocr_result.success:
                    # Obtener tipo de documento
                    if ocr_result.document_type:
                        doc_type = DocumentType(ocr_result.document_type.value)

                    # Extraer pares etiqueta-valor
                    for pair in ocr_result.layout_pairs:
                        extracted_data[pair.label] = pair.value

                        evidence.append(
                            Evidence(
                                field=pair.label,
                                source="ocr",
                                location=f"page=1 bbox={pair.bbox}" if pair.bbox else "page=1",
                                raw=f"{pair.label_japanese}: {pair.value}",
                                confidence=pair.confidence,
                            )
                        )

                    warnings.extend(ocr_result.warnings)
                else:
                    warnings.extend(ocr_result.warnings)

            except Exception as e:
                logger.error(f"Error en OCR: {e}")
                warnings.append(f"Error en OCR: {str(e)}")
        else:
            warnings.append("OCR no disponible")

        # Detección de rostro
        if self.face_detector:
            try:
                # Mapear tipo de documento para el detector
                face_doc_type = FaceDocType.GENERIC
                if doc_type == DocumentType.ZAIRYUCARD:
                    face_doc_type = FaceDocType.ZAIRYUCARD
                elif doc_type == DocumentType.PASSPORT:
                    face_doc_type = FaceDocType.PASSPORT
                elif doc_type == DocumentType.LICENSE:
                    face_doc_type = FaceDocType.LICENSE

                face_result = self.face_detector.detect_and_extract(
                    image_path=str(file_path), document_type=face_doc_type
                )

                if face_result.success and face_result.faces:
                    best_face = face_result.faces[0]
                    face_data = {
                        "image_bytes": best_face.image_bytes,
                        "bbox": f"{best_face.bbox[0]},{best_face.bbox[1]},{best_face.bbox[2]},{best_face.bbox[3]}",
                        "mime": best_face.image_mime,
                        "confidence": best_face.confidence,
                    }

                    evidence.append(
                        Evidence(
                            field="foto_rostro",
                            source="face",
                            location=f"bbox={face_data['bbox']}",
                            raw="[imagen binaria]",
                            confidence=best_face.confidence,
                        )
                    )

                warnings.extend(face_result.warnings)

            except Exception as e:
                logger.error(f"Error en detección de rostro: {e}")
                warnings.append(f"Error detectando rostro: {str(e)}")
        else:
            warnings.append("Detector de rostros no disponible")

        return extracted_data, evidence, doc_type, face_data, warnings

    def _process_excel(
        self, file_path: Path, form_schema: dict[str, Any]
    ) -> tuple[dict, list[Evidence], list[str]]:
        """
        Procesa un archivo Excel.

        Returns:
            (datos_extraidos, evidencias, warnings)
        """
        extracted_data = {}
        evidence = []
        warnings = []

        if not self.excel_parser:
            warnings.append("Parser de Excel no disponible")
            return extracted_data, evidence, warnings

        try:
            parse_result = self.excel_parser.parse(
                file_path=str(file_path), form_schema=form_schema
            )

            if parse_result.success:
                # Extraer campos
                for ef in parse_result.extracted_fields:
                    extracted_data[ef.field_name] = ef.value

                    evidence.append(
                        Evidence(
                            field=ef.field_name,
                            source="excel",
                            location=ef.location,
                            raw=ef.raw_value,
                            confidence=ef.confidence,
                        )
                    )

                # Si no se extrajeron campos con el schema,
                # intentar extraer de las tablas directamente
                if not extracted_data and parse_result.tables:
                    for table in parse_result.tables:
                        for header in table.headers:
                            # Buscar primera fila con valor
                            for _row_idx, row in enumerate(table.rows):
                                col_idx = table.headers.index(header)
                                if col_idx < len(row) and row[col_idx] is not None:
                                    extracted_data[header] = row[col_idx]
                                    break

                warnings.extend(parse_result.warnings)
            else:
                warnings.extend(parse_result.warnings)

        except Exception as e:
            logger.error(f"Error parseando Excel: {e}")
            warnings.append(f"Error parseando Excel: {str(e)}")

        return extracted_data, evidence, warnings

    @staticmethod
    def _is_date(value: Any) -> bool:
        """Verifica si un valor parece ser una fecha."""
        if not isinstance(value, str):
            return False
        import re

        return bool(re.match(r"\d{4}-\d{2}-\d{2}", value))


# =============================================================================
# Convenience Functions (API del Super-Prompt)
# =============================================================================


def extract_document_data(
    files: list[str], form_schema: dict[str, Any], db_path: str
) -> list[dict[str, Any]]:
    """
    Función principal de extracción según el super-prompt.

    Args:
        files: Lista de rutas a archivos
        form_schema: Schema de campos a extraer
        db_path: Ruta al archivo SQLite

    Returns:
        Lista de resultados de extracción
    """
    extractor = DocumentDataExtractor(db_path=db_path)
    results = extractor.process(files=files, form_schema=form_schema)
    return [r.to_dict() for r in results]


# =============================================================================
# CLI
# =============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extractor de datos de documentos e IDs japoneses")
    parser.add_argument("files", nargs="+", help="Archivos a procesar (imágenes, PDF, Excel)")
    parser.add_argument(
        "--db", default="documents.db", help="Ruta al archivo SQLite (default: documents.db)"
    )
    parser.add_argument("--schema", help="Archivo JSON con schema de campos")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")

    args = parser.parse_args()

    # Schema por defecto para Zairyū Card
    default_schema = {
        "nombre": {"type": "string", "required": True, "aliases": ["氏名", "NAME", "名前"]},
        "fecha_nacimiento": {
            "type": "date",
            "required": True,
            "aliases": ["生年月日", "DATE OF BIRTH", "DOB"],
        },
        "genero": {"type": "string", "aliases": ["性別", "SEX"]},
        "nacionalidad": {"type": "string", "aliases": ["国籍・地域", "国籍", "NATIONALITY"]},
        "direccion": {"type": "string", "aliases": ["住居地", "住所", "ADDRESS"]},
        "estado_residencia": {"type": "string", "aliases": ["在留資格", "STATUS OF RESIDENCE"]},
        "periodo_estancia": {"type": "string", "aliases": ["在留期間", "PERIOD OF STAY"]},
        "numero_tarjeta": {
            "type": "string",
            "aliases": ["在留カード番号", "RESIDENCE CARD NUMBER"],
        },
        "fecha_expiracion": {"type": "date", "aliases": ["有効期限", "DATE OF EXPIRY"]},
    }

    # Cargar schema personalizado si existe
    form_schema = default_schema
    if args.schema:
        try:
            with open(args.schema) as f:
                form_schema = json.load(f)
        except Exception as e:
            print(f"Error cargando schema: {e}", file=sys.stderr)
            sys.exit(1)

    # Procesar
    try:
        extractor = DocumentDataExtractor(db_path=args.db)
        results = extractor.process(files=args.files, form_schema=form_schema)

        if args.json:
            output = [r.to_dict() for r in results]
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            for i, result in enumerate(results):
                print(f"\n{'=' * 50}")
                print(f"Archivo #{i + 1}: {args.files[i]}")
                print(f"{'=' * 50}")
                print(f"Document ID: {result.document_id}")
                print("\n--- Datos extraídos ---")
                for field, value in result.result.items():
                    print(f"  {field}: {value}")

                if result.evidence:
                    print("\n--- Evidencias ---")
                    for ev in result.evidence:
                        print(f"  [{ev.source}] {ev.field}: {ev.location}")

                if result.warnings:
                    print("\n--- Advertencias ---")
                    for w in result.warnings:
                        print(f"  - {w}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
