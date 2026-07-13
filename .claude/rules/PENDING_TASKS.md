# Tareas Pendientes — Se auto-inyecta en CADA sesión

> Leer esto SIEMPRE al inicio de sesión. Son tareas NO completadas que no deben olvidarse.

## 🟢 Estado actual: sin tareas críticas abiertas

Al cierre del 2026-07-02 no hay bloqueantes ni 🔴 CRÍTICOS pendientes.
Ecosistema en verde. Ver **sesión 2026-07-02** abajo para lo más reciente
(cierre de audit-pro + merge de `feat/quota-threshold-ui-cascade`, PR #107, +
housekeeping de este doc). Residuos activos:
- Issue **#108** — 3 checks de CI preexistentes en `main`, no bloqueantes.
- **Rotar `OPENROUTER_API_KEY` / `OPENCODE_API_KEY`** en `.env` — quemadas en un
  chat, ver sección propia abajo.
- Issue **#12** ("Nose", vacío, autor propio) — sin acción, requiere aclaración del usuario.

Si surge una tarea nueva que no debe olvidarse, agregala como sección con su
estado (🔴 crítico / 🟡 importante / 🟢 nice-to-have) **arriba** de los
recordatorios permanentes.

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
caliente con `/provider <x>`. **Rollback**: botón "Desconectar proxy" en Nexus,
`python .agent/core/provider_switch.py disconnect`, o borrar `ANTHROPIC_BASE_URL`
de `~/.claude/settings.json` (requiere reiniciar 1 vez). SPOF aceptado: con proxy
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
