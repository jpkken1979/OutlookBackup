"""Tests de deteccion de version de Outlook.

Fase 1 del plan v3.2 (docs/PLAN_HARDENING_WIN10_11.md):
- Verifica el comportamiento ACTUAL de enumeracion de versions del registro
  (`account_inventory._read_registry_servers` busca en 16.0, 15.0, 14.0).
- Marca con xfail los comportamientos que Fase 4 va a implementar
  (deteccion de M365 vs perpetual, version 17.0 futura, fallback flavor).

Estos tests corren en Linux Y Windows porque conftest.py mockea winreg con
MagicMock autouse. Para sobrescribir el mock con un comportamiento especifico
se usa `monkeypatch.setattr` sobre `account_inventory.winreg`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytestmark = pytest.mark.outlook_version


# ---------------------------------------------------------------------------
# Test 1: comportamiento actual del enumerador de versions
# ---------------------------------------------------------------------------


def test_registry_servers_enumerates_known_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_read_registry_servers` debe iterar 16.0, 15.0 y 14.0 en ese orden.

    Si esta lista cambia en el futuro (ej: agregar 17.0 cuando salga Office 2025),
    este test va a fallar y forza al desarrollador a actualizarlo conscientemente.
    """
    import account_inventory

    versions_probed: list[str] = []

    fake_winreg = MagicMock()
    fake_winreg.HKEY_CURRENT_USER = "HKCU_FAKE"

    def fake_open_key(_root: Any, path: str) -> Any:
        # Capturar cada version probada
        for v in ("16.0", "15.0", "14.0", "17.0", "13.0"):
            if f"\\Office\\{v}\\" in path:
                versions_probed.append(v)
                break
        # Simular que ninguna version existe
        raise OSError("Not found")

    fake_winreg.OpenKey = fake_open_key
    monkeypatch.setattr(account_inventory, "winreg", fake_winreg)

    result = account_inventory._read_registry_servers("test@example.com")

    assert result is None, "Sin registry hits debe devolver None"
    assert versions_probed == ["16.0", "15.0", "14.0"], (
        f"Solo debe probar 16.0/15.0/14.0, probo: {versions_probed}"
    )


def test_registry_servers_returns_none_when_no_smtp() -> None:
    """Sin SMTP address, debe devolver None sin tocar el registry."""
    import account_inventory

    assert account_inventory._read_registry_servers("") is None
    assert account_inventory._read_registry_servers(None) is None  # type: ignore[arg-type]


def test_registry_servers_returns_none_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """En non-Windows debe devolver None sin tocar winreg."""
    import account_inventory

    monkeypatch.setattr(account_inventory.os, "name", "posix")
    assert account_inventory._read_registry_servers("test@example.com") is None


# ---------------------------------------------------------------------------
# Test 2: contrato del Dispatch().Version (mockeado)
# ---------------------------------------------------------------------------


def test_outlook_application_version_is_parseable() -> None:
    """`Outlook.Application.Version` debe ser un string tipo '16.0.x.x' parseable.

    Verifica que cuando llamamos `Dispatch("Outlook.Application")`, el atributo
    `.Version` retorna un string que se puede parsear como tupla de ints.
    Esto blinda el contrato que Fase 4 va a usar para detectar la version real.
    """
    # Re-importar fresh para usar la mock global de conftest
    import win32com.client

    fake_app = MagicMock()
    fake_app.Version = "16.0.17726.20126"  # M365 actual al 2026-05
    win32com.client.Dispatch = MagicMock(return_value=fake_app)

    app = win32com.client.Dispatch("Outlook.Application")
    version_str = app.Version

    assert isinstance(version_str, str)
    parts = version_str.split(".")
    assert len(parts) >= 2, f"Version debe tener al menos major.minor: {version_str}"
    major, minor = int(parts[0]), int(parts[1])
    assert major >= 14, f"Version major debe ser >= 14: {major}"
    assert minor == 0, f"Version minor por convencion Office es 0: {minor}"


# ---------------------------------------------------------------------------
# Tests xfail — comportamiento que Fase 4 debe implementar
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Fase 4 del plan v3.2: detectar Outlook 17.0 cuando salga (futuro Office 2025)",
    strict=False,
)
def test_future_outlook_17_should_be_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cuando Microsoft saque Outlook 17.0, debe detectarse sin parche.

    Hoy `_read_registry_servers` tiene `versions = ["16.0", "15.0", "14.0"]` hardcoded.
    Fase 4 va a implementar enumeracion dinamica via `winreg.EnumKey` sobre
    `Software\\Microsoft\\Office\\` para no tener que parchear cada major release.
    """
    import account_inventory

    versions_probed: list[str] = []
    fake_winreg = MagicMock()
    fake_winreg.HKEY_CURRENT_USER = "HKCU_FAKE"

    def fake_open_key(_root: Any, path: str) -> Any:
        for v in ("16.0", "15.0", "14.0", "17.0"):
            if f"\\Office\\{v}\\" in path:
                versions_probed.append(v)
                break
        raise OSError("Not found")

    fake_winreg.OpenKey = fake_open_key
    monkeypatch.setattr(account_inventory, "winreg", fake_winreg)
    account_inventory._read_registry_servers("test@example.com")

    assert "17.0" in versions_probed, "Fase 4 debe enumerar dinamicamente, no hardcodear"


@pytest.mark.xfail(
    reason="Fase 4 del plan v3.2: distinguir Outlook M365 (Click-to-Run) vs perpetual",
    strict=False,
)
def test_outlook_flavor_detection_distinguishes_m365_vs_perpetual() -> None:
    """Fase 4 va a crear `src/outlook/version.py:detect_outlook_version()`.

    Debe retornar un dataclass con campo `flavor: Literal["M365", "perpetual", "unknown"]`
    leyendo `HKLM\\SOFTWARE\\Microsoft\\Office\\ClickToRun\\Configuration` para M365 y
    `HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Office\\{ver}\\Outlook\\InstallRoot\\Path`
    para perpetual.
    """
    # Cuando exista, hacer:
    # from outlook.version import detect_outlook_version
    # info = detect_outlook_version()
    # assert info.flavor in ("M365", "perpetual", "unknown")
    pytest.skip("Fase 4 no implementada todavia")


@pytest.mark.xfail(
    reason="Fase 4 del plan v3.2: warnear si version no soportada (Outlook < 16.0)",
    strict=False,
)
def test_outlook_2016_or_older_is_marked_unsupported() -> None:
    """Por decision del usuario, Outlook 2016 (15.0) y anteriores no se soportan en v3.2.

    Fase 4 va a agregar campo `supported: bool` al resultado de `detect_outlook_version()`.
    """
    pytest.skip("Fase 4 no implementada todavia")


# ---------------------------------------------------------------------------
# Helper: garantizar que account_inventory este importable
# ---------------------------------------------------------------------------


def test_account_inventory_module_importable() -> None:
    """Sanity check — el modulo debe cargar sin tocar Outlook real."""
    if "account_inventory" in sys.modules:
        del sys.modules["account_inventory"]
    import account_inventory  # noqa: F401

    assert hasattr(account_inventory, "_read_registry_servers")
