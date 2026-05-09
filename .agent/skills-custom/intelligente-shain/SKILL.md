---
name: intelligente-shain
description: Gestión inteligente de empleados para el mercado japonés. Sincronización Excel-DB, datos de shain (従業員).
---

# Intelligente Shain — Gestión Inteligente de Empleados

Skill especializado para la gestión de empleados (社員/shain) en el mercado japonés de dispatch (派遣).

## Funcionalidades

- Consulta de empleados por ID o filtros
- Actualización de datos de shain
- Listado de empleados activos
- Sincronización con archivos Excel japoneses (Shift-JIS)

## Uso

```bash
python scripts/main.py --action list
python scripts/main.py --action query --employee-id EMP001
python scripts/main.py --action update --employee-id EMP001
```

## Tags

`uns-dispatch`, `haken`, `employee-management`, `japanese-market`