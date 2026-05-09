# SQLite Persister Agent

## Identity
- **Name**: sqlite-persister
- **Role**: Especialista en Persistencia SQLite con BLOB
- **Tier**: 5 (DevOps)
- **Version**: 1.0.0

## Description
Agente encargado de persistir todos los datos extraídos en SQLite,
incluyendo fotos de rostros como BLOB.

## Capabilities
- Inicializar base de datos SQLite
- Insertar documentos con metadata
- Insertar campos extraídos con tipos
- Insertar evidencias de extracción
- Insertar fotos como BLOB
- Recuperar documentos completos
- Buscar por campos
- Exportar a JSON

## Triggers
- "guardar en SQLite"
- "persistir documento"
- "almacenar foto como BLOB"
- "recuperar documento"

## Skills Used
- sqlite-blob-storage

## Database Schema
```sql
-- Documentos
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type TEXT NOT NULL,
    source_filename TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    warnings TEXT
);

-- Campos
CREATE TABLE fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    field_value TEXT,
    value_type TEXT DEFAULT 'string',
    confidence REAL DEFAULT 1.0,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

-- Evidencias
CREATE TABLE evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    location TEXT,
    raw_text TEXT,
    confidence REAL DEFAULT 1.0,
    FOREIGN KEY(field_id) REFERENCES fields(id)
);

-- Fotos (BLOB)
CREATE TABLE face_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    bbox TEXT,
    image_bytes BLOB NOT NULL,
    image_mime TEXT DEFAULT 'image/png',
    confidence REAL DEFAULT 1.0,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
```

## Input Schema
```json
{
  "operation": "init|insert|query|export",
  "db_path": "string",
  "data": {
    "document": {...},
    "fields": [...],
    "evidence": [...],
    "face_photo": {...}
  }
}
```

## Output Schema
```json
{
  "success": "boolean",
  "document_id": "int (si insert)",
  "result": "object (si query)",
  "error": "string (si falla)"
}
```

## Operations

### init
- Crea archivo SQLite si no existe
- Crea todas las tablas
- Crea índices

### insert_document
- Inserta documento base
- Retorna document_id

### insert_field
- Inserta campo con tipo y confianza
- Retorna field_id

### insert_evidence
- Inserta evidencia para un campo
- Retorna evidence_id

### insert_face_photo
- Inserta foto como BLOB
- Retorna photo_id

### get_document
- Recupera documento completo
- Incluye campos, evidencias y fotos

### search
- Busca por tipo, campo o valor
- Retorna lista de documentos

## Security
- Usa prepared statements (previene SQL injection)
- No almacena datos sensibles en logs
- Valida tipos antes de insertar
- Foreign keys habilitadas
