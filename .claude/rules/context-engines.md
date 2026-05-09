# Regla: Pluggable Context Engines

Aplica a todas las sesiones de Claude Code en este repositorio.

## Principio

El contexto que ve el agente cada turno lo decide un **Context Engine**, que
es una estrategia intercambiable via plugins. En vez de tener UNA sola manera
de armar el contexto (stack + memoria + observaciones), ahora tenemos varias
estrategias seleccionables por `.antigravity/config.json` o env var.

Esto permite:
- Sesiones largas en el mismo dominio con `brain_aware` (inyecta Brain top-K).
- Iteracion sobre archivos grandes con `delta_aware` (hint para delta_read).
- Conversaciones con historial extenso con `summarizing`.
- Proyectos UNS con `domain_uns` (reglas dispatch japones).
- Combinacion de todos con `composite` (chain configurable).

## Engines built-in

| Nombre | Que hace | Cuando usarlo |
|---|---|---|
| `default` | Comportamiento historico: stack + memoria + observaciones | Fallback seguro, baseline para tests |
| `brain_aware` | Default + top-K del Brain Network antes de cada turno | Sesiones largas en el mismo dominio |
| `delta_aware` | Default + marca archivos > 50 lineas con `[delta]` para hint de ruteo | Edit loops sobre archivos grandes |
| `summarizing` | Default + comprime open_files y history largos (heuristico, sin LLM) | Sesiones con mucho estado arrastrado |
| `domain_uns` | Default + recordatorio reglas UNS si detecta keywords (派遣, 個別契約) | Proyectos UNS / dispatch japones |
| `composite` | Chain de engines en orden: delta_aware → brain_aware → summarizing → domain_uns | Sesiones intensivas (recomendado) |

## Como seleccionar el engine activo

Orden de resolucion (primera fuente gana):

1. Argumento explicito al llamar `get_engine("brain_aware")`.
2. Env var `ANTIGRAVITY_CONTEXT_ENGINE=composite`.
3. Campo `"context_engine": "composite"` en `.antigravity/config.json`.
4. Fallback: `"default"`.

## Uso desde codigo Python

```python
import sys; sys.path.insert(0, ".agent")
from core.context_injection import prepare_context

# API recomendada nueva (respeta el engine activo):
ctx = await prepare_context(task="refactor login")

# API legacy (sigue funcionando, bypass de engines):
from core.context_injection import build_injection_context
ctx = await build_injection_context(task="refactor login")
```

## Uso desde MCP (Claude Code)

Usa el servidor `antigravity-context-engine`:

- `context_engine_list()` — engines disponibles con metadata.
- `context_engine_current()` — engine activo + fuente de seleccion.
- `context_engine_switch({name})` — cambia el activo (escribe config).
- `context_engine_preview({task, engine_name?})` — simula sin side effects.
- `context_engine_stats({task})` — metricas chars/tokens vs legacy.

## Slash command

```
/context-engine list                # listar engines
/context-engine current             # ver el activo
/context-engine switch <name>       # cambiar
/context-engine preview "<task>"    # ver que inyectaria
/context-engine stats               # metricas
```

## Recomendacion por caso

| Caso | Engine sugerido |
|---|---|
| Proyecto nuevo, sin historia | `default` |
| Sesion larga revisando el mismo modulo | `brain_aware` |
| Refactoring con muchos archivos grandes | `delta_aware` |
| Conversacion con muchas vueltas | `summarizing` |
| Algo relacionado con dispatch japones | `domain_uns` |
| **Sesion intensa de desarrollo** | `composite` (default recomendado) |

## Cuando NO cambiar el engine

- **Mitad de sesion critica**: cambiar en caliente NO rompe estado, pero
  puede confundir si estas siguiendo un hilo. Termina el bloque actual primero.
- **Tests reproducibles**: siempre usa `default` en CI/mutation testing para
  que el output sea deterministico.

## Extensibilidad

Para registrar un engine custom desde un plugin:

```python
from core.context_engines import register_engine

class MyEngine:
    @property
    def metadata(self):
        return ContextEngineMetadata(name="my_engine", description="...")
    async def prepare(self, inp):
        ...

register_engine("my_engine", MyEngine())
```

## Storage

- Config por proyecto: `.antigravity/config.json` campo `context_engine`.
- Override global: env `ANTIGRAVITY_CONTEXT_ENGINE`.
- Config especifica por engine:
  - `ANTIGRAVITY_CONTEXT_BRAIN_K` (default 3)
  - `ANTIGRAVITY_CONTEXT_DELTA_MIN_LINES` (default 50)
  - `ANTIGRAVITY_CONTEXT_SUMMARY_FILE_LIMIT` (default 10)
  - `ANTIGRAVITY_CONTEXT_SUMMARY_HISTORY_LIMIT` (default 8)
  - `ANTIGRAVITY_CONTEXT_DOMAIN_KEYWORDS` (lista separada por coma)
  - `ANTIGRAVITY_CONTEXT_COMPOSITE_CHAIN` (lista separada por coma)

## Anti-patrones

- No hagas bypass del engine en llamadas nuevas — usa `prepare_context()`, no
  `build_injection_context()` directo.
- No pongas logica de negocio en un engine — los engines solo ORDENAN/FILTRAN
  contexto; efectos laterales van en memory_router o Brain.
- No encadenes composite dentro de composite — la implementacion lo evita pero
  se desperdicia trabajo.

## Troubleshooting

| Sintoma | Diagnostico | Fix |
|---|---|---|
| Engine siempre es `default` | env/config vacios | Setea `ANTIGRAVITY_CONTEXT_ENGINE` |
| `brain_aware` no inyecta nada | Brain vacio o path mal | `/brain stats`; verifica `.agent/brain/` |
| `delta_aware` no marca archivos | open_files paths relativos mal resueltos | Pasa `project_dir` explicito |
| `domain_uns` no activa | Keywords no coinciden | Override via `ANTIGRAVITY_CONTEXT_DOMAIN_KEYWORDS` |

## Fuentes canonicas

- API publica: `.agent/core/context_injection.py` (`prepare_context`)
- Paquete engines: `.agent/core/context_engines/`
- Builtins: `.agent/core/context_engines/builtin/`
- MCP server: `.agent/mcp/context-engine-server.py`
- Tests: `tests/core/test_context_engines.py`
