"""Default engine — comportamiento baseline, snapshot-identico al pre-refactor.

Envuelve `build_injection_context()` tal cual existia antes de la introduccion
del sistema de engines. Sirve como referencia para snapshot tests y como
fallback si la seleccion falla.
"""

from __future__ import annotations

from ..base import ContextEngineInput, ContextEngineMetadata


class DefaultContextEngine:
    """Engine baseline, sin modificaciones sobre el historial de build_injection_context."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        return ContextEngineMetadata(
            name="default",
            description=(
                "Baseline — recopila stack, memoria y observaciones como siempre. "
                "Sin optimizaciones extra."
            ),
            requires=(),
            version="1.0.0",
        )

    async def prepare(self, inp: ContextEngineInput, base=None):  # type: ignore[no-untyped-def]
        if base is not None:
            return base
        # Import tardio para romper ciclo: context_injection -> registry -> default
        from ..context_injection_compat import call_legacy_build

        return await call_legacy_build(
            task=inp.task,
            project_dir=inp.project_dir,
            current_file=inp.current_file,
            open_files=list(inp.open_files),
        )
