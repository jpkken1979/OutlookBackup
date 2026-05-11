"""Capa de observabilidad — logging estructurado, crash reporting, update check.

Tres modulos:
- `logging`: setup_logger() configura structlog con dos sinks (JSON a archivo +
  consola formateada). Reemplaza el `logging.basicConfig` que estaba en main.py.
- `crash`: install_crash_handler() instala un sys.excepthook que guarda
  crash_{ts}.json sanitizado a APPDATA cuando hay excepcion no atrapada.
- `updater`: check_for_updates() consulta GitHub Releases para ver si hay
  version mas nueva. Solo informa, no auto-instala.

Diseno:
- Sin dependencia entre modulos — cada uno se puede usar independiente.
- main.py los compone: setup_logger() primero, install_crash_handler() segundo,
  check_for_updates() en background opcional.
"""

from observability.crash import install_crash_handler, sanitize_for_crash_report
from observability.logging import get_logger, setup_logger
from observability.updater import UpdateInfo, check_for_updates

__all__ = [
    "UpdateInfo",
    "check_for_updates",
    "get_logger",
    "install_crash_handler",
    "sanitize_for_crash_report",
    "setup_logger",
]
