"""Tests directos del modulo `history_manager`.

Cubre:
- list_backups: lectura de report.json, orden desc por start_time, status derivado
- delete_backup: happy path + guardas de seguridad (path traversal, nombre invalido)
- cleanup_old: borra solo backups exitosos mas viejos que keep_last, respeta limites
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _make_backup(
    base_dir: Path,
    name: str,
    start_time: str,
    accounts_success: list[bool] | None = None,
    write_report: bool = True,
) -> Path:
    """Crea una carpeta backup_{name}/ con su report.json."""
    backup_dir = base_dir / name
    backup_dir.mkdir(parents=True)

    if write_report:
        accounts_success = accounts_success if accounts_success is not None else [True]
        report = {
            "start_time": start_time,
            "end_time": start_time,
            "duration_seconds": 10,
            "accounts_processed": [
                {"smtp": f"user{i}@uns-kikaku.com", "success": ok, "size_mb": 1.0}
                for i, ok in enumerate(accounts_success)
            ],
            "total_emails": 5,
            "errors": [] if all(accounts_success) else [{"msg": "fallo"}],
        }
        (backup_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")

    return backup_dir


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------


def test_list_backups_empty_when_base_dir_missing(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    history = BackupHistory(str(tmp_path / "does_not_exist"))
    assert history.list_backups() == []


def test_list_backups_reads_report_and_computes_status(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_20260101_000000", "2026-01-01T00:00:00", [True, True])
    _make_backup(tmp_path, "backup_20260102_000000", "2026-01-02T00:00:00", [True, False])
    _make_backup(tmp_path, "backup_20260103_000000", "2026-01-03T00:00:00", [False])

    history = BackupHistory(str(tmp_path))
    backups = history.list_backups()

    statuses = {b["name"]: b["status"] for b in backups}
    assert statuses["backup_20260101_000000"] == "success"
    assert statuses["backup_20260102_000000"] == "partial"
    assert statuses["backup_20260103_000000"] == "failed"


def test_list_backups_sorted_descending_by_start_time(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_old", "2026-01-01T00:00:00")
    _make_backup(tmp_path, "backup_new", "2026-01-03T00:00:00")
    _make_backup(tmp_path, "backup_mid", "2026-01-02T00:00:00")

    history = BackupHistory(str(tmp_path))
    names = [b["name"] for b in history.list_backups()]

    assert names == ["backup_new", "backup_mid", "backup_old"]


def test_list_backups_ignores_non_backup_folders(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_valid", "2026-01-01T00:00:00")
    (tmp_path / "other_folder").mkdir()
    (tmp_path / "not_a_dir.txt").write_text("x", encoding="utf-8")

    history = BackupHistory(str(tmp_path))
    names = [b["name"] for b in history.list_backups()]

    assert names == ["backup_valid"]


def test_list_backups_without_report_json_marked_incomplete(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_no_report", "2026-01-01T00:00:00", write_report=False)

    history = BackupHistory(str(tmp_path))
    backups = history.list_backups()

    assert len(backups) == 1
    assert backups[0]["status"] == "incomplete"
    assert backups[0]["start_time"] is not None  # cae al mtime de la carpeta


# ---------------------------------------------------------------------------
# delete_backup
# ---------------------------------------------------------------------------


def test_delete_backup_removes_directory(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    backup_dir = _make_backup(tmp_path, "backup_to_delete", "2026-01-01T00:00:00")
    history = BackupHistory(str(tmp_path))

    assert history.delete_backup(str(backup_dir)) is True
    assert not backup_dir.exists()


def test_delete_backup_returns_false_when_missing(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    history = BackupHistory(str(tmp_path))
    assert history.delete_backup(str(tmp_path / "backup_ghost")) is False


def test_delete_backup_rejects_path_outside_base_dir(tmp_path: Path) -> None:
    """Guarda de seguridad: no debe borrar nada fuera de base_dir."""
    from history_manager import BackupHistory

    outside_dir = tmp_path.parent / f"backup_outside_{tmp_path.name}"
    outside_dir.mkdir(exist_ok=True)
    try:
        base_dir = tmp_path / "backups"
        base_dir.mkdir()
        history = BackupHistory(str(base_dir))

        assert history.delete_backup(str(outside_dir)) is False
        assert outside_dir.exists()
    finally:
        if outside_dir.exists():
            outside_dir.rmdir()


def test_delete_backup_rejects_name_not_starting_with_backup_prefix(tmp_path: Path) -> None:
    """Guarda de seguridad: solo borra carpetas nombradas backup_*."""
    from history_manager import BackupHistory

    suspicious_dir = tmp_path / "not_a_backup_folder"
    suspicious_dir.mkdir()

    history = BackupHistory(str(tmp_path))

    assert history.delete_backup(str(suspicious_dir)) is False
    assert suspicious_dir.exists()


# ---------------------------------------------------------------------------
# cleanup_old
# ---------------------------------------------------------------------------


def test_cleanup_old_deletes_oldest_successful_beyond_keep_last(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    for i in range(5):
        _make_backup(tmp_path, f"backup_{i}", f"2026-01-0{i + 1}T00:00:00", [True])

    history = BackupHistory(str(tmp_path))
    deleted = history.cleanup_old(keep_last=2)

    remaining = {b["name"] for b in history.list_backups()}
    assert remaining == {"backup_3", "backup_4"}
    assert len(deleted) == 3


def test_cleanup_old_never_deletes_failed_or_partial_backups(tmp_path: Path) -> None:
    """Los backups fallidos se mantienen aunque superen keep_last (para revisar)."""
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_ok_1", "2026-01-01T00:00:00", [True])
    _make_backup(tmp_path, "backup_ok_2", "2026-01-02T00:00:00", [True])
    _make_backup(tmp_path, "backup_ok_3", "2026-01-03T00:00:00", [True])
    _make_backup(tmp_path, "backup_failed", "2026-01-04T00:00:00", [False])

    history = BackupHistory(str(tmp_path))
    history.cleanup_old(keep_last=1)

    remaining = {b["name"] for b in history.list_backups()}
    assert "backup_failed" in remaining
    assert "backup_ok_3" in remaining  # el exitoso mas reciente se conserva


def test_cleanup_old_noop_when_successful_count_within_keep_last(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_1", "2026-01-01T00:00:00", [True])
    _make_backup(tmp_path, "backup_2", "2026-01-02T00:00:00", [False])

    history = BackupHistory(str(tmp_path))
    deleted = history.cleanup_old(keep_last=5)

    assert deleted == []
    assert len(history.list_backups()) == 2


def test_cleanup_old_with_zero_or_negative_keep_last_is_noop(tmp_path: Path) -> None:
    from history_manager import BackupHistory

    _make_backup(tmp_path, "backup_1", "2026-01-01T00:00:00", [True])

    history = BackupHistory(str(tmp_path))

    assert history.cleanup_old(keep_last=0) == []
    assert history.cleanup_old(keep_last=-1) == []
    assert len(history.list_backups()) == 1
