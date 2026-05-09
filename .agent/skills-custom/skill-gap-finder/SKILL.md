---
name: skill-gap-finder
description: Identifica capacidades faltantes en el ecosistema comparando las skills existentes con necesidades comunes de desarrollo de software.
category: analysis
version: "1.0.0"
author: Antigravity Ecosystem
tags: [skills, analysis, gaps, ecosystem, inventory]
status: active
interface:
  inputs:
    - name: task
      type: string
      description: Área o categoría específica a analizar (opcional — si vacío analiza todo el ecosistema)
      required: false
  outputs:
    - name: result
      type: string
      description: Lista de gaps identificados con prioridad y categoría, ordenados por impacto
---

# Skill Gap Finder — Identificador de Capacidades Faltantes

## Descripción

Escanea los directorios `.agent/skills/` y `.agent/skills-custom/` para inventariar
las capacidades actuales del ecosistema. Las compara contra una base de conocimiento
de capacidades comunes en proyectos de software moderno. Retorna los gaps identificados
ordenados por prioridad con recomendaciones de acción.

## Cuándo usar

- Al planificar la expansión del ecosistema (nuevas skills)
- Antes de un sprint de desarrollo de skills para identificar qué crear primero
- Cuando el agente `architect` necesita entender qué capacidades faltan
- Para generar el backlog de skills del ecosistema
- Como parte del workflow de auditoría de ecosistema

## Categorías analizadas

| Categoría | Descripción |
|-----------|-------------|
| `security` | Auditoría, SAST, dependency scan, secrets detection |
| `testing` | Unit, integration, e2e, mutation, property-based |
| `devops` | Docker, CI/CD, deployment, monitoring, alertas |
| `database` | Migration, backup, query optimization, schema review |
| `frontend` | Accesibilidad, performance, bundle analysis, SEO |
| `api` | Design review, rate limiting, documentation, versioning |
| `observability` | Logging, tracing, metrics, dashboards |
| `ai_ml` | Model evaluation, data validation, prompt testing |
| `documentation` | API docs, architecture diagrams, changelog |
| `performance` | Profiling, load testing, caching, bottleneck detection |

## Proceso

1. Escanear `.agent/skills/` y `.agent/skills-custom/` recursivamente
2. Extraer nombres y categorías de cada skill
3. Comparar contra base de conocimiento de capacidades esperadas
4. Calcular coverage por categoría (% de capacidades cubiertas)
5. Priorizar gaps por: frecuencia de uso estimada + ausencia de alternativas
6. Generar recomendaciones de skills a crear

## Ejemplos

```bash
# Analizar todo el ecosistema
python .agent/skills-custom/skill-gap-finder/scripts/main.py

# Analizar una categoría específica
python .agent/skills-custom/skill-gap-finder/scripts/main.py \
  --task "security"

# Salida JSON para integración con otras tools
python .agent/skills-custom/skill-gap-finder/scripts/main.py --json
```

## Output esperado

```
=== SKILL GAP FINDER REPORT ===
Skills escaneadas: 792 base + 9 custom = 801 total
Categorías con coverage < 50%: 3

GAPS DE ALTA PRIORIDAD:
  [security] secrets-scanner — No encontrado (impacto: alto)
  [testing]  mutation-testing — No encontrado (impacto: alto)
  [api]      rate-limit-tester — No encontrado (impacto: medio)
...
```
