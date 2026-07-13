# Regla: Sistema de Memoria — Jerarquia Unificada

Aplica a todas las sesiones de Claude Code en este repositorio.

> **Consolidado de `memory-engine.md` + `memory-sync.md`** (2026-05-09).
> Las规则的 anteriores estaban duplicadas y contenían contradicciones.
> Esta versión unificada es la fuente de verdad.

---

## 1. Jerarquia de Capas

El proyecto tiene **TRES capas de memoria**. Entender cual es cual evita perder
informacion y sobrescribir decisiones previas.

| Capa | Ubicacion | Proposito | Versionado | Fuente de verdad |
|---|---|---|---|---|
| **1. Memorias markdown** | `.claude/memory/*.md` | Decisiones, bugfixes, patrones, sesiones | Git | **Si** |
| **2. Brain Network** | `.agent/brain/` (concepts/, sessions/, patterns/) | Conocimiento estructurado con cross-refs, tags, decay | Git | **Si** |
| **3. Mem0 semantica** | Gateway `:4747` + `~/.antigravity/memory/` | Recall semantico automatico (opcional) | No (local) | No — cache volatil |

### Regla critica sobre fuente de verdad

- **Capas 1 y 2 son la fuente de verdad** porque viven en git y sincronizan entre PCs.
- **Capa 3 es cache auxiliar**: si el gateway esta caido, el sistema no pierde memoria
  porque capas 1 y 2 siguen funcionando.
- Nunca tratar `~/.antigravity/memory/` como fuente de verdad — es regenerable.

---

## 2. Cuando usar cada capa

### Capa 1: `.claude/memory/` (default para cierre de sesion)

Archivos markdown individuales con formato:

```markdown
---
name: {nombre descriptivo}
description: {una linea para relevancia futura}
type: {project|feedback|reference}
trigger: {decision|bugfix|discovery|pattern|config|session}
date: YYYY-MM-DD
---

{contenido}
```

Nombres: `decision_{topic}.md`, `bugfix_{topic}.md`, `discovery_{topic}.md`,
`pattern_{topic}.md`, `config_{topic}.md`, `session_{date}.md`.

El archivo indice `.claude/memory/MEMORY.md` lista todas las memorias; se
actualiza manualmente o via `/session-summary`.

### Capa 2: Brain Network (default para conocimiento estructurado)

API Python:

```python
import sys; sys.path.insert(0, '.agent')
from core.brain import Brain
from pathlib import Path

brain = Brain(Path('.agent/brain'), app_id='nexus-mother')
brain.ingest(
    title="...",
    context="...",
    area="...",           # ej. "memory", "nexus", "brain"
    tags=[...],
    node_type="...",      # session|concept|adr|decision|pattern|entity
    importance="...",     # low|medium|high|critical
)
```

Slash commands: `/brain query`, `/brain ingest`, `/brain stats`, `/brain lint`,
`/brain traverse`, `/brain consolidate`.

**Siempre correr `brain.rebuild_index()` al final de la sesion** para mantener
`.agent/brain/index.md` sincronizado. El hook `Stop` lo hace automaticamente
via `.agent/scripts/rebuild_brain_index.py`.

### Capa 3: Mem0 via gateway (opcional, solo si el gateway esta corriendo)

Condiciones para que este activa:
1. Servidor MCP `antigravity-memory` registrado en `.mcp.json`.
2. Gateway responde en `http://127.0.0.1:4747/v1/health`.
3. Endpoints `/v1/mem0/recall`, `/v1/mem0/store`, `/v1/mem0/stats` responden.

Si cualquiera falla, los hooks encolan eventos en
`~/.antigravity/memory/hooks/pending-events.jsonl` y los envian cuando el
gateway vuelve.

**No asumir que mem0 esta activo**: siempre escribir tambien en capas 1 y/o 2.

---

## 3. Politica de auto-save

Despues de acciones significativas, guardar en AMBAS capas 1 y 2 (no solo una).
Detalle completo de triggers en `.claude/rules/auto-save-triggers.md`.

### Triggers criticos

| Trigger | Capa 1 (archivo) | Capa 2 (node_type) |
|---|---|---|
| Decision de arquitectura | `decision_{topic}.md` | `decision` o `adr` |
| Bug resuelto con root cause | `bugfix_{topic}.md` | `pattern` (con area=bugfix) |
| Descubrimiento o gotcha | `discovery_{topic}.md` | `concept` |
| Patron o convencion | `pattern_{topic}.md` | `pattern` |
| Cambio de config critica | `config_{topic}.md` | `concept` (area=config) |
| Cierre de sesion (3+ cambios) | `session_{date}.md` | `session` |

---

## 4. Git y Sincronizacion entre PCs

### Regla de hierro

**Toda memoria generada durante la sesion DEBE estar en git antes de cerrar.**
Si no se sube, se pierde cuando cambies de PC.

### Flujo de cierre de sesion

1. **Capa 1** (`.claude/memory/`): el hook `memory-sync.sh` corre automatico en
   Stop y copia de `~/.claude/projects/`. Verificar que los archivos quedaron
   en el working tree antes de salir.
2. **Capa 2** (`.agent/brain/`): el hook Stop corre
   `rebuild_brain_index.py` automaticamente — pero eso solo reconstruye `index.md`.
   **NO alcanza**. Hay que hacer `git add` y `git commit` de TODOS los cambios
   del brain generados durante la sesion.
3. **Commit + push automatico**: al cerrar cualquier sesion (incluyendo `/finalize`,
   `/git-pushing`, `/session-summary` y el hook Stop), SIEMPRE ejecutar:

   ```bash
   # Ver que cambio en el brain
   git status .agent/brain/ .claude/memory/
   # Si hay cambios sin commitear, hacer:
   git add .agent/brain/ .claude/memory/
   git commit -m "chore(memory): sincronizar memorias de sesion"
   git push
   ```

4. **Nunca irse sin hacer push de las memorias**. Si el push falla (offline,
   conflicto), avisar al usuario y no cerrar la sesion hasta resolverlo.
5. **Si hay cambios no relacionados con memorias** (codigo, configs), hacer
   commits separados — no mezclar memorias con cambios funcionales.

### Al iniciar sesion

Si `.claude/memory/MEMORY.md` existe en el repositorio, leerlo para recuperar
contexto de sesiones anteriores (incluso de otras PCs). El Brain Network
tambien se puede consultar via `/brain query` o `/recall`.

---

## 5. Excepciones validas en .gitignore para .claude/

El gitignore **SI** puede ignorar ciertos archivos/directorios de `.claude/`
cuando son efectivamente temporales o auto-generados:

| Ubicacion | Proposito | Por que se ignora |
|---|---|---|
| `.claude/worktrees/` | Worktrees temporales de Claude Code | Artefactos de sesion, no datos persistentes |
| `.claude/audit_report_*.md` | Reportes de auditoria auto-generados | Auto-regenerados por hooks, no son memoria operativa |
| `nexus-app/.claude/audit_report_*.md` | Mismo patron en subdirectorios | Mismo rationale |

**NO se ignora** (debe sincronizarse por git):
- `.claude/memory/*.md` — memorias reales del usuario
- `.claude/settings.json` — config del proyecto
- `.claude/rules/*.md` — reglas auto-inyectadas
- `.claude/commands/*.md` — slash commands
- `.claude/hooks/scripts/*.sh` — scripts de hooks
- `.claude/skills/` — skills instalados

---

## 6. Troubleshooting

| Problema | Diagnostico | Fix |
|---|---|---|
| Brain index incompleto | `wc -l .agent/brain/index.md` muestra < 50 lineas | `python .agent/scripts/rebuild_brain_index.py` |
| `.claude/memory/MEMORY.md` desactualizado | Faltan entradas recientes | Actualizar manualmente o via `/session-summary` |
| Mem0 no responde | Gateway offline | `python start_gateway.py` |
| Memorias en PC A no aparecen en PC B | No se commitearon | `git status` y commit/push |
| Eventos encolados crecen sin drenar | Gateway caido hace tiempo | Arrancar gateway; `flush_pending_events()` corre automatico |

---

## Fuentes canonicas

- Engine Brain Network: `.agent/core/brain.py`
- MCP memory server: `.agent/mcp/memory-server.py`
- Hooks de captura: `.agent/hooks/memory/` (session_start, session_stop, post_tool_use, user_prompt_submit)
- Script de rebuild: `.agent/scripts/rebuild_brain_index.py`
- Reglas relacionadas: `.claude/rules/auto-save-triggers.md`, `.claude/rules/proactive-memory.md`

---

## Historial de cambios

| Fecha | Cambio |
|---|---|
| 2026-05-09 | Consolidado de `memory-engine.md` + `memory-sync.md`. Eliminada duplicacion. Agregada seccion 5 de excepciones validas en gitignore. |