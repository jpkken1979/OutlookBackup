"""Composite engine — encadena otros engines para combinar sus senales.

La chain por default es:
    delta_aware -> brain_aware -> summarizing -> domain_uns

El primero genera el contexto base; los siguientes reciben el contexto ya
enriquecido y solo pueden AGREGAR (no sobreescribir fields raw como stack
o project_dir). Internamente cada engine llama a `call_legacy_build` que
tiene side-effects acotados; para que el pipeline sume sin duplicar, cada
engine agrega a listas existentes.

Config:
    ANTIGRAVITY_CONTEXT_COMPOSITE_CHAIN: str — lista separada por coma.
    Ej: "default" (desactiva composite), "brain_aware,domain_uns".
"""

from __future__ import annotations

import logging
import os

from ..base import ContextEngineInput, ContextEngineMetadata
from ..context_injection_compat import call_legacy_build

logger = logging.getLogger(__name__)

_DEFAULT_CHAIN = ("delta_aware", "brain_aware", "summarizing", "domain_uns")


class CompositeContextEngine:
    """Encadena engines built-in. Default chain cubre la mayoria de casos."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        return ContextEngineMetadata(
            name="composite",
            description=(
                "Chain configurable: delta_aware + brain_aware + summarizing + domain_uns. "
                "Recomendado para sesiones intensivas."
            ),
            requires=("brain",),
            version="1.0.0",
        )

    async def prepare(self, inp: ContextEngineInput, base=None):  # type: ignore[no-untyped-def]
        chain = _load_chain()
        if not chain:
            if base is not None:
                return base
            return await call_legacy_build(
                task=inp.task,
                project_dir=inp.project_dir,
                current_file=inp.current_file,
                open_files=list(inp.open_files),
            )

        # Import tardio para evitar ciclo con el registry.
        from ..registry import _ensure_loaded, _registry

        _ensure_loaded()

        ctx = base
        for name in chain:
            if name == "composite":
                continue  # proteccion contra recursion infinita
            engine = _registry.get(name)
            if engine is None:
                logger.debug("composite: engine %r no disponible, skip", name)
                continue
            # Pasamos el ctx acumulado para que cada engine sume sobre el
            # trabajo del anterior en vez de reconstruir desde cero.
            ctx = await engine.prepare(inp, base=ctx)

        if ctx is None:
            ctx = await call_legacy_build(
                task=inp.task,
                project_dir=inp.project_dir,
                current_file=inp.current_file,
                open_files=list(inp.open_files),
            )
        return ctx


def _load_chain() -> tuple[str, ...]:
    override = os.environ.get("ANTIGRAVITY_CONTEXT_COMPOSITE_CHAIN", "").strip()
    if override:
        parts = tuple(p.strip() for p in override.split(",") if p.strip())
        if parts:
            return parts
    return _DEFAULT_CHAIN
