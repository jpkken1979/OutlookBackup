---
name: PyInstaller resuelve paths del .spec relativos al directorio del spec
description: Gotcha de PyInstaller que rompe builds en CI cuando el spec esta en subcarpeta
type: project
auto_saved: true
trigger: discovery
date: 2026-05-08
---

## Gotcha
Cuando ejecutas `pyinstaller build/pyinstaller.spec` desde la raiz del repo,
PyInstaller resuelve los paths internos del spec **relativos al directorio del spec**
(`build/`), NO relativos al CWD donde corres el comando.

Esto significa que un `Analysis(['src/main.py'])` en `build/pyinstaller.spec` se intenta
resolver como `build/src/main.py` y falla con `script ... not found`.

## Donde se vio
Build #1 de `jpkken1979/OutlookBackup` (commit `2f8bcbf`) en GitHub Actions:
```
script 'D:\a\OutlookBackup\OutlookBackup\build\src\main.py' not found
```

## Solucion correcta
Usar la variable `SPECPATH` que PyInstaller inyecta al ejecutar el spec — es el directorio
absoluto donde esta el .spec. Calcular paths desde ahi:

```python
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# SPECPATH es inyectada por PyInstaller, apunta al dir del .spec
ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

datas = [
    (os.path.join(ROOT, 'src', 'web'), 'web'),
    (os.path.join(ROOT, 'assets', '*.ico'), 'assets'),
]

a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[os.path.join(ROOT, 'src')],
    ...
)

exe = EXE(
    ...
    icon=os.path.join(ROOT, 'assets', 'icon.ico'),
    version=os.path.join(ROOT, 'build', 'version_info.txt'),
)
```

## Implicaciones
- Aplica a TODOS los paths del spec: `Analysis(scripts)`, `pathex`, `datas`, `binaries`,
  `EXE(icon)`, `EXE(version)`.
- Tambien aplica a `Inno Setup .iss` PERO ahi los paths con `..\` SI funcionan porque
  Inno Setup resuelve relativos al .iss explicitamente.
- Si el spec esta en la raiz del repo, el problema no se manifiesta porque ROOT == SPECPATH.

## Como prevenir
- Siempre usar `os.path.join(SPECPATH, ...)` en specs ubicados en subcarpetas.
- Validar el spec localmente con `pyinstaller --noconfirm <spec>` antes de pushear a CI,
  o como minimo con `python -c "import ast; ast.parse(open(...).read())"` para sintaxis.
