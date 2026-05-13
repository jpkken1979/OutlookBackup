"""Tests del bundling de WebView2 en el installer Inno Setup.

Despues de Fase 2 del plan v3.2, la deteccion del runtime esta cubierta
exhaustivamente en `tests/test_runtime_check.py`. Este archivo solo cubre la
INTEGRACION con el installer Inno Setup que NO se puede testear desde Python
directamente (el .iss se compila con ISCC.exe, no se importa).

Verifica el contrato del installer.iss:
- Declara el bootstrapper en [Files] con DestDir adecuado.
- Tiene un check en [Code] que decide si correrlo segun registry.
- Lo ejecuta en [Run] con flag de silent install.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.webview2

ISS_PATH = Path(__file__).parent.parent / "build" / "installer.iss"


def test_installer_iss_exists() -> None:
    """Sanity check del path del installer."""
    assert ISS_PATH.is_file(), f"installer.iss no encontrado en {ISS_PATH}"


def test_installer_declares_webview2_bootstrapper() -> None:
    """El installer debe declarar `MicrosoftEdgeWebview2Setup.exe` en [Files].

    Decision aprobada 2026-05-13: bundle del bootstrapper evergreen (~1.7MB)
    elimina la friccion del primer run en Win 10 sin WebView2.
    """
    content = ISS_PATH.read_text(encoding="utf-8", errors="replace")
    assert "MicrosoftEdgeWebview2Setup.exe" in content, (
        "installer.iss debe declarar el bootstrapper en [Files] (Fase 2)"
    )


def test_installer_runs_bootstrapper_silently() -> None:
    """El installer debe ejecutar el bootstrapper con flag de silent install."""
    content = ISS_PATH.read_text(encoding="utf-8", errors="replace")
    has_silent_flag = "/silent /install" in content or "/install /silent" in content
    assert has_silent_flag, (
        "installer.iss debe ejecutar el bootstrapper con '/silent /install' (Fase 2)"
    )


def test_installer_has_webview2_check_in_code_section() -> None:
    """[Code] section debe tener un check que evita re-instalar si ya esta presente.

    Esto evita que cada upgrade del installer corra el bootstrapper de nuevo
    (fricion innecesaria + 1.7MB de download repetido).
    """
    content = ISS_PATH.read_text(encoding="utf-8", errors="replace")
    has_check_function = (
        "WebView2NeedsInstall" in content
        or "function NeedsWebView2" in content
        or "RegQueryStringValue" in content
    )
    assert has_check_function, (
        "installer.iss debe tener funcion en [Code] que chequea registry antes de "
        "instalar WebView2 (Fase 2)"
    )
