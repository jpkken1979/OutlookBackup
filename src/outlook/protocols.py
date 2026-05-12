"""Protocols (PEP 544) que documentan la API minima de Outlook COM que la app consume.

Estos Protocols definen el contrato — no son clases base. Los objetos pywin32
Dispatch los cumplen estructuralmente (structural subtyping), igual que los
fakes in-memory de `outlook.fakes`.

Decisiones:
- Usamos `typing.Protocol` (PEP 544). No herencia.
- Atributos COM se modelan como properties tipadas. Algunos son mutables en
  pywin32 (ej. Folder.Name) pero la app no los muta, asi que se ven como readonly.
- Collections (Accounts, Stores, Folders, Items) se modelan como `Iterable[X]`
  en vez de `list` porque COM devuelve enumeradores, no listas. La iteracion
  funciona; indexing/Count se exponen donde la app los usa.
- Las constantes COM (olStoreUnicode=3, olMailItem=43, etc.) viven en
  `outlook.constants` para no contaminar los Protocols.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MailItemProtocol(Protocol):
    """Email individual dentro de una carpeta."""

    Subject: str
    ReceivedTime: Any  # COM Date — pywin32 lo entrega como datetime.datetime
    Class: int  # 43 = olMailItem

    def SaveAs(self, path: str, format_id: int) -> None:
        """Guarda el item a disco. format_id=3 -> .msg (olMSG)."""
        ...


@runtime_checkable
class ItemsProtocol(Protocol):
    """Coleccion de items en una carpeta (emails, citas, contactos...)."""

    Count: int

    def __iter__(self) -> Iterable[MailItemProtocol]:  # type: ignore[override]
        ...


@runtime_checkable
class FolderProtocol(Protocol):
    """Carpeta en un store de Outlook (Inbox, Sent, custom...)."""

    Name: str

    @property
    def Items(self) -> ItemsProtocol:
        """Items dentro de la carpeta."""
        ...

    @property
    def Folders(self) -> Iterable[FolderProtocol]:
        """Subcarpetas inmediatas."""
        ...

    @property
    def Parent(self) -> FolderProtocol | None:
        """Carpeta padre. None si es la raiz del store."""
        ...

    def CopyTo(self, target_folder: FolderProtocol) -> FolderProtocol:
        """Copia esta carpeta (con items y subcarpetas) al destino."""
        ...


@runtime_checkable
class StoreProtocol(Protocol):
    """Data store de Outlook (PST, OST, Exchange mailbox, etc.)."""

    DisplayName: str
    FilePath: str | None  # None para Exchange online
    StoreID: str
    IsDataFileStore: bool

    def GetRootFolder(self) -> FolderProtocol:
        """Devuelve la carpeta raiz del store."""
        ...


@runtime_checkable
class AccountProtocol(Protocol):
    """Cuenta de correo configurada en Outlook (IMAP, Exchange, POP3...)."""

    SmtpAddress: str
    DisplayName: str
    UserName: str
    AccountType: int  # 0=Exchange, 1=IMAP, 2=POP3, 3=HTTP, 4=EAS, 5=Other

    @property
    def DeliveryStore(self) -> StoreProtocol:
        """Store por defecto donde llegan emails de esta cuenta."""
        ...


@runtime_checkable
class NamespaceProtocol(Protocol):
    """Namespace MAPI — punto de entrada para Accounts, Stores, Folders."""

    @property
    def Accounts(self) -> Iterable[AccountProtocol]:
        """Cuentas configuradas en Outlook."""
        ...

    @property
    def Stores(self) -> Iterable[StoreProtocol]:
        """Stores (PST/OST/Exchange) montados."""
        ...

    def GetDefaultFolder(self, folder_type: int) -> FolderProtocol:
        """Carpetas built-in. 6=Inbox, 5=Sent, 16=Drafts, 3=Deleted, 4=Outbox."""
        ...

    def AddStore(self, path: str) -> None:
        """Monta un PST existente como store (formato detectado)."""
        ...

    def AddStoreEx(self, path: str, format_id: int) -> None:
        """Crea/monta un PST. format_id=3 -> olStoreUnicode."""
        ...

    def RemoveStore(self, root_folder: FolderProtocol) -> None:
        """Desmonta un store. Recibe la carpeta raiz, no el store directamente."""
        ...


@runtime_checkable
class ApplicationProtocol(Protocol):
    """Outlook.Application — top-level COM object."""

    def GetNamespace(self, namespace_type: str) -> NamespaceProtocol:
        """En la practica solo se usa 'MAPI'."""
        ...


# ============================================================
# High-level facade protocol
# ============================================================
#
# Los engines (BackupEngine, ImportEngine) consumen OutlookClient, no Dispatch
# directo. OutlookClient mezcla acceso COM low-level con orquestacion. Este
# Protocol documenta la API que los engines usan, para que FakeOutlookClient
# pueda reemplazarlo en tests.


@runtime_checkable
class OutlookAccountInfo(Protocol):
    """Cuenta como la conoce la app (no el AccountProtocol de COM crudo).

    El OutlookAccount real (en outlook_client.py) cumple este Protocol. Es lo
    que se pasa entre engines y UI.
    """

    smtp_address: str
    display_name: str
    account_type: str

    def matches_domain(self, domain: str) -> bool:
        """True si smtp_address termina con @{domain}."""
        ...


@runtime_checkable
class OutlookClientProtocol(Protocol):
    """Facade high-level sobre Outlook que los engines usan.

    El namespace tipado se expone para ImportEngine que toca AddStore/Stores
    directamente. Los export_* son metodos high-level que BackupEngine usa
    sin tocar COM directo.
    """

    namespace: NamespaceProtocol

    def export_account_to_pst(
        self,
        account: OutlookAccountInfo,
        output_path: str,
        progress_cb: Callable[..., Any] | None = None,
    ) -> bool:
        """Exporta una cuenta entera a un archivo .pst. True si exito."""
        ...

    def export_folder_to_msg_files(
        self,
        account: OutlookAccountInfo,
        output_dir: str,
        progress_cb: Callable[..., Any] | None = None,
    ) -> int:
        """Exporta emails como archivos .msg individuales. Devuelve count."""
        ...

    def count_emails_for_account(
        self, account: OutlookAccountInfo, progress_cb: Callable[..., Any] | None = None
    ) -> dict:
        """Cuenta correos. Devuelve dict con total_emails, total_folders, etc."""
        ...
