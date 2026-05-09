# SDD — Account Settings Panel v3.1
**Fecha:** 2026-05-09
**Autor:** K. Kaneshiro
**Versión app:** 3.1.0
**Status:** SPEC

---

## 1. Resumen y contexto

La app v3.1 tiene detección de cuentas y export de inventario, pero **no hay forma de ver detalles individuales de cada cuenta** (server settings, tipo, credenciales detectadas) ni de **testear la conexión** IMAP/SMTP sin hacer un backup completo. El usuario necesita poder:

- Ver la lista de cuentas con sus server settings (incoming/outgoing)
- Exportar inventario de una cuenta individual
- Testear conectividad IMAP/SMTP desde la UI
- Editar configuración por cuenta (domain filter, formato default)

---

## 2. Análisis del codebase

### 2.1 APIs existentes relevantes

| Endpoint | Ubicación | Qué hace |
|---|---|---|
| `detect_accounts()` | `api.py:68` | Lista cuentas vía COM con `smtp`, `display_name`, `type`, `matches_domain` |
| `export_inventory()` | `api.py:513` | Exporta inventario completo (todas las cuentas) a JSON. **BUG:** importa `export_inventory_file` y `get_default_inventory_path` que no existen en `account_inventory.py` — la función real es `save_inventory()` |
| `get_config()` / `update_config()` | `api.py:100` | Config global |
| `_read_registry_servers()` | `account_inventory.py:136` | Lee server settings del registry de Outlook |
| `_read_credential_vault()` | `account_inventory.py:259` | Lee passwords del Windows Credential Vault |

### 2.2 BUG en api.py

```python
# api.py:293-295 — función _auto_export_inventory
from account_inventory import (
    build_inventory, export_inventory_file,  # ❌ NO EXISTE
    get_default_inventory_path,                # ❌ NO EXISTE
)

# api.py:515-518 — función export_inventory
from account_inventory import (
    build_inventory, export_inventory_file,    # ❌ NO EXISTE
    get_default_inventory_path,                # ❌ NO EXISTE
)
```

La función real en `account_inventory.py` es `save_inventory(inventory, output_dir, password=None)`.

### 2.3 Frontend actual

- **5 tabs:** backup, restore, history, auto, cache
- **Sin tab "accounts"** — no hay forma de ver cuentas individuales
- El tab "backup" tiene la lista de cuentas pero solo con checkbox, sin details
- No hay connection tester en la UI

### 2.4 Inventario de funciones en account_inventory.py

```
build_inventory(outlook_client, selected_smtp_addresses=None, include_servers=True, include_passwords=False)
save_inventory(inventory: Dict, output_dir: str, password: Optional[str] = None) -> str
summarize_inventory(inventory: Dict) -> str
```

---

## 3. Diseño de la solución

### 3.1 Nueva pestaña "Accounts"

```
┌──────────────────────────────────────────────────────────────┐
│ 📧 アカウント設定                                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Account list — grid de tarjetas]                           │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐          │
│  │ 📧 kenji@uns-kikaku  │  │ 📧 info@uns-kikaku   │          │
│  │ IMAP · 送我用        │  │ Exchange · 社内      │          │
│  │ [詳細] [テスト] [-export]│  │ ...                │          │
│  └──────────────────────┘  └──────────────────────┘          │
│                                                              │
│  ───────────────────────────────────────────────             │
│  全般設定                                                    │
│  Domain Filter: [________________________] [保存]            │
│  Default Format: (•) PST ( ) MSG                            │
│  Default Import Mode: (•) separate ( ) merge ( ) new       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 API methods a agregar en api.py

| Método | Parámetros | Retorna |
|---|---|---|
| `get_account_details()` | `smtp: str` | `{smtp, display_name, type, server_settings, credential_count, matches_domain}` |
| `test_connection()` | `params: Dict` | `{success, latency_ms, error}` — usa `connection_tester.py` |
| `export_account_inventory()` | `smtp: str, include_passwords: bool, master_password: str` | `{success, path}` |

### 3.3 Nuevo módulo: connection_tester.py

Ubicación: `src/connection_tester.py`

Implementa tests de conectividad IMAP y SMTP:

- **IMAP test:** conecta al puerto 993 (IMAPS) o 143 (IMAP), hace `NOOP` o `CAPABILITY`, mide latency
- **SMTP test:** conecta al puerto 465/587, hace `EHLO`, mide latency
- Timeout configurable (default 10s)
- Retry 1 vez en caso de timeout transient
- Detecta si el server responde con banner para diagnosis

### 3.4 Fix de imports en api.py

Reemplazar `export_inventory_file` y `get_default_inventory_path` por `save_inventory` en ambas funciones (`_auto_export_inventory` y `export_inventory`). `save_inventory` toma `(inventory, output_dir, password)` y devuelve el path.

---

## 4. Estructura de datos

### 4.1 Account detail response

```python
{
    "smtp": "kenji@uns-kikaku.com",
    "display_name": "K. Kaneshiro",
    "account_type": "IMAP",
    "matches_domain": True,
    "server_settings": {
        "incoming_server": "mail.uns-kikaku.com",
        "outgoing_server": "smtp.uns-kikaku.com",
        "ports_detected": [
            {"protocol": "imaps", "port": 993},
            {"protocol": "smtp_starttls", "port": 587},
        ],
        "outlook_version": "16.0",
    },
    "credential_count": 2,  # cuántas credenciales matchearon en vault
    "inventory_exportable": True,
}
```

### 4.2 Connection test request

```python
{
    "smtp": "kenji@uns-kikaku.com",  # para auto-detectar server desde registry
    "protocol": "auto",  # o "imap", "smtp"
    "timeout": 10,       # segundos
}
```

### 4.3 Connection test response

```python
{
    "success": True,
    "tests": {
        "imap": {"success": True, "latency_ms": 234, "server_banner": "* OK ..."},
        "smtp": {"success": False, "error": "Connection refused", "port": 587},
    },
    "summary": "IMAP OK · SMTP failed",
}
```

---

## 5. Dependencias y constraints

- `connection_tester.py` usa solo stdlib (`socket`, `ssl`, `time`) — no agregar deps externas
- El tab "Accounts" se agrega como **último tab** (posición 6) después de cache
- Compatibilidad backward: no cambiar firma de funciones existentes
- Tests manuales (no hay test suite automatizada)
- La app ya tiene WebView2, no requiere cambios de runtime

---

## 6. Criterios de aceptación

- [ ] Tab "アカウント設定" aparece como último tab en `index.html`
- [ ] `get_account_details(smtp)` retorna server settings desde registry
- [ ] `test_connection()` prueba IMAP y SMTP y retorna latency
- [ ] `export_account_inventory()` exporta una sola cuenta
- [ ] Bug de imports en `api.py` corregido (usa `save_inventory`)
- [ ] Botón "詳細" abre modal con server settings completos
- [ ] Botón "テスト" abre modal con resultado de connection test
- [ ] Botón "Export" exporta inventario de esa cuenta
- [ ] Sección "全般設定" permite editar domain filter y defaults
- [ ] Se pueden editar settings desde la UI y se persisten en config.json