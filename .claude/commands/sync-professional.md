---
name: sync-professional
description: Sincronización profesional completa: pull, commit, push y finalize
allowed-tools: Read, Write, Bash, Glob
---

# /sync-professional — Sincronización Profesional

Ejecuta el flujo completo de sincronización git en un solo comando.

## Uso

```bash
python .agent/skills-custom/sync-professional/scripts/main.py [opciones]
```

## Opciones

- `--force-commit`: Forzar commit incluso si no hay cambios nuevos
- `--skip-tests`: Saltar tests (modo emergencia)

## Flujo

1. **Git Pull** — Trae cambios del servidor
2. **Detectar Cambios** — Identifica archivos modificados/nuevos
3. **Tests** — Ejecuta tests según alcance
4. **Commit Inteligente** — Commitea cambios o secciones pasadas
5. **Push** — Sube al servidor
6. **Finalize** — Guarda memorias y actualiza estado

## Cuándo usar

- Al terminar una sesión de trabajo
- Antes de cambiar de PC
- Para mantener el repo sincronizado
- Como替代 a /finalize + /git-pushing combinados

