"""Tests del ImportEngine.

Estrategia:
- ImportEngine toca self.client.namespace.AddStore/AddStoreEx/Stores
- Pasamos FakeOutlookClient con FakeNamespace
- Validamos los 3 modos: separate_folder, merge, new_files
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from import_engine import ImportEngine, find_pst_files  # noqa: E402
from outlook.fakes import (  # noqa: E402
    FakeFolder,
    FakeMailItem,
    FakeOutlookClient,
    FakeStore,
)


def _wait_for_import(engine: ImportEngine, timeout: float = 5.0) -> tuple[bool, int, int]:
    """Helper: arranca, espera, devuelve (success, succeeded, total)."""
    done = threading.Event()
    result: dict = {}

    def progress_cb(msg: str) -> None:
        pass

    def finish_cb(success: bool, succeeded: int, total: int) -> None:
        result["success"] = success
        result["succeeded"] = succeeded
        result["total"] = total
        done.set()

    engine.run_async(progress_cb, finish_cb)
    if not done.wait(timeout):
        raise TimeoutError(f"Import no termino en {timeout}s")
    return result["success"], result["succeeded"], result["total"]


class TestImportEngineSeparateFolder:
    """Mode: separate_folder — usa AddStore."""

    def test_imports_two_psts_via_addstore(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        pst1 = str(tmp_path / "backup1.pst")
        pst2 = str(tmp_path / "backup2.pst")

        engine = ImportEngine(
            outlook_client=client,
            pst_files=[pst1, pst2],
            mode="separate_folder",
        )

        success, ok, total = _wait_for_import(engine)

        assert success is True
        assert ok == 2
        assert total == 2
        # Verificar que AddStore fue llamado con ambos paths
        added_paths = [path for path, fmt in client.namespace._added_stores if fmt is None]
        assert pst1 in added_paths
        assert pst2 in added_paths

    def test_results_track_each_file(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = ImportEngine(
            outlook_client=client,
            pst_files=[str(tmp_path / "a.pst")],
            mode="separate_folder",
        )

        _wait_for_import(engine)

        assert len(engine.results) == 1
        assert engine.results[0]["success"] is True


class TestImportEngineNewFiles:
    """Mode: new_files — usa AddStoreEx con olStoreUnicode=3."""

    def test_imports_via_addstoreex_unicode(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = ImportEngine(
            outlook_client=client,
            pst_files=[str(tmp_path / "new.pst")],
            mode="new_files",
        )

        success, ok, _ = _wait_for_import(engine)

        assert success is True
        assert ok == 1
        # Verificar que se llamo AddStoreEx con format=3 (olStoreUnicode)
        assert len(client.namespace._added_stores) == 1
        path, fmt = client.namespace._added_stores[0]
        assert fmt == 3


class TestImportEngineMerge:
    """Mode: merge — copia carpetas del source al target."""

    def test_merge_without_target_smtp_fails(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = ImportEngine(
            outlook_client=client,
            pst_files=[str(tmp_path / "src.pst")],
            mode="merge",
            target_smtp=None,
        )

        success, ok, total = _wait_for_import(engine)
        # Mode merge sin target_smtp falla — ok=0
        assert ok == 0
        assert total == 1

    def test_merge_with_target_account_copies_folders(self, tmp_path: Path) -> None:
        """Setup completo: source PST + target account ya existente."""
        client = FakeOutlookClient()
        pst_path = str(tmp_path / "source.pst")

        # Setup: hay un store target ya montado en el namespace (la cuenta del usuario)
        target_store = FakeStore(
            DisplayName="kenji@uns-kikaku.com",
            FilePath=None,
            _root=FakeFolder(Name="target_root"),
        )
        client.namespace.stores.append(target_store)

        # Cuando AddStore se llame con pst_path, simular que el source store
        # queda en la lista con carpetas para copiar
        original_add_store = client.namespace.AddStore

        def add_store_with_data(path: str) -> None:
            original_add_store(path)
            # El store recien agregado: anadirle carpetas y items
            new_store = client.namespace.stores[-1]
            inbox = FakeFolder(Name="Inbox")
            inbox.Items.append(FakeMailItem(Subject="email 1"))
            sent = FakeFolder(Name="Sent")
            new_store._root = FakeFolder(Name="source_root", Folders=[inbox, sent])

        client.namespace.AddStore = add_store_with_data  # type: ignore[method-assign]

        engine = ImportEngine(
            outlook_client=client,
            pst_files=[pst_path],
            mode="merge",
            target_smtp="kenji@uns-kikaku.com",
        )

        success, ok, _ = _wait_for_import(engine)

        assert success is True
        assert ok == 1
        # El target_store deberia tener Inbox y Sent copiados
        target_folder_names = [f.Name for f in target_store._root.Folders]
        assert "Inbox" in target_folder_names
        assert "Sent" in target_folder_names


class TestImportEngineCancel:
    def test_cancel_before_run_skips_all(self, tmp_path: Path) -> None:
        client = FakeOutlookClient()
        engine = ImportEngine(
            outlook_client=client,
            pst_files=[str(tmp_path / f"{i}.pst") for i in range(3)],
            mode="separate_folder",
        )

        engine.cancel()
        success, ok, total = _wait_for_import(engine)
        # Cancelled antes de procesar — no AddStore se llamo
        assert len(client.namespace._added_stores) == 0


class TestFindPstFiles:
    """Helper: encuentra PSTs en un directorio."""

    def test_find_psts_recursive(self, tmp_path: Path) -> None:
        # Setup: crear estructura de archivos
        (tmp_path / "a.pst").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.pst").touch()
        (tmp_path / "ignored.txt").touch()

        results = find_pst_files(str(tmp_path), recursive=True)

        assert len(results) == 2
        # Resultados ordenados alfabeticamente
        assert all(r.endswith(".pst") for r in results)

    def test_find_psts_non_recursive_skips_subdirs(self, tmp_path: Path) -> None:
        (tmp_path / "a.pst").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.pst").touch()

        results = find_pst_files(str(tmp_path), recursive=False)

        assert len(results) == 1
        assert results[0].endswith("a.pst")

    def test_find_psts_returns_empty_when_dir_missing(self) -> None:
        results = find_pst_files("/nonexistent/path")
        assert results == []
