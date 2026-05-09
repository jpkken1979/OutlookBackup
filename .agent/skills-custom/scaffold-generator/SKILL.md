---
name: Scaffold Generator
description: "Genera scaffolding de proyectos desde templates — FastAPI, React, Tauri plugins, agents, skills, MCP servers. Recibe un tipo de proyecto y genera la estructura completa con archivos base. Triggers: scaffold, template, generate, create project, scaffolding, boilerplate."
---

# Scaffold Generator

Genera scaffolding de proyectos desde templates — FastAPI, React, Tauri plugins, agents, skills, MCP servers. Recibe un tipo de proyecto y genera la estructura completa con archivos base.

**Agent Tier:** 1 (Orchestration and above)
**Auth Required:** No
**Timeout:** 30 seconds (archivos locales)
**Cost:** Free (sin APIs externas)

## Descripcion

Este skill crea la estructura inicial de un proyecto a partir de un template predefinido. Soporta seis tipos de proyectos:

| Tipo | Descripcion | Ubicacion tipica |
|---|---|---|
| `fastapi` | Python FastAPI app | Raiz del proyecto |
| `react` | React + TypeScript + Vite | `apps/` o raiz |
| `tauri-plugin` | Tauri 2 plugin para Nexus | `nexus-app/plugins/` |
| `agent` | Agente para `.agent/agents/` | `.agent/agents/` |
| `skill` | Skill para `.agent/skills-custom/` | `.agent/skills-custom/` |
| `mcp-server` | MCP server portable | `mcp-server/` |

## Input Schema

```json
{
  "type": "string (required) — fastapi|react|tauri-plugin|agent|skill|mcp-server",
  "name": "string (required) — nombre del proyecto",
  "output": "string (optional) — directorio de salida, default: cwd",
  "dry_run": "boolean (optional) — solo mostrar que crearia sin crear"
}
```

## Output Schema

```json
{
  "status": "success|error|skipped",
  "type": "string",
  "name": "string",
  "output_dir": "string",
  "files_created": ["list of created paths"],
  "message": "string"
}
```

## CLI Usage

```bash
# Generar un proyecto FastAPI
py .agent/skills-custom/scaffold-generator/scripts/main.py --type fastapi --name "mi-api"

# Generar un agente
py .agent/skills-custom/scaffold-generator/scripts/main.py --type agent --name "mi-agente"

# Generar un skill
py .agent/skills-custom/scaffold-generator/scripts/main.py --type skill --name "mi-skill"

# Generar un plugin Tauri
py .agent/skills-custom/scaffold-generator/scripts/main.py --type tauri-plugin --name "mi-plugin"

# Dry-run — ver que crearia sin crear
py .agent/skills-custom/scaffold-generator/scripts/main.py --type fastapi --name "mi-api" --dry-run

# Listar tipos disponibles
py .agent/skills-custom/scaffold-generator/scripts/main.py --list

# Output en directorio especifico
py .agent/skills-custom/scaffold-generator/scripts/main.py --type agent --name "mi-agente" --output ".agent/agents"
```

## Tipos de Template

### `fastapi`

Estructura:

```
mi-api/
├── main.py              # Entry point FastAPI
├── routes/
│   ├── __init__.py
│   └── health.py       # Ruta health basica
├── models/
│   ├── __init__.py
│   └── base.py         # BaseModel comun
├── schemas/
│   ├── __init__.py
│   └── common.py        # Schemas compartidos
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── pyproject.toml      # Config con dependencias
├── .env.example        # Template de variables
└── README.md
```

### `react`

Estructura:

```
mi-react/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   └── components/
│       └── Counter.tsx
├── public/
│   └── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js  # si se pide
└── README.md
```

### `tauri-plugin`

Estructura:

```
mi-plugin/
├── src-tauri/
│   └── src/
│       ├── lib.rs      # Plugin entry
│       └── commands/
│           ├── mod.rs
│           └── hello.rs
├── src/
│   └── index.ts        # API publica del plugin
├── README.md
└── package.json
```

### `agent`

Estructura:

```
mi-agente/
├── IDENTITY.md         # Identidad, tier, capacidades
├── memory/
│   └── shared_memory.json
├── scripts/
│   ├── __init__.py
│   └── main.py        # Entry point con execute()
└── logs/              # Directorio vacio para logs
```

### `skill`

Estructura:

```
mi-skill/
├── SKILL.md           # Documentacion completa
└── scripts/
    ├── __init__.py
    └── main.py        # Entry point con CLI argparse
```

### `mcp-server`

Estructura:

```
mi-mcp/
├── src/
│   ├── __init__.py
│   └── server.py      # Server con decorators @tool
├── server.py          # Entry point
├── http_gateway.py    # Gateway HTTP opcional
├── requirements.txt
├── pyproject.toml
├── README.md
└── tests/
    ├── __init__.py
    └── test_server.py
```

## Comportamiento

- **No sobreescribe archivos existentes**: si un archivo ya existe, lo detecta y pregunta (o lo salta en modo non-interactive).
- **Crea directorios segun necesidad**: usa `parents=True` en `mkdir`.
- **Placeholders en templates**: los archivos contienen marcadores como `{{PROJECT_NAME}}` reemplazados por el nombre del proyecto.

## Opciones de CLI

| Opcion | Descripcion |
|---|---|
| `--type` | Tipo de proyecto (required) |
| `--name` | Nombre del proyecto (required) |
| `--output` | Directorio de salida (default: cwd) |
| `--dry-run` | Solo muestra archivos que crearia |
| `--list` | Lista tipos disponibles |
| `--force` | Sobreescribe archivos existentes sin preguntar |

## Error Handling

- **Tipo invalido**: lista los tipos disponibles y sale con error.
- **Nombre vacio o invalido**: error con mensaje descriptivo.
- **Directorio no existe**: lo crea si es valido, error si es inaccesible.
- **Archivo existe**: pregunta al usuario o salta ( `--force` para sobreescribir).

## Performance Notes

- Tiempo tipico: <1s para proyectos pequenos (agent, skill)
- Tiempo tipico: <3s para proyectos complejos (fastapi, react)
- Sin I/O externo, solo archivos locales

## Testing

```bash
# Test dry-run
py .agent/skills-custom/scaffold-generator/scripts/main.py --type agent --name "test-agent" --dry-run

# Listar tipos
py .agent/skills-custom/scaffold-generator/scripts/main.py --list

# Help
py .agent/skills-custom/scaffold-generator/scripts/main.py --help
```

## Author

Architecture Team
**Version:** 1.0.0
**Created:** 2026-04-22

## License

MIT (same as OpenAntigravity)
