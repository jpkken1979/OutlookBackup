---
name: autonomous-executor
description: Recibe un objetivo de texto libre, genera un plan, espera aprobación humana, y ejecuta completamente autónomo. Planifica, crea skills, coordina agentes, analiza código, aplica fixes, corre tests, reporta progreso y guarda en Brain.
category: other
version: "1.0.0"
author: Antigravity Ecosystem
tags:
  - autonomous
  - execution
  - planning
  - agents
  - coordination
  - brain
status: active
interface:
  inputs:
    - goal
    - plan_only
    - json
  outputs:
    - plan
    - execution_results
    - summary
---

# Autonomous Executor — Planificador y Ejecutor Autónomo

## Descripción

Esta skill recibe un **objetivo de texto libre**, genera un **plan de ejecución estructurado**,
espera la **aprobación humana**, y luego ejecuta **completamente de forma autónoma**.

El flujo completo es:

```
Objetivo → Análisis → Plan → Aprobación → Ejecución Autónoma → Reporte
```

## Características principales

- **Análisis inteligente**: descompone el objetivo en pasos ejecutables
- **Aprobación humana**: muestra el plan antes de ejecutar (patrón blocking)
- **Ejecución autónoma**: corre todos los pasos sin intervención humana
- **Coordinación de agentes**: usa MCP para invocar agentes cuando los necesita
- **Gestión de skills**: crea skills faltantes si el plan los requiere
- **Reporting de progreso**: muestra cada paso con estado (ok / fail / skip)
- **Integración con Brain**: guarda decisiones y resultados en el Brain Network

## Cuando usar

- Bugs complejos que requieren múltiples pasos de análisis y fix
- Features que involucran múltiples archivos y componentes
- Refactors que tocan código en varias capas del proyecto
- Tareas de auditoría o seguridad multi-fase
- Cualquier objetivo que requiera investigación + implementación + tests

## Cuando NO usar

- Objetivos triviales de un solo paso (usar un agente directamente)
- Objetivos que ya tienen un plan claro (usar un agente de ejecución)
- Tareas que solo requieren lectura sin cambios (usar /brain query)

## Flujo de aprobación humana

El plan se muestra en formato estructurado:

```
══════════════════════════════════════════
OBJETIVO: arreglar el bug de login
══════════════════════════════════════════
PLAN:
  [1] Analizar auth flow (src/auth/*.ts, src/middleware/*.ts)
  [2] Identificar causa raíz (logs + code review)
  [3] Implementar fix en schema/validator
  [4] Correr tests: pytest tests/ -v
  [5] Verificar con mypy + ruff
  [6] Commitear cambios

¿Ejecuto? [Sí] [No] [Modificar plan]
══════════════════════════════════════════
```

## Proceso detallado

### Fase 1: Análisis
1. Recibe el objetivo
2. Analiza el contexto del proyecto (archivos relevantes, historial, reglas)
3. Identifica qué skills/agents/agentes现有的 necesitan

### Fase 2: Planificación
1. Genera una lista de pasos concretos
2. Para cada paso: acción + archivos objetivo + criterio de éxito
3. Identifica dependencias entre pasos
4. Evalúa riesgos (posibles efectos secundarios)

### Fase 3: Aprobación (blocking)
1. Muestra el plan completo al usuario
2. Espera input: `sí` / `no` / `modificar`
3. Si `modificar`: permite editar el plan antes de ejecutar

### Fase 4: Ejecución Autónoma
1. Ejecuta cada paso en orden
2. Si un paso falla: decide (retry / skip / abort) según config
3. Reporta progreso en cada paso
4. Al final: resumen + archivos tocados + recomendaciones

### Fase 5: Brain Integration
1. Guarda el objetivo completado como nodo `session` en Brain
2. Guarda decisiones clave (path elegido, alternativa descartada)
3. Rebuild del índice Brain

## Integración con MCP

Usa los siguientes MCP servers para operar:

| MCP Server | Uso |
|---|---|
| `antigravity-skills` | Buscar skills existentes, identificar gaps |
| `antigravity-agents` | Invocar agentes especializados cuando el plan los necesita |
| `antigravity-brain` | Guardar decisiones, successes, failures |
| Gateway `:4747` | HTTP fallback si MCP no está disponible |

### Graceful degradation

- Si el gateway no responde, opera en modo offline
- Skills/agents se buscan primero por MCP, luego por filesystem
- Tests y lint siempre se corren via subprocess directo (no dependen del gateway)

## Comandos disponibles

```bash
# Ejecución completa (plan → aprobación → execute)
python .agent/skills-custom/autonomous-executor/scripts/main.py \
  --goal "arreglar el bug de login"

# Solo plan, sin ejecución
python .agent/skills-custom/autonomous-executor/scripts/main.py \
  --goal "implementar feature X" --plan-only

# Output JSON
python .agent/skills-custom/autonomous-executor/scripts/main.py \
  --goal "analizar y arreglar deuda técnica" --json
```

## Métricas de ejecución

Cada ejecución genera:

```
{
  "goal": "...",
  "plan_steps": [...],
  "executed_steps": [...],
  "successful_steps": N,
  "failed_steps": M,
  "duration_seconds": X,
  "files_modified": [...],
  "new_skills_created": [...],
  "agents_invoked": [...],
  "brain_nodes_created": [...],
  "recommendations": [...]
}
```

## Límites y timeouts

- Timeout por paso: 60s (configurable via env `EXECUTOR_STEP_TIMEOUT`)
- Max reintentos por paso fallido: 2
- Max steps en un plan: 20 (para evitar planes excesivos)
- Graceful abort: si > 30% de steps fallan, abortar la ejecución

## Errores y recuperación

| Error | Comportamiento |
|---|---|
| Gateway offline | Continuar sin MCP, loguear warning |
| Skill no encontrado | Crear skill básico inlined o skipear el paso |
| Agente falló | Retry automático, luego skip si persiste |
| Tests fallan | Reportar con diff, continuar (no abortar) |
| Plan vacío | Advertir al usuario, no ejecutar |

## Dependencias

- Python 3.11+
- requests (HTTP al gateway)
- httpx (async, para MCP fallback)
- Los MCP servers del ecosistema (opcionales, graceful degradation)