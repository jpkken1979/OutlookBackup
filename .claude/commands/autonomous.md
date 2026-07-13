---
description: Planificador y ejecutor autonomo de objetivos
argument-hint: "<objetivo>"
allowed-tools: Bash
---

Ejecuta el Autonomous Executor para lograr un objetivo de forma autonoma.

## Uso

`/autonomous arreglar el bug de login`
`/autonomous implementar el modulo de reportes`
`/autonomous auditar seguridad del codigo`

## Que hace

1. Analiza el objetivo y genera un plan estructurado de pasos
2. Muestra el plan y espera aprobacion humana antes de ejecutar
3. Ejecuta cada paso de forma autonoma usando subprocess, MCP y Brain
4. Reintenta pasos fallidos automaticamente (max 2 retries)
5. Aborta si >30%% de los pasos fallan
6. Guarda resumen en Brain Network y sincroniza memorias en git

## Comandos de ejecucion

Ejecuta directamente:

```bash
py .agent/skills-custom/autonomous-executor/scripts/main.py --goal "$ARGUMENTS"
```

## Opciones del script

- `--goal "..."` — Objetivo de texto libre a ejecutar
- `--plan-only` — Solo genera el plan, no ejecuta
- `--json` — Salida en formato JSON
- `--verbose` — Logging detallado

## Ejemplo de salida

```
[Autonomous Executor] Objetivo: arreglar el bug de login
[Autonomous Executor] Gateway: http://127.0.0.1:4747

[1/5] Analizando objetivo...
       Plan generados: 6 pasos

============================================================
OBJETIVO: arreglar el bug de login
============================================================

PLAN:
  [1] Analizar codigo
       Target: Archivos relevantes del proyecto
       Criteria: Se identifican los archivos a modificar
       Method: subprocess
  ...
============================================================

Respuestas validas: si / no / modificar
```
