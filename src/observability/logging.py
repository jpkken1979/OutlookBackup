"""Logging estructurado via structlog.

Dos sinks por defecto:
- Consola: formato legible con colores (cuando es TTY) o plain.
- Archivo JSON: una linea JSON por evento, para grep/jq/ingest en logs central.

Uso:
    from observability import setup_logger, get_logger

    setup_logger(json_file="auto.log")  # llamar UNA vez al arrancar la app
    log = get_logger(__name__)
    log.info("backup.started", account="kenji@uns-kikaku.com", n=42)

El logger de structlog es bound — cada call genera un evento estructurado.
A diferencia del logging stdlib, no necesitas % formatting ni concatenacion.
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from pathlib import Path
from typing import Any

import structlog


def setup_logger(
    *,
    json_file: str | Path | None = None,
    level: int = stdlib_logging.INFO,
    add_console: bool = True,
) -> None:
    """Configura structlog + stdlib logging.

    Args:
        json_file: si se da, escribe una linea JSON por evento. Path absoluto
            preferible; si es relativo se resuelve al cwd.
        level: nivel minimo (INFO default).
        add_console: si True, agrega un handler que va a stderr con formato
            legible (colores si es TTY).
    """
    handlers: list[stdlib_logging.Handler] = []

    if add_console:
        console_handler = stdlib_logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(
            stdlib_logging.Formatter("%(message)s"),  # structlog hace el formateo
        )
        handlers.append(console_handler)

    if json_file is not None:
        path = Path(json_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = stdlib_logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(stdlib_logging.Formatter("%(message)s"))
        handlers.append(file_handler)

    stdlib_logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=handlers,
        force=True,  # override config previa (ej. main.py:setup_logging viejo)
    )

    # Processors comunes: timestamp, level, callsite, exception
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            # Renderer final: JSON al archivo, console-friendly a la consola.
            # Como structlog usa un solo set de processors globalmente, lo
            # decidimos por presencia de TTY: si STDERR es TTY (modo dev), usar
            # ConsoleRenderer; sino JSON (modo auto / produccion).
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
            if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Devuelve un bound logger. `name` suele ser `__name__` del modulo caller."""
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bindea variables al contexto del thread (visibles en todos los logs siguientes).

    Util al arrancar una operacion larga:
        bind_context(operation="backup", session_id="abc123")
        log.info("starting")  # incluira operation y session_id

    Limpiar al final con `clear_context()`.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Limpia el contexto del thread."""
    structlog.contextvars.clear_contextvars()
