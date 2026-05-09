---
name: deno-v2
description: Skill especializado en Deno 2, el runtime JavaScript/TypeScript seguro y moderno con compatibilidad Node.js
type: feature
---

# Deno v2

Skill especializado en Deno 2 - el runtime JavaScript/TypeScript seguro y moderno con Node.js compatibility.

## Descripcion

Deno 2 trae compatibilidad total con Node.js y npm, manteniendo su modelo de seguridad:

- Compatibilidad con npm y Node.js
- TypeScript nativo sin configuracion
- Permisos granulares de seguridad
- Deploy integrado (Deno Deploy)
- Fresh framework para web
- JSR (JavaScript Registry)

## Capacidades

- Migrar proyectos Node.js a Deno
- Usar npm packages en Deno
- Configurar permisos de seguridad
- Deploy en edge con Deno Deploy
- Desarrollar con Fresh framework
- Publicar en JSR

## Uso

### HTTP Server

```typescript
Deno.serve({ port: 3000 }, (request) => {
  const url = new URL(request.url);

  if (url.pathname === "/api/users") {
    return Response.json({ users: [] });
  }

  return new Response("Hello Deno!");
});
```

### Compatibilidad npm

```typescript
// package.json (opcional)
// o importar directamente
import express from "npm:express@4";
import { z } from "npm:zod";

const app = express();
app.get("/", (req, res) => res.send("Hello!"));
app.listen(3000);
```

### Permisos de Seguridad

```bash
# Ejecutar con permisos especificos
deno run --allow-net --allow-read server.ts

# Permisos granulares
deno run --allow-net=api.example.com server.ts
deno run --allow-read=./data server.ts

# Todos los permisos (desarrollo)
deno run -A server.ts
```

### Fresh Framework

```typescript
// routes/index.tsx
export default function Home() {
  return (
    <div>
      <h1>Welcome to Fresh!</h1>
    </div>
  );
}

// routes/api/users.ts
export const handler = {
  GET(_req: Request) {
    return Response.json({ users: [] });
  },
};
```

## Patrones Comunes

### File I/O

```typescript
// Leer archivo
const content = await Deno.readTextFile("./data.json");
const data = JSON.parse(content);

// Escribir archivo
await Deno.writeTextFile("./output.txt", "Hello World");

// Leer binario
const bytes = await Deno.readFile("./image.png");
```

### Testing Nativo

```typescript
// example_test.ts
import { assertEquals } from "jsr:@std/assert";

Deno.test("2 + 2 equals 4", () => {
  assertEquals(2 + 2, 4);
});

Deno.test("async test", async () => {
  const data = await fetchData();
  assertEquals(data.length, 10);
});

// Ejecutar: deno test
```

### JSR (JavaScript Registry)

```typescript
// Importar desde JSR
import { parseArgs } from "jsr:@std/cli/parse-args";
import { join } from "jsr:@std/path";

// Publicar a JSR
// deno publish
```

### KV Store (Deno Deploy)

```typescript
const kv = await Deno.openKv();

// Set
await kv.set(["users", "123"], { name: "Alice" });

// Get
const entry = await kv.get(["users", "123"]);
console.log(entry.value);

// List
const entries = kv.list({ prefix: ["users"] });
for await (const entry of entries) {
  console.log(entry);
}
```

### WebSockets

```typescript
Deno.serve((req) => {
  if (req.headers.get("upgrade") === "websocket") {
    const { socket, response } = Deno.upgradeWebSocket(req);

    socket.onmessage = (e) => {
      socket.send(`Echo: ${e.data}`);
    };

    return response;
  }

  return new Response("Not a WebSocket request");
});
```

## Configuracion

```json
// deno.json
{
  "tasks": {
    "dev": "deno run -A --watch src/main.ts",
    "test": "deno test -A",
    "build": "deno compile src/main.ts"
  },
  "imports": {
    "@std/": "jsr:@std/",
    "express": "npm:express@4"
  },
  "compilerOptions": {
    "strict": true
  }
}
```

## Migracion desde Node.js

```bash
# 1. Instalar Deno
curl -fsSL https://deno.land/install.sh | sh

# 2. Crear deno.json
deno init

# 3. Agregar node: prefix para builtins
# import fs from "node:fs";
# import path from "node:path";

# 4. Ejecutar
deno run -A src/index.ts
```

## Deploy

```bash
# Deno Deploy (edge)
deployctl deploy --project=my-project src/main.ts

# Compile a ejecutable
deno compile --output=app src/main.ts
```

## Tags

deno, javascript, typescript, secure, edge, fresh, jsr, npm-compat

## Version

1.0.0

## Autor

Antigravity Team
