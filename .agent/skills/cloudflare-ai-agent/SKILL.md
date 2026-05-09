---
name: cloudflare-ai-agent
description: "Construye agentes IA en Cloudflare Workers con el Agents SDK. Clase Agent con estado persistente, WebSocket, SQL storage, scheduled tasks y React useAgent hook."
type: feature
---

# Building AI Agents on Cloudflare

Guía para construir agentes IA con el Cloudflare Agents SDK sobre Workers.

## Arquitectura

```
Client (React) ←→ WebSocket ←→ Worker (Agent) ←→ AI Models
                                    ↕
                              Durable Object
                              (State + SQL)
```

## Agent Class

```typescript
import { Agent } from "@cloudflare/agents";

interface Env {
  AI: Ai;
  MY_KV: KVNamespace;
}

interface AgentState {
  messages: Message[];
  context: Record<string, unknown>;
  status: "idle" | "thinking" | "responding";
}

export class MyAgent extends Agent<Env, AgentState> {
  // Inicialización del estado
  initialState: AgentState = {
    messages: [],
    context: {},
    status: "idle",
  };

  // WebSocket: nueva conexión
  async onConnect(connection: Connection, ctx: ConnectionContext) {
    console.log("Client connected:", connection.id);
  }

  // WebSocket: mensaje recibido
  async onMessage(connection: Connection, message: string) {
    const userMessage = JSON.parse(message);

    // Actualizar estado (persiste automáticamente)
    this.setState({
      ...this.state,
      messages: [...this.state.messages, userMessage],
      status: "thinking",
    });

    // Llamar al modelo AI
    const response = await this.env.AI.run("@cf/meta/llama-3-8b-instruct", {
      messages: this.state.messages,
    });

    // Enviar respuesta al cliente
    connection.send(JSON.stringify({
      role: "assistant",
      content: response.response,
    }));

    this.setState({ ...this.state, status: "idle" });
  }

  // WebSocket: desconexión
  async onClose(connection: Connection) {
    console.log("Client disconnected:", connection.id);
  }
}
```

## State Management

```typescript
// setState persiste automáticamente en Durable Object storage
this.setState({
  ...this.state,
  messages: [...this.state.messages, newMessage],
});

// State es reactive — cambios se propagan a clientes suscritos
// Usar spread para inmutabilidad
```

## SQL Storage

```typescript
export class MyAgent extends Agent<Env, AgentState> {
  async onStart() {
    // Crear tablas al iniciar
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        summary TEXT
      )
    `);
  }

  async saveConversation(userId: string, summary: string) {
    this.sql.exec(
      "INSERT INTO conversations (id, user_id, summary) VALUES (?, ?, ?)",
      [crypto.randomUUID(), userId, summary]
    );
  }
}
```

## Scheduled Tasks

```typescript
export class MyAgent extends Agent<Env, AgentState> {
  // Tarea programada via cron
  async onCron(trigger: string) {
    if (trigger === "cleanup") {
      // Limpiar conversaciones antiguas
      this.sql.exec(
        "DELETE FROM conversations WHERE created_at < datetime('now', '-30 days')"
      );
    }
  }
}

// wrangler.toml
// [triggers]
// crons = ["0 0 * * *"]  # Diario a medianoche
```

## AIChatAgent (Subclase para Chat)

```typescript
import { AIChatAgent } from "@cloudflare/agents";

export class ChatBot extends AIChatAgent<Env> {
  async onChatMessage(onFinish: StreamCallback) {
    const result = await this.env.AI.run("@cf/meta/llama-3-8b-instruct", {
      messages: this.messages,
      stream: true,
    });
    return result;
  }
}
```

## React Client (useAgent Hook)

```tsx
import { useAgent } from "@cloudflare/agents/react";

function ChatApp() {
  const { state, sendMessage, isConnected } = useAgent({
    agent: "my-agent",
    name: "chat-session-123",
  });

  return (
    <div>
      <div>{isConnected ? "Connected" : "Disconnecting..."}</div>
      {state.messages.map((msg, i) => (
        <div key={i}>{msg.role}: {msg.content}</div>
      ))}
      <button onClick={() => sendMessage({ role: "user", content: "Hello!" })}>
        Send
      </button>
    </div>
  );
}
```

## Wrangler Config

```toml
# wrangler.toml
name = "my-ai-agent"
main = "src/index.ts"
compatibility_date = "2025-01-01"

[ai]
binding = "AI"

[[durable_objects.bindings]]
name = "MY_AGENT"
class_name = "MyAgent"

[[migrations]]
tag = "v1"
new_sqlite_classes = ["MyAgent"]
```

## Deploy

```bash
# Desarrollo local
npx wrangler dev

# Deploy a producción
npx wrangler deploy
```

## Recursos

- [Cloudflare Agents Docs](https://developers.cloudflare.com/agents/)
- [Agents SDK](https://github.com/cloudflare/agents)
- [Workers AI Models](https://developers.cloudflare.com/workers-ai/models/)
