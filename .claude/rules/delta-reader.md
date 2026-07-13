# Regla: Delta Reader — Lectura con deduplicacion por diff

Aplica a todas las sesiones de Claude Code en este repositorio.

## Cuando preferir `delta_read` sobre `Read`

Usa la tool MCP `delta_read` (del servidor `antigravity-delta-reader`) en vez del `Read` nativo cuando se cumplan TODAS estas condiciones:

1. **El archivo tiene > 50 lineas** — si es mas chico, delta_reader devuelve full igual, no aporta.
2. **Es probable que lo vuelvas a leer en la sesion** — tipico al iterar `Read → Edit → Read` sobre el mismo archivo.
3. **Es texto UTF-8** — binarios son rechazados automaticamente.

Casos concretos donde conviene:

| Archivo | Por que |
|---|---|
| `.agent/core/orchestrator.py` y modulos grandes de core | Se tocan varias veces por sesion |
| `ESTADO_PROYECTO.md` (70KB) | Se lee al principio y durante la sesion |
| `CLAUDE.md` y reglas en `.claude/rules/` | Referenciados iterativamente |
| Schemas de ARARI, modelos pydantic grandes | Iteracion sobre modelos |
| Archivos de `.agent/brain/concepts/` que trae `/recall` | Consultados repetidamente |

## Cuando NO usar `delta_read`

- **Primera exploracion del repo** — la primera lectura siempre es full de todos modos, `Read` nativo esta bien.
- **Archivos < 50 lineas** — la politica devuelve full por defecto, sin ahorro.
- **Archivos binarios** (imagenes, PDFs, `.db`) — `delta_read` los rechaza con error.
- **Archivos que no vas a volver a leer** — el overhead de guardar snapshot no se amortiza.

## Como usarlo

### Via MCP (preferido)

Llama a la tool `delta_read` del servidor `antigravity-delta-reader`:

```json
{
  "path": ".agent/core/orchestrator.py",
  "session_id": "<id-de-la-sesion-actual>",
  "force_full": false
}
```

El `session_id` debe mantenerse constante durante la sesion para que las relecturas compartan snapshot. Si no lo pasas, usa `claude-code-default` (seguro pero pierde aislamiento entre sesiones concurrentes).

### Interpretacion del resultado

- `mode: "full"` → tratalo como si fuera la salida de `Read` comun, usa `content`.
- `mode: "unchanged"` → el archivo no cambio desde la lectura anterior. `content` es un marker corto tipo `[sin cambios desde turn N]`. Podes seguir trabajando con la version que ya tenes en contexto.
- `mode: "delta"` → el archivo cambio poco. `diff` tiene el diff unificado. Reconstruis mentalmente la version actual aplicando el diff a la anterior.
- `mode: "external_edit"` → alguien edito el archivo fuera de tu flujo (VS Code abierto, por ejemplo). `content` es el full nuevo; la snapshot se refresca automaticamente.
- `mode: "error"` → revisa `error`, corregi y reintenta.

## Metricas y limpieza

- `delta_stats(session_id)` — ver ahorro acumulado (`savings_ratio`, bytes_full vs bytes_served).
- `delta_reset_session(session_id)` — si cambias de contexto de trabajo y las snapshots viejas ya no sirven.
- `delta_cleanup()` — mantenimiento global, elimina snapshots > 7 dias. Seguro correrlo en cualquier momento.

## Anti-patrones

- No uses `delta_read` para descubrir archivos (usa `Glob`/`Grep`).
- No pases `force_full: true` salvo que sospeches corrupcion del store.
- No cambies el `session_id` en mitad de una sesion — pierdes todo el estado y todo vuelve a ser "first_read".
- No confies en deltas para archivos que cambian desde fuera (build artifacts, logs) — el `mode: external_edit` te cubre, pero es mejor no invocar `delta_read` sobre esos.

## Storage

- SQLite WAL en `~/.antigravity/delta-reader/state.db` (configurable via `ANTIGRAVITY_DELTA_STATE`).
- TTL de snapshots: 7 dias (configurable via `ANTIGRAVITY_DELTA_TTL`).
- Roots permitidos: `ANTIGRAVITY_DELTA_ROOTS` (default: `$ANTIGRAVITY_ROOT`).

## Troubleshooting

| Sintoma | Accion |
|---|---|
| "Path fuera de roots permitidos" | Revisa `ANTIGRAVITY_DELTA_ROOTS` en `.mcp.json` |
| "Archivo binario detectado" | Usa `Read` nativo; `delta_read` es solo para texto UTF-8 |
| Siempre devuelve `full` | Verifica que `session_id` sea el mismo entre llamadas |
| Tool no aparece en Claude Code | Corre `/reload-plugins` o reinicia la sesion |

## Fuente canonica

- Engine: `.agent/core/delta_reader.py`
- MCP server: `.agent/mcp/delta-reader-server.py`
- Skill: `.agent/skills-custom/delta-reader/`
- Tests: `tests/core/test_delta_reader.py`
