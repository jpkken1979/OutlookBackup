# Regla: Routing de Herramientas — "Director de Orquesta"

> Auto-inyectada cada sesion. Define **cuando usar cada capacidad** del ecosistema.
> Cada herramienta con su funcion; evitar el solapamiento y el anti-patron de
> "usar la generica (Grep) para todo cuando hay una especifica disponible".
> Origen: auditoria 2026-06-04 (descubrimiento: Serena infrautilizada + 16 skills duplicados).

## 1. Navegacion y edicion de codigo

| Lenguaje / area | Herramienta primaria | Por que |
|---|---|---|
| **TypeScript / React** (`nexus-app/`) | **Grep/Glob + lecturas dirigidas + tests TS** | Serena fue removido de las configs MCP a pedido del usuario; usar busqueda local y checks TS como ruta canonica. |
| **Python** (`.agent/`, `src` bot) | **Grep + Read + `delta_read`** | Ruta canonica para runtime Python; sin dependencia de MCP externo. |
| **Rust** (`nexus-app/src-tauri/`) | **Grep + Read** | Ruta canonica para backend Tauri; validar con `cargo check/test`. |
| **Discovery** ("donde esta X?") | **Glob** (nombres) + **Grep** (contenido) | Inmediato, sin setup |

> **Gotcha documentado**: Serena llego a levantar solo `Programming languages:
> typescript`, con onboarding incompleto, y luego se removio de las configs MCP
> porque no aportaba suficiente valor frente al costo/ruido operativo. Si algun
> dia se reactiva como herramienta on-demand, debe volver por el generador y con
> una prueba clara de beneficio.

## 2. Conocimiento y memoria

| Necesidad | Herramienta |
|---|---|
| Decisiones, sesiones, patrones, ADRs (estructurado) | **Brain** (`brain_query`, `brain_ingest`) — `antigravity-brain` |
| Visualizar el Brain como grafo force-directed | `/graph` (`antigravity-brain-graph`) |
| Recall semantico automatico (cache) | **mem0** (`antigravity-memory`) |
| Fuente de verdad versionada | `.claude/memory/*.md` + `.agent/brain/` (git) |

Capas 1 (markdown) y 2 (Brain) son fuente de verdad; mem0 (capa 3) es cache auxiliar.

## 3. Lectura eficiente

| Caso | Herramienta |
|---|---|
| Archivo > 50 lineas que se va a releer en la sesion | `delta_read` (`antigravity-delta-reader`) |
| Primera lectura / archivo chico | `Read` |

## 4. Grafo unificado codigo+docs+media (opcional, on-demand)

**graphify** (`safishamsi/graphify`): convierte una carpeta (codigo + SQL + docs + PDFs +
media) en un grafo de conocimiento consultable. **NO correrlo global** sobre el monorepo
(la indexacion manda lo no-codigo al LLM = caro en tokens). Usar **acotado a un
sub-proyecto** cuando se necesite mapa cross-tipo, onboarding de un repo nuevo, o el
PR impact dashboard. Se solapa con busqueda de codigo + Brain (conocimiento): no es default.

## 5. Auditoria del ecosistema

`.agent/scripts/detect_duplicate_capabilities.py`: scout **determinista** (~0 tokens de
modelo) que mapea skills/agentes por nombre+descripcion y agrupa candidatos a duplicado
(Jaccard). Correr antes de instalar un skill nuevo o como mantenimiento periodico. La
verificacion profunda de cada cluster se hace con subagentes (Agent tool con salida de
texto — **no** usar `StructuredOutput` forzado: el provider del proxy no lo soporta bien).

## 6. Paralelismo: subagentes vs Agent Teams vs Workflow

Cuatro mecanismos que se solapan — elegir por lo que la tarea NECESITA, no por novedad:

| Situacion | Mecanismo |
|---|---|
| Solo importa el resultado; los workers no necesitan hablarse | **Subagentes** (Agent tool) — mas barato, reportan al caller y listo |
| Los workers necesitan comunicarse entre si: debate de hipotesis, review multi-lente, cambios cross-layer con dueños distintos | **Agent Teams** (nativo, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) — task list compartida + mensajeria directa |
| Fan-out determinista con loops/condicionales controlados por script | **Workflow** tool (pipeline/parallel) |
| Trabajo secuencial, mismo archivo, o muchas dependencias entre pasos | **Sesion unica** — ni team ni fan-out |

Reglas practicas para Agent Teams:

- **Tamano**: 3-5 teammates, 5-6 tareas por teammate. Cada teammate dueño de
  archivos distintos (dos editando el mismo archivo = overwrite garantizado).
- **Modelo por teammate**: NO heredan el `/model` del lead — se fija en el spawn
  prompt y no se puede cambiar despues. Anotar con `/cual-modelo --teams "rol 1" "rol 2"`.
- **Provider alternativo activo** (minimax/zai/openrouter/...): NO degradar modelos
  por tarea — omitir `model` y usar el mejor del provider (el CLI de cual-modelo
  ya lo detecta solo via proxy_state).
- **Roles reutilizables**: usar las definitions de `.claude/agents/` (teammate-implementer,
  teammate-reviewer, teammate-researcher) — traen tools y model pineados.
- **Windows**: modo `in-process` (default). Split panes requiere tmux/iTerm2 y NO
  funciona en Windows Terminal — no perseguirlo.
- **Limitaciones**: `/resume` no restaura teammates; los teammates in-process no
  pueden lanzar subagentes en background; un solo team por sesion, sin anidar.
- **Observabilidad**: los eventos TaskCreated/TaskCompleted/TeammateIdle se capturan
  al daily (`.claude/memory/daily/`) via `team_event_capture.py` (hook no bloqueante).

## Principio anti-solapamiento

> Antes de agarrar una herramienta, preguntarse: **¿hay una mas especifica para esta tarea?**
> Codigo TS/Py/Rust -> Grep+Read dirigido · Conocimiento -> Brain · Recall -> mem0 ·
> Relectura -> delta_read. No usar la generica cuando existe la simbolica/especifica.
