"""Pytest fixtures globales.

CRITICO: el fixture `mock_win32_modules` corre con autouse=True y SE EJECUTA
ANTES de cualquier import del codigo bajo test. Esto inyecta MagicMocks en
sys.modules para win32com, win32cred, winreg, pythoncom y webview — de modo
que los modulos de src/ pueden importarse en Linux sin pywin32 instalado.

Si necesitas la implementacion real en un test (ej: integration test en
Windows con Outlook), usa pytestmark = pytest.mark.windows en ese archivo
y skipea via el marker.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

WIN32_MODULES = [
    "win32com",
    "win32com.client",
    "win32com.gen_py",
    "win32cred",
    "winreg",
    "pythoncom",
    "pywintypes",
    "webview",
]


@pytest.fixture(autouse=True, scope="session")
def mock_win32_modules() -> Iterator[None]:
    """Inyecta MagicMocks en sys.modules ANTES de cualquier import de src/.

    Esto permite que tests corran en Linux (CI) sin pywin32 instalado.
    En Windows, el mock sigue activo — los tests usan fakes explicitos via
    fixtures, no la libreria real.
    """
    originals = {name: sys.modules.get(name) for name in WIN32_MODULES}
    for name in WIN32_MODULES:
        sys.modules[name] = MagicMock(name=name)
    yield
    # Restaurar al final de la sesion
    for name, mod in originals.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


@pytest.fixture
def fake_outlook_namespace() -> MagicMock:
    """Namespace COM mockeado con la API minima que usan los engines.

    Expandir conforme los engines necesiten mas metodos. Ver Fase 2 del plan
    para reemplazar esto con un fake tipado en src/outlook/fakes.py.
    """
    namespace = MagicMock(name="Namespace")
    namespace.Accounts = []
    namespace.Folders = []
    namespace.Stores = []
    return namespace


@pytest.fixture
def tmp_appdata(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Sobrescribe APPDATA para que config.py escriba en tmp_path.

    Usar en cualquier test que toque config persistente.
    """
    appdata = tmp_path / "AppData" / "Roaming"
    appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata))
    return appdata
