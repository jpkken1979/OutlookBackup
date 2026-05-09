---
description: Verificación de calidad del código
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash
---

Ejecuta verificaciones de calidad:

1. `ruff check .agent/` — Python linting
2. `python -m mypy .agent/core/` — Type checking
3. `cd nexus-app && npm run lint` — ESLint
4. `cd nexus-app && npm run ts:app` — TypeScript check
5. Verificar que todos los skills tienen SKILL.md
6. Verificar que todos los agentes tienen IDENTITY.md

Reportar un resumen con pass/fail por categoría.
