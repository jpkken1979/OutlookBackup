---
name: remote-control
description: |
type: feature
---
  Gestiona el servidor MCP remoto de Antigravity (remote-server.py).
  Permite iniciar/detener el servidor, verificar su estado, generar
  tokens de auth y producir configuración .mcp.json para IDEs remotos.
  Triggers: remote server, mcp remoto, remote-control, acceso remoto,
  conectar IDE, token auth, puerto 3777.
---

# Remote Control — Gestión del Servidor MCP Remoto

## Role

Administrador del servidor MCP remoto de Antigravity. Gestiona `remote-server.py`,
que expone los 40+ agentes del ecosistema vía HTTP/SSE desde cualquier red.

## Capabilities

| Capacidad | Descripción |
|-----------|-------------|
| **start** | Lanza `remote-server.py` en el puerto indicado (defecto 3777) |
| **stop** | Detiene el proceso del servidor por puerto o PID |
| **health** | Verifica el estado del servidor via `GET /health` |
| **config** | Genera snippet `.mcp.json` listo para pegar en IDE remoto |
| **token** | Genera un token seguro con `secrets.token_urlsafe(32)` |

## Endpoints del Servidor

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check (público) |
| `GET` | `/agents` | Sí | Lista de agentes (REST) |
| `POST` | `/mcp` | Sí | JSON-RPC sobre HTTP (Streamable HTTP transport) |
| `GET` | `/sse` | Sí | Server-Sent Events (notificaciones en tiempo real) |
| `POST` | `/sse` | Sí | MCP sobre SSE (bidireccional) |

## Patterns — Comandos por Caso de Uso

### Iniciar el servidor

```bash
# Básico (puerto 3777, sin auth — solo desarrollo)
python .agent/mcp/remote-server.py

# Con autenticación (obligatorio para producción)
export ANTIGRAVITY_API_TOKEN=$(python .agent/skills/remote-control/scripts/remote_control.py token)
ANTIGRAVITY_API_TOKEN=$ANTIGRAVITY_API_TOKEN python .agent/mcp/remote-server.py

# Puerto y host personalizados
python .agent/mcp/remote-server.py --port 8777 --host 127.0.0.1

# Con home explícito (cuando se ejecuta desde otro directorio)
python .agent/mcp/remote-server.py --home /ruta/a/AntigravitiSkillUSN
```

### Usando el helper CLI

```bash
# Verificar estado del servidor
python .agent/skills/remote-control/scripts/remote_control.py health

# Health contra URL personalizada
python .agent/skills/remote-control/scripts/remote_control.py health --url http://192.168.1.100:3777

# Generar configuración .mcp.json para IDE remoto
python .agent/skills/remote-control/scripts/remote_control.py config

# Config con URL y token específicos
python .agent/skills/remote-control/scripts/remote_control.py config \
  --url http://mi-servidor:3777 \
  --token mi-token-secreto

# Generar token seguro
python .agent/skills/remote-control/scripts/remote_control.py token
```

### Verificar manualmente con curl

```bash
# Health check (sin auth)
curl http://localhost:3777/health

# Lista de agentes (con token)
curl -H "Authorization: Bearer $ANTIGRAVITY_API_TOKEN" http://localhost:3777/agents

# MCP request manual
curl -X POST http://localhost:3777/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ANTIGRAVITY_API_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Configuración IDE remoto

El snippet generado por `config` tiene este formato:

```json
{
  "mcpServers": {
    "antigravity-remote": {
      "url": "http://TU_IP:3777/mcp",
      "headers": {
        "Authorization": "Bearer TU_TOKEN"
      }
    }
  }
}
```

Pegar en:
- **Claude Code**: `~/.claude/mcp.json` o `.mcp.json` del proyecto
- **Cursor**: `~/.cursor/mcp.json`
- **Windsurf**: `~/.codeium/windsurf/mcp_config.json`

### Con Docker Compose

```bash
# Arrancar el servicio remoto
ANTIGRAVITY_API_TOKEN=mi-token docker-compose up mcp-remote -d

# Ver logs
docker-compose logs -f mcp-remote

# Verificar health dentro del contenedor
docker-compose exec mcp-remote curl http://localhost:3777/health
```

## Variables de Entorno

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `ANTIGRAVITY_API_TOKEN` | Token Bearer para autenticación | No (pero sí en producción) |
| `ANTIGRAVITY_HOME` | Ruta base del ecosistema | No (auto-detectada) |

## Anti-Patterns

| ❌ Evitar | ✅ Hacer en su lugar |
|----------|---------------------|
| `subprocess.run(cmd, shell=True)` | `subprocess.run(shlex.split(cmd), shell=False)` |
| Hardcodear token en el código | Leer de `os.environ.get("ANTIGRAVITY_API_TOKEN")` |
| Exponer sin auth en producción | Definir `ANTIGRAVITY_API_TOKEN` siempre |
| Commitear `.env` con el token | Usar `.env.example` como plantilla |
| Compartir token por texto plano | Generar uno nuevo con `remote_control.py token` |

## Notas de Seguridad

- La comparación de tokens usa `secrets.compare_digest` (timing-safe, evita timing attacks)
- Sin `ANTIGRAVITY_API_TOKEN`, el servidor acepta **todas** las conexiones — solo para desarrollo local
- El endpoint `/health` es siempre público (sin auth) para facilitar monitoreo
- En producción, combinar con firewall que restrinja el puerto 3777 por IP

## Related Skills

- `mcp-integration` — Configuración general de MCP servers en el ecosistema
- `secrets-management` — Gestión segura de credenciales y tokens
- `docker-compose` — Orquestación del stack completo de servicios
