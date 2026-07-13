# Context Size Guard — fix definitivo del "Request too large (max 32MB)"

PreToolUse hook que previene en su raíz el error `Request too large (max 32MB)` de
Claude Code. Ese error es un techo DURO de la API de Anthropic sobre el body completo
(system + reglas + historial + tool_results). La causa dominante (memoria 2026-06-09)
es la **acumulación**: leer un PDF o imagen con `Read` los incrusta como base64
(~1.3MB/PDF) que se **reenvían en cada turno** → una lectura temprana envenena toda la
sesión hasta chocar el techo, "sin haber subido nada nuevo".

## Qué hace

`context_size_guard.py` intercepta `Read` ANTES de que el contenido pesado entre al
contexto:

- **PDF** → bloquea y redirige al skill `/pdf` (texto plano, ~100x más liviano).
- **Imagen > 1.5MB** → bloquea y sugiere redimensionar (se reenvía cada turno).
- **Aviso (no bloquea)** cuando el transcript de la sesión supera 24MB → recomienda `/clear`.

El bloqueo devuelve un mensaje accionable al **agente** (no rompe el flujo del usuario):
Claude simplemente toma el camino liviano (`/pdf`, `delta_read`) en vez del `Read` pesado.

## Activación (pegar en `.claude/settings.json`)

Agregá esta clave dentro de `"hooks"` (por ejemplo, justo antes de `"PostToolUse"`):

```json
"PreToolUse": [
  {
    "matcher": "Read",
    "hooks": [
      {
        "type": "command",
        "command": "cd \"${CLAUDE_PROJECT_DIR:-.}\" && python -X utf8 \".claude/hooks/scripts/context_size_guard.py\"",
        "timeout": 5000
      }
    ]
  }
],
```

Surte efecto en la próxima sesión de Claude Code (los hooks se cargan al arranque).

## Seguridad

- **Fail-open**: cualquier error, input ilegible o bug del guard → permite la tool
  (exit 0). Jamás te deja una sesión bloqueada.
- **Kill switch**: `ANTIGRAVITY_CONTEXT_GUARD=off` desactiva todo el guard.
- **Umbrales configurables** por env:
  - `ANTIGRAVITY_GUARD_IMAGE_MAX_BYTES` (default `1500000`)
  - `ANTIGRAVITY_GUARD_TRANSCRIPT_WARN_BYTES` (default `24000000`)

## Tests

`tests/hooks/test_context_size_guard.py` — 16 tests (lógica pura + fail-open del
entry point por subproceso real).

## Relacionado

- `.claude/memory/discovery_request_too_large_provider_y_dedup_reglas_globales.md`
- `.claude/memory/discovery_request_too_large_pdf_acumulacion.md`
- `.claude/memory/bugfix_request_too_large_32mb_intelligence_log.md`
