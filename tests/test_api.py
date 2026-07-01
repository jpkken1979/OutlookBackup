"""Tests directos de `api.API` — el bridge pywebview <-> Python.

Es el modulo mas grande del proyecto (927 lineas, 51 metodos publicos) y el
unico sin cobertura directa (los engines se testean por separado). Aca se
prioriza la logica de mayor riesgo:

- El patron de jobs async: _backup_lock/_import_lock previniendo doble-start
  (doc en CLAUDE.md: "toda operacion que tarde mas de 2s usa este patron")
- Wiring de progress/finish callbacks hacia el estado de polling
- Validaciones de parametros obligatorios antes de tocar engines reales
- Config persistente aislada (nunca debe tocar el ~/.config real del host)

Los engines pesados (BackupEngine, ImportEngine, CacheBackupEngine) se
reemplazan por fakes sincronicos que llaman progress/finish directamente,
sin threads reales — evita flakiness y hace las asserts deterministicas.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Evita que Config() toque ~/.config real del host que corre los tests."""
    import config

    cfg_dir = tmp_path / "uns-config"
    cfg_dir.mkdir(parents=True, exist_ok=True)  # get_config_dir() real tambien lo crea
    monkeypatch.setattr(config, "get_config_dir", lambda: cfg_dir)
    return cfg_dir


@pytest.fixture
def api(isolated_config: Path) -> Any:
    from api import API

    return API()


class _FakeBackupEngine:
    """Corre progress/finish sincronicamente — sin threads reales."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.cancel_called = False
        self.thread: threading.Thread | None = None

    def run_async(self, progress: Any, finish: Any) -> None:
        """Igual que la produccion: corre en un thread separado (nunca sincronico,
        o deadlockea contra el mismo _backup_lock que start_backup sigue sosteniendo)."""

        def _run() -> None:
            progress("[fake] backup iniciado")
            finish(True, str(self.kwargs.get("output_dir", "")) + "/backup_fake")

        self.thread = threading.Thread(target=_run, daemon=True)
        self.thread.start()

    def cancel(self) -> None:
        self.cancel_called = True


class _FakeImportEngine:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.thread: threading.Thread | None = None

    def run_async(self, progress: Any, finish: Any) -> None:
        def _run() -> None:
            progress("[fake] import iniciado")
            finish(True, 2, 2)

        self.thread = threading.Thread(target=_run, daemon=True)
        self.thread.start()


def _wait_for_job(engine: Any, timeout: float = 2.0) -> None:
    assert engine.thread is not None
    engine.thread.join(timeout=timeout)
    assert not engine.thread.is_alive(), "el job fake no termino a tiempo"


# ---------------------------------------------------------------------------
# __init__ — estado inicial
# ---------------------------------------------------------------------------


def test_init_state_starts_idle_and_empty(api: Any) -> None:
    assert api._backup_state == "idle"
    assert api._import_state == "idle"
    assert api._backup_log == []
    assert api._import_log == []
    assert api.accounts == []


# ---------------------------------------------------------------------------
# start_backup — patron de jobs async
# ---------------------------------------------------------------------------


def test_start_backup_rejects_double_start_while_running(api: Any) -> None:
    """Doble-click en la UI no debe pisar un backup en curso."""
    api._backup_state = "running"

    result = api.start_backup({"output_dir": "/tmp/x", "accounts": []})

    assert result == {"success": False, "error": "Already running"}


def test_start_backup_requires_output_dir(api: Any) -> None:
    result = api.start_backup({"output_dir": "", "accounts": []})
    assert result["success"] is False
    assert "output_dir" in result["error"]


def test_start_backup_requires_at_least_one_selected_account(api: Any, tmp_path: Path) -> None:
    api.accounts = [SimpleNamespace(smtp_address="kenji@uns-kikaku.com")]

    result = api.start_backup({"output_dir": str(tmp_path), "accounts": ["nope@x.com"]})

    assert result["success"] is False
    assert "No accounts selected" in result["error"]


def test_start_backup_happy_path_updates_state_and_log(
    api: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backup_engine

    monkeypatch.setattr(backup_engine, "BackupEngine", _FakeBackupEngine)
    api.accounts = [SimpleNamespace(smtp_address="kenji@uns-kikaku.com")]

    result = api.start_backup(
        {"output_dir": str(tmp_path), "accounts": ["kenji@uns-kikaku.com"], "format": "pst"}
    )
    _wait_for_job(api._backup_engine)

    assert result == {"success": True}
    assert api._backup_state == "success"
    assert api._backup_result == str(tmp_path) + "/backup_fake"
    assert any("iniciado" in entry["msg"] for entry in api._backup_log)


def test_start_backup_triggers_inventory_export_on_success(
    api: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backup_engine

    monkeypatch.setattr(backup_engine, "BackupEngine", _FakeBackupEngine)

    inventory_calls: list[Any] = []
    monkeypatch.setattr(
        api,
        "_auto_export_inventory",
        lambda **kwargs: inventory_calls.append(kwargs),
    )
    api.accounts = [SimpleNamespace(smtp_address="kenji@uns-kikaku.com")]

    api.start_backup(
        {
            "output_dir": str(tmp_path),
            "accounts": ["kenji@uns-kikaku.com"],
            "export_inventory": True,
        }
    )
    _wait_for_job(api._backup_engine)

    assert len(inventory_calls) == 1


def test_start_backup_marks_failed_on_unexpected_exception(
    api: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backup_engine

    class BrokenEngine:
        def __init__(self, **_kwargs: Any) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(backup_engine, "BackupEngine", BrokenEngine)
    api.accounts = [SimpleNamespace(smtp_address="kenji@uns-kikaku.com")]

    result = api.start_backup({"output_dir": str(tmp_path), "accounts": ["kenji@uns-kikaku.com"]})

    assert result["success"] is False
    assert api._backup_state == "failed"


def test_get_backup_progress_returns_state_and_last_50_log_entries(api: Any) -> None:
    api._backup_state = "running"
    api._backup_log = [{"ts": "t", "msg": f"m{i}"} for i in range(60)]

    progress = api.get_backup_progress()

    assert progress["state"] == "running"
    assert progress["log_count"] == 60
    assert len(progress["log"]) == 50
    assert progress["log"][-1]["msg"] == "m59"


def test_cancel_backup_without_engine_returns_error(api: Any) -> None:
    result = api.cancel_backup()
    assert result == {"success": False, "error": "No backup running"}


def test_cancel_backup_with_engine_delegates_cancel(api: Any) -> None:
    engine = _FakeBackupEngine(output_dir="/tmp")
    api._backup_engine = engine

    result = api.cancel_backup()

    assert result == {"success": True}
    assert engine.cancel_called is True


# ---------------------------------------------------------------------------
# start_import — mismo patron de lock
# ---------------------------------------------------------------------------


def test_start_import_rejects_double_start_while_running(api: Any) -> None:
    api._import_state = "running"
    result = api.start_import({"files": ["a.pst"]})
    assert result == {"success": False, "error": "Already running"}


def test_start_import_requires_files(api: Any) -> None:
    result = api.start_import({"files": []})
    assert result["success"] is False
    assert "No files selected" in result["error"]


def test_start_import_happy_path_updates_state_and_result(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import import_engine

    monkeypatch.setattr(import_engine, "ImportEngine", _FakeImportEngine)
    api.outlook_client = SimpleNamespace()  # ya "conectado", evita connect_outlook real

    result = api.start_import({"files": ["kenji_at_uns-kikaku_com.pst"]})
    _wait_for_job(api._import_engine)

    assert result == {"success": True}
    assert api._import_state == "success"
    assert api._import_result == {"ok_count": 2, "total": 2}


def test_get_import_progress_returns_current_state(api: Any) -> None:
    api._import_state = "failed"
    api._import_result = {"ok_count": 0, "total": 1}

    progress = api.get_import_progress()

    assert progress["state"] == "failed"
    assert progress["result"] == {"ok_count": 0, "total": 1}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_get_config_returns_a_copy_of_current_data(api: Any) -> None:
    cfg = api.get_config()
    assert cfg["domain_filter"] == "uns-kikaku.com"


def test_set_config_persists_value(api: Any, isolated_config: Path) -> None:
    result = api.set_config("domain_filter", "example.com")

    assert result == {"success": True}
    assert (isolated_config / "config.json").exists()

    # Un nuevo Config() leyendo el mismo dir debe ver el cambio persistido
    import config

    reloaded = config.Config()
    assert reloaded.get("domain_filter") == "example.com"


def test_update_config_sets_multiple_keys_at_once(api: Any) -> None:
    result = api.update_config({"schedule_enabled": True, "schedule_keep_last": 10})

    assert result == {"success": True}
    assert api.config.get("schedule_enabled") is True
    assert api.config.get("schedule_keep_last") == 10


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_list_history_returns_backups_from_configured_dir(api: Any, tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup_20260101_000000"
    backup_dir.mkdir()
    (backup_dir / "report.json").write_text(
        '{"start_time": "2026-01-01T00:00:00", "accounts_processed": [{"success": true}]}',
        encoding="utf-8",
    )

    result = api.list_history(str(tmp_path))

    assert result["success"] is True
    assert len(result["backups"]) == 1


def test_delete_history_reports_failure_when_backup_missing(api: Any, tmp_path: Path) -> None:
    api.config.set("default_backup_dir", str(tmp_path))

    result = api.delete_history(str(tmp_path / "backup_does_not_exist"))

    assert result == {"success": False, "error": "Could not delete"}


def test_get_backup_history_is_alias_for_list_history(api: Any, tmp_path: Path) -> None:
    assert api.get_backup_history(str(tmp_path)) == api.list_history(str(tmp_path))


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


def test_save_schedule_requires_frequency_and_time(api: Any) -> None:
    result = api.save_schedule({"day_of_week": "MON"})
    assert result["success"] is False
    assert "obligatorios" in result["error"]


def test_save_schedule_creates_task_and_persists_config(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler

    captured: dict = {}
    monkeypatch.setattr(
        scheduler,
        "create_task",
        lambda **kwargs: captured.update(kwargs) or True,
    )

    result = api.save_schedule(
        {"frequency": "weekly", "time": "02:00", "day_of_week": "TUE", "keep_last": 3}
    )

    assert result == {"success": True}
    assert captured["frequency"] == "weekly"
    assert api.config.get("schedule_enabled") is True
    assert api.config.get("schedule_keep_last") == 3


def test_remove_schedule_deletes_task_and_disables_config(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler

    monkeypatch.setattr(scheduler, "delete_task", lambda: True)
    api.config.set("schedule_enabled", True)

    result = api.remove_schedule()

    assert result == {"success": True}
    assert api.config.get("schedule_enabled") is False


def test_get_schedule_info_reports_inactive_when_task_does_not_exist(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scheduler

    monkeypatch.setattr(scheduler, "task_exists", lambda: False)

    result = api.get_schedule_info()

    assert result == {"success": True, "active": False, "info": None}


# ---------------------------------------------------------------------------
# Connection tester
# ---------------------------------------------------------------------------


def test_test_connection_requires_smtp(api: Any) -> None:
    result = api.test_connection({})
    assert result == {"success": False, "error": "smtp required"}


def test_test_connection_delegates_to_connection_tester(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import connection_tester

    monkeypatch.setattr(
        connection_tester,
        "test_account_connection",
        lambda smtp, protocol="auto", timeout=10: {"success": True, "smtp": smtp},
    )

    result = api.test_connection({"smtp": "kenji@uns-kikaku.com"})
    assert result == {"success": True, "smtp": "kenji@uns-kikaku.com"}


# ---------------------------------------------------------------------------
# Cuentas
# ---------------------------------------------------------------------------


def test_detect_accounts_maps_matches_domain(api: Any) -> None:
    from outlook.fakes import FakeOutlookAccount

    api.outlook_client = SimpleNamespace(
        list_accounts=lambda: [
            FakeOutlookAccount(smtp_address="kenji@uns-kikaku.com", display_name="Kenji"),
            FakeOutlookAccount(smtp_address="ext@gmail.com", display_name="Externo"),
        ]
    )

    result = api.detect_accounts()

    assert result["success"] is True
    matches = {a["smtp"]: a["matches_domain"] for a in result["accounts"]}
    assert matches["kenji@uns-kikaku.com"] is True
    assert matches["ext@gmail.com"] is False


def test_estimate_backup_size_without_detected_accounts_fails(api: Any) -> None:
    result = api.estimate_backup_size(["kenji@uns-kikaku.com"])
    assert result == {"success": False, "error": "No accounts detected yet"}


def test_estimate_backup_size_sums_inbox_counts(api: Any) -> None:
    from outlook.fakes import FakeOutlookAccount

    account = FakeOutlookAccount(smtp_address="kenji@uns-kikaku.com")
    api.accounts = [account]
    api.outlook_client = SimpleNamespace(
        get_account_inbox=lambda _acc: SimpleNamespace(Items=SimpleNamespace(Count=42))
    )

    result = api.estimate_backup_size(["kenji@uns-kikaku.com"])

    assert result["success"] is True
    assert result["total_emails"] == 42


def test_estimate_backup_size_end_to_end_with_real_outlook_client(api: Any) -> None:
    """Regresion: `get_account_inbox` no existia en OutlookClient (bug real,
    la estimacion siempre devolvia 0 en produccion). Prueba la cadena
    completa api -> OutlookClient real -> FakeNamespace/FakeStore."""
    from outlook.fakes import FakeItems, FakeMailItem, FakeNamespace, FakeOutlookAccount, FakeStore
    from outlook_client import OL_FOLDER_INBOX, OutlookClient

    store = FakeStore(DisplayName="kenji@uns-kikaku.com")
    store.GetDefaultFolder(OL_FOLDER_INBOX).Items = FakeItems(
        [FakeMailItem(), FakeMailItem(), FakeMailItem()]
    )
    client = OutlookClient.__new__(OutlookClient)
    client.app = None
    client.namespace = FakeNamespace(stores=[store])

    api.outlook_client = client
    api.accounts = [FakeOutlookAccount(smtp_address="kenji@uns-kikaku.com")]

    result = api.estimate_backup_size(["kenji@uns-kikaku.com"])

    assert result["success"] is True
    assert result["total_emails"] == 3


# ---------------------------------------------------------------------------
# App info
# ---------------------------------------------------------------------------


def test_get_app_info_matches_pyproject_version() -> None:
    import re

    from api import API

    api_instance = API.__new__(API)  # no necesita config para este metodo
    info = api_instance.get_app_info()

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    assert info["version"] == match.group(1)
