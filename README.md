# 📦 UNS メールバックアップ v3.1

> Aplicación de backup + restore de Outlook para **ユニバーサル企画株式会社 (UNS-Kikaku)**

App Windows en **japonés** que respalda y restaura correos de Outlook,
y **exporta inventario completo de cuentas** (con passwords encriptados opcional).

---

## ✨ Novedades v3.1

| Feature | Descripción |
|---|---|
| 💾 **キャッシュバックアップ** | Backup directo de archivos OST/PST del disco. Funciona aunque el servidor IMAP/Exchange esté muerto |
| 🔍 **Cache scanner** | Escanea automáticamente `%LOCALAPPDATA%\Microsoft\Outlook` y detecta archivos de caché |
| 🔐 **Integrity check** | SHA256 verify después de copiar archivos de caché |

## ✨ Novedades v3.0

| Feature | Descripción |
|---|---|
| 🌐 **WebView2 UI** | Interfaz moderna con HTML/CSS/JS dentro de Edge Chromium nativo |
| 📊 **Report HTML** | Reportes visuales con branding UNS después de cada backup |
| 🔄 **Progress real-time** | Barra de progreso y log en vivo durante operaciones |

## ✨ Funcionalidades

| Feature | Descripción |
|---|---|
| 🇯🇵 **Solo japonés** | UI completamente en japonés con fuente Yu Gothic UI |
| 📤 **バックアップ** | Backup a `.pst` o `.msg` vía COM de Outlook |
| 💾 **キャッシュバックアップ** | Copia directa de OST/PST — funciona offline sin servidor |
| 📥 **復元・インポート** | Restaura `.pst` con 3 modos |
| 🔍 **PSTプレビュー** | Ve el contenido de un `.pst` antes de importarlo |
| 📊 **履歴** | Historial de backups previos con estadísticas |
| ⏰ **自動バックアップ** | Backup automático con Windows Task Scheduler |
| 🧹 **世代管理** | Auto-elimina backups antiguos (mantén últimos N) |
| 🌐 **全アカウント** | Respalda TODAS las cuentas Outlook (no solo @uns-kikaku.com) |
| 📋 **アカウント情報エクスポート** | Inventario JSON con email + servidor + tipo |
| 🔐 **パスワード暗号化** | Opcionalmente incluye passwords con AES-256-GCM |

---

## 📁 Estructura del proyecto v3.1

```
uns-backup-app/
├── src/
│   ├── main.py              # Entry point (pywebview GUI + --auto mode)
│   ├── api.py               # Bridge Python ↔ JavaScript
│   ├── web/                 # Frontend (WebView2)
│   │   ├── index.html
│   │   ├── css/styles.css
│   │   └── js/app.js       # Lógica UI, polling, modales
│   ├── outlook_client.py    # COM con Outlook (pywin32)
│   ├── backup_engine.py     # Backup multi-cuenta + reportes HTML
│   ├── cache_backup.py     # Copia directa OST/PST del disco
│   ├── import_engine.py    # Restore PST (3 modos)
│   ├── pst_inspector.py    # Preview de PST sin importar
│   ├── history_manager.py  # Historial de backups
│   ├── scheduler.py        # Windows Task Scheduler (schtasks.exe)
│   ├── account_inventory.py # Inventario de cuentas
│   ├── crypto_utils.py     # AES-256-GCM + PBKDF2
│   ├── config.py           # Config persistente
│   └── i18n.py            # Strings en japonés
├── assets/icon.ico
├── build/
│   ├── pyinstaller.spec    # PyInstaller config
│   ├── installer.iss       # Inno Setup
│   └── version_info.txt
├── .github/workflows/build.yml
├── requirements.txt
├── build.bat / run.bat
└── README.md
```

---

## 🔐 Inventario de cuentas encriptadas

### Caso 1: Solo inventario (seguro)

```
backup_20260506_143000/
├── kenji_at_uns-kikaku_com.pst
├── info_at_uns-kikaku_com.pst
├── report.html
├── report.json
└── accounts.json          ← inventario sin passwords
```

### Caso 2: Inventario + passwords encriptados

Marcás `🔐 パスワードも含める` → te pide master password → genera:

```
accounts.json.enc           ← AES-256-GCM con tu master password
```

**Estructura del archivo:**
```
[MAGIC "UNSCRYPT"][version 1][PBKDF2 iterations 200K][salt 16B][nonce 12B][AES-GCM ciphertext][auth tag]
```

---

## 🚀 Cómo conseguir el `.exe`

### Opción A: GitHub Actions (recomendada — 3 minutos)

```bash
git tag v3.1.0 && git push origin v3.1.0
```

Espera al workflow → descarga desde **Actions → Artifacts**.

### Opción B: Compilar localmente

Requisitos: Python 3.10+ y opcionalmente Inno Setup 6.

```cmd
build.bat
```

Resultado en `dist/`:
- `UNS-Outlook-Backup.exe` — ejecutable portable (~30 MB con cryptography)
- `UNS-Outlook-Backup-Setup-3.1.0.exe` — instalador profesional

### Opción C: Probar sin compilar

```cmd
run.bat
```

---

## 🎯 Las pestañas

### 📤 バックアップ
Detecta cuentas Outlook → filtra por dominio (o todas) → exporta a `.pst`/`.msg` → genera reporte HTML.

### 💾 キャッシュバックアップ
Escanea archivos OST/PST en `%LOCALAPPDATA%\Microsoft\Outlook` → copia directa al destino → SHA256 verify.

Útil cuando el servidor IMAP/Exchange está muerto.

### 📥 復元・インポート
Busca PST en una carpeta → muestra lista con tamaño/fecha → importa con uno de 3 modos:

- **別フォルダとして開く** (default) — el PST aparece como carpeta separada en Outlook
- **既存のアカウントに統合** — mergea contenido al Inbox de la cuenta seleccionada
- **各PSTを別データファイルに** — cada PST como data file independiente

Bonus: botón **🔍 PSTの中身をプレビュー** para inspeccionar el `.pst` sin importarlo.

### 📊 履歴
Lista todos los backups previos, ordenados por fecha. Click → ver reporte / abrir carpeta / borrar.

### ⏰ 自動バックアップ
Configura backup automático:
- **Frecuencia:** diario / semanal / quincenal / mensual / cada N días
- **Día y hora** específicos
- **Carpeta destino**
- **Cuentas:** solo `@uns-kikaku.com` o todas
- **Retención:** mantener últimos N backups

---

## 🔧 Tecnologías

- **Python 3.11** + **pywebview** (WebView2 / Edge Chromium nativo)
- **pywin32** — automatización Outlook vía COM
- **PyInstaller 6** — empaquetado a `.exe`
- **Inno Setup 6** — instalador profesional
- **schtasks.exe** — built-in de Windows para programar tareas
- **cryptography** — AES-256-GCM con PBKDF2-HMAC-SHA256 (200K iteraciones)
- **win32cred** — Windows Credential Vault para passwords
- **winreg** — Registro de Windows para server settings

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
