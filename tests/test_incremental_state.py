"""Tests directos del modulo `incremental_state` (Feature A plan v3.2).

Cubre:
- Persistence (write + read)
- Estado vacio cuando archivo no existe
- update_last_backup autosave
- get_last_backup retorna datetime parseado
- clear / clear_all
- Edge cases: archivo corrupto, version mismatch
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Construccion + carga
# ---------------------------------------------------------------------------


def test_load_returns_empty_when_file_missing(tmp_path: Path) -> None:
    """Sin archivo previo, state arranca vacio sin errores."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.all_tracked_smtps() == []
    assert state.get_last_backup("anyone@example.com") is None


def test_load_reads_existing_file(tmp_path: Path) -> None:
    """Archivo existente es leido correctamente."""
    from incremental_state import STATE_FILENAME, STATE_VERSION, IncrementalState

    payload = {
        "version": STATE_VERSION,
        "last_backup_by_smtp": {
            "kenji@uns-kikaku.com": "2026-05-13T14:23:12",
            "info@uns-kikaku.com": "2026-05-12T08:00:00",
        },
    }
    (tmp_path / STATE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.get_last_backup("kenji@uns-kikaku.com") == datetime.datetime(2026, 5, 13, 14, 23, 12)
    assert state.get_last_backup("info@uns-kikaku.com") == datetime.datetime(2026, 5, 12, 8, 0, 0)


def test_load_resets_on_corrupted_json(tmp_path: Path) -> None:
    """JSON invalido: warning + state vacio (no crash)."""
    from incremental_state import STATE_FILENAME, IncrementalState

    (tmp_path / STATE_FILENAME).write_text("{not json", encoding="utf-8")

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.all_tracked_smtps() == []


def test_load_resets_on_version_mismatch(tmp_path: Path) -> None:
    """Version distinta: warning + reset (no migration todavia)."""
    from incremental_state import STATE_FILENAME, IncrementalState

    payload = {
        "version": 999,
        "last_backup_by_smtp": {"old@example.com": "2026-01-01T00:00:00"},
    }
    (tmp_path / STATE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.get_last_backup("old@example.com") is None


def test_load_handles_unexpected_format(tmp_path: Path) -> None:
    """Si last_backup_by_smtp no es dict, warning + reset."""
    from incremental_state import STATE_FILENAME, STATE_VERSION, IncrementalState

    payload = {"version": STATE_VERSION, "last_backup_by_smtp": "garbage"}
    (tmp_path / STATE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.all_tracked_smtps() == []


# ---------------------------------------------------------------------------
# update_last_backup + persistence
# ---------------------------------------------------------------------------


def test_update_last_backup_persists_to_disk(tmp_path: Path) -> None:
    """update_last_backup debe persistir y otra carga debe leer el valor."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    ts = datetime.datetime(2026, 5, 13, 10, 30, 45)
    state.update_last_backup("kenji@uns-kikaku.com", ts)

    # Re-cargar y verificar
    state2 = IncrementalState.load(config_dir=tmp_path)
    assert state2.get_last_backup("kenji@uns-kikaku.com") == ts


def test_update_last_backup_uses_now_when_ts_none(tmp_path: Path) -> None:
    """Sin ts explicito, usa now()."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    before = datetime.datetime.now()
    state.update_last_backup("kenji@uns-kikaku.com")
    after = datetime.datetime.now()

    saved = state.get_last_backup("kenji@uns-kikaku.com")
    assert saved is not None
    # Tolerancia: el ts esta entre before y after (con segundos truncados)
    assert before.replace(microsecond=0) <= saved <= after.replace(microsecond=0) + datetime.timedelta(seconds=1)


def test_update_overrides_previous_value(tmp_path: Path) -> None:
    """Updates subsecuentes pisan el valor anterior."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    state.update_last_backup("kenji@uns-kikaku.com", datetime.datetime(2026, 1, 1))
    state.update_last_backup("kenji@uns-kikaku.com", datetime.datetime(2026, 5, 13))

    assert state.get_last_backup("kenji@uns-kikaku.com") == datetime.datetime(2026, 5, 13)


def test_update_multiple_accounts(tmp_path: Path) -> None:
    """Multi-cuenta: cada SMTP tiene su propio timestamp."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    state.update_last_backup("a@example.com", datetime.datetime(2026, 5, 13))
    state.update_last_backup("b@example.com", datetime.datetime(2026, 5, 12))

    assert state.get_last_backup("a@example.com") == datetime.datetime(2026, 5, 13)
    assert state.get_last_backup("b@example.com") == datetime.datetime(2026, 5, 12)
    assert sorted(state.all_tracked_smtps()) == ["a@example.com", "b@example.com"]


# ---------------------------------------------------------------------------
# get_last_backup edge cases
# ---------------------------------------------------------------------------


def test_get_last_backup_unknown_smtp_returns_none(tmp_path: Path) -> None:
    """Cuenta nunca trackeada: None (debe hacerse full)."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.get_last_backup("never_seen@example.com") is None


def test_get_last_backup_corrupted_timestamp_returns_none(tmp_path: Path) -> None:
    """Timestamp invalido en disco: None + warning (no crash)."""
    from incremental_state import STATE_FILENAME, STATE_VERSION, IncrementalState

    payload = {
        "version": STATE_VERSION,
        "last_backup_by_smtp": {"x@example.com": "garbage timestamp"},
    }
    (tmp_path / STATE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    state = IncrementalState.load(config_dir=tmp_path)
    assert state.get_last_backup("x@example.com") is None


# ---------------------------------------------------------------------------
# clear / clear_all
# ---------------------------------------------------------------------------


def test_clear_removes_single_smtp(tmp_path: Path) -> None:
    """clear(smtp) borra solo esa cuenta."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    state.update_last_backup("a@example.com", datetime.datetime(2026, 5, 13))
    state.update_last_backup("b@example.com", datetime.datetime(2026, 5, 12))

    state.clear("a@example.com")

    assert state.get_last_backup("a@example.com") is None
    assert state.get_last_backup("b@example.com") == datetime.datetime(2026, 5, 12)


def test_clear_unknown_smtp_no_op(tmp_path: Path) -> None:
    """clear(unknown) no debe crashear."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    state.clear("never_existed@example.com")  # no crash
    assert state.all_tracked_smtps() == []


def test_clear_all_resets_state(tmp_path: Path) -> None:
    """clear_all() vacia todo y persiste."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    state.update_last_backup("a@example.com", datetime.datetime(2026, 5, 13))
    state.update_last_backup("b@example.com", datetime.datetime(2026, 5, 12))

    state.clear_all()

    state2 = IncrementalState.load(config_dir=tmp_path)
    assert state2.all_tracked_smtps() == []


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def test_atomic_write_no_tmp_leftover(tmp_path: Path) -> None:
    """Despues de update, no debe haber archivos .tmp huerfanos."""
    from incremental_state import IncrementalState

    state = IncrementalState.load(config_dir=tmp_path)
    state.update_last_backup("a@example.com", datetime.datetime(2026, 5, 13))

    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_creates_parent_dir_if_missing(tmp_path: Path) -> None:
    """Si el config dir no existe todavia, lo crea."""
    from incremental_state import IncrementalState

    sub = tmp_path / "deep" / "nested" / "dir"
    state = IncrementalState.load(config_dir=sub)
    state.update_last_backup("a@example.com", datetime.datetime(2026, 5, 13))
    assert sub.is_dir()
