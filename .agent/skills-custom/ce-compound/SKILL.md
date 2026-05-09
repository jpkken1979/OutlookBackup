---
name: ce-compound
description: "Documenta problemas resueltos recientemente para compound knowledge. Captura en docs/solutions/ con YAML frontmatter e ingesta al Brain Network."
argument-hint: "[solución resuelta]"
---

# ce-compound — Knowledge Compounding Skill

## Core Principle

"Each unit of engineering work should make subsequent units easier."

## Workflow

1. **Auto Memory Scan** — brain.query() para buscar si ya existe documentación del problema
2. **Parallel Research** — subagents para context, solution extraction, related docs
3. **Assembly & Write** — escribe `docs/solutions/YYYY-MM-DD-<slug>.md`
4. **Selective Refresh Check** — verificar si hay nodos existentes que actualizar
5. **Brain Ingest** — ingestar al Brain Network con node_type=`pattern`

## Output Schema (YAML frontmatter)

```yaml
---
name: solution_<slug>
description: <one-line>
type: pattern
trigger: session
date: YYYY-MM-DD
area: problem_domain
tags: [resolution, solved, <domain>]
---

# Solution: <Problem Title>

## Problem
## Root Cause
## Resolution
## Prevention
```

## Brain Integration

Usa `.agent/core/brain.py`:
```python
from core.brain import Brain
brain = Brain(Path('.agent/brain'), app_id='nexus-mother')
brain.ingest(
    title="Solution: <Problem>",
    context="...",
    area="problem_domain",
    tags=["resolution", "solved"],
    node_type="pattern",
    importance="medium"
)
```

## Usage

```bash
# Direct invocation
python .agent/skills-custom/ce-compound/main.py "solución resuelta"

# Via skill runner
python .agent/scripts/invoke-skill.py ce-compound "solución resuelta"
```

## Arguments

- `solution` (required): Descripción breve de la solución resuelta (se usa como slug base)

## Output

- Documento: `docs/solutions/YYYY-MM-DD-<slug>.md`
- Nodo Brain: `pattern` en `.agent/brain/`
