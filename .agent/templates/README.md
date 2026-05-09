# Templates

Este directorio contiene templates estándar para crear nuevos agentes y skills.

## Contenido

```
templates/
├── README.md               # Este archivo
├── SKILL_TEMPLATE.md       # Template para crear skills
└── AGENT_TEMPLATE/         # Template para crear agentes
    ├── SYSTEM_PROMPT.md    # Prompt del sistema
    ├── IDENTITY.md         # Identidad del agente
    └── agent.json          # Configuración JSON
```

## Crear un Nuevo Skill

1. Copiar el template:
   ```bash
   cp -r .agent/templates/SKILL_TEMPLATE.md .agent/skills/mi-nuevo-skill/SKILL.md
   ```

2. Editar el archivo:
   - Actualizar metadata YAML (name, description, category, etc.)
   - Completar secciones de documentación
   - Agregar ejemplos de uso

3. Agregar implementación:
   ```bash
   mkdir -p .agent/skills/mi-nuevo-skill/scripts
   touch .agent/skills/mi-nuevo-skill/scripts/main.py
   ```

## Crear un Nuevo Agente

1. Copiar el template:
   ```bash
   cp -r .agent/templates/AGENT_TEMPLATE .agent/agents/mi-nuevo-agente
   ```

2. Editar archivos:
   - `SYSTEM_PROMPT.md` - Definir comportamiento del agente
   - `IDENTITY.md` - Definir metadata y relaciones
   - `agent.json` - Configurar parámetros

3. Agregar implementación (opcional):
   ```bash
   mkdir -p .agent/agents/mi-nuevo-agente/scripts
   touch .agent/agents/mi-nuevo-agente/scripts/main.py
   ```

## Estructura Requerida

### Skills (Mínimo)
```
skill-name/
├── SKILL.md          # REQUERIDO: Metadata y documentación
└── scripts/          # OPCIONAL: Implementación
    └── main.py
```

### Agentes (Mínimo)
```
agent-name/
├── SYSTEM_PROMPT.md  # REQUERIDO: Comportamiento
└── IDENTITY.md       # REQUERIDO: Metadata
```

### Agentes (Completo)
```
agent-name/
├── SYSTEM_PROMPT.md  # Comportamiento
├── IDENTITY.md       # Metadata
├── agent.json        # Configuración
├── README.md         # Documentación extendida
├── scripts/          # Implementación
│   └── main.py
└── examples/         # Ejemplos de uso
```

## Estándares

### Naming Conventions
- **Skills**: `kebab-case` (ej: `api-design-patterns`)
- **Agentes**: `kebab-case` (ej: `security-auditor`)
- **Archivos**: `UPPER_CASE.md` para docs, `snake_case.py` para código

### Metadata YAML
Siempre incluir en SKILL.md:
```yaml
---
name: skill-name
description: "Descripción"
category: backend|frontend|testing|security|devops|database|ai|architecture|specialized
version: "1.0.0"
---
```

### Tiers de Agentes
| Tier | Categoría | Ejemplos |
|------|-----------|----------|
| 1 | Orquestación | planner, architect |
| 2 | Desarrollo Core | backend-specialist, frontend-specialist |
| 3 | Calidad | code-reviewer, test-engineer |
| 4 | Seguridad | security-auditor, debugger |
| 5 | DevOps | devops-engineer, mcp-integrator |
| 6 | Especializado | ui-ux-designer, i18n |
| 7 | Ecosistemas | tauri-*, vite-* |
| 8 | Enterprise | uns-*, haken-* |
| 9 | Sistema | memory, stuck, finalizer |

---

*Antigravity Agents v3.1.0*
