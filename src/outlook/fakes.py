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

from dataclasses import dataclass, field
from datetime import datetime

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

    def __iter__(self):
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
    def Accounts(self):
        return iter(self.accounts)

    @property
    def Stores(self):
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
