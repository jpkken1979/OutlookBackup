# /ramas — Auditoría de ramas, relevancia y limpieza

Analiza todas las ramas locales y remotas, determina cuáles están mergeadas,
cuáles tienen contenido útil y cuáles son basura. Limpia con confirmación.

---

## FILOSOFÍA

> "Las ramas abandonadas son deuda técnica invisible."

Reglas de oro:
1. **Nunca borres una rama sin verificar que su contenido ya está en main** (o es irrelevante)
2. **Si tiene commits únicos**, analiza si vale la pena cherry-pickear antes de eliminar
3. **Siempre pide confirmación** antes de eliminar ramas remotas
4. **Documenta lo que encontraste** aunque no lo borres

---

## FASE 1 — Inventario completo

### 1.1 Listar todas las ramas

```bash
git fetch --prune
git branch -a
```

### 1.2 Para cada rama, obtener:

```bash
# Último commit y fecha
git log <branch> --oneline -1 --format="%h %ai %s"

# Divergencia respecto a main (commits adelante/atrás)
git rev-list --left-right --count main...<branch>
```

Construir una tabla:

```
| Rama | Último commit | Fecha | Adelante | Atrás | Estado |
```

---

## FASE 2 — Clasificación automática

Clasifica cada rama en una de estas categorías:

### MUERTA (eliminar con seguridad)
Criterios (cumplir TODOS):
- 0 commits adelante de main
- Solo atrás (todos sus commits ya están en main)
- No es una rama de release o protegida

### HUÉRFANA (probablemente eliminar)
Criterios:
- Solo 1-2 commits adelante
- Commit es solo "Initial plan", docs, o cosmético
- Más de 15 commits atrás de main

### CON CONTENIDO (requiere análisis)
Criterios:
- 3+ commits adelante de main
- Contiene código funcional (no solo docs/plans)

### ACTIVA (no tocar)
Criterios:
- Tiene commits recientes (< 7 días)
- Es la rama actual
- Es main/master/develop

---

## FASE 3 — Análisis de contenido para ramas CON CONTENIDO

Para cada rama clasificada como "CON CONTENIDO":

### 3.1 Listar commits únicos

```bash
git log main..<branch> --oneline
```

### 3.2 Para cada commit, verificar si ya está en main

Método:
1. `git show <hash> --stat` — ver qué archivos cambiaron
2. Para archivos clave, verificar en main:
   - `git show main:<filepath>` — el archivo existe en main?
   - `git log main -- <filepath> --oneline -3` — fue tocado recientemente?
   - Comparar contenido: el cambio del commit ya está reflejado en main?

### 3.3 Clasificar cada commit

| Estado | Significado |
|--------|-------------|
| YA EN MAIN | El cambio existe en main (mismo contenido, distinto hash) |
| PARCIAL | Parte del cambio está en main, parte no |
| NO EN MAIN | Cambio completamente ausente de main |

### 3.4 Evaluar valor de lo que NO está en main

Para commits NO EN MAIN, evaluar:
- Es un fix de seguridad? → **Alta prioridad**, cherry-pick
- Es una feature funcional? → Evaluar si sigue siendo relevante
- Es solo docs/cosmético? → Baja prioridad
- Tiene dependencias con otros commits? → Requiere merge, no cherry-pick
- Cuántos conflictos tendría? → Si >20 commits atrás, conflictos probables

---

## FASE 4 — Reporte

Genera un reporte con este formato:

```
══════════════════════════════════════════════════
  REPORTE DE RAMAS — [FECHA]
══════════════════════════════════════════════════

  RESUMEN
  Total ramas: X (Y locales + Z remotas)
  Muertas: X
  Huérfanas: X
  Con contenido: X
  Activas: X

  MUERTAS (eliminar con seguridad)
  - codex/feature-x — 0 adelante, 18 atrás, todo mergeado
  [...]

  HUÉRFANAS (probablemente eliminar)
  - copilot/plan-x — 1 commit ("Initial plan"), 19 atrás
  [...]

  CON CONTENIDO (análisis detallado)
  ─── rama/nombre ───
  Commits únicos: X
  Ya en main: X
  No en main: X
  Valor de lo ausente:
    - [commit] — [descripción] — CHERRY-PICK / IRRELEVANTE
  Recomendación: [eliminar / cherry-pick + eliminar / mantener]
  [...]

  ACTIVAS (no tocar)
  - main
  [...]

  ACCIONES RECOMENDADAS
  1. Eliminar ramas muertas: [lista]
  2. Cherry-pick de: [lista de commits]
  3. Eliminar tras cherry-pick: [lista]
  4. Mantener: [lista y razón]
══════════════════════════════════════════════════
```

---

## FASE 5 — Ejecución (con confirmación)

**Mostrar el reporte al usuario y pedir confirmación antes de ejecutar.**

### 5.1 Cherry-picks (si los hay)

Para cada commit a cherry-pickear:

```bash
git cherry-pick <hash> --no-commit
git diff --cached --stat     # Verificar cambios
git commit -m "<mensaje original>

Cherry-pick de <hash> — [razón].

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Si hay conflictos: reportar al usuario, no forzar.

### 5.2 Eliminar ramas muertas y huérfanas

```bash
# Locales
git branch -D <rama>

# Remotas (una por una para ver errores)
git push origin --delete <rama>
```

### 5.3 Push si hubo cherry-picks

```bash
git push
```

### 5.4 Verificación final

```bash
git branch -a
```

Confirmar que solo quedan ramas activas.

---

## Opciones de invocación

```
/ramas              → auditoría completa (todas las fases)
/ramas --solo-audit → solo fases 1-4 (reporte sin eliminar nada)
/ramas --limpiar    → solo eliminar ramas ya clasificadas como muertas
```

---

## Compatibilidad

Este comando funciona con:
- Claude Code (`/ramas`)
- Cursor — pega el contenido como prompt de sistema
- Windsurf, GitHub Copilot, cualquier AI — las fases son autoexplicativas
- También ejecutable manualmente siguiendo las fases en orden
