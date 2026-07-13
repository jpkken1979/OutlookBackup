Gestionar Research Spaces — contenedores de investigación por proyecto/tema.

## Comandos disponibles

| Comando | Descripción |
|---|---|
| `/space create <nombre> [descripción]` | Crear un nuevo space |
| `/space list` | Listar todos los spaces |
| `/space attach <space_id> <session_path>` | Vincular una sesión/memoria |
| `/space attach-agent <space_id> <agent_id>` | Vincular un agente |
| `/space context <space_id>` | Ver contexto completo del space |
| `/space stats` | Estadísticas globales de spaces |
| `/space delete <space_id>` | Eliminar un space |

## API de referencia

```python
import sys; sys.path.insert(0, '.agent')
from core.spaces import ResearchSpace

# Crear
space = ResearchSpace.create(name="Mi Proyecto", description="...")

# Listar
spaces = ResearchSpace.list_spaces()

# Adjuntar sesión
space.attach_session(".claude/memory/session_2026-05-09.md")

# Adjuntar agente
space.attach_agent("explorer")

# Contexto completo
ctx = space.get_context()

# Stats global
stats = ResearchSpace.space_stats()
```

## Estructura de directorio

```
.agent/spaces/{space_id}/
├── space.json     # metadata
├── sessions/      # sesiones vinculadas
├── agents/       # agentes vinculados
└── index.md      # índice generado
```

## Ejemplo de uso

1. Crear un space para un proyecto:
   `/space create "ARARI Research" "Investigación sobre módulos ARARI"`

2. Vincular sesiones de memoria:
   `/space attach "arari-research-abc123" ".claude/memory/session_2026-05-09.md"`

3. Vincular agentes relevantes:
   `/space attach-agent "arari-research-abc123" "explorer"`

4. Ver todo el contexto:
   `/space context "arari-research-abc123"`

## Reglas

- Responder siempre en español
- Usar `ResearchSpace.create()` para crear, no instanciar directo
- `space_id` se genera automáticamente a partir del nombre (slug + uuid suffix)
- Los spaces persisten en `.agent/spaces/` y survive between sessions
