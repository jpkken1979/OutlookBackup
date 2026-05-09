---
name: excel-smart-parser
description: Skill avanzado para parsing de archivos Excel con soporte para celdas fusionadas, encabezados multi-fila y detección automática de tablas
type: feature
---

# Excel Smart Parser Skill

## Metadata
- **Name**: excel-smart-parser
- **Version**: 1.0.0
- **Category**: data-extraction, document-processing
- **Tags**: excel, xlsx, parsing, merged-cells, tables, data-extraction

## Description
Skill avanzado para parsing de archivos Excel con soporte para:
- Celdas fusionadas (merged cells)
- Encabezados multi-fila
- Múltiples hojas
- Detección automática de tablas
- Normalización de tipos de datos
- Evidencia de extracción (Sheet!Cell)

## Características Principales
1. **Detección de Tablas**: Identifica automáticamente dónde comienza y termina cada tabla
2. **Manejo de Merged Cells**: Expande valores de celdas fusionadas
3. **Headers Inteligentes**: Detecta encabezados de una o múltiples filas
4. **Normalización**: Convierte fechas, números y porcentajes a formatos estándar
5. **Evidencia**: Registra la ubicación exacta de cada dato (Hoja!Celda)

## Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_path | string | Yes* | Ruta al archivo Excel |
| file_bytes | bytes | Yes* | Bytes del archivo Excel |
| sheet_names | list | No | Hojas específicas a procesar (default: todas) |
| form_schema | dict | No | Schema de campos a extraer |
| detect_tables | boolean | No | Auto-detectar tablas (default: true) |
| normalize_dates | boolean | No | Normalizar fechas a YYYY-MM-DD (default: true) |

*Uno de file_path o file_bytes es requerido

## Outputs
| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Si la extracción fue exitosa |
| sheets | list | Lista de hojas procesadas |
| tables | list | Tablas detectadas con datos |
| extracted_fields | dict | Campos extraídos según form_schema |
| evidence | list | Evidencias de ubicación |
| warnings | list | Advertencias |

## Estructura de Evidencia
```json
{
  "field": "nombre",
  "source": "excel",
  "location": "Sheet1!B2",
  "raw": "田中 太郎",
  "confidence": 1.0
}
```

## Ejemplo de Uso

```python
from excel_smart_parser import ExcelSmartParser

parser = ExcelSmartParser()

# Parsear archivo
result = parser.parse("employees.xlsx")

# Con schema específico
schema = {
    "nombre": {"type": "string", "aliases": ["Name", "氏名", "名前"]},
    "fecha_nacimiento": {"type": "date", "aliases": ["DOB", "生年月日"]},
    "salario": {"type": "number", "aliases": ["Salary", "給与"]}
}

result = parser.parse("employees.xlsx", form_schema=schema)

# Acceder a los datos
for table in result['tables']:
    print(f"Tabla en {table['location']}")
    for row in table['rows']:
        print(row)
```

## Manejo de Celdas Fusionadas

### Antes (en Excel)
```
|    A    |    B    |    C    |
|---------|---------|---------|
|  Nombre (merged A1:C1)       |
|---------|---------|---------|
| Juan    | 30      | Ing.    |
```

### Después (parseado)
```python
{
    "headers": ["Nombre", "Nombre", "Nombre"],  # Expandido
    "rows": [
        ["Juan", 30, "Ing."]
    ]
}
```

## Normalización de Tipos

| Tipo Original | Tipo Normalizado | Ejemplo |
|---------------|------------------|---------|
| Fecha Excel (número) | YYYY-MM-DD | 2023-12-25 |
| Porcentaje | Decimal | 0.15 (era 15%) |
| Moneda | Número | 50000 (era ¥50,000) |
| Booleano | boolean | true/false |

## Dependencias
- openpyxl
- pandas
- python-dateutil

## Instalación
```bash
pip install openpyxl pandas python-dateutil
```

## Notas
- Las celdas vacías se mantienen como null
- Los errores de fórmula (#REF!, #N/A) se registran como warnings
- Soporta archivos .xlsx, .xlsm (no .xls antiguo)
