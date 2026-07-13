# /daily — Daily Capture Inbox (Logseq-style)

> Crear o abrir el capture inbox del día actual.

## Uso

```
/daily
```

## Qué hace

1. **Crea** `.claude/memory/daily/YYYY-MM-DD.md` si no existe para hoy
2. **Detecta** el proyecto activo desde `ESTADO_PROYECTO.md`
3. **Muestra** resumen del estado del Brain (última sesión)

El archivo tiene este formato:

```markdown
---
name: daily-{fecha}
description: Capture inbox para el día {fecha}
type: daily-capture
date: {fecha}
tags: [capture, daily, {proyecto}]
---

# {fecha} — Daily Capture

## Context
> ¿En qué proyecto estás trabajando hoy?

## Objectives
> - [ ] Objetivo 1
> - [ ] Objetivo 2

## Notes
> Capturas del día...

## Reflections
> Al cerrar la sesión: ¿qué aprendiste? ¿qué funcionó?
```

## Ejecución manual

```bash
python .agent/scripts/daily_capture.py
```

## Idempotencia

- Si ya existe el capture para hoy, lo salta (no sobreescribe)
- Safe para ejecutar múltiples veces

## Proyecto activo

Detecta automáticamente desde el header de sesión más reciente en `ESTADO_PROYECTO.md`.
Si no puede detectar, usa `general` como tag.

## Integración con hooks

El hook `session_start.sh` ejecuta este script automáticamente al inicio de cada sesión de Claude Code.
