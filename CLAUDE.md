# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sobre el proyecto

App Windows en japonés para **ユニバーサル企画株式会社 (UNS-Kikaku)** que respalda y restaura correos de Outlook. La versión actual es **v3.2.0**, declarada en tres lugares que deben mantenerse en sync al bumpear: `build/installer.iss:5` (`MyAppVersion`, fuente de verdad para el release), `pyproject.toml:10` y `src/api.py:get_app_info`. El `name:` de `.github/workflows/build.yml` todavía dice "v3.1" — es cosmético (solo el título del workflow), no afecta el release.

El proyecto vive **dentro** del repo `Jpkken1979` que tiene su propio ecosistema Antigravity. Las reglas globales en `../CLAUDE.md` y `../.claude/rules/` aplican aquí (respuestas en español, commits convencionales, etc.).

## Comandos comunes

### Dev / Build

| Comando | Qué hace |
|---|---|
| `run.bat` | Modo dev: crea `.venv` si no existe, instala `requirements.txt`, ejecuta `python src\main.py` |
| `build.bat` | Build completo: venv + deps + icono + PyInstaller + Inno Setup (si está) |
| `pyinstaller build\pyinstaller.spec --clean --noconfirm` | Build manual del `.exe` (resultado en `dist/`) |
| `python src\main.py` | Lanzar GUI directamente (requiere venv activo) |
| `python src\main.py --auto` | Modo background usado por Windows Task Scheduler (sin GUI) |
| `python build\generate_icon.py` | Regenerar `assets/icon.ico` |
| `git tag v3.2.X && git push origin v3.2.X` | Dispara release en GitHub Actions con `.exe` + installer adjuntos |

### Calidad (toolchain con `uv`)

`pyproject.toml` es la fuente moderna de deps; `requirements.txt` se mantiene en sync para `build.yml` (regenerable con `uv export --no-hashes > requirements.txt`).

| Comando | Qué hace |
|---|---|
| `uv sync --extra dev` | Instala deps de dev (ruff, mypy, pytest, playwright, hypothesis) |
| `uv run ruff check src tests` | Lint (reglas E/W/F/I/B/C4/UP/ARG/SIM, línea 100) |
| `uv run ruff format --check src tests` | Verifica formato (reemplaza black + isort) |
| `uv run mypy src` | Typecheck — `disallow_untyped_defs` se aplica por **lista explícita** de módulos en `pyproject.toml`; un módulo nuevo no queda cubierto hasta agregarlo ahí |
| `uv run pytest -v --cov=src --cov-report=term-missing` | Suite completa con coverage |
| `uv run pytest tests/test_backup_engine.py::test_xxx` | Correr un solo test |
| `uv run pytest -m "not e2e"` | Saltear los E2E de Playwright (más rápido) |
| `uv run pytest -m "not windows"` | En Linux skipea los tests con `pytestmark = pytest.mark.windows` |
| `uv run playwright install --with-deps chromium` | Instala el browser para los E2E |

**Gotcha multi-PC**: el `.venv/` está en el working tree pero `pyvenv.cfg` guarda rutas absolutas de la máquina que lo creó. En otra PC `uv run` falla con `uv trampoline failed to canonicalize script path` — el fix es recrearlo (`uv sync --extra dev`), no debuggear el comando. Sin `structlog` y `rarfile` instalados fallan 15 tests (`test_observability.py`, `test_shell_extractor.py`) por `ModuleNotFoundError`, no por código roto.

## Arquitectura — pywebview bridge (v3.0+)

A partir de v3.0 la GUI dejó de ser **tkinter** y pasó a ser una **WebView2 nativa** que renderiza HTML/CSS/JS.

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend (WebView2 / Edge Chromium) — modular en v3.1       │
│ index.html → tokens.css + components.css + styles.css        │
│            → i18n.js → services/api.js + state.js            │
│            → components/*.js → pages/*.js                    │
│            → app-orchestrator.js (routing + init sequence)   │
│          ↑ window.pywebview.api.<method>(args)               │
│          ↓                                                   │
│ src/api.py — Clase API (bridge Python ↔ JS)                │
│   ├─ Estado: _backup_state, _import_state (locks)          │
│   ├─ Polling: get_backup_progress(), get_import_progress()   │
│   └─ Métodos públicos → accesibles desde JS                 │
│             ↓ imports lazy                                  │
│ src/*.py — Motores backend                                  │
└──────────────────────────────────────────────────────────────┘
```

**Estructura del frontend (refactor v3.1):**
```
src/web/
├── index.html              # 7 tabs: backup, restore, history, auto, cache, tools, settings
├── css/
│   ├── tokens.css          # Design tokens (colores, espaciado, tipografía)
│   ├── components.css      # Estilos por componente
│   └── styles.css          # Layout global, tabs, overlays
└── js/
    ├── app-orchestrator.js # Routing tabs + init sequence + connection badge (único entry point;
    │                       # el viejo app.js monolítico ya no existe)
    ├── i18n/
    │   ├── i18n.js         # Helper t() y carga
    │   └── ja.json         # Strings japoneses del frontend
    ├── services/
    │   ├── api.js          # Wrapper tipado de window.pywebview.api (Api.start_backup, etc.)
    │   └── state.js        # Store reactivo con listeners (State.set/get/onChange)
    ├── components/
    │   ├── Modal.js        # confirm/alert con promise
    │   ├── Toast.js        # notifications no bloqueantes
    │   └── Button.js, Card.js, List.js
    └── pages/
        ├── backup.js       # Cada page expone init(el) / mount() / unmount()
        ├── restore.js, history.js, auto.js, cache.js, tools.js, settings.js
```

**Cómo funciona el bridge:**
- `main.py:run_gui()` instancia `API()` y la pasa como `js_api=api` a `webview.create_window`.
- Toda función pública de `API` (sin guion bajo) queda accesible desde JS como `window.pywebview.api.<nombre>(args)`.
- El frontend usa `Api.<method>(args)` (wrapper en `services/api.js`) en vez de tocar `window.pywebview.api` directo — esto centraliza error handling.
- Cada page module hace su propio polling con `setInterval` cada 500ms.
- Diálogos nativos (carpeta, archivo) usan `webview.create_file_dialog`.

### Pattern de page modules

Cada tab es un IIFE en `js/pages/<nombre>.js` que expone:

```javascript
const BackupPage = (() => {
    function init(el)    { /* bind events una vez */ }
    function mount()     { /* render + cargar datos al cambiar de tab */ }
    function unmount()   { /* clearInterval del polling, cleanup */ }
    return { init, mount, unmount };
})();
```

`app-orchestrator.js` mantiene un `pages` registry y llama `pages[tab].mount()/unmount()` al cambiar de tab. Esto evita memory leaks de intervals huérfanos cuando el usuario alterna tabs durante operaciones largas.

### Patrón de jobs asíncronos

**Regla**: toda operación que tarde más de ~2s debe usar este patrón.

```
API._backup_state  → "idle" | "running" | "success" | "failed"
API._backup_log    → [{ts, msg}, ...] (últimos 50 mensajes)
API._backup_result → string con la ruta cuando termina
API._backup_lock   → threading.Lock para coherencia
API._backup_engine → motor activo (permite cancel())
```

Nuevo job: `start_X(params)` → dispara thread → `run_async(progress_cb, finish_cb)` → polling `get_X_progress()`.

**Ejemplo de polling desde un page module** (patrón usado en `src/web/js/pages/backup.js`):
```javascript
// Iniciar backup → polling loop cada 500ms via Api wrapper
const r = await Api.start_backup({...});
if (!r.success) return;
pollingInterval = setInterval(async () => {
    const p = await Api.get_backup_progress();
    updateBackupUI(p);
    if (p.state === 'success' || p.state === 'failed') {
        clearInterval(pollingInterval);
        onBackupDone(p);
    }
}, 500);
```

**Importante**: el polling debe limpiarse en `unmount()` de cada page. El orquestador llama `unmount()` automático al cambiar de tab.

### Progress overlay

El overlay (`#progress-overlay` en `index.html:608-619`) se reutiliza para backup normal, import y cache backup. Se calcula percent desde regex `\[(\d+)\/(\d+)\]` en los mensajes de log y se gestiona desde cada page.

### Componentes UI reutilizables

- `Modal.confirm(title, body)` — Promise<boolean>, botones Cancel/OK
- `Modal.alert(title, body)` — Promise<void>, solo OK
- `Toast.show(msg, type)` — notification no bloqueante (`type`: `info|success|warn|error`)

## Dos caminos de backup

| Camino | Archivo | Servidor muerto | Dependencias |
|--------|---------|-----------------|--------------|
| **COM** (`backup_engine.py`) | `.pst` / `.msg` vía `AddStoreEx` + `CopyTo` | No funciona | Outlook abierto, servidor responsivo |
| **Cache** (`cache_backup.py`) | Copia directa `.ost`/`.pst` | Funciona | Solo lectura del archivo en disco |

### COM backup (`backup_engine.py`)

```
BackupEngine._run_internal()
→ Para cada cuenta:
    1. namespace.AddStoreEx(output_path, 3)  # olStoreUnicode
    2. Busca el store recién creado
    3. Busca el store origen (match por DisplayName o smtp en DisplayName)
    4. _copy_folder_recursive() — CopyTo por cada subcarpeta
    5. namespace.RemoveStore(new_root)  # cerrar PST
→ Genera report.json + report.html
```

**Slug de archivos**: `smtp_address.replace("@", "_at_").replace(".", "_")` → `kenji_at_uns-kikaku_com.pst`

**Formatos de export**: `pst` (default, archivo único) o `msg` (cada email como `.msg` individual).

### Cache backup (`cache_backup.py`) — v3.1

Útil para disaster recovery cuando el servidor IMAP/Exchange está caído.

```
CacheBackupEngine._run()
→ Opcional: cierra Outlook (_kill_outlook via COM o taskkill)
→ Para cada archivo:
    1. _copy_with_progress() — copia en chunks de 4MB con feedback
    2. _verify_copy() — SHA256 del src vs dest
→ _write_report() — genera report.json
```

**Ubicaciones escaneadas** (`get_outlook_cache_dirs()`):
- `%LOCALAPPDATA%\Microsoft\Outlook`
- `%APPDATA%\Microsoft\Outlook`
- `Documents\Outlook Files`
- `Documents\Outlook ファイル`

**Match con cuentas**: `map_cache_to_account()` usa `winreg` para leer `HKCU\Software\Microsoft\Office\{ver}\Outlook\Profiles\{profile}` — busca SMTP en valores REG_SZ y REG_BINARY (utf-16-le decoded). Si no hay registry, infiere desde el nombre del archivo (patrones `_at_`, ` - `, `@`).

**Opciones**:
- `verify_integrity` — calcula SHA256 después de copiar (default: True)
- `close_outlook` — cierra Outlook antes de copiar OST (necesario porque OST está bloqueado)
- `use_vss` — (default: True) sólo aplica cuando `close_outlook=False`. Intenta hot-copy VSS (requiere admin); si no es admin, falla o el módulo no está, cae al copy clásico, que sobre un OST abierto puede dar `PermissionError`

## Tres modos de import

`import_engine.py` restaura PSTs con estos modos:

| Modo | Método COM | Semántica |
|------|-----------|----------|
| `separate_folder` (default) | `namespace.AddStore(pst_path)` | PST como carpeta separada en sidebar |
| `merge` | `namespace.AddStore` + `.CopyTo(target)` recursivo | Items al Inbox de la cuenta target |
| `new_files` | `namespace.AddStoreEx(pst_path, 3)` | Cada PST como data file Unicode |

Para `merge`: busca source_store por `FilePath` match y target_store por `DisplayName`. Después de copiar carpetas, hace `RemoveStore(source_root)` para desmontar el PST origen (el target ya tiene los datos).

## Inventario encriptado — formato binario

`account_inventory.py` + `crypto_utils.py` generan archivos `.json.enc`:

```
[MAGIC 8B][version 1B][iterations 4B][salt 16B][nonce 12B][AES-GCM ciphertext + auth tag]
```

- **MAGIC**: `b"UNSCRYPT"` — identificar el formato
- **VERSION**: 1
- **iterations**: 200_000 (PBKDF2)
- **Key derivation**: PBKDF2-HMAC-SHA256 → AES-256 key
- **Cipher**: AES-256-GCM con nonce aleatorio de 12B
- **Auth tag**: appended por pyca/cryptography (12B típicos)

### Inventario de cuentas

`build_inventory()` en `account_inventory.py`:

1. **Info básica** — vía `namespace.Accounts` COM (smtp, display_name, account_type, delivery_store)
2. **Server settings** — desde `HKCU\Software\Microsoft\Office\{ver}\Outlook\Profiles` (winreg) — busca email match en REG_BINARY utf-16-le, extrae server strings y puertos de KNOWN_PORTS
3. **Passwords** — desde Windows Credential Vault (`win32cred.CredEnumerate`) — filtra por patrones Outlook en TargetName + match con smtp/domain

## Módulos del backend

| Módulo | Responsabilidad |
|---|---|
| `api.py` | Bridge pywebview, polling state, diálogos nativos, orchestrador |
| `outlook_client.py` | COM con Outlook (pywin32). `export_account_to_pst` usa `AddStoreEx` + `CopyTo`. `export_folder_to_msg_files` guarda emails como `.msg` individuales |
| `backup_engine.py` | Backup multi-cuenta + BackupReport (genera report.html con branding UNS) |
| `cache_backup.py` | Copia directa OST/PST del disco, con SHA256 verify. Lee registry para mapear archivos a cuentas |
| `import_engine.py` | Restore PST con 3 modos: `separate_folder`, `merge`, `new_files` |
| `pst_inspector.py` | Preview de PST sin importarlo: monta, lee carpetas, top 5 senders, date range |
| `history_manager.py` | Lista backups previos desde `backup_{timestamp}/` folders. `cleanup_old(keep_last)` borra los más viejos (solo exitosos) |
| `shell_extractor.py` | Extrae archivos RAR y ejecuta scripts de migración (PowerShell, batch, VBS, EXE). Requiere WinRAR o 7-Zip instalado |
| `scheduler.py` | Wrap de `schtasks.exe` (built-in Windows). `create_task()` soporta daily/weekly/biweekly (WEEKLY+MO2)/monthly/custom (DAILY+MO). Nombre fijo: `UNS-Outlook-Backup-Auto` |
| `account_inventory.py` | Genera JSON con cuentas. `_read_registry_servers()` y `_read_credential_vault()` para server settings y passwords |
| `crypto_utils.py` | AES-256-GCM + PBKDF2-HMAC-SHA256 (200K iter). `estimate_password_strength()` → score 0-100 con label japonés |
| `connection_tester.py` | Test de conectividad IMAP/SMTP con `socket` + `ssl` puros (sin libs externas). Mide latencia, captura banner, prueba LOGIN. Usado por `API.test_connection()` en tab Settings |
| `config.py` | Config persistente en `%APPDATA%\UNS-Kikaku\Backup\config.json`. DEFAULT_CONFIG incluye todos los settings con defaults |
| `search_index.py` | Índice FTS5 (SQLite stdlib) sobre los **metadatos** del historial de backups — cuentas, fechas, tamaños, estado, rutas PST. La app no parsea PST, así que "búsqueda" nunca significa buscar dentro de los emails. `rebuild_from_history()` es idempotente (borra y reconstruye) |
| `vss_copy.py` | Hot-copy de OST/PST vía Volume Shadow Copy **sin cerrar Outlook**. Requiere admin (`IsUserAnAdmin`); si no lo es devuelve `VssCopyResult(success=False, reason="not_admin")` y el caller hace fallback a cerrar Outlook. Siempre limpia el shadow en `finally` |
| `i18n.py` | Loader que lee los strings desde `src/web/js/i18n/ja.json` (192 keys) — **fuente única compartida con el frontend**, no un dict inline. `t(key, **kwargs)` interpola y devuelve la key tal cual si falta (defensivo, nunca crashea). El backend usa `json.load()`, el frontend `fetch()` sobre el mismo archivo, así no divergen |

### Configuración por defecto (`config.py:30-57`)

```python
DEFAULT_CONFIG = {
    "domain_filter": "uns-kikaku.com",
    "backup_all_accounts": False,
    "default_backup_dir": "~/Documents/UNS_Backup",
    "default_format": "pst",  # o "msg"
    "default_import_mode": "separate_folder",
    # schedule
    "schedule_enabled": False,
    "schedule_frequency": "weekly",
    "schedule_day_of_week": "MON",
    "schedule_time": "02:00",
    "schedule_custom_days": 7,
    "schedule_save_to": "",
    "schedule_scope": "uns_only",  # "uns_only" | "all" | "custom"
    "schedule_custom_accounts": [],
    "schedule_keep_last": 4,
    # inventory
    "inventory_enabled": False,
    "inventory_include_servers": True,
    "inventory_include_passwords": False,
    # última ejecución
    "last_run_time": None,
    "last_run_status": None,
}
```

### Logging en modo auto

`main.py:run_auto_backup()` configura logging a archivo (`auto.log` en `%APPDATA%\UNS-Kikaku\Backup\`) y loguea con emojis + japonés (ej: `📡 Outlookに接続中...`, `🤖 自動バックアップ開始`).

## PyInstaller spec

`build/pyinstaller.spec` calcula paths con `SPECPATH` (el directorio del spec, **no** el CWD). Usa `ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))`.

**Módulos en `hidden`** (líneas 11-28): cualquier módulo nuevo en `src/` que se importe dinámicamente (dentro de funciones, como hace `api.py`) debe agregarse aquí. Si el `.exe` falla con `ModuleNotFoundError`, falta en el spec — ver "Imports lazy y el `.exe`" más abajo para la lista y por qué el build no lo detecta.

**Excludes** (líneas 45-50): PyQt, PySide, matplotlib, numpy, pandas, scipy, IPython, pytest — mantenidos para reducir tamaño.

**`datas`**: copia `src/web/` a `web/` y `assets/*.ico` a `assets/`. Archivos nuevos en `src/web/` se incluyen automáticamente.

**Output name**: `UNS-Outlook-Backup.exe` (línea 66).

## GitHub Actions release

`.github/workflows/build.yml` corre en `push` a `main`/`master`, en tags `v*`, y manualmente. El job necesita `permissions: contents: write` para crear releases con `softprops/action-gh-release`.

Para publicar release:
1. Bump versión en `src/api.py` (`get_app_info`), `pyproject.toml` (`version`), `build/installer.iss` (`MyAppVersion`), workflow (`name`).
2. Commit, push.
3. `git tag v3.2.X && git push origin v3.2.X`.
4. Esperar el workflow → release aparece con `.exe` portable + installer.

CI usa **Python 3.11** en `windows-latest`. Timeout de 25 min.

## Stack y dependencias

```
pywin32      — COM con Outlook (Dispatch "Outlook.Application")
pyinstaller  — empaquetado a .exe
cryptography — AES-256-GCM + PBKDF2 (inventario encriptado)
pywebview    — WebView2 nativa para la UI
pythonnet    — CLR loader requerido por pywebview en Windows
rarfile      — Lectura de archivos RAR (requiere WinRAR o 7-Zip instalado)
structlog    — Logging estructurado (usado por src/observability)
win32cred    — Windows Credential Vault para passwords
winreg       — Registro de Windows para server settings y profile mapping
```

Runtime: Python 3.10+. Toolchain de dev: **uv + ruff + mypy + pytest + playwright**.

## Testing — corre en Linux Y Windows

`tests/` tiene 25 archivos `test_*.py` top-level + 3 E2E en `tests/e2e/` (Playwright), cubriendo engines (backup/cache/import), observability, i18n, fakes de Outlook, deteccion de runtime (WebView2, version Outlook), long paths, date filter, incremental state y connection tester.

**El truco para correr en Linux**: `tests/conftest.py` define un fixture `mock_win32_modules(autouse=True, scope="session")` que inyecta `MagicMock` en `sys.modules` para `win32com`, `win32cred`, `winreg`, `pythoncom`, `pywintypes`, `webview` ANTES de cualquier import de `src/`. Esto permite que el código bajo test se importe sin pywin32 instalado.

**Markers** (`pyproject.toml:192-201`):
- `slow` — tests pesados, deselect con `-m "not slow"`
- `windows` — requieren Windows real, skipean en Linux CI
- `outlook` — requieren Outlook instalado de verdad
- `e2e` — Playwright + chromium (necesita `playwright install`)
- `outlook_version` — tests version-specific de Outlook (introducido por Fase 1 plan v3.2)
- `webview2` — flujo de deteccion del runtime WebView2 (Fase 2 plan v3.2)
- `long_paths` — paths > MAX_PATH (260 chars) con prefijo `\\?\` (Fase 3 plan v3.2)

**Coverage** (`pyproject.toml:208-224`): incluye todo `src/` excepto `main.py` y `src/web/*`. No hay umbral mínimo configurado en CI todavía.

**Fakes tipados**: `src/outlook/fakes.py` reemplaza al `MagicMock` genérico para tests más realistas — usar via fixtures en `tests/test_outlook_fakes.py`.

## Sub-packages del backend (refactor reciente)

Además de los módulos top-level mencionados arriba, `src/` tiene dos subpackages:

```
src/outlook/
├── protocols.py    # Protocols (PEP 544) que tipan la API COM de Outlook
├── constants.py    # OL_FOLDER_INBOX = 6, OL_STORE_UNICODE = 3, etc.
├── fakes.py        # Implementación in-memory para tests sin Outlook
└── real.py         # Wrapper sobre win32com.client.Dispatch (producción)

src/observability/
├── logging.py      # structlog setup — JSON en prod, pretty en dev
├── crash.py        # Captura excepciones no manejadas → archivo + telemetry
└── updater.py      # Check de versiones contra GitHub Releases
```

`outlook_client.py` (top-level) sigue siendo el entry point legacy; el subpackage `outlook/` es la abstracción nueva con tipos. Verificar cuál usa el módulo que tocás antes de elegir.

## Módulos del plan v3.2 (hardening Win 10/11)

El plan `docs/PLAN_HARDENING_WIN10_11.md` introdujo módulos de detección de entorno y robustez.

| Módulo | Fase | Responsabilidad |
|---|---|---|
| `runtime_check.py` | 2 | Detección de WebView2: `is_webview2_installed()` lee registry (`HKLM/HKCU` PV value). Si falta, `ensure_webview2_runtime()` muestra diálogo en japonés, busca bootstrapper bundleado o lo baja, y corre `MicrosoftEdgeWebview2Setup.exe /silent /install` |
| `path_utils.py` | 3 | Long path support para Win 10 sin la policy habilitada. `is_long_path()` detecta >260 chars, `safe_path()` antepone `\\?\` para evitar `FileNotFoundError`, `validate_backup_dir()` chequea permisos antes de empezar |
| `outlook/version.py` | 4 | Detección de versión Outlook: `detect_outlook_version()` distingue M365 (`HKCU\Software\Microsoft\Office\ClickToRun\Configuration`) de perpetual (`HKLM\Software\Microsoft\Office\{ver}\Outlook\InstallRoot`). `is_supported()` valida ≥ Outlook 2016 |
| `date_filter.py` | 6 (partial) | Filtro por rango de fechas para Feature C. `should_include(item, start, end)` evalúa cada email; `filter_pst_items()` recorre el store aplicando el filtro |
| `incremental_state.py` | Feature A | Estado del backup incremental: clase `IncrementalState` que persiste último timestamp procesado por cuenta para evitar re-exportar emails ya backupeados |
| `search_index.py` | Feature B | Índice FTS5 sobre metadatos del historial (ver tabla de módulos del backend) |
| `vss_copy.py` | 6 | Hot-copy VSS sin cerrar Outlook (ver tabla de módulos del backend) |

Cuando agregues un módulo nuevo del plan: registralo en el bloque strict de `pyproject.toml` (`[[tool.mypy.overrides]]` con `disallow_untyped_defs`), agregalo al `hidden` de `build/pyinstaller.spec` si se importa lazy, y bajalo a tests con su marker correspondiente.

### Imports lazy y el `.exe` — la trampa recurrente

Los módulos del plan v3.2 se importan **dentro de funciones**, no en el top-level:

| Módulo | Import lazy en | Si falta en el spec |
|---|---|---|
| `runtime_check` | `main.py:62` | Se pierde la detección de WebView2 |
| `outlook.version` | `main.py:61` | Se pierde la detección de versión |
| `search_index` | `api.py:488` | Cae en el try genérico → error a la UI |
| `vss_copy` | `cache_backup.py:306` | Tiene `except ImportError` → fallback al copy clásico |
| `incremental_state` | `backup_engine.py:303` | **Sin guarda** → el backup incremental falla |
| `date_filter` | `backup_engine.py:263` | (también top-level en `outlook_client.py:14`) |

PyInstaller no detecta estos imports, así que **el build pasa igual y `python src\main.py` funciona** — sólo revienta en el `.exe` y sólo al ejecutar ese camino. Los siete ya están en `hidden` (2026-07-28). `outlook.fakes` queda deliberadamente afuera: es solo de tests.

El bloque strict de mypy también quedó completo: `scheduler`, `search_index` y `vss_copy` faltaban y se agregaron. Verificado con `mypy src --ignore-missing-imports` → 31 archivos sin errores.

## CI — dos workflows independientes

| Workflow | Trigger | Qué hace |
|---|---|---|
| `.github/workflows/build.yml` | push main/master, tags `v*`, manual | Build `.exe` + installer en Windows, publica release en tags |
| `.github/workflows/quality.yml` | push/PR a main/master, manual | Lint (ruff), typecheck (mypy advisory), tests (pytest matrix Linux + Win 11 + Win 10) con coverage |

**Quality workflow detalle** (`quality.yml`):
- `lint` — Ruff check + format check, bloqueante
- `typecheck` — Mypy con `continue-on-error: true` (advisory hasta que limpie todo el legacy). Notar que aunque `pyproject.toml` declara strict per-module sobre todo `src/`, el CI no lo bloquea todavia
- `tests` — Matrix de **3 plataformas**: `ubuntu-latest`, `windows-latest` (Win 11) y `windows-2019` (Win 10 baseline para validar sin WebView2 preinstalado y con Outlook 2019 perpetual)
- Cachea browsers de Playwright entre runs; sube `htmlcov/` como artifact solo en Windows 11
- Concurrency cancela runs viejos al pushear de nuevo
- Usa `astral-sh/setup-uv@v3` con cache habilitado

## Convenciones

- **Strings de UI en japonés** (`i18n.py`).
- **Identificadores en inglés** en código.
- **Mensajes de log** mezclan emoji + japonés (intencional, el usuario final lee la UI en japonés).
- **Slug de archivos**: `email_at_dominio_com.pst` (`@` → `_at_`, `.` → `_`)
- **Config y logs**: `%APPDATA%\UNS-Kikaku\Backup\`. Backups por defecto: `~\Documents\UNS_Backup\`
- **Tarea programada**: nombre fijo `UNS-Outlook-Backup-Auto`
- **Win32 fallback**: todos los módulos que usan pywin32 tienen `try/except ImportError` con `WIN32_AVAILABLE = True/False`

## Archivos generados por backup

```
backup_{YYYYMMDD_HHMMSS}/
├── kenji_at_uns-kikaku_com.pst
├── info_at_uns-kikaku_com.pst
├── ...
├── report.html          # reporte visual con branding UNS
├── report.json          # datos estructurados
└── accounts.json        # (si inventory_enabled) inventario plano
    accounts.json.enc    # (si inventory_enabled + passwords) encriptado
```

```
cache_backup_{YYYYMMDD_HHMMSS}/
├── *.ost / *.pst       # copias directas
└── report.json         # con stats y SHA256 verify
```

## Windows Credential Vault

`win32cred.CredEnumerate` filtra credenciales por patrones en `TargetName`:
```
OUTLOOK_PATTERNS = [
    'microsoftoffice', 'microsoft.exchange', 'microsoft_oc1',
    'mail.', 'imap.', 'pop.', 'smtp.', 'outlook.com',
    'office365', 'exchange.', 'ssti:',
]
```
Match secundario: smtp o domain en TargetName o UserName.

## Registry paths de Outlook

Busca en `HKCU\Software\Microsoft\Office\{ver}\Outlook\Profiles` (ver=16.0, 15.0, 14.0). Scanea valores REG_BINARY decodificando utf-16-le, buscando emails y server strings.

---

<!-- ANTIGRAVITY-START -->

## Integracion Antigravity

Proyecto integrado con **Antigravity v6.1.4**.
Instalado por Nexus el 2026-07-24.

### Persona activa: gentleman

El estilo de comunicacion de la IA se adapta segun el modo de persona.
Modos disponibles: `gentleman` (detallado, pedagogico), `neutral` (factual),
`conciso` (minimalista). Configurar via `ANTIGRAVITY_PERSONA` env var o
`.antigravity/config.json`. Ver `.claude/rules/persona.md` para detalles.

### Runtime MCP-first

```
.agent/
  agents/ skills/ skills-custom/ workflows/
  scripts/ core/ mcp/ plugins/
.claude/
  settings.json hooks/ rules/
.antigravity/
  config.json sdk/ ai_manifest.json rules.md
```

### Clientes compatibles

- Claude Code: `.claude/settings.json` + `.mcp.json`
- Cursor: `.cursor/mcp.json` + `.cursorrules`
- Windsurf: `.windsurf/mcp.json` + `.windsurfrules`
- VS Code / Roo / Cline: `.vscode/mcp.json` y `.vscode/cline_mcp_settings.json`
- Zed: `.zed/settings.json`
- Cualquier IA/IDE con MCP: `.mcp.json` y `.antigravity/ai_manifest.json`

### SDK Python

```python
from .antigravity.sdk.client import Client
client = Client()
result = client.run("explorer", "analiza el repo")
```

### Memoria

- Memoria MCP: `antigravity-memory` (mem0)
- Memoria de proyecto: `ESTADO_PROYECTO.md`
- Reglas compartidas: `.claude/rules/` y `.antigravity/rules.md`

<!-- ANTIGRAVITY-END -->
---

## Skills y Agentes prioritarios para esta app

**Dominio**: Backup / Storage (respaldo y gestion de archivos y datos del ecosistema)

| Tipo | Nombre | Para que |
|---|---|---|
| skill | `cross-pc-memory-sync` | Sincronizacion de memorias y configuracion entre PCs via git |
| skill | `aspirador` | Auditoria exhaustiva y limpieza segura de archivos y dependencias |
| skill | `security-audit` | Verificacion de integridad y seguridad de los backups |
| skill | `code-review` | Revision de scripts de backup y restore |
| agent | `subagent-orchestrator` | Coordinacion de tareas de backup multi-destino |

**Como invocarlos**:
- Skills: `Skill(skill="<nombre>")` o `python .agent/skills-custom/<nombre>/scripts/main.py`
- Agents: `python .agent/scripts/invoke-agent.py <nombre>`

**Inventario completo**: ver `RULES.md` en OpenAntigravity26.3.30 para los 879 skills + 113 agents disponibles.
