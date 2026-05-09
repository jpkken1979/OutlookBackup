---
name: openai-notion-meeting-intelligence
description: "Preparación de reuniones con contexto de Notion. Templates para status, decisiones, planificación, retros, 1:1 y brainstorming."
type: feature
---

# Notion Meeting Intelligence

Prepara y documenta reuniones usando contexto almacenado en Notion.

## Setup

```bash
mcp add notion --url https://mcp.notion.com/mcp
```

## Templates de Reunión

### Status Update
```markdown
# Status Update — [Fecha]

## Progreso
- [Proyecto A]: [estado] — [detalles]
- [Proyecto B]: [estado] — [detalles]

## Blockers
- [Descripción del blocker]

## Próximos Pasos
- [ ] [Acción 1] — @responsable — [fecha]
- [ ] [Acción 2] — @responsable — [fecha]
```

### Decision Meeting
```markdown
# Decisión: [Título]

## Contexto
[Descripción del problema a resolver]

## Opciones
| Opción | Pros | Contras |
|--------|------|---------|
| A | ... | ... |
| B | ... | ... |

## Decisión
[Opción elegida y justificación]

## Acciones
- [ ] [Implementar decisión] — @responsable
```

### Planning Session
```markdown
# Planning — [Sprint/Periodo]

## Objetivos del Sprint
1. [Objetivo 1]
2. [Objetivo 2]

## Capacidad del Equipo
| Miembro | Disponibilidad | Foco |
|---------|----------------|------|
| ... | ... | ... |

## Items Priorizados
1. [Item] — [puntos] — @owner
2. [Item] — [puntos] — @owner

## Riesgos
- [Riesgo identificado]
```

### Retrospective
```markdown
# Retro — [Sprint/Periodo]

## ¿Qué salió bien? ✅
- [Item positivo]

## ¿Qué mejorar? 🔧
- [Item a mejorar]

## Acciones
- [ ] [Acción de mejora] — @responsable
```

### 1:1 Meeting
```markdown
# 1:1 — [Persona A] + [Persona B] — [Fecha]

## Check-in
[Cómo te sientes, energía, ánimo]

## Temas
- [Tema 1]
- [Tema 2]

## Action Items
- [ ] [Acción] — @responsable — [fecha]

## Notas
[Notas adicionales]
```

### Brainstorming
```markdown
# Brainstorm: [Tema]

## Problema/Oportunidad
[Descripción clara]

## Ideas
1. [Idea] — Impacto: [alto/medio/bajo] — Esfuerzo: [alto/medio/bajo]
2. [Idea] — Impacto: ... — Esfuerzo: ...

## Ideas Seleccionadas
- [Idea a explorar]

## Próximos Pasos
- [ ] [Validar idea X]
```

## Workflow de Preparación

1. **Consultar Notion** — Buscar notas previas, action items pendientes.
2. **Seleccionar template** — Según tipo de reunión.
3. **Pre-llenar contexto** — Datos de proyectos, métricas, items pendientes.
4. **Durante reunión** — Tomar notas en la estructura.
5. **Post-reunión** — Crear action items, asignar responsables.

## Recursos

- [Notion API](https://developers.notion.com/)
- [Notion MCP](https://github.com/makenotion/notion-mcp-server)
