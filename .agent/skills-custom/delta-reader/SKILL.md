---
name: delta-reader
description: "Lectura de archivos con deduplicación por diff para reducir consumo de tokens en sesiones largas con Claude Code. Primera lectura devuelve full; relectura sin cambios devuelve marker cortísimo; relectura con cambios chicos devuelve diff unificado. Usa SQLite para persistir snapshots con TTL 7 días. Triggers: delta read, token saving, file deduplication, reread, session efficiency."
---

# Delta Reader Skill

Lectura de archivos con deduplicacion por diff para reducir consumo de tokens en sesiones largas con Claude Code.

**Agent Tier:** 1 (Orchestration y superiores)
**Auth Required:** No (acceso a filesystem local)
**Timeout:** 5 segundos
**Cost:** Free (cero dependencias externas, solo stdlib)

## Descripcion

Cuando Claude Code lee el mismo archivo varias veces durante una sesion (comun al iterar sobre `orchestrator.py`, `ESTADO_PROYECTO.md`, schemas grandes, etc.), las lecturas repetidas meten el archivo completo al contexto cada vez. Delta Reader intercepta esas relecturas y devuelve:

- **Primera lectura**: contenido full (se guarda snapshot).
- **Relectura sin cambios**: marker cortisimo `[sin cambios desde turn N]`.
- **Relectura con cambios chicos**: diff unificado (tipo `git diff`).
- **Relectura con cambios grandes** (> 40% del archivo): full de nuevo.

El modelo reconstruye el estado actual a partir del diff + la lectura anterior que ya tiene en contexto.

## Cuando usar

Conviene preferir `delta_read` sobre `Read` para:

- Archivos > 50 lineas que se van a leer mas de una vez en la sesion.
- Archivos que estas editando iterativamente (`Edit` → `Read` → `Edit`).
- Documentos grandes de referencia (`ESTADO_PROYECTO.md`, schemas, configs).

No conviene para:

- Primera lectura de exploracion (la primera siempre es full igual).
- Archivos < 50 lineas (devuelve full por politica).
- Binarios (rechaza).

## Input Schema

```json
{
  "path": "string (required) — ruta al archivo",
  "session_id": "string (optional) — id logico de sesion",
  "force_full": "boolean (optional, default false) — ignorar snapshot previa"
}
```

## Output Schema

```json
{
  "mode": "full | delta | unchanged | external_edit | error",
  "path": "string — ruta absoluta resuelta",
  "session_id": "string",
  "content": "string — contenido full (modes: full, unchanged marker)",
  "diff": "string — diff unificado (solo mode=delta)",
  "prior_turn": "int — turno de la snapshot anterior",
  "stats": {
    "bytes_full": "int — tamano original",
    "bytes_served": "int — tamano devuelto",
    "lines": "int",
    "reason": "first_read | hash_match | delta_compressed | diff_too_large | file_too_small | file_too_large | external_edit_detected",
    "savings_ratio": "float 0..1 (solo mode=delta)"
  },
  "success": "boolean"
}
```

## Ejemplos

### 1. Primera lectura

**Input:**
```json
{"path": ".agent/core/orchestrator.py", "session_id": "session_abc"}
```

**Output (resumen):**
```json
{
  "mode": "full",
  "content": "from __future__ import annotations\n...",
  "stats": {"lines": 1234, "bytes_full": 48200, "bytes_served": 48200, "reason": "first_read"},
  "success": true
}
```

### 2. Relectura sin cambios

**Output:**
```json
{
  "mode": "unchanged",
  "content": "[sin cambios desde turn 1; hash=a1b2c3d4e5f6]",
  "prior_turn": 1,
  "stats": {"bytes_full": 48200, "bytes_served": 48, "reason": "hash_match"},
  "success": true
}
```

Ahorro en este caso: 48200 → 48 bytes (99.9%).

### 3. Relectura con cambio chico

**Output:**
```json
{
  "mode": "delta",
  "diff": "@@ -45,3 +45,5 @@\n def process():\n-    return None\n+    validate()\n+    return result\n",
  "prior_turn": 1,
  "stats": {"bytes_served": 124, "bytes_full": 48200, "diff_ratio": 0.003, "savings_ratio": 0.997},
  "success": true
}
```

## Uso programatico

```python
import sys
sys.path.insert(0, ".agent")
from core.delta_reader import DeltaReader, default_state_path

reader = DeltaReader(default_state_path())
result = reader.read(".agent/core/orchestrator.py", session_id="my_session")

if result.mode == "full":
    send_to_model(result.content)
elif result.mode == "delta":
    send_to_model(f"Cambios desde turn {result.prior_turn}:\n{result.diff}")
elif result.mode == "unchanged":
    send_to_model(result.content)  # marker corto
elif result.mode == "error":
    raise RuntimeError(result.error)
```

## Uso via MCP

El servidor MCP `antigravity-delta-reader` esta registrado en `.mcp.json` y expone estas tools:

- `delta_read(path, session_id, force_full)` — lectura principal
- `delta_stats(session_id)` — metricas de ahorro
- `delta_reset_session(session_id)` — limpiar snapshots
- `delta_cleanup()` — limpiar snapshots expiradas (TTL global)
- `delta_status()` — config activa + path del store SQLite

## Configuracion

Todas las env vars son opcionales:

| Variable | Default | Descripcion |
|---|---|---|
| `ANTIGRAVITY_DELTA_STATE` | `~/.antigravity/delta-reader/state.db` | Path del SQLite |
| `ANTIGRAVITY_DELTA_ROOTS` | `$ANTIGRAVITY_ROOT` | Roots permitidos (os.pathsep separado) |
| `ANTIGRAVITY_DELTA_MIN_LINES` | `50` | Min lineas para considerar delta |
| `ANTIGRAVITY_DELTA_MAX_BYTES` | `2000000` | Max bytes; mas grande = full |
| `ANTIGRAVITY_DELTA_RATIO` | `0.4` | Si diff/full supera esto, devolver full |
| `ANTIGRAVITY_DELTA_TTL` | `604800` | TTL de snapshots en segundos (7 dias) |

## Manejo de errores

- **session_id vacio** → `mode=error`, `error="session_id es requerido"`.
- **Archivo inexistente** → `mode=error`, `error="Archivo no existe: ..."`.
- **Path fuera de roots permitidos** → `mode=error`, `error="Path fuera de roots permitidos"`.
- **Binario** → `mode=error`, `error="Archivo binario detectado"`.
- **Edicion externa detectada** → `mode=external_edit` (no es error; se devuelve full + snapshot se refresca).

## Rendimiento

- Primera lectura: `O(file_size)` I/O + hash SHA-256.
- Relectura sin cambios: `O(file_size)` I/O + hash, pero output es constante (marker).
- Relectura con diff: `O(file_size)` I/O + `difflib.unified_diff` `O(n*m)` en el peor caso, pero con heuristicas `difflib` es casi lineal para cambios chicos.
- Store SQLite: WAL mode, transacciones atomicas, connection pool nuevo por call.
- Memoria: el contenido se persiste en SQLite (no en RAM).

## Seguridad

- Sin `shell=True`, sin `eval`, sin `pickle`.
- Validacion opcional de paths contra allowlist (`allowed_roots`).
- SQL parametrizado (no injection).
- Binarios rechazados (null byte detection).
- Guard-rail contra archivos > 50MB (excepcion antes de `read_text`).

## Tests

```bash
python -m pytest tests/core/test_delta_reader.py -v
```

Coverage actual: 28 tests cubriendo config validation, todas las decisiones de mode, aislamiento entre sesiones, stats, errores, allowlist, persistencia cross-connection, TTL cleanup, force_full y env overrides.

## Author

OpenAntigravity — K. Kaneshiro / UNS
**Version:** 1.0.0
**Created:** 2026-04-14

## License

Misma licencia que OpenAntigravity. Inspirado conceptualmente en el Delta Mode de `alexgreensh/token-optimizer` (PolyForm-NC) pero reimplementado desde cero sin codigo compartido, para evitar el acoplamiento legal y adaptarlo al ecosistema MCP-first.
