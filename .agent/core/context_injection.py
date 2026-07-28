"""Context Injection Protocol — enriquece invocaciones de agentes con contexto.

Cuando un agente se invoca desde un IDE o app, este módulo genera
un paquete de contexto relevante para inyectar en el prompt del agente.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LEGACY_MAX_FILES = 10
LEGACY_MAX_EDITS = 10
LEGACY_MAX_ERRORS = 5
LEGACY_MAX_DECISIONS = 5
LEGACY_MAX_MEMORY_HINTS = 5
MAX_FILES = 5
MAX_EDITS = 5
MAX_ERRORS = 3
MAX_DECISIONS = 3
MAX_MEMORY_HINTS = 3
MAX_ITEM_CHARS = 160
MAX_SECTION_CHARS = 1400


@dataclass
class InjectionContext:
    """Contexto inyectable para un agente."""

    task: str = ""
    current_file: str = ""
    recent_edits: list[str] = field(default_factory=list)
    project_stack: str = ""
    recent_errors: list[str] = field(default_factory=list)
    open_files: list[str] = field(default_factory=list)
    project_dir: str = ""
    relevant_decisions: list[str] = field(default_factory=list)
    memory_hints: list[str] = field(default_factory=list)

    def compact(self) -> InjectionContext:
        """Devuelve una copia compactada para inyeccion eficiente en tokens."""
        return InjectionContext(
            task=self.task.strip()[:MAX_ITEM_CHARS],
            current_file=self.current_file.strip()[:MAX_ITEM_CHARS],
            recent_edits=_compact_items(self.recent_edits, MAX_EDITS),
            project_stack=self.project_stack.strip()[:MAX_ITEM_CHARS],
            recent_errors=_compact_items(self.recent_errors, MAX_ERRORS),
            open_files=_compact_items(self.open_files, MAX_FILES),
            project_dir=self.project_dir.strip()[:MAX_ITEM_CHARS],
            relevant_decisions=_compact_items(self.relevant_decisions, MAX_DECISIONS),
            memory_hints=_compact_items(self.memory_hints, MAX_MEMORY_HINTS),
        )

    def to_prompt_section(self) -> str:
        """Genera sección de prompt con el contexto inyectado.

        Returns:
            Texto formateado para insertar en el prompt del agente.
        """
        compacted = self.compact()
        return _serialize_prompt_section(compacted, max_section_chars=MAX_SECTION_CHARS)

    def to_dict(self) -> dict[str, Any]:
        """Serializa el contexto a dict."""
        return asdict(self)


async def build_injection_context(
    task: str,
    *,
    project_dir: str | None = None,
    current_file: str | None = None,
    open_files: list[str] | None = None,
) -> InjectionContext:
    """Construye un contexto de inyección completo para un agente.

    Recopila información del proyecto, memoria y observaciones
    para enriquecer la ejecución del agente.

    Args:
        task: Descripción de la tarea.
        project_dir: Ruta al proyecto (detecta CWD si None).
        current_file: Archivo en el que trabaja el usuario.
        open_files: Archivos abiertos en el editor.

    Returns:
        InjectionContext listo para inyectar en el prompt.
    """
    ctx = InjectionContext(task=task)
    proj = Path(project_dir) if project_dir else Path.cwd()
    ctx.project_dir = str(proj)

    if current_file:
        ctx.current_file = current_file
    if open_files:
        ctx.open_files = open_files

    # Detect stack
    try:
        from .injection_intelligence import detect_stack

        profile = detect_stack(str(proj))
        parts: list[str] = []
        if profile.languages:
            parts.append(", ".join(profile.languages))
        if profile.frameworks:
            parts.append(", ".join(profile.frameworks))
        ctx.project_stack = " + ".join(parts) if parts else "desconocido"
    except Exception as e:
        logger.debug("No se pudo detectar stack: %s", e)

    # Get memory context and recent edits
    try:
        from .memory_router import get_memory_router

        router = get_memory_router(str(proj))
        bundle = await router.preload_context(task, limit=3)

        ctx.recent_errors = [e.get("error", str(e)) for e in bundle.recent_errors[:3]]
        ctx.relevant_decisions = [d.get("decision", str(d)) for d in bundle.recent_decisions[:3]]
        ctx.memory_hints = [r.content for r in bundle.relevant_memories[:3]]

        # Recent edits from observations (reuse same router)
        obs_results = await router.search(
            "archivos editados recientemente",
            sources=["observations"],
            limit=5,
        )
        ctx.recent_edits = [r.content for r in obs_results[:5]]
    except Exception as e:
        logger.debug("No se pudo cargar contexto de memoria: %s", e)

    return ctx


async def prepare_context(
    task: str,
    *,
    project_dir: str | None = None,
    current_file: str | None = None,
    open_files: list[str] | None = None,
    history: list[dict[str, Any]] | None = None,
    extras: dict[str, Any] | None = None,
    engine_name: str | None = None,
) -> InjectionContext:
    """Entry point recomendado que respeta el engine activo.

    Si no se especifica `engine_name`, resuelve via env/config (ver
    `context_engines.resolve_engine_name`). Si el engine fallara por cualquier
    razon, cae a `build_injection_context` preservando backward compat.

    Esta funcion es el punto de extensibilidad — callers nuevos deben usarla
    en vez de `build_injection_context` directo.
    """
    from .context_engines import ContextEngineInput, get_engine

    try:
        engine = get_engine(engine_name)
        inp = ContextEngineInput(
            task=task,
            project_dir=project_dir,
            current_file=current_file,
            open_files=list(open_files or []),
            history=list(history or []),
            extras=dict(extras or {}),
        )
        return await engine.prepare(inp)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prepare_context fallback a build_injection_context: %s", exc)
        return await build_injection_context(
            task,
            project_dir=project_dir,
            current_file=current_file,
            open_files=open_files,
        )


def enhance_agent_prompt(base_prompt: str, context: InjectionContext) -> str:
    """Inyecta contexto en el prompt base de un agente.

    Args:
        base_prompt: Prompt original del agente (IDENTITY.md + tarea).
        context: Contexto a inyectar.

    Returns:
        Prompt enriquecido con contexto del proyecto.
    """
    context_section = context.to_prompt_section()
    if not _has_meaningful_context(context_section):
        return base_prompt

    # Insert context before the task section
    marker = "### TAREA ASIGNADA"
    if marker in base_prompt:
        parts = base_prompt.split(marker, 1)
        return f"{parts[0]}{context_section}\n\n{marker}{parts[1]}"

    # Fallback: append at the end
    return f"{base_prompt}\n\n{context_section}"


def measure_prompt_footprint(context: InjectionContext) -> dict[str, int]:
    """Compara el tamaño del contexto legado vs el contexto compacto actual."""
    legacy_context = InjectionContext(
        task=context.task,
        current_file=context.current_file,
        recent_edits=context.recent_edits[:LEGACY_MAX_EDITS],
        project_stack=context.project_stack,
        recent_errors=context.recent_errors[:LEGACY_MAX_ERRORS],
        open_files=context.open_files[:LEGACY_MAX_FILES],
        project_dir=context.project_dir,
        relevant_decisions=context.relevant_decisions[:LEGACY_MAX_DECISIONS],
        memory_hints=context.memory_hints[:LEGACY_MAX_MEMORY_HINTS],
    )
    legacy_section = _serialize_prompt_section(legacy_context, max_section_chars=None)
    compact_section = context.to_prompt_section()

    legacy_chars = len(legacy_section)
    compact_chars = len(compact_section)
    legacy_tokens = estimate_tokens_approx(legacy_section)
    compact_tokens = estimate_tokens_approx(compact_section)

    return {
        "legacy_chars": legacy_chars,
        "compact_chars": compact_chars,
        "saved_chars": max(legacy_chars - compact_chars, 0),
        "legacy_tokens_approx": legacy_tokens,
        "compact_tokens_approx": compact_tokens,
        "saved_tokens_approx": max(legacy_tokens - compact_tokens, 0),
    }


def estimate_tokens_approx(text: str) -> int:
    """Estimación barata y estable de tokens para comparar presupuestos de contexto."""
    normalized = " ".join(text.split())
    if not normalized:
        return 0
    return max(1, (len(normalized) + 3) // 4)


def _serialize_prompt_section(
    context: InjectionContext,
    *,
    max_section_chars: int | None,
) -> str:
    """Serializa una sección de contexto con límites configurables."""
    sections: list[str] = ["## Contexto del Proyecto"]

    sections.extend(_serialize_inline_fields(context))
    _append_bullet_list(sections, "**Errores recientes:**", context.recent_errors)
    _append_bullet_list(sections, "**Decisiones relevantes:**", context.relevant_decisions)
    _append_bullet_list(sections, "**Conocimiento previo:**", context.memory_hints)

    prompt = "\n".join(sections)
    if max_section_chars is None:
        return prompt.rstrip()
    return prompt[:max_section_chars].rstrip()


def _serialize_inline_fields(context: InjectionContext) -> list[str]:
    """Serializa los campos escalares y de lista corta del contexto.

    Args:
        context: Contexto de inyección con los campos del proyecto.

    Returns:
        Lista de líneas en formato markdown (una por campo presente).
    """
    lines: list[str] = []
    if context.project_stack:
        lines.append(f"**Stack:** {context.project_stack}")
    if context.project_dir:
        lines.append(f"**Directorio:** {context.project_dir}")
    if context.current_file:
        lines.append(f"**Archivo actual:** {context.current_file}")
    if context.open_files:
        lines.append(f"**Archivos abiertos:** {', '.join(context.open_files)}")
    if context.recent_edits:
        lines.append(f"**Ediciones recientes:** {', '.join(context.recent_edits)}")
    return lines


def _append_bullet_list(sections: list[str], header: str, items: list[str]) -> None:
    """Agrega un header y sus items como bullets si la lista no está vacía.

    Args:
        sections: Acumulador de líneas a mutar in-place.
        header: Título en markdown de la sección.
        items: Items a renderizar como bullets; si está vacía no agrega nada.
    """
    if not items:
        return
    sections.append(header)
    sections.extend(f"- {item}" for item in items)


def _compact_items(items: list[str], max_items: int) -> list[str]:
    """Deduplica, limpia y trunca items contextuales."""
    compacted: list[str] = []
    seen: set[str] = set()

    for raw in items:
        normalized = " ".join(str(raw).split()).strip()
        if not normalized:
            continue
        normalized = normalized[:MAX_ITEM_CHARS]
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        compacted.append(normalized)
        if len(compacted) >= max_items:
            break

    return compacted


def _has_meaningful_context(section: str) -> bool:
    """Evita inyectar headers vacios o casi vacios."""
    meaningful_lines = [
        line
        for line in section.splitlines()
        if line.strip() and line.strip() != "## Contexto del Proyecto"
    ]
    return bool(meaningful_lines)
