# Regla: PATH de Node.js / npx en Windows desde Claude Code

Aplica a todos los scripts del repositorio que invoquen `npx`, `node`, o
binarios instalados via `npm install -g` cuando se ejecutan desde una
sesion de Claude Code en Windows.

## Sintoma

Comandos como:

```bash
where npx        # bash: no encuentra nada
```

```powershell
Get-Command npx  # PowerShell: tampoco
```

devuelven vacio aunque Node este instalado en el sistema. Lo mismo le
pasa a `shutil.which("npx")` desde Python — devuelve `None`.

## Root cause

Claude Code en Windows hereda un PATH minimal en el process del shell.
El PATH a nivel **Machine** (que SI contiene `C:\Program Files\nodejs\`)
no se propaga al process del shell de la sesion:

```powershell
# Machine SI lo tiene
[System.Environment]::GetEnvironmentVariable('PATH','Machine') -split ';' | Where-Object { $_ -match 'node' }
# C:\Program Files\nodejs\

# Process NO lo tiene
$env:PATH -split ';' | Where-Object { $_ -match 'node' }
# (vacio)
```

Esto rompe cualquier script que dependa de resolver `npx` por PATH.

## Workaround

Hay 3 niveles, de mas barato a mas robusto:

### 1. Inline en sesion (ad-hoc)

```powershell
$env:PATH = "C:\Program Files\nodejs;$env:PATH"; npx skills find "<query>"
```

```bash
export PATH="/c/Program Files/nodejs:$PATH" && npx skills find "<query>"
```

### 2. En scripts Python (recomendado)

Usar un helper que haga fallback a ubicaciones conocidas de Windows si
`shutil.which` falla. Patron canonico (ver `.agent/scripts/compare_skills.py`):

```python
def _resolve_npx() -> str | None:
    """Locate npx across platforms with Windows fallbacks."""
    npx_path = shutil.which("npx")
    if npx_path:
        return npx_path
    if sys.platform == "win32":
        candidates = [
            Path(r"C:\Program Files\nodejs\npx.cmd"),
            Path(r"C:\Program Files\nodejs\npx"),
            Path(r"C:\Program Files (x86)\nodejs\npx.cmd"),
            Path(os.environ.get("APPDATA", "")) / "npm" / "npx.cmd",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "npx.cmd",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None
```

### 3. Fix permanente del entorno

Si te molesta cada vez, podes setear el PATH a nivel **User** (asi se
hereda en cualquier shell nuevo, incluido el de Claude Code):

```powershell
[System.Environment]::SetEnvironmentVariable(
    "PATH",
    "C:\Program Files\nodejs;" + [System.Environment]::GetEnvironmentVariable('PATH','User'),
    "User"
)
```

Reiniciar Claude Code despues.

## Otros binarios afectados

El mismo problema aplica a cualquier binario que viva en `C:\Program Files\nodejs\`:

- `npm`, `npx`, `node`
- Todo lo instalado via `npm install -g <pkg>` (vive en `%APPDATA%\npm\`)
- En menor medida, herramientas tipo `gh.exe` instaladas en `C:\Program Files\GitHub CLI\`

El `_resolve_npx()` se puede generalizar a `_resolve_node_bin(name)` si
hace falta.

## Cuando NO aplicar el workaround

- Si el script corre via `pre-commit`, GitHub Actions, o cualquier
  entorno no-Claude-Code: el PATH normalmente esta intacto, no hace
  falta el fallback (aunque tampoco molesta).
- Si Node fue instalado via `nvm-windows`, `volta`, o `fnm`: el
  binario vive en otra ruta. Ajustar candidates en `_resolve_npx`.

## Discovery

Detectado el 2026-05-17 mientras se corria `compare_skills.py` desde
Claude Code: el script fallaba silencioso devolviendo 0 remote skills,
porque `shutil.which("npx")` devolvia None aunque Node estaba instalado
y funcionando perfectamente en otros contextos.

Fix aplicado en `.agent/scripts/compare_skills.py` via helper
`_resolve_npx()`.
