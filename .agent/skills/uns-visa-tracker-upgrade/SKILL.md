---
name: uns-visa-tracker-upgrade
type: feature
description: "UPGRADE para uns-visa-tracker - agrega script ejecutable completo con: tracking de在留カード, alertas automáticas, generación de reportes, notificaciones LINE/Email, calendario de vencimientos, recordatorios de renovación, checklist de documentos, integración con入管 requirements. Triggers: visa tracker upgrade, 在留カード tracking, visa alerts, visa notifications."
---

# UNS Visa Tracker UPGRADE 🛂

Script ejecutable completo para el skill uns-visa-tracker.

## Features

- ✅ Check de vencimientos con alertas por nivel
- 📅 Calendario de renovaciones
- 📧 Notificaciones automáticas (LINE/Email)
- 📋 Checklist de documentos por tipo de visa
- 📊 Dashboard HTML de visas
- 📤 Export CSV para入管

## Uso

```bash
# Check de alertas
python scripts/visa_tracker.py check

# Dashboard HTML
python scripts/visa_tracker.py dashboard --output visa_dashboard.html

# Notificar por LINE
python scripts/visa_tracker.py notify --channel line

# Export para入管
python scripts/visa_tracker.py export --output visa_report.csv

# Checklist de documentos
python scripts/visa_tracker.py checklist --visa-type 特定技能1号
```
