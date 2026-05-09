---
description: Guarda primero la memoria del proyecto y luego hace commit y push a GitHub.
universal: true
aliases:
  - git-pushing
  - push-with-memory
---

# /git-pushing - Memoria primero, Git después

// turbo-all

## Objetivo

Antes de hacer `commit` y `push`, registrar en la memoria del proyecto qué se hizo en la sesión.

## Entrada

`$ARGUMENTS`

Si el usuario no da resumen, inferir uno corto desde el diff.

## Flujo

### 1. Revisar estado del repo

```bash
git status -s
git diff --stat
git log --oneline -5
```

Detectar explícitamente:
- cambios `staged`
- cambios `unstaged`
- archivos `untracked`

Si hay mezcla (`staged` + `unstaged/untracked`), preguntar al usuario:
- **Agrupar** todo en un commit
- **Separar** y commitear solo lo staged

### 2. Actualizar memoria del proyecto

Actualizar `ESTADO_PROYECTO.md`:
- cambiar la línea `> Última actualización:` a la fecha actual
- insertar una nueva sección de sesión antes de la primera sección histórica `## Sesión` existente
- resumir solo cambios significativos
- incluir validaciones reales ejecutadas

Formato:

```markdown
## Sesión YYYY-MM-DD — resumen breve

### Cambios realizados
| Área | Estado |
|---|---|
| archivo o módulo | cambio principal |

### Validación
- resultado relevante
```

### 3. Preparar staging

Usar el script del skill para aplicar la decisión anterior:

```bash
bash .agent/skills/git-pushing/scripts/smart_commit.sh "<mensaje>" --group
```

o

```bash
bash .agent/skills/git-pushing/scripts/smart_commit.sh "<mensaje>" --separate
```

### 4. Crear commit y push

El script realiza commit y push a la rama actual con upstream (`-u`) si hace falta.

Si la rama actual no es `main`, usar la rama actual y no forzar push.

### 5. Verificación post-push

Verificar `git status` limpio y reportar si quedaron cambios locales.

### 6. Reporte final

```text
✅ Git push completado
📝 Memoria actualizada primero
📦 Commit: <hash> - <mensaje>
🚀 Push: OK
🧹 Estado post-push: limpio | con cambios locales
```

## Reglas

- Si hay conflictos de rebase o push, parar y explicarlos.
- Si no hay cambios locales, no crear commit vacío.
- No saltarse la actualización de memoria salvo que el usuario lo pida explícitamente.
