---
name: openai-render-deploy
description: "Despliega aplicaciones en Render.com usando Blueprint (render.yaml) o Direct Creation via MCP. Soporta deeplinks, OAuth setup y post-deploy verification."
type: feature
---

# Deploy to Render

Despliega aplicaciones web, APIs y servicios en Render.com.

## Métodos de Despliegue

### 1. Blueprint (render.yaml)
Infraestructura como código declarativa:

```yaml
# render.yaml
services:
  - type: web
    name: my-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: mydb
          property: connectionString

databases:
  - name: mydb
    plan: starter
    databaseName: myapp_db
```

### 2. Direct Creation (MCP)
Creación directa via herramientas MCP de Render:

```
mcp__render__create_service({
  name: "my-api",
  type: "web",
  repo: "https://github.com/user/repo",
  branch: "main",
  runtime: "python"
})
```

## Workflow

1. **Preparar aplicación** — Dockerfile o buildpack compatible.
2. **Configurar render.yaml** — Definir servicios, databases, env vars.
3. **Conectar repo** — Vincular repositorio GitHub/GitLab.
4. **Deploy** — Push a branch o trigger manual.
5. **Verificar** — Health checks y smoke tests post-deploy.
6. **Generar deeplink** — URL de deploy directo para compartir.

## MCP Setup

### Cursor
```json
{
  "mcpServers": {
    "render": {
      "command": "npx",
      "args": ["-y", "@render/mcp-server"],
      "env": {
        "RENDER_API_KEY": "rnd_xxx"
      }
    }
  }
}
```

### Claude Code
```bash
claude mcp add render -- npx -y @render/mcp-server
export RENDER_API_KEY=rnd_xxx
```

## Deeplinks

Generar URLs de deploy one-click:

```
https://render.com/deploy?repo=https://github.com/user/repo
```

Con render.yaml, esto configura automáticamente todos los servicios.

## Post-Deploy Verification

```bash
# Health check
curl -f https://my-api.onrender.com/health

# Smoke test
curl -X POST https://my-api.onrender.com/api/test \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

## Tipos de Servicio

| Tipo | Uso |
|------|-----|
| Web Service | APIs, aplicaciones web |
| Static Site | SPAs, sitios estáticos |
| Background Worker | Jobs, procesamiento async |
| Cron Job | Tareas programadas |
| Private Service | Servicios internos (no público) |

## Variables de Entorno

```yaml
envVars:
  - key: API_KEY
    sync: false          # No sincronizar entre deploys
  - key: NODE_ENV
    value: production    # Valor estático
  - key: DB_URL
    fromDatabase:        # Referencia a otro servicio
      name: mydb
      property: connectionString
```

## Recursos

- [Render Docs](https://render.com/docs)
- [Blueprint Spec](https://render.com/docs/blueprint-spec)
- [Render MCP](https://github.com/render-oss/render-mcp-server)
