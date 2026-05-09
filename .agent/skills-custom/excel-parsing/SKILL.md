---
name: excel-parsing
description: Mejores prácticas para parsear archivos Excel (.xlsx, .xlsm, .xls). Manejo de headers, whitespace, multi-sheet, validación de tipos, data cleaning. Librería: openpyxl o pandas. Triggers: Excel, xlsx, parse Excel, read spreadsheet, data import, column mapping, sheet selection.
---

# Excel Parsing - Mejores Prácticas

## Propósito

Guía completa para parsear archivos Excel correctamente.

## Mejores Prácticas

### 1. Seleccionar Librería
**openpyxl:** Control fino, cell-level
**pandas:** Data frames, análisis rápido
**xlrd:** Legacy, solo lectura

### 2. Headers y Whitespace
```python
# ✅ BUENO
df = pd.read_excel(file, header=0, skipinitialspace=True)
headers = [col.strip() for col in df.columns]

# ❌ MALO
data = pd.read_excel(file)  # Headers con espacios
```

### 3. Sheet Selection
```python
# ✅ Específico
df = pd.read_excel(file, sheet_name='Data')

# ❌ Ambiguo
df = pd.read_excel(file)  # Asume Sheet1
```

### 4. Type Validation
```python
# ✅ Validar tipos
df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
df['date'] = pd.to_datetime(df['date'], errors='coerce')

# ❌ Sin validación
data = df['amount']  # Puede ser str, int, float...
```

### 5. Data Cleaning
- Trim whitespace
- Handle null/empty
- Convert types
- Remove duplicates
- Validate ranges

## Uso

```bash
/excel-parsing "Necesito parsear archivo.xlsx con..."
```

Describe:
- Estructura esperada
- Validaciones necesarias
- Salida deseada
