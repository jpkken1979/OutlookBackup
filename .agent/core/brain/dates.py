"""Normalizacion de fechas heterogeneas del Brain.

PyYAML parsea campos de fecha sin comillas como ``datetime.date``, pero los
nodos creados por codigo o con comillas en el frontmatter tienen ``str``. Estos
helpers normalizan ambos a ISO string para que el sort no explote con
``TypeError`` al comparar tipos distintos.

Extraido del monolito ``brain.py`` (refactor 2026-05-31). Sin cambios de
comportamiento.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import BrainNode


def _date_sort_key(n: BrainNode) -> str:
    """Clave de ordenamiento tolerante a date/str/None en n.date.

    PyYAML parsea campos de fecha sin comillas como datetime.date, pero
    nodos creados por codigo o con comillas en el frontmatter tienen str.
    Esta helper normaliza ambos a ISO string para que sort no explote con
    TypeError al comparar instancias de tipos distintos.

    Args:
        n: Nodo del brain a ordenar.

    Returns:
        Fecha como string ISO YYYY-MM-DD, o string vacio si es None/invalido.
    """
    return _normalize_date_value(n.date)


def _normalize_date_value(value: Any) -> str:
    """Normaliza fecha heterogenea (date/datetime/str/None) a string ISO.

    Args:
        value: Valor de fecha en cualquier formato tolerado.

    Returns:
        Fecha normalizada como string ISO (YYYY-MM-DD) o "" si es vacio.
    """
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        # datetime.date o datetime.datetime
        return value.isoformat()
    return str(value)


def _parse_date_value(value: Any) -> datetime | None:
    """Parsea fecha heterogenea y devuelve datetime naive o None.

    Args:
        value: Fecha como date/datetime/str.

    Returns:
        datetime parseado o None si no se pudo interpretar.
    """
    normalized = _normalize_date_value(value)
    if not normalized:
        return None

    # Soporta YYYY-MM-DD y datetime ISO tomando solo la parte de fecha.
    date_part = normalized[:10]
    try:
        return datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        return None
