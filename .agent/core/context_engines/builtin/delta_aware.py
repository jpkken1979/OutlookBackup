"""Delta-aware engine — marca archivos grandes para hint de ruteo delta.

No llama `delta_read` directamente (eso lo decide el cliente IA). Su trabajo
es INFORMAR al prompt que ciertos archivos son grandes y se beneficiarian de
releerlos con el MCP `antigravity-delta-reader` en vez del `Read` nativo.

Config:
    ANTIGRAVITY_CONTEXT_DELTA_MIN_LINES: int — umbral (default 50, coincide con delta_reader).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ..base import ContextEngineInput, ContextEngineMetadata
from ..context_injection_compat import call_legacy_build

logger = logging.getLogger(__name__)


class DeltaAwareContextEngine:
    """Default + marca archivos > N lineas como candidatos a delta_read."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        return ContextEngineMetadata(
            name="delta_aware",
            description=(
                "Default + etiqueta archivos grandes con [delta] para que "
                "el cliente IA use `delta_read` en relecturas y ahorre tokens."
            ),
            requires=("delta_reader",),
            version="1.0.0",
        )

    async def prepare(self, inp: ContextEngineInput, base=None):  # type: ignore[no-untyped-def]
        if base is not None:
            ctx = base
        else:
            ctx = await call_legacy_build(
                task=inp.task,
                project_dir=inp.project_dir,
                current_file=inp.current_file,
                open_files=list(inp.open_files),
            )

        try:
            min_lines = int(os.environ.get("ANTIGRAVITY_CONTEXT_DELTA_MIN_LINES", "50") or 50)
        except ValueError:
            min_lines = 50

        proj = Path(inp.project_dir) if inp.project_dir else Path.cwd()
        marked_open: list[str] = []
        for f in ctx.open_files:
            path = Path(f) if Path(f).is_absolute() else proj / f
            if _line_count_over_threshold(path, min_lines):
                marked_open.append(f"[delta] {f}")
            else:
                marked_open.append(f)
        ctx.open_files = marked_open

        if ctx.current_file:
            cur_path = Path(ctx.current_file)
            if not cur_path.is_absolute():
                cur_path = proj / cur_path
            if _line_count_over_threshold(cur_path, min_lines):
                ctx.current_file = f"[delta] {ctx.current_file}"

        return ctx


def _line_count_over_threshold(path: Path, threshold: int) -> bool:
    """Retorna True si el archivo tiene > threshold lineas y es texto UTF-8."""
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
        # Heuristica rapida: si pesa > 100KB es casi seguro grande (evita leer completo).
        if size > 100_000:
            return True
        # Contamos lineas solo si es texto razonable.
        with path.open("rb") as fh:
            chunk = fh.read(8192)
            if b"\x00" in chunk:
                return False  # binario
        count = 0
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for count, _ in enumerate(fh, start=1):
                if count > threshold:
                    return True
        return count > threshold
    except OSError as exc:
        logger.debug("delta_aware line count fallo %s: %s", path, exc)
        return False
