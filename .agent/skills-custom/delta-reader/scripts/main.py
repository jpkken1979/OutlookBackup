"""Delta Reader skill wrapper — entry point Pydantic-compatible.

Permite invocar el engine desde el skill runner del ecosistema con
validacion input/output estandar. El engine real vive en
`.agent/core/delta_reader.py`; este archivo es solo la fachada.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

# Permitir ejecutar el skill sin instalar el paquete.
_here = Path(__file__).resolve()
_agent_dir = (
    _here.parent.parent.parent.parent
)  # .agent/skills-custom/delta-reader/scripts/ → .agent/
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

try:
    from pydantic import BaseModel, Field

    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover
    _HAS_PYDANTIC = False

    # Fallback minimal: sin validacion pero compatible con el runner.
    # Los defaults de Field() se honran; Field(...) indica requerido y
    # falla al __init__ si no se pasa el argumento.
    _REQUIRED_SENTINEL = object()

    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs: object) -> None:
            # Aplicar defaults declarados en la clase.
            for name in getattr(type(self), "__annotations__", {}):
                if name in kwargs:
                    setattr(self, name, kwargs[name])
                    continue
                default = getattr(type(self), name, _REQUIRED_SENTINEL)
                if default is _REQUIRED_SENTINEL:
                    raise TypeError(f"Falta argumento requerido: {name}")
                setattr(self, name, default)

        def model_dump(self) -> dict[str, object]:
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def Field(  # type: ignore[no-redef]
        default: object = _REQUIRED_SENTINEL,
        *,
        default_factory: object = None,
        **_: object,
    ) -> object:
        if default_factory is not None and callable(default_factory):
            return default_factory()
        # Ellipsis (...) se usa para campos requeridos; convertimos al sentinel.
        if default is Ellipsis:
            return _REQUIRED_SENTINEL
        return default


from core.delta_reader import DeltaReader, default_state_path  # noqa: E402


class Input(BaseModel):
    """Parametros de lectura."""

    path: str = Field(..., description="Ruta al archivo a leer")
    session_id: str = Field(
        default="skill-default",
        description="ID logico de sesion para compartir snapshots",
    )
    force_full: bool = Field(
        default=False,
        description="Si True, ignora snapshot previa",
    )


class Output(BaseModel):
    """Resultado estandarizado."""

    mode: Literal["full", "delta", "unchanged", "external_edit", "error"]
    path: str
    session_id: str
    content: str = ""
    diff: str = ""
    prior_turn: int | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    status: Literal["success", "error"] = "success"


_reader_singleton: DeltaReader | None = None


def _get_reader() -> DeltaReader:
    global _reader_singleton
    if _reader_singleton is None:
        _reader_singleton = DeltaReader(default_state_path())
    return _reader_singleton


def execute(input_args: Input) -> Output:
    """Ejecuta una lectura delta-aware.

    Args:
        input_args: path, session_id, force_full.

    Returns:
        Output con mode, content/diff, stats.
    """
    reader = _get_reader()
    result = reader.read(
        input_args.path,
        session_id=input_args.session_id,
        force_full=input_args.force_full,
    )
    status: Literal["success", "error"] = "error" if result.mode == "error" else "success"
    return Output(
        mode=result.mode,
        path=result.path,
        session_id=result.session_id,
        content=result.content,
        diff=result.diff,
        prior_turn=result.prior_turn,
        stats=result.stats,
        error=result.error,
        status=status,
    )
