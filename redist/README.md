# `redist/` — Binarios redistribuidos en el installer

Este directorio contiene binarios de terceros que el installer Inno Setup
bundlea con el `.exe` de UNS Outlook Backup pero que **NO se commitean al
repositorio** (estan ignorados via `*.exe` en `.gitignore`).

Antes de compilar el installer (`build.bat` / `iscc.exe build/installer.iss`),
descargar los binarios listados abajo en este directorio.

## Archivos requeridos

### `MicrosoftEdgeWebview2Setup.exe`

Bootstrapper evergreen del runtime WebView2 (~1.7MB). Internamente descarga el
runtime completo (~150MB) durante la instalacion si hace falta.

**Descargar antes del build:**

```powershell
# PowerShell
Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile "redist/MicrosoftEdgeWebview2Setup.exe"
```

```bash
# Bash (Git Bash / WSL)
curl -L -o redist/MicrosoftEdgeWebview2Setup.exe "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
```

**Por que no esta en git:**
- Microsoft actualiza el bootstrapper periodicamente
- `*.exe` en `.gitignore` global (regla de seguridad del proyecto)
- Tamano (~1.7MB) no critico, pero versionar binarios es mala practica

**Por que el installer lo bundlea (decision aprobada 2026-05-13):**
- Win 10 < 22H2 viene sin WebView2; la app abriria ventana en blanco
- Bundlearlo elimina la friccion del primer run
- Inno Setup [Code] section verifica registry antes de ejecutarlo (no se corre
  si ya esta instalado)
- Ver `build/installer.iss` seccion `[Files]` + `[Code]`
- Ver `src/runtime_check.py` para la deteccion en runtime de la app

## Si falta el bootstrapper al compilar

`ISCC.exe` va a fallar con: `File not found: redist\MicrosoftEdgeWebview2Setup.exe`.

Solucion: ejecutar el comando `curl`/`Invoke-WebRequest` de arriba.

## En CI (GitHub Actions)

El workflow `build.yml` debe descargar el bootstrapper antes de ejecutar
`iscc.exe`. Pendiente de implementacion (Fase 2 entrega el bundling local;
el wire-up en CI puede ser un siguiente paso menor).
