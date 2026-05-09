---
description: Revisión de código universal basada en el comando legacy code-review.
universal: true
aliases:
  - review-pr
  - code-review
---

# /code-review - Revisión de código universal

## Objetivo

Revisar cambios locales, una rama, un archivo o una PR con foco en:
- bugs y regresiones
- seguridad
- tests faltantes
- mantenibilidad

## Entrada

`$ARGUMENTS`

Si no se proveen argumentos, revisar cambios locales no commiteados.

## Flujo

### 1. Construir contexto del cambio

Usar según corresponda:

```bash
git status -s
git diff --stat
git diff
git log --oneline -5
```

Si el argumento apunta a una rama o PR, obtener el diff correspondiente antes de revisar.

### 2. Revisar por severidad

Priorizar:
- lógica incorrecta
- riesgo de seguridad
- regresiones funcionales
- ausencia de tests en cambios relevantes

### 3. Formato del resultado

- Hallazgos primero, ordenados por severidad
- Referencias concretas a archivo y línea cuando aplique
- Resumen breve solo al final

## Checklist mínimo

- [ ] El cambio hace lo que promete
- [ ] No introduce bugs obvios
- [ ] No rompe contratos existentes
- [ ] No expone secretos o entradas inseguras
- [ ] Tiene tests o justificación de por qué no hacen falta

## Salida esperada

```markdown
## Findings

1. [Alta] archivo.ext:123 - descripción del problema
2. [Media] archivo.ext:45 - descripción del problema

## Resumen

- Riesgo general: bajo|medio|alto
- Estado: aprobar|cambios requeridos
```
