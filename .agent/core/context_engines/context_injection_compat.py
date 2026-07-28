"""Shim para evitar ciclo de import entre context_engines y context_injection.

Los engines necesitan acceder a `build_injection_context` y a `InjectionContext`
del modulo padre, pero `context_injection.py` expone `get_engine()` desde este
subpaquete. Para romper el ciclo, los engines importan desde aca y el import
real se resuelve lazy la primera vez que se llama.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..context_injection import InjectionContext

_legacy_fn: Any = None


async def call_legacy_build(
    task: str,
    project_dir: str | None = None,
    current_file: str | None = None,
    open_files: list[str] | None = None,
) -> InjectionContext:
    """Llama `build_injection_context` resolviendo el import lazy."""
    global _legacy_fn
    if _legacy_fn is None:
        from ..context_injection import build_injection_context

        _legacy_fn = build_injection_context
    return await _legacy_fn(
        task,
        project_dir=project_dir,
        current_file=current_file,
        open_files=open_files,
    )


def make_empty_context(task: str = "") -> InjectionContext:
    """Construye un InjectionContext vacio — utilidad para engines."""
    from ..context_injection import InjectionContext

    return InjectionContext(task=task)
