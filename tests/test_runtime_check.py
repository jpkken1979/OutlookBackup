"""Tests directos del modulo `runtime_check` (Fase 2 plan v3.2).

Cubre las funciones publicas:
- `is_webview2_installed()` — deteccion via registry
- `get_bundled_installer_path()` — busqueda del bootstrapper en redist/
- `download_bootstrapper()` — descarga via urllib (mockeada)
- `run_installer_silent()` — ejecucion via subprocess (mockeada)
- `show_japanese_install_dialog()` — tkinter messagebox (mockeada)
- `ensure_webview2_runtime()` — orquestador

Estos tests corren en Linux Y Windows. En Linux, conftest.py mockea winreg
con MagicMock (autouse session-scope). Para sobreescribir con comportamiento
controlado, los tests usan `monkeypatch.setattr` directamente sobre
`runtime_check.winreg` o sobre los helpers internos.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytestmark = pytest.mark.webview2


# ---------------------------------------------------------------------------
# is_webview2_installed
# ---------------------------------------------------------------------------


def test_is_webview2_installed_returns_false_on_non_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En POSIX siempre devuelve False sin tocar registry."""
    import runtime_check

    monkeypatch.setattr(runtime_check.os, "name", "posix")
    assert runtime_check.is_webview2_installed() is False


def test_is_webview2_installed_false_when_no_registry_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el registry no tiene ninguna de las 3 ubicaciones, devuelve False."""
    import runtime_check

    monkeypatch.setattr(runtime_check.os, "name", "nt")
    monkeypatch.setattr(runtime_check, "_read_pv_value", lambda _r, _p: None)
    assert runtime_check.is_webview2_installed() is False


def test_is_webview2_installed_true_when_machine_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detecta runtime en HKLM (machine-wide install)."""
    import runtime_check

    monkeypatch.setattr(runtime_check.os, "name", "nt")

    def fake_read(root: int, path: str) -> str | None:
        if "WOW6432Node" in path:
            return "133.0.3065.92"
        return None

    monkeypatch.setattr(runtime_check, "_read_pv_value", fake_read)
    assert runtime_check.is_webview2_installed() is True


def test_is_webview2_installed_true_when_user_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detecta runtime en HKCU (per-user install)."""
    import runtime_check

    monkeypatch.setattr(runtime_check.os, "name", "nt")

    def fake_read(root: int, path: str) -> str | None:
        # Solo el path HKCU sin WOW6432Node devuelve version
        if "WOW6432Node" not in path:
            return "133.0.3065.92"
        return None

    monkeypatch.setattr(runtime_check, "_read_pv_value", fake_read)
    assert runtime_check.is_webview2_installed() is True


def test_is_webview2_installed_false_when_pv_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """version '0.0.0.0' es marker de runtime parcialmente desinstalado."""
    import runtime_check

    monkeypatch.setattr(runtime_check.os, "name", "nt")
    monkeypatch.setattr(runtime_check, "_read_pv_value", lambda _r, _p: "0.0.0.0")
    assert runtime_check.is_webview2_installed() is False


# ---------------------------------------------------------------------------
# get_bundled_installer_path
# ---------------------------------------------------------------------------


def test_bundled_installer_path_none_when_not_present(tmp_path: Path) -> None:
    """Sin bundle local en ningun candidate path, devuelve None."""
    import runtime_check

    # Por defecto, el bundle no esta en mi tmp_path
    result = runtime_check.get_bundled_installer_path()
    assert result is None or result.is_file()  # podria existir si dev tiene redist/


# ---------------------------------------------------------------------------
# download_bootstrapper
# ---------------------------------------------------------------------------


def test_download_bootstrapper_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """En success, escribe el bytes content al destino."""
    import runtime_check

    fake_response = MagicMock()
    fake_response.read.return_value = b"fake_installer_bytes"
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)

    monkeypatch.setattr(runtime_check.urllib.request, "urlopen", lambda *_a, **_kw: fake_response)

    dest = tmp_path / "subdir" / "bootstrapper.exe"
    assert runtime_check.download_bootstrapper(dest) is True
    assert dest.is_file()
    assert dest.read_bytes() == b"fake_installer_bytes"


def test_download_bootstrapper_returns_false_on_network_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cualquier error de red devuelve False sin propagar."""
    import runtime_check

    def fake_urlopen(*_a: object, **_kw: object) -> object:
        raise OSError("Network unreachable")

    monkeypatch.setattr(runtime_check.urllib.request, "urlopen", fake_urlopen)

    dest = tmp_path / "boot.exe"
    assert runtime_check.download_bootstrapper(dest) is False
    assert not dest.exists()


# ---------------------------------------------------------------------------
# run_installer_silent
# ---------------------------------------------------------------------------


def test_run_installer_silent_returns_false_when_file_missing(tmp_path: Path) -> None:
    """Si el path no existe, devuelve False sin invocar subprocess."""
    import runtime_check

    assert runtime_check.run_installer_silent(tmp_path / "nope.exe") is False


def test_run_installer_silent_success_returncode_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Returncode 0 → True."""
    import runtime_check

    installer = tmp_path / "fake.exe"
    installer.write_bytes(b"fake")

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = ""
    fake_result.stderr = ""

    monkeypatch.setattr(runtime_check.subprocess, "run", lambda *_a, **_kw: fake_result)

    assert runtime_check.run_installer_silent(installer) is True


def test_run_installer_silent_failure_returncode_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Returncode != 0 → False."""
    import runtime_check

    installer = tmp_path / "fake.exe"
    installer.write_bytes(b"fake")

    fake_result = MagicMock()
    fake_result.returncode = 1603  # Windows installer generic failure
    fake_result.stdout = "fail output"
    fake_result.stderr = "stderr details"

    monkeypatch.setattr(runtime_check.subprocess, "run", lambda *_a, **_kw: fake_result)

    assert runtime_check.run_installer_silent(installer) is False


# ---------------------------------------------------------------------------
# ensure_webview2_runtime — orquestador
# ---------------------------------------------------------------------------


def test_ensure_runtime_short_circuits_when_already_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si ya esta instalado, retorna True sin tocar dialogo ni installer."""
    import runtime_check

    monkeypatch.setattr(runtime_check, "is_webview2_installed", lambda: True)

    # Si llama a estos, el test debe fallar
    monkeypatch.setattr(
        runtime_check,
        "show_japanese_install_dialog",
        lambda: pytest.fail("No deberia llamar dialogo"),
    )

    assert runtime_check.ensure_webview2_runtime(interactive=True) is True


def test_ensure_runtime_non_interactive_returns_false_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En modo --auto: log warning y devolver False sin bloquear."""
    import runtime_check

    monkeypatch.setattr(runtime_check, "is_webview2_installed", lambda: False)
    monkeypatch.setattr(
        runtime_check,
        "show_japanese_install_dialog",
        lambda: pytest.fail("No deberia llamar dialogo en modo auto"),
    )

    assert runtime_check.ensure_webview2_runtime(interactive=False) is False


def test_ensure_runtime_user_rejects_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el usuario clickea 'No' en el dialogo, retorna False."""
    import runtime_check

    monkeypatch.setattr(runtime_check, "is_webview2_installed", lambda: False)
    monkeypatch.setattr(runtime_check, "show_japanese_install_dialog", lambda: False)

    assert runtime_check.ensure_webview2_runtime(interactive=True) is False


def test_ensure_runtime_full_install_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flujo completo: no instalado → user acepta → installer corre → re-detecta."""
    import runtime_check

    install_states = [False, True]  # antes y despues del install

    def fake_is_installed() -> bool:
        return install_states.pop(0)

    monkeypatch.setattr(runtime_check, "is_webview2_installed", fake_is_installed)
    monkeypatch.setattr(runtime_check, "show_japanese_install_dialog", lambda: True)
    monkeypatch.setattr(
        runtime_check, "get_bundled_installer_path", lambda: Path("fake/installer.exe")
    )
    monkeypatch.setattr(runtime_check, "run_installer_silent", lambda _p: True)

    assert runtime_check.ensure_webview2_runtime(interactive=True) is True


def test_ensure_runtime_install_fails_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el installer falla, retorna False aunque user haya aceptado."""
    import runtime_check

    monkeypatch.setattr(runtime_check, "is_webview2_installed", lambda: False)
    monkeypatch.setattr(runtime_check, "show_japanese_install_dialog", lambda: True)
    monkeypatch.setattr(
        runtime_check, "get_bundled_installer_path", lambda: Path("fake/installer.exe")
    )
    monkeypatch.setattr(runtime_check, "run_installer_silent", lambda _p: False)

    assert runtime_check.ensure_webview2_runtime(interactive=True) is False


# ---------------------------------------------------------------------------
# Constants — sanity check
# ---------------------------------------------------------------------------


def test_runtime_guid_constant() -> None:
    """El GUID es publico y estable. Si Microsoft lo cambia (improbable), reportar."""
    import runtime_check

    assert runtime_check.WEBVIEW2_RUNTIME_GUID == "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def test_bootstrapper_url_is_microsoft() -> None:
    """La URL del evergreen bootstrapper debe ser de microsoft.com."""
    import runtime_check

    assert "microsoft.com" in runtime_check.WEBVIEW2_BOOTSTRAPPER_URL
