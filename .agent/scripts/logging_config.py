#!/usr/bin/env python3
"""
Módulo de logging estándar para el ecosistema Antigravity.

Este módulo proporciona configuración de logging consistente
para todos los scripts del ecosistema.

Uso:
    from logging_config import setup_logger
    logger = setup_logger(__name__)
    logger.info("Mensaje")
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str, level: int = logging.INFO, log_file: Path | None = None, console: bool = True
) -> logging.Logger:
    """
    Configura y retorna un logger con formato Antigravity estándar.

    Args:
        name: Nombre del logger (típicamente __name__)
        level: Nivel de logging (default: INFO)
        log_file: Ruta opcional para archivo de log
        console: Si debe mostrar en consola (default: True)

    Returns:
        Logger configurado

    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Proceso iniciado")
        [2026-02-01 10:30:00] [INFO] [module] Proceso iniciado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar handlers duplicados
    if logger.handlers:
        return logger

    # Formato estándar Antigravity
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler de consola
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Handler de archivo (opcional)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_log_path(script_name: str) -> Path:
    """
    Genera la ruta de log para un script.

    Args:
        script_name: Nombre del script

    Returns:
        Path al archivo de log
    """
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return logs_dir / f"{script_name}_{date_str}.log"


class LogContext:
    """
    Context manager para logging de operaciones.

    Example:
        with LogContext(logger, "Procesando archivo"):
            # operaciones...
    """

    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Iniciando: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb):
        elapsed = datetime.now() - self.start_time
        if exc_type is None:
            self.logger.info(f"Completado: {self.operation} ({elapsed.total_seconds():.2f}s)")
        else:
            self.logger.error(f"Error en: {self.operation} - {exc_val}")
        return False


# Logger global para el ecosistema
antigravity_logger = setup_logger("antigravity")


if __name__ == "__main__":
    # Ejemplo de uso
    logger = setup_logger("test_module", log_file=get_log_path("test"))

    logger.debug("Mensaje de debug")
    logger.info("Mensaje de información")
    logger.warning("Mensaje de advertencia")
    logger.error("Mensaje de error")

    with LogContext(logger, "Operación de prueba"):
        import time

        time.sleep(0.5)

    print("\n✓ Logging configurado correctamente")
