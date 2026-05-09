---
name: mcp-server-development
description: "Crear servidores MCP (Model Context Protocol) propios: tools, resources y prompts. Desde scaffolding hasta producción. Compatible con Claude Desktop, Cursor, Windsurf y VS Code."
version: "1.0.0"
risk: safe
tags: [mcp, model-context-protocol, claude, server, tools, resources, prompts, anthropic]
type: feature
---

# MCP Server Development

> Construye servidores MCP para exponer Tools, Resources y Prompts a cualquier cliente IA compatible.
> Claude Desktop · Cursor · Windsurf · VS Code · Claude Code

---

## ¿Cuándo usar esta skill?

- Quieres exponer funciones propias a Claude/Cursor como herramientas
- Necesitas un servidor MCP para automatizar flujos de trabajo IA
- Quieres conectar Claude con APIs, bases de datos o servicios internos
- Ampliar el ecosistema Antigravity con nuevos MCP servers
- Crear una herramienta/skill que Claude pueda invocar directamente

---

## Conceptos MCP

| Primitiva | Qué es | Ejemplo |
|---|---|---|
| **Tools** | Funciones que el LLM puede llamar | `search_files`, `run_query`, `list_skills` |
| **Resources** | Datos que el LLM puede leer | `file://...`, `db://...`, `antigravity://catalog` |
| **Prompts** | Templates de prompts del servidor | `/security-audit`, `/code-review` |
| **Sampling** | El servidor puede pedir inferencia al LLM | Para razonamiento interno |

---

## Stack recomendado

| Stack | Cuándo usar |
|---|---|
| **Python + `mcp`** | Backend Antigravity, scripts, integración con `.agent/` |
| **TypeScript + `@modelcontextprotocol/sdk`** | Integración con nexus-app, Node.js services |
| **FastMCP (Python)** | Scaffolding ultra-rápido con decoradores |

---

## Quickstart — Python con FastMCP

```bash
pip install fastmcp
```

```python
# server.py — MCP server mínimo funcional
from fastmcp import FastMCP

mcp = FastMCP("mi-servidor")

@mcp.tool()
def buscar_skills(query: str) -> str:
    """Busca skills en el ecosistema Antigravity por keyword."""
    import os
    from pathlib import Path
    
    skills_dir = Path(".agent/skills")
    results = [
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and query.lower() in d.name.lower()
    ]
    return "\n".join(results) if results else "Sin resultados"

@mcp.tool()
def leer_archivo(ruta: str) -> str:
    """Lee el contenido de un archivo del proyecto."""
    from pathlib import Path
    p = Path(ruta)
    if not p.exists():
        return f"Error: {ruta} no existe"
    return p.read_text(encoding="utf-8")

@mcp.resource("antigravity://stats")
def get_stats() -> str:
    """Estadísticas del ecosistema."""
    return "40 agentes | 940 skills | MCP v4.0"

if __name__ == "__main__":
    mcp.run()
```

```bash
# Correr el servidor
python server.py
```

---

## Quickstart — TypeScript (SDK oficial)

```typescript
// server.ts
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "mi-servidor-ts",
  version: "1.0.0",
});

// Tool
server.tool(
  "listar_archivos",
  "Lista archivos en un directorio",
  { directorio: z.string().describe("Ruta del directorio") },
  async ({ directorio }) => {
    const fs = await import("fs/promises");
    const files = await fs.readdir(directorio);
    return { content: [{ type: "text", text: files.join("\n") }] };
  }
);

// Resource
server.resource(
  "config://settings",
  new ResourceTemplate("config://{filename}", { list: undefined }),
  async (uri, { filename }) => ({
    contents: [{ uri: uri.href, text: `Contenido de ${filename}`, mimeType: "text/plain" }],
  })
);

// Prompt
server.prompt(
  "code-review",
  "Review de código con el estilo Antigravity",
  { codigo: z.string() },
  ({ codigo }) => ({
    messages: [{
      role: "user",
      content: { type: "text", text: `Haz un code review de:\n\`\`\`\n${codigo}\n\`\`\`` }
    }]
  })
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

---

## Transportes disponibles

| Transporte | Cuándo usar |
|---|---|
| `stdio` | Claude Desktop, Cursor, VS Code — proceso local |
| `streamable-http` (SSE) | Servidor remoto accesible por HTTP |
| `sse` (legacy) | Nginx / reverse proxy setups |

**HTTP Server (para gateway remoto):**
```python
from fastmcp import FastMCP

mcp = FastMCP("gateway", port=4747)

# ... registrar tools aquí ...

if __name__ == "__main__":
    mcp.run(transport="streamable-http")  # en lugar de stdio
```

---

## Configurar en Claude Desktop

```json
// ~/.config/claude/claude_desktop_config.json (Linux/macOS)
// %APPDATA%\Claude\claude_desktop_config.json (Windows)
{
  "mcpServers": {
    "mi-servidor": {
      "command": "python",
      "args": ["/ruta/absoluta/server.py"],
      "env": {
        "MY_API_KEY": "valor"
      }
    }
  }
}
```

**Con uv (recomendado para Python):**
```json
{
  "mcpServers": {
    "mi-servidor": {
      "command": "uv",
      "args": ["run", "--directory", "/ruta/proyecto", "python", "server.py"]
    }
  }
}
```

---

## Patrones de Tools avanzados

### Tool con validación Pydantic

```python
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("servidor-pydantic")

class QueryParams(BaseModel):
    query: str = Field(description="Búsqueda a realizar")
    limit: int = Field(default=10, ge=1, le=100)
    filters: list[str] = Field(default_factory=list)

@mcp.tool()
def buscar(params: QueryParams) -> dict:
    """Búsqueda avanzada con parámetros validados."""
    return {
        "query": params.query,
        "results": [],  # implementar
        "total": 0
    }
```

### Tool asíncrono con base de datos

```python
import asyncio
import asyncpg

@mcp.tool()
async def query_db(sql: str) -> list[dict]:
    """Ejecuta una query SQL de solo lectura."""
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        rows = await conn.fetch(sql)
        return [dict(row) for row in rows]
    finally:
        await conn.close()
```

---

## Resources — patrones comunes

```python
# Resource estático
@mcp.resource("config://readme")
def get_readme() -> str:
    return Path("README.md").read_text()

# Resource dinámico con template
@mcp.resource("agents://{agent_name}")
def get_agent(agent_name: str) -> str:
    p = Path(f".agent/agents/{agent_name}/IDENTITY.md")
    return p.read_text() if p.exists() else f"Agente {agent_name} no encontrado"

# Resource con lista de URIs disponibles
@mcp.resource("skills://list")  
def list_skills() -> str:
    skills = [d.name for d in Path(".agent/skills").iterdir() if d.is_dir()]
    return "\n".join(sorted(skills))
```

---

## Integración con el ecosistema Antigravity

El MCP server ya existente está en `mcp-server/server.py`. Para extenderlo:

```python
# mcp-server/server.py — estructura del gateway v4.0
# Tools presentes: list_skills, run_skill, list_agents, compose_skills, get_ecosystem_stats
# Resources: antigravity://catalog/*, antigravity://memory/*
# Prompts: architect, debug, review, plan, security-audit, find-agent

# Para añadir un nuevo tool al gateway existente:
@mcp.tool()
def mi_nuevo_tool(param: str) -> str:
    """Descripción del tool para el LLM."""
    # implementación
    return resultado
```

**Registro en `.mcp.json`:**
```json
{
  "mcpServers": {
    "mi-servidor-nuevo": {
      "command": "python",
      "args": ["mcp-server/mi_server.py"],
      "env": {}
    }
  }
}
```

---

## Testing del servidor MCP

```bash
# Inspeccionar tools/resources/prompts
npx @modelcontextprotocol/inspector python server.py

# O con uv
uvx mcp dev server.py
```

**Test unitario de tools:**
```python
import pytest
from fastmcp import FastMCP

def test_buscar_skills():
    # Importar la función directamente (sin servidor)
    from server import buscar_skills
    result = buscar_skills("security")
    assert isinstance(result, str)
    assert len(result) > 0
```

---

## Seguridad

- **NUNCA** exponer tools que ejecuten shell arbitrario sin validación
- Validar todas las rutas de archivo contra PROJECT_ROOT para prevenir path traversal
- Usar variables de entorno para API keys — nunca hardcodear
- En HTTP transport: añadir autenticación si el servidor es accesible externamente
- Limitar el scope de tools: read-only cuando sea posible

```python
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def validate_path(user_path: str) -> Path:
    """Prevenir directory traversal."""
    p = (PROJECT_ROOT / user_path).resolve()
    if not str(p).startswith(str(PROJECT_ROOT)):
        raise ValueError(f"Acceso denegado: {user_path}")
    return p
```

---

## Checklist de un MCP server production-ready

```
[ ] Tools documentados con docstring clara (el LLM la lee)
[ ] Parámetros validados con Pydantic/Zod
[ ] Manejo de errores — nunca crashear el servidor
[ ] Logging con formato estándar [%(asctime)s] [%(levelname)s]
[ ] Variables sensibles en .env, nunca en código
[ ] Transport configurado correctamente (stdio vs HTTP)
[ ] Registrado en .mcp.json / claude_desktop_config.json
[ ] Tests unitarios básicos de cada tool
[ ] (HTTP) Autenticación si es accesible externamente
```

---

## Recursos

- Spec oficial MCP: https://modelcontextprotocol.io
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
- FastMCP: https://github.com/jlowin/fastmcp
- Inspector: `npx @modelcontextprotocol/inspector`
- Gateway Antigravity existente: `mcp-server/server.py` (v4.0)

---

*Skill: mcp-server-development — Ecosistema Antigravity — v1.0.0*
