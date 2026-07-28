"""Summarizing engine — comprime open_files y history grandes.

No usa LLM (eso seria acople y latencia). Aplica heuristicas:
    - Si `open_files` > N, agrupa por extension y menciona el subset relevante.
    - Si `history` es largo, resume en 1 bullet por turno con los primeros 80 chars.

Util cuando la sesion arrastra mucho estado y el prompt se infla.

Config:
    ANTIGRAVITY_CONTEXT_SUMMARY_FILE_LIMIT: int — default 10
    ANTIGRAVITY_CONTEXT_SUMMARY_HISTORY_LIMIT: int — default 8
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from pathlib import Path

from ..base import ContextEngineInput, ContextEngineMetadata
from ..context_injection_compat import call_legacy_build

logger = logging.getLogger(__name__)


class SummarizingContextEngine:
    """Default + compresion heuristica de open_files y history largos."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        return ContextEngineMetadata(
            name="summarizing",
            description=(
                "Default + comprime open_files (agrupa por extension) e "
                "historial de turnos (bullets de 80 chars)."
            ),
            requires=(),
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
            file_limit = int(os.environ.get("ANTIGRAVITY_CONTEXT_SUMMARY_FILE_LIMIT", "10") or 10)
            history_limit = int(
                os.environ.get("ANTIGRAVITY_CONTEXT_SUMMARY_HISTORY_LIMIT", "8") or 8
            )
        except ValueError:
            file_limit, history_limit = 10, 8

        if len(ctx.open_files) > file_limit:
            ctx.open_files = _summarize_file_list(ctx.open_files, file_limit)

        # history viene del extras, no de InjectionContext directamente.
        history = inp.history or []
        if len(history) > history_limit:
            summary = _summarize_history(history, history_limit)
            # Agregamos al final de memory_hints para no perder.
            if summary:
                ctx.memory_hints = [*(ctx.memory_hints or []), summary]

        return ctx


def _summarize_file_list(files: list[str], limit: int) -> list[str]:
    """Deja los primeros `limit` y agrega una linea resumen por extension."""
    head = files[:limit]
    rest = files[limit:]
    if not rest:
        return head
    counter: Counter[str] = Counter()
    for f in rest:
        ext = Path(f).suffix or "(sin ext)"
        counter[ext] += 1
    summary_parts = [f"{n}×{ext}" for ext, n in counter.most_common(5)]
    head.append(f"[+{len(rest)} archivos: {', '.join(summary_parts)}]")
    return head


def _summarize_history(history: list[dict], keep_tail: int) -> str:
    """Resume turnos antiguos en un solo bullet."""
    old = history[:-keep_tail]
    if not old:
        return ""
    parts: list[str] = []
    for turn in old[-5:]:
        role = turn.get("role", "?")
        content = str(turn.get("content", ""))[:80]
        parts.append(f"{role}: {content}")
    return "[history] " + " | ".join(parts)
