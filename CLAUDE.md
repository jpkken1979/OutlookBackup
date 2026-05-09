# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sobre el proyecto

App Windows en japonés para **ユニバーサル企画株式会社 (UNS-Kikaku)** que respalda y restaura correos de Outlook. La versión actual es **v3.1.0** (verificable en `src/api.py:616` y `build/installer.iss:5`).

El proyecto vive **dentro** del repo `Jpkken1979` que tiene su propio ecosistema Antigravity. Las reglas globales en `../CLAUDE.md` y `../.claude/rules/` aplican aquí (respuestas en español, commits convencionales, etc.).

## Comandos comunes

| Comando | Qué hace |
|---|---|
| `run.bat` | Modo dev: crea `.venv` si no existe, instala `requirements.txt`, ejecuta `python src\main.py` |
| `build.bat` | Build completo: venv + deps + icono + PyInstaller + Inno Setup (si está) |
| `pyinstaller build\pyinstaller.spec --clean --noconfirm` | Build manual del `.exe` (resultado en `dist/`) |
| `python src\main.py` | Lanzar GUI directamente (requiere venv activo) |
| `python src\main.py --auto` | Modo background usado por Windows Task Scheduler (sin GUI) |
| `python build\generate_icon.py` | Regenerar `assets/icon.ico` |
| `git tag v3.1.X && git push origin v3.1.X` | Dispara release en GitHub Actions con `.exe` + installer adjuntos |

**No hay tests.** Verificación manual ejecutando `run.bat` o el `.exe` compilado.

## Arquitectura — pywebview bridge (v3.0+)

A partir de v3.0 la GUI dejó de ser **tkinter** y pasó a ser una **WebView2 nativa** que renderiza HTML/CSS/JS.

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend (WebView2 / Edge Chromium)                         │
│ src/web/index.html + css/styles.css + js/app.js              │
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

**Estructura del frontend:**
```
src/web/
├── index.html     # Entry HTML con tabs: backup, restore, history, auto, cache
├── css/styles.css
└── js/app.js     # App singleton con bindUI, polling, modales, toasts
```

**Cómo funciona el bridge:**
- `main.py:run_gui()` instancia `API()` y la pasa como `js_api=api` a `webview.create_window`.
- Toda función pública de `API` (sin guion bajo) queda accesible desde JS como `window.pywebview.api.<nombre>(args)`.
- El frontend (`app.js`) usa polling con `setInterval` cada 500ms para operaciones largas.
- Diálogos nativos (carpeta, archivo) usan `webview.create_file_dialog`.

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

**Ejemplo de polling desde JS** (ver `src/web/js/app.js:358-369`):
```javascript
// Iniciar backup → polling loop cada 500ms
const r = await api.start_backup({...});
if (!r.success) return;
this.backupPolling = setInterval(async () => {
    const p = await api.get_backup_progress();
    this.updateBackupUI(p);
    if (p.state === 'success' || p.state === 'failed') {
        clearInterval(this.backupPolling);
        this.onBackupDone(p);
    }
}, 500);
```

### Engine de polling en frontend

`App` en `app.js` tiene polling dedicado por operación:
- `startBackupPolling()` → `updateBackupUI()` → `onBackupDone()`
- `startImportPolling()` → `updateImportUI()` → `onImportDone()`
- `startCacheBackupPolling()` → `updateCacheBackupUI()` → `onCacheBackupDone()`

El UI de progreso es compartido: overlay con `progress-fill` y `progress-status`.

### Progress overlay

El mismo overlay se reutiliza para backup normal, import y cache backup. Se muestra con `showProgress()` (calcula percent desde regex `\[(\d+)\/(\d+)\]` en los mensajes de log) y se oculta con `hideProgress()`.

### Modales y toasts

- `App.confirm(title, body)` — modal con botón Cancel/OK, Promise
- `App.alert(title, body)` — modal con solo OK
- `App.showToast(msg, type)` — por ahora usa `setStatus()` (no hay toast visual aún)

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
| `scheduler.py` | Wrap de `schtasks.exe` (built-in Windows). `create_task()` soporta daily/weekly/biweekly (WEEKLY+MO2)/monthly/custom (DAILY+MO). Nombre fijo: `UNS-Outlook-Backup-Auto` |
| `account_inventory.py` | Genera JSON con cuentas. `_read_registry_servers()` y `_read_credential_vault()` para server settings y passwords |
| `crypto_utils.py` | AES-256-GCM + PBKDF2-HMAC-SHA256 (200K iter). `estimate_password_strength()` → score 0-100 con label japonés |
| `config.py` | Config persistente en `%APPDATA%\UNS-Kikaku\Backup\config.json`. DEFAULT_CONFIG incluye todos los settings con defaults |
| `i18n.py` | 213 strings japoneses en el dict `JA`. Función `t(key, **kwargs)` para interpolación |

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

**Módulos en `hidden`** (líneas 11-28): cualquier módulo nuevo en `src/` que se importe dinámicamente (dentro de funciones, como hace `api.py`) debe agregarse aquí. Si el `.exe` falla con `ModuleNotFoundError`, falta en el spec.

**Excludes** (líneas 45-50): PyQt, PySide, matplotlib, numpy, pandas, scipy, IPython, pytest — mantenidos para reducir tamaño.

**`datas`**: copia `src/web/` a `web/` y `assets/*.ico` a `assets/`. Archivos nuevos en `src/web/` se incluyen automáticamente.

**Output name**: `UNS-Outlook-Backup.exe` (línea 66).

## GitHub Actions release

`.github/workflows/build.yml` corre en `push` a `main`/`master`, en tags `v*`, y manualmente. El job necesita `permissions: contents: write` para crear releases con `softprops/action-gh-release`.

Para publicar release:
1. Bump versión en `src/api.py` (`get_app_info`), `build/installer.iss` (`MyAppVersion`), workflow (`name`).
2. Commit, push.
3. `git tag v3.1.X && git push origin v3.1.X`.
4. Esperar el workflow → release aparece con `.exe` portable + installer.

CI usa **Python 3.11** en `windows-latest`. Timeout de 25 min.

## Stack y dependencias

```
pywin32      — COM con Outlook (Dispatch "Outlook.Application")
pyinstaller  — empaquetado a .exe
cryptography — AES-256-GCM + PBKDF2 (inventario encriptado)
pywebview    — WebView2 nativa para la UI
pythonnet    — CLR loader requerido por pywebview en Windows
win32cred    — Windows Credential Vault para passwords
winreg       — Registro de Windows para server settings y profile mapping
```

Local: Python 3.10+ funciona. No hay tests automatizados.

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
