---
name: cloudflare-mcp-server
description: "Construye MCP servers en Cloudflare Workers con McpAgent. Tools con Zod validation, OAuth auth, templates público/autenticado, deploy con wrangler."
type: feature
---

# Building MCP Servers on Cloudflare

Guía para construir servidores MCP (Model Context Protocol) en Cloudflare Workers.

## Arquitectura

```
AI Client (Claude, Cursor, etc.)
    ↕ MCP Protocol (SSE/WebSocket)
Cloudflare Worker
    ↕
McpAgent (Durable Object)
    ↕
Bindings (D1, KV, R2, AI)
```

## McpAgent Class

```typescript
import { McpAgent } from "@cloudflare/agents/mcp";
import { z } from "zod";

interface Env {
  MY_KV: KVNamespace;
  MY_D1: D1Database;
}

export class MyMcpServer extends McpAgent<Env> {
  server = {
    name: "my-mcp-server",
    version: "1.0.0",
  };

  async init() {
    // Definir herramientas
    this.server.tool(
      "get_data",
      "Retrieves data by key from the store",
      { key: z.string().describe("The key to look up") },
      async ({ key }) => {
        const value = await this.env.MY_KV.get(key);
        return {
          content: [{ type: "text", text: value ?? "Not found" }],
        };
      }
    );

    this.server.tool(
      "query_database",
      "Runs a read-only SQL query",
      {
        query: z.string().describe("SQL SELECT query"),
        params: z.array(z.string()).optional().describe("Query parameters"),
      },
      async ({ query, params }) => {
        const result = await this.env.MY_D1
          .prepare(query)
          .bind(...(params ?? []))
          .all();
        return {
          content: [{ type: "text", text: JSON.stringify(result.results) }],
        };
      }
    );
  }
}
```

## Tool Definition con Zod

```typescript
// Los parámetros se validan automáticamente con Zod
this.server.tool(
  "create_item",                          // nombre
  "Creates a new item in the database",   // descripción
  {                                       // schema Zod
    name: z.string().min(1).max(100),
    type: z.enum(["task", "note", "event"]),
    priority: z.number().int().min(1).max(5).default(3),
    tags: z.array(z.string()).optional(),
  },
  async ({ name, type, priority, tags }) => {
    // Implementación...
    return {
      content: [{ type: "text", text: `Created: ${name}` }],
    };
  }
);
```

## Templates

### Servidor Público (Sin Auth)

```typescript
// Para herramientas de solo lectura, datos públicos
export default {
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url);

    if (url.pathname === "/sse" || url.pathname === "/mcp") {
      return MyMcpServer.serveSSE(request, env);
    }

    return new Response("MCP Server", { status: 200 });
  },
};
```

### Servidor Autenticado (OAuth)

```typescript
import { OAuthProvider } from "@cloudflare/agents/oauth";

export default {
  async fetch(request: Request, env: Env) {
    // OAuth flow
    const auth = new OAuthProvider({
      providers: {
        github: {
          clientId: env.GITHUB_CLIENT_ID,
          clientSecret: env.GITHUB_CLIENT_SECRET,
          scopes: ["read:user"],
        },
      },
    });

    const session = await auth.authenticate(request);
    if (!session) {
      return auth.redirect(request);
    }

    return MyMcpServer.serveSSE(request, env, { user: session.user });
  },
};
```

## OAuth Providers Soportados

| Provider | Config |
|----------|--------|
| GitHub | `clientId`, `clientSecret`, `scopes` |
| Google | `clientId`, `clientSecret`, `scopes` |
| Auth0 | `domain`, `clientId`, `clientSecret` |

## Wrangler Config

```toml
name = "my-mcp-server"
main = "src/index.ts"
compatibility_date = "2025-01-01"

[[d1_databases]]
binding = "MY_D1"
database_name = "my-database"
database_id = "xxx"

[[kv_namespaces]]
binding = "MY_KV"
id = "xxx"

[[durable_objects.bindings]]
name = "MCP_SERVER"
class_name = "MyMcpServer"

[[migrations]]
tag = "v1"
new_sqlite_classes = ["MyMcpServer"]
```

## Client Configuration

### Claude Code
```bash
claude mcp add my-server --url https://my-mcp-server.workers.dev/sse
```

### Cursor
```json
{
  "mcpServers": {
    "my-server": {
      "url": "https://my-mcp-server.workers.dev/sse"
    }
  }
}
```

## Deploy

```bash
npx wrangler deploy
```

## Recursos

- [Cloudflare MCP Docs](https://developers.cloudflare.com/agents/mcp/)
- [MCP Protocol Spec](https://modelcontextprotocol.io/)
- [Zod Schema Validation](https://zod.dev/)
