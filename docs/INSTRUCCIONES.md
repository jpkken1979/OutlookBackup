# 📋 INSTRUCCIONES — UNS メールバックアップ v2.0

> Manual técnico para Kenji · ユニバーサル企画株式会社

---

## ⚡ Lo que cambió desde v1.0

| | v1.0 | v2.0 |
|---|---|---|
| Idioma | Español | **Japonés** |
| Tabs | Solo backup | **4 tabs** (backup, restore, history, scheduler) |
| Import PST | ❌ | ✅ 3 modos |
| Vista previa PST | ❌ | ✅ |
| Historial | ❌ | ✅ |
| Auto-backup | ❌ | ✅ Task Scheduler |
| Retención automática | ❌ | ✅ |
| Modo CLI | ❌ | ✅ `--auto` |

---

## 🚀 Cómo obtener el .exe

### A. GitHub Actions (3 min, sin instalar nada)

```bash
git init
git add .
git commit -m "v2.0"
git remote add origin https://github.com/TU-USER/uns-outlook-backup.git
git push -u origin main
```

Espera el workflow → descarga desde **Actions → Artifacts**.

Para release oficial:
```bash
git tag v2.0.0
git push origin v2.0.0
```

### B. Compilar local

```cmd
build.bat
```

Necesita: Python 3.10+ y opcionalmente Inno Setup 6.

### C. Solo probar (dev mode)

```cmd
run.bat
```

---

## 🏗️ Arquitectura

```
[GUI tkinter con tabs]
        ↓
   gui/app.py (root)
   ├── tab_backup.py
   ├── tab_restore.py
   ├── tab_history.py
   └── tab_settings.py
        ↓
[Backend modules]
   ├── outlook_client.py    (COM)
   ├── backup_engine.py     (export to PST)
   ├── import_engine.py     (import PST, 3 modos)
   ├── pst_inspector.py     (preview PST)
   ├── history_manager.py   (lista report.json)
   ├── scheduler.py         (schtasks.exe)
   ├── config.py            (%APPDATA%/config.json)
   └── i18n.py              (strings JP)
```

---

## 🔁 Flujo del modo `--auto`

Cuando Windows Task Scheduler ejecuta `UNS-Outlook-Backup.exe --auto`:

1. Lee `%APPDATA%\UNS-Kikaku\Backup\config.json`
2. Conecta a Outlook (lo abre si está cerrado)
3. Filtra cuentas según `schedule_scope`:
   - `uns_only` → solo `@uns-kikaku.com`
   - `all` → todas las cuentas
   - `custom` → solo las en lista guardada
4. Crea backup en `schedule_save_to`
5. Si `schedule_keep_last > 0`, borra backups antiguos
6. Logs a `%APPDATA%\UNS-Kikaku\Backup\auto.log`

---

## 🛠️ Personalización

### Cambiar strings japoneses

Edita `src/i18n.py` — diccionario `JA`. Todos los textos visibles están ahí.

### Agregar idiomas

Crea `EN = {...}` con los mismos keys, ajusta función `t()` para tomar un parámetro de idioma. Las labels se actualizan al recompilar.

### Cambiar colores

Edita `src/gui/theme.py`:
```python
UNS_NAVY = "#0052CC"  # cambia aquí
```

### Cambiar formato de PST

Edita `src/outlook_client.py`, función `export_account_to_pst`. La constante `3 = olStoreUnicode`. Otros valores:
- `1` = ANSI (compatibilidad antigua)
- `3` = Unicode (recomendado, soporta archivos > 2GB)

---

## 🐛 Troubleshooting

### "schtasks: アクセスが拒否されました"

El usuario no tiene permisos para crear tareas. Soluciones:
- Ejecutar la app como admin
- O dar permisos al grupo "Users" sobre `\Tasks` en regedit

### "PSTファイルが見つかりません"

La búsqueda recursiva no encuentra archivos. Verifica:
- El path tiene `.pst` (no `.ost`, que es solo cache)
- Los archivos no están en una carpeta protegida

### Auto-backup no se ejecuta

```cmd
schtasks /Query /TN "UNS-Outlook-Backup-Auto" /V
```

Si aparece "Last Result: 0x1" → revisa `%APPDATA%\UNS-Kikaku\Backup\auto.log`.
Errores típicos:
- Outlook no abre en sesión no-interactiva → marcar tarea como "Run only when user is logged on"
- pywin32 corrupto → reinstalar la app

### El `.pst` queda corrupto al importar

Pasa a veces si Outlook está ocupado. Solución:
- Cerrar Outlook
- Mover el `.pst` a `%LOCALAPPDATA%\Microsoft\Outlook\`
- Abrir Outlook → File → Open & Export → manual

---

## 🔐 Code signing (opcional, ~$200/año)

Sin firmar, el SmartScreen de Windows mostrará "Editor desconocido" en el primer arranque. Para evitarlo:

1. Comprar certificado de Code Signing (Sectigo, DigiCert)
2. Firmar con `signtool`:

```cmd
signtool sign /f cert.pfx /p PASSWORD /t http://timestamp.digicert.com /fd SHA256 dist\UNS-Outlook-Backup.exe
```

Para empleados internos no es necesario.

---

## 🚢 Distribución

### Email interno
Adjunta `UNS-Outlook-Backup-Setup-2.0.0.exe` con instrucciones cortas.

### VPS Hostinger
Subir a `https://backup.uns-kikaku.cloud/UNS-Outlook-Backup.exe` (aprovechando Dokploy).

### Network share
`\\server\public\UNS-Tools\UNS-Outlook-Backup-Setup-2.0.0.exe`

---

## 🔮 Roadmap futuro

Cosas que se pueden agregar después:

| Feature | Esfuerzo | Valor |
|---|---|---|
| Encriptar PST con contraseña | Medio | Alto si hay datos sensibles |
| Filtrar por fecha al backup | Bajo | Medio |
| Subir backup a Google Drive/S3 | Medio | Alto |
| Dashboard web de todos los empleados | Alto | Alto para admin |
| Notificación LINE al terminar | Bajo | Bajo |
| Backup incremental | Alto | Alto si correos pesan mucho |
| Versión Mac | Alto | Solo si tienen empleados con Mac |

Cualquiera la implementamos cuando la necesites.

---

ユニバーサル企画株式会社 · UNS-Kikaku
〒461-0025 愛知県名古屋市東区徳川2丁目18番18号
