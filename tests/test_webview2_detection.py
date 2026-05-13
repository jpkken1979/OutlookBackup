"""Tests del flujo de deteccion del runtime WebView2.

Fase 1 del plan v3.2 (docs/PLAN_HARDENING_WIN10_11.md):
- Documenta el comportamiento ACTUAL (no hay deteccion — la app abre en blanco
  en Win 10 < 22H2 que viene sin WebView2).
- Marca con xfail los tests del nuevo `src/runtime_check.py` que Fase 2 va a crear.

Por que importa para UNS-Kikaku:
- Win 10 22H2+ trae WebView2 preinstalado, pero anteriores NO.
- Algunos clientes UNS estan en Win 10 21H2 (PCs viejas) — la app de v3.1.1
  abre ventana en blanco sin error visible. Diagnostico imposible para usuario.
- Fase 2 + bundle en installer (decision aprobada 2026-05-13) elimina la friccion.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.webview2


# Registry path canonico de Microsoft para deteccion del runtime WebView2.
# Fuente: https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
WEBVIEW2_REG_PATH = (
    r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
    r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
)


# ---------------------------------------------------------------------------
# Documentacion del estado ACTUAL (no es un test xfail — es factual)
# ---------------------------------------------------------------------------


def test_main_module_has_no_webview2_check_currently() -> None:
    """Documenta que main.py NO importa el modulo runtime_check de Fase 2.

    Este test va a fallar cuando Fase 2 implemente la deteccion. En ese momento
    se debe BORRAR este test y hacer pasar los xfail de abajo.

    Nota: solo chequeamos los identificadores de Fase 2 (`ensure_webview2_runtime`,
    `runtime_check`). NO chequeamos "WebView2" en mayusculas porque main.py ya
    menciona "WebView2" en el docstring del header (es la libreria que usa).
    """
    from pathlib import Path

    main_path = Path(__file__).parent.parent / "src" / "main.py"
    content = main_path.read_text(encoding="utf-8")

    has_runtime_check_import = (
        "ensure_webview2_runtime" in content
        or "from runtime_check" in content
        or "import runtime_check" in content
    )
    assert not has_runtime_check_import, (
        "main.py ya importa runtime_check — borrar este test y habilitar xfail de Fase 2"
    )


# ---------------------------------------------------------------------------
# Tests xfail — comportamiento que Fase 2 debe implementar
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Fase 2 del plan v3.2: src/runtime_check.py debe existir",
    strict=False,
)
def test_runtime_check_module_exists() -> None:
    """Fase 2 va a crear `src/runtime_check.py`.

    Cuando exista, debe exponer:
        from runtime_check import ensure_webview2_runtime, is_webview2_installed
    """
    from runtime_check import ensure_webview2_runtime, is_webview2_installed  # noqa: F401


@pytest.mark.xfail(
    reason="Fase 2: is_webview2_installed() debe leer registry HKLM y HKCU",
    strict=False,
)
def test_is_webview2_installed_reads_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """`is_webview2_installed()` debe devolver True/False segun registry."""
    try:
        from runtime_check import is_webview2_installed
    except ImportError:
        pytest.skip("runtime_check no existe todavia (Fase 2)")

    fake_winreg = MagicMock()
    fake_winreg.HKEY_LOCAL_MACHINE = "HKLM_FAKE"
    fake_winreg.HKEY_CURRENT_USER = "HKCU_FAKE"
    fake_winreg.OpenKey = MagicMock(side_effect=OSError("Not found"))

    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    assert is_webview2_installed() is False


@pytest.mark.xfail(
    reason="Fase 2: ensure_webview2_runtime() debe mostrar dialog japones si runtime falta",
    strict=False,
)
def test_ensure_webview2_shows_japanese_dialog_when_missing() -> None:
    """Si WebView2 falta y modo interactivo: dialogo en japones."""
    try:
        from runtime_check import ensure_webview2_runtime  # noqa: F401
    except ImportError:
        pytest.skip("runtime_check no existe todavia (Fase 2)")

    pytest.skip("Implementacion de dialogo nativo va en Fase 2")


@pytest.mark.xfail(
    reason="Fase 2: en modo --auto NO debe abrir dialogo, solo log warning",
    strict=False,
)
def test_ensure_webview2_in_auto_mode_does_not_block() -> None:
    """`--auto` mode no es interactivo. Si WebView2 falta, log y continuar."""
    try:
        from runtime_check import ensure_webview2_runtime  # noqa: F401
    except ImportError:
        pytest.skip("runtime_check no existe todavia (Fase 2)")

    pytest.skip("Implementacion del modo auto-friendly va en Fase 2")


@pytest.mark.xfail(
    reason="Fase 2: installer.iss debe bundlear MicrosoftEdgeWebview2Setup.exe",
    strict=False,
)
def test_installer_iss_includes_webview2_bootstrapper() -> None:
    """El installer Inno Setup debe incluir el bootstrapper en su seccion [Files].

    Decision aprobada 2026-05-13: bundle del bootstrapper (~1.7MB) en el installer.
    """
    from pathlib import Path

    iss_path = Path(__file__).parent.parent / "build" / "installer.iss"
    content = iss_path.read_text(encoding="utf-8", errors="replace")

    assert "MicrosoftEdgeWebview2Setup.exe" in content, (
        "installer.iss debe declarar el bootstrapper en [Files] (Fase 2)"
    )
    assert "/silent /install" in content or "/install" in content, (
        "installer.iss debe correr el bootstrapper con flag de silent install"
    )


# ---------------------------------------------------------------------------
# Constants check
# ---------------------------------------------------------------------------


def test_webview2_registry_path_constant() -> None:
    """El GUID del runtime WebView2 es publico y estable.

    Fuente Microsoft: https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
    Si Microsoft cambia el GUID (improbable), Fase 2 va a fallar.
    """
    assert "F3017226-FE2A-4295-8BDF-00C3A9A7E4C5" in WEBVIEW2_REG_PATH
    assert WEBVIEW2_REG_PATH.startswith("SOFTWARE\\WOW6432Node")
