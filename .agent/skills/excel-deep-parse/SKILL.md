---
name: excel-deep-parse
description: "Advanced spatial Excel parser for complex, non-tabular, or highly stylized sheets (e.g., invoices, government forms, Japanese Haken documents). Extracts data based on spatial relationships, styles, and hierarchical headers. Detects key-value pairs, multi-row headers, and cell metadata (color, font, border)."
type: feature
---

# Excel Deep Parse - Antigravity Edition 🕵️‍♂️

> **Status:** ACTIVE
> **Purpose:** Extract data from "Human-formatted" Excel sheets that defy standard tabular parsing.

This skill provides a mechanism to "read" an Excel sheet like a human does: looking for labels, identifying values next to or below them, understanding hierarchy through cell merging, and using visual cues (colors, borders) to determine context.

## 🚀 Capabilities

1.  **Spatial Key-Value Extraction**: Finds "Name:" in A1 and extracts "Kenji" from B1 (Right) or A2 (Below).
2.  **Hierarchical Table Parsing**: Handles complex multi-row headers (e.g., "Salary" merged over "Base" and "Tax").
3.  **Visual Semantics**: Can filter or identify cells based on background color (e.g., "Extract only yellow input cells").
4.  **Japanese Layout Support**: Optimized for typical Japanese business forms (vertical layouts, merged labels).

## 🛠️ Usage

### Python Script (Direct)

```python
from skills.excel_deep_parse.scripts.deep_parser import ExcelDeepParser

parser = ExcelDeepParser("checklist.xlsx")

# 1. Extract specific fields by label (searches neighbors)
data = parser.extract_fields([
    {"label": "氏名", "direction": "auto"},  # Finds Name next to or below
    {"label": "合計金額", "direction": "right"},
    {"label": "Status", "bg_color": "FFFF00"} # Only if cell is yellow
])

# 2. Extract complex table with multi-row header
tables = parser.extract_complex_tables()
```

## 🧩 When to use this vs `excel-smart-parser`

| Feature | `excel-smart-parser` | `excel-deep-parse` |
| :--- | :--- | :--- |
| **Simple Tables** | ✅ Fast & Easy | ⚠️ Overkill |
| **merged_cells** | 🟢 Basic support | 🦄 **Full Structural Awareness** |
| **Non-Tabular Forms** | ❌ Fails | ✅ **Spatial Neighbor Detection** |
| **Style/Color Logic** | ❌ Ignored | ✅ **Visual Extraction** |
| **Target Use Case** | Data dumps, CSV-like lists | Invoices, Tax Forms, Dashboards |

## 📦 Dependencies

- `openpyxl` (Required for style analysis)
- `pandas` (Optional, for dataframe export)
