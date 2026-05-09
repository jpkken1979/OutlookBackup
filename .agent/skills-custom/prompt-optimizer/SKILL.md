---
name: prompt-optimizer
description: Analiza un prompt dado y sugiere mejoras estructuradas para maximizar la calidad de respuesta de cualquier LLM.
category: optimization
version: "1.0.0"
author: Antigravity Ecosystem
tags: [prompt, optimization, llm, quality, engineering]
status: active
interface:
  inputs:
    - name: task
      type: string
      description: El prompt original a analizar y mejorar
      required: true
    - name: target_model
      type: string
      description: Modelo objetivo (claude, gpt, groq). Afecta recomendaciones específicas.
      required: false
  outputs:
    - name: result
      type: string
      description: Análisis de heurísticas, versión mejorada del prompt y explicación de cambios
---

# Prompt Optimizer — Mejora de Prompts para LLMs

## Descripción

Evalúa la calidad de un prompt aplicando 5 heurísticas comprobadas de prompt engineering:
claridad, especificidad, ejemplos, formato de salida y rol del sistema. Genera una
versión mejorada del prompt con explicación detallada de cada cambio aplicado.

## Cuándo usar

- Antes de usar un prompt repetidamente en producción
- Cuando las respuestas del LLM son inconsistentes o imprecisas
- Al diseñar prompts para skills del ecosistema
- Para revisar prompts de agentes existentes en `.agent/agents/*/IDENTITY.md`
- Cuando el agente `performance-optimizer` detecta baja calidad en respuestas

## Heurísticas evaluadas

| Heurística | Descripcion | Peso |
|------------|-------------|------|
| `clarity` | ¿El prompt es claro y sin ambigüedad? | 20% |
| `specificity` | ¿Especifica exactamente qué se necesita? | 25% |
| `examples` | ¿Incluye ejemplos few-shot si es complejo? | 20% |
| `output_format` | ¿Define el formato de salida esperado? | 20% |
| `role_setting` | ¿Establece el rol o contexto del asistente? | 15% |

## Proceso

1. Analizar el prompt contra cada heurística (score 0-10)
2. Calcular score total ponderado
3. Identificar las heurísticas con peor score
4. Generar versión mejorada del prompt aplicando mejoras
5. Explicar cada mejora con justificación

## Ejemplos

```bash
# Via CLI
python .agent/skills-custom/prompt-optimizer/scripts/main.py \
  --task "Resume este texto"

# Con modelo objetivo
python .agent/skills-custom/prompt-optimizer/scripts/main.py \
  --task "Clasifica este email como spam o no spam" \
  --target-model claude

# Salida JSON
python .agent/skills-custom/prompt-optimizer/scripts/main.py \
  --task "Escribe codigo para..." --json
```

## Output esperado

```
=== PROMPT OPTIMIZER REPORT ===
Prompt original: Resume este texto
Score total: 24/100

Heurísticas:
  clarity:       6/10  [WARN]
  specificity:   2/10  [FAIL] — No especifica longitud ni enfoque
  examples:      0/10  [FAIL] — Sin ejemplos del formato esperado
  output_format: 1/10  [FAIL] — No define formato de salida
  role_setting:  0/10  [FAIL] — Sin contexto de rol

=== PROMPT MEJORADO ===
Eres un asistente experto en síntesis de información.
Resume el siguiente texto en 3-5 oraciones clave...
```
