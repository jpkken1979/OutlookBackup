"""Tests directos de `pst_inspector.PSTInspector`.

Monta un PST temporalmente (AddStore), lo recorre, lo desmonta (RemoveStore).
`src/outlook/fakes.py` no cubre `Items.Item(i)` (indexado 1-based estilo COM,
usado para samplear senders/fechas), asi que se usan fakes locales minimos.

Cubre:
- Archivo inexistente -> error sin intentar montar
- Happy path: monta, encuentra el store, recorre carpetas, desmonta,
  calcula date_range y top_senders
- Store no encontrado tras AddStore -> error, se queda "mounted" (no llega
  a RemoveStore)
- Excepcion inesperada durante el proceso se atrapa en `result["error"]`
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _PstItem:
    def __init__(self, sender: str = "", received_time: datetime | None = None) -> None:
        self.SenderEmailAddress = sender
        self.ReceivedTime = received_time


class _PstItems:
    def __init__(self, items: list[_PstItem]) -> None:
        self._items = items

    @property
    def Count(self) -> int:
        return len(self._items)

    def Item(self, index: int) -> _PstItem:
        return self._items[index - 1]  # COM es 1-indexed


class _PstFolder:
    def __init__(
        self, name: str, items: _PstItems | None = None, folders: list[_PstFolder] | None = None
    ) -> None:
        self.Name = name
        self.Items = items or _PstItems([])
        self.Folders = folders or []


class _PstStore:
    def __init__(self, file_path: str, root: _PstFolder) -> None:
        self.FilePath = file_path
        self._root = root

    def GetRootFolder(self) -> _PstFolder:
        return self._root


class _PstNamespace:
    def __init__(self) -> None:
        self.stores: list[_PstStore] = []
        self.added: list[str] = []
        self.removed: list[Any] = []

    @property
    def Stores(self) -> Any:
        return iter(self.stores)

    def AddStore(self, path: str) -> None:
        self.added.append(path)

    def RemoveStore(self, root: Any) -> None:
        self.removed.append(root)


def _make_client(namespace: _PstNamespace) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(namespace=namespace)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def test_inspect_missing_file_returns_error_without_mounting() -> None:
    from pst_inspector import PSTInspector

    namespace = _PstNamespace()
    inspector = PSTInspector(_make_client(namespace))

    result = inspector.inspect("/does/not/exist.pst")

    assert result["exists"] is False
    assert result["mounted"] is False
    assert result["error"] == "ファイルが存在しません"
    assert namespace.added == []


def test_inspect_happy_path_walks_and_unmounts(tmp_path: Path) -> None:
    from pst_inspector import PSTInspector

    pst_file = tmp_path / "kenji_at_uns-kikaku_com.pst"
    pst_file.write_bytes(b"fake-pst-contents")

    inbox = _PstFolder(
        "Inbox",
        items=_PstItems(
            [
                _PstItem(sender="a@x.com", received_time=datetime(2026, 1, 5)),
                _PstItem(sender="b@x.com", received_time=datetime(2026, 3, 1)),
                _PstItem(sender="a@x.com", received_time=datetime(2026, 2, 10)),
            ]
        ),
    )
    root = _PstFolder("root", folders=[inbox])
    store = _PstStore(file_path=str(pst_file), root=root)

    namespace = _PstNamespace()

    def add_store(path: str) -> None:
        namespace.added.append(path)
        namespace.stores.append(store)

    namespace.AddStore = add_store  # type: ignore[method-assign]

    inspector = PSTInspector(_make_client(namespace))
    result = inspector.inspect(str(pst_file))

    assert result["error"] is None
    assert result["exists"] is True
    assert result["mounted"] is False  # se desmonto al final
    assert result["total_emails"] == 3
    assert result["total_folders"] == 1
    assert result["folders"][0] == {"name": "Inbox", "count": 3, "depth": 1}
    assert result["date_range"] == {"oldest": "2026-01-05", "newest": "2026-03-01"}
    assert result["senders"] == {"a@x.com": 2, "b@x.com": 1}
    assert result["top_senders"][0] == ("a@x.com", 2)
    assert namespace.removed == [root]


def test_inspect_returns_error_when_mounted_store_not_found(tmp_path: Path) -> None:
    """AddStore corrio pero ningun store.FilePath matchea: no desmonta nada."""
    from pst_inspector import PSTInspector

    pst_file = tmp_path / "ghost.pst"
    pst_file.write_bytes(b"x")

    namespace = _PstNamespace()  # AddStore no agrega nada a namespace.stores
    inspector = PSTInspector(_make_client(namespace))

    result = inspector.inspect(str(pst_file))

    assert result["mounted"] is True  # nunca se llego a desmontar
    assert result["error"] == "PSTをマウントできませんでした"
    assert namespace.removed == []


def test_inspect_catches_unexpected_exception(tmp_path: Path) -> None:
    from pst_inspector import PSTInspector

    pst_file = tmp_path / "kenji.pst"
    pst_file.write_bytes(b"x")

    class BrokenNamespace:
        def AddStore(self, _path: str) -> None:
            raise RuntimeError("COM se cayo")

    inspector = PSTInspector(_make_client(BrokenNamespace()))  # type: ignore[arg-type]
    result = inspector.inspect(str(pst_file))

    assert result["error"] == "COM se cayo"


def test_inspect_ignores_dismount_failure() -> None:
    """Si RemoveStore falla al desmontar, el resultado igual se devuelve OK."""
    from pst_inspector import PSTInspector

    root = _PstFolder("root")
    store = _PstStore(file_path="/tmp/kenji.pst", root=root)

    class FlakyNamespace(_PstNamespace):
        def RemoveStore(self, _root: Any) -> None:
            raise RuntimeError("no se pudo desmontar")

    namespace = FlakyNamespace()
    namespace.stores.append(store)

    inspector = PSTInspector(_make_client(namespace))

    import os
    from unittest.mock import patch

    with (
        patch.object(os.path, "exists", return_value=True),
        patch.object(os.path, "getsize", return_value=1024),
    ):
        result = inspector.inspect("/tmp/kenji.pst")

    assert result["error"] is None  # el fallo de RemoveStore se traga silenciosamente
    assert result["mounted"] is True  # como RemoveStore fallo, nunca se puso en False


# ---------------------------------------------------------------------------
# _walk — sampling limitado a 50 items
# ---------------------------------------------------------------------------


def test_walk_samples_at_most_50_items_per_folder() -> None:
    from pst_inspector import PSTInspector

    many_items = [_PstItem(sender=f"user{i}@x.com") for i in range(120)]
    folder = _PstFolder("Big Folder", items=_PstItems(many_items))

    inspector = PSTInspector(_make_client(_PstNamespace()))
    result: dict = {
        "total_emails": 0,
        "total_folders": 0,
        "folders": [],
        "senders": {},
        "date_range": {"oldest": None, "newest": None},
    }
    inspector._walk(folder, result, depth=0)

    assert result["total_emails"] == 120  # el count total si refleja los 120
    assert sum(result["senders"].values()) == 50  # pero el sample de senders es 50
