---
name: document-data-extraction
description: Skill orquestador principal que coordina la extracción completa de datos de documentos de identidad, archivos Excel y fotos de rostros
type: feature
---

# Document Data Extraction Skill (Orquestador Principal)

## Metadata
- **Name**: document-data-extraction
- **Version**: 1.0.0
- **Category**: orchestration, document-processing
- **Tags**: ocr, excel, sqlite, extraction, japanese, id-card, zairyucard

## Description
Skill orquestador principal que coordina la extracción completa de datos de:
- Documentos de identidad japoneses (Zairyū Card, pasaporte, licencia)
- Archivos Excel con cualquier estructura
- Fotos de rostros en documentos

Almacena TODO en SQLite incluyendo fotos como BLOB.

## Flujo de Procesamiento

```
Paso 0: Leer FORM_SCHEMA
   ↓
Paso 1: Clasificar archivo (imagen/PDF/Excel)
   ↓
Paso 2 (Documentos ID):
   2.1 Preprocesar imagen
   2.2 OCR japonés + layout
   2.3 Detectar y recortar foto/rostro
   ↓
Paso 3 (Excel):
   3.1 Detectar hojas y tablas
   3.2 Extraer campos según schema
   ↓
Paso 4: Schema Mapper
   4.1 Mapear campos extraídos al FORM_SCHEMA
   4.2 Validar tipos y formatos
   ↓
Paso 5: Persistencia SQLite
   5.1 Insertar documento
   5.2 Insertar campos
   5.3 Insertar evidencias
   5.4 Insertar foto como BLOB
   ↓
Paso 6: Output final
```

## Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| files | list | Yes | Lista de rutas a archivos |
| form_schema | dict | Yes | Schema de campos a extraer |
| db_path | string | Yes | Ruta al archivo SQLite |

## FORM_SCHEMA Ejemplo

```json
{
  "nombre": {
    "type": "string",
    "required": true,
    "aliases": ["氏名", "NAME", "名前"]
  },
  "fecha_nacimiento": {
    "type": "date",
    "required": true,
    "aliases": ["生年月日", "DATE OF BIRTH", "DOB"]
  },
  "direccion": {
    "type": "string",
    "required": false,
    "aliases": ["住居地", "ADDRESS", "住所"]
  },
  "numero_tarjeta": {
    "type": "string",
    "required": true,
    "aliases": ["在留カード番号", "RESIDENCE CARD NUMBER"]
  },
  "nacionalidad": {
    "type": "string",
    "required": false,
    "aliases": ["国籍・地域", "NATIONALITY"]
  }
}
```

## Output

```json
{
  "document_id": 1,
  "result": {
    "nombre": "田中 太郎",
    "fecha_nacimiento": "1990-01-15",
    "direccion": "東京都渋谷区...",
    "numero_tarjeta": "AB12345678CD",
    "nacionalidad": "中国"
  },
  "evidence": [
    {
      "field": "nombre",
      "source": "ocr",
      "location": "page=1 bbox=100,50,200,30",
      "raw": "氏名 田中 太郎",
      "confidence": 0.95
    }
  ],
  "warnings": []
}
```

## Skills Utilizados
1. **japanese-document-ocr** - OCR de documentos japoneses
2. **face-detection-extraction** - Detección y recorte de fotos
3. **excel-smart-parser** - Parsing de Excel
4. **sqlite-blob-storage** - Persistencia en SQLite

## Ejemplo de Uso

```python
from document_data_extraction import DocumentDataExtractor

# Definir schema
schema = {
    "nombre": {"type": "string", "aliases": ["氏名", "NAME"]},
    "fecha_nacimiento": {"type": "date", "aliases": ["生年月日"]}
}

# Crear extractor
extractor = DocumentDataExtractor(db_path="data.db")

# Procesar documento
result = extractor.process(
    files=["zairyucard.jpg"],
    form_schema=schema
)

print(result)
# {
#   "document_id": 1,
#   "result": {"nombre": "田中 太郎", "fecha_nacimiento": "1990-01-15"},
#   "evidence": [...],
#   "warnings": []
# }
```

## Seguridad
- NO inventa datos
- Si un campo no está claro, usa null + warning
- NO intenta identificar personas por su rostro
- Conserva texto original sin "corregir"

## Dependencias
- japanese-document-ocr
- face-detection-extraction
- excel-smart-parser
- sqlite-blob-storage
