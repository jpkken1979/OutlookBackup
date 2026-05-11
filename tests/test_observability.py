"""Tests del modulo observability — logging, crash reporter, updater."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ============================================================
# observability.logging
# ============================================================


class TestSetupLogger:
    def test_setup_logger_creates_json_file(self, tmp_path: Path) -> None:
        from observability import get_logger, setup_logger

        log_file = tmp_path / "test.log"
        setup_logger(json_file=log_file, add_console=False)

        log = get_logger("test")
        log.info("event.fired", foo="bar", n=42)

        # Flush handlers
        import logging as stdlib_logging

        for h in stdlib_logging.root.handlers:
            h.flush()

        # En modo TTY puede ser console renderer, en CI sera JSON
        content = log_file.read_text(encoding="utf-8").strip()
        assert content  # algo se escribio
        # En CI (no-TTY) sera JSON parseable
        if not sys.stderr.isatty():
            data = json.loads(content.splitlines()[-1])
            assert data["event"] == "event.fired"
            assert data["foo"] == "bar"

    def test_setup_logger_creates_parent_dir(self, tmp_path: Path) -> None:
        from observability import setup_logger

        log_file = tmp_path / "nested" / "deep" / "test.log"
        setup_logger(json_file=log_file, add_console=False)

        assert log_file.parent.exists()

    def test_bind_context_propagates_to_logs(self, tmp_path: Path, capsys) -> None:
        from observability import get_logger, setup_logger
        from observability.logging import bind_context, clear_context

        setup_logger(json_file=tmp_path / "ctx.log", add_console=False)
        log = get_logger("test")

        bind_context(operation="backup", session="abc")
        log.info("with-context")
        clear_context()
        log.info("no-context")

        import logging as stdlib_logging

        for h in stdlib_logging.root.handlers:
            h.flush()

        content = (tmp_path / "ctx.log").read_text(encoding="utf-8")
        # En modo no-TTY (CI), parseable como JSON
        if not sys.stderr.isatty():
            lines = [json.loads(line) for line in content.strip().splitlines()]
            with_ctx = next(line for line in lines if line["event"] == "with-context")
            no_ctx = next(line for line in lines if line["event"] == "no-context")
            assert with_ctx.get("operation") == "backup"
            assert "operation" not in no_ctx


# ============================================================
# observability.crash
# ============================================================


class TestCrashReporter:
    def test_sanitize_replaces_username(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from observability import sanitize_for_crash_report

        monkeypatch.setenv("USERNAME", "kenji")
        result = sanitize_for_crash_report("C:\\Users\\kenji\\Documents\\foo.txt")
        assert "kenji" not in result
        assert "<user>" in result

    def test_sanitize_no_username_no_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from observability import sanitize_for_crash_report

        monkeypatch.delenv("USERNAME", raising=False)
        monkeypatch.delenv("USER", raising=False)
        text = "C:\\Users\\someone\\Documents"
        # Sin USERNAME, no sanitiza
        assert sanitize_for_crash_report(text) == text

    def test_write_crash_report_creates_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

        from observability.crash import write_crash_report

        try:
            raise ValueError("test error message")
        except ValueError as e:
            out = write_crash_report(type(e), e, e.__traceback__)

        assert out.exists()
        assert out.name.startswith("crash_")
        assert out.suffix == ".json"

        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["exception"]["type"] == "ValueError"
        assert "test error message" in report["exception"]["message"]
        assert report["app"] == "uns-outlook-backup"

    def test_crash_report_redacts_secret_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
        monkeypatch.setenv("UNS_BANK_TOKEN", "supersecret123")
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-abc-xyz")

        from observability.crash import write_crash_report

        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            out = write_crash_report(type(e), e, e.__traceback__)

        report = json.loads(out.read_text(encoding="utf-8"))
        env = report["env"]
        if "UNS_BANK_TOKEN" in env:
            assert env["UNS_BANK_TOKEN"] == "<redacted>"
        if "MINIMAX_API_KEY" in env:
            assert env["MINIMAX_API_KEY"] == "<redacted>"

    def test_install_crash_handler_replaces_excepthook(self) -> None:
        from observability import install_crash_handler

        original = sys.excepthook
        try:
            install_crash_handler()
            assert sys.excepthook is not original
        finally:
            sys.excepthook = original


# ============================================================
# observability.updater
# ============================================================


class TestUpdater:
    def test_parse_version_handles_v_prefix(self) -> None:
        from observability.updater import _parse_version

        assert _parse_version("v3.1.1") == (3, 1, 1)
        assert _parse_version("3.1.1") == (3, 1, 1)
        assert _parse_version("V3.1.1") == (3, 1, 1)

    def test_parse_version_handles_pre_release(self) -> None:
        from observability.updater import _parse_version

        # Tolera prerelease — corta en el primer no-digit despues de split.
        # "rc1" no empieza con digito puro, asi que se descarta.
        assert _parse_version("3.1.1-rc1") == (3, 1, 1)
        assert _parse_version("3.2.0") == (3, 2, 0)

    def test_is_newer_compares_correctly(self) -> None:
        from observability.updater import _is_newer

        assert _is_newer("v3.2.0", "3.1.1") is True
        assert _is_newer("v3.1.2", "3.1.1") is True
        assert _is_newer("v3.1.1", "3.1.1") is False
        assert _is_newer("v3.1.0", "3.1.1") is False

    def test_check_for_updates_network_failure_returns_error(self) -> None:
        from observability.updater import check_for_updates

        with patch("urllib.request.urlopen") as mock_open:
            import urllib.error

            mock_open.side_effect = urllib.error.URLError("connection refused")
            info = check_for_updates(current_version="3.1.1")

        assert info.available is False
        assert "network" in info.error
        assert info.current_version == "3.1.1"

    def test_check_for_updates_finds_newer_release(self) -> None:
        from observability.updater import check_for_updates

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(
            {
                "tag_name": "v3.2.0",
                "html_url": "https://github.com/test/test/releases/v3.2.0",
                "body": "Release notes here",
                "assets": [
                    {
                        "name": "UNS-Outlook-Backup.exe",
                        "browser_download_url": "https://example.com/download.exe",
                    }
                ],
            }
        ).encode("utf-8")
        fake_response.__enter__ = lambda self: self
        fake_response.__exit__ = lambda *args: None

        with (
            patch("urllib.request.urlopen", return_value=fake_response),
            patch("json.load", return_value=json.loads(fake_response.read())),
        ):
            info = check_for_updates(current_version="3.1.1")

        assert info.available is True
        assert info.latest_version == "v3.2.0"
        assert info.download_url == "https://example.com/download.exe"
        assert info.notes == "Release notes here"

    def test_check_for_updates_same_version_not_available(self) -> None:
        from observability.updater import check_for_updates

        fake_data = {
            "tag_name": "v3.1.1",
            "html_url": "",
            "body": "",
            "assets": [],
        }
        fake_response = MagicMock()
        fake_response.__enter__ = lambda self: self
        fake_response.__exit__ = lambda *args: None

        with (
            patch("urllib.request.urlopen", return_value=fake_response),
            patch("json.load", return_value=fake_data),
        ):
            info = check_for_updates(current_version="3.1.1")

        assert info.available is False
        assert info.error == ""
        assert info.latest_version == "v3.1.1"
