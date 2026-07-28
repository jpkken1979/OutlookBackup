# Tareas Pendientes — Se auto-inyecta en CADA sesión

> Leer esto SIEMPRE al inicio de sesión. Son tareas NO completadas que no deben olvidarse.

## 🟡 Sesión 2026-07-26 — Auditoría funcional de Nexus: Fase A hecha, B-G pendientes

Auditoría end-to-end de `nexus-app/` con regla de evidencia ejecutada. Resultado:
**18 roturas funcionales verificadas y ~28 comandos sin consumidor, con las 5
suites de test en verde**. Plan completo:
`docs/plans/2026-07-26-auditoria-funcional-nexus-plan-maestro.md`.

✅ **Fase A cerrada** — PR **#138** (`fix/gateway-auth-headers`, commit `16ac4e6b`):
inyectado `X-API-Key` en `context_engine.rs` (5 comandos), `watcher.rs` (spawn +
SSE) y `useWatcherMetrics.ts`, más dos bugs de shape encadenados. Falta mergear.

🟡 **Fases pendientes, en orden sugerido:**

1. **Fase B — panel Brain (6 acciones rotas).** `brain_stats`/`brain_query`/
   `brain_traverse` con structs desalineados; `brain_graph` y `brain_node_detail`
   con `sys.path` mal armado (`ModuleNotFoundError: No module named 'core'`,
   `brain.rs:513,553` — one-liner, empezar por ahí); y **`POST /v1/brain/ingest`
   no existe** en el gateway (`gateway_main.py:1605-1606` solo registra `query` y
   `stats`): decidir si se agrega la ruta o se apunta el comando al subprocess
   Python que ya funciona.
2. **Fase C — fuentes de datos equivocadas.** `analytics.rs:71` lee
   `~/.antigravity/observations.db` (**0 filas**) en vez de la real (**9.765
   obs**) → Observability y Skills Analytics en cero. Y
   `plugin_eval/cli.py:88-89` imprime a stdout sin gatear por `if not
   json_output`, así que `invoke_plugin_eval` falla el parseo **siempre**.
3. **Fase D — seguridad y pérdida de datos.** `accounts.rs:334` hace el backup de
   credenciales Codex con `let _ =` y sobrescribe igual si falla (contradice
   `security.md`). `fix_claude_plugins` corre siempre destructivo porque el
   `dry_run` es inalcanzable desde la UI (`PluginsPanel.tsx:174`).
4. **Fase E — borrar ~28 comandos muertos.** Empezar por `provider_hotswap`
   (segunda implementación divergente del switch, sin `normalize_provider_id` ni
   preflight), `restore_global_backup` e `import_global_backup` (más peligrosos
   que sus reemplazos selectivos). NO tocar `create_global_backup_impl`, que sí
   se usa internamente.
5. **Fase F — la que evita que todo esto se re-rompa.** Los fixtures validan
   contratos que el gateway nunca devuelve (`BrainStats.test.tsx:19-20`,
   `BrainIngest.test.tsx:33`). Ver
   `[[discovery_tests_verdes_contratos_imaginarios]]`.
6. **Fase G — features.** La mejor es el panel de costos/tokens: ya está medio
   construido (el proxy persiste `turn_usage.jsonl` y `cost_tracker.py` tiene
   estimación y presupuesto; falta el cable entre ambos y la UI).

**Hallazgos operativos que no son código:**

- 🟡 **El gateway no tiene supervisión**: `auto_start_watchdog` default `false` y
  ninguna pantalla lo lee ni lo escribe. `watchdog.log`/`watchdog.pid` no existen.
- 🟡 **P1 nuevo**: `POST /v1/context-engine/stats` tarda más de 15s y el cliente
  Rust tiene timeout de 15s.
- 🟡 **Duda abierta**: `.claude/hooks/post_shu_execution.py` no aparece registrado
  en ningún `settings.json`. Si nunca se dispara, todo el dominio Shu-métricas es
  cosmético de forma permanente.
- ⚪ Queda una memoria de prueba de la auditoría (`AUDIT PROBE memory_save nexus
  2026-07-26`, id `dddaae90-c7e5-4682-a969-11ed69c492c8`) en `history.db`: mem0
  es append-only y `memory_delete` es un stub que devuelve `ok:false`.

## 🟡 Sesión 2026-07-25 (cont.) — 11 tests fallando en `pytest tests/` completo (no aislados)

Corriendo la suite COMPLETA (`pytest tests/ --timeout=30 -q`, no solo `tests/core/`
ni archivos puntuales) aparecen 11 failures que **no están relacionados a ningún
cambio de esta sesión** — confirmado con `git log --name-only 9851b4db..HEAD` (el
commit previo al inicio de esta sesión): ninguno de los commits de hoy toca los
archivos fuente ni de test involucrados. Sin código para arreglar todavía —
diagnóstico parcial, falta root-cause real:

**Grupo 1 — reproduce siempre en aislado, mismo patrón Windows (7 tests):**
- `tests/mcp/test_remote_server_hardening.py` — 5 tests, todos con
  `AssertionError: assert 401 == 200` (el server remoto rechaza auth que el test
  esperaba que pasara — huele a env var de API key no seteada en el entorno del
  test, no hay `monkeypatch.setenv` de auth en el archivo, revisar el fixture
  `scope="module"` de la línea 33 y cómo arranca el server de prueba).
- `tests/scripts/test_skill_copies_sync.py::test_skill_script_copies_identicas[webapp-testing/scripts/with_server.py]`
  y `tests/scripts/test_mcp_injector_integration.py::test_double_inject_direct_is_practically_idempotent`
  — ambos con `FileNotFoundError: [WinError 3]` dentro de
  `.agent/scripts/mcp_injector.py:merge_tree` → `shutil.copy2` (línea 564). Huele
  a path largo de Windows o un directorio temp que el test asume y no existe en
  esta máquina — no es código roto, es un problema de entorno/fixture.

**Grupo 2 — flaky, no reproduce siempre aislado (test pollution ya documentado
en la memoria del proyecto, mismo patrón que el singleton de `memory_router`):**
- `tests/mcp/test_skills_server.py::TestReadSkill::test_read_real_skill`
- `tests/core/test_mixin_proxy_failover.py::test_reroutes_to_next_healthy_alt` —
  mismatch `'auto_failover_quota_reroute'` vs `'auto_failover_reroute'` esperado;
  huele a estado global/singleton de failover que no se resetea entre tests y
  queda contaminado por un test previo que sí dispara el reason "quota".

**Grupo 3 — ya conocido, no es bug (confirmado en la auditoría original 2026-07-25):**
- `tests/core/test_compute_brain_embeddings.py` — 2 tests, asumen que
  `sentence-transformers` NO está instalado; en esta máquina sí lo está (gap de
  entorno documentado desde la Fase 6 de embeddings, ver histórico abajo).

**Para la próxima sesión:** empezar por el Grupo 1 (reproducible, más fácil de
diagnosticar) — revisar cómo `test_remote_server_hardening.py` arranca el server
de prueba y si le falta una env var de auth; y correr `merge_tree` a mano contra
el mismo `webapp-testing/scripts/with_server.py` para ver el path exacto que
falla. El Grupo 2 necesita bisectar con `pytest -p no:xdist` + orden fijo para
encontrar qué test dejar contaminado el estado global.

## 🟡 Sesión 2026-07-25 — Auditoría exhaustiva OpenAntigravity26.3.30

Auditoría función-por-función completa (5 sub-agentes en paralelo: `.agent/core/`,
MCP+agents+skills, `nexus-app/`, bot Telegram, `mcp-server/`). Resultado: **3 PRs
abiertos** (revisar y mergear cuando el usuario tenga tiempo) + varios fixes
directos a `main` ya pusheados.

**PRs abiertos, todos verdes (tests/clippy/fmt/tsc/eslint limpios), esperando review:**
- **#135** — `memory.rs` path traversal (canonicalize+starts_with) + API key de IA
  ya no viaja en texto plano al frontend (`get_config` la redacta, nuevo comando
  `reveal_ai_api_key` on-demand) + mojibake en 3 strings de `config.rs`.
- **#136** — `.agent/core/gateway.py` borrado (código muerto, `AntigravityGateway`
  sin importers de producción, llamaba métodos inexistentes del orchestrator) +
  79 `try-except-pass` en 48 archivos justificados con `# ponytail:` o `logger.debug`.
- **#137** — `secrets.rs` borrado: keyring service duplicado con `config.rs` que
  resultó ser migración legacy muerta (`secrets_migrate_legacy` nunca migraba nada
  en la práctica — `get_config` ya corría su propia migración interna antes de que
  el otro comando llegara a leer el store).

**Fixes directos ya en `main`:** 11 `IDENTITY.md` con frontmatter YAML duplicado
(y luego una regresión propia de ESE fix — un `- <example>` sin block-scalar
indicator rompía el YAML real que usa `discovery.py`, ya reparada y verificada
con `test_orchestrator_discovery.py`), tests nuevos para `multi_user_auth.py`
(0%→cubierto), validación de identificadores SQL en `data_sync.py`, fix de
encoding UTF-8 en `/cual-modelo` (crasheaba en Windows cp932), URL-encoding en
`_registry_load` de `mcp-server/server.py`.

**🟡 PENDIENTE — no completado, alcance real medido pero no ejecutado:**

Deuda de type hints en `.agent/core/`: la regla `python.md` exige type hints en
"todas las funciones" pero el `select` de ruff en `pyproject.toml` (E,W,F,I,B,
C4,UP,ARG,SIM) no incluye `ANN*`. Conteo real (no el estimado ~213 del hallazgo
original — medido con `ruff check .agent/core/ --select ANN001,ANN201,ANN202,
ANN205,ANN206 --statistics`):

| Regla | Qué falta | Cantidad |
|---|---|---|
| ANN201 | return type en función pública | 173 |
| ANN202 | return type en función privada | 149 |
| ANN001 | type hint en parámetro | 40 |
| ANN205 | return type en static method | 1 |
| **Total** | | **363** |

No se atacó esta sesión porque agregar 363 anotaciones correctas (no solo tapar
el lint con `-> None`/`Any` a lo loco) requiere leer cada función para inferir
el tipo real — es una campaña propia, no un remate de sesión. Próxima sesión:
1. Agregar `ANN` al `select` de `pyproject.toml` (o un subset: `ANN001,ANN201,
   ANN202,ANN205` que son los que aparecen).
2. Atacar en lotes por archivo/módulo con sub-agentes en paralelo (mismo patrón
   que el barrido de `try-except-pass` de esta sesión — PR aparte, verificar
   `mypy .agent/core --ignore-missing-imports` + `pytest tests/core/` completo
   antes/después con `git stash` para descartar regresiones).
3. Multi-archivo en `.agent/core/` → requiere feature branch + PR (`best-practices.md`).

## ✅ Sesión 2026-07-20 — Barrido completo Nexus cerrado

El plan `docs/superpowers/plans/2026-07-19-nexus-full-sweep-testing.md` quedó
cerrado de punta a punta: 55 paradas Playwright, revisión visual, fixes de
Process Watcher y Hooks, `npm run quality` verde (203 archivos / 2.134 tests),
memoria y sincronización Git. No quedan bugs funcionales de ese barrido.

Las respuestas 401 observadas en 7 paradas son exclusivas de browser-preview:
el fallback no expone la session key efímera de Tauri. Las pantallas degradan de
forma segura; evitar esas requests en navegador es una mejora opcional, no un
pendiente bloqueante.

## 🟡 Sesión 2026-07-17 — NotebookLM como segundo cerebro (research + hardening)

Research completo en `discovery_notebooklm_second_brain_research_2026-07-17.md`.
**Hecho en código** (PR `feat/notebooklm-hardening` + PR #127): circuit breaker del
auto-recall (3 fallos → 6h off), timeout default 25→15s, versión del CLI pineada
(0.8.3), política "cuándo NO usar NotebookLM" en la regla, auto-login al abrir
Nexus, root editable desde la UI. **Pendientes que NO son código:**

1. 🟡 **Seguir issue #248** (device-binding de Google rompe cookie-replay):
   https://github.com/jacob-bd/notebooklm-mcp-cli/issues/248 — probable causa de
   los timeouts del auto-recall. Si sale fix upstream, subir el pin
   (`NOTEBOOKLM_MCP_CLI_VERSION` en `notebooklm_bridge.py`) y validar.
2. 🟡 **Migrar fuentes vivas de los Memory Books a Google Docs** (acción manual):
   NotebookLM auto-sincroniza fuentes Drive nativas desde 2026-05; URLs/PDFs/texto
   pegado NO. Empezar por CLAUDE.md/ESTADO_PROYECTO de los proyectos activos.
3. 🟢 **Evaluar PleasePrompto/notebooklm-mcp como transporte fallback** (browser
   persistente Patchright, inmune al device-binding; menos features).
4. 🟢 **Pipeline semanal de mantenimiento del registry** (batch/pipeline del MCP:
   agregar sesiones nuevas, podar fuentes muertas, tag común `memory-book` para
   habilitar cross_notebook_query global).
5. 🟢 **Bitemporalidad estilo Graphiti en el Brain** (valid_from/invalidated_at) —
   backlog, no urgente.

## ✅ Sesión 2026-07-16 (noche) — TODOS los PRs mergeados (7) + open-design

Análisis comparativo del proxy vs 5 repos GitHub → 6 PRs + el #117 preexistente,
**TODOS mergeados a main el 2026-07-16** con gate de tests local (CI sigue caído por billing):
#118 (buffer SSE), #119 (rescate stream vacío), #124 (dialectos tool-calls, reemplaza a #120
que GitHub cerró al borrar su base), #122 (clasificador errores), #123 (usage + pinning),
#121 (UI ModeBanner RC), #117 (resiliencia provider — conflicto resuelto conservando ambos
métodos, 424 tests verdes). Detalle: `session_2026-07-16_proxy_mejoras_comparativa_repos.md`.

Pendientes que quedan:
1. ✅ **Rebuild + INSTALACIÓN de Nexus 2.7.1 COMPLETOS** (2026-07-17): instaladores en `nexus-app/Compilacion/` e instalado silencioso (`/S`) en `%LOCALAPPDATA%\Antigravity Nexus\` — corriendo desde la ruta instalada (ya no desde `target/release`, adiós gotcha "os error 5" en builds futuros). Incluye UI #121.
2. 🟢 Mini-panel de telemetría de tokens en Nexus (el backend ya reporta usage real tras #123).
3. ✅ **`.mcp.json` reparado por Nexus** — revisado, CURADO y commiteado (2026-07-16 noche). Se conservó lo bueno (NPM_CONFIG_CACHE+PREFER_OFFLINE, fix quotes magic-21st, PATH venv paddleocr) y se descartó lo roto: `--no-cache` (config npm inválida, solo generaba warnings) y `PYTHONHOME=venv` (VERIFICADO: crashea el intérprete al arrancar — el venv de uv no tiene stdlib). Ver `config_mcp_repair_curado.md`. Launchers del repair (`START_MCP_REPAIR.cmd` + `CREAR_ACCESO_DIRECTO.ps1`) commiteados.
4. ⚪ **CONDICIÓN PERMANENTE**: Remote Control del cel intacto (memoria `remote-control-siempre-prioritario`).
   ⚠️ **REGRESIÓN 2026-07-26**: se rompió de nuevo, por partida doble — el proxy
   había vuelto a `~/.claude/settings.json` (alguien tocó un toggle de provider en
   Nexus o corrió `/provider`/`hotswap`; es lo único que re-inyecta la base URL) Y
   `remoteEnabled` estaba ausente en `~/.claude.json`. Corregido el mismo día. La
   frase "nada reconecta el proxy por defecto" es cierta solo si NO se tocan los
   switches de provider — no es una garantía pasiva. Checklist de diagnóstico
   completo en `bugfix_remote_control_regresion_doble_2026-07-26.md`.

## 🟢 Estado previo: sin tareas críticas abiertas

Al cierre del 2026-07-16 no hay bloqueantes ni 🔴 CRÍTICOS pendientes.
Ecosistema en verde. Ver **sesión 2026-07-16** abajo para lo más reciente
(mejoras a `/finalize` y nuevo comando `/merge-and-clean`).
Residuos activos:
- Issue **#108** — ✅ CLOSED (2026-07-15, lockfile drift resuelto con `npm install`)
- **Rotar `OPENROUTER_API_KEY` / `OPENCODE_API_KEY`** en `.env` — quemadas en un
  chat (2026-06-26), siguen sin rotar.
- Issue **#12** ("Nose", vacío) — ✅ CLOSED (2026-07-15, sin contexto recuperable)
- PR **#117** — fix proxy resiliencia, bloqueado por billing de CI (ver abajo)

Si surge una tarea nueva que no debe olvidarse, agregala como sección con su
estado (🔴 crítico / 🟡 importante / 🟢 nice-to-have) **arriba** de los
recordatorios permanentes.

## ✅ Sesión 2026-07-16 (mejoras /finalize + nuevo /merge-and-clean + commit brain)

Se ejecutó el plan A de 9 pasos: mejorar `/finalize` con graceful fallback para NotebookLM auth expirada, crear nuevo comando `/merge-and-clean`, y commitear los 18 nodos Brain pendientes.

**Cambios realizados:**

| Componente | Estado | Detalles |
|---|---|---|
| `/finalize` PASO 1 | ✅ Mejorado | Auto-detect cambios en `.claude/memory/` y `.agent/brain/`, ofrece commitearlos antes de continuar. Crítico para multi-PC. |
| `/finalize` PASO 2.5 | ✅ Mejorado | Validación de memoria pre-commit: verifica Capas 1, 2, 3 completadas (con fallback graceful). No pushea si memoria falló. |
| `/finalize` PASO 4.6 | ✅ Mejorado | NotebookLM auth expirada → skip silencioso + warning. No bloquea flujo. Procedimiento detallado con dry-run. |
| `/finalize` PASO 7 | ✅ Mejorado | Reporte reestructurado: 5 secciones (Validación, Memoria, Commits, Extras, Pendiente). Detalles de commits + archivos + memory. |
| `/merge-and-clean` | ✅ NUEVO | 9 pasos: validaciones → fetch → merge → cleanup local → cleanup remoto → push → reporte. Ideal para feature branches. |
| Brain sync | ✅ Sincronizado | 18 cambios (7 mods + 11 nuevos) committeados en `6bcd6e68`. 19 archivos. Includes finalize/merge-and-clean improvements. |
| Push | ✅ Completado | `git push origin main` exitoso. Commit incluye también `.claude/commands/finalize.md` y nuevo `merge-and-clean.md`. |

**Validaciones:**

- ✅ Git status limpio post-push
- ✅ Commit message en español, formato convencional `docs(brain): ...`
- ✅ Nuevo comando `/merge-and-clean` listado en skills disponibles
- ✅ `/finalize` mejorado cargable (sin syntax errors)
- ✅ PENDING_TASKS.md actualizado

**Próximos pasos:**

1. Reiniciar Claude Code para que cargue el nuevo comando `/merge-and-clean`
2. (Opcional) Testar `/finalize` completo en próxima sesión para validar graceful fallback
3. (Opcional) Rotar `OPENROUTER_API_KEY` / `OPENCODE_API_KEY` en `.env` (siguen quemadas desde 2026-06-26)

## ✅ Sesión 2026-07-15 (auditoría exhaustiva → plan 9 fases → Fases 0-8 COMPLETADAS / 7 DIFERIDA)

Se completó auditoría en 3 frentes (deuda técnica real, sistema de memoria de 3 capas, 
decisión Graphify). Hallazgos verificados contra el repo en vivo. Se aprobó plan exhaustivo
de 9 fases. **Avance:**

- ✅ **Fase 0** (housekeeping): `npm install`, cierre issues #108 #12, rebuild brain index, PENDING_TASKS actualizado
- ✅ **Fase 1** (refresh_claude_md.py): Script extendido para ambos CLAUDE.md + BRAIN_README.md; contadores synced
- ✅ **Fase 2** (reconciliar hooks): 5 wrappers en `~/.antigravity/hooks/memory/` creados; SessionEnd removido; smoke test pasado; commit `44176515`
- ✅ **Fase 3** (enriquecer session_stop): mem0 summary en nodos Brain; recall_recent_context integrado; commit `52e22751`
- ✅ **Fase 4** (brain_lint Stop): hook automático en `.claude/settings.json` proyecto; --severity error --fail-on never; commit `fc85dc8a`
- ✅ **Fase 5** (auto-remediate gateway): parámetro ?auto_fix=true en /v1/memory/diagnose; subprocess rebuild_brain_index.py; non-fatal timeout 30s; commit `c10a0dac`
- ✅ **Fase 6** (rank fusion MVP embeddings): `.agent/scripts/compute_brain_embeddings.py` + `Brain.query()` hybrid scorer (60% embedding + 40% keyword); TF-IDF proxy; placeholder para sentence-transformers; mergeado a main commit `bd4f2424`.
  **Actualizado**: el placeholder TF-IDF se reemplazó por `sentence-transformers` real
  (`multi-qa-MiniLM-L6-cos-v1`, coseno real, cache `.embeddings_cache.npz` con
  invalidación por firma mtime+size) — ya no es MVP, es la implementación completa.
  Requiere instalar el extra `.[memory]` o `.[reranking]` de `pyproject.toml` (trae
  `sentence-transformers`) y un warm-up con red para descargar el modelo una vez
  antes de que `HF_HUB_OFFLINE=1` aplique; sin eso, `Brain.query()` cae de vuelta al
  proxy `keyword_score * 0.9` (fallback graceful, ver `Brain._embedding_scores()`).
- 🟡 **Fase 7** (graphify re-benchmark): DIFERIDA — graphifyy no disponible en venv actual. Veredicto junio vigente (on-demand, no default).
- ✅ **Fase 8** (documentar): consolidación exhaustiva en memoria + Brain ingest listo (/finalize); commit `0dd8fac7`
- 🟡 **Fase 9**: PR #117 billing CI — acción del usuario (externo)

**Deuda técnica cierre:**
- Issue #108 (3 checks CI) — ✅ CLOSED. Sub-ítem "lockfile drift" resuelto: `npm install` 
  regeneró `package-lock.json`, `gcp-metadata@7.0.1` resuelto correctamente. Commiteado.
- Issue #12 ("Nose") — ✅ CLOSED. Sin contexto, se puede reabrir si usuario recuerda qué era.
- Working tree sucio — ✅ LIMPIO. `.agent/brain/index.md` y `.agent/brain/log.md` rebuildeados
  y commiteados.
- PR #117 (fix proxy resiliencia) — 🟡 BLOQUEADO por billing de CI (ver punto 3 abajo).

**Sistema de memoria 3 capas — hallazgos críticos:**
- **Hooks corren desde `$HOME/.antigravity/hooks/memory/*.py` (global)**, NO desde 
  `.agent/hooks/memory/*.py` (repo) — eso divergió. Arquitectura es global, afecta TODOS 
  los repos del usuario.
- **SessionEnd hook reapareció duplicando escritura junto a Stop** — bug que memoria decía 
  resuelto desde 2026-04-19, pero está vivo hoy en `~/.claude/settings.json`.
- **Capa 1 (`.claude/memory/*.md`, 386 archivos) fuera del pipeline de recall automático** 
  — solo indexada como texto legible, no consultada en runtime por recall.
- **Brain Network (capa 2) usa solo keyword+fuzzy matching** — CERO embeddings reales, pese 
  a que `sentence-transformers` ya es dependencia (usada por mem0). **Hallazgo del audit
  2026-07-15, superado por la Fase 6 del mismo plan** (ver arriba): hoy `Brain.query()`
  SÍ usa embeddings reales de `sentence-transformers` en hybrid rank fusion, gated por
  tener el extra `.[memory]`/`.[reranking]` instalado y el modelo cacheado localmente
  (si no, fallback automático a keyword-only con warning-once en logs).
- **Otros**: `brain_lint()` solo manual, `handle_memory_diagnose` solo reporta (no auto-remedia),
  contadores en `BRAIN_README.md` desactualizados (1517→1544 reales).

**Graphify:**
- Confirmado: `Graphify-Labs/graphify` == `safishamsi/graphify`, mismo paquete pip `graphifyy`
- Ya evaluado, instalado y benchmarkeado 2026-06-04/05 (315 nodos, 638 edges, 7.4x reducción 
  tokens). Veredicto: on-demand, no default.
- Usuario pidió re-benchmark actualizado en vez de asumir vigencia de junio.

**Plan de 9 fases** (alcance completo: memory perfeccionada + embeddings Brain + graphify 
re-benchmark) documentado en `.claude/plans/quiero-que-la-deuda-serene-emerson.md`. 
Fase 0 iniciada (housekeeping completado 2026-07-15).

## 🟡 Sesión 2026-07-10 (bug sistémico del injector — hooks + guard "nunca más")

Se arregló un bug sistémico: el injector inyectaba `settings.json` cableando
`.agent/hooks/memory/user_prompt_submit.py` pero **no copiaba `.agent/hooks/`**
(`PORTABLE_AGENT_DIRS` no incluía "hooks") → UserPromptSubmit exit≠0 → **bloqueo
de TODO prompt en 36 apps de jpkken1979**. Cerrado de raíz: **PR #114 mergeado a
main** (`fb4049c3`) con el fix + un guard auto-sanador `verify_and_heal_injected_hooks()`
(guiado por el settings, cubre hooks futuros) + tests. Las 36 apps remediadas
(`.agent/hooks/` copiado, re-scan 0). Detalle en
`[[discovery_backup_workspace_missing_hooks_2026-07-10]]`.

**Pendientes (causa externa, NO código — acción manual del usuario):**

1. 🟡 **`BorrarCarpetas26.3.30` — commit de hooks sin pushear.** Está 35 commits
   detrás de origin y `.agent/mcp/observations_mcp.log` está **bloqueado por un
   proceso corriendo** (impide `git pull`/`reset --hard`). Un rebase quedó trabado
   y se limpió a mano; HEAD intacto con el hooks commit, WIP del usuario a salvo en
   `stash@{0}`. **Para cerrar:** parar el proceso que tiene el `.log` (gateway/MCP),
   `git pull`, `git stash pop`, `git push`. Bonus: sacar ese `.log` del tracking.
2. 🟡 **`JP-v26.3.30nousar` — commit de hooks sin pushear.** Su remote apunta a
   `JP-v26.3.25.git` que da **"Repository not found" (404)**. Impusheable hasta
   arreglar la URL del remote o crear el repo (es la app "nousar").
3. 🟡 **CI de GitHub Actions caído por BILLING** — *"recent account payments have
   failed or your spending limit needs to be increased"*. Ningún job arranca, en
   todos los PRs **y en main**. No es código. **Revisar Billing & plans** en GitHub.
   (Distinto del issue #108, que es fallo de checks a nivel código.)

## ✅ Sesión 2026-07-02 (cierre audit-pro: 4 PRs mergeados + task #107 falso positivo)

Se retomó el ciclo de `audit-pro` que había quedado abierto con 4 PRs y una
tarea pendiente (#107, campaña print()→logger). Cerrado íntegro:

**4 PRs revisados y mergeados a `main`** (los CI rojos eran preexistentes en
`main`, no regresiones de estos PRs — verificado con `gh run list --branch main`
antes de mergear):
1. **#103** — hardening Nexus: `KnowledgePanel.tsx` deja de hardcodear el vault
   path de Obsidian (default `''`, configurable por usuario vía `get_config`);
   `ProviderSelector.tsx`/`useUniversalSearch.ts` dejan de hardcodear
   `http://127.0.0.1:4747` y usan `useGatewayUrl()`.
2. **#104** — `npm audit fix`: `tsx` `4.21.0→4.22.4` + regenerado
   `package-lock.json` (root + `nexus-app/`), resolvió 10 vulnerabilidades high
   (form-data CRLF, nodemailer, protobufjs, ws).
3. **#105** — CI agrega `cargo fmt --check` (con `components: rustfmt`) +
   `cargo fmt` aplicado a todo `nexus-app/src-tauri/` (33 archivos, mecánico) +
   `#[allow(dead_code)]` documentado en `provider_state.rs` (falso positivo de
   clippy sin `--all-targets`: no compila `#[cfg(test)]`, así que métodos
   usados solo por los 12 unit tests del archivo aparecían "sin usar").
4. **#106** — `ruff --fix` en 21 archivos `.agent/`, `pip-audit` agregado como
   dev dependency, 11 tests `xpass` obsoletos removidos de
   `test_agent_memory_characterization.py`.

**Task #107 (print()→logger, ~510+30 print() flagueados por el audit) cerrada
SIN cambios de código — falso positivo del audit.** Los 30 de `.agent/mcp/`
son la escritura real del protocolo stdio JSON-RPC (`print(json.dumps(...),
flush=True)` — convertirlos a logger habría roto el transporte). De 15
archivos muestreados en `.agent/core/` (~170 de 544 prints), el 100% cae en
bloques `if __name__ == "__main__":` con argparse, self-tests estilo ponytail,
docstrings, o templates de código generado (`mcp_native.py` genera OTRO
archivo `.py` como string). Cero deuda real. Documentado en
`[[discovery_print_to_logger_falso_positivo_2026-07-02]]` (commit `ac713046`
directo a main, por ser memoria).

**✅ RESUELTO — `feat/quota-threshold-ui-cascade` mergeado a `main`** (PR #107,
merge commit `86935980`) — umbral de rotación por cuota editable desde Nexus
(textbox, hot, default 5→10) + cascada extendida a
`claude→zai→minimax→opencode→openrouter→ollama`. Ejecutado con
`superpowers:subagent-driven-development` (implementer + reviewer por tarea).
Plan: `docs/superpowers/plans/2026-07-01-quota-threshold-ui-cascade.md`. Spec:
`docs/superpowers/specs/2026-07-01-quota-threshold-ui-cascade-design.md`. Las
4 tasks (Python `quota_state`+proxy+cascada, comandos Rust) quedaron aprobadas
y mergeadas; los 3 findings menores de la revisión final también resueltos.

Antes de mergear apareció un check nuevo en rojo (**Nexus Rust Tests → `cargo
fmt --check`**) por código de Task 4 que nunca había pasado por rustfmt desde
que PR #105 agregó ese gate. Fix mecánico, sin cambio semántico, pusheado
antes del merge: commit `f40f2b60`.

**3 checks en rojo preexistentes en `main` — NO son regresión de este PR**
(verificado contra el último run de CI sobre `main` antes de mergear, fallan
por las mismas razones ahí también). Trackeados en **issue #108**
(`Lint & Type Check` zip() sin strict=, `Ecosystem Structure Validation` sin
`SYSTEM_PROMPT.md` en `crisis-handler`, `TypeScript tests` lockfile drift) —
housekeeping de CI, no bloqueante, sin dueño asignado todavía.

## 🟡 PENDIENTE — rotar 2 API keys quemadas (desde sesión 2026-06-26)

`OPENROUTER_API_KEY` y `OPENCODE_API_KEY` se pegaron en texto plano durante un chat →
quemadas. **Siguen sin rotar en `.env`** (verificado 2026-07-02). Acción manual del
usuario: regenerar en el dashboard de OpenRouter / OpenCode Zen y pasar los valores
nuevos para reemplazar en `.env`.

## ✅ Housekeeping 2026-07-02 (limpieza PENDING_TASKS + branches + issues)

Confirmado con `gh pr list --state open` (vacío) que **todos** los PRs referenciados en
las secciones de sesiones 2026-06-17 a 2026-06-26 (abajo, en el histórico) ya están
mergeados — el doc había quedado desactualizado apilando esas secciones sin archivar.

- **4 ramas locales `worktree-agent-*`** (todas `YA MERGEADA` contra `main`, sin worktree
  activo en disco) → borradas con `git branch -d`.
- **Issues #7, #8, #22** (reportes automáticos de actualización de dependencias, meses
  viejos, sin nada urgente) → cerrados.
- **Issue #12** ("Nose", vacío, autor propio) → dejado abierto, sin acción — requiere
  que el usuario aclare qué era.
- Issue **#108** (3 checks CI preexistentes en `main`) → sigue abierto, sin dueño.

## 🟢 PENDIENTES de sesiones previas (no bloqueantes)

### Sesión 2026-06-11 (diagnóstico ecosistema)
1. ~~Revisar y mergear 3 PRs~~ ✅ **completado** (#50, #51, #52 mergeados, ramas borradas)
2. ~~Reinicios diferidos~~ 🟡 **diferido por usuario** — instalar Nexus 2.6.20 (no 2.6.19) + reiniciar gateway/Claude Code. **Env var `ANTIGRAVITY_ROOT` ya limpiada** (2026-06-12), pero falta aplicar nuevo binario.
3. ~~Menor: borrar memoria `diagnostic-probe`~~ ✅ **completado** (junto con limpieza de worktrees, 2026-06-12)

### Sesión 2026-06-14 (plan 022 + rename)
1. ~~Validar plan 022 en runtime~~ ✅ **VALIDADO 2026-06-15** — Gateway arranca con log exacto: `"Autonomia activada: daemon spawneado al arranque del gateway"`. Daemon proxy spawneado en :4748 ~12s post-boot. `ANTIGRAVITY_AUTONOMY_EAGER=0` revierte a lazy. Ver `.omc/gateway_boot_test.log.err` como evidencia.
2. ~~Borrar 2 ramas remotas~~ ✅ **BORRADAS 2026-06-15** — `git push origin --delete claude/activate-autonomy-eager claude/rename-confidence-assessor` ejecutado exitosamente desde local.

## 🟡 RECORDATORIOS PERMANENTES

### `.env` en este repo ES VERSIONADO INTENCIONALMENTE
- El `.env` en la raíz de `OpenAntigravity26.3.30` **SÍ está en git** — es una decisión consciente
- El repo es **privado** — ver `.gitignore` líneas 151-153 y `.claude/rules/security.md`
- **NUNCA proponer borrar, mover o ignorar el `.env` de este repo**
- Esta excepción NO aplica a repos públicos ni forks

### Tokens activos en `.env`
- `MINIMAX_API_KEY` — presente y activo
- `ZAI_API_KEY` — presente y activo
- `NVIDIA_API_KEY` — presente y activo
- `GH_TOKEN` — presente y activo
- `MAGIC_21ST_API_KEY` — presente y activo (resuelto 2026-05-18)
- `STITCH_API_KEY` — presente; MCP `stitch` desactivado temporalmente (2026-06-02)

## ✅ Histórico de resueltos (referencia)

### PRs de provider switching/cascada mergeados (sesiones 2026-06-17 → 2026-06-26)

Todos verificados mergeados (`gh pr list --state open` vacío al 2026-07-02). Detalle
completo en los `.md` de `.claude/memory/` referenciados:

- **#69/#70/#71** (2026-06-18) — roadmap Nexus Fases 0/1/2: auto-disable shadow,
  reset circuito + fail-closed remote, sampling shadow + export/import `.mcp.json`.
  Spec: `docs/superpowers/specs/2026-06-18-nexus-mejoras-roadmap-design.md`.
- **#72** — rate-limit friendly message (header `unified-reset`).
- **#73** — fix test pollution gateway: nunca purgar `sys.modules` de `mcp.*`
  (anti-patrón documentado en el Brain).
- **#76/#77** (2026-06-22) — cascada de fallback `claude→minimax→zai→ollama` + toggle
  `autoswitch` opt-in. `[[session_2026-06-22_cascade_fallback]]`, `[[session_2026-06-22_variante_b]]`.
- **#79/#80** (2026-06-24) — sanitizer robusto del proxy (reconcilia tool_use/tool_result
  huérfanos ante switch en caliente) + catálogo declarativo `.antigravity/providers.json`.
  `[[bugfix_cross_provider_history_400]]`.
- **#87** — fix GLM-5.2 SSE false-positive (`_chunk_has_recoverable_sse_error` parseaba
  mal el primer frame) + migración de `test_gateway_health_deep_probe.py` al patrón
  sin purgar `sys.modules`.
- **#88** (2026-06-26) — providers catalog-driven + alta OpenRouter/OpenCode Zen.
  `[[session_2026-06-26_providers_catalog_openrouter_opencode]]`. **Validación runtime
  de providers OpenAI remotos (OpenRouter/OpenCode) mid-tool-loop sigue sin confirmar**
  — riesgo real no cerrado, retomar si se usan esos providers.

### Proxy hot-swap de IA unificado (cerrado 2026-05-26)

Funcional de punta a punta bajo el modelo proxy-always. `ANTHROPIC_BASE_URL`
apunta SIEMPRE al proxy (`http://127.0.0.1:4747/claudeproxy`); el provider activo
vive en `~/.antigravity/proxy/active_provider.json`, NO en la base URL. Cambio en
caliente con `/provider <x>`. **Rollback** (actualizado 2026-07-12): borrar
`ANTHROPIC_BASE_URL` de `~/.claude/settings.json` a mano y reiniciar 1 vez. ⚠️ El botón
"Desconectar proxy" de Nexus y `provider_switch.py disconnect` quedaron **deprecados** (en
proxy-always ya no sacan el proxy). Es la vía real para usar Remote Control del cel — ver
`[[decision_proxy_disconnect_for_mobile_remote_2026-07-10]]`. SPOF aceptado: con proxy
conectado, si el gateway `:4747` cae, no hay IA — Nexus lo auto-arranca. Detalle:
`feature_provider_hotswap_proxy.md`.

### Test pollution del core (cerrado 2026-05-25)

- `user_model.json`: default de `UserPreferenceModel` ya no apunta al repo
  (`user_preference_model.py:109-121`, resolución 3-tier).
- `shared_memory.json` / nodos basura del brain: commits `efe82775` + `0ee9473b`.
- Si REAPARECE pollution en `git status` tras tests:
  `py .agent/skills-custom/test-fixture-isolator-runtime/scripts/main.py --scope tests/core/`

### Otros fixes

- Fix: `memory.rs` — inyección de `X-API-Key` en todos los calls mem0 → commit `ddc1f91c`
- Fix: `MinimaxToggleCard.tsx` + `ZaiToggleCard.tsx` — auto-refresh 15s + focus event
- Build Nexus v2.5.3 exitoso → instaladores en `nexus-app/Compilacion/`
- Fix: race condition `process_watcher._wait_exit` → commit `25d5569f` (2026-05-17)
- Fix: `shell=True` eliminado en `webapp-testing/scripts/with_server.py` → commit `2dd46842` (2026-05-17)
- Fix: PATH npx en Windows resuelto con `_resolve_npx()` → commit `1262d190` (2026-05-17)
- Feat: 26 skills nuevos/upgrade desde skills.sh → commits `7fd54d66` + `7cf34254` (2026-05-17)
- Refinamiento: `tail()` espera `finished_stdout`/`finished_stderr` separados consistente con `_wait_exit` (2026-05-17)
- **Resuelto: `MAGIC_21ST_API_KEY`** — usuario pegó la key en `.env` (2026-05-18). MCP magic-21st operativo. Requiere `/reload-plugins` en sesiones nuevas para activar.
- Lite refactor 16 skills custom + 4 agentes nuevos al estándar oficial Anthropic (2026-05-18)
- Instalación de `skill-creator` + `mcp-builder` oficiales de anthropics/skills (2026-05-18)
- Fix 6 gaps no críticos kintai/yukyu/haken + 2 skills no-UNS (2026-05-18)
