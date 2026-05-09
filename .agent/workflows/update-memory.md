---
description: Actualización universal de memoria de proyecto basada en el comando legacy update-memory.
universal: true
aliases:
  - update-memory
  - memory-sync
---

# /update-memory - Actualizar memoria del proyecto

## Objetivo

Registrar cambios significativos de la sesión en la memoria documental del proyecto.

## Entrada

`$ARGUMENTS`

Objetivos sugeridos:
- `all`
- `estado`
- `session`

## Flujo

### 1. Recopilar cambios reales

Usar:

```bash
git status -s
git diff --stat
git log --oneline -5
```

### 2. Actualizar memoria

Prioridad:
- `ESTADO_PROYECTO.md`
- `CLAUDE.md` solo si cambió el contrato operativo

### 3. Registrar solo cambios significativos

No listar ruido trivial. Agrupar por áreas.

## Estructura recomendada

```markdown
## Sesión YYYY-MM-DD — resumen breve

### Cambios realizados
| Área | Estado |
|---|---|
| área | cambio |

### Validación
- comando o resultado relevante
```
