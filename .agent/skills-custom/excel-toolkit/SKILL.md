---
name: excel-toolkit
description: "Consolidated guide for the Excel Engine — unified operations, backend routing, performance KPIs, and troubleshooting for Excel automation in the Antigravity ecosystem (parseo, escritura, charts, macros, Power Query, DAX, era japonesa, encoding Shift-JIS/CP932)."
---

# Excel Toolkit — Consolidated Guide

**Skill Name:** excel-toolkit  
**Version:** 1.0.0  
**Tier:** 6 (Specialized) — UNS Enterprise  
**Status:** Production  
**Category:** Excel Automation / Japanese Market

## Overview

The Excel Engine (`excel_engine.py`) is the central orchestrator for all Excel
operations in the Antigravity ecosystem. It provides a unified API for:

- **Parseo inteligente** (era japonesa, Shift-JIS, headers kobetsu/haken)
- **Escritura headless** (batch, sin Excel instalado)
- **Automatizacion live** (VBA, charts dinamicos, dashboards)
- **Power features** (Power Query, DAX, slicers, formatos condicionales)

It runs as a double-fanout: MCP stdio server + Gateway HTTP endpoints.

## Architecture

```
 CONSUMIDORES
 Claude Code  Nexus  Bot Telegram
      │          │         │
      ▼ stdio    ▼ HTTP    ▼ HTTP
 ┌─────────────────────────────────────┐
 │  SURFACE LAYER                      │
 │  excel-server.py (MCP stdio)        │
 │  gateway.py (/v1/excel/*)           │
 └──────────────┬──────────────────────┘
                │
 ┌──────────────▼──────────────────────┐
 │  CORE ENGINE (excel_engine.py)       │
 │  SessionManager  BackendRouter       │
 │  BrainTracker    OperationDispatcher │
 └────┬────────────┬─────────────┬──────┘
      │            │             │
 ┌────▼────┐ ┌─────▼────┐ ┌─────▼────┐
 │super-agent│ │ openpyxl│ │ xlwings │
 │ (parseo)  │ │(batch)  │ │ (live)  │
 └──────────┘ └─────────┘ └─────────┘
```

### Backend routing decision table

| Operation | Default | Override |
|---|---|---|
| `parse_smart` | super-agent | — |
| `read_range` | super-agent | — |
| `write_range`, `apply_formula`, `set_format` | openpyxl | xlwings si sesion live |
| `create_table` | openpyxl | xlwings si live |
| `create_chart` | openpyxl (estatico) | xlwings si `dynamic=true` |
| `create_pivot` | xlwings | — |
| `run_macro`, `update_dashboard`, `screenshot` | xlwings | error si Excel no disponible |
| `power_query`, `dax_measure`, `slicer` | xlwings | error si Excel no disponible |
| `calculation_mode` | xlwings | no-op en openpyxl |
| `save_as` | sigue al backend de la sesion | — |

Operations that require live Excel (xlwings): `run_macro`, `update_dashboard`,
`screenshot`, `power_query`, `dax_measure`, `slicer`.

## Session Management

Sessions are managed by `SessionManager` with:
- **TTL**: 30 minutos de inactividad
- **Max concurrent**: 5 sesiones (regla del proyecto)
- **Cleanup LRU**: la 6ta sesion cierra la LRU
- **Locks**: asyncio.Lock por session_id

```python
# API basica de sesiones
engine.open(path, mode="read")        # openpyxl, solo lectura
engine.open(path, mode="write")       # openpyxl, lectura/escritura
engine.open(path, mode="live")        # xlwings, requiere Excel corriendo
engine.close(session_id, save=True)   # guardar y cerrar
engine.list_sessions()                # lista sesiones activas
```

## Operations Reference

### Phase 1 — Core Read/Write

#### parse_smart(path, hints?)
Parseo inteligente via SuperAgentBackend. Maneja era japonesa (令和/平成),
Shift-JIS/CP932, headers kobetsu/haken, formularios gobierno.

```python
result = engine.parse_smart("kobetsu_2026.xlsx", hints={"era": "reiwa"})
# result.data = parsed spreadsheet as dict
```

#### read_range(session_id, sheet, range_addr)
Lee un rango de celdas. range_addr: 'A1:C10'.

```python
result = engine.read_range(sid, sheet="Sheet1", range_addr="A1:D10")
# result.data["values"] = [[val, val, ...], ...]
```

#### write_range(session_id, sheet, range_addr, values, fmt?)
Escribe valores 2D en el rango. Opcionalmente aplica CellFormat.

```python
values = [["Nombre", "Horas", "Total"], ["K. Kaneshiro", 40, 200000]]
engine.write_range(sid, sheet="Nómina", range_addr="A1", values=values)
# fmt: CellFormat(number_format="#,##0", font_color="FF0000", bold=True)
```

#### apply_formula(session_id, sheet, range_addr, formula)
Escribe formula en celda.

```python
engine.apply_formula(sid, sheet="Nómina", range_addr="C2", formula="=B2*C2")
```

#### set_format(session_id, sheet, range_addr, fmt)
Aplica formato a un rango.

```python
from excel_engine.types import CellFormat
fmt = CellFormat(number_format="#,##0", font_color="0000FF", bold=True)
engine.set_format(sid, sheet="Nómina", range_addr="C2:C10", fmt=fmt)
```

### Phase 2 — Tables and Charts

#### create_table(session_id, sheet, range_addr, name, style?)
Convierte rango en Tabla Excel con estilo opcional.

```python
engine.create_table(sid, sheet="Datos", range_addr="A1:E100",
                    name="TablaKobetsu", style="TableStyleMedium2")
```

#### create_chart(session_id, sheet, range_addr, chart_type, title?, legend?)
Crea grafico. Tipos: column, bar, line, pie, scatter, area.

```python
engine.create_chart(sid, sheet="Resumen", range_addr="A1:D5",
                    chart_type="column", title="Ventas 2026", legend=True)
```

#### create_pivot(session_id, sheet, data_range, dest_cell, rows?, columns?, values?)
Crea tabla pivote.

```python
engine.create_pivot(sid, sheet="Datos", data_range="A1:E100",
                    dest_cell="G3", rows=["Departamento"],
                    columns=["Mes"], values=["Ventas"])
```

### Phase 3 — Live Automation (xlwings)

#### run_macro(session_id, macro_name, args)
Ejecuta macro VBA por nombre. Requiere Excel corriendo.

```python
# Macro en el mismo workbook: Module1.RefreshAll
engine.run_macro(sid, macro_name="Module1.RefreshAll", args=[])
# Macro con argumentos
engine.run_macro(sid, macro_name="Module1.CalcWithParams", args=["2026-04", 100])
```

#### update_dashboard(session_id, dashboard_sheet, data_sheets, refresh_all?)
Actualiza celdas KPI en dashboard y fuerza recalculo.

```python
kpis = {"B2": 450000, "B3": 0.87, "B4": "2026-04-28"}
engine.update_dashboard(sid, dashboard_sheet="Dashboard",
                        data_sheets=["Nómina", "Ventas"], refresh_all=True)
```

#### screenshot(session_id, sheet, path, region?)
Captura hoja como PNG.

```python
engine.screenshot(sid, sheet="Dashboard", path="dash_2026.png")
# Region opcional: "A1:J20"
```

#### calculation_mode(session_id, mode)
Cambia modo de calculo: automatic, manual, semiautomatic.

```python
engine.calculation_mode(sid, mode="manual")   # antes de macrosbatch
engine.calculation_mode(sid, mode="automatic") # despues
```

### Power Features (Phase 3)

#### power_query(session_id, query_name, connection_string, output_cell, sql?)
Ejecuta o crea Power Query.

```python
# Listar queries
engine.power_query(sid, query_name="list", connection_string="", output_cell="A1")
# Refresh
engine.power_query(sid, query_name="RefreshAll", connection_string="", output_cell="A1")
# Crear query M
m_code = 'let Source = Sql.Database("localhost","DB") in Source'
engine.power_query(sid, query_name="NewQuery", connection_string=m_code,
                   output_cell="A1")
```

#### dax_measure(session_id, table_name, measure_name, expression)
Crea o actualiza medida DAX.

```python
engine.dax_measure(sid, table_name="Ventas",
                    measure_name="TotalNeto",
                    expression="SUM(Ventas[Bruto]) - SUM(Ventas[Descuento])")
```

#### slicer(session_id, pivot_table_name, source_field, dest_cell, style?)
Crea slicer de segmentacion.

```python
engine.slicer(sid, pivot_table_name="Pivot_Kobetsu",
               source_field="Departamento", dest_cell="K3",
               style="SlicerStyleLight1")
```

#### conditional_format(session_id, sheet, range_addr, rule_type, formula_or_threshold, format_style?)
Aplica formato condicional.

```python
# Regla por formula
engine.conditional_format(sid, sheet="Nómina", range_addr="C2:C100",
                         rule_type="formula",
                         formula_or_threshold="C2>500000",
                         format_style="red_bold")
# Data bar
engine.conditional_format(sid, sheet="Nómina", range_addr="D2:D100",
                         rule_type="data_bar")
```

#### save_as(session_id, path, format)
Exporta a otro formato.

```python
engine.save_as(sid, path="output.pdf", format="pdf")
engine.save_as(sid, path="output.csv", format="csv")
engine.save_as(sid, path="output.xlsm", format="xlsm")
```

## Quick Start

### Via MCP (Claude Code, Cursor, Windsurf)

El server `antigravity-excel` esta registrado en `.mcp.json`. Tools disponibles:

```
excel_open         → open(path, mode)
excel_close        → close(session_id, save)
excel_list_sessions → list_sessions()
excel_parse_smart  → parse_smart(path, hints)
excel_read_range   → read_range(session_id, sheet, range)
excel_write_range  → write_range(session_id, sheet, range, values, fmt)
excel_apply_formula → apply_formula(session_id, sheet, range, formula)
excel_set_format   → set_format(session_id, sheet, range, fmt)
excel_create_table → create_table(session_id, sheet, range, name, style)
excel_save_as      → save_as(session_id, path, format)
excel_health      → backends_available
excel_run_macro   → run_macro(session_id, macro_name, args)
excel_create_chart → create_chart(session_id, sheet, range, chart_type, title, legend)
excel_create_pivot → create_pivot(...)
excel_update_dashboard → update_dashboard(...)
excel_screenshot   → screenshot(session_id, sheet, path, region)
excel_power_query  → power_query(...)
excel_dax_measure  → dax_measure(...)
excel_slicer       → slicer(...)
excel_conditional_format → conditional_format(...)
excel_calculation_mode → calculation_mode(...)
```

### Via Gateway HTTP

```bash
# Abrir sesion
curl -X POST http://127.0.0.1:4747/v1/excel/sessions \
  -H "X-API-Key: ..." -H "Content-Type: application/json" \
  -d '{"path": "kobetsu.xlsx", "mode": "write"}'

# Escribir rango
curl -X POST http://127.0.0.1:4747/v1/excel/sessions/{sid}/range \
  -H "X-API-Key: ..." -H "Content-Type: application/json" \
  -d '{"sheet": "Nómina", "range": "A1", "values": [["Nombre","Horas"]]}'

# Ejecutar macro
curl -X POST http://127.0.0.1:4747/v1/excel/sessions/{sid}/macro \
  -d '{"macro_name": "Module1.RefreshAll", "args": []}'

# Health
curl http://127.0.0.1:4747/v1/excel/health
```

### Via CLI (excel-toolkit fallback)

Cuando el gateway no esta corriendo, usar el CLI directo:

```bash
python .agent/skills-custom/excel-toolkit/scripts/main.py parse --path kobetsu.xlsx
python .agent/skills-custom/excel-toolkit/scripts/main.py write --session <sid> \
    --sheet "Nómina" --range A1 --values '[["Nombre","Horas"],["K. Kaneshiro",40]]'
python .agent/skills-custom/excel-toolkit/scripts/main.py macro --session <sid> \
    --name Module1.RefreshAll
```

## xlwings — Notes and Installation

xlwings permite automatizar Excel vivo via COM en Windows. Es necesario para
operaciones Phase 2+3 que requieren Excel corriendo.

### Requisitos

- Windows con Microsoft Excel instalado
- `pip install xlwings>=0.30`
- Macros habilitadas o Trust Access al VBA project object model

### Instalacion

```bash
pip install xlwings
```

### Habilitar macros en Excel

1. Archivo > Opciones > Centro de confianza > Configuracion de macros
2. Marcar "Habilitar macros" (o "Trust access to VBA project object model")
3. Guardar y reiniciar Excel

### Verificar disponibilidad

```python
import xlwings as xw
wb = xw.Book("test.xlsx")
print(wb.app.name)  # 'Microsoft Excel'
```

### COM initialization

xlwings usa COM (pywin32/win32com). En Windows Server puede requerir:
- Regsvr32 para registros COM
- Permisos de ejecucion de automation

### Limitaciones

- **No funciona en Mac/Linux** sin Excel (solo openpyxl headless)
- **COM no es thread-safe**: el engine usa un lock global para serializar ops xlwings
- **Modal dialogs bloquean**: MsgBox, InputBox en VBA pueden causar timeout
- **Excel debe estar visible** o usar `xw.App(visible=True)` para evitar hang

## Era Japonesa y Encoding

### Fechas en era (令和/平成)

El parseo inteligente detecta automaticamente el formato de fecha japonesa:

```python
# Se parsean como datetime
"2026/04/28"     → 2026-04-28
"令和8年4月28日"  → 2026-04-28 (era Reiwa)
"平成28年4月28日" → 2016-04-28 (era Heisei)
```

El `SuperAgentBackend` realiza la conversion; `openpyxl` no maneja eras nativamente.

### Encoding Shift-JIS / CP932

Excel archivos japoneses usan CP932 (extension de Shift-JIS). El super-agent
maneja esto automaticamente; openpyxl puede tener problemas con caracteres
extensos si no se especifica encoding.

```python
# En super_agent_backend.py se usa:
with open(path, "rb") as f:
    raw = f.read()
# Detect encoding via chardet, priorizar CP932
```

## KPIs de Rendimiento

### Tiempos de respuesta (target P95)

| Operation | Target | Backend |
|---|---|---|
| `parse_smart` (1MB tabular) | < 500ms | super-agent |
| `write_range` (1000 cells) | < 200ms | openpyxl |
| `create_pivot` (10k rows) | < 3s | xlwings |
| `power_query` refresh (SQL local) | < 2s | xlwings |
| `run_macro` simple | < 1s | xlwings |
| `screenshot` | < 2s | xlwings |

### Sesiones activas

- Maximo: 5 sesiones simultaneas
- TTL: 30 minutos de inactividad
- Si se alcanza el limite: cierra LRU automaticamente

### Error rates

| Code | Category | Description |
|---|---|---|
| `BACKEND_NOT_AVAILABLE` | fatal | xlwings no instalado o Excel no corre |
| `BACKEND_NOT_SHIPPED` | fatal | Operacion Phase 3 sin Excel |
| `PATH_NOT_FOUND` | user | Archivo no existe |
| `SESSION_UNKNOWN` | user | session_id invalido |
| `FILE_LOCKED_BY_USER` | transient | Excel abierto por otro proceso |
| `EXCEL_CRASHED` | fatal | Excel murio durante operacion |
| `MACRO_TIMEOUT` | fatal | Macro con dialogo modal bloqueante |
| `PATH_ENCODING_INVALID` | user | Path con caracteres no soportados |

### Recovery automatico

El engine reintenta automaticamente errores recuperables una vez
aplicando `suggested_next_actions`. Errores transient (timeout COM,
archivo bloqueado) tienen retry backoff 200→500→1500ms.

## FAQs

### Como abro un archivo para escritura?

```python
engine.open(path, mode="write")  # openpyxl headless
```

### Como ejecuto una macro VBA?

Necesitas modo live:

```python
engine.open(path, mode="live")  # xlwings, Excel debe estar corriendo
sid = result.data["session_id"]
engine.run_macro(sid, macro_name="Module1.RefreshAll", args=[])
```

### Puedo usar el engine sin tener Excel instalado?

Si, con modo `read` o `write` (openpyxl headless). Solo las operaciones
Phase 3 (run_macro, screenshot, power_query, dax_measure, slicer)
requieren Excel.

### Como exporto a PDF?

```python
engine.save_as(sid, path="output.pdf", format="pdf")
```

### El engine maneja archivos con passwords?

No directamente. Para archivos protegidos, se requiere abrir con
`mode="live"` y deshabilitar password via VBA primero.

### Cuantas sesiones puedo tener abiertas?

Maximo 5 sesiones simultaneas. Se cierra automaticamente la LRU
Least Recently Used si se intenta abrir una 6ta.

### Como limpio sesiones huérfanas?

El cleanup corre automaticamente cada 30 min (TTL). Para forzar cleanup:

```python
# Cerrar todas las sesiones inactivas
for s in engine.list_sessions().data["sessions"]:
    if s["inactive_for"] > 600:  # > 10 min
        engine.close(s["session_id"])
```

## Referencias

- Spec completo: `docs/superpowers/specs/2026-04-27-excel-engine-design.md`
- Plan de implementacion: `docs/superpowers/plans/2026-04-28-excel-engine-mvp-plan-b.md`
- MCP server: `.agent/mcp/excel-server.py`
- Core engine: `.agent/core/excel_engine/engine.py`
- Backend xlwings: `.agent/core/excel_engine/backends/xlwings_backend.py`
- Backend openpyxl: `.agent/core/excel_engine/backends/openpyxl_backend.py`
- Super agent: `.agent/skills/excel-super-agent/scripts/main.py`

## Changelog

### v1.0.0 (2026-04-28)
- Initial release — consolidated excel-toolkit skill
- Phase 1+2+3 operations documented
- Backend routing table, KPIs, troubleshooting
- Era japonesa y encoding notes
- xlwings installation and limitations

## Author

Antigravity Team — K. Kaneshiro / UNS  
**License:** Proprietary — Part of Antigravity Ecosystem