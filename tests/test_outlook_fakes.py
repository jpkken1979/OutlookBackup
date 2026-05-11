"""Tests que validan que los fakes cumplen los Protocols y se comportan correctamente.

Si estos tests pasan, los engines pueden depender de los Protocols con confianza:
- Los fakes son drop-in replacements del real adapter en tests.
- Cualquier cambio en los Protocols que rompa los fakes se detecta aca.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from outlook import constants as olc  # noqa: E402
from outlook.fakes import (  # noqa: E402
    FakeAccount,
    FakeApplication,
    FakeFolder,
    FakeItems,
    FakeMailItem,
    FakeNamespace,
    FakeStore,
)
from outlook.protocols import (  # noqa: E402
    AccountProtocol,
    ApplicationProtocol,
    FolderProtocol,
    ItemsProtocol,
    MailItemProtocol,
    NamespaceProtocol,
    StoreProtocol,
)


class TestProtocolConformance:
    """Verifica isinstance(fake, Protocol) via @runtime_checkable."""

    def test_fake_mailitem_is_mailitem(self) -> None:
        item = FakeMailItem(Subject="hi", ReceivedTime=datetime.now())
        assert isinstance(item, MailItemProtocol)

    def test_fake_items_is_items(self) -> None:
        items = FakeItems()
        assert isinstance(items, ItemsProtocol)

    def test_fake_folder_is_folder(self) -> None:
        folder = FakeFolder(Name="Inbox")
        assert isinstance(folder, FolderProtocol)

    def test_fake_store_is_store(self) -> None:
        store = FakeStore(DisplayName="kenji@uns")
        assert isinstance(store, StoreProtocol)

    def test_fake_account_is_account(self) -> None:
        acc = FakeAccount(SmtpAddress="k@uns.com", DisplayName="K")
        assert isinstance(acc, AccountProtocol)

    def test_fake_namespace_is_namespace(self) -> None:
        ns = FakeNamespace()
        assert isinstance(ns, NamespaceProtocol)

    def test_fake_application_is_application(self) -> None:
        app = FakeApplication()
        assert isinstance(app, ApplicationProtocol)


class TestFakeBehavior:
    """Verifica que los fakes simulan correctamente la semantica de Outlook."""

    def test_application_get_namespace_returns_mapi(self) -> None:
        app = FakeApplication()
        ns = app.GetNamespace("MAPI")
        assert ns is app.namespace

    def test_application_rejects_non_mapi(self) -> None:
        app = FakeApplication()
        with pytest.raises(AssertionError):
            app.GetNamespace("Other")

    def test_namespace_iterates_accounts(self) -> None:
        ns = FakeNamespace()
        a1 = FakeAccount(SmtpAddress="a@x.com")
        a2 = FakeAccount(SmtpAddress="b@x.com")
        ns.accounts.extend([a1, a2])

        smtp_list = [a.SmtpAddress for a in ns.Accounts]
        assert smtp_list == ["a@x.com", "b@x.com"]

    def test_namespace_iterates_stores(self) -> None:
        ns = FakeNamespace()
        ns.stores.extend([FakeStore(DisplayName="s1"), FakeStore(DisplayName="s2")])

        names = [s.DisplayName for s in ns.Stores]
        assert names == ["s1", "s2"]

    def test_addstoreex_appends_to_stores(self) -> None:
        ns = FakeNamespace()
        ns.AddStoreEx("C:/tmp/out.pst", olc.STORE_UNICODE)

        assert ns._added_stores == [("C:/tmp/out.pst", olc.STORE_UNICODE)]
        assert len(ns.stores) == 1
        assert ns.stores[0].FilePath == "C:/tmp/out.pst"
        assert ns.stores[0].IsDataFileStore is True

    def test_addstore_appends_to_stores(self) -> None:
        ns = FakeNamespace()
        ns.AddStore("C:/tmp/existing.pst")

        assert ns._added_stores == [("C:/tmp/existing.pst", None)]
        assert ns.stores[0].FilePath == "C:/tmp/existing.pst"

    def test_removestore_removes_by_root_folder(self) -> None:
        ns = FakeNamespace()
        ns.AddStoreEx("C:/tmp/out.pst", olc.STORE_UNICODE)
        store = ns.stores[0]
        root = store.GetRootFolder()

        ns.RemoveStore(root)

        assert root in ns._removed_stores
        assert store not in ns.stores

    def test_store_root_is_consistent(self) -> None:
        """GetRootFolder devuelve el mismo objeto en llamadas repetidas."""
        store = FakeStore(DisplayName="kenji@uns")
        root1 = store.GetRootFolder()
        root2 = store.GetRootFolder()
        assert root1 is root2

    def test_folder_copyto_creates_subfolder_at_target(self) -> None:
        source = FakeFolder(Name="Inbox")
        source.Items.append(FakeMailItem(Subject="email 1"))
        source.Items.append(FakeMailItem(Subject="email 2"))

        target = FakeFolder(Name="Archive")

        copy = source.CopyTo(target)

        assert target in source._copied_to
        assert copy in target.Folders
        assert copy.Name == "Inbox"
        assert copy.Items.Count == 2
        assert copy.Items._items[0].Subject == "email 1"

    def test_folder_copyto_is_recursive(self) -> None:
        sub = FakeFolder(Name="Sub")
        sub.Items.append(FakeMailItem(Subject="nested"))
        source = FakeFolder(Name="Top", Folders=[sub])

        target = FakeFolder(Name="Archive")
        source.CopyTo(target)

        copied_top = target.Folders[0]
        assert copied_top.Name == "Top"
        assert len(copied_top.Folders) == 1
        assert copied_top.Folders[0].Items.Count == 1

    def test_items_count_matches_iteration(self) -> None:
        items = FakeItems()
        for i in range(5):
            items.append(FakeMailItem(Subject=f"e{i}"))
        assert items.Count == 5
        assert sum(1 for _ in items) == 5

    def test_mailitem_saveas_records_call(self) -> None:
        item = FakeMailItem(Subject="test")
        item.SaveAs("C:/out/test.msg", olc.SAVE_AS_MSG)
        item.SaveAs("C:/out/test.html", olc.SAVE_AS_HTML)

        assert item._saved_to == [
            ("C:/out/test.msg", olc.SAVE_AS_MSG),
            ("C:/out/test.html", olc.SAVE_AS_HTML),
        ]

    def test_getdefaultfolder_is_idempotent(self) -> None:
        ns = FakeNamespace()
        inbox1 = ns.GetDefaultFolder(olc.FOLDER_INBOX)
        inbox2 = ns.GetDefaultFolder(olc.FOLDER_INBOX)
        assert inbox1 is inbox2


class TestConstants:
    """Verifica que las constantes coinciden con valores reales de Outlook."""

    def test_folder_inbox_is_6(self) -> None:
        assert olc.FOLDER_INBOX == 6

    def test_mail_item_is_43(self) -> None:
        assert olc.MAIL_ITEM == 43

    def test_store_unicode_is_3(self) -> None:
        assert olc.STORE_UNICODE == 3

    def test_account_type_names_complete(self) -> None:
        # Verifica que todos los tipos numericos tienen nombre
        for type_id in range(6):
            assert type_id in olc.ACCOUNT_TYPE_NAMES
