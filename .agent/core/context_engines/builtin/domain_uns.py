"""Domain UNS engine — detecta keywords de dispatch japones y agrega reglas.

Cuando la tarea o los archivos tocan temas de dispatch (派遣), contratos
individuales (個別契約書), seguros sociales o datos bancarios UNS, el engine
agrega un bullet con las restricciones clave del dominio:

- Datos sensibles UNS solo en env vars (UNS_BANK_*, UNS_DISPATCH_LICENSE).
- Formato 個別契約書 sigue el template oficial.
- Fechas en formato japones (和暦).

Esto reduce la chance de que el agente olvide reglas del dominio en sesiones
largas o multi-proyecto.

Config:
    ANTIGRAVITY_CONTEXT_DOMAIN_KEYWORDS: str — override de keywords (separadas por coma).
"""

from __future__ import annotations

import logging
import os

from ..base import ContextEngineInput, ContextEngineMetadata
from ..context_injection_compat import call_legacy_build

logger = logging.getLogger(__name__)

_DEFAULT_KEYWORDS = (
    "派遣",
    "個別契約",
    "労働者派遣",
    "dispatch",
    "uns_bank",
    "uns_dispatch",
    "特定派遣",
    "社会保険",
    "源泉徴収",
    "tokubetsu_jintai",
)

_DOMAIN_REMINDER = (
    "[domain_uns] Proyecto UNS detectado: "
    "secretos bancarios y dispatch solo en env vars (UNS_BANK_*, UNS_DISPATCH_LICENSE); "
    "形式 de 個別契約書 segun template oficial; "
    "fechas preferidas en 和暦 cuando aplica."
)


class DomainUnsContextEngine:
    """Default + recordatorio de reglas UNS cuando se detectan keywords del dominio."""

    @property
    def metadata(self) -> ContextEngineMetadata:
        return ContextEngineMetadata(
            name="domain_uns",
            description=(
                "Default + recordatorio de reglas UNS (dispatch japones) cuando la tarea "
                "o los archivos contienen keywords del dominio."
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

        keywords = _load_keywords()
        haystack = " ".join(
            [
                inp.task or "",
                inp.current_file or "",
                *(inp.open_files or []),
                " ".join(ctx.memory_hints or []),
            ]
        ).lower()

        if any(kw.lower() in haystack for kw in keywords):
            ctx.memory_hints = [_DOMAIN_REMINDER, *(ctx.memory_hints or [])]

        return ctx


def _load_keywords() -> tuple[str, ...]:
    override = os.environ.get("ANTIGRAVITY_CONTEXT_DOMAIN_KEYWORDS", "").strip()
    if override:
        parts = tuple(p.strip() for p in override.split(",") if p.strip())
        if parts:
            return parts
    return _DEFAULT_KEYWORDS
