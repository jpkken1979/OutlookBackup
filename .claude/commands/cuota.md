---
description: Mostrar cuotas actuales de CodexBar
argument-hint: [--refresh|--json]
allowed-tools: Bash, Read
---

Ejecuta el lector de cuotas de CodexBar y reporta el resultado tal cual, sin
inventar porcentajes ni resets. Por defecto es solo lectura sobre
`~/.codexbar/snapshots.json`; usa `--refresh` solo si el usuario lo pidio.

Resultado de CodexBar:
!`python .agent/scripts/codexbar_quota.py $ARGUMENTS`

Si el script falla, explica el error y sugiere abrir CodexBar o volver a ejecutar
`/cuota --refresh`.
