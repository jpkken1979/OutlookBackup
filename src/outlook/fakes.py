"""Implementaciones in-memory de los Protocols de outlook.protocols.

Para tests unitarios: en vez de mockear cada metodo de Dispatch con MagicMock,
construis un FakeNamespace con la topologia que necesita tu test y se la
pasas al engine. Asi los tests son legibles y los assertions naturales.

Ejemplo:
    namespace = FakeNamespace()
    account = FakeAccount(smtp="k@uns-kikaku.com", display_name="Kenji")
    inbox = FakeFolder(name="Inbox", items=[FakeMailItem(subject="Hi")])
    store = FakeStore(display_name="k@uns-kikaku.com", root=FakeFolder(
        name="root", folders=[inbox]
    ))
    namespace.accounts.append(account)
    namespace.stores.append(store)

    # Pasar al engine bajo test
    engine = BackupEngine(namespace=namespace, ...)
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from outlook import constants as olc


@dataclass
class FakeMailItem:
    """Email en memoria."""

    Subject: str = ""
    ReceivedTime: datetime = field(default_factory=datetime.now)
    Class: int = olc.MAIL_ITEM
    Body: str = ""
    SenderEmailAddress: str = ""

    # Trace para tests: cada SaveAs se registra
    _saved_to: list[tuple[str, int]] = field(default_factory=list)

    def SaveAs(self, path: str, format_id: int) -> None:
        self._saved_to.append((path, format_id))


@dataclass
class FakeItems:
    """Coleccion de items. Iterable + Count."""

    _items: list[FakeMailItem] = field(default_factory=list)

    @property
    def Count(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[FakeMailItem]:
        return iter(self._items)

    def append(self, item: FakeMailItem) -> None:
        self._items.append(item)


@dataclass
class FakeFolder:
    """Carpeta en memoria. Items y subcarpetas mutables."""

    Name: str = "Folder"
    Items: FakeItems = field(default_factory=FakeItems)
    Folders: list[FakeFolder] = field(default_factory=list)
    Parent: FakeFolder | None = None

    # Trace de operaciones para tests
    _copied_to: list[FakeFolder] = field(default_factory=list)

    def CopyTo(self, target_folder: FakeFolder) -> FakeFolder:
        """Simula CopyTo de Outlook — anade self a target_folder.Folders.

        Las subcarpetas se agregan a `copy` automaticamente cuando se llaman
        recursivamente (cada CopyTo hace su propio append al target).
        """
        copy = FakeFolder(
            Name=self.Name,
            Items=FakeItems(_items=list(self.Items._items)),
            Folders=[],
            Parent=target_folder,
        )
        target_folder.Folders.append(copy)
        # Recursion: cada sub.CopyTo(copy) appendea al copy.Folders por si mismo
        for sub in self.Folders:
            sub.CopyTo(copy)
        self._copied_to.append(target_folder)
        return copy


@dataclass
class FakeStore:
    """Store en memoria (PST/OST/Exchange simulado)."""

    DisplayName: str = "Default"
    FilePath: str | None = None
    StoreID: str = ""
    IsDataFileStore: bool = False
    _root: FakeFolder | None = None

    def GetRootFolder(self) -> FakeFolder:
        if self._root is None:
            self._root = FakeFolder(Name=f"root::{self.DisplayName}")
        return self._root


@dataclass
class FakeAccount:
    """Cuenta de correo en memoria."""

    SmtpAddress: str = ""
    DisplayName: str = ""
    UserName: str = ""
    AccountType: int = olc.ACCOUNT_TYPE_IMAP
    DeliveryStore: FakeStore = field(default_factory=FakeStore)


@dataclass
class FakeNamespace:
    """Namespace MAPI fake. Mutable — agrega accounts/stores en tu setup."""

    accounts: list[FakeAccount] = field(default_factory=list)
    stores: list[FakeStore] = field(default_factory=list)
    default_folders: dict[int, FakeFolder] = field(default_factory=dict)

    # Trace para tests
    _added_stores: list[tuple[str, int | None]] = field(default_factory=list)
    _removed_stores: list[FakeFolder] = field(default_factory=list)

    @property
    def Accounts(self) -> Iterator[FakeAccount]:
        return iter(self.accounts)

    @property
    def Stores(self) -> Iterator[FakeStore]:
        return iter(self.stores)

    def GetDefaultFolder(self, folder_type: int) -> FakeFolder:
        if folder_type not in self.default_folders:
            self.default_folders[folder_type] = FakeFolder(Name=f"default::{folder_type}")
        return self.default_folders[folder_type]

    def AddStore(self, path: str) -> None:
        """Crea un FakeStore vacio en la lista. Test override-able."""
        self._added_stores.append((path, None))
        new_store = FakeStore(DisplayName=path, FilePath=path)
        self.stores.append(new_store)

    def AddStoreEx(self, path: str, format_id: int) -> None:
        self._added_stores.append((path, format_id))
        new_store = FakeStore(
            DisplayName=path,
            FilePath=path,
            IsDataFileStore=True,
        )
        self.stores.append(new_store)

    def RemoveStore(self, root_folder: FakeFolder) -> None:
        self._removed_stores.append(root_folder)
        # Buscar store cuyo root coincide
        for store in list(self.stores):
            if store._root is root_folder:
                self.stores.remove(store)
                return


@dataclass
class FakeApplication:
    """Outlook.Application fake."""

    namespace: FakeNamespace = field(default_factory=FakeNamespace)

    def GetNamespace(self, namespace_type: str) -> FakeNamespace:
        assert namespace_type == "MAPI", f"Solo MAPI soportado, no {namespace_type}"
        return self.namespace


# ============================================================
# High-level fakes for engines
# ============================================================


@dataclass
class FakeOutlookAccount:
    """Domain account info — cumple OutlookAccountInfo Protocol.

    Drop-in replacement de OutlookAccount (definido en outlook_client.py) en
    tests. Tiene los atributos que los engines leen.
    """

    smtp_address: str = ""
    display_name: str = ""
    account_type: str = "IMAP"
    store_id: str = ""

    def matches_domain(self, domain: str) -> bool:
        return self.smtp_address.lower().endswith(f"@{domain.lower()}")

    def to_dict(self) -> dict:
        return {
            "smtp": self.smtp_address,
            "name": self.display_name,
            "type": self.account_type,
        }


@dataclass
class FakeOutlookClient:
    """High-level facade fake — cumple OutlookClientProtocol.

    Por defecto las operaciones devuelven exito y crean archivos vacios para
    que los `os.path.exists` de los engines no fallen. Para simular errores,
    setea entries en _export_returns / _msg_returns / _count_returns.

    Ejemplo:
        client = FakeOutlookClient()
        client._export_returns["broken@uns.com"] = False  # simula export fallido
        engine = BackupEngine(outlook_client=client, ...)
    """

    namespace: FakeNamespace = field(default_factory=FakeNamespace)

    # Behavior overrides per-account (default: success)
    _export_returns: dict[str, bool] = field(default_factory=dict)
    _msg_returns: dict[str, int] = field(default_factory=dict)
    _count_returns: dict[str, dict] = field(default_factory=dict)

    # Trace de llamadas para asserts en tests
    _export_calls: list[tuple[str, str]] = field(default_factory=list)
    _msg_calls: list[tuple[str, str]] = field(default_factory=list)
    _count_calls: list[str] = field(default_factory=list)

    def export_account_to_pst(
        self,
        account: Any,
        output_path: str,
        progress_cb: Callable | None = None,
        date_from: Any | None = None,  # noqa: ARG002 — Fase 6 partial; fake no aplica filter
        date_to: Any | None = None,  # noqa: ARG002 — fake no aplica filter
    ) -> bool:
        smtp = account.smtp_address
        self._export_calls.append((smtp, output_path))
        if progress_cb:
            progress_cb(f"[fake] export {smtp} -> {output_path}")

        success = self._export_returns.get(smtp, True)
        if success:
            # Crear archivo vacio para que os.path.exists() pase en BackupEngine
            from pathlib import Path

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).touch()
        return success

    def export_folder_to_msg_files(
        self, account: Any, output_dir: str, progress_cb: Callable | None = None
    ) -> int:
        smtp = account.smtp_address
        self._msg_calls.append((smtp, output_dir))
        if progress_cb:
            progress_cb(f"[fake] msg-export {smtp} -> {output_dir}")

        count = self._msg_returns.get(smtp, 5)
        if count > 0:
            from pathlib import Path

            Path(output_dir).mkdir(parents=True, exist_ok=True)
        return count

    def count_emails_for_account(self, account: Any, progress_cb: Callable | None = None) -> dict:
        smtp = account.smtp_address
        self._count_calls.append(smtp)
        return self._count_returns.get(
            smtp,
            {
                "total_emails": 10,
                "total_folders": 3,
                "total_size_bytes": 1024 * 1024,
                "folders": [],
            },
        )
