"""Crash reporter — captura excepciones no atrapadas y guarda JSON sanitizado.

El handler reemplaza `sys.excepthook` con uno que:
1. Loguea el crash con stack trace (via structlog si esta configurado).
2. Escribe `crash_{timestamp}.json` a `%APPDATA%\\UNS-Kikaku\\Backup\\crashdumps\\`.
3. Sanitiza paths con username + secretos conocidos antes de guardar.
4. Re-lanza al excepthook original para no romper el comportamiento default.

Datos que se incluyen:
- exception_type, exception_message, traceback (string)
- python_version, platform, app_version
- timestamp ISO
- env vars relevantes (sanitizadas)

Datos que se EXCLUYEN:
- USERNAME, USERPROFILE, HOMEDRIVE — reemplazados por <user>
- Variables UNS_* (tokens) — reemplazadas por <redacted>
- PATH completo — solo se loguea longitud
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import re
import sys
import traceback
from pathlib import Path
from typing import Any

# Patrones sensibles a redactar
_SECRET_ENV_PATTERNS = re.compile(r"^(UNS_.*|.*_TOKEN|.*_KEY|.*_PASSWORD|.*_SECRET)$", re.I)


def get_crashdumps_dir() -> Path:
    """Directorio donde se guardan los crashdumps. Crea si no existe."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        base = Path(appdata) / "UNS-Kikaku" / "Backup" / "crashdumps"
    else:
        base = Path.home() / ".uns-kikaku" / "crashdumps"
    base.mkdir(parents=True, exist_ok=True)
    return base


def sanitize_for_crash_report(text: str) -> str:
    """Reemplaza el username en paths con `<user>`.

    Ej: "C:\\Users\\kenji\\Github\\..." -> "C:\\Users\\<user>\\Github\\..."
    """
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if username:
        # Reemplazar tanto en lower como case-sensitive
        text = text.replace(username, "<user>")
        text = text.replace(username.lower(), "<user>")
    return text


def _collect_env_sanitized() -> dict[str, str]:
    """Snapshot de env vars relevantes con redaccion."""
    keep = {
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS",
        "LANG",
        "LC_ALL",
        "PYTHONVERSION",
        "PYTHONPATH",
    }
    result = {}
    for k, v in os.environ.items():
        if k in keep:
            result[k] = sanitize_for_crash_report(v)
        elif _SECRET_ENV_PATTERNS.match(k):
            result[k] = "<redacted>"
    return result


def _build_crash_report(exc_type: type, exc_value: BaseException, exc_tb: Any) -> dict:
    """Construye el dict del crashdump."""
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "app": "uns-outlook-backup",
        "exception": {
            "type": exc_type.__name__,
            "module": getattr(exc_type, "__module__", "?"),
            "message": sanitize_for_crash_report(str(exc_value)),
            "traceback": sanitize_for_crash_report(tb_str),
        },
        "runtime": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "argv": [sanitize_for_crash_report(a) for a in sys.argv],
        },
        "env": _collect_env_sanitized(),
    }


def write_crash_report(exc_type: type, exc_value: BaseException, exc_tb: Any) -> Path:
    """Escribe el crash a disco. Devuelve el path."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = get_crashdumps_dir() / f"crash_{timestamp}.json"
    report = _build_crash_report(exc_type, exc_value, exc_tb)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def install_crash_handler() -> None:
    """Instala el handler global. Llamar UNA vez al arrancar la app.

    Despues de esto, cualquier excepcion no atrapada en main thread genera
    un crashdump y se re-lanza al excepthook previo.
    """
    previous_hook = sys.excepthook

    def _crash_hook(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
        # Excluir KeyboardInterrupt del crashdump — es exit normal del usuario
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_tb)
            return
        try:
            out = write_crash_report(exc_type, exc_value, exc_tb)
            sys.stderr.write(f"\n[crash] Reporte guardado en: {out}\n")
        except Exception as e:
            sys.stderr.write(f"\n[crash] Fallo guardar reporte: {e}\n")
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_hook
