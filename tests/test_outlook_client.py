"""Tests directos del modulo `outlook_client` (cliente COM real, no el facade fake).

`src/outlook/fakes.py` ya provee `FakeOutlookClient`, un facade de alto nivel
usado por los engines (backup_engine, import_engine) — pero eso nunca ejercita
la implementacion real de `outlook_client.OutlookClient`. Aca se testea esa
implementacion directamente, construyendo el cliente sin pasar por `_connect()`
(que llama COM real) e inyectando un `FakeNamespace` con la topologia deseada.

Cubre:
- list_accounts / list_stores: mapeo de atributos COM + tolerancia a cuentas rotas
- count_emails_for_account: matching de store + fallback a inbox default
- export_account_to_pst: AddStoreEx + matching de stores + CopyTo + RemoveStore,
  incluyendo el camino de error cuando no se encuentra el store origen
- export_folder_to_msg_files / _save_msg_recursive: guardado de .msg, filtrado
  por Class, sanitizacion de nombres
- OutlookAccount: matches_domain / to_dict
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _make_client(namespace: Any) -> Any:
    """Construye OutlookClient saltando _connect() (que llama COM real)."""
    from outlook_client import OutlookClient

    client = OutlookClient.__new__(OutlookClient)
    client.app = None
    client.namespace = namespace
    return client


# ---------------------------------------------------------------------------
# OutlookAccount (dataclass de dominio)
# ---------------------------------------------------------------------------


def test_outlook_account_matches_domain_case_insensitive() -> None:
    from outlook_client import OutlookAccount

    acc = OutlookAccount("Kenji@UNS-Kikaku.com", "Kenji", "IMAP")
    assert acc.matches_domain("uns-kikaku.com") is True
    assert acc.matches_domain("other.com") is False


def test_outlook_account_to_dict_rounds_size() -> None:
    from outlook_client import OutlookAccount

    acc = OutlookAccount("k@uns-kikaku.com", "Kenji", "IMAP")
    acc.size_bytes = 2 * 1024 * 1024
    d = acc.to_dict()
    assert d["size_mb"] == 2.0


# ---------------------------------------------------------------------------
# list_accounts / list_stores
# ---------------------------------------------------------------------------


def test_list_accounts_maps_type_and_tolerates_broken_entries() -> None:
    from outlook.constants import ACCOUNT_TYPE_IMAP
    from outlook.fakes import FakeAccount, FakeNamespace

    good = FakeAccount(
        SmtpAddress="kenji@uns-kikaku.com", DisplayName="Kenji", AccountType=ACCOUNT_TYPE_IMAP
    )

    class BrokenAccount:
        @property
        def SmtpAddress(self) -> str:
            raise RuntimeError("boom")

    namespace = FakeNamespace(accounts=[good])
    namespace.accounts.append(BrokenAccount())  # type: ignore[arg-type]

    client = _make_client(namespace)
    accounts = client.list_accounts()

    assert len(accounts) == 1
    assert accounts[0].smtp_address == "kenji@uns-kikaku.com"
    assert accounts[0].account_type == "IMAP"


def test_list_stores_returns_display_and_path() -> None:
    from outlook.fakes import FakeNamespace, FakeStore

    namespace = FakeNamespace(
        stores=[FakeStore(DisplayName="kenji@uns-kikaku.com", FilePath="C:\\kenji.ost")]
    )
    client = _make_client(namespace)

    stores = client.list_stores()
    assert stores[0]["display_name"] == "kenji@uns-kikaku.com"
    assert stores[0]["file_path"] == "C:\\kenji.ost"


# ---------------------------------------------------------------------------
# get_account_inbox
# ---------------------------------------------------------------------------


def test_get_account_inbox_returns_matching_store_default_folder() -> None:
    from outlook.fakes import FakeItems, FakeMailItem, FakeNamespace, FakeStore
    from outlook_client import OL_FOLDER_INBOX

    store = FakeStore(DisplayName="kenji@uns-kikaku.com")
    store.GetDefaultFolder(OL_FOLDER_INBOX).Items = FakeItems([FakeMailItem(), FakeMailItem()])

    client = _make_client(FakeNamespace(stores=[store]))
    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com", display_name="Kenji")

    inbox = client.get_account_inbox(account)

    assert inbox is not None
    assert inbox.Items.Count == 2


def test_get_account_inbox_returns_none_when_no_store_matches() -> None:
    from outlook.fakes import FakeNamespace

    client = _make_client(FakeNamespace())
    account = SimpleNamespace(smtp_address="ghost@uns-kikaku.com", display_name="Ghost")

    assert client.get_account_inbox(account) is None


# ---------------------------------------------------------------------------
# count_emails_for_account
# ---------------------------------------------------------------------------


def test_count_emails_walks_matching_store_folders() -> None:
    from outlook.fakes import FakeFolder, FakeItems, FakeMailItem, FakeNamespace, FakeStore

    inbox = FakeFolder(Name="Inbox", Items=FakeItems([FakeMailItem(), FakeMailItem()]))
    root = FakeFolder(Name="root", Folders=[inbox])
    store = FakeStore(DisplayName="kenji@uns-kikaku.com", _root=root)
    namespace = FakeNamespace(stores=[store])
    client = _make_client(namespace)

    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com", display_name="Kenji")
    result = client.count_emails_for_account(account)

    assert result["total_emails"] == 2
    assert result["total_folders"] == 1


def test_count_emails_falls_back_to_default_inbox_when_no_store_matches() -> None:
    from outlook.fakes import FakeFolder, FakeItems, FakeMailItem, FakeNamespace
    from outlook_client import OL_FOLDER_INBOX

    default_inbox = FakeFolder(Name="Inbox", Items=FakeItems([FakeMailItem()]))
    parent_root = FakeFolder(Name="parent-root", Folders=[default_inbox])
    default_inbox.Parent = parent_root
    namespace = FakeNamespace(default_folders={OL_FOLDER_INBOX: default_inbox})
    client = _make_client(namespace)

    account = SimpleNamespace(smtp_address="unknown@uns-kikaku.com", display_name="Unknown")
    result = client.count_emails_for_account(account)

    # Cae al Parent del inbox default como root de recorrido
    assert result["total_emails"] == 1


# ---------------------------------------------------------------------------
# export_account_to_pst
# ---------------------------------------------------------------------------


def test_export_account_to_pst_happy_path_copies_and_closes_store(tmp_path: Path) -> None:
    from outlook.fakes import FakeFolder, FakeItems, FakeMailItem, FakeNamespace, FakeStore

    source_inbox = FakeFolder(Name="Inbox", Items=FakeItems([FakeMailItem()]))
    source_root = FakeFolder(Name="root::source", Folders=[source_inbox])
    source_store = FakeStore(DisplayName="kenji@uns-kikaku.com", _root=source_root)

    namespace = FakeNamespace(stores=[source_store])
    client = _make_client(namespace)

    output_path = str(tmp_path / "kenji_at_uns-kikaku_com.pst")
    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com")

    log: list[str] = []
    ok = client.export_account_to_pst(account, output_path, progress_cb=log.append)

    assert ok is True
    assert (output_path,) in [(p,) for p, _fmt in namespace._added_stores]
    assert len(namespace._removed_stores) == 1
    # La carpeta origen debe haber sido copiada al nuevo store
    assert len(source_inbox._copied_to) == 1
    assert any("完了" in m or "Backup completado" in m for m in log)


def test_export_account_to_pst_returns_false_and_closes_pst_when_source_missing(
    tmp_path: Path,
) -> None:
    """Si no se encuentra el store origen, el PST recien creado se cierra igual."""
    from outlook.fakes import FakeNamespace

    namespace = FakeNamespace()  # sin stores origen
    client = _make_client(namespace)

    output_path = str(tmp_path / "ghost_at_uns-kikaku_com.pst")
    account = SimpleNamespace(smtp_address="ghost@uns-kikaku.com")

    ok = client.export_account_to_pst(account, output_path)

    assert ok is False
    assert len(namespace._removed_stores) == 1  # el PST vacio se cerro de todos modos


def test_export_account_to_pst_removes_pre_existing_output_file(tmp_path: Path) -> None:
    from outlook.fakes import FakeFolder, FakeNamespace, FakeStore

    output_path = tmp_path / "kenji_at_uns-kikaku_com.pst"
    output_path.write_bytes(b"basura-de-un-intento-anterior")

    source_store = FakeStore(DisplayName="kenji@uns-kikaku.com", _root=FakeFolder(Name="root"))
    namespace = FakeNamespace(stores=[source_store])
    client = _make_client(namespace)

    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com")
    client.export_account_to_pst(account, str(output_path))

    # AddStoreEx (via el fake) recreo el archivo path como store, el archivo
    # basura original ya no debe seguir en disco tal cual estaba
    assert not output_path.exists() or output_path.stat().st_size != len(
        b"basura-de-un-intento-anterior"
    )


def test_export_account_to_pst_applies_date_filter_when_range_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Si date_from/date_to estan seteados, se llama filter_pst_items sobre el nuevo root."""
    import outlook_client
    from outlook.fakes import FakeFolder, FakeNamespace, FakeStore

    calls: list[Any] = []

    def fake_filter(root_folder: Any, date_from: Any, date_to: Any, progress_cb: Any = None) -> int:
        calls.append((root_folder, date_from, date_to))
        return 3

    monkeypatch.setattr(outlook_client, "filter_pst_items", fake_filter)

    source_store = FakeStore(DisplayName="kenji@uns-kikaku.com", _root=FakeFolder(Name="root"))
    namespace = FakeNamespace(stores=[source_store])
    client = _make_client(namespace)

    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com")
    output_path = str(tmp_path / "kenji_at_uns-kikaku_com.pst")

    ok = client.export_account_to_pst(
        account, output_path, date_from="2026-01-01", date_to="2026-06-30"
    )

    assert ok is True
    assert len(calls) == 1
    assert calls[0][1] == "2026-01-01"
    assert calls[0][2] == "2026-06-30"


def test_export_account_to_pst_returns_false_on_unexpected_exception(tmp_path: Path) -> None:
    """Cualquier excepcion COM inesperada se atrapa y devuelve False, no propaga."""

    class BrokenNamespace:
        _added_stores: list[Any] = []

        def AddStoreEx(self, *_a: Any, **_k: Any) -> None:
            raise RuntimeError("COM se cayo")

    client = _make_client(BrokenNamespace())
    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com")

    ok = client.export_account_to_pst(account, str(tmp_path / "x.pst"))
    assert ok is False


# ---------------------------------------------------------------------------
# _copy_folder_recursive
# ---------------------------------------------------------------------------


def test_copy_folder_recursive_skips_system_folders() -> None:
    from outlook.fakes import FakeFolder

    sync_issues = FakeFolder(Name="Sync Issues")
    inbox = FakeFolder(Name="Inbox")
    source = FakeFolder(Name="root", Folders=[sync_issues, inbox])
    dest = FakeFolder(Name="dest-root")

    client = _make_client(namespace=None)
    client._copy_folder_recursive(source, dest)

    copied_names = [f.Name for f in dest.Folders]
    assert "Sync Issues" not in copied_names
    assert "Inbox" in copied_names


def test_copy_folder_recursive_continues_after_subfolder_error() -> None:
    """Si un CopyTo individual falla, las demas carpetas se siguen copiando."""
    from outlook.fakes import FakeFolder

    class BrokenFolder:
        Name = "Broken"

        def CopyTo(self, _target: Any) -> None:
            raise RuntimeError("locked")

    good = FakeFolder(Name="Inbox")
    source = FakeFolder(Name="root")
    source.Folders = [BrokenFolder(), good]  # type: ignore[list-item]
    dest = FakeFolder(Name="dest-root")

    client = _make_client(namespace=None)
    client._copy_folder_recursive(source, dest)

    assert [f.Name for f in dest.Folders] == ["Inbox"]


# ---------------------------------------------------------------------------
# export_folder_to_msg_files / _save_msg_recursive
# ---------------------------------------------------------------------------


def test_export_folder_to_msg_files_returns_zero_when_store_missing(tmp_path: Path) -> None:
    from outlook.fakes import FakeNamespace

    client = _make_client(FakeNamespace())
    account = SimpleNamespace(smtp_address="ghost@uns-kikaku.com")

    count = client.export_folder_to_msg_files(account, str(tmp_path))
    assert count == 0


def test_export_folder_to_msg_files_saves_only_mail_items(tmp_path: Path) -> None:
    from outlook.constants import MAIL_ITEM
    from outlook.fakes import FakeFolder, FakeItems, FakeMailItem, FakeNamespace, FakeStore

    mail = FakeMailItem(Subject="Hola", Class=MAIL_ITEM)
    non_mail = FakeMailItem(Subject="No es mail", Class=999)
    inbox = FakeFolder(Name="Inbox", Items=FakeItems([mail, non_mail]))
    root = FakeFolder(Name="root", Folders=[inbox])
    store = FakeStore(DisplayName="kenji@uns-kikaku.com", _root=root)

    client = _make_client(FakeNamespace(stores=[store]))
    account = SimpleNamespace(smtp_address="kenji@uns-kikaku.com")

    count = client.export_folder_to_msg_files(account, str(tmp_path))

    assert count == 1
    assert len(mail._saved_to) == 1
    assert len(non_mail._saved_to) == 0


def test_save_msg_recursive_uses_item_index_when_no_received_time() -> None:
    from outlook.constants import MAIL_ITEM
    from outlook.fakes import FakeFolder, FakeItems, FakeMailItem

    class NoDateMailItem(FakeMailItem):
        @property
        def ReceivedTime(self) -> Any:  # type: ignore[override]
            raise AttributeError("sin fecha")

        @ReceivedTime.setter
        def ReceivedTime(self, _value: Any) -> None:
            pass

    item = NoDateMailItem(Subject="Sin fecha", Class=MAIL_ITEM)
    folder = FakeFolder(Name="Inbox", Items=FakeItems([item]))

    client = _make_client(namespace=None)
    count = client._save_msg_recursive(folder, "/tmp/whatever")

    assert count == 1
    assert item._saved_to[0][0].endswith(".msg")
    assert "item_00000" in item._saved_to[0][0]


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------


def test_sanitize_filename_replaces_invalid_windows_chars() -> None:
    from outlook_client import OutlookClient

    result = OutlookClient._sanitize_filename('a<b>c:d"e/f\\g|h?i*j')
    assert result == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_filename_truncates_to_200_chars() -> None:
    from outlook_client import OutlookClient

    result = OutlookClient._sanitize_filename("a" * 300)
    assert len(result) == 200


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


def test_close_resets_app_and_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    import outlook_client

    calls: list[str] = []
    monkeypatch.setattr(outlook_client.pythoncom, "CoUninitialize", lambda: calls.append("uninit"))

    client = _make_client(namespace=object())
    client.app = object()
    client.close()

    assert client.namespace is None
    assert client.app is None
    assert calls == ["uninit"]


def test_close_swallows_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    import outlook_client

    def raise_error() -> None:
        raise RuntimeError("CoUninitialize fail")

    monkeypatch.setattr(outlook_client.pythoncom, "CoUninitialize", raise_error)

    client = _make_client(namespace=object())
    client.close()  # no debe propagar
