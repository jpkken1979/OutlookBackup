# 📦 UNS メールバックアップ v2.1

> Aplicación de backup + restore de Outlook para **ユニバーサル企画株式会社 (UNS-Kikaku)**

App de Windows en **japonés** que respalda y restaura correos de Outlook,
y **exporta inventario completo de cuentas** (con passwords encriptados opcional).

---

## ✨ Novedades v2.1 (sobre v2.0)

| Feature | Descripción |
|---|---|
| 📋 **アカウント情報エクスポート** | NEW: Inventario JSON con email + servidor + tipo |
| 🔐 **パスワード暗号化** | NEW: Opcionalmente incluye passwords con AES-256-GCM |
| 🔑 **Master Password** | NEW: Diálogo con strength meter (0-100) |
| 🔓 **JSON復号ビューア** | NEW: Visualizador para JSONs encriptados |
| 📡 **Server detection** | NEW: Lee servidor IMAP/SMTP del registro de Windows |

## ✨ Funcionalidades v2.0

| Feature | Descripción |
|---|---|
| 🇯🇵 **Solo japonés** | UI completamente en japonés con fuente Yu Gothic UI |
| 📤 **バックアップ** | Backup a `.pst` o `.msg` |
| 📥 **復元・インポート** | Restaura `.pst` con 3 modos |
| 🔍 **PSTプレビュー** | Ve el contenido de un `.pst` antes de importarlo |
| 📊 **履歴** | Historial de backups previos con estadísticas |
| ⏰ **自動バックアップ** | Backup automático con Windows Task Scheduler |
| 🧹 **世代管理** | Auto-elimina backups antiguos (mantén últimos N) |
| 🌐 **全アカウント** | Respalda TODAS las cuentas Outlook (no solo @uns-kikaku.com) |

---

## 🔐 Cómo funciona el inventario de cuentas

### Caso 1: Solo inventario (seguro)
Marcas `アカウント情報をJSONにエクスポート` → al final del backup se genera:

```
backup_20260506_143000/
├── kenji_at_uns-kikaku_com.pst
├── info_at_uns-kikaku_com.pst
├── ...
├── accounts.json         ← inventario sin passwords
└── report.html
```

Contenido típico de `accounts.json`:
```json
{
  "format_version": "2.1",
  "exported_at": "2026-05-06T14:30:00",
  "company": "ユニバーサル企画株式会社",
  "host_info": { "computer_name": "PC-KENJI", "user_name": "kenji" },
  "total_accounts": 4,
  "includes_passwords": false,
  "accounts": [
    {
      "smtp_address": "kenji@uns-kikaku.com",
      "display_name": "金城 賢士",
      "user_name": "kenji@uns-kikaku.com",
      "account_type": "IMAP",
      "delivery_store": "kenji@uns-kikaku.com",
      "server_settings": {
        "incoming_server": "mail.hostbig.com",
        "outgoing_server": "smtp.hostbig.com",
        "ports_detected": [
          {"protocol": "imaps", "port": 993},
          {"protocol": "smtps", "port": 465}
        ]
      }
    }
  ]
}
```

### Caso 2: Inventario + passwords encriptados
Marcas también `🔐 パスワードも含める` → te pide master password con confirmación + strength meter → se genera:

```
backup_20260506_143000/
├── ...
├── accounts.json.enc     ← AES-256-GCM con tu master password
└── report.html
```

**Estructura del archivo encriptado:**
```
[MAGIC "UNSCRYPT"][version 1][PBKDF2 iterations 200K][salt 16B][nonce 12B][AES-GCM ciphertext][auth tag]
```

Para verlo después, en la pestaña **復元・インポート**:
- Click `🔓 アカウント情報を復号`
- Seleccionas el `.json.enc`
- Pones la master password
- Ves los datos en una tabla, con toggle para mostrar/ocultar passwords
- Opcionalmente exportas a JSON plano (con warning)

---

## 🚀 Cómo conseguir el `.exe`

### Opción A: GitHub Actions (recomendada — 3 minutos)

```bash
git init
git add .
git commit -m "v2.1.0"
git remote add origin https://github.com/TU-USER/uns-outlook-backup.git
git push -u origin main
git tag v2.1.0
git push origin v2.1.0
```

Espera al workflow → descarga desde **Actions → Artifacts**.

### Opción B: Compilar localmente

Requisitos: Python 3.10+ y opcionalmente Inno Setup 6.

```cmd
build.bat
```

Resultado en `dist/`:
- `UNS-Outlook-Backup.exe` — ejecutable portable (~30 MB con cryptography)
- `UNS-Outlook-Backup-Setup-2.1.0.exe` — instalador profesional

### Opción C: Probar sin compilar

```cmd
run.bat
```

---

## 📁 Estructura del proyecto v2.1

```
uns-backup-app/
├── src/
│   ├── main.py
│   ├── i18n.py
│   ├── config.py
│   ├── crypto_utils.py          # NEW v2.1
│   ├── account_inventory.py     # NEW v2.1
│   ├── outlook_client.py
│   ├── backup_engine.py
│   ├── import_engine.py
│   ├── pst_inspector.py
│   ├── history_manager.py
│   ├── scheduler.py
│   └── gui/
│       ├── theme.py
│       ├── app.py
│       ├── tab_backup.py
│       ├── tab_restore.py       # con decrypt viewer
│       ├── tab_history.py
│       ├── tab_settings.py
│       └── password_dialog.py   # NEW v2.1
├── assets/...
├── build/...
├── docs/INSTRUCCIONES.md
├── .github/workflows/build.yml
├── requirements.txt             # ahora incluye cryptography
├── build.bat / run.bat
└── README.md
```

---

## 🔧 Tecnologías nuevas v2.1

- **cryptography 42+** — AES-256-GCM con PBKDF2-HMAC-SHA256 (200K iteraciones)
- **win32cred** — Lectura de Windows Credential Vault
- **winreg** — Lectura del registro de Windows para settings de Outlook

---

## 🛡️ Seguridad

### Inventario sin passwords (seguro)
- Email, nombre, tipo de cuenta, servidor → datos no sensibles
- JSON plano legible

### Inventario con passwords (sensible)
- AES-256-GCM (algoritmo aprobado por NIST)
- Master password derivada con PBKDF2 (200,000 iteraciones)
- Salt aleatorio único por archivo (16 bytes)
- Nonce aleatorio único por archivo (12 bytes)
- Auth tag previene modificación

**Reglas de oro:**
1. Master password fuerte (16+ caracteres con símbolos)
2. NO compartir el .json.enc por email/Slack/etc.
3. NO guardar el .json.enc junto al master password
4. Borrar el .json.enc cuando ya no lo necesites

---

## 📞 Soporte

Cualquier duda contacta al administrador de sistemas de UNS.

---

**ユニバーサル企画株式会社**
〒461-0025 愛知県名古屋市東区徳川2丁目18番18号
TEL: 052-938-8840 · FAX: 052-938-8841

---

## 🎯 Las 4 pestañas

### 1️⃣ 📤 バックアップ
Detecta cuentas Outlook → filtra por dominio (o todas) → exporta a `.pst`/`.msg` → genera reporte HTML.

### 2️⃣ 📥 復元・インポート
Busca PST en una carpeta → muestra lista con tamaño/fecha → importa con uno de 3 modos:

- **別フォルダとして開く** (default) — el PST aparece como carpeta separada en Outlook
- **既存のアカウントに統合** — mergea contenido al Inbox de la cuenta seleccionada
- **各PSTを別データファイルに** — cada PST como data file independiente

Bonus: botón **🔍 PSTの中身をプレビュー** para inspeccionar el `.pst` sin importarlo.

### 3️⃣ 📊 履歴
Lista todos los backups previos, ordenados por fecha. Click → ver reporte / abrir carpeta / borrar.

### 4️⃣ ⏰ 自動バックアップ
Configura backup automático:
- **Frecuencia:** diario / semanal / quincenal / mensual / cada N días
- **Día y hora** específicos
- **Carpeta destino**
- **Cuentas:** solo `@uns-kikaku.com` o todas
- **Retención:** mantener últimos N backups

Crea una tarea programada de Windows que ejecuta `UNS-Outlook-Backup.exe --auto` en background.

---

## 🚀 Cómo conseguir el `.exe`

### Opción A: GitHub Actions (recomendada — 3 minutos)

1. Sube el ZIP a GitHub
2. Espera a que termine el workflow `Build Windows Installer`
3. Descarga el `.exe` desde **Actions → Artifacts**

### Opción B: Compilar localmente

Requisitos: Python 3.10+ y opcionalmente Inno Setup 6.

```cmd
build.bat
```

Resultado en `dist/`:
- `UNS-Outlook-Backup.exe` — ejecutable portable (~25 MB)
- `UNS-Outlook-Backup-Setup-2.0.0.exe` — instalador profesional

### Opción C: Probar sin compilar

```cmd
run.bat
```

---

## 📁 Estructura del proyecto

```
uns-backup-app/
├── src/
│   ├── main.py              # Entry + --auto mode
│   ├── i18n.py              # Strings japonés (128 strings)
│   ├── config.py            # Config persistente (%APPDATA%)
│   ├── outlook_client.py    # COM Outlook
│   ├── backup_engine.py     # Motor de backup
│   ├── import_engine.py     # NEW Motor de import (3 modos)
│   ├── pst_inspector.py     # NEW Vista previa de PST
│   ├── history_manager.py   # NEW Historial
│   ├── scheduler.py         # NEW Task Scheduler
│   └── gui/
│       ├── theme.py         # Branding UNS + widgets
│       ├── app.py           # Ventana principal con tabs
│       ├── tab_backup.py    # Tab バックアップ
│       ├── tab_restore.py   # Tab 復元・インポート
│       ├── tab_history.py   # Tab 履歴
│       └── tab_settings.py  # Tab 自動バックアップ
├── assets/
│   ├── icon.ico             # Icono multi-resolución
│   └── icon.png
├── build/
│   ├── pyinstaller.spec
│   ├── installer.iss        # Inno Setup
│   ├── version_info.txt
│   └── generate_icon.py
├── .github/workflows/
│   └── build.yml            # CI/CD
├── docs/
│   └── INSTRUCCIONES.md     # Manual técnico
├── requirements.txt
├── build.bat
├── run.bat
└── README.md
```

---

## 🔧 Tecnologías

- **Python 3.11** + **tkinter** (GUI nativa Windows)
- **pywin32** — automatización Outlook vía COM
- **PyInstaller 6** — empaquetado a `.exe`
- **Inno Setup 6** — instalador profesional
- **schtasks.exe** — built-in de Windows para programar tareas
- **Pillow** — generación del icono

---

## 🛡️ Privacidad y seguridad

- **100% local** — sin servidores externos
- **Sin telemetría**
- **Solo lectura** de Outlook (no modifica originales)
- **Sin permisos de admin** requeridos
- **Config en %APPDATA%** — accesible solo al usuario

---

## 📞 Soporte

Cualquier duda contacta al administrador de sistemas de UNS.

---

**ユニバーサル企画株式会社**
〒461-0025 愛知県名古屋市東区徳川2丁目18番18号
TEL: 052-938-8840 · FAX: 052-938-8841
[uns-kikaku.com](https://www.uns-kikaku.com)
