# /finalize — Cerrar trabajo, validar, revisar y sincronizar

Ejecuta este flujo completo cada vez que terminás una tarea o sesión de desarrollo.
Nunca saltes un paso. Si uno falla, detente y reportá antes de continuar.

> Version 3.0 — incluye verificaciones de integridad, stash, divergencia, y conflictos.

---

## PASO 0 — Resumen de sesión (auto-save)

Antes de cualquier validación, genera un resumen de la sesión actual:

1. Identificá TODO lo que se hizo en esta sesión (cambios, decisiones, descubrimientos)
2. Creá un archivo `.claude/memory/session_YYYY-MM-DD.md` con formato:

```markdown
---
name: Sesion YYYY-MM-DD — [tema principal]
description: [una linea]
type: project
auto_saved: true
trigger: session
date: YYYY-MM-DD
---

## Que se hizo
- [lista de cambios]

## Decisiones tecnicas
- [decisiones no obvias y por que]

## Descubrimientos
- [gotchas, comportamiento inesperado]

## Pendiente
- [lo que quedo fuera]
```

3. Si hay descubrimientos o decisiones importantes, crear archivos adicionales:
   - `discovery_{topic}.md` para gotchas
   - `decision_{topic}.md` para decisiones de arquitectura
   - `bugfix_{topic}.md` para bugs resueltos con root cause

---

## PASO 1 — Inventario completo de cambios

```bash
git status
git diff --stat
git stash list
git fsck --full 2>&1 | tail -5
```

- Lista qué archivos cambiaron (tracked + **untracked**)
- Verificá si hay **archivos sin trackear** que deberían estar (nuevos scripts, configs, etc.)
- Verificá si hay algo en **stash** (cambios guardados que no se commitearon)
- Corré `git fsck` para verificar integridad del repo

**Si hay archivos untracked nuevos:** preguntá al usuario si deben incluirse o ignorarse.

**Si hay stash:** informá qué hay y sugierí que se commitee o se descarte antes de continuar.

**Si `git fsck` reporta errores:** detener y reportar antes de continuar.

---

## PASO 1.5 — Verificar divergencia vs origin

```bash
git fetch origin 2>&1 | tail -3
git status -sb | head -5
```

- Si la rama está **atrás de origin**: `git pull` antes de continuar
- Si está **adelantada y atrás** (divergente): informar al usuario antes de continuar
- Si está **solo adelantada**: normal, se pusheara al final

---

## PASO 1.7 — Verificar conflictos sin resolver

```bash
grep -rE "<<<<<<<|=======|>>>>>>" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.rs" --include="*.md" . 2>/dev/null | head -10
```

- Buscar marcadores de conflicto en archivos del proyecto
- Si se encuentran: **detener** y reportar antes de continuar

---

## PASO 2 — Tests según el alcance

Ejecuta **solo los tests relevantes** a los archivos cambiados. No corras todo si no es necesario.

### Si cambiaron archivos Python (`.agent/`, `src/`, `tests/`):
```bash
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -20
```
Si falla algún test — **detente**, mostrá el error, no continúes.

### Si cambiaron archivos TypeScript/React (`nexus-app/src/`, `src/`):
```bash
cd nexus-app && npx tsc -b tsconfig.app.json --noEmit 2>&1 | head -20
cd nexus-app && npm run lint 2>&1 | head -20
cd nexus-app && npm test -- --run 2>&1 | tail -20
```

### Si cambiaron archivos Rust (`nexus-app/src-tauri/`):
```bash
cd nexus-app/src-tauri && cargo check 2>&1 | grep -E "^error" | head -20
```

### Si cambiaron archivos del bot (`src/`):
```bash
npx tsc --noEmit 2>&1 | head -20
npm test -- --run 2>&1 | tail -20
```

Si todos los tests pasan -> continua al paso 2.5.
Si alguno falla -> mostrá el error completo y preguntá al usuario como proceder.

---

## PASO 2.5 — Code review automatizado

```bash
git diff --cached --stat
git diff --stat
```

Revisá cada archivo cambiado buscando:
- **Seguridad**: secrets hardcodeados, shell=True, inputs sin validar
- **Calidad**: funciones sin type hints, código duplicado, TODOs sin plan
- **Consistencia**: nombres en idioma incorrecto, imports no usados
- **Performance**: queries N+1, loops innecesarios, falta de caching

Si encontrás problemas críticos (seguridad), corregirlos ANTES de continuar.
Si encontrás problemas menores, listarlos en el reporte final como "mejoras sugeridas".

Para Python, ejecutar también:
```bash
ruff check --diff .agent/ 2>&1 | head -30
```

Para TypeScript (nexus-app), ejecutar:
```bash
cd nexus-app && npm run lint 2>&1 | head -20
```

---

## PASO 3 — Guardar en memoria persistente (3 sistemas)

Guardá un resumen completo en **los 3 sistemas** de memoria:

### 3.1 Auto-memory de Claude Code

Crear o actualizar un archivo en `~/.claude/projects/<slug-del-repo-actual>/memory/` con:

- Nombre: `project_<tema>_<YYYY_MM_DD>.md`
- Frontmatter: name, description, type: project
- Contenido:
  - Qué se implementó o corrigió
  - Decisiones técnicas no obvias
  - Problemas encontrados y cómo se resolvieron
  - Causa raíz si hubo debugging
  - Advertencias para el futuro
  - Lista de commits con hashes

Antes de escribir:

1. Derivá el slug del repo actual desde `git rev-parse --show-toplevel`
2. Convertí la ruta del repo al formato que usa Claude en `~/.claude/projects/`
3. Si no existe esa carpeta de auto-memory, omití este paso y continuá

Actualizar `MEMORY.md` con un puntero al nuevo archivo si existe un índice local equivalente.

### 3.2 MCP antigravity-memory (mem0)

Si el gateway está activo, guardar también en mem0:

```
memory_store({
  content: "[FECHA] Sesión: [descripción]. Cambios: [lista]. Decisiones: [por qué].",
  metadata: { type: "session", date: "YYYY-MM-DD" }
})
```

Si el gateway no responde, omitir silenciosamente (no bloquear el flujo).

### 3.3 Brain Network (conocimiento estructurado)

Ingestar la sesión en el Brain Network para que el conocimiento sea consultable
con cross-refs, expansión semántica, y temporal decay:

```python
import sys; sys.path.insert(0, '.agent')
from core.brain import Brain
from pathlib import Path

brain = Brain(Path('.agent/brain'), app_id='nexus-mother')
brain.ingest(
    title="Sesion YYYY-MM-DD — [tema principal]",
    context="[que se hizo y por que]",
    decisions="[decisiones tecnicas tomadas]",
    output="[archivos creados/modificados, commits]",
    pending="[lo que quedo pendiente]",
    area="[dev|ops|ux|business|architecture|security]",
    tags=["[tags relevantes]"],
    node_type="session",
    importance="[normal|high|critical]",
)
```

Si hubo **bugs resueltos**, crear nodo adicional tipo `pattern`:
```python
brain.ingest(
    title="Fix: [descripcion del bug]",
    context="Sintoma: [que pasaba]. Root cause: [por que].",
    decisions="Fix: [como se arreglo]. Prevencion: [como evitarlo].",
    area="ops",
    tags=["bugfix", "root-cause", "[area afectada]"],
    node_type="pattern",
    importance="high",
)
```

Si hubo **decisiones de arquitectura**, crear nodo tipo `adr`:
```python
brain.ingest(
    title="Decision: [que se decidio]",
    context="[contexto y motivacion]",
    decisions="[la decision y alternativas descartadas]",
    area="architecture",
    tags=["decision", "adr", "[area]"],
    node_type="adr",
    importance="high",
)
```

---

## PASO 4 — Actualizar ESTADO_PROYECTO.md

Si los cambios son significativos (nueva feature, fix importante, refactor):

1. Leé el archivo `ESTADO_PROYECTO.md`
2. Actualizá la fecha de última actualización
3. Agregá una entrada en la sección de la sesión actual con fecha de hoy
4. Actualizá el estado verificado si corresponde

---

## PASO 4.5 — Sincronizar Brain con docs del repo (auto-ingest)

Si tocaste cualquier `.md` del repo (CLAUDE.md, RULES.md, `.claude/rules/`, `docs/`, `nexus-app/CLAUDE.md`, README, etc.), corré el crawler para que el Brain absorba los cambios:

```bash
python .agent/scripts/repo_crawler.py --apply
```

Comportamiento esperado:
- **Idempotente**: si nada cambió en los .md whitelisted, devuelve `0 nuevos, 0 actualizados, 0 archivados` y termina rápido (segundos).
- Si hay nuevos .md → ingesta nodos al Brain con tags semánticos canónicos (`nexus`, `arari`, `kobetsu`, etc.) y cross-linking automático.
- Si renombraste/borraste .md → archiva los nodos huérfanos (`status="archived"`).
- Si modificaste un .md ya ingestado → actualiza el nodo existente (mismo slug, hash nuevo).

Ver `.claude/rules/repo-crawler.md` para política completa de tags y paths.

---

## PASO 5 — Commit

Construí el mensaje de commit siguiendo las reglas del proyecto:
```
<type>(<scope>): <descripción en español>

[cuerpo opcional con detalles si hace falta]

Co-Authored-By: Claude <noreply@anthropic.com>
```

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Reglas:
- Descripción en **español**
- Scope en inglés (nombre del módulo)
- Máximo 72 caracteres en la primera línea
- Si hay múltiples cambios no relacionados, usá **commits separados**

```bash
git add <archivos específicos — no usar git add -A ciegamente>
git commit -m "..."
```

---

## PASO 5.5 — Verificación de archivos dejados atrás

Después del commit, verificá que no quedó nada sin commitear:

```bash
git status --short
```

Si hay **archivos sin trackear que deberían existir** (nuevos archivos creados durante la sesión): preguntá al usuario si incluirlos.

Si hay **archivos en staging que no se commitearon**: agregarlos y hacer commit adicional.

---

## PASO 6 — Push

```bash
git push
```

Si falla porque la rama divergió:
1. Mostrá el error al usuario
2. Proponé: `git pull --rebase` o `git push --force-with-lease` según el contexto
3. **No hagas force push a main/master sin confirmación explícita**

---

## PASO 6.5 — Sincronizar memorias al repositorio

Copiar las memorias creadas en el PASO 0 y PASO 3 al repositorio para sincronizar entre PCs:

1. Verificar que `.claude/memory/` existe en el repositorio
2. Los archivos de sesión ya fueron creados en PASO 0
3. Verificar que están incluidos en el commit (si no, hacer commit adicional):

```bash
git add .claude/memory/*.md
git diff --cached --name-only | grep ".claude/memory"
```

Si hay archivos de memoria pendientes, commitearlos:
```bash
git commit -m "chore(memory): sincronizar memorias de sesion"
git push
```

**CRITICO**: No dejar memorias sin commitear. El usuario trabaja en múltiples PCs.

---

## PASO 6.7 — Sincronizar Brain al repositorio

Verificar que el Brain quedó sincronizado en git:

```bash
git status --short .agent/brain/
```

Si hay cambios sin commitear en el Brain:
```bash
git add .agent/brain/concepts/ .agent/brain/sessions/ .agent/brain/patterns/ .agent/brain/index.md .agent/brain/log.md 2>/dev/null
git diff --cached --stat
git commit -m "chore(brain): sincronizar brain network"
git push
```

---

## PASO 7 — Reporte final

Mostrá un resumen conciso:

```
✅ Repo integrity: OK (git fsck passed)
✅ Tests: X passaram / 0 fallaron
✅ Stash: limpio (sin cambios sin commitear)
✅ Conflictos: ninguno
✅ Memoria: actualizada (auto-memory + mem0 + brain)
✅ ESTADO_PROYECTO.md: actualizado
✅ Commit: <hash> — <mensaje>
✅ Push: origin/<rama>
✅ Brain: sincronizado en git

Cambios incluidos:
- [lista de lo que se hizo]

Pendiente (si hay):
- [si hay algo que quedó fuera o fue dejado para después]
```

---

## Reglas universales

- **Nunca** commitees archivos `.env`, secretos, o credenciales
- **Nunca** uses `git add -A` sin revisar primero `git status`
- **Nunca** hagas push si los tests fallan
- Si hay cambios no commiteados en stash o worktrees, mencionarlos
- Si el usuario pide solo un subconjunto (ej. "solo commiteá los tests"), respetá eso
- Después de compilar Nexus, **siempre** copiar instaladores a `nexus-app/Compilacion/`

## Compatibilidad

Este comando funciona con:
- Claude Code (`/finalize`)
- Cursor (pega el contenido como prompt)
- Windsurf, Copilot, cualquier AI — las instrucciones son autoexplicativas
