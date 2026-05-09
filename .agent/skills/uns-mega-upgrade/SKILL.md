---
name: uns-mega-upgrade
type: feature
description: "MEGA UPGRADE para todos los skills UNS existentes. Incluye: (1) visa-tracker completo con notificaciones LINE/Email, (2) Dashboard HTML unificado para todos los módulos, (3) API REST FastAPI con Swagger, (4) Analytics con gráficos matplotlib, (5) Google Sheets sync, (6) Mejoras a 36kyotei-checker con predicciones, (7) Sistema de alertas centralizado, (8) Reportes ejecutivos automáticos. Este skill COMPLEMENTA y MEJORA todos los demás skills UNS. Triggers: mega upgrade, mejoras, upgrade all, dashboard unificado, analytics, notifications."
---

# UNS MEGA UPGRADE 🚀

Actualización masiva para todos los skills UNS existentes.

## 🎯 Módulos Incluidos

### 1. 📧 Notification Center
- Email templates profesionales (HTML)
- LINE Notify integration
- Slack webhooks (opcional)
- Alertas automáticas por cron

### 2. 🖥️ Unified Dashboard
- HTML5 responsive
- Chart.js gráficos interactivos
- Tabs para cada módulo
- Dark/Light mode

### 3. 🔌 REST API
- FastAPI con auto-docs
- JWT authentication
- Rate limiting
- CORS configurado

### 4. 📊 Analytics Engine
- Trends de粗利
- Heatmap de overtime
- Predicción de visas
- Comparativas por派遣先

### 5. 🔄 Google Sheets Sync
- Push data a Sheets
- Pull updates
- Sync bidireccional

## 🚀 Quick Start

```bash
# Iniciar todo
python scripts/mega_upgrade.py serve --port 8080

# Solo notificaciones
python scripts/mega_upgrade.py notify --check-all

# Generar dashboard
python scripts/mega_upgrade.py dashboard --output dashboard.html

# Sync con Google Sheets
python scripts/mega_upgrade.py sync-sheets --sheet-id YOUR_SHEET_ID
```
