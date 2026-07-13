"""Tests para vss_copy.py — VSS hot-copy de OST/PST.

Cubre: deteccion de admin, parsing de volumen, no-Windows, no-admin fallback,
flujo completo mockeado, y cleanup de shadow siempre ejecutado.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vss_copy import (  # noqa: E402
    SHADOW_CREATE_TIMEOUT,
    VssCopyResult,
    _run_vssadmin_create,
    _run_vssadmin_delete,
    _volume_of,
    is_admin,
    vss_copy,
)


class TestIsAdmin:
    """Verificacion del chequeo de privilegios."""

    def test_not_windows_returns_false(self):
        with patch("vss_copy.os") as mock_os:
            mock_os.name = "posix"
            assert is_admin() is False

    def test_windows_ctypes_call(self):
        with patch("vss_copy.os") as mock_os, patch("vss_copy.ctypes") as mock_ctypes:
            mock_os.name = "nt"
            mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 1
            assert is_admin() is True

    def test_windows_ctypes_exception_returns_false(self):
        with patch("vss_copy.os") as mock_os, patch("vss_copy.ctypes") as mock_ctypes:
            mock_os.name = "nt"
            mock_ctypes.windll.shell32.IsUserAnAdmin.side_effect = OSError("denied")
            assert is_admin() is False


class TestVolumeOf:
    """Extraccion del volumen desde un path absoluto."""

    def test_drive_c(self):
        assert _volume_of(Path("C:\\Users\\test\\file.ost")) == "C:"

    def test_drive_d(self):
        assert _volume_of(Path("D:\\Data\\backup.pst")) == "D:"

    def test_no_drive_returns_empty(self):
        # Paths UNC (\\server\share) no soportan VSS de volumen local
        result = _volume_of(Path("\\\\server\\share\\file.ost"))
        assert result == ""


class TestVssCopyResult:
    """Contrato del dataclass VssCopyResult."""

    def test_immutable(self):
        r = VssCopyResult(success=True, dest="/tmp/x", reason="ok")
        with pytest.raises(Exception):
            r.success = False  # frozen

    def test_default_fields(self):
        r = VssCopyResult(success=False, dest="/tmp/x", reason="not_admin")
        assert r.shadow_device == ""
        assert r.success is False
        assert r.reason == "not_admin"


class TestRunVssadminCreate:
    """Parsing de la salida de vssadmin create shadow."""

    def test_parse_globalroot_path(self):
        fake_completed = _make_completed(
            stdout=(
                "vssadmin 1.1 - Volume Shadow Copy Service\n"
                "Copyright (C) Microsoft Corporation.\n"
                "Shadow Copy Volume Name: \\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1\n"
            ),
            returncode=0,
        )
        with patch("vss_copy.subprocess.run", return_value=fake_completed):
            ok, dev = _run_vssadmin_create("C:")
            assert ok is True
            assert dev.startswith("\\\\?\\GLOBALROOT\\")

    def test_vssadmin_error_returns_false(self):
        fake_completed = _make_completed(stdout="", stderr="Access denied", returncode=1)
        with patch("vss_copy.subprocess.run", return_value=fake_completed):
            ok, err = _run_vssadmin_create("C:")
            assert ok is False
            assert "exit 1" in err

    def test_no_globalroot_in_output(self):
        fake_completed = _make_completed(stdout="some output without device", returncode=0)
        with patch("vss_copy.subprocess.run", return_value=fake_completed):
            ok, _ = _run_vssadmin_create("C:")
            assert ok is False

    def test_timeout_propagates(self):
        import subprocess as sp

        with patch("vss_copy.subprocess.run", side_effect=sp.TimeoutExpired(cmd="vssadmin", timeout=60)):
            with pytest.raises(sp.TimeoutExpired):
                _run_vssadmin_create("C:")


class TestRunVssadminDelete:
    """Cleanup de shadow copy."""

    def test_success(self):
        fake = _make_completed(stdout="", returncode=0)
        with patch("vss_copy.subprocess.run", return_value=fake):
            assert _run_vssadmin_delete("\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1") is True

    def test_failure_returns_false_not_raises(self):
        with patch("vss_copy.subprocess.run", side_effect=Exception("boom")):
            assert _run_vssadmin_delete("anything") is False


class TestVssCopyFallback:
    """Casos donde VSS no aplica y debe hacer fallback."""

    def test_not_windows(self):
        with patch("vss_copy.os") as mock_os:
            mock_os.name = "posix"
            r = vss_copy(Path("/tmp/a.ost"), Path("/tmp/b.ost"))
            assert r.success is False
            assert r.reason == "not_windows"

    def test_not_admin_fallback(self):
        with patch("vss_copy.os") as mock_os, patch("vss_copy.is_admin", return_value=False):
            mock_os.name = "nt"
            r = vss_copy(Path("C:\\Data\\a.ost"), Path("C:\\Backup\\b.ost"))
            assert r.success is False
            assert r.reason == "not_admin"

    def test_not_admin_progress_cb_called(self):
        calls: list[str] = []

        def cb(msg: str) -> None:
            calls.append(msg)

        with patch("vss_copy.os") as mock_os, patch("vss_copy.is_admin", return_value=False):
            mock_os.name = "nt"
            vss_copy(Path("C:\\a.ost"), Path("C:\\b.ost"), progress_cb=cb)
            assert any("管理者権限" in c for c in calls)


class TestVssCopyFullFlow:
    """Flujo completo mockeado: admin, crear shadow, copiar, limpiar."""

    def test_success_flow(self, tmp_path):
        src = tmp_path / "src.ost"
        dest = tmp_path / "out" / "dest.ost"
        src.write_bytes(b"x" * 100)
        dest.parent.mkdir()

        shadow = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1"

        # Mock: is_admin True, subprocess (create ok), open lee del fake, delete ok
        with patch("vss_copy.is_admin", return_value=True), patch(
            "vss_copy.os.name", "nt"
        ), patch(
            "vss_copy._run_vssadmin_create", return_value=(True, shadow)
        ) as mock_create, patch(
            "vss_copy._run_vssadmin_delete", return_value=True
        ) as mock_delete, patch(
            "vss_copy._copy_from_shadow", return_value=True
        ) as mock_copy:

            r = vss_copy(src, dest)

            assert r.success is True
            assert r.reason == "ok"
            assert r.shadow_device == shadow
            mock_create.assert_called_once()
            mock_copy.assert_called_once()
            # Cleanup SIEMPRE ejecutado
            mock_delete.assert_called_once_with(shadow)

    def test_shadow_create_fails_no_cleanup_needed(self, tmp_path):
        src = tmp_path / "src.ost"
        dest = tmp_path / "dest.ost"
        src.write_bytes(b"data")

        with patch("vss_copy.is_admin", return_value=True), patch(
            "vss_copy.os.name", "nt"
        ), patch("vss_copy._run_vssadmin_create", return_value=(False, "error")), patch(
            "vss_copy._run_vssadmin_delete"
        ) as mock_delete:
            r = vss_copy(src, dest)
            assert r.success is False
            assert r.reason == "shadow_failed"
            # No shadow was created, no cleanup
            mock_delete.assert_not_called()

    def test_copy_fails_but_shadow_still_cleaned(self, tmp_path):
        """CRITICO: si la copia falla, el shadow debe eliminarse igual (finally)."""
        src = tmp_path / "src.ost"
        dest = tmp_path / "dest.ost"
        src.write_bytes(b"data")
        shadow = "\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy1"

        with patch("vss_copy.is_admin", return_value=True), patch(
            "vss_copy.os.name", "nt"
        ), patch("vss_copy._run_vssadmin_create", return_value=(True, shadow)), patch(
            "vss_copy._copy_from_shadow", return_value=False
        ), patch(
            "vss_copy._run_vssadmin_delete", return_value=True
        ) as mock_delete:

            r = vss_copy(src, dest)
            assert r.success is False
            assert r.reason == "copy_failed"
            # CRITICO: cleanup ejecutado en el finally
            mock_delete.assert_called_once_with(shadow)

    def test_cancel_check_aborts(self, tmp_path):
        src = tmp_path / "src.ost"
        dest = tmp_path / "dest.ost"
        src.write_bytes(b"data")

        with patch("vss_copy.is_admin", return_value=True), patch(
            "vss_copy.os.name", "nt"
        ), patch("vss_copy._run_vssadmin_create", return_value=(True, "shadow")), patch(
            "vss_copy._run_vssadmin_delete", return_value=True
        ):
            # _copy_from_shadow recibira cancel_check
            r = vss_copy(src, dest, cancel_check=lambda: True)
            # copy_from_shadow es real y aborta via InterruptedError -> copy_failed
            assert r.success is False
            assert r.reason in ("copy_failed",)


class TestConstants:
    """Tiempos de timeout sane."""

    def test_timeouts_positive(self):
        assert SHADOW_CREATE_TIMEOUT > 0
        from vss_copy import SHADOW_COPY_TIMEOUT, SHADOW_DELETE_TIMEOUT

        assert SHADOW_COPY_TIMEOUT > SHADOW_CREATE_TIMEOUT  # copia tarda mas que crear
        assert SHADOW_DELETE_TIMEOUT > 0


# Helper para crear CompletedProcess sin invocar subprocess real
def _make_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    import subprocess as sp

    return sp.CompletedProcess(args=["vssadmin"], returncode=returncode, stdout=stdout, stderr=stderr)
