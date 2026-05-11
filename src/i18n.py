"""i18n loader — carga strings desde el ja.json compartido con el frontend.

Fuente unica de verdad: `src/web/js/i18n/ja.json`. El frontend lo lee con
fetch(); el backend con json.load(). Asi no hay divergencia entre los
mensajes que el usuario ve via UI vs los que Python loguea/genera.

Uso:
    from i18n import t

    label = t("tab_backup")
    msg = t("confirm_backup_msg", count=3, dir="C:\\\\Backup")

Si la key no existe (o el archivo no se pudo leer), `t()` devuelve la key
tal cual. Esto es defensivo — nunca crashea por una key faltante.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# Path al ja.json. En dev: src/i18n.py -> src/web/js/i18n/ja.json
# En binario PyInstaller: _MEIPASS/i18n.py -> _MEIPASS/web/js/i18n/ja.json
# El spec copia src/web/ a web/ en el binario, asi que el path relativo
# desde i18n.py funciona en ambos.
_JA_JSON_PATH = Path(__file__).parent / "web" / "js" / "i18n" / "ja.json"


@lru_cache(maxsize=1)
def _load_strings() -> dict[str, str]:
    """Carga el JSON una vez y cachea. lru_cache(maxsize=1) sirve como singleton."""
    try:
        with open(_JA_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (OSError, json.JSONDecodeError):
        # ja.json no encontrado o corrupto — caller recibe key como fallback
        return {}


def t(key: str, **kwargs: Any) -> str:
    """Devuelve el string traducido. Soporta formato con kwargs.

    Args:
        key: Clave en ja.json (ej. "tab_backup", "confirm_backup_msg").
        **kwargs: Sustituciones para `{name}` en el template.

    Returns:
        El string traducido. Si la key no existe, devuelve la key sin cambios.
    """
    text = _load_strings().get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def all_strings() -> dict[str, str]:
    """Devuelve una copia del dict de strings cargados. Util para debug/test."""
    return dict(_load_strings())
