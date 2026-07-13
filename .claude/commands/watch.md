Lanzar procesos en background con matching reactivo de patrones via MCP `antigravity-watcher`.

## Cuando usarlo

- Necesitas correr un dev server / daemon / build largo y reaccionar a eventos en su output.
- Queres historial de matches (errores, eventos importantes) persistido en SQLite.
- Preferis notificaciones reactivas sobre polling manual del output.

## Uso

```
/watch                                    # listar watches activos + historial
/watch <cmd>                              # spawn con patterns inferidos
/watch tauri                              # preset: npm run tauri:dev con patterns
/watch gateway                            # preset: python start_gateway.py
/watch tests                              # preset: make test
/watch telegram                           # preset: npm run dev (bot)
/watch status <watch_id>                  # estado del watch
/watch tail <watch_id> [lines]            # ultimas lineas stdout/stderr
/watch matches <watch_id> [limit]         # matches persistidos
/watch kill <watch_id>                    # terminar proceso
/watch cleanup                            # purgar viejos (TTL)
/watch stats                              # metricas globales
```

## Flujo

1. Inferi el modo segun los argumentos.

2. Si es un preset conocido, usa los patterns predefinidos:

### Preset `tauri`
```json
{
  "cmd": "npm run tauri:dev",
  "cwd": "nexus-app",
  "label": "nexus-dev",
  "patterns": [
    {"regex": "Compiled successfully|ready in", "label": "dev ready", "importance": "high"},
    {"regex": "error\\[E\\d+|rustc: error", "label": "rust error", "importance": "critical", "auto_brain_ingest": true},
    {"regex": "error TS\\d+", "label": "ts error", "importance": "high"},
    {"regex": "EADDRINUSE|Address already in use", "label": "port conflict", "importance": "critical"}
  ]
}
```

### Preset `gateway`
```json
{
  "cmd": "python start_gateway.py",
  "label": "gateway",
  "patterns": [
    {"regex": "Uvicorn running on", "label": "gateway up", "importance": "high"},
    {"regex": "Address already in use|EADDRINUSE", "label": "port conflict", "importance": "critical"},
    {"regex": "Traceback \\(most recent", "label": "python traceback", "importance": "critical", "auto_brain_ingest": true}
  ]
}
```

### Preset `tests`
```json
{
  "cmd": "make test",
  "label": "pytest suite",
  "patterns": [
    {"regex": "FAILED|ERROR", "label": "test failed", "importance": "critical", "auto_brain_ingest": true},
    {"regex": "\\d+ passed", "label": "summary", "importance": "high"}
  ]
}
```

### Preset `telegram`
```json
{
  "cmd": "npm run dev",
  "label": "telegram-bot",
  "patterns": [
    {"regex": "Long polling started|Bot .* started", "label": "bot online", "importance": "high"},
    {"regex": "Unauthorized|401|TelegramError", "label": "telegram auth fail", "importance": "critical", "auto_brain_ingest": true}
  ]
}
```

3. Si es un comando arbitrario, pregunta brevemente al usuario que patterns quiere
   (o inferilos por heuristica: si el comando es `make`, `pytest`, `npm run`, ya
   tenes defaults sensibles).

4. Ejecuta `watch_spawn` y devolve el `watch_id` al usuario.

5. Si el usuario pide `status`, `tail`, `matches`, `kill`, `cleanup`, `stats`:
   llama la tool MCP correspondiente y presenta el resultado de forma tabular
   y breve.

## Formato de presentacion

Listar watches:

```
## Watches activos (3)

| watch_id      | label          | state   | pid   | matches | started |
|---------------|----------------|---------|-------|---------|---------|
| w-abc123..    | nexus-dev      | running | 12345 | 2       | 14:22   |
| w-def456..    | gateway        | running | 12346 | 1       | 14:25   |
| w-ghi789..    | pytest suite   | exited  | 12347 | 0       | 14:30   |
```

Estado individual:

```
## Watch w-abc123

**cmd**: npm run tauri:dev (cwd=nexus-app)
**estado**: running (pid 12345)
**inicio**: 14:22:03
**matches**: 2

### Patterns
- dev ready (high) — regex: Compiled successfully|ready in
- rust error (critical) — regex: error\[E\d+
```

## Reglas

- Responder en espanol.
- Usar las tools MCP directamente (no shell `bash run_in_background`).
- Si el usuario no especifica `importance`, usar `high` para keywords de error.
- Al spawnear, recordarle al usuario el `watch_id` y como ver tail/matches.
- Si falla el spawn, no reintentar silenciosamente — mostrar el error y sugerir fix.
