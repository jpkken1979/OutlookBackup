# Regla: Test de Inflacion de Contexto

Antes de ejecutar una accion, evaluar si infla el contexto innecesariamente.

## Hacer inline (sin delegar)
- Leer 1-3 archivos
- Editar 1 archivo
- Comandos bash simples (git status, ls, etc.)
- Consultas grep/glob puntuales

## Delegar a sub-agente (Agent tool)
- Leer 4+ archivos para investigacion
- Editar multiples archivos en paralelo
- Ejecutar test suites completas
- Busquedas amplias en el codebase
- Tareas que generan output > 500 lineas

## Por que
El contexto de Claude Code es limitado. Cada archivo leido ocupa tokens.
Delegar a sub-agentes mantiene el contexto principal limpio para decisiones.
