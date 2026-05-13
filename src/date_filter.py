"""Filter de items por fecha de recepcion (Fase 6 partial Feature C plan v3.2).

Por que existe este modulo
--------------------------
Cuentas UNS con 10+ anios de historia generan PSTs gigantes en cada backup.
Para auditorias fiscales japonesas o cleanups solo se necesitan los ultimos
N meses de emails. Este modulo provee:

1. Parser de fechas ISO 8601 con validacion (no acepta formatos ambiguos).
2. `should_include(received, from, to)` predicate puro, testeable a fondo.
3. `filter_pst_items(root, from, to)` que recorre un PST montado y elimina
   items fuera del rango. Wire-up con Outlook COM via duck typing.

Referencias canonicas
---------------------
- COM ItemsAPI: https://learn.microsoft.com/office/vba/api/outlook.items
- ReceivedTime es datetime nativo en Win32com (pywintypes.datetime).
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


def parse_iso_date(s: str | None) -> datetime.date | None:
    """Parsea string ISO 8601 ('YYYY-MM-DD') a datetime.date.

    Args:
        s: String en formato ISO 8601, o None/empty.

    Returns:
        datetime.date si se pudo parsear. None si s es None/empty/invalid.

    Examples:
        >>> parse_iso_date("2026-05-13")
        datetime.date(2026, 5, 13)
        >>> parse_iso_date(None) is None
        True
        >>> parse_iso_date("") is None
        True
        >>> parse_iso_date("2026/05/13") is None  # solo ISO
        True
    """
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        log.warning("Fecha invalida (esperaba ISO 8601 YYYY-MM-DD): %r", s)
        return None


def should_include(
    received: datetime.datetime | datetime.date | None,
    date_from: datetime.date | None,
    date_to: datetime.date | None,
) -> bool:
    """True si el item debe incluirse en el backup segun el rango de fechas.

    Logica (filtro inclusivo en ambos extremos):
    - Sin date_from ni date_to: incluir todo (no hay filter activo).
    - Solo date_from: incluir si received >= date_from.
    - Solo date_to: incluir si received <= date_to.
    - Ambos: incluir si date_from <= received <= date_to.
    - Si received es None (item sin fecha conocida): EXCLUIR si hay filter activo
      (mejor conservador que perder data — pero loggear).

    Args:
        received: Fecha del email (ReceivedTime de Outlook COM). Datetime o date.
        date_from: Limite inferior inclusivo. None = sin limite inferior.
        date_to: Limite superior inclusivo. None = sin limite superior.

    Returns:
        True si el item califica para el backup.
    """
    # Sin filter: incluir todo
    if date_from is None and date_to is None:
        return True

    if received is None:
        log.debug("Item sin ReceivedTime; excluyendo por filter activo")
        return False

    # Normalizar a date (drop time component)
    if isinstance(received, datetime.datetime):
        received_date = received.date()
    elif isinstance(received, datetime.date):
        received_date = received
    else:
        log.warning("ReceivedTime tipo inesperado: %r", type(received).__name__)
        return False

    out_of_lower = date_from is not None and received_date < date_from
    out_of_upper = date_to is not None and received_date > date_to
    return not (out_of_lower or out_of_upper)


def filter_pst_items(
    root_folder: Any,
    date_from: datetime.date | None,
    date_to: datetime.date | None,
    progress_cb: Callable[[str], None] | None = None,
) -> int:
    """Recorre un PST montado y elimina items fuera del rango de fechas.

    Esta funcion es el wire-up con Outlook COM. Para tests en Linux sin Outlook,
    el caller debe pasar un mock o fake folder con la misma API:
        - root_folder.Folders → iterable de subfolders
        - root_folder.Items → iterable de items con .ReceivedTime y .Delete()

    Si date_from y date_to son ambos None, retorna 0 sin recorrer nada (no-op).

    Args:
        root_folder: Folder raiz del PST montado (Outlook MAPIFolder).
        date_from: Fecha minima inclusiva. None = sin limite inferior.
        date_to: Fecha maxima inclusiva. None = sin limite superior.
        progress_cb: Callback opcional para reportar progreso.

    Returns:
        Numero total de items eliminados.
    """
    if date_from is None and date_to is None:
        return 0

    deleted_count = 0

    def _process_folder(folder: Any, depth: int = 0) -> int:
        """Recorre folder + subfolders, devuelve count eliminados."""
        local_deleted = 0

        # Iterar items (en reverse para evitar reindexing al borrar)
        try:
            items = list(folder.Items)  # snapshot para safety
        except (AttributeError, Exception):  # noqa: BLE001
            items = []

        for item in reversed(items):
            try:
                received = getattr(item, "ReceivedTime", None)
                if not should_include(received, date_from, date_to):
                    item.Delete()
                    local_deleted += 1
            except (AttributeError, Exception):  # noqa: BLE001
                # Item raro (ej: meeting request sin ReceivedTime); skip
                continue

        # Recurse en subfolders
        try:
            subfolders = list(folder.Folders)
        except (AttributeError, Exception):  # noqa: BLE001
            subfolders = []

        for sub in subfolders:
            local_deleted += _process_folder(sub, depth + 1)

        return local_deleted

    deleted_count = _process_folder(root_folder)

    if progress_cb and deleted_count > 0:
        progress_cb(f"  🗑️ {deleted_count}件のメールを日付範囲外で削除しました")

    return deleted_count
