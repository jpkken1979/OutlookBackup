---
name: jpkkenfull
description: Executor autónomo sin permisos. Recibe un objetivo libre, planifica, ejecuta completamente, usa los mejores agents/skills, se auto-mejora, consulta memoria/internet, y solo pregunta si está genuinamente confundido.
category: execution
version: "2.0.0"
author: K. Kaneshiro / Antigravity Ecosystem
tags:
  - autonomous
  - no-permission
  - self-improving
  - memory-aware
  - web-search
  - agents
  - skills
  - brain
status: active
interface:
  inputs:
    - goal
    - context
    - force_internet
    - skip_agents
  outputs:
    - execution_summary
    - files_modified
    - decisions_made
    - self_improvements
    - clarifications_asked
    - brain_nodes
---

# Jpkkenfull v2 — Executor Autónomo Sin Permisos

## Filosofía

**Ningún permiso, ninguna confusión.** Este skill ejecuta cualquier objetivo de principio a fin sin pedir confirmación en cada paso. Suena peligroso — y lo es — pero la diferencia con `--dangerously-skip-permissions` de Claude Code es que Jpkkenfull tiene:

1. **Un cerebro propio**: consulta memoria, Brain y reglas antes de actuar.
2. **Un radar de confusión**: si no sabe qué hacer, PREGUNTA (una sola vez, específicamente).
3. **Autosuperación real**: después de cada ejecución, lee learnings previos del Brain y guarda nuevas lecciones.
4. **Mejores herramientas**: siempre invoca el agent/skill más adecuado, no el primero que encuentra.
5. **Internet como fallback**: si no tiene info, busca en la web antes de preguntar.
6. **Guarda de destructividad**: operaciones peligrosas (`git reset --hard`, `rm -rf`, `DROP TABLE`) siempre preguntan antes.

## Diferencia con Autonomous Executor

| Aspecto | Autonomous Executor | Jpkkenfull v2 |
|---|---|---|
| Permisos por paso | Requiere aprobación | No pide nada |
| Clarification gate | No pide | Solo si está genuinamente perdido (con input real) |
| Uso de agents | Genérico | El mejor para la tarea + brain-informed |
| Auto-mejora | Solo writing | Learning loop real: brain.query al inicio + brain.save al final |
| Internet search | No | Sí (graceful degradation si endpoint falta) |
| Memoria/Brain | Al final nomás | Antes, durante y después |
| Self-improvement | No | Sí (lee learnings previos + guarda nuevas lecciones) |
| Abort mechanism | No | Sí (SIGINT/SIGTERM handler) |
| Critical ops guard | No | Sí (lista de ops peligrosas con confirmación) |

## Flujo interno v2

```
Objetivo
  ↓
[1] CONTEXT GATHERING
    ├── Consultar .claude/memory/ (MEMORY.md + decisiones relacionadas)
    ├── Brain query (LEARNING LOOP — busca learnings previos)
    │   └── "jpkkenfull: what worked for tasks like: [goal_keywords]"
    ├── Leer reglas del proyecto (.claude/rules/)
    ├── Detectar tipo de tarea (audit/fix/feat/refactor/docs)
    └── Git status
  ↓
[1b] INTERNET SEARCH (si falta info crítica)
    ├── Si endpoint existe → busca en web
    └── Si endpoint no existe → log warning y continuar (graceful degradation)
  ↓
[2] AGENT/SKILL SELECTION (brain-informed scoring)
    ├── Listar agents/skills via MCP
    ├── Evaluar cuál es el MEJOR para esta tarea específica
    ├── Score boost por past learnings del Brain
    └── Prioridad: specialized > quality > security > devops > orchestration
  ↓
[3] PLANNING (reusa autonomous-executor logic)
    ├── Descomponer objetivo en pasos ejecutables por goal type
    ├── 12 flujos diferentes (bug, feature, audit, refactor, etc.)
    ├── Definir éxito y failure criteria por paso
    └── Asignar agent/skill a cada paso
  ↓
[4] CRITICAL OPERATIONS GUARD
    ├── Por cada paso: check against CRITICAL_PATTERNS
    ├── Si matchea → confirmación interactiva ANTES de ejecutar
    ├── Lista: git reset --hard, git push --force, rm -rf, DROP TABLE, etc.
    └── Si usuario niega → skip y continuar
  ↓
[5] EXECUTION (sin pedir permiso)
    ├── Para cada paso:
    │   ├── Invocar agent/skill óptimo
    │   ├── Si falla → retry con alternativa
    │   ├── Si falla 2 veces → skip y registrar
    │   └── Si es crítico → abortar y reportar
    ├── Logging continuo de decisiones
    ├── Acumular archivos tocados
    └── Abort threshold 30% — si falla >30% de pasos, para
  ↓
[6] CLARIFICATION GATE (con input real)
    ├── ¿Hay ambigüedad crítica en el objetivo?
    ├── ¿Faltan datos que solo el usuario tiene?
    ├── ¿El objetivo contradice reglas del proyecto?
    └── Si sí → UNA pregunta específica con input() blocking
  ↓
[7] SELF-IMPROVEMENT (learning loop real)
    ├── ¿Qué funcionó? → brain.ingest() como pattern node
    ├── ¿Qué falló? → brain.ingest() como lesson
    ├── ¿Qué tools se usaron? → guardar para futuras selecciones
    ├── Rebuild Brain index si hubo cambios
    └── Leer learnings al inicio de la próxima ejecución
  ↓
[8] ABORT SIGNAL HANDLER
    ├── Si recibe SIGINT/SIGTERM → marca aborted, guarda estado parcial
    └── No perder lo ya ejecutado
  ↓
REPORTE FINAL
```

## Regla de confusión

**Solo pregunta si se cumple TODOS estos a la vez:**

1. La tarea no está clara (múltiples interpretaciones válidas)
2. No hay información en memoria/Brain/reglas para decidir
3. Un web search no resuelve la ambigüedad
4. La decisión afectaría el resultado de forma irreversible

**Ejemplo de cuándo PREGUNTA:**
> "Implementar el módulo de auth" — pero no sabés si es JWT, OAuth, session-based, ni qué BD se usa. Preguntás UNA vez.

**Ejemplo de cuándo NO PREGUNTA:**
> "Fixear el bug de login" — aunque no tengas toda la info, podés analizar el código, buscar logs, y usar el mejor approach existente en el proyecto.

## Critical Operations Guard

**Siempre pregunta antes de ejecutar estas operaciones:**

| Patrón | Descripción |
|---|---|
| `git reset --hard` | Perdería todos los cambios locales |
| `git push --force` | Sobrescribe historial remoto |
| `rm -rf` | Borrado recursivo destructivo |
| `del /f /s` | Borrado forzado Windows |
| `DROP TABLE` | Borrado de tabla en base de datos |
| `DELETE FROM` | Borrado masivo en base de datos |
| `TRUNCATE` | Vaciar tabla |
| `git push` a main/master | Rama protegida |

## Auto-mejora (Learning Loop Real)

```python
# AL INICIO: Leer learnings previos
learnings = brain.query(f"jpkkenfull: what worked for tasks like: {goal[:80]}", limit=5)
for node in learnings:
    info["past_learnings"].append(f"{node.title}: {node.context[:100]}")

# AL FINAL: Guardar resultado
brain.ingest(
    title=f"jpkkenfull: {goal[:80]}",
    context=f"Goal: {goal}\nSteps executed: {n}\nSuccess: {success_rate}\nTools used: {tools}",
    area="jpkkenfull",
    tags=["jpkkenfull", "execution", "auto-improving", task_type],
    node_type="pattern",
    importance="medium",
)
```

## Comandos

```bash
# Ejecución completa
python .agent/skills-custom/jpkkenfull/scripts/main.py --goal "analizar y arreglar el memory leak en production"

# Con contexto extra
python .agent/skills-custom/jpkkenfull/scripts/main.py --goal "implementar web search" --context "usar tavily, integrate with brain"

# Forzar internet search aunque crea que no lo necesita
python .agent/skills-custom/jpkkenfull/scripts/main.py --goal "migrar a FastAPI 0.100" --force_internet

# Skip agent selection (solo usar skills directos)
python .agent/skills-custom/jpkkenfull/scripts/main.py --goal "audit de seguridad" --skip_agents

# Output JSON (para MCP)
python .agent/skills-custom/jpkkenfull/scripts/main.py --goal "git status" --json
```

## Integración MCP

| MCP Server | Uso |
|---|---|
| `antigravity-skills` | Listar y seleccionar skills óptimos |
| `antigravity-agents` | Invocar agents especializados |
| `antigravity-brain` | Consulta + guardado post-ejecución |
| `antigravity-memory` | Consulta mem0 para contexto |
| `jpkkenfull` | Executor autónomo (este skill) |

## Métricas de auto-evaluación

Post-ejecución, Jpkkenfull se mide a sí mismo:

```
{
  "goal": "...",
  "clarification_asked": bool,
  "clarification_question": "..." | null,
  "clarification_response": "..." | null,
  "internet_search_triggered": bool,
  "agents_used": [...],
  "skills_used": [...],
  "self_created_skill": bool,
  "execution_success_rate": 0.0-1.0,
  "files_modified": [...],
  "decisions_log": [...],
  "lessons_learned": [...],
  "past_learnings": [...],      ← LEARNING LOOP: learnings consultados
  "aborted_via_signal": bool,  ← ABORT handler
  "critical_ops_intercepted": [...]  ← CRITICAL OPS GUARD
}
```

## Dependencias

- Python 3.11+
- requests, httpx
- MCP servers del ecosistema (graceful degradation si no hay)
- Brain Network para auto-mejora

## Fuente canónica

- Skill: `.agent/skills-custom/jpkkenfull/`
- Main: `.agent/skills-custom/jpkkenfull/scripts/main.py`
- MCP Server: `.agent/mcp/jpkkenfull-server.py`
- Brain tags: `jpkkenfull`, `execution`, `auto-improving`
