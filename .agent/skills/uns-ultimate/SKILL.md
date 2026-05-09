---
name: uns-ultimate
type: feature
description: "Sistema DEFINITIVO de gestión UNS. Incluye: Parser REAL de Excel勤怠表 (8 filas/empleado), Dashboard HTML interactivo, API REST FastAPI, reportes con gráficos (matplotlib/plotly), CLI interactivo con menús (rich), templates de email/LINE, integración弥生/freee, validaciones completas según ley japonesa, multi-idioma (JP/VN/ES/EN), auditoría de cambios, backup automático. El skill más completo jamás creado. Triggers: ultimate, definitivo, todo, complete system, full system, mega system."
---

# UNS ULTIMATE System 🚀

El sistema más completo para gestión de派遣社員.

## 🎯 Características ULTIMATE

### 📊 Excel Parser Real
- Lee勤怠表 con estructura real de 8 filas por empleado
- Detecta automáticamente締日 (15 o 20)
- Extrae: 定時, 残業, 深夜, 休日, 遅刻, 早退
- Valida datos antes de importar

### 🖥️ Dashboard Web
- HTML/CSS responsive profesional
- Gráficos interactivos (Chart.js)
- Alertas visuales en tiempo real
- Export a PDF/Excel desde web

### 🔌 API REST
- FastAPI con documentación automática
- Endpoints para todo el sistema
- Autenticación JWT
- Rate limiting

### 📈 Reportes con Gráficos
- Tendencias de horas/粗利
- Comparativas por派遣先
- Análisis de overtime
- Export PNG/SVG

### 💬 Notificaciones
- Templates de email profesionales
- Mensajes LINE listos
- Alertas automáticas

### 🔄 Integraciones
- Export para弥生会計
- Export para freee
- CSV estándar japonés

## 🚀 Quick Start

```bash
# CLI Interactivo (menús bonitos)
python scripts/uns_ultimate.py interactive

# Dashboard web
python scripts/uns_ultimate.py serve --port 8080

# Parser de Excel勤怠表
python scripts/uns_ultimate.py parse-kintai input.xlsx --month 2025-01

# Reporte con gráficos
python scripts/uns_ultimate.py report --month 2025-01 --charts

# Backup completo
python scripts/uns_ultimate.py backup --output backup_20250201.zip
```
