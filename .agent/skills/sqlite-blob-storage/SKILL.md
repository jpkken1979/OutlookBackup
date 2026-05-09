---
name: sqlite-blob-storage
description: "Persistencia de datos en SQLite con soporte completo para BLOBs: almacenamiento de imágenes, gestión de documentos extraídos, evidencias de extracción y fotos de rostros recortadas. Usa prepared statements y validación de tipos para seguridad. Triggers: SQLite BLOB, image storage, document persistence, blob, SQLite database, embedded database."
type: feature
---

# SQLite BLOB Storage Skill

## Metadata
- **Name**: sqlite-blob-storage
- **Version**: 1.0.0
- **Category**: data-persistence
- **Tags**: sqlite, blob, database, storage, images, documents

## Description
Skill especializado en persistencia de datos en SQLite con soporte completo para:
- Almacenamiento de imágenes como BLOB
- Gestión de documentos extraídos
- Evidencias de extracción
- Fotos de rostros recortadas

## Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| db_path | string | Yes | Ruta al archivo SQLite |
| operation | string | Yes | init/insert_document/insert_field/insert_evidence/insert_face_photo/query |
| data | object | Depends | Datos según la operación |

## Outputs
| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Si la operación fue exitosa |
| result | object | Resultado de la operación (ID insertado, datos, etc.) |
| error | string | Mensaje de error si hubo fallo |

## Schema SQLite

```sql
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
```

## Funciones Disponibles

### sqlite_init(db_path)
Inicializa la base de datos y crea las tablas si no existen.

### sqlite_insert_document(doc_type, filename, warnings_json) -> document_id
Inserta un nuevo documento y retorna su ID.

### sqlite_insert_field(document_id, field_name, field_value, value_type, confidence) -> field_id
Inserta un campo extraído y retorna su ID.

### sqlite_insert_evidence(field_id, source, location, raw_text, confidence)
Inserta evidencia de extracción para un campo.

### sqlite_insert_face_photo(document_id, bbox, image_bytes, image_mime, confidence) -> photo_id
Inserta una foto de rostro como BLOB.

### sqlite_get_document(document_id) -> document_data
Recupera un documento con todos sus campos, evidencias y fotos.

### sqlite_search_fields(field_name, value_pattern) -> results
Busca campos por nombre y/o valor.

## Ejemplo de Uso

```python
from sqlite_blob_storage import SQLiteBlobStorage

# Inicializar
db = SQLiteBlobStorage("data.db")
db.init()

# Insertar documento
doc_id = db.insert_document(
    doc_type="zairyucard",
    filename="card_001.jpg",
    warnings=["Low confidence on address field"]
)

# Insertar campo
field_id = db.insert_field(
    document_id=doc_id,
    field_name="nombre",
    field_value="田中 太郎",
    value_type="string",
    confidence=0.95
)

# Insertar evidencia
db.insert_evidence(
    field_id=field_id,
    source="ocr",
    location="page=1 bbox=100,200,300,50",
    raw_text="氏名 田中 太郎",
    confidence=0.95
)

# Insertar foto como BLOB
with open("face_crop.png", "rb") as f:
    photo_bytes = f.read()

db.insert_face_photo(
    document_id=doc_id,
    bbox="150,80,120,150",
    image_bytes=photo_bytes,
    image_mime="image/png",
    confidence=0.98
)
```

## Dependencias
- sqlite3 (built-in Python)
- typing
- dataclasses
- json

## Notas de Seguridad
- Usa prepared statements para prevenir SQL injection
- Valida tipos de datos antes de insertar
- No almacena información sensible en logs
