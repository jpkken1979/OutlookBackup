"""Pluggable Context Engines — estrategias intercambiables de preparacion de contexto.

Cada engine recibe una tarea y opciones (project_dir, current_file, open_files,
history) y retorna un `InjectionContext` listo para enriquecer el prompt del
agente. Los engines son composable: `composite` encadena varios para combinar
sus senales.

Uso publico:
    from core.context_engines import get_engine, list_engines

    engine = get_engine()              # lee config/env
    engine = get_engine("brain_aware") # explicito
    ctx = await engine.prepare(task="...", current_file="...")

Engines built-in disponibles (ver `list_engines()` para detalle en runtime):
    - default:      baseline, idéntico al `build_injection_context()` historico
    - brain_aware:  inyecta top-3 del Brain Network antes de cada turno
    - delta_aware:  marca archivos grandes con [delta] para hint de ruteo
    - summarizing:  comprime open_files > N si son muchos
    - domain_uns:   detecta keywords dispatch japones (派遣, 個別契約) y agrega nota
    - composite:    chain configurable de otros engines

Extension: plugins pueden registrar engines propios via `register_engine()`.
"""

from __future__ import annotations

from .base import (
    ContextEngine,
    ContextEngineInput,
    ContextEngineMetadata,
)
from .registry import (
    get_engine,
    list_engines,
    register_engine,
    resolve_engine_name,
)

__all__ = [
    "ContextEngine",
    "ContextEngineInput",
    "ContextEngineMetadata",
    "get_engine",
    "list_engines",
    "register_engine",
    "resolve_engine_name",
]
