# Plan — Account Settings Panel v3.1
**Spec:** `docs/superpowers/specs/2026-05-09-account-settings-design.md`
**Fecha:** 2026-05-09

## Tareas (en orden de dependencia)

### Tarea 1: Fix imports en api.py
**Archivos:** `src/api.py`
**Descripción:** Corregir las líneas 293-295 y 515-518 que importan `export_inventory_file` y `get_default_inventory_path` (no existen). Reemplazar por `save_inventory` que es la función real en `account_inventory.py`.
**Verificación:** `python -c "from src.api import API; print('OK')"`

### Tarea 2: Crear connection_tester.py
**Archivos:** `src/connection_tester.py` (nuevo)
**Descripción:** Módulo de test de conectividad IMAP/SMTP con socket + ssl. Funciones:
- `test_imap_connection(host, port, timeout=10)` → `{success, latency_ms, server_banner}`
- `test_smtp_connection(host, port, timeout=10)` → `{success, latency_ms, server_banner, error}`
- `test_account_connection(smtp, protocol='auto', timeout=10)` → usa registry para auto-detectar servers, prueba ambos
- Solo stdlib (`socket`, `ssl`, `time`) — sin dependencias externas
**Verificación:** `python -c "from src.connection_tester import test_account_connection; print('OK')"`

### Tarea 3: Agregar API methods en api.py
**Archivos:** `src/api.py`
**Descripción:** Agregar 3 métodos públicos:
- `get_account_details(smtp: str)` → busca server settings en registry, cuenta credenciales
- `test_connection(params: Dict)` → llama a `connection_tester.test_account_connection`
- `export_account_inventory(params: Dict)` → exporta una sola cuenta (reusa `build_inventory` + `save_inventory`)
**Verificación:** `python -c "from src.api import API; a=API(); print(hasattr(a,'get_account_details'), hasattr(a,'test_connection'), hasattr(a,'export_account_inventory'))"`

### Tarea 4: Agregar tab "アカウント設定" en index.html
**Archivos:** `src/web/index.html`
**Descripción:** Agregar el tab 6 con:
- Sección "アカウント一覧" — grid de tarjetas de cuentas con botones [詳細] [テスト] [Export]
- Sección "全般設定" — domain filter, default format, default import mode
- Modal de detalles de cuenta (server settings completos)
- Modal de resultado de connection test
**Verificación:** Archivo HTML válido, sin syntax errors

### Tarea 5: Binding JS en app.js
**Archivos:** `src/web/js/app.js`
**Descripción:** Agregar al App:
- `bindAccountSettings()` — bindea todos los botones del nuevo tab
- `loadAccountDetails()` — llama `get_account_details()` por cuenta
- `renderAccountCards()` — renderiza grid de cuentas con acciones
- `openAccountDetail(smtp)` — modal con server settings
- `testAccountConnection(smtp)` — modal con resultado del test
- `exportSingleAccount(smtp)` — llama `export_account_inventory()`
- Secciones editables de settings con `persistConfig()`
**Verificación:** `node -e "require('fs').readFileSync('src/web/js/app.js','utf8')" && echo OK`

### Tarea 6: Actualizar pyinstaller.spec
**Archivos:** `build/pyinstaller.spec`
**Descripción:** Agregar `src/connection_tester.py` a la lista de `hiddenimports` (línea ~15)
**Verificación:** `grep -c "connection_tester" build/pyinstaller.spec` → 1

### Tarea 7: Verificación final manual
**Descripción:** Ejecutar `run.bat` y verificar:
- Tab "アカウント設定" visible como último tab
- Al hacer click en una cuenta: modal con server settings
- Al hacer click en "テスト": modal con resultado IMAP/SMTP
- Al hacer click en "Export": genera archivo accounts.json
- Los settings de "全般設定" se persisten en config.json