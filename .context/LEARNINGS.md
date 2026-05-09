# LEARNINGS & ANTI-PATTERNS (Memoria Histórica)

Este archivo registra errores corregidos para que los agentes futuros no los repitan.

## [2026-02-02] Fidelidad de Datos vs Automatización
- **Contexto**: Importación de nombres desde el 社員台帳.
- **Error**: Se intentó automatizar la conversión Kanji -> Katakana usando una librería (`pykakasi`).
- **Problema**: El Excel ya contenía la columna `カナ` con los nombres verificados. La automatización generaba variaciones innecesarias.
- **Lección Aprendida**: SIEMPRE verificar si existe una columna nativa en el Excel para datos sensibles antes de aplicar algoritmos de conversión. La columna `カナ` o `カタカナ` es la fuente de verdad.
- **Acción Correctiva**: El `EmployeeLoader` ahora prioriza la columna `カナ`.

---

## [2026-02-02] Mapeo de Hojas en Excel v3.1
- **Contexto**: Detección de hojas en el maestro de empleados.
- **Problema**: El usuario se refería a las hojas como "GenzaiX" y "Ukeoi", pero en el archivo real se llaman `派遣社員` y `請負社員`.
- **Lección Aprendida**: Usar un script diagnosticador (`debug_shain.py`) para listar las hojas reales antes de implementar el parser final.
- **Acción Correctiva**: Actualizadas las constantes en `UNS_FILES`.

---

## [2026-02-27] preload.cjs vs preload.ts en Electron

- **Contexto**: Nexus App tiene dos archivos preload: `preload.ts` (TypeScript con validación) y `preload.cjs` (CommonJS cargado en runtime).
- **Problema**: Se añadieron IPC handlers en `main.ts` y en `preload.ts`, pero `preload.cjs` (el archivo real que Electron carga) no se actualizó.
- **Lección Aprendida**: Electron carga **`preload.cjs`**, no `preload.ts`. Siempre actualizar ambos al añadir nuevos canales IPC. El `.ts` es solo source con tipo-seguridad; el `.cjs` es lo que importa en runtime.
- **Acción Correctiva**: Al añadir `toggle-remote-server` y `generate-token`, actualizar ambos archivos en el mismo commit.

---

## [2026-02-27] Hooks de Claude Code — Rutas Absolutas Obligatorias

- **Contexto**: Los hooks `PostToolUse`, `Stop` y `SessionStart` en `.claude/settings.json` usaban rutas relativas (`python3 .agent/scripts/hook.py`).
- **Problema**: Al ejecutar comandos desde `nexus-app/` (subcarpeta del proyecto), el working directory cambia y las rutas relativas no resuelven al directorio raíz correcto.
- **Lección Aprendida**: Los hooks de Claude Code usan el working directory del proceso padre, no la raíz del proyecto. **Siempre usar rutas absolutas** en hooks para garantizar que funcionen independientemente del CWD.
- **Acción Correctiva**: Todos los comandos de hooks actualizados a `python3 C:/Users/kenji/AntigravitiSkillUSN/.agent/scripts/...`
- **Nota**: Los cambios en `settings.json` requieren **reiniciar Claude Code** para surtir efecto.

---

## [2026-02-27] Skill remote-control — Token Generation

- **Contexto**: El helper `remote_control.py` genera tokens para `ANTIGRAVITY_API_TOKEN`.
- **Lección Aprendida**: `secrets.token_urlsafe(32)` en Python y `crypto.randomBytes(32).toString('base64url')` en Node producen exactamente la misma longitud (43 caracteres) y entropía equivalente (256 bits). Para el IPC de Nexus es más eficiente usar Node directamente en `main.ts` que spawnar un proceso Python.
- **Acción Correctiva**: El handler `generate-token` en `main.ts` usa `crypto.randomBytes` nativo de Node.

---

## [2026-03-02] SQLite `unixepoch('now','subsec')` — Compatibilidad de Versión

- **Contexto**: `SQLiteMemoryBackend` en `memory_backend.py` necesitaba timestamps de alta precisión.
- **Problema**: `unixepoch('now','subsec')` requiere SQLite ≥ 3.38.5 (lanzado 2022). Python 3.11 bundlea SQLite 3.39+ pero entornos con Python 3.10 o versiones anteriores fallan silenciosamente.
- **Lección Aprendida**: Para timestamps en SQLite, preferir `julianday('now')` (disponible desde siempre) sobre funciones modernas de `unixepoch`. Es universalmente compatible.
- **Acción Correctiva**: Schema actualizado a `CHECK-IN REAL DEFAULT (julianday('now'))`.

---

## [2026-03-02] Framer Motion Variants — Deben Estar Fuera del Componente

- **Contexto**: TypeScript strict (`noUnusedLocals`, `erasableSyntaxOnly`) en el proyecto Nexus.
- **Problema**: Definir `const variants: Variants = {...}` dentro de un componente React crea una nueva referencia en cada render, causando re-animaciones innecesarias. TypeScript strict también puede marcarlas como dependencias de useEffect si se usan dentro de efectos.
- **Lección Aprendida**: **Siempre** extraer Framer Motion Variants a constantes de módulo (fuera del componente). En Nexus: `sidebarVariants.ts` centraliza todas las Variants del sidebar.
- **Acción Correctiva**: Creado `src/components/Sidebar/sidebarVariants.ts` con todas las Variants exportadas.

---

## [2026-03-02] `nexus-app/release/` en .gitignore — Commitear el .exe

- **Contexto**: El directorio `nexus-app/release/` está en `.gitignore` (electron-builder lo genera automáticamente).
- **Problema**: `git add nexus-app/release/Antigravity-Nexus-1.0.0.exe` falla silenciosamente — el archivo se ignora.
- **Lección Aprendida**: Para commitear el `.exe` compilado (administrado con Git LFS), usar `git add -f nexus-app/release/Antigravity-Nexus-1.0.0.exe`.
- **Acción Correctiva**: Usar `-f` (force) en todos los commits del exe de release.

---

## [2026-03-02] AppLayout `left: 220` Hardcodeado — Limitación Post-MVP

- **Contexto**: El content area de `AppLayout.tsx` usa `style={{ top: 76, left: 220 }}` fijo.
- **Problema**: Cuando el sidebar colapsa a 56px, el content area no se ajusta automáticamente — el sidebar superpone levemente el contenido.
- **Lección Aprendida**: Para MVP es aceptable. Para producción, pasar el estado `isExpanded` del sidebar hacia arriba (via callback o context) y calcular `left` dinámicamente en `AppLayout`.
- **Acción Correctiva (post-MVP)**: `onExpandedChange?: (expanded: boolean) => void` prop en Sidebar + estado en AppLayout.

---

## [2026-03-03] Dependencias No Instaladas — Orchestrator en Modo SIMULATED

- **Contexto**: Sprints 1-9 generaron ~35 módulos core nuevos en una sesión de 8 horas.
- **Problema**: Las dependencias críticas (`crewai`, `redis`, `anthropic`, `fastapi`, `chromadb`) no están instaladas. El orchestrator tiene 4 tiers de fallback y siempre cae al Tier 4 (SIMULATED), retornando resultados ficticios.
- **Lección Aprendida**: El código de los sprints es arquitecturalmente sólido y los tests pasan con mocks, pero **nunca se ejecutó end-to-end**. Antes de considerar el ecosistema "operativo", ejecutar: `pip install -e ".[all]"` + crear `.env` con API keys + `docker-compose up -d`.
- **Detalle técnico**: Todos los módulos avanzados usan `try/except` lazy imports con fallbacks graceful. El `redis_message_bus` tiene fallback SQLite. Esto es correcto como diseño defensivo pero enmascara la ausencia de dependencias.
- **Acción Correctiva**: Documentado en `ESTADO_PROYECTO.md` con checklist de activación.

---

## [2026-03-03] Migración Electron → Tauri 2 — Legacy Coexiste

- **Contexto**: Nexus Desktop migrado de Electron a Tauri 2 con backend Rust.
- **Problema**: El directorio `electron/` existía con `main.ts` (1452 líneas), `preload.cjs` y `splash.html`, generando confusión.
- **Lección Aprendida**: `package.json` ya NO tiene `electron` como dependencia. Tiene `@tauri-apps/api` + plugins Tauri 2. Los scripts activos son `tauri:dev` y `tauri:build`.
- **Acción Correctiva**: Directorio `electron/` eliminado con `git rm -r`. Referencias actualizadas en toda la documentación. Los `docs/plans/` históricos mantienen referencias como contexto arqueológico.

---

## [2026-03-03] Patrón de Lazy Imports con try/except — Diseño Defensivo

- **Contexto**: Los módulos de Sprints 1-9 (`agent_daemon`, `gateway`, etc.) importan dependencias dentro de bloques `try/except`.
- **Problema**: Esto permite que el código cargue sin errores incluso cuando las dependencias no están instaladas. Pero enmascara problemas — un módulo puede "funcionar" sin hacer nada real.
- **Lección Aprendida**: Este patrón es correcto para un ecosistema con dependencias opcionales. Pero al debuggear, verificar PRIMERO si las dependencias están realmente instaladas antes de buscar bugs en la lógica. `pip list | grep <dep>` es el primer paso de diagnóstico.
- **Señal de alerta**: Si ves `logger.warning("... no disponible: %s", e)` en los logs, es casi seguro que falta una dependencia, no un bug.

---

## [2026-03-05] FastAPI redirect_slashes y MCP — Endpoint /mcp vs /mcp/

- **Contexto**: El servidor MCP remoto (`mcp-server/remote.py`) montaba la app SSE en `/mcp/` con FastAPI.
- **Problema**: FastAPI tiene `redirect_slashes=True` por defecto. Un cliente que accede a `/mcp` (sin trailing slash) recibe un 307 redirect a `/mcp/`. Algunos clientes MCP no siguen redirects automáticamente, causando fallos de conexión.
- **Lección Aprendida**: Siempre agregar endpoints explícitos para ambas variantes (`/mcp` y `/mcp/`) o desactivar `redirect_slashes`. En APIs MCP, los redirects pueden romper la conexión SSE/Streamable HTTP.
- **Acción Correctiva**: Agregado endpoint explícito para `/mcp` que redirige manualmente con `RedirectResponse`.

---

## [2026-03-05] Tauri invoke() para datos de filesystem — Evitar gateway HTTP innecesario

- **Contexto**: `PluginsPanel.tsx` usaba `fetch("http://localhost:4747/plugins")` para listar plugins.
- **Problema**: Requería que el gateway Python estuviera corriendo. Los plugins son simplemente directorios en `.agent/plugins/` — no necesitan procesamiento Python.
- **Lección Aprendida**: Para datos que son puramente del filesystem (listar directorios, contar archivos), crear un Tauri command en Rust es más eficiente y confiable que depender del gateway HTTP. Reservar el gateway para operaciones que realmente necesitan Python (agentes, skills, memoria).
- **Acción Correctiva**: Creado `plugins.rs` con `list_plugins` que escanea el filesystem directamente desde Rust. El panel funciona sin gateway.

---

## [2026-03-08] Agent Lifecycle: De Activo a Deprecado — Proceso de Consolidación

### Contexto General
El ecosistema creció de forma orgánica en múltiples sprints: 40+ agentes especializados, herramientas redundantes, roles solapados. Consolidación es necesaria para reducir mantenimiento y mejorar claridad.

### Consolidación Realizada (2026-02-04)
Se consolidaron **7 agentes documentados**:
- `project-planner` → `planner` (WBS, estimación, roadmaps)
- `product-owner` → `product-manager` (PRD, MoSCoW, RICE)
- `product-strategist` → `product-manager` (visión estratégica)
- `product-architect` → `architect` (decisiones arquitectónicas)
- `qa-specialist` → `test-engineer` (automatización de tests)
- `qa-automation-engineer` → `test-engineer` (test automation)
- `accessibility-specialist` → `a11y` (WCAG 2.1 AA/AAA compliance)

### Anti-patrones de Deprecación

**Evitar:**
- Deprecar sin crear reemplazo claro — causa confusión sobre qué usar
- No documentar la razón — genera uncertainty sobre reactivación futura
- Dejar agentes en caché después de deprecar — rompe orchestrator cache
- Eliminar inmediatamente — perder referencia histórica y código valioso
- No verificar referencias — deprecar algo que otros agentes siguen usando

**Mejor práctica:**
- Crear reemplazo ANTES de deprecar
- Documentar mapping en `DEPRECATED.md` (por qué, dónde migraron capacidades)
- Mover a `.agent/agents/_deprecated/` (mantener para auditoría histórica)
- Actualizar `ORGANIZATION.md` con categorización (consolidado, framework-specific, legacy, etc.)
- Buscar referencias: scripts, workflows, skills, tests
- Comunicar en `.context/LEARNINGS.md` (para futuras decisiones)

### Auditoría Resultante (2026-03-08)

Después de organizar los 68 agentes deprecados:

| Categoría | Cantidad | Estado |
|-----------|----------|--------|
| Consolidados (documentados) | 7 | ✅ Seguro eliminar |
| Consolidados (inferidos) | 4 | ⚠️ Verificar refs |
| Framework-específicos | 7 | ⚠️ Confirmar soporte |
| Extraídos a skills/core | 6 | ✅ Seguro eliminar |
| Legacy sin reemplazo claro | 37 | 🔴 Requiere auditoría |

**Lección Clave:** La categoría de "legacy sin reemplazo" (37 agentes) sugiere que algunos fueron creados experimentalmente sin arquitectura clara desde el inicio. Futuras decisiones de diseño deben:
1. Definir tier y propósito del agente antes de crear
2. Mantener matriz de "quién llama a quién" (agent dependency graph)
3. Revisar antes de cada consolidación: ¿ese agente está realmente en uso?

### Proceso de Consolidación Próxima

Cuando se identifique un agente para consolidar:

```
1. [DECISIÓN] Identificar agente + proponer reemplazo
   └─ Ejemplo: "coder es generalista, debería dividirse en especialistas"

2. [DISEÑO] Crear reemplazo en agentes activos
   └─ Ejemplo: frontend-specialist + backend-specialist absorben "coder"
   └─ Documentar en IDENTITY.md qué capacidades cubre

3. [AUDITORÍA] Buscar todas las referencias
   └─ grep -r "coder" .agent/agents/ .agent/skills/ .agent/workflows/
   └─ grep -r "coder" tests/

4. [MIGRACIÓN] Actualizar referencias
   └─ Cambiar workflows que llamen a "coder"
   └─ Actualizar agentes que dependan de "coder"

5. [DOCUMENTACIÓN] Crear entrada en DEPRECATED.md
   └─ Fecha, agente, razón, reemplazo, capacidades absorbidas

6. [MOVIMIENTO] mv .agent/agents/{name} .agent/agents/_deprecated/{name}

7. [TABLA] Actualizar .agent/agents/_deprecated/ORGANIZATION.md
   └─ Categorizar en tabla + verificación

8. [VALIDACIÓN] Tests deben pasar sin referencias al agente deprecado
```

### Caso de Reactivación

Si en el futuro se descubre que un agente deprecado sigue siendo necesario:

1. Revisar ORGANIZATION.md para entender por qué fue deprecado
2. Evaluar si el reemplazo realmente cubre todos los casos
3. Decidir:
   - Mover de vuelta a `.agent/agents/` (reactivar)
   - Consolidar capacidades únicas en reemplazo existente
   - Mantener deprecado pero actualizar docs
4. Documentar la decisión con fecha y justificación

### Herramientas de Referencia

- `.agent/agents/_deprecated/DEPRECATED.md` — Consolidación original
- `.agent/agents/_deprecated/ORGANIZATION.md` — Auditoría completa + categorización
- `.context/LEARNINGS.md` — Este archivo (decisiones y lecciones)

**No eliminar** `.agent/agents/_deprecated/` hasta que se complete la auditoría y confirme cero referencias históricas.

---

## [2026-03-09] Nexus: Errores Silenciosos de Memoria (Causa Raíz de Desconexión)

- **Contexto**: El usuario reportaba que "la memoria no se conectaba" en Nexus Desktop.
- **Causa Raíz**: 5 catch blocks en `useMemoryData.ts` usaban `catch { /* silencioso */ }` — tragaban TODOS los errores de conexión sin mostrar nada al usuario ni en los logs.
- **Problema Compuesto**: Los Tauri commands en `memory.rs` creaban `reqwest::Client::new()` sin timeout, permitiendo que la UI se congelara indefinidamente si el gateway no respondía.
- **Tercer Factor**: No existía health check inmediato después de iniciar el gateway — había un gap de 30s donde la UI decía "running" pero el gateway aún no estaba listo.
- **Lección**: NUNCA usar `catch { /* silencioso */ }` en hooks que conectan con servicios remotos. Siempre loggear el error para diagnóstico. Siempre configurar timeouts en clientes HTTP.
- **Acciones Correctivas**:
  1. Reemplazados 5 catch silenciosos con `addLog('[WARN] ...')` en `useMemoryData.ts`
  2. Creada función `memory_client()` con timeout de 10s y connect_timeout de 5s en `memory.rs`
  3. Agregado callback `onGatewayStateChange` en `useServerState.ts` que dispara health check 2s después de arrancar
  4. Agregados delays de 1s entre arranques de servidores en `App.tsx` para evitar contención

---

## [2026-03-09] asyncio.get_event_loop() Deprecado en Python 3.10+

- **Contexto**: 12 archivos core usaban `asyncio.get_event_loop()` que genera DeprecationWarning en Python 3.10+.
- **Lección**: Usar `asyncio.get_running_loop()` dentro de coroutines. `get_event_loop()` puede crear loops implícitamente, causando bugs sutiles.
- **Archivos afectados**: agent_daemon.py, mcp_client.py, redis_message_bus.py, workflow_engine.py, webhooks.py, cross_agent_messaging.py, y 4 gateway mixins.

---

## [2026-03-09] agent_daemon.py Monolito → Mixins

- **Contexto**: `agent_daemon.py` tenía 2,945 líneas — demasiado grande para mantener.
- **Solución**: Extraer métodos adaptadores a 3 mixins:
  - `_daemon_mixin_planning.py` (MetaPlanner, AnomalyDetector, Telemetry, SelfImprover)
  - `_daemon_mixin_coordination.py` (Reactive, Negotiation, Swarm, Router, Consensus, Observatory, Workflow)
  - `_daemon_mixin_advanced.py` (Reputation→EmergentBehavior, Sprint 6-9C)
- **Resultado**: 1,330 líneas core + 3 archivos mixins. API intacta gracias a herencia múltiple.
- **Lección**: Cuando una clase supera ~1,500 líneas, descomponer en mixins por dominio funcional.

---

## [2026-03-09] Bot TS: console.* vs createLogger()

- **Contexto**: `query-cache.ts` usaba 9 llamadas a `console.error/info/warn` directamente.
- **Problema**: El resto del bot usa `createLogger()` para logging estructurado con tags.
- **Lección**: Consistencia en logging es más importante que la herramienta. Si el proyecto usa un logger, usarlo en TODOS los módulos.
