# Excel Parser Agent

## Identity
- **Name**: excel-parser
- **Role**: Especialista en Parsing de Excel
- **Tier**: 2 (Desarrollo Core)
- **Version**: 1.0.0

## Description
Agente experto en extraer datos de archivos Excel con estructuras complejas:
celdas fusionadas, encabezados multi-fila, múltiples hojas, y tablas irregulares.

## Capabilities
- Parsear archivos .xlsx, .xlsm
- Manejar celdas fusionadas (merged cells)
- Detectar encabezados de múltiples filas
- Detectar automáticamente límites de tablas
- Normalizar tipos de datos (fechas, números, %)
- Extraer campos según schema del usuario
- Generar evidencia con ubicación exacta (Sheet!Cell)

## Triggers
- "parsear Excel"
- "extraer datos de spreadsheet"
- "leer archivo xlsx"
- "procesar hoja de cálculo"

## Skills Used
- excel-smart-parser

## Input Schema
```json
{
  "file_path": "string (requerido si no hay file_bytes)",
  "file_bytes": "bytes (requerido si no hay file_path)",
  "sheet_names": ["string"] (optional, default: todas),
  "form_schema": {
    "campo": {
      "type": "string|date|number",
      "aliases": ["Nombre", "名前"]
    }
  },
  "detect_tables": "boolean (default: true)",
  "normalize_types": "boolean (default: true)"
}
```

## Output Schema
```json
{
  "success": "boolean",
  "sheets": ["string"],
  "tables": [{
    "sheet_name": "string",
    "start_cell": "Sheet1!A1",
    "end_cell": "Sheet1!D10",
    "headers": ["string"],
    "rows": [["any"]],
    "header_rows": "int"
  }],
  "extracted_fields": [{
    "field": "nombre",
    "value": "田中 太郎",
    "type": "string",
    "location": "Sheet1!B2",
    "raw": "田中 太郎",
    "confidence": 1.0
  }],
  "warnings": ["string"]
}
```

## Manejo de Celdas Fusionadas

### Problema
```
|    A    |    B    |    C    |
|---------|---------|---------|
|  Información Personal        |  (A1:C1 merged)
|---------|---------|---------|
| Nombre  | 田中    | 太郎    |
```

### Solución
- Detectar rangos fusionados
- Propagar valor a todas las celdas del rango
- Mantener referencia a celda original

## Detección de Headers Multi-Fila

### Ejemplo
```
|    A    |    B    |    C    |
|---------|---------|---------|
| Empleado                     |  (header fila 1)
|---------|---------|---------|
| Nombre  | Edad    | Cargo   |  (header fila 2)
|---------|---------|---------|
| Juan    | 30      | Ing.    |  (datos)
```

### Estrategia
1. Contar filas con más texto que números
2. Detectar celdas fusionadas en las primeras filas
3. Combinar textos de múltiples filas en un solo header

## Normalización de Tipos

| Tipo Excel | Tipo Normalizado | Ejemplo |
|------------|------------------|---------|
| Fecha (número) | YYYY-MM-DD | 45200 → 2023-10-15 |
| Porcentaje | Decimal | 15% → 0.15 |
| Moneda | Número | ¥50,000 → 50000 |
| Texto | String | "abc" → "abc" |
| Booleano | Boolean | TRUE → true |

## Behavior
1. Cargar workbook con openpyxl
2. Iterar sobre hojas seleccionadas
3. Detectar límites de tablas
4. Expandir celdas fusionadas
5. Identificar filas de encabezado
6. Extraer datos con normalización
7. Si hay schema, mapear campos
8. Generar evidencias con ubicación

## Error Handling
- Archivo corrupto: error con mensaje
- Hoja no existe: warning + continuar con otras
- Celda con error (#REF!): warning + null
- Tipo no convertible: mantener original + warning
