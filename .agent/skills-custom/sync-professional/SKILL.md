---
name: sync-professional
description: "Sincronización profesional completa: pull, commit secciones pasadas, push y finalize en un solo comando. Detecta cambios pendientes, commitea memorias y work en progreso, ejecuta tests y mantiene el repositorio sincronizado entre múltiples PCs."
category: workflow
version: "2.0.0"
author: Antigravity Ecosystem
tags: [git, sync, workflow, finalize, memorias, multi-pc]
status: active
interface:
  inputs:
    - name: force_commit
      type: boolean
      description: "Forzar commit incluso si no hay cambios nuevos (útil para commitear secciones pasadas)"
      default: false
    - name: skip_tests
      type: boolean
      description: "Saltar ejecución de tests (usar solo en emergencias)"
      default: false
    - name: target_branch
      type: string
      description: "Rama target para el push (default: rama actual)"
      default: "current"
---

# Sincronización Profesional Completa

Ejecuta el flujo completo de sincronización git para mantener el repositorio actualizado entre múltiples PCs y workstations.

## Use this skill when

- Terminaste una sesión de trabajo y querés sincronizar todo
- Vas a cambiar de PC y necesitás commitear todo el progreso
- Querés asegurar que las memorias, cambios y work en progreso estén guardados
- Necesitas hacer pull + commit + push + finalize en un solo comando

## Do not use this skill when

- Solo necesitas hacer pull (usá `git pull` directo)
- Solo necesitás commitear archivos específicos (usá `/git-pushing`)
- Estás en una rama de feature donde no debería haber push

## Context

Esta skill combina:
1. **Git Pull** — Trae cambios del servidor (detecta conflictos)
2. **Detectar Cambios** — Identifica archivos modificados, memorias, work en progreso
3. **Commit Inteligente** — Si no hay cambios nuevos, commitea secciones pasadas
4. **Tests** — Ejecuta tests según alcance (Python/TS/Rust)
5. **Push** — Sube cambios al servidor
6. **Finalize** — Guarda memorias, actualiza ESTADO_PROYECTO.md

## Instructions

### PASO 0 — Git Pull

```bash
git pull origin $(git branch --show-current)
```

- Si hay conflictos, DETENTE y reporte al usuario
- Si hay cambios nuevos del servidor, integrarlos primero
- Verificar que `ESTADO_PROYECTO.md` y `CLAUDE.md` no tengan merge conflicts

### PASO 1 — Detectar Cambios

```bash
git status
git diff --stat
```

Identificar:
- Archivos modificados (tracked)
- Archivos nuevos (untracked)
- Archivos eliminados
- Cambios en `.claude/memory/`
- Cambios en `ESTADO_PROYECTO.md`

### PASO 2 — Tests según Alcance

Ejecutar **solo los tests relevantes**:

**Python (`.agent/`, `src/`):**
```bash
python -m pytest tests/core/ -x --tb=short -q 2>&1 | tail -20
```

**TypeScript Nexus (`nexus-app/`):**
```bash
cd nexus-app && npm run ts:app 2>&1 | head -20
cd nexus-app && npm run lint 2>&1 | head -20
cd nexus-app && npm test -- --run 2>&1 | tail -20
```

**Bot TypeScript (`src/`):**
```bash
npm test -- --run 2>&1 | tail -20
```

Si algún test falla → DETENER y reportar.

### PASO 3 — Commit Inteligente

**Si hay cambios nuevos:**
```bash
git add <archivos específicos>
git commit -m "tipo(scope): descripción en español"
```

**Si NO hay cambios nuevos (solo secciones pasadas):**
- Commitear `.claude/memory/*.md` si existen memorias nuevas
- Commitear `ESTADO_PROYECTO.md` si se actualizó
- Commitear archivos de work en progreso (drafts, snippets, etc.)

**Reglas de commit:**
- Mensaje en español, scope en inglés
- Máximo 72 caracteres primera línea
- `Co-Authored-By: Claude <noreply@anthropic.com>`
- Separar commits no relacionados

### PASO 4 — Push

```bash
git push origin $(git branch --show-current)
```

Si falla por divergencia:
- Proponer `git pull --rebase`
- Nunca force push a main/master sin confirmación

### PASO 5 — Finalize

Ejecutar el flujo completo de `/finalize`:
- Resumen de sesión
- Code review automatizado
- Guardar en memoria persistente
- Actualizar ESTADO_PROYECTO.md

### PASO 6 — Reporte Final

```
✅ Pull: actualizado
✅ Tests: X pasaron / 0 fallaron
✅ Commit: <hash> — <mensaje>
✅ Push: origin/<rama>
✅ Memoria: sincronizada
✅ ESTADO_PROYECTO.md: actualizado

Estado final: listo para cambiar de PC o cerrar sesión
```

## Recursos

- `/finalize` — Flujo completo de cierre de sesión
- `/git-pushing` — Stage, commit y push
- `/sync-memories` — Sincronizar memorias al repo
- `CLAUDE.md` — Convenciones del proyecto
- `.claude/rules/commits.md` — Formato de commits
