"""Brain-aware engine — consulta Brain Network antes de cada turno.

Extiende el `default` con top-K resultados del Brain inyectados en
`memory_hints`. Usa la misma `InjectionContext` para no romper consumidores.

Config:
    ANTIGRAVITY_CONTEXT_BRAIN_K: int — top-K resultados a inyectar (default 3).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from ..base import ContextEngineInput, ContextEngineMetadata
from ..context_injection_compat import call_legacy_build

logger = logging.getLogger(__name__)


class BrainAwareContextEngine:
    """Default + top-K del Brain Network en memory_hints."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        return ContextEngineMetadata(
            name="brain_aware",
            description=(
                "Default + top-K del Brain Network antes de cada turno. "
                "Ideal para sesiones largas en el mismo dominio."
            ),
            requires=("brain",),
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
            k = int(os.environ.get("ANTIGRAVITY_CONTEXT_BRAIN_K", "3") or 3)
        except ValueError:
            k = 3

        try:
            agent_dir = Path(__file__).resolve().parent.parent.parent.parent
            if str(agent_dir) not in sys.path:
                sys.path.insert(0, str(agent_dir))
            from core.brain import Brain  # type: ignore[import-not-found]

            brain_dir = agent_dir / "brain"
            if not brain_dir.exists():
                return ctx
            brain = Brain(brain_dir, app_id=inp.extras.get("app_id", "nexus-mother"))
            results = brain.query(inp.task, limit=k)
            hints: list[str] = []
            for r in results[:k]:
                title = getattr(r, "title", None) or getattr(r, "slug", "?")
                body = getattr(r, "context", "") or ""
                hints.append(f"[brain] {title}: {body[:120]}")
            # Prepend brain hints preservando los pre-existentes
            ctx.memory_hints = [*hints, *(ctx.memory_hints or [])]
        except Exception as exc:  # noqa: BLE001
            logger.debug("brain_aware skip: %s", exc)
        return ctx
