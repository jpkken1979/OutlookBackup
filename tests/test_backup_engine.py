"""Tests del BackupEngine + BackupReport.

Estrategia:
- BackupReport es pura logica (sin COM) — tests directos
- BackupEngine usa OutlookClientProtocol — pasamos FakeOutlookClient
- run_async dispara thread, esperamos via threading.Event
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backup_engine import BackupEngine, BackupReport  # noqa: E402
from outlook.fakes import FakeOutlookAccount, FakeOutlookClient  # noqa: E402

# ============================================================
# BackupReport — pura logica
# ============================================================


class TestBackupReport:
    def test_initial_state(self) -> None:
        report = BackupReport()
        assert report.accounts_processed == []
        assert report.errors == []
        assert report.total_emails == 0
        assert report.end_time is None

    def test_add_account_accumulates_emails(self) -> None:
        report = BackupReport()
        report.add_account({"smtp": "a@x.com", "emails": 10})
        report.add_account({"smtp": "b@x.com", "emails": 5})

        assert len(report.accounts_processed) == 2
        assert report.total_emails == 15

    def test_add_error_stores_with_timestamp(self) -> None:
        report = BackupReport()
        report.add_error("boom")

        assert len(report.errors) == 1
        assert report.errors[0]["message"] == "boom"
        assert "time" in report.errors[0]

    def test_finish_sets_end_time(self) -> None:
        report = BackupReport()
        assert report.end_time is None
        report.finish()
        assert report.end_time is not None

    def test_duration_zero_before_finish(self) -> None:
        report = BackupReport()
        assert report.duration_seconds == 0

    def test_duration_positive_after_finish(self) -> None:
        report = BackupReport()
        report.finish()
        assert report.duration_seconds >= 0

    def test_save_json_writes_valid_json(self, tmp_path: Path) -> None:
        report = BackupReport()
        report.add_account({"smtp": "a@x.com", "emails": 7})
        report.finish()

        out = tmp_path / "report.json"
        report.save_json(str(out))

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["total_emails"] == 7
        assert len(data["accounts_processed"]) == 1

    def test_save_html_writes_valid_html(self, tmp_path: Path) -> None:
        report = BackupReport()
        report.add_account({"smtp": "a@x.com", "emails": 7, "success": True})
        report.finish()

        out = tmp_path / "report.html"
        report.save_html(str(out))

        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "a@x.com" in content
        assert "UNS Outlook Backup Report" in content


# ============================================================
# BackupEngine
# ============================================================


def _wait_for_backup(engine: BackupEngine, timeout: float = 5.0) -> tuple[bool, str]:
    """Helper: arranca el engine, espera el finish_cb, devuelve resultado."""
    done = threading.Event()
    result: dict = {}

    def progress_cb(msg: str) -> None:
        pass

    def finish_cb(success: bool, info: str) -> None:
        result["success"] = success
        result["info"] = info
        done.set()

    engine.run_async(progress_cb, finish_cb)
    if not done.wait(timeout):
        raise TimeoutError(f"Backup no termino en {timeout}s")
    return result["success"], result["info"]


class TestBackupEngine:
    def test_run_pst_format_happy_path(self, tmp_path: Path) -> None:
        """Backup PST de 2 cuentas, ambas exitosas, genera reports + PSTs."""
        client = FakeOutlookClient()
        accounts = [
            FakeOutlookAccount(smtp_address="kenji@uns-kikaku.com", display_name="Kenji"),
            FakeOutlookAccount(smtp_address="info@uns-kikaku.com", display_name="Info"),
        ]
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=accounts,
            export_format="pst",
        )

        success, session_dir = _wait_for_backup(engine)

        assert success is True
        session = Path(session_dir)
        assert session.exists()
        assert (session / "report.json").exists()
        assert (session / "report.html").exists()
        assert (session / "kenji_at_uns-kikaku_com.pst").exists()
        assert (session / "info_at_uns-kikaku_com.pst").exists()
        assert len(client._export_calls) == 2

    def test_run_msg_format_uses_msg_export(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        accounts = [FakeOutlookAccount(smtp_address="k@x.com")]
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=accounts,
            export_format="msg",
        )

        success, _ = _wait_for_backup(engine)

        assert success is True
        assert len(client._msg_calls) == 1
        assert len(client._export_calls) == 0  # PST path no se usa en msg

    def test_run_with_failing_account_logs_error(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        client._export_returns["broken@x.com"] = False
        accounts = [
            FakeOutlookAccount(smtp_address="ok@x.com"),
            FakeOutlookAccount(smtp_address="broken@x.com"),
        ]
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=accounts,
            export_format="pst",
        )

        success, session_dir = _wait_for_backup(engine)

        # Aun con una cuenta fallida, success=True porque al menos 1 paso
        assert success is True
        report_data = json.loads((Path(session_dir) / "report.json").read_text(encoding="utf-8"))
        ok = next(a for a in report_data["accounts_processed"] if a["smtp"] == "ok@x.com")
        broken = next(a for a in report_data["accounts_processed"] if a["smtp"] == "broken@x.com")
        assert ok["success"] is True
        assert broken["success"] is False

    def test_run_creates_session_dir_with_timestamp(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=[FakeOutlookAccount(smtp_address="a@x.com")],
        )

        _, session_dir = _wait_for_backup(engine)
        session = Path(session_dir)

        # Formato: backup_YYYYMMDD_HHMMSS
        assert session.name.startswith("backup_")
        assert len(session.name) == len("backup_20260511_153045")

    def test_smtp_slug_replaces_at_and_dot(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=[FakeOutlookAccount(smtp_address="k.kaneshiro@uns-kikaku.com")],
        )

        _, session_dir = _wait_for_backup(engine)
        # @ -> _at_, . -> _
        expected = "k_kaneshiro_at_uns-kikaku_com.pst"
        assert (Path(session_dir) / expected).exists()

    def test_cancel_aborts_remaining_accounts(self, tmp_path: Path) -> None:
        """Si cancel() se llama, el resto de cuentas se saltea."""
        # Setup: 5 cuentas. Marcar cancel apenas arranca.
        client = FakeOutlookClient()
        accounts = [FakeOutlookAccount(smtp_address=f"u{i}@x.com") for i in range(5)]
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=accounts,
        )

        # Cancel BEFORE running — el flag se chequea al inicio de cada iteracion
        engine.cancel()
        success, _ = _wait_for_backup(engine)

        # Ninguna cuenta se procesa (el cancel se ve antes de la primera iteracion)
        assert len(client._export_calls) == 0

    def test_count_emails_called_after_export(self, tmp_path: Path) -> None:
        """count_emails_for_account se llama post-backup para anotar el reporte."""
        client = FakeOutlookClient()
        client._count_returns["a@x.com"] = {
            "total_emails": 42,
            "total_folders": 5,
            "total_size_bytes": 0,
            "folders": [],
        }
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=[FakeOutlookAccount(smtp_address="a@x.com")],
        )

        _, session_dir = _wait_for_backup(engine)
        report = json.loads((Path(session_dir) / "report.json").read_text(encoding="utf-8"))
        assert report["accounts_processed"][0]["emails"] == 42
        assert "a@x.com" in client._count_calls

    def test_zero_accounts_succeeds_with_empty_report(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = BackupEngine(
            outlook_client=client,
            output_dir=str(tmp_path),
            selected_accounts=[],
        )

        success, session_dir = _wait_for_backup(engine)
        assert success is True
        report = json.loads((Path(session_dir) / "report.json").read_text(encoding="utf-8"))
        assert report["accounts_processed"] == []
        assert report["total_emails"] == 0
