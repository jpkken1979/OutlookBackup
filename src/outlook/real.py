"""Adapter real sobre pywin32 win32com.client.Dispatch.

Patron: como los Protocols son structural (PEP 544 / duck typing), los objetos
que devuelve `Dispatch("Outlook.Application")` ya cumplen los Protocols por
forma — tienen los atributos y metodos que pedimos. No necesitamos una clase
wrapper que reimplemente cada metodo.

Este modulo solo provee:
- `create_outlook_application()` — factory tipada que devuelve ApplicationProtocol
- `OutlookSession` — context manager para CoInitialize/CoUninitialize

Solo importable en Windows con pywin32 instalado. En CI Linux fallaria con
ImportError, que es lo que queremos: tests deben usar `outlook.fakes`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from outlook.protocols import ApplicationProtocol


class OutlookUnavailableError(RuntimeError):
    """Outlook no se pudo abrir (no instalado, COM bloqueado, etc.)."""


def create_outlook_application() -> ApplicationProtocol:
    """Crea una instancia de Outlook.Application via COM.

    Si Outlook no esta abierto, COM lo inicia. Si esta abierto, se conecta
    a la instancia existente.

    Returns:
        Objeto Dispatch que cumple ApplicationProtocol estructuralmente.

    Raises:
        OutlookUnavailableError: si pywin32 no esta o Dispatch falla.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise OutlookUnavailableError(
            "pywin32 no esta instalado. Ejecuta: pip install pywin32"
        ) from exc

    try:
        pythoncom.CoInitialize()
        app = win32com.client.Dispatch("Outlook.Application")
    except Exception as exc:  # COMError + otros — pywin32 lanza varias clases
        raise OutlookUnavailableError(
            f"No se pudo conectar a Outlook (¿esta instalado?). Error: {exc}"
        ) from exc

    # Dispatch retorna Any; el Protocol lo cumple por duck-typing en runtime.
    return app  # type: ignore[no-any-return]


@contextlib.contextmanager
def outlook_session() -> Iterator[ApplicationProtocol]:
    """Context manager que maneja CoInitialize/CoUninitialize.

    Uso:
        with outlook_session() as app:
            namespace = app.GetNamespace("MAPI")
            ...

    Importante: pywin32 requiere CoInitialize en cada thread. Si lanzas el
    backup en un thread, ese thread necesita su propio session.
    """
    app = create_outlook_application()
    try:
        yield app
    finally:
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except Exception:
            pass
