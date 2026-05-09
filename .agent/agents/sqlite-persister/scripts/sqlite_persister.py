#!/usr/bin/env python3
"""
SQLite Persister Agent - Almacena datos extraídos en SQLite.

Wrapper del skill sqlite-blob-storage que proporciona una interfaz
de agente para persistencia de documentos con soporte BLOB.

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
sys.path.insert(0, str(SKILLS_PATH / "sqlite-blob-storage" / "scripts"))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SqlitePersisterAgent:
    """Agente especializado en persistencia de datos en bases de datos SQLite."""

    def __init__(self, db_path: str = "documents.db"):
        self.db_path = db_path

    def persist(
        self,
        doc_type: str,
        filename: str,
        fields: dict[str, Any],
        evidence: list[dict] | None = None,
        face_photo_path: str | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persiste un documento."""
        return persist_document(
            self.db_path, doc_type, filename, fields, evidence, face_photo_path, warnings
        )

    def query(self, document_id: int) -> dict[str, Any]:
        """Consulta un documento."""
        return query_document(self.db_path, document_id)


def persist_document(
    db_path: str,
    doc_type: str,
    filename: str,
    fields: dict[str, Any],
    evidence: list[dict] | None = None,
    face_photo_path: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """
    Persiste un documento completo en SQLite.

    Args:
        db_path: Ruta al archivo SQLite
        doc_type: Tipo de documento
        filename: Nombre del archivo origen
        fields: Diccionario de campos extraídos
        evidence: Lista de evidencias
        face_photo_path: Ruta a foto de rostro para guardar como BLOB
        warnings: Advertencias

    Returns:
        Diccionario con resultado
    """
    try:
        from sqlite_blob_storage import SQLiteBlobStorage
    except ImportError as e:
        return {"success": False, "error": f"SQLite module not available: {e}"}

    try:
        # Initialize storage
        storage = SQLiteBlobStorage(db_path)
        storage.init()

        # Insert document
        doc_id = storage.insert_document(
            doc_type=doc_type, source_filename=filename, warnings=warnings
        )

        # Insert fields
        field_ids = {}
        for field_name, field_value in fields.items():
            if field_value is not None:
                # Determine type
                value_type = "string"
                if isinstance(field_value, (int, float)):
                    value_type = "number"
                elif isinstance(field_value, str) and len(field_value) == 10:
                    if field_value[4] == "-" and field_value[7] == "-":
                        value_type = "date"

                field_id = storage.insert_field(
                    document_id=doc_id,
                    field_name=field_name,
                    field_value=str(field_value),
                    value_type=value_type,
                    confidence=1.0,
                )
                field_ids[field_name] = field_id

        # Insert evidence
        if evidence:
            for ev in evidence:
                field_name = ev.get("field")
                if field_name in field_ids:
                    storage.insert_evidence(
                        field_id=field_ids[field_name],
                        source=ev.get("source", "unknown"),
                        location=ev.get("location", ""),
                        raw_text=ev.get("raw", ""),
                        confidence=ev.get("confidence", 1.0),
                    )

        # Insert face photo if provided
        photo_id = None
        if face_photo_path:
            photo_path = Path(face_photo_path)
            if photo_path.exists():
                image_bytes = photo_path.read_bytes()
                mime = "image/png" if photo_path.suffix.lower() == ".png" else "image/jpeg"
                photo_id = storage.insert_face_photo(
                    document_id=doc_id,
                    image_bytes=image_bytes,
                    bbox=None,
                    image_mime=mime,
                    confidence=0.9,
                )

        return {
            "success": True,
            "document_id": doc_id,
            "fields_inserted": len(field_ids),
            "photo_id": photo_id,
            "db_path": str(db_path),
        }

    except Exception as e:
        logger.error(f"Error persistiendo documento: {e}")
        return {"success": False, "error": str(e)}


def query_document(db_path: str, document_id: int) -> dict[str, Any]:
    """
    Recupera un documento de la base de datos.

    Args:
        db_path: Ruta al archivo SQLite
        document_id: ID del documento

    Returns:
        Diccionario con el documento
    """
    try:
        from sqlite_blob_storage import SQLiteBlobStorage
    except ImportError as e:
        return {"success": False, "error": f"SQLite module not available: {e}"}

    try:
        storage = SQLiteBlobStorage(db_path)
        result = storage.export_document_json(document_id)

        if result:
            return {"success": True, **result}
        else:
            return {"success": False, "error": f"Document {document_id} not found"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_statistics(db_path: str) -> dict[str, Any]:
    """Obtiene estadísticas de la base de datos."""
    try:
        from sqlite_blob_storage import SQLiteBlobStorage
    except ImportError as e:
        return {"success": False, "error": f"SQLite module not available: {e}"}

    try:
        storage = SQLiteBlobStorage(db_path)
        storage.init()
        stats = storage.get_statistics()
        return {"success": True, **stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="SQLite Persister Agent - Almacena datos en SQLite"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Insert command
    insert_parser = subparsers.add_parser("insert", help="Insertar documento")
    insert_parser.add_argument("--db", required=True, help="Ruta al archivo SQLite")
    insert_parser.add_argument("--type", required=True, help="Tipo de documento")
    insert_parser.add_argument("--filename", required=True, help="Nombre del archivo origen")
    insert_parser.add_argument("--data", required=True, help="Archivo JSON con campos")
    insert_parser.add_argument("--evidence", help="Archivo JSON con evidencias")
    insert_parser.add_argument("--photo", help="Ruta a foto de rostro")

    # Query command
    query_parser = subparsers.add_parser("query", help="Consultar documento")
    query_parser.add_argument("--db", required=True, help="Ruta al archivo SQLite")
    query_parser.add_argument("--id", type=int, required=True, help="ID del documento")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Estadísticas")
    stats_parser.add_argument("--db", required=True, help="Ruta al archivo SQLite")

    # Init command
    init_parser = subparsers.add_parser("init", help="Inicializar base de datos")
    init_parser.add_argument("--db", required=True, help="Ruta al archivo SQLite")

    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    result = {}

    if args.command == "insert":
        # Load data
        with open(args.data) as f:
            fields = json.load(f)

        evidence = None
        if args.evidence:
            with open(args.evidence) as f:
                evidence = json.load(f)

        result = persist_document(
            db_path=args.db,
            doc_type=args.type,
            filename=args.filename,
            fields=fields,
            evidence=evidence,
            face_photo_path=args.photo,
        )

    elif args.command == "query":
        result = query_document(args.db, args.id)

    elif args.command == "stats":
        result = get_statistics(args.db)

    elif args.command == "init":
        try:
            from sqlite_blob_storage import SQLiteBlobStorage

            storage = SQLiteBlobStorage(args.db)
            storage.init()
            result = {"success": True, "message": f"Database initialized: {args.db}"}
        except Exception as e:
            result = {"success": False, "error": str(e)}

    # Output
    if args.json if hasattr(args, "json") else False:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        if result.get("success"):
            if args.command == "insert":
                print(f"Documento insertado: ID={result['document_id']}")
                print(f"Campos: {result['fields_inserted']}")
                if result.get("photo_id"):
                    print(f"Foto: ID={result['photo_id']}")
            elif args.command == "query":
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            elif args.command == "stats":
                print(f"Documentos: {result.get('documents_by_type', {})}")
                print(f"Campos totales: {result.get('total_fields', 0)}")
                print(f"Evidencias: {result.get('total_evidence', 0)}")
                print(f"Fotos: {result.get('total_face_photos', 0)}")
                print(f"Tamaño DB: {result.get('db_size_bytes', 0)} bytes")
            elif args.command == "init":
                print(result.get("message", "Database initialized"))
        else:
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
