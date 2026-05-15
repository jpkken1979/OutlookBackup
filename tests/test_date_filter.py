"""Tests directos del modulo `date_filter` (Fase 6 partial plan v3.2).

Cubre:
- `parse_iso_date(s)` — strict ISO 8601 parsing
- `should_include(received, from, to)` — predicate puro con boundary cases
- `filter_pst_items(root, from, to)` — con fake folder + fake items
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from unittest.mock import MagicMock

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# parse_iso_date
# ---------------------------------------------------------------------------


def test_parse_iso_date_valid() -> None:
    from date_filter import parse_iso_date

    assert parse_iso_date("2026-05-13") == datetime.date(2026, 5, 13)
    assert parse_iso_date("2000-01-01") == datetime.date(2000, 1, 1)


def test_parse_iso_date_returns_none_for_none_or_empty() -> None:
    from date_filter import parse_iso_date

    assert parse_iso_date(None) is None
    assert parse_iso_date("") is None


def test_parse_iso_date_rejects_non_iso_formats() -> None:
    """Solo ISO 8601. NO acepta DD/MM/YYYY, MM-DD-YYYY, etc."""
    from date_filter import parse_iso_date

    assert parse_iso_date("13/05/2026") is None
    assert parse_iso_date("05-13-2026") is None
    assert parse_iso_date("garbage") is None
    assert parse_iso_date("2026-13-45") is None  # mes invalido


# ---------------------------------------------------------------------------
# should_include
# ---------------------------------------------------------------------------


def test_should_include_no_filter_accepts_all() -> None:
    """Sin date_from ni date_to: incluir todo (no-op filter)."""
    from date_filter import should_include

    assert should_include(datetime.datetime(2026, 5, 13), None, None) is True
    assert should_include(None, None, None) is True
    assert should_include(datetime.date(1990, 1, 1), None, None) is True


def test_should_include_only_from() -> None:
    """Solo date_from: incluir si received >= date_from."""
    from date_filter import should_include

    cutoff = datetime.date(2026, 1, 1)
    assert should_include(datetime.datetime(2026, 5, 13), cutoff, None) is True
    assert should_include(datetime.datetime(2026, 1, 1), cutoff, None) is True  # boundary
    assert should_include(datetime.datetime(2025, 12, 31), cutoff, None) is False


def test_should_include_only_to() -> None:
    """Solo date_to: incluir si received <= date_to."""
    from date_filter import should_include

    cutoff = datetime.date(2026, 5, 13)
    assert should_include(datetime.datetime(2026, 1, 1), None, cutoff) is True
    assert should_include(datetime.datetime(2026, 5, 13), None, cutoff) is True  # boundary
    assert should_include(datetime.datetime(2026, 6, 1), None, cutoff) is False


def test_should_include_both_bounds() -> None:
    """Ambos: incluir si date_from <= received <= date_to."""
    from date_filter import should_include

    start = datetime.date(2026, 1, 1)
    end = datetime.date(2026, 12, 31)
    assert should_include(datetime.datetime(2026, 5, 13), start, end) is True
    assert should_include(datetime.datetime(2026, 1, 1), start, end) is True
    assert should_include(datetime.datetime(2026, 12, 31), start, end) is True
    assert should_include(datetime.datetime(2025, 12, 31), start, end) is False
    assert should_include(datetime.datetime(2027, 1, 1), start, end) is False


def test_should_include_none_received_with_filter_excludes() -> None:
    """Si filter activo y received es None: excluir (conservative)."""
    from date_filter import should_include

    assert should_include(None, datetime.date(2026, 1, 1), None) is False
    assert should_include(None, None, datetime.date(2026, 12, 31)) is False


def test_should_include_accepts_date_or_datetime() -> None:
    """Funciona con datetime.date Y datetime.datetime."""
    from date_filter import should_include

    cutoff = datetime.date(2026, 5, 13)
    # Pasar datetime con tiempo > 00:00 — debe normalizar a date
    dt_with_time = datetime.datetime(2026, 5, 13, 23, 59, 59)
    assert should_include(dt_with_time, cutoff, cutoff) is True
    # Pasar date directamente
    assert should_include(datetime.date(2026, 5, 13), cutoff, cutoff) is True


# ---------------------------------------------------------------------------
# filter_pst_items
# ---------------------------------------------------------------------------


class FakeItem:
    def __init__(self, received: datetime.datetime | None) -> None:
        self.ReceivedTime = received
        self.deleted = False

    def Delete(self) -> None:
        self.deleted = True


class FakeFolder:
    def __init__(self, items: list[FakeItem], subfolders: list[FakeFolder] | None = None) -> None:
        self._items = items
        self._subfolders = subfolders or []

    @property
    def Items(self) -> list[FakeItem]:
        # Outlook COM Items NO soporta builtin remove from list during iteration,
        # pero filter_pst_items hace list() snapshot por safety. Devolvemos los
        # items no-borrados para simular el comportamiento de Outlook.
        return [i for i in self._items if not i.deleted]

    @property
    def Folders(self) -> list[FakeFolder]:
        return self._subfolders


def test_filter_pst_items_noop_when_no_filter() -> None:
    """Sin filter (ambos None): retorna 0, no toca nada."""
    from date_filter import filter_pst_items

    items = [FakeItem(datetime.datetime(2026, 5, 13)) for _ in range(3)]
    folder = FakeFolder(items)
    assert filter_pst_items(folder, None, None) == 0
    assert all(not i.deleted for i in items)


def test_filter_pst_items_deletes_out_of_range() -> None:
    """Borra solo items fuera del rango."""
    from date_filter import filter_pst_items

    items = [
        FakeItem(datetime.datetime(2025, 12, 31)),  # antes de from
        FakeItem(datetime.datetime(2026, 1, 1)),  # dentro
        FakeItem(datetime.datetime(2026, 5, 13)),  # dentro
        FakeItem(datetime.datetime(2027, 1, 1)),  # despues de to
    ]
    folder = FakeFolder(items)

    deleted = filter_pst_items(folder, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))

    assert deleted == 2
    assert items[0].deleted is True
    assert items[1].deleted is False
    assert items[2].deleted is False
    assert items[3].deleted is True


def test_filter_pst_items_recurses_into_subfolders() -> None:
    """Recorre subfolders recursivamente."""
    from date_filter import filter_pst_items

    inbox_items = [
        FakeItem(datetime.datetime(2025, 1, 1)),
        FakeItem(datetime.datetime(2026, 5, 13)),
    ]
    sent_items = [FakeItem(datetime.datetime(2027, 1, 1))]

    inbox = FakeFolder(inbox_items)
    sent = FakeFolder(sent_items)
    root = FakeFolder([], subfolders=[inbox, sent])

    deleted = filter_pst_items(root, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))

    assert deleted == 2  # 1 en inbox + 1 en sent
    assert inbox_items[0].deleted is True
    assert inbox_items[1].deleted is False
    assert sent_items[0].deleted is True


def test_filter_pst_items_calls_progress_cb_with_count() -> None:
    """Si hay items eliminados, llama progress_cb con mensaje japones."""
    from date_filter import filter_pst_items

    items = [FakeItem(datetime.datetime(2024, 1, 1))]
    folder = FakeFolder(items)

    messages: list[str] = []
    deleted = filter_pst_items(folder, datetime.date(2026, 1, 1), None, progress_cb=messages.append)

    assert deleted == 1
    assert len(messages) == 1
    assert "削除" in messages[0]  # japones para "deleted"


def test_filter_pst_items_no_progress_cb_when_zero_deleted() -> None:
    """Si no se borro nada, NO llama progress_cb (no spam)."""
    from date_filter import filter_pst_items

    items = [FakeItem(datetime.datetime(2026, 5, 13))]
    folder = FakeFolder(items)

    messages: list[str] = []
    deleted = filter_pst_items(
        folder, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), progress_cb=messages.append
    )

    assert deleted == 0
    assert messages == []


def test_filter_pst_items_handles_item_without_received_time() -> None:
    """Items sin ReceivedTime (ej: meeting requests) NO crashean."""
    from date_filter import filter_pst_items

    weird_item = MagicMock(spec=[])  # No tiene ReceivedTime
    weird_item.Delete = MagicMock()

    folder_mock = MagicMock()
    folder_mock.Items = [weird_item]
    folder_mock.Folders = []

    # No deberia crashear, deberia tratarlo como received=None y excluirlo si filter activo
    deleted = filter_pst_items(folder_mock, datetime.date(2026, 1, 1), None)
    assert deleted == 1  # se borra porque received=None + filter activo


def test_filter_pst_items_handles_folder_without_items() -> None:
    """Folder sin items (ej: contacts folder) NO crashea."""
    from date_filter import filter_pst_items

    weird_folder = MagicMock(spec=[])  # No tiene Items ni Folders

    deleted = filter_pst_items(weird_folder, datetime.date(2026, 1, 1), None)
    assert deleted == 0
