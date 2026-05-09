"""Base contracts for Context Engines.

Un `ContextEngine` es una estrategia que, dado un `ContextEngineInput`,
produce un `InjectionContext` listo para enriquecer el prompt del agente.

Los engines son async para permitir I/O (Brain query, memory router,
delta_read). Sincronos pueden implementarse trivialmente envolviendo el
resultado en `asyncio`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..context_injection import InjectionContext


@dataclass(frozen=True)
class ContextEngineInput:
    """Entrada estandar para un engine.

    Args:
        task: descripcion de la tarea del usuario (obligatoria).
        project_dir: ruta al proyecto; None usa CWD.
        current_file: archivo en foco en el editor.
        open_files: otros archivos abiertos (paths relativos o absolutos).
        history: turnos previos de la sesion (opcional, usado por summarizing).
        extras: metadata libre para engines custom (app_id, session_id, etc).
    """

    task: str = ""
    project_dir: str | None = None
    current_file: str | None = None
    open_files: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextEngineMetadata:
    """Descripcion estatica de un engine para la UI / MCP tools.

    Args:
        name: slug unico (snake_case).
        description: 1-2 oraciones en espanol.
        requires: capacidades que necesita (ej: "brain", "memory_router",
            "delta_reader"). Se informan al usuario si faltan.
        version: semver del engine para auditoria.
    """

    name: str
    description: str
    requires: tuple[str, ...] = ()
    version: str = "1.0.0"


@runtime_checkable
class ContextEngine(Protocol):
    """Protocolo que toda estrategia de context engine debe satisfacer."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        """Retorna metadata estatica del engine."""
        ...

    async def prepare(
        self,
        inp: ContextEngineInput,
        base: InjectionContext | None = None,
    ) -> InjectionContext:
        """Produce el contexto enriquecido para una tarea dada.

        Args:
            inp: entrada con task, project_dir, archivos, history, extras.
            base: contexto previo (usado por composite chain). Si es None,
                el engine construye desde cero. Si se pasa, el engine suma
                sobre ese contexto sin perder las senales acumuladas.

        Returns:
            InjectionContext listo para `enhance_agent_prompt()`.
        """
        ...
