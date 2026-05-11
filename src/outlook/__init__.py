"""Capa de abstraccion sobre la API COM de Outlook.

Tres modulos:
- `protocols`: contratos tipados (Protocol) que documentan la API minima
  que la app consume de Outlook. Independientes de pywin32 — sirven en
  Linux para tipado y tests.
- `real`: adapter que envuelve `win32com.client.Dispatch` y cumple los
  Protocols. Solo importable en Windows con pywin32.
- `fakes`: implementaciones in-memory de los Protocols. Para tests
  unitarios sin Outlook real.

Patron: los engines (backup, import, cache) reciben un Namespace por
constructor (DI). En produccion se pasa el real adapter; en tests se
pasa un fake. Asi los engines son testeables.
"""

from outlook.protocols import (
    AccountProtocol,
    ApplicationProtocol,
    FolderProtocol,
    ItemsProtocol,
    MailItemProtocol,
    NamespaceProtocol,
    StoreProtocol,
)

__all__ = [
    "AccountProtocol",
    "ApplicationProtocol",
    "FolderProtocol",
    "ItemsProtocol",
    "MailItemProtocol",
    "NamespaceProtocol",
    "StoreProtocol",
]
