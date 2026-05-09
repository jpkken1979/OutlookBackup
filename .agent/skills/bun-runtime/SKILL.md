---
name: bun-runtime
description: Skill especializado en Bun, el runtime JavaScript ultrarapido con bundler, test runner y package manager integrados
type: feature
---

# Bun Runtime

Skill especializado en Bun - el runtime JavaScript ultrarapido con bundler, test runner y package manager integrados.

## Descripcion

Bun es un runtime JavaScript/TypeScript escrito en Zig que ofrece:

- 4x mas rapido que Node.js
- Bundler nativo (reemplaza webpack/esbuild)
- Test runner integrado
- Package manager compatible con npm
- SQLite nativo
- Native APIs modernas

## Capacidades

- Migrar proyectos Node.js a Bun
- Configurar bundling con Bun
- Escribir tests con Bun test runner
- Usar Bun como package manager
- Implementar APIs con Bun.serve()
- Usar SQLite nativo

## Uso

### HTTP Server

```typescript
Bun.serve({
  port: 3000,
  fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/api/users") {
      return Response.json({ users: [] });
    }

    return new Response("Hello Bun!");
  },
});
```

### Bundler

```typescript
// bun build
await Bun.build({
  entrypoints: ['./src/index.ts'],
  outdir: './dist',
  minify: true,
  splitting: true,
  sourcemap: 'external',
  target: 'browser',
});
```

### Test Runner

```typescript
// example.test.ts
import { expect, test, describe } from "bun:test";

describe("math", () => {
  test("2 + 2", () => {
    expect(2 + 2).toBe(4);
  });
});

// Ejecutar: bun test
```

### SQLite Nativo

```typescript
import { Database } from "bun:sqlite";

const db = new Database("mydb.sqlite");

db.run(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT
  )
`);

const insert = db.prepare("INSERT INTO users (name) VALUES (?)");
insert.run("Alice");

const users = db.query("SELECT * FROM users").all();
```

## Patrones Comunes

### File I/O Rapido

```typescript
// Leer archivo
const content = await Bun.file("./data.json").text();
const json = await Bun.file("./data.json").json();

// Escribir archivo
await Bun.write("./output.txt", "Hello World");
await Bun.write("./data.json", JSON.stringify(data));
```

### Password Hashing

```typescript
const password = "super-secure";

// Hash
const hash = await Bun.password.hash(password);

// Verify
const isMatch = await Bun.password.verify(password, hash);
```

### WebSockets

```typescript
Bun.serve({
  fetch(req, server) {
    if (server.upgrade(req)) {
      return; // Upgraded to WebSocket
    }
    return new Response("Upgrade failed", { status: 500 });
  },
  websocket: {
    message(ws, message) {
      ws.send(`Echo: ${message}`);
    },
  },
});
```

### Package Manager

```bash
# Instalar dependencias (4x mas rapido que npm)
bun install

# Agregar paquete
bun add express

# Dev dependency
bun add -d typescript

# Global
bun add -g serve
```

## Migracion desde Node.js

```bash
# 1. Instalar Bun
curl -fsSL https://bun.sh/install | bash

# 2. Reemplazar package-lock.json
rm package-lock.json
bun install  # Genera bun.lockb

# 3. Ejecutar
bun run src/index.ts
```

## Configuracion

```json
// bunfig.toml
[install]
optional = false

[run]
preload = ["./src/preload.ts"]

[test]
preload = ["./test/setup.ts"]
```

## Tags

bun, javascript, typescript, bundler, runtime, fast, sqlite

## Version

1.0.0

## Autor

Antigravity Team
