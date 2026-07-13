# Regla: Watch Patterns — procesos en background con matching reactivo

Aplica a todas las sesiones de Claude Code en este repositorio.

## Principio

Cuando necesites lanzar un proceso largo (dev server, test runner, build,
daemon) y reaccionar a eventos en su output, usa el MCP `antigravity-watcher`
en vez del flujo `bash run_in_background + grep + poll`. El watcher detecta
patrones regex en tiempo real, notifica al gateway local y opcionalmente
ingesta matches criticos al Brain.

## Cuando preferir `watch_spawn` sobre `bash run_in_background`

Usa la tool MCP `watch_spawn` cuando se cumpla al menos una:

1. **Necesitas saber cuando algo aparezca en el output** sin releer manualmente.
2. **El proceso es de larga duracion** (dev server, daemon, tail -f, telegram bot).
3. **Queres alertas proactivas** en errores recurrentes (`error\[E`, `panic:`, `FAILED`).
4. **Queres historial de matches** para auditar que paso (persistido en SQLite).

## Cuando NO usarlo

- **Comandos one-shot** (< 5s) con salida chica: usa `Bash` normal.
- **Scripts interactivos** que esperan stdin: el watcher redirige stdin a DEVNULL.
- **Comandos que requieren shell features** (pipes, redirecciones inline): envolver
  en `bash -c "..."` antes; shell=False fuerza shlex.split.

## Tools MCP disponibles

| Tool | Proposito |
|---|---|
| `watch_spawn(cmd, patterns, cwd?, label?)` | Lanza proceso + inicia matching |
| `watch_status(watch_id)` | Estado + metadata del proceso |
| `watch_tail(watch_id, lines?, stream?)` | Ultimas N lineas stdout/stderr (en memoria) |
| `watch_matches(watch_id, limit?)` | Matches persistidos (SQLite) |
| `watch_kill(watch_id)` | SIGTERM + SIGKILL fallback |
| `watch_list(include_finished?)` | Activos + 50 historicos recientes |
| `watch_stats()` | Metricas globales |
| `watch_cleanup()` | Purgar finalizados viejos (TTL 7 dias default) |
| `watch_status_engine()` | Config activa + path del store |

## Endpoints HTTP del gateway (`:4747/v1/watcher/*`)

Complementan las tools MCP para clientes que no son Claude Code.

| Endpoint | Descripcion |
|---|---|
| `POST /v1/watcher/events` | Ingesta de un evento (usado por el engine internamente) |
| `GET  /v1/watcher/events/recent?limit&importance` | Historial in-memory (ring buffer) |
| `GET  /v1/watcher/events/history?limit&importance&watch_id` | Historial persistido SQLite (sobrevive restarts) |
| `GET  /v1/watcher/stream?importance` | SSE stream en vivo para Nexus/browser/bots |
| `GET  /v1/watcher/status` | Estado subsistema (dedup, rate-limit, bus, store) |
| `GET  /v1/watcher/metrics` | Counters Prometheus (o JSON con `Accept: application/json`) |
| `POST /v1/watcher/spawn` | Lanzar proceso via daemon hospedado en el gateway |
| `GET  /v1/watcher/list?include_finished` | Listar watches |
| `POST /v1/watcher/{watch_id}/kill` | Terminar proceso |
| `GET  /v1/watcher/{watch_id}/tail?lines&stream` | Tail stdout/stderr |

### Daemon persistente via gateway

A diferencia del MCP server (vive mientras Claude Code esta conectado), el
gateway hostea un ProcessWatcher singleton. Los watches spawneados via
`POST /v1/watcher/spawn` sobreviven cierres de IDE / bot / Nexus mientras
el gateway este arriba. Ideal para procesos largos (dev server) que querer
que sigan corriendo aunque cambies de contexto.

## Formato de patterns

```json
{
  "regex": "error\\[E\\d+",
  "label": "rust compile error",
  "importance": "critical",
  "auto_brain_ingest": true
}
```

- `importance`:
  - `low`: solo persiste en SQLite, sin notificar.
  - `high`: notifica al gateway (`POST :4747/v1/watcher/events`).
  - `critical`: notifica + si `auto_brain_ingest=true`, ingesta al Brain como `pattern`.

## Ejemplos concretos del ecosistema

### Tauri dev

```json
{
  "cmd": "npm run tauri:dev",
  "cwd": "nexus-app",
  "label": "nexus-dev",
  "patterns": [
    {"regex": "Compiled successfully", "label": "dev ready", "importance": "high"},
    {"regex": "error\\[E\\d+", "label": "rust error", "importance": "critical", "auto_brain_ingest": true},
    {"regex": "error TS\\d+", "label": "ts error", "importance": "high"}
  ]
}
```

### Gateway local

```json
{
  "cmd": "python start_gateway.py",
  "label": "gateway",
  "patterns": [
    {"regex": "Uvicorn running on", "label": "gateway up", "importance": "high"},
    {"regex": "Address already in use", "label": "port conflict", "importance": "critical"}
  ]
}
```

### Test runner

```json
{
  "cmd": "make test",
  "label": "pytest suite",
  "patterns": [
    {"regex": "FAILED", "label": "test failed", "importance": "critical", "auto_brain_ingest": true},
    {"regex": "\\d+ passed", "label": "summary", "importance": "high"}
  ]
}
```

### Bot Telegram

```json
{
  "cmd": "npm run dev",
  "label": "telegram-bot",
  "patterns": [
    {"regex": "Long polling started", "label": "bot online", "importance": "high"},
    {"regex": "Unauthorized|401", "label": "auth fail", "importance": "critical"}
  ]
}
```

## Flujo recomendado

1. Arrancas el proceso con `watch_spawn` y guardas el `watch_id`.
2. Seguis trabajando; cuando matchee algo importante, lo ves via notificacion del gateway.
3. Si queres inspeccionar output reciente: `watch_tail(watch_id, 50)`.
4. Al terminar: `watch_kill(watch_id)` — libera slot para otro proceso.

## Interpretacion de estados

- `running`: proceso vivo, matching activo.
- `exited`: el proceso termino solo (puede haber sido exito o error).
- `killed`: lo terminaste via `watch_kill`.
- `error`: fallo en boot (cmd inexistente, permisos, etc).

## Storage

- **State del engine**: SQLite WAL en `~/.antigravity/watcher/state.db`
  (override `ANTIGRAVITY_WATCHER_STATE`). Guarda watches + matches +
  metadata. TTL 7 dias.
- **Historial de eventos del gateway**: SQLite WAL en
  `~/.antigravity/watcher/history.db` (override `ANTIGRAVITY_WATCHER_HISTORY_DB`).
  Guarda cada evento que pasa dedup+rate-limit. TTL 30 dias
  (`ANTIGRAVITY_WATCHER_HISTORY_TTL_DAYS`). Consultable via
  `GET /v1/watcher/events/history`.
- Output completo de stdout/stderr vive solo en memoria (buffer circular
  de 500 lineas por stream, `ANTIGRAVITY_WATCHER_TAIL`).
- Limpieza del engine: `watch_cleanup` MCP o el hook `/finalize`. El
  gateway corre cleanup del history store cada 6h automatico.

## Limites

- Max 16 watches concurrentes (override via `ANTIGRAVITY_WATCHER_MAX`).
- Lineas matcheadas se truncan a 500 chars al persistir.
- Regex invalida aborta el spawn (no inicia proceso con patterns rotos).
- `cwd` validado contra `ANTIGRAVITY_WATCHER_CWDS` si esta seteado (por defecto permite cualquier dir
  dentro de `ANTIGRAVITY_ROOT`).

## Anti-patrones

- No uses `watch_spawn` para procesos one-shot de < 1s — el overhead del thread + store no vale.
- No pongas `importance=critical` en patterns que matcheen 100 veces por segundo — inundaras el gateway.
- No asumas que el tail persiste al matar el proceso: si lo vas a necesitar, `watch_tail` antes de `watch_kill`.
- No reutilices `watch_id` entre sesiones: cada spawn genera uno nuevo.

## Troubleshooting

| Sintoma | Accion |
|---|---|
| "cmd no encontrado" | Verifica PATH y cwd; usa comando absoluto si hace falta |
| "max_watches alcanzado" | `watch_list` + `watch_kill` en alguno viejo |
| Matches no llegan al gateway | `curl :4747/v1/health`; si esta caido, se skipea (no bloquea) |
| Tool no aparece en Claude Code | Revisa `.mcp.json` y corre `/reload-plugins` |

## Fuente canonica

- Engine: `.agent/core/process_watcher.py`
- MCP server: `.agent/mcp/watcher-server.py`
- Tests: `tests/core/test_process_watcher.py`
- Smoke test: `.agent/scripts/watcher-smoke.py`
