# MCP Servers Integration Guide

Guía para integrar los mejores MCP servers del ecosistema oficial y comunidad.

## Servers Oficiales Recomendados

### 1. Git Server (Oficial)
**Propósito:** Leer, buscar y manipular repositorios Git

```json
{
  "mcpServers": {
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git"],
      "env": {
        "GIT_REPOS_PATH": "/path/to/repos"
      }
    }
  }
}
```

**Herramientas disponibles:**
- `git_status` - Ver estado del repo
- `git_log` - Ver historial de commits
- `git_diff` - Ver cambios
- `git_search` - Buscar en código
- `git_branch` - Gestionar ramas

### 2. Filesystem Server (Oficial)
**Propósito:** Operaciones seguras de archivos

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]
    }
  }
}
```

**Herramientas disponibles:**
- `read_file` - Leer archivos
- `write_file` - Escribir archivos
- `list_directory` - Listar directorios
- `search_files` - Buscar archivos

### 3. Memory Server (Oficial)
**Propósito:** Memoria persistente basada en knowledge graph

```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

**Herramientas disponibles:**
- `create_entities` - Crear entidades
- `create_relations` - Crear relaciones
- `search_nodes` - Buscar en el grafo
- `open_nodes` - Abrir nodos específicos

### 4. Fetch Server (Oficial)
**Propósito:** Obtener contenido web para LLMs

```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    }
  }
}
```

---

## Servers de la Comunidad

### 5. GitHub Server (Oficial GitHub)
**URL:** https://github.com/github/github-mcp-server

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@github/mcp-server"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

**Herramientas disponibles:**
- Gestión de issues
- Pull requests
- Repositorios
- Actions

### 6. PostgreSQL/Neon Server
**URL:** https://github.com/neondatabase/mcp-server-neon

```json
{
  "mcpServers": {
    "neon": {
      "command": "npx",
      "args": ["-y", "@neondatabase/mcp-server-neon"],
      "env": {
        "NEON_API_KEY": "${NEON_API_KEY}"
      }
    }
  }
}
```

### 7. Playwright Browser Server (Microsoft)
**URL:** https://github.com/microsoft/playwright-mcp

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-playwright"]
    }
  }
}
```

**Herramientas disponibles:**
- `navigate` - Navegar a URLs
- `screenshot` - Capturar pantalla
- `click` - Hacer click
- `fill` - Llenar formularios
- `evaluate` - Ejecutar JavaScript

### 8. Semgrep Security Server
**URL:** https://github.com/semgrep/mcp

```json
{
  "mcpServers": {
    "semgrep": {
      "command": "npx",
      "args": ["-y", "@semgrep/mcp-server"]
    }
  }
}
```

**Herramientas disponibles:**
- `scan` - Escanear código
- `rules` - Gestionar reglas
- `findings` - Ver hallazgos

### 9. E2B Code Sandbox
**URL:** https://github.com/e2b-dev/mcp-server

```json
{
  "mcpServers": {
    "e2b": {
      "command": "npx",
      "args": ["-y", "@e2b/mcp-server"],
      "env": {
        "E2B_API_KEY": "${E2B_API_KEY}"
      }
    }
  }
}
```

**Herramientas disponibles:**
- `run_code` - Ejecutar código en sandbox
- `install_packages` - Instalar paquetes
- `upload_file` - Subir archivos
- `download_file` - Descargar archivos

### 10. Exa Search Server
**URL:** https://github.com/exa-labs/exa-mcp-server

```json
{
  "mcpServers": {
    "exa": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-exa"],
      "env": {
        "EXA_API_KEY": "${EXA_API_KEY}"
      }
    }
  }
}
```

---

## Configuración Completa Recomendada

Agregar a `.claude/settings.json`:

```json
{
  "mcpServers": {
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@github/mcp-server"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "semgrep": {
      "command": "npx",
      "args": ["-y", "@semgrep/mcp-server"]
    }
  }
}
```

---

## Registro Oficial

Más servers disponibles en: https://registry.modelcontextprotocol.io/

---

## Referencias

- [MCP Official Servers](https://github.com/modelcontextprotocol/servers)
- [Awesome MCP Servers](https://github.com/wong2/awesome-mcp-servers)
- [Microsoft MCP](https://github.com/microsoft/mcp)
- [IBM MCP](https://github.com/IBM/mcp)

---

*Última actualización: 2026-02-03*
