# Antigravity Agents MCP Servers

Servidores MCP que exponen los 40 agentes del ecosistema Antigravity como herramientas ejecutables.

## Servidores Disponibles

| Servidor | Archivo | Transporte | Puerto | Uso |
|----------|---------|-----------|--------|-----|
| **Universal Gateway** | `gateway.py` | HTTP/SSE/stdio | 4747 | **Gateway Maestro v3.0** (Recomendado) |
| **agents-server** | `agents-server.py` | stdio | - | IDE local (Claude Code, Cursor, etc.) |
| **remote-server** | `remote-server.py` | HTTP/SSE | 3777 | Acceso remoto legacy |
| **intelligence-server** | `intelligence-server.py` | stdio | - | Capa de inteligencia |
| **skills-server** | `skills-server.py` | stdio | - | Libreria de skills |
| **ui-server** | `ui-server.py` | stdio | - | Herramientas UI/UX |

## agents-server.py (stdio - Local)

Servidor MCP principal. Se lanza como proceso local desde el IDE.

```json
{
  "mcpServers": {
    "antigravity-agents": {
      "command": "python",
      "args": ["/ruta/a/AntigravitiSkillUSN/.agent/mcp/agents-server.py"]
    }
  }
}
```

## remote-server.py (HTTP/SSE - Remoto)

Servidor MCP con transporte HTTP para acceso desde cualquier ordenador via red.

### Arranque

```bash
# Basico (puerto 3777, sin auth)
python .agent/mcp/remote-server.py

# Con autenticacion (recomendado)
ANTIGRAVITY_API_TOKEN=mi-token-secreto python .agent/mcp/remote-server.py

# Puerto y host custom
python .agent/mcp/remote-server.py --port 8777 --host 127.0.0.1

# Con Docker
docker-compose up mcp-remote
```

### Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/mcp` | JSON-RPC sobre HTTP (Streamable HTTP transport) |
| GET | `/sse` | Server-Sent Events (notificaciones en tiempo real) |
| POST | `/sse` | MCP sobre SSE (bidireccional) |
| GET | `/health` | Health check (publico, sin auth) |
| GET | `/agents` | Lista de agentes (REST) |

### Configuracion en IDE Remoto

```json
{
  "mcpServers": {
    "antigravity-remote": {
      "url": "http://tu-servidor:3777/mcp",
      "headers": {
        "Authorization": "Bearer mi-token-secreto"
      }
    }
  }
}
```

### Con Docker Compose

```bash
# Arrancar solo el servidor remoto
ANTIGRAVITY_API_TOKEN=mi-token docker-compose up mcp-remote

# Verificar health
curl http://localhost:3777/health
```

### Autenticacion

- Define `ANTIGRAVITY_API_TOKEN` como variable de entorno
- Los clientes envian `Authorization: Bearer <token>` en cada request
- Si no se define token, el servidor acepta todas las conexiones (solo para desarrollo)
- La comparacion de tokens usa `secrets.compare_digest` (timing-safe)

## Herramientas Disponibles (todos los servidores)

- `list_agents` - Lista todos los agentes (con filtro de ejecutables)
- `execute_agent` - Ejecuta un agente con una tarea especifica
- `run_autonomous_agent` - Ejecuta un agente en modo autonomo (ReAct loop)
- `find_best_agent` - Sugiere agentes adecuados segun descripcion de tarea
- `get_agent_info` - Metadata detallada y contenido de IDENTITY.md
- `get_costs` - Reporte de uso y costos
- `get_history` - Historial de ejecuciones
- `spawn_team` - Crea un equipo colaborativo de agentes
- `send_team_message` - Envia mensajes entre miembros de un equipo

---
---
*Antigravity Agents v3.0.0 (Optimized) - 40 agentes | 940 skills | 6 MCP servers*
