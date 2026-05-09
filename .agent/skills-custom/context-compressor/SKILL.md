---
name: context-compressor
description: Comprime contexto largo (conversaciones, documentos) manteniendo la información más relevante en ≤20% del tamaño original.
category: optimization
version: "1.0.0"
author: Antigravity Ecosystem
tags: [context, compression, memory, compaction, summarization]
status: active
interface:
  inputs:
    - name: task
      type: string
      description: El texto largo a comprimir (conversación, documento, log, etc.)
      required: true
    - name: target_ratio
      type: string
      description: Ratio de compresión objetivo (ej. 0.20 para 20%). Default 0.20.
      required: false
  outputs:
    - name: result
      type: string
      description: Versión comprimida estructurada con hechos clave, decisiones, tareas y errores
---

# Context Compressor — Compresión de Contexto

## Descripción

Recibe texto largo (conversaciones de sesión, documentos, logs) y extrae la información
más relevante de forma estructurada. Produce una versión comprimida de ≤20% del
tamaño original, organizada en cuatro secciones: hechos clave, decisiones tomadas,
tareas pendientes y errores/problemas conocidos.

## Cuándo usar

- Antes de pasar contexto de sesión a un LLM con ventana de contexto limitada
- Para compactar el historial de conversación del bot Telegram (`/compact`)
- Para resumir logs extensos antes de pasarlos al agente `debugger`
- Cuando el agente necesita "recordar" una sesión anterior sin el contexto completo
- Para generar resúmenes de reuniones, documentos técnicos o threads largos
- Complementa la skill `finalizar` al comprimir el contexto de la sesión de trabajo

## Proceso

1. Calcular tamaño original y target (ratio × original)
2. Dividir el texto en segmentos semánticos
3. Extraer por categoría:
   - **Hechos clave**: datos, valores, nombres, URLs, versiones mencionadas
   - **Decisiones tomadas**: frases que indican elecciones o resoluciones
   - **Tareas pendientes**: acciones futuras identificadas
   - **Errores/problemas**: issues, bugs, errores mencionados
4. Priorizar por frecuencia y posición (inicio/fin tienen más peso)
5. Formatear en estructura compacta

## Ejemplos

```bash
# Comprimir un archivo de texto
python .agent/skills-custom/context-compressor/scripts/main.py \
  --task "$(cat conversacion_larga.txt)"

# Con ratio personalizado (30%)
python .agent/skills-custom/context-compressor/scripts/main.py \
  --task "..." --target-ratio 0.30

# Salida JSON para integración
python .agent/skills-custom/context-compressor/scripts/main.py \
  --task "..." --json
```

## Output esperado

```
=== CONTEXT COMPRESSOR ===
Original: 4,200 chars | Comprimido: 420 chars | Ratio: 10.0%

HECHOS CLAVE:
- Python 3.11, FastAPI v0.115, PostgreSQL 16
- DB_HOST=localhost:5432

DECISIONES TOMADAS:
- Usar SQLite como fallback cuando Redis no está disponible
- Migrar a Tauri 2 para la app desktop

TAREAS PENDIENTES:
- Instalar dependencias: pip install -e ".[dev]"
- Configurar ANTIGRAVITY_API_TOKEN en .env

ERRORES/PROBLEMAS:
- ImportError en cost_tracker.py — dependencia crewai faltante
```

## Integración con compaction del bot

Esta skill alimenta el sistema de compaction de `src/telegram/compaction.ts`.
Los campos extraídos mapean a: `durableFacts`, decisions → `preferences`, `pendingTasks`.
