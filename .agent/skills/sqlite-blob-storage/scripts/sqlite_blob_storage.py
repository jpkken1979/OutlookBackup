#!/usr/bin/env python3
"""
SQLite BLOB Storage - Persistencia de documentos con soporte BLOB.

Permite almacenar:
- Documentos extraídos (IDs, Excel)
- Campos con tipos y confianza
- Evidencias de extracción
- Fotos de rostros como BLOB

Version: 1.0.0
"""

import sqlite3
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Document:
    """Representa un documento almacenado."""

    id: int
    doc_type: str
    source_filename: str | None
    created_at: str
    warnings: str | None
    fields: list["Field"] = field(default_factory=list)
    face_photos: list["FacePhoto"] = field(default_factory=list)


@dataclass
class Field:
    """Campo extraído de un documento."""

    id: int
    document_id: int
    field_name: str
    field_value: str | None
    value_type: str = "string"
    confidence: float = 1.0
    evidence: list["Evidence"] = field(default_factory=list)


@dataclass
class Evidence:
    """Evidencia de extracción de un campo."""

    id: int
    field_id: int
    source: str  # ocr, excel, face
    location: str | None  # page/bbox or sheet/cell
    raw_text: str | None
    confidence: float = 1.0


@dataclass
class FacePhoto:
    """Foto de rostro almacenada como BLOB."""

    id: int
    document_id: int
    bbox: str | None
    image_bytes: bytes
    image_mime: str = "image/png"
    confidence: float = 1.0


# =============================================================================
# SQLite BLOB Storage Class
# =============================================================================


class SQLiteBlobStorage:
    """
    Gestiona persistencia en SQLite con soporte BLOB.

    Uso:
        db = SQLiteBlobStorage("data.db")
        db.init()
        doc_id = db.insert_document("zairyucard", "card.jpg")
    """

    SCHEMA = """
    -- Tabla principal de documentos
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_type TEXT NOT NULL,
        source_filename TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        warnings TEXT
    );

    -- Campos extraídos
    CREATE TABLE IF NOT EXISTS fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        field_name TEXT NOT NULL,
        field_value TEXT,
        value_type TEXT DEFAULT 'string',
        confidence REAL DEFAULT 1.0,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );

    -- Evidencias de extracción
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        location TEXT,
        raw_text TEXT,
        confidence REAL DEFAULT 1.0,
        FOREIGN KEY(field_id) REFERENCES fields(id) ON DELETE CASCADE
    );

    -- Fotos de rostros (BLOB)
    CREATE TABLE IF NOT EXISTS face_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        bbox TEXT,
        image_bytes BLOB NOT NULL,
        image_mime TEXT DEFAULT 'image/png',
        confidence REAL DEFAULT 1.0,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );

    -- Índices para búsquedas rápidas
    CREATE INDEX IF NOT EXISTS idx_fields_document ON fields(document_id);
    CREATE INDEX IF NOT EXISTS idx_fields_name ON fields(field_name);
    CREATE INDEX IF NOT EXISTS idx_evidence_field ON evidence(field_id);
    CREATE INDEX IF NOT EXISTS idx_face_photos_document ON face_photos(document_id);
    """

    def __init__(self, db_path: str | Path):
        """
        Inicializa el storage.

        Args:
            db_path: Ruta al archivo SQLite
        """
        self.db_path = Path(db_path)
        self._connection: sqlite3.Connection | None = None

    @contextmanager
    def _get_connection(self):
        """Context manager para conexiones."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init(self) -> bool:
        """
        Inicializa la base de datos creando las tablas.

        Returns:
            True si se inicializó correctamente
        """
        try:
            # Crear directorio si no existe
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with self._get_connection() as conn:
                conn.executescript(self.SCHEMA)
                logger.info(f"Base de datos inicializada: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Error inicializando DB: {e}")
            raise

    # =========================================================================
    # Document Operations
    # =========================================================================

    def insert_document(
        self, doc_type: str, source_filename: str | None = None, warnings: list[str] | None = None
    ) -> int:
        """
        Inserta un nuevo documento.

        Args:
            doc_type: Tipo de documento (zairyucard, license, passport, excel)
            source_filename: Nombre del archivo origen
            warnings: Lista de advertencias

        Returns:
            ID del documento insertado
        """
        warnings_json = json.dumps(warnings, ensure_ascii=False) if warnings else None

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (doc_type, source_filename, warnings)
                VALUES (?, ?, ?)
                """,
                (doc_type, source_filename, warnings_json),
            )
            doc_id = cursor.lastrowid
            logger.info(f"Documento insertado: ID={doc_id}, tipo={doc_type}")
            return doc_id

    def get_document(self, document_id: int) -> Document | None:
        """
        Recupera un documento completo con campos, evidencias y fotos.

        Args:
            document_id: ID del documento

        Returns:
            Document con todos sus datos o None
        """
        with self._get_connection() as conn:
            # Obtener documento
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()

            if not row:
                return None

            doc = Document(
                id=row["id"],
                doc_type=row["doc_type"],
                source_filename=row["source_filename"],
                created_at=row["created_at"],
                warnings=row["warnings"],
                fields=[],
                face_photos=[],
            )

            # Obtener campos
            field_rows = conn.execute(
                "SELECT * FROM fields WHERE document_id = ?", (document_id,)
            ).fetchall()

            for fr in field_rows:
                f = Field(
                    id=fr["id"],
                    document_id=fr["document_id"],
                    field_name=fr["field_name"],
                    field_value=fr["field_value"],
                    value_type=fr["value_type"],
                    confidence=fr["confidence"],
                    evidence=[],
                )

                # Obtener evidencias del campo
                ev_rows = conn.execute(
                    "SELECT * FROM evidence WHERE field_id = ?", (f.id,)
                ).fetchall()

                for er in ev_rows:
                    f.evidence.append(
                        Evidence(
                            id=er["id"],
                            field_id=er["field_id"],
                            source=er["source"],
                            location=er["location"],
                            raw_text=er["raw_text"],
                            confidence=er["confidence"],
                        )
                    )

                doc.fields.append(f)

            # Obtener fotos
            photo_rows = conn.execute(
                "SELECT * FROM face_photos WHERE document_id = ?", (document_id,)
            ).fetchall()

            for pr in photo_rows:
                doc.face_photos.append(
                    FacePhoto(
                        id=pr["id"],
                        document_id=pr["document_id"],
                        bbox=pr["bbox"],
                        image_bytes=pr["image_bytes"],
                        image_mime=pr["image_mime"],
                        confidence=pr["confidence"],
                    )
                )

            return doc

    def update_document_warnings(self, document_id: int, warnings: list[str]) -> bool:
        """Actualiza las advertencias de un documento."""
        warnings_json = json.dumps(warnings, ensure_ascii=False)

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET warnings = ? WHERE id = ?", (warnings_json, document_id)
            )
            return True

    # =========================================================================
    # Field Operations
    # =========================================================================

    def insert_field(
        self,
        document_id: int,
        field_name: str,
        field_value: str | None,
        value_type: str = "string",
        confidence: float = 1.0,
    ) -> int:
        """
        Inserta un campo extraído.

        Args:
            document_id: ID del documento padre
            field_name: Nombre del campo (ej: "nombre", "fecha_nacimiento")
            field_value: Valor extraído
            value_type: Tipo (string, date, number, boolean)
            confidence: Confianza de la extracción (0.0-1.0)

        Returns:
            ID del campo insertado
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO fields (document_id, field_name, field_value, value_type, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, field_name, field_value, value_type, confidence),
            )
            field_id = cursor.lastrowid
            logger.debug(f"Campo insertado: {field_name}={field_value}")
            return field_id

    def get_fields_by_document(self, document_id: int) -> list[Field]:
        """Obtiene todos los campos de un documento."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM fields WHERE document_id = ?", (document_id,)
            ).fetchall()

            return [
                Field(
                    id=r["id"],
                    document_id=r["document_id"],
                    field_name=r["field_name"],
                    field_value=r["field_value"],
                    value_type=r["value_type"],
                    confidence=r["confidence"],
                )
                for r in rows
            ]

    # =========================================================================
    # Evidence Operations
    # =========================================================================

    def insert_evidence(
        self,
        field_id: int,
        source: str,
        location: str | None = None,
        raw_text: str | None = None,
        confidence: float = 1.0,
    ) -> int:
        """
        Inserta evidencia de extracción.

        Args:
            field_id: ID del campo al que pertenece
            source: Fuente (ocr, excel, face)
            location: Ubicación (page=1 bbox=x,y,w,h OR Sheet1!A1)
            raw_text: Texto original detectado
            confidence: Confianza de la extracción

        Returns:
            ID de la evidencia insertada
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO evidence (field_id, source, location, raw_text, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (field_id, source, location, raw_text, confidence),
            )
            return cursor.lastrowid

    # =========================================================================
    # Face Photo Operations (BLOB)
    # =========================================================================

    def insert_face_photo(
        self,
        document_id: int,
        image_bytes: bytes,
        bbox: str | None = None,
        image_mime: str = "image/png",
        confidence: float = 1.0,
    ) -> int:
        """
        Inserta una foto de rostro como BLOB.

        Args:
            document_id: ID del documento padre
            image_bytes: Bytes de la imagen (PNG/JPEG)
            bbox: Bounding box original "x,y,w,h"
            image_mime: Tipo MIME (image/png, image/jpeg)
            confidence: Confianza de la detección

        Returns:
            ID de la foto insertada
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO face_photos (document_id, bbox, image_bytes, image_mime, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, bbox, image_bytes, image_mime, confidence),
            )
            photo_id = cursor.lastrowid
            logger.info(f"Foto insertada: ID={photo_id}, size={len(image_bytes)} bytes")
            return photo_id

    def get_face_photo(self, photo_id: int) -> FacePhoto | None:
        """Recupera una foto de rostro por ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM face_photos WHERE id = ?", (photo_id,)).fetchone()

            if not row:
                return None

            return FacePhoto(
                id=row["id"],
                document_id=row["document_id"],
                bbox=row["bbox"],
                image_bytes=row["image_bytes"],
                image_mime=row["image_mime"],
                confidence=row["confidence"],
            )

    def get_face_photos_by_document(self, document_id: int) -> list[FacePhoto]:
        """Obtiene todas las fotos de un documento."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM face_photos WHERE document_id = ?", (document_id,)
            ).fetchall()

            return [
                FacePhoto(
                    id=r["id"],
                    document_id=r["document_id"],
                    bbox=r["bbox"],
                    image_bytes=r["image_bytes"],
                    image_mime=r["image_mime"],
                    confidence=r["confidence"],
                )
                for r in rows
            ]

    def save_face_photo_to_file(self, photo_id: int, output_path: str | Path) -> bool:
        """Guarda una foto de la DB a un archivo."""
        photo = self.get_face_photo(photo_id)
        if not photo:
            return False

        output_path = Path(output_path)
        output_path.write_bytes(photo.image_bytes)
        return True

    # =========================================================================
    # Search Operations
    # =========================================================================

    def search_documents(
        self,
        doc_type: str | None = None,
        field_name: str | None = None,
        field_value: str | None = None,
        limit: int = 100,
    ) -> list[Document]:
        """
        Busca documentos por criterios.

        Args:
            doc_type: Filtrar por tipo de documento
            field_name: Filtrar por nombre de campo
            field_value: Filtrar por valor (LIKE pattern)
            limit: Máximo de resultados

        Returns:
            Lista de documentos que coinciden
        """
        with self._get_connection() as conn:
            query = "SELECT DISTINCT d.id FROM documents d"
            params = []

            if field_name or field_value:
                query += " JOIN fields f ON d.id = f.document_id"

            conditions = []

            if doc_type:
                conditions.append("d.doc_type = ?")
                params.append(doc_type)

            if field_name:
                conditions.append("f.field_name = ?")
                params.append(field_name)

            if field_value:
                conditions.append("f.field_value LIKE ?")
                params.append(f"%{field_value}%")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += f" LIMIT {limit}"

            rows = conn.execute(query, params).fetchall()

            documents = []
            for row in rows:
                doc = self.get_document(row["id"])
                if doc:
                    documents.append(doc)

            return documents

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas de la base de datos."""
        with self._get_connection() as conn:
            stats = {}

            # Conteo de documentos por tipo
            rows = conn.execute(
                "SELECT doc_type, COUNT(*) as count FROM documents GROUP BY doc_type"
            ).fetchall()
            stats["documents_by_type"] = {r["doc_type"]: r["count"] for r in rows}

            # Total de campos
            row = conn.execute("SELECT COUNT(*) as count FROM fields").fetchone()
            stats["total_fields"] = row["count"]

            # Total de evidencias
            row = conn.execute("SELECT COUNT(*) as count FROM evidence").fetchone()
            stats["total_evidence"] = row["count"]

            # Total de fotos
            row = conn.execute("SELECT COUNT(*) as count FROM face_photos").fetchone()
            stats["total_face_photos"] = row["count"]

            # Tamaño de la DB
            stats["db_size_bytes"] = self.db_path.stat().st_size if self.db_path.exists() else 0

            return stats

    def export_document_json(self, document_id: int) -> dict[str, Any] | None:
        """
        Exporta un documento completo a JSON (sin los bytes de las fotos).

        Las fotos se representan como metadata sin los bytes.
        """
        doc = self.get_document(document_id)
        if not doc:
            return None

        return {
            "document_id": doc.id,
            "doc_type": doc.doc_type,
            "source_filename": doc.source_filename,
            "created_at": doc.created_at,
            "warnings": json.loads(doc.warnings) if doc.warnings else [],
            "result": {f.field_name: f.field_value for f in doc.fields},
            "evidence": [
                {
                    "field": f.field_name,
                    "source": e.source,
                    "location": e.location,
                    "raw": e.raw_text,
                    "confidence": e.confidence,
                }
                for f in doc.fields
                for e in f.evidence
            ],
            "face_photos": [
                {
                    "photo_id": p.id,
                    "bbox": p.bbox,
                    "mime": p.image_mime,
                    "size_bytes": len(p.image_bytes),
                    "confidence": p.confidence,
                }
                for p in doc.face_photos
            ],
        }


# =============================================================================
# Convenience Functions (API del Super-Prompt)
# =============================================================================

_default_storage: SQLiteBlobStorage | None = None


def sqlite_init(db_path: str) -> SQLiteBlobStorage:
    """Inicializa la base de datos SQLite."""
    global _default_storage
    _default_storage = SQLiteBlobStorage(db_path)
    _default_storage.init()
    return _default_storage


def sqlite_insert_document(doc_type: str, filename: str, warnings_json: str | None = None) -> int:
    """Inserta un documento y retorna su ID."""
    if not _default_storage:
        raise RuntimeError("Debe llamar sqlite_init() primero")

    warnings = json.loads(warnings_json) if warnings_json else None
    return _default_storage.insert_document(doc_type, filename, warnings)


def sqlite_insert_field(
    document_id: int,
    field_name: str,
    field_value: str | None,
    value_type: str = "string",
    confidence: float = 1.0,
) -> int:
    """Inserta un campo y retorna su ID."""
    if not _default_storage:
        raise RuntimeError("Debe llamar sqlite_init() primero")

    return _default_storage.insert_field(
        document_id, field_name, field_value, value_type, confidence
    )


def sqlite_insert_evidence(
    field_id: int, source: str, location: str, raw_text: str, confidence: float = 1.0
) -> int:
    """Inserta evidencia para un campo."""
    if not _default_storage:
        raise RuntimeError("Debe llamar sqlite_init() primero")

    return _default_storage.insert_evidence(field_id, source, location, raw_text, confidence)


def sqlite_insert_face_photo(
    document_id: int,
    bbox: str,
    image_bytes: bytes,
    image_mime: str = "image/png",
    confidence: float = 1.0,
) -> int:
    """Inserta una foto de rostro como BLOB."""
    if not _default_storage:
        raise RuntimeError("Debe llamar sqlite_init() primero")

    return _default_storage.insert_face_photo(
        document_id, image_bytes, bbox, image_mime, confidence
    )


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python sqlite_blob_storage.py <db_path> [comando]")
        print("Comandos: init, stats, export <doc_id>")
        sys.exit(1)

    db_path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "init"

    storage = SQLiteBlobStorage(db_path)

    if command == "init":
        storage.init()
        print(f"Base de datos inicializada: {db_path}")

    elif command == "stats":
        storage.init()
        stats = storage.get_statistics()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif command == "export" and len(sys.argv) > 3:
        storage.init()
        doc_id = int(sys.argv[3])
        result = storage.export_document_json(doc_id)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Documento {doc_id} no encontrado")

    else:
        print(f"Comando desconocido: {command}")
