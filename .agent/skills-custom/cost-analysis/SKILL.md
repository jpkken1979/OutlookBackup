---
name: cost-analysis
description: Estima el costo de ejecutar una tarea con diferentes modelos LLM y recomienda el modelo más económico para el tipo de tarea.
category: optimization
version: "1.0.0"
author: Antigravity Ecosystem
tags: [cost, llm, optimization, tokens, budget]
status: active
interface:
  inputs:
    - name: task
      type: string
      description: La tarea o prompt a analizar para estimar costo
      required: true
    - name: model_filter
      type: string
      description: Filtrar por familia de modelo (claude, gpt, groq). Opcional.
      required: false
  outputs:
    - name: result
      type: string
      description: Tabla comparativa de costos y recomendación de modelo
---

# Cost Analysis — Estimación de Costos LLM

## Descripción

Analiza una tarea dada, estima los tokens necesarios y compara el costo de ejecutarla
en distintos modelos LLM disponibles en el ecosistema. Retorna una recomendación
del modelo más económico sin sacrificar calidad para el tipo de tarea detectado.

## Cuándo usar

- Antes de elegir qué modelo usar para una operación masiva o repetitiva
- Para optimizar el presupuesto de API cuando hay múltiples tareas similares
- Para justificar la elección de modelo en un reporte de arquitectura
- Cuando el agente `cost-optimizer` recomienda revisar gastos de LLM

## Proceso

1. Tokenizar la tarea usando estimación heurística (1 token ≈ 4 caracteres)
2. Añadir overhead estimado de respuesta según el tipo de tarea detectado
3. Calcular costo por modelo usando tarifas actuales (input + output tokens)
4. Clasificar la tarea: `conversational`, `code`, `analysis`, `structured_output`
5. Recomendar el modelo óptimo por tipo de tarea y presupuesto
6. Mostrar tabla comparativa ordenada por costo total estimado

## Modelos comparados

| Modelo | Input ($/1M tok) | Output ($/1M tok) | Bueno para |
|--------|-----------------|-------------------|------------|
| Claude Haiku 3.5 | $0.80 | $4.00 | Conversacional, clasificación |
| Claude Sonnet 4 | $3.00 | $15.00 | Análisis complejo, código |
| GPT-4o mini | $0.15 | $0.60 | Tareas simples, volumen alto |
| GPT-4o | $2.50 | $10.00 | Razonamiento avanzado |
| Groq Llama 3.1 8B | $0.05 | $0.08 | Velocidad, bajo costo |
| Groq Llama 3.3 70B | $0.59 | $0.79 | Balance calidad/costo |

## Ejemplos

```bash
# Via CLI
python .agent/skills-custom/cost-analysis/scripts/main.py \
  --task "Analizar 500 CVs y clasificar por perfil técnico"

# Via agente
python .agent/scripts/invoke-agent.py cost-optimizer \
  "Estima el costo de procesar 1000 documentos con este prompt: [...]"
```

## Integración con el ecosistema

Consulta `.agent/core/cost_tracker.py` si existe para historial real de costos.
Si no hay historial, usa estimaciones basadas en las tarifas actuales de cada proveedor.
