# AntigravitiSkillUSN — Conocimiento de Aplicación

> Actualizado: 2026-03-03 | Versión del ecosistema: 2.1.0

---

## Resumen Ejecutivo

| Aspecto | Valor |
|---------|-------|
| **Tipo** | Ecosistema multi-capa (Python backend + Tauri 2 desktop) |
| **Lenguaje backend** | Python 3.11+ |
| **Framework backend** | FastAPI (gateway) + MCP protocol |
| **Desktop app** | Tauri 2 (Rust) + React 19 + TypeScript 5.9 |
| **Base de datos** | PostgreSQL (producción), SQLite (observaciones locales) |
| **Testing** | pytest (251 archivos) |
| **Versión** | 2.1.0 |

---

## Componentes Principales

### Backend Python (`.agent/`)

| Módulo | Descripción |
|--------|-------------|
| `agents/` | 119 agentes autónomos en 12 tiers |
| `skills/` | 937+ skills (788 base + 9 custom + 140 en plugins) |
| `mcp/` | 8 servidores MCP: gateway.py (4747), ecosystem-server, agents-server, skills-server, intelligence-server, observations-server, ui-server, remote-server (3777) |
| `core/` | 90 módulos core + 10 subdirectorios (Sprints 1-9: orquestación, swarm, inteligencia, resiliencia, observabilidad, memoria) |
| `plugins/` | 73 plugins integrados |
| `sdk/` | Python SDK: `from antigravity.sdk.client import Client` |

### Desktop App (`nexus-app/`) — Tauri 2

Tauri 2 (Rust backend) + React 19 + TypeScript. Control center visual del ecosistema. **Ventana: 1100×750px.**

> **Nota:** `electron/` fue eliminado. La app usa `src-tauri/` con commands Rust.

**Archivos clave:**
| Archivo | Función |
|---------|---------|
| `src-tauri/src/main.rs` | Entry point Tauri: registro commands, plugins, estado global |
| `src-tauri/src/tray.rs` | System tray con menú contextual |
| `src-tauri/src/commands/` | 8 módulos: config, deps, ecosystem, gateway, memory, observations, remote, servers |
| `src/App.tsx` | Dashboard principal — gestiona estado + despacha a AppLayout |
| `src/SetupWizard.tsx` | Wizard de primera ejecución (2 pasos) |
| `src/ErrorBoundary.tsx` | Catch-all de errores React |
| `src/components/Layout/AppLayout.tsx` | Layout principal: Sidebar + StatusBar + AnimatePresence |
| `src/components/Sidebar/Sidebar.tsx` | Sidebar colapsable 220↔56px (spring stiffness 300, damping 30) |
| `src/components/StatusBar/StatusBar.tsx` | Barra fija top:40 h:36 — estado 3 servidores + gateway 4747 |
| `src/features/panels/` | 7+ paneles: Motores, Memoria, IA, Red, Logs, Agentes, Evolución, Plugins |

**Secciones del sidebar:**
| Sección | Contenido |
|---------|-----------|
| Motores | ServerControlCard + GatewayStatusCard |
| Memoria | ClaudeMemBackupCard + MemoryPanel |
| IA | AiConfigPanel + SessionProfilePanel |
| Red | RemoteNetworkingPanel + RemoteTokenCard + InjectorCard |
| Agentes | AgentesPanel — panel de agentes del ecosistema |
| Evolución | EvolucionPanel — genome y evolución (Sprint 8) |
| Plugins | PluginsPanel — gestión de plugins |
| Logs | LogsViewer (full height) |

### MCP Servers (8 internos)

| Servidor | Transporte | Puerto | Uso |
|----------|-----------|--------|-----|
| `gateway.py` | HTTP/SSE | 4747 | Gateway maestro v3.0 (recomendado) |
| `ecosystem-server.py` | stdio | — | Servidor principal del ecosistema |
| `agents-server.py` | stdio | — | Gestión de agentes |
| `skills-server.py` | stdio | — | Skills library |
| `intelligence-server.py` | stdio | — | Hub de inteligencia |
| `observations-server.py` | stdio | — | Pipeline de observaciones |
| `ui-server.py` | stdio | — | Servidor para Nexus UI |
| `remote-server.py` | HTTP/SSE | 3777 | Acceso remoto via red |

---

## Tauri Commands (Nexus App — 27 commands)

> Migrado de Electron IPC a Tauri commands (Rust). Todos son `async fn` → `Result<T, String>`.

### Window & System (main.rs, 4 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `select_folder` | `app: AppHandle` | Dialog OS para elegir carpeta |
| `get_auto_start` | `app: AppHandle` | Verificar si autostart está habilitado |
| `set_auto_start` | `enabled: bool` | Habilitar/deshabilitar autostart al login |
| `show_notification` | `title, body: String` | Notificación nativa del OS |

### Config (commands/config.rs, 3 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `get_config` | `app: AppHandle` | Lee `nexus-config.json` del app data dir |
| `save_config` | `updates: HashMap<String, Value>` | Merge parcial de config |
| `validate_path` | `root_path, path_type: String` | Valida ruta como "antigravity" o "claudeMem" |

### Servers (commands/servers.rs, 3 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `toggle_antigravity_server` | `state: bool` | Start/stop Antigravity MCP server |
| `toggle_claude_mem` | `state: bool` | Start/stop Claude-Mem Bun worker |
| `toggle_remote_server` | `state: bool` | Start/stop servidor MCP remoto (:3777) |

### Observations (commands/observations.rs, 6 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `get_observation_stats` | — | Estadísticas del pipeline de observaciones |
| `search_observations` | `query: String, limit?: u32` | Búsqueda en observaciones (default 20) |
| `get_recent_sessions` | `limit?: u32` | Últimas sesiones IA (default 30) |
| `get_file_history` | `file_path: String, limit?: u32` | Historial de observaciones por archivo |
| `get_claude_mem_projects` | — | Listar proyectos de Claude-Mem |
| `get_queue_status` | — | Estado de la cola de observaciones |

### Memory (commands/memory.rs, 3 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `backup_claude_mem` | `app: AppHandle` | Backup completo de Claude-Mem (file picker) |
| `export_memories` | `app: AppHandle` | Exportar memorias a JSON/tar |
| `import_memories` | `app: AppHandle` | Importar memorias desde JSON/tar |

### Ecosystem (commands/ecosystem.rs, 2 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `update_ecosystem` | — | Git pull --ff-only en ambos repos |
| `inject_mcp` | `target_dir: String` | Ejecuta `mcp_injector.py` en carpeta destino |

### Dependencies (commands/deps.rs, 4 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `check_dependency` | `command: String` | Verifica binario disponible (`--version`) |
| `check_python_deps` | — | Verifica mcp, pydantic, fastapi, httpx |
| `install_bun` | — | Instala Bun via PowerShell |
| `install_python_deps` | — | `pip install -e ".[dev,llm,observability]"` |

### Remote (commands/remote.rs, 3 commands)

| Command | Parámetros | Descripción |
|---------|-----------|-------------|
| `generate_token` | — | Genera token random 32-byte (base64url) |
| `test_remote_connection` | `url, token: String` | Test HTTP GET a `/health` con bearer auth |
| `get_mcp_snippet` | `url, token: String` | Genera snippet MCP para servidor remoto |

---

## Configuración del Sistema (nexus-config.json)

Almacenada en `{userData}/config/nexus-config.json`. Campos:

```typescript
interface NexusConfig {
  antigravityRoot: string;      // Ruta al proyecto AntigravitiSkillUSN
  pythonPath: string;            // Ejecutable Python (defecto: 'python')
  bunPath: string;               // Ejecutable Bun
  gitPath: string;               // Ejecutable Git
  firstRunComplete: boolean;     // false → muestra SetupWizard
  trayNotificationShown: boolean;
  autoStartEnabled: boolean;
  openGatewayInBrowserOnLaunch: boolean;
  sessionProfile?: 'fast' | 'balanced' | 'deep';  // Haiku/Sonnet/Opus
}
```

---

## Variables de Entorno

```env
# IA Providers
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_AI_API_KEY=

# Database
DATABASE_URL=
REDIS_URL=

# Seguridad
SECRET_KEY=
ANTIGRAVITY_API_TOKEN=     # Token Bearer para remote-server.py

# Observabilidad
SENTRY_DSN=
SLACK_WEBHOOK_URL=
OTEL_EXPORTER_OTLP_ENDPOINT=

# UNS Enterprise (solo env vars, NUNCA hardcodear)
UNS_DATA_PATH=
UNS_PHONE=
UNS_FAX=
UNS_REPRESENTATIVE=
UNS_COMPLAINT_HANDLER=
UNS_DISPATCH_LICENSE=
UNS_BANK_NAME=
UNS_BANK_BRANCH=
UNS_BANK_TYPE=
UNS_BANK_ACCOUNT=
UNS_BANK_HOLDER=

# Ecosistema
ANTIGRAVITY_HOME=          # Auto-detectado si no se define
ENVIRONMENT=
DEBUG=
LOG_LEVEL=
PORT=
```

---

## Comandos de Build

```bash
# Nexus App (Tauri 2)
cd nexus-app/
npm install
npm run dev              # Vite dev server solo (puerto 5173)
npm run build            # TypeScript check + Vite production build
npm run tauri:dev        # Vite + ventana Tauri nativa
npm run tauri:build      # Vite + compilar Rust + empaquetar

# Python backend
make install && make test && make lint

# Docker
docker-compose up -d
```

---

## Flujo de Inicio (Nexus App — Tauri 2)

```
1. Tauri app launch → ventana principal con WebView
2. React mount → App.tsx carga configuración via Tauri commands
3. SetupWizard si firstRunComplete = false
4. Dashboard operational con servidores controlables
5. System tray activo (tray.rs) con menú contextual
```

---

## Zonas de Riesgo

| Área | Nivel | Razón |
|------|-------|-------|
| `electron/` eliminado | — | Migrado a Tauri commands (directorio borrado) |
| Datos UNS | ALTO | PII sensible — solo en env vars |
| `remote-server.py` sin token | MEDIO | Acepta todas las conexiones si `ANTIGRAVITY_API_TOKEN` no está definido |
| Observation pipeline Python | BAJO | Migrado de `exec()` a `spawn()` + `observation_ipc.py` (2026-02-27) |
| Dependencias no instaladas | MEDIO | Orchestrator cae a Tier 4 (SIMULATED) sin crewai/anthropic |
| Lazy imports con try/except | BAJO | Enmascara dependencias faltantes — verificar con `pip list` |

---

## Skills Destacadas

| Skill | Trigger | Función |
|-------|---------|---------|
| `remote-control` | `/remote-control` | Gestiona remote-server.py: start, health, config, token |
| `mcp-integration` | `/mcp-integration` | Configura servidores MCP en IDEs |
| `secrets-management` | `/secrets-management` | Gestión segura de tokens y credenciales |
| `docker-compose` | `/docker-compose` | Orquestación del stack Docker |

---

*Ecosistema Antigravity v5.0.0 — 119 agentes | 907+ skills | 90 core modules | 9 MCP servers | Nexus App v2.4.3 (Tauri 2)*
