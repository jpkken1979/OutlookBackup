---
name: cloudflare-durable-objects
description: "Durable Objects en Cloudflare Workers. Átomos de coordinación con getByName, SQLite storage, RPC methods, alarms y vitest testing."
type: feature
---

# Cloudflare Durable Objects

Guía para usar Durable Objects como átomos de coordinación con estado persistente.

## Concepto

Durable Objects son instancias singleton con:
- **Estado persistente** — SQLite integrado
- **Single-threaded** — Sin race conditions
- **Ubicación global** — Se ejecutan cerca del primer request
- **WebSocket support** — Comunicación en tiempo real

## Clase Base

```typescript
import { DurableObject } from "cloudflare:workers";

export class Counter extends DurableObject<Env> {
  private count: number = 0;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
  }

  // Inicialización con blockConcurrencyWhile
  async initialize() {
    await this.ctx.blockConcurrencyWhile(async () => {
      const stored = await this.ctx.storage.get<number>("count");
      this.count = stored ?? 0;
    });
  }

  async increment(): Promise<number> {
    this.count++;
    await this.ctx.storage.put("count", this.count);
    return this.count;
  }

  async getCount(): Promise<number> {
    return this.count;
  }
}
```

## Routing con getByName

```typescript
export default {
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url);
    const name = url.searchParams.get("room") ?? "default";

    // Obtener stub por nombre (determinístico)
    const id = env.COUNTER.idFromName(name);
    const stub = env.COUNTER.get(id);

    // Llamar método RPC
    const count = await stub.increment();
    return new Response(`Count: ${count}`);
  },
};
```

## SQLite Storage

```typescript
export class DataStore extends DurableObject<Env> {
  sql = this.ctx.storage.sql;

  async initialize() {
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        data TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  async addItem(name: string, data: string): Promise<string> {
    const id = crypto.randomUUID();
    this.sql.exec(
      "INSERT INTO items (id, name, data) VALUES (?, ?, ?)",
      id, name, data
    );
    return id;
  }

  async getItem(id: string): Promise<Record<string, unknown> | null> {
    const cursor = this.sql.exec(
      "SELECT * FROM items WHERE id = ?", id
    );
    const rows = [...cursor];
    return rows.length > 0 ? rows[0] as Record<string, unknown> : null;
  }

  async listItems(limit: number = 50): Promise<Record<string, unknown>[]> {
    const cursor = this.sql.exec(
      "SELECT * FROM items ORDER BY created_at DESC LIMIT ?", limit
    );
    return [...cursor] as Record<string, unknown>[];
  }
}
```

## RPC Methods

```typescript
export class TaskManager extends DurableObject<Env> {
  // Los métodos públicos son automáticamente invocables via RPC
  async createTask(title: string, assignee: string): Promise<string> {
    const id = crypto.randomUUID();
    this.sql.exec(
      "INSERT INTO tasks (id, title, assignee, status) VALUES (?, ?, ?, 'pending')",
      id, title, assignee
    );
    return id;
  }

  async completeTask(id: string): Promise<boolean> {
    this.sql.exec(
      "UPDATE tasks SET status = 'done', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
      id
    );
    return true;
  }
}

// Llamada desde Worker
const result = await stub.createTask("Fix bug", "alice");
```

## Alarms

```typescript
export class Scheduler extends DurableObject<Env> {
  async scheduleTask(delayMs: number) {
    // Programar alarm
    await this.ctx.storage.setAlarm(Date.now() + delayMs);
  }

  // Se ejecuta cuando el alarm dispara
  async alarm() {
    console.log("Alarm fired! Running scheduled task...");
    // Ejecutar tarea programada
    await this.processQueue();

    // Reprogramar si hay más trabajo
    const pending = this.sql.exec("SELECT COUNT(*) as c FROM queue").one();
    if (pending.c > 0) {
      await this.ctx.storage.setAlarm(Date.now() + 60_000);
    }
  }
}
```

## Testing con Vitest

```typescript
import { env, createExecutionContext } from "cloudflare:test";
import { describe, it, expect } from "vitest";

describe("Counter Durable Object", () => {
  it("should increment count", async () => {
    const id = env.COUNTER.idFromName("test");
    const stub = env.COUNTER.get(id);

    const count1 = await stub.increment();
    expect(count1).toBe(1);

    const count2 = await stub.increment();
    expect(count2).toBe(2);
  });

  it("should persist state", async () => {
    const id = env.COUNTER.idFromName("persist-test");
    const stub = env.COUNTER.get(id);

    await stub.increment();
    const count = await stub.getCount();
    expect(count).toBe(1);
  });
});
```

```typescript
// vitest.config.ts
import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        wrangler: { configPath: "./wrangler.toml" },
      },
    },
  },
});
```

## Anti-Patterns

- **NO** crear Durable Objects para datos read-only → usar KV o D1
- **NO** asumir ubicación geográfica → se posicionan automáticamente
- **NO** almacenar datos grandes en storage.get/put → usar SQL o R2
- **NO** bloquear el event loop con operaciones sincrónicas largas
- **NO** crear un DO por request → usar getByName para reusar instancias

## Wrangler Config

```toml
[[durable_objects.bindings]]
name = "COUNTER"
class_name = "Counter"

[[migrations]]
tag = "v1"
new_sqlite_classes = ["Counter"]
```

## Recursos

- [Durable Objects Docs](https://developers.cloudflare.com/durable-objects/)
- [SQLite in DO](https://developers.cloudflare.com/durable-objects/api/storage-api/)
- [Testing DO](https://developers.cloudflare.com/workers/testing/vitest-integration/testing-durable-objects/)
