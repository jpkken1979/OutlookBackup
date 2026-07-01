"""Tests directos del modulo `scheduler` (wrapper de schtasks.exe).

Cubre:
- _run_schtasks: construccion de comando, shell=False implicito (subprocess.run
  con lista de args, nunca string+shell=True), manejo de FileNotFoundError/timeout
- task_exists / get_task_info / delete_task / run_task_now: interpretacion de
  returncode y de excepciones
- create_task: argumentos correctos por frecuencia (daily/weekly/biweekly/
  monthly/custom), frecuencia invalida
- calculate_next_run: proxima ejecucion estimada por frecuencia
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _fake_run(returncode: int = 0, stdout: str = "", stderr: str = "") -> object:
    """Crea un stand-in de subprocess.run que devuelve un CompletedProcess fijo."""

    def _run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr=stderr
        )

    return _run


# ---------------------------------------------------------------------------
# _run_schtasks
# ---------------------------------------------------------------------------


def test_run_schtasks_calls_subprocess_with_arg_list_not_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nunca debe usar shell=True — siempre lista de args (regla security.md)."""
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    scheduler._run_schtasks(["/Query", "/TN", scheduler.TASK_NAME])

    assert captured["cmd"] == ["schtasks", "/Query", "/TN", scheduler.TASK_NAME]
    assert isinstance(captured["cmd"], list)
    assert captured["kwargs"].get("shell") is not True


def test_run_schtasks_raises_runtime_error_on_file_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scheduler

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="schtasks.exe no encontrado"):
        scheduler._run_schtasks(["/Query"])


def test_run_schtasks_raises_runtime_error_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="timeout"):
        scheduler._run_schtasks(["/Query"])


def test_run_schtasks_uses_create_no_window_flag_only_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    monkeypatch.setattr(scheduler, "os", SimpleNamespace(name="posix"))

    scheduler._run_schtasks(["/Query"])

    assert captured["kwargs"]["creationflags"] == 0


# ---------------------------------------------------------------------------
# task_exists / delete_task / run_task_now — interpretacion de returncode
# ---------------------------------------------------------------------------


def test_task_exists_true_when_returncode_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=0))
    assert scheduler.task_exists() is True


def test_task_exists_false_when_returncode_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=1))
    assert scheduler.task_exists() is False


def test_task_exists_false_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    assert scheduler.task_exists() is False


def test_delete_task_true_when_returncode_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=0))
    assert scheduler.delete_task() is True


def test_delete_task_false_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    assert scheduler.delete_task() is False


def test_run_task_now_true_when_returncode_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=0))
    assert scheduler.run_task_now() is True


# ---------------------------------------------------------------------------
# get_task_info
# ---------------------------------------------------------------------------


def test_get_task_info_parses_csv_output(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    csv_output = (
        "HostName,TaskName,Next Run Time,Status,Last Run Time,Last Result,Schedule\r\n"
        '"HOST","\\UNS-Outlook-Backup-Auto","2026-07-02 02:00:00","Ready",'
        '"2026-06-25 02:00:00","0","Weekly"\r\n'
    )
    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=0, stdout=csv_output))

    info = scheduler.get_task_info()

    assert info is not None
    assert info["next_run"] == "2026-07-02 02:00:00"
    assert info["status"] == "Ready"
    assert info["last_result"] == "0"


def test_get_task_info_none_when_returncode_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=1))
    assert scheduler.get_task_info() is None


def test_get_task_info_none_when_output_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.subprocess, "run", _fake_run(returncode=0, stdout=""))
    assert scheduler.get_task_info() is None


def test_get_task_info_none_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    assert scheduler.get_task_info() is None


# ---------------------------------------------------------------------------
# create_task — construccion de argumentos por frecuencia
# ---------------------------------------------------------------------------


def test_create_task_daily_builds_correct_args(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    assert scheduler.create_task("daily", "02:00") is True
    assert "/SC" in captured["cmd"] and "DAILY" in captured["cmd"]
    assert "/ST" in captured["cmd"] and "02:00" in captured["cmd"]
    assert "/TN" in captured["cmd"] and scheduler.TASK_NAME in captured["cmd"]


def test_create_task_weekly_builds_correct_args(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    scheduler.create_task("weekly", "02:00", day_of_week="TUE")

    idx = captured["cmd"].index("/SC")
    assert captured["cmd"][idx : idx + 2] == ["/SC", "WEEKLY"]
    assert "/D" in captured["cmd"] and "TUE" in captured["cmd"]


def test_create_task_biweekly_uses_weekly_with_mo_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """schtasks no tiene 'biweekly' nativo: WEEKLY + /MO 2."""
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    scheduler.create_task("biweekly", "02:00", day_of_week="MON")

    assert "WEEKLY" in captured["cmd"]
    mo_idx = captured["cmd"].index("/MO")
    assert captured["cmd"][mo_idx + 1] == "2"


def test_create_task_monthly_runs_on_day_1(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    scheduler.create_task("monthly", "02:00")

    assert "MONTHLY" in captured["cmd"]
    d_idx = captured["cmd"].index("/D")
    assert captured["cmd"][d_idx + 1] == "1"


def test_create_task_custom_uses_daily_with_mo_days(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    scheduler.create_task("custom", "02:00", custom_days=10)

    assert "DAILY" in captured["cmd"]
    mo_idx = captured["cmd"].index("/MO")
    assert captured["cmd"][mo_idx + 1] == "10"


def test_create_task_custom_days_clamped_to_minimum_one(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    captured: dict = {}

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    scheduler.create_task("custom", "02:00", custom_days=0)

    mo_idx = captured["cmd"].index("/MO")
    assert captured["cmd"][mo_idx + 1] == "1"


def test_create_task_unknown_frequency_raises_value_error() -> None:
    import scheduler

    with pytest.raises(ValueError, match="Frecuencia desconocida"):
        scheduler.create_task("yearly", "02:00")


def test_create_task_returns_false_when_schtasks_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(
        scheduler.subprocess, "run", _fake_run(returncode=1, stderr="access denied")
    )
    assert scheduler.create_task("daily", "02:00") is False


def test_create_task_returns_false_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    def fake_run(cmd: list, **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    assert scheduler.create_task("daily", "02:00") is False


# ---------------------------------------------------------------------------
# get_app_executable
# ---------------------------------------------------------------------------


def test_get_app_executable_frozen_returns_bare_exe(monkeypatch: pytest.MonkeyPatch) -> None:
    import scheduler

    monkeypatch.setattr(scheduler.sys, "frozen", True, raising=False)
    monkeypatch.setattr(scheduler.sys, "executable", "C:\\Program Files\\UNS\\app.exe")

    assert scheduler.get_app_executable() == "C:\\Program Files\\UNS\\app.exe"


def test_get_app_executable_dev_mode_quotes_python_and_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scheduler

    monkeypatch.delattr(scheduler.sys, "frozen", raising=False)
    monkeypatch.setattr(scheduler.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(scheduler.sys, "argv", ["/repo/src/main.py"])

    result = scheduler.get_app_executable()

    assert result.startswith('"/usr/bin/python3" "')
    assert result.endswith('main.py"')


# ---------------------------------------------------------------------------
# calculate_next_run
# ---------------------------------------------------------------------------


def test_calculate_next_run_returns_error_marker_on_bad_input() -> None:
    import scheduler

    assert scheduler.calculate_next_run("daily", "not-a-time") == "(計算できません)"


def test_calculate_next_run_weekly_lands_on_requested_weekday() -> None:
    import datetime

    import scheduler

    result = scheduler.calculate_next_run("weekly", "02:00", day_of_week="WED")
    parsed = datetime.datetime.strptime(result, "%Y-%m-%d %H:%M")

    assert parsed.weekday() == 2  # WED
    assert parsed.hour == 2 and parsed.minute == 0


def test_calculate_next_run_monthly_lands_on_day_one() -> None:
    import datetime

    import scheduler

    result = scheduler.calculate_next_run("monthly", "02:00")
    parsed = datetime.datetime.strptime(result, "%Y-%m-%d %H:%M")

    assert parsed.day == 1


def test_calculate_next_run_custom_adds_days_offset() -> None:
    import datetime

    import scheduler

    result = scheduler.calculate_next_run("custom", "23:59", custom_days=5)
    parsed = datetime.datetime.strptime(result, "%Y-%m-%d %H:%M")
    now = datetime.datetime.now()

    delta_days = (parsed.date() - now.date()).days
    assert delta_days in (4, 5)  # +4 dias desde "hoy" segun redondeo de hora
