# Regla: Repo Crawler — auto-ingesta de docs del repo al Brain

Aplica a todas las sesiones de Claude Code en este repositorio.

## Principio

El Brain Network (`.agent/brain/`) debe representar el conocimiento canonico del repo. Los `.md` del repo (CLAUDE.md, RULES.md, reglas, docs, READMEs de sub-apps) son la fuente de verdad de como funciona el ecosistema. El crawler los ingesta como nodos del Brain con tags semanticos canonicos para que `/brain query` y `/recall` los encuentren junto a las sesiones historicas.

## Cuando correr el crawler

| Disparador | Comando |
|---|---|
| Cierre de sesion (`/finalize`) | Auto: PASO 4.5 lo invoca si tocaste algun .md whitelisted |
| Despues de editar reglas o docs grandes | `python .agent/scripts/repo_crawler.py --apply` |
| Primera vez en una PC nueva | `python .agent/scripts/repo_crawler.py --apply` (poblara los nodos por primera vez en local) |
| Nunca | Si solo tocaste codigo Python/TS/Rust sin editar .md |

El crawler es **idempotente**: si nada cambio, devuelve `0 nuevos, 0 actualizados, 0 archivados` en segundos. Es seguro correrlo de mas.

## Qué archivos absorbe (whitelist)

Definidos en `INCLUDE_PATTERNS` dentro de `.agent/scripts/repo_crawler.py`. Resumen:

- Raiz: `CLAUDE.md`, `RULES.md`, `BRAIN_README.md`, `BUILD.md`, `ESTADO_PROYECTO.md`, `WORKFLOW_RULES.md`, `README.md`
- `.claude/rules/*.md`, `.claude/memory/*.md`, `.claude/commands/*.md`
- `docs/**/*.md`
- `nexus-app/CLAUDE.md`, `nexus-app/README.md`, `nexus-app/docs/**/*.md`
- `src/**/README.md`, `mcp-server/**/*.md`
- `.antigravity/rules.md`, `.antigravity/README.md`

Si agregas una nueva categoria de docs canonicos, **agregala al whitelist** del crawler. No al reves (no convertir cualquier .md del repo en nodo del Brain — eso es ruido).

## Qué archivos NO absorbe (blacklist)

- `.agent/brain/**` (loop infinito si se auto-ingesta)
- `.agent/brain-backups/**`
- `.git/**`, `node_modules/**`, `target/**`, `dist/**`, `build/**`
- `.claude/worktrees/**`
- `**/CHANGELOG.md` (cambian todo el tiempo, ruido)
- `**/*.test.md`

## Politica de tags canonicos

Los tags hardcodeados en el crawler usan **convenciones existentes del Brain** (no inventar variantes). Verificados via top-30 tags actuales:

### Apps UNS (negocio)

| Keyword en path/contenido | Tag canonico |
|---|---|
| `arari`, `ARARI` | `arari` |
| `kobetsu`, `個別契約` | `kobetsu` |
| `rirekisho`, `履歴書` | `rirekisho` |
| `kintai`, `勤怠` | `kintai` |
| `yukyu`, `有給` | `yukyu` |
| `chingi`, `賃金` | `chingi` |
| `apartments-opus` | `apartments` |
| `paginaweb`, `uns-web` | `paginaweb` |
| `kintaiflow` | `kintaiflow` |
| `haken`, `派遣` | `uns-dispatch` |

### Ecosistema tecnico

| Keyword | Tag canonico |
|---|---|
| `Nexus`, path `nexus-app/` | `nexus`, `tauri`, `desktop` |
| path `src/` (TS) | `telegram`, `bot`, `typescript` |
| path `mcp-server/` | `mcp`, `server-portable` |
| `:4747`, `gateway local` | `gateway` |
| `watch_spawn`, `process_watcher` | `watcher` |
| `context engine`, `prepare_context` | `context-engine` |
| `brain.ingest`, `brain network` | `brain` |
| `delta_read`, `delta_reader` | `delta-reader` |
| `mem0`, `antigravity-memory` | `mem0` |

### Filename / ubicacion

| Senal | Tags |
|---|---|
| `CLAUDE.md` | `claude-code`, `project-instructions` |
| `.claude/rules/*` | `rules`, `convention` |
| `docs/**` | `docs` |

### Tag de origen (siempre)

Todos los nodos del crawler llevan tag `auto-ingested` y `app_origin: repo-crawler` para distinguirlos de sesiones manuales o de otros ingestadores.

## Variantes prohibidas (NO inventar)

Usar siempre el canonico:

- `nexus` — NO `nexus-app`, `nexus-desktop`
- `arari` — NO `arari-crm`, `arari-pro`
- `kobetsu` — NO `kobetsu-keiyaku`
- `mcp` — NO `mcp-server` (ya existe `server-portable`)
- `rules` — NO `governance` como tag (governance es `area`)

Si agregas un app nuevo al ecosistema y queres ingestarlo, **definí su tag canonico una sola vez** en `CONTENT_TAGS` del crawler (`.agent/scripts/repo_crawler.py`).

## Comportamiento de re-ingesta

El crawler dedupea por SHA256 del contenido (guardado en `source_notes` del nodo):

| Estado | Accion |
|---|---|
| Path nuevo | `brain.ingest()` con tags + cross-linking automatico |
| Path existente, hash igual | Skip silencioso |
| Path existente, hash distinto | `brain.update_node()` actualiza context + tags + hash |
| Path desaparecido del filesystem | `status="archived"` (no se borra el nodo, queda en historial) |

El cross-linking entre nodos es **automatico** via `Brain._detect_related()`: cualquier par de nodos con tags solapados se linkea bidireccionalmente con score `tags*2 + area*1`. Por eso los tags canonicos importan tanto.

## Frontmatter del .md original

Si un `.md` tiene frontmatter YAML con campos estandar, el crawler los respeta y mergea:

- `tags: [...]` del frontmatter se mergean con los detectados
- `title:` pisa el extraido del primer H1
- `area:` pisa el heuristico
- `importance:` (low/normal/high/critical) pisa el detectado

Si no hay frontmatter o el YAML es invalido, fallback al comportamiento default sin error.

## Anti-patrones

- NO correr el crawler sobre paths fuera del repo (no es un absorber generico — para eso esta `file_absorber.py`)
- NO ingestar el propio `.agent/brain/` (loop)
- NO inventar tags nuevos que no esten en el set canonico — se rompen las cross-refs
- NO desactivar el cleanup en `--apply` salvo que tengas razon especifica (los huerfanos son ruido)
- NO commitear `.agent/brain/` parcial — incluir siempre `concepts/`, `sessions/`, `index.md`, `log.md` juntos

## Fuente canonica

- Engine: `.agent/scripts/repo_crawler.py`
- Brain API: `.agent/core/brain.py` (`Brain.ingest`, `Brain._detect_related`)
- Slash command que lo invoca: `.claude/commands/finalize.md` (PASO 4.5)
- Reglas relacionadas: `.claude/rules/memory-engine.md`, `.claude/rules/auto-save-triggers.md`
