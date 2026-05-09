---
name: agent-benchmark
description: Evalúa el rendimiento de agentes del ecosistema en un conjunto de tareas estándar, midiendo calidad estimada, tiempo y tokens.
category: analysis
version: "1.0.0"
author: Antigravity Ecosystem
tags: [benchmark, agents, evaluation, performance, quality]
status: active
interface:
  inputs:
    - name: task
      type: string
      description: Nombre del agente a evaluar, o "all" para comparar todos los disponibles
      required: true
    - name: benchmark_suite
      type: string
      description: Suite de benchmark a usar (standard, code, analysis). Default "standard".
      required: false
  outputs:
    - name: result
      type: string
      description: Reporte de benchmark con scores, tiempos estimados y recomendaciones
---

# Agent Benchmark — Evaluación de Rendimiento de Agentes

## Descripción

Ejecuta un conjunto de tareas estándar de benchmark contra uno o más agentes del
ecosistema. Mide y compara: calidad estimada de respuesta, tiempo de respuesta
esperado, tokens estimados, y cobertura de capacidades. Genera un reporte comparativo
que ayuda a elegir el agente más adecuado para cada tipo de tarea.

## Cuándo usar

- Antes de elegir qué agente usar para una tarea importante
- Para validar que un nuevo agente funciona correctamente tras modificaciones
- Para detectar degradación de calidad en agentes existentes (regression testing)
- Al comparar agentes similares para decidir cuál especializar
- Como parte del health check del ecosistema (`make health`)
- Cuando el `performance-optimizer` detecta latencia alta en respuestas de agentes

## Suites de Benchmark

### Standard (por defecto)
5 tareas de cobertura general:
1. **Análisis de código** — Revisar una función Python y detectar issues
2. **Planificación** — Crear plan de 5 pasos para implementar una feature
3. **Explicación técnica** — Explicar un concepto de arquitectura
4. **Debugging** — Identificar la causa de un error dado su traceback
5. **Documentación** — Generar docstring para una función

### Code
Enfocado en capacidades de programación:
- Generación de código, refactorización, code review, tests, optimización

### Analysis
Enfocado en capacidades analíticas:
- Análisis de logs, detección de patrones, síntesis de documentos, evaluación de riesgos

## Métricas evaluadas

| Métrica | Descripción | Peso |
|---------|-------------|------|
| `identity_score` | ¿El agente tiene IDENTITY.md completo y bien definido? | 30% |
| `coverage_score` | ¿Cubre los dominios de las tareas benchmark? | 25% |
| `tool_readiness` | ¿Tiene scripts y herramientas configuradas? | 25% |
| `memory_ready` | ¿Tiene memoria compartida configurada? | 20% |

## Proceso

1. Localizar el agente en `.agent/agents/<nombre>/`
2. Leer `IDENTITY.md` y evaluar completitud
3. Verificar scripts, memoria y estructura del directorio
4. Calcular scores por métrica
5. Estimar capacidades reales vs benchmark suite
6. Generar reporte comparativo con ranking

## Ejemplos

```bash
# Benchmark de un agente específico
python .agent/skills-custom/agent-benchmark/scripts/main.py \
  --task "architect"

# Comparar todos los agentes
python .agent/skills-custom/agent-benchmark/scripts/main.py \
  --task "all"

# Suite específica
python .agent/skills-custom/agent-benchmark/scripts/main.py \
  --task "debugger" --benchmark-suite code

# JSON para integración
python .agent/skills-custom/agent-benchmark/scripts/main.py \
  --task "all" --json
```

## Output esperado

```
=== AGENT BENCHMARK REPORT ===
Suite: standard | Agentes evaluados: 40

RANKING (score total):
  1. architect          95.2/100  [identity:OK scripts:OK memory:OK]
  2. debugger           91.5/100  [identity:OK scripts:OK memory:WARN]
  3. security-auditor   88.0/100  [identity:OK scripts:WARN memory:OK]
  ...

RECOMENDACIÓN para tareas de análisis: architect o debugger
```

## Integración con el ecosistema

Complementa `python .agent/core/health_check.py` con evaluación cualitativa.
Los scores alimentan el ranking de agentes en `.agent/scripts/invoke-agent.py`.
