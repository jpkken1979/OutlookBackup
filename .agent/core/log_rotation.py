"""Utilidad de rotación best-effort para archivos JSONL append-only.

Previene que logs de escritura continua superen el límite de 32 MB de la
API de Anthropic conservando sólo las últimas N líneas cuando el archivo
excede el umbral configurado.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def rotate_jsonl_if_needed(path: Path, max_lines: int = 2000) -> None:
    """Truncar un JSONL a las últimas *max_lines* líneas si lo supera.

    La operación es atómica: escribe a un archivo temporal en el mismo
    directorio y luego hace ``os.replace`` para evitar datos corruptos
    ante cortes de proceso o disco lleno.

    La función es **best-effort**: cualquier excepción se loguea como
    ``WARNING`` y nunca se propaga al caller.

    Args:
        path: Ruta al archivo JSONL a proteger.
        max_lines: Número máximo de líneas a conservar (las más recientes).
            Debe ser un entero positivo; valores <= 0 se ignoran sin error.
    """
    if max_lines <= 0:
        return

    try:
        if not path.exists():
            return

        raw = path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()

        if len(lines) <= max_lines:
            return

        logger.debug(
            "Rotando %s: %d líneas → últimas %d",
            path,
            len(lines),
            max_lines,
        )

        trimmed = lines[-max_lines:]
        content = "\n".join(trimmed) + "\n"

        # Escritura atómica: temporal en el mismo dir para que os.replace
        # sea una operación dentro del mismo filesystem (rename).
        dir_ = path.parent
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp_path, path)
        except Exception:
            # Limpiar el temporal si algo falló después de crearlo.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.info(
            "Log rotado: %s conservó %d/%d líneas",
            path,
            max_lines,
            len(lines),
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning("rotate_jsonl_if_needed falló para %s: %s", path, exc)
