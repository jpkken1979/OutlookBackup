# Regla: Sistema de Memoria — Jerarquia Unificada

Aplica a todas las sesiones de Claude Code en este repositorio.

## Principio

El proyecto tiene TRES capas de memoria. Entender cual es cual evita perder
informacion y sobrescribir decisiones previas.

## Jerarquia de capas

| Capa | Ubicacion | Proposito | Versionado | Fuente de verdad |
|---|---|---|---|---|
| **1. Memorias markdown** | `.claude/memory/*.md` | Decisiones, bugfixes, patrones, sesiones | Git | Si |
| **2. Brain Network** | `.agent/brain/` (concepts/, sessions/, patterns/) | Conocimiento estructurado con cross-refs, tags, decay | Git | Si |
| **3. Mem0 semantica** | Gateway `:4747` + `~/.antigravity/memory/` | Recall semantico automatico (opcional) | No (local) | No — cache volatil |

### Regla critica sobre fuente de verdad

- **Capas 1 y 2 son la fuente de verdad** porque viven en git y sincronizan entre PCs.
- **Capa 3 es cache auxiliar**: si el gateway esta caido, el sistema no pierde memoria
  porque capas 1 y 2 siguen funcionando.
- Nunca tratar `~/.antigravity/memory/` como fuente de verdad — es regenerable.

## Cuando usar cada capa

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

## Politica de auto-save

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

## Git y sincronizacion entre PCs

- `.claude/memory/` **debe** estar en git (versionado).
- `.agent/brain/` **debe** estar en git (versionado).
- `~/.antigravity/memory/` **no va** en git (es cache local).
- Nunca agregar `.claude/memory/`, `.agent/brain/` o `.agent/hooks/memory/` al `.gitignore`.

El hook `Stop` corre `memory-sync.sh` para copiar auto-memorias de
`~/.claude/projects/.../memory/` (si existe) a `.claude/memory/`. Si esa
ubicacion esta vacia, no pasa nada — es esperado porque Claude Code no siempre
escribe ahi.

## Cuando el gateway esta caido

Detectable si:
- `session_start.py` no muestra `[Antigravity Memory] N memoria(s)`.
- `curl http://127.0.0.1:4747/v1/health` falla.
- Hay eventos en `~/.antigravity/memory/hooks/pending-events.jsonl`.

En ese caso **no pierdes memoria** — solo pierdes recall semantico automatico.
Las capas 1 y 2 (git) siguen funcionando. Para arrancar gateway:

```bash
python start_gateway.py
```

## Troubleshooting

| Problema | Diagnostico | Fix |
|---|---|---|
| Brain index incompleto | `wc -l .agent/brain/index.md` muestra < 50 lineas | `python .agent/scripts/rebuild_brain_index.py` |
| `.claude/memory/MEMORY.md` desactualizado | Faltan entradas recientes | Actualizar manualmente o via `/session-summary` |
| Mem0 no responde | Gateway offline | `python start_gateway.py` |
| Memorias en PC A no aparecen en PC B | No se commitearon | `git status` y commit/push |
| Eventos encolados crecen sin drenar | Gateway caido hace tiempo | Arrancar gateway; `flush_pending_events()` corre automatico |

## Fuentes canonicas

- Engine Brain Network: `.agent/core/brain.py`
- MCP memory server: `.agent/mcp/memory-server.py`
- Hooks de captura: `.agent/hooks/memory/` (session_start, session_stop, post_tool_use, user_prompt_submit)
- Script de rebuild: `.agent/scripts/rebuild_brain_index.py`
- Reglas relacionadas: `.claude/rules/auto-save-triggers.md`, `.claude/rules/memory-sync.md`, `.claude/rules/proactive-memory.md`
