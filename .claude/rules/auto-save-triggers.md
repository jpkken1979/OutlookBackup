# Regla: Auto-Save Triggers para Memoria

Aplica a todas las sesiones de Claude Code en este repositorio.

## Triggers de guardado automatico

Despues de completar cualquiera de estas acciones, guardar automaticamente en:
1. **`.claude/memory/`** — archivos markdown (sincronizables por git)
2. **`.agent/brain/`** — Brain Network (conocimiento estructurado con cross-refs, decay temporal, expansion semantica)

Para ingestar en el Brain:
```python
import sys; sys.path.insert(0, '.agent')
from core.brain import Brain; from pathlib import Path
brain = Brain(Path('.agent/brain'), app_id='nexus-mother')
brain.ingest(title="...", context="...", area="...", tags=[...], node_type="...", importance="...")
```

Triggers de guardado:

### 1. Decisiones de arquitectura
Cuando se tome una decision de diseno significativa (nueva abstraccion, cambio de patron, eleccion de libreria):
- Guardar: que se decidio, por que, alternativas descartadas
- Archivo: `.claude/memory/decision_{topic}.md`
- Tipo: `project`

### 2. Bugs resueltos con root cause
Cuando se resuelva un bug no trivial:
- Guardar: sintoma, root cause, fix aplicado, como prevenir
- Archivo: `.claude/memory/bugfix_{topic}.md`
- Tipo: `project`

### 3. Descubrimientos del codebase
Cuando se descubra comportamiento no documentado o gotcha:
- Guardar: que se descubrio, donde, implicaciones
- Archivo: `.claude/memory/discovery_{topic}.md`
- Tipo: `project`

### 4. Patrones establecidos
Cuando se establezca un nuevo patron o convencion:
- Guardar: el patron, cuando usarlo, ejemplo
- Archivo: `.claude/memory/pattern_{topic}.md`
- Tipo: `feedback`

### 5. Configuracion critica
Cuando se modifique configuracion que afecte al ecosistema:
- Guardar: que cambio, valor anterior vs nuevo, razon
- Archivo: `.claude/memory/config_{topic}.md`
- Tipo: `project`

### 6. Cierre de sesion
Al finalizar una sesion significativa (3+ cambios):
- Guardar resumen: que se hizo, archivos tocados, decisiones, pendientes
- Archivo: `.claude/memory/session_{date}.md`
- Tipo: `project`

## Formato de memoria auto-guardada

```markdown
---
name: {nombre descriptivo}
description: {una linea para relevancia futura}
type: {project|feedback|reference}
auto_saved: true
trigger: {decision|bugfix|discovery|pattern|config|session}
date: {YYYY-MM-DD}
---

{contenido}
```

## Cuando NO auto-guardar
- Ediciones menores (typos, formatting)
- Cambios que ya estan documentados en CLAUDE.md
- Informacion derivable del codigo o git log
- Tareas rutinarias sin decisiones significativas
