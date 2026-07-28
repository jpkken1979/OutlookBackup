# /merge-and-clean — Mergear a main y limpiar rama

Flujo automatizado para mergear la rama actual a `main`, limpiar cambios locales
y deletear la rama del origen. Ideal después de terminar una feature o fix.

---

## PASO 1 — Validaciones previas

```bash
git status
git log origin/main..HEAD --oneline
git diff main..HEAD --stat
```

- Verificá que estás en una rama (no en `main` ya)
- Verificá que no hay cambios sin commitear (si los hay, ofrece commitearlos primero con `/finalize`)
- Listá los commits locales que se van a mergear
- Verificá qué archivos cambiarían en main

**Si estás ya en `main`:** informá que no hay rama para mergear. Si tiene cambios sin pushear, ofrece pushear directo.

**Si hay cambios sin commitear:** sugierí `/finalize` primero para completar el ciclo.

**Si hay conflictos potenciales:** corré `git diff main...HEAD` y reportá qué archivos entran en conflicto.

---

## PASO 2 — Traer cambios remotos

```bash
git fetch origin main 2>&1 | tail -3
git status -sb
```

- Traé los cambios más recientes de `origin/main`
- Verificá si la rama está adelantada, atrás o divergente

**Si está atrás de main:** `git rebase origin/main` (rebasa la rama sobre main remoto)

**Si está divergente (adelantada Y atrás):** reportá y preguntá:
- ¿Mergear con `--rebase` (lineal)?
- ¿Mergear con `--no-ff` (mantener historia de rama)?

---

## PASO 3 — Actualizar ESTADO_PROYECTO.md EN LA RAMA (si aplica)

**IMPORTANTE:** Esto debe hacerse EN LA RAMA, ANTES de mergear (asegura atomicidad).

Si la rama que estás por mergear tenía cambios significativos:

1. Abrí `ESTADO_PROYECTO.md` (en la rama actual, NO en main)
2. Agregá una entrada en la sección de sesión/trabajo:
   ```
   - ✅ [descripción del trabajo completado en esta rama]
   ```
3. Committeá este cambio:
   ```bash
   git add ESTADO_PROYECTO.md
   git commit -m "chore(proyecto): actualizar estado — [rama completada]"
   ```

**Beneficio:** Cuando mergees a main (PASO 4), el merge commit atomicamente incluye
código + ESTADO_PROYECTO.md. Nada queda fuera de sync.

**Si la rama NO tenía cambios significativos (solo fixes chicos):** podés skipear este PASO.

---

## PASO 4 — Mergear a main

```bash
git checkout main
git merge <rama-actual> --no-ff -m "merge: <descripcion breve>"
```

- Cambiate a `main`
- Mergeá con `--no-ff` (crea un merge commit, preserva historia)
- Usa mensaje descriptivo en español

**Si hay conflictos:** detente y reportá. El usuario debe resolverlos manualmente.

**Si el merge es exitoso:** continuá al PASO 5.

---

## PASO 5 — Limpiar rama local

```bash
git branch -d <rama-actual>
```

- Deletea la rama local (solo si el merge fue exitoso)
- `-d` falla si hay cambios sin mergear (previene accidentes)

**Si `-d` falla:** usá `-D` solo si estás 100% seguro de que querés perder la rama.

---

## PASO 6 — Limpiar rama remota (opcional)

```bash
git push origin --delete <rama-actual> 2>&1 | tail -2
```

- Deletea la rama del origin
- Reportá el resultado

**Si fallas a deletear del origin:** es un warning, no un bloqueante. Reportá y sugierí limpiar manualmente después.

---

## PASO 7 — Push a main

```bash
git push origin main
```

- Pusheá los cambios (incluyendo el merge commit) a `origin/main`

**Si falla porque `main` divergió:** reportá y sugierí `git pull --rebase` antes de reintentar.

---

## PASO 8 — Limpiar stash local (si quedó)

```bash
git stash list
```

- Verificá si quedó algo en stash (cambios guardados durante el merge)
- Si hay stash: preguntá si descartarlo o aplicarlo

---

## PASO 9 — Reporte final (estructurado)

```
✅ Rama: <nombre> mergeada a main
✅ Commits mergeados: <N>
✅ Archivos modificados: <lista>
✅ Push: origin/main
✅ Limpieza: rama local deleteda, rama remota deleteda
✅ Stash: limpio

Cambios en main:
- [lista de cambios]

Pendiente:
- [si hay PRs asociadas o trabajos relacionados]
```

---

## Reglas universales

- **Nunca** mergees a `main` sin haber testeado la rama primero (`/finalize` incluye tests)
- **Nunca** uses `--force-delete` en la rama remota sin confirmación explícita del usuario
- Si la rama tiene asociación con una PR abierta en GitHub, cerála automáticamente con el merge commit
- Después de limpiar, verificá que no quedó nada en stash o worktrees

---

## Compatibilidad

Este comando funciona con:
- Claude Code (`/merge-and-clean`)
- Cursor, Windsurf, Copilot (pega el contenido como prompt)
- Automatización: puede invocarse desde scripts de CI/CD si `GH_TOKEN` está disponible
