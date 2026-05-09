---
description: Ejecución y análisis universal de tests basado en el comando legacy test-suite.
universal: true
aliases:
  - test-suite
  - test-run
---

# /test-suite - Ejecutar y analizar tests

## Objetivo

Ejecutar la suite relevante, resumir fallos y detectar cobertura o casos faltantes.

## Entrada

`$ARGUMENTS`

Áreas sugeridas:
- `backend`
- `frontend`
- `all`

Flags sugeridos:
- `--coverage`
- `--fix`

## Flujo

### 1. Detectar stack de test

Elegir los comandos reales del repo antes de correr nada.

### 2. Ejecutar tests relevantes

Ejemplos típicos:

```bash
pytest tests/ -v
npm test
```

### 3. Resumir resultados

Informar:
- total passed/failed/skipped
- fallos más importantes
- módulos sin cobertura suficiente

### 4. Si se pidió `--fix`

Corregir primero:
- tests rotos por regresión real
- tests obsoletos tras refactor
- flakiness obvia

## Salida esperada

```markdown
## Resultado

- Backend: OK|FAIL
- Frontend: OK|FAIL

## Fallos relevantes
- ...

## Cobertura / gaps
- ...
```
