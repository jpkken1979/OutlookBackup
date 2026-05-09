name: excel-specialist
description: Agente especializado en Excel — parseo inteligente, escritura headless y live, automatización, dashboards, Power Query y DAX
tier: specialized
version: 1.0.0

capabilities:
  - excel_parse: Delegar excel_parse_smart al antigravity-excel MCP
  - excel_write: Delegar excel_write_range al antigravity-excel (openpyxl)
  - excel_live: Delegar excel_open mode=live al antigravity-excel (xlwings)
  - excel_chart: Crear charts dinámicos
  - excel_pivot: Crear tablas dinámicas
  - excel_macro: Ejecutar macros VBA
  - excel_power: Power Query y DAX

skills_required:
  - excel-super-agent

mcp_required:
  - antigravity-excel
  - antigravity-brain

triggers:
  keywords:
    - excel, xlsx, xlsm, kobetsu, haken, planilla, pivot, dashboard
    - vba, dax, power query, macro, chart, formato condicional
    - 個別契約, 派遣, 勤怠, 有給, 賃金, 履歴書
  file_patterns:
    - "*.xlsx", "*.xlsm", "*.xls", "*.csv"

routing:
  orchestrator_keywords:
    - excel, xlsx, kobetsu, haken, planilla, pivot, dashboard
    - vba, dax, power query, 個別契約, 派遣

modes:
  parse: antigravity-excel → excel_parse_smart
  write: antigravity-excel → excel_write_range (openpyxl)
  live: antigravity-excel → excel_open mode=live (xlwings)
  chart: antigravity-excel → excel_create_chart
  pivot: antigravity-excel → excel_create_pivot
  macro: antigravity-excel → excel_run_macro
  power: antigravity-excel → excel_power_query / excel_dax_measure

entry_point: python .agent/agents/excel-specialist/scripts/main.py

memory:
  shared_memory_path: .agent/agents/excel-specialist/memory/shared_memory.json
  persist_after_run: true
