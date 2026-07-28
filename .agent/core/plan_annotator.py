# .agent/core/plan_annotator.py
"""Parsea planes markdown y anota cada tarea con su modelo recomendado."""

from __future__ import annotations

import re

from core.model_advisor import TaskInput, recommend

ANNOTATION_MARKER: str = "  →  🧠 "
_TASK_RE = re.compile(r"^(\s*-\s*\[[ xX]\]\s*)(.+?)\s*$")


def parse_tasks(markdown: str) -> list[tuple[int, str]]:
    """Devuelve (indice_de_linea, texto_de_tarea) de las lineas checkbox.

    El texto excluye una anotacion previa (todo lo que sigue a ANNOTATION_MARKER).
    """
    tasks: list[tuple[int, str]] = []
    for i, line in enumerate(markdown.splitlines()):
        m = _TASK_RE.match(line)
        if not m:
            continue
        body = m.group(2)
        if ANNOTATION_MARKER in body:
            body = body.split(ANNOTATION_MARKER, 1)[0].rstrip()
        tasks.append((i, body))
    return tasks


def annotate_markdown(markdown: str, forced: str | None = None) -> str:
    """Reescribe el markdown anotando cada tarea con `→ 🧠 <modelo> · <razon>`.

    Idempotente: una anotacion previa se reemplaza, no se duplica.

    Args:
        markdown: Contenido del plan en formato markdown.
        forced: Si se especifica, anota todas las tareas con este modelo y la
            razon ``"override manual"`` en vez de llamar al advisor.
    """
    lines = markdown.splitlines(keepends=True)
    for idx, text in parse_tasks(markdown):
        raw = lines[idx]
        newline = "\n" if raw.endswith("\n") else ""
        m = _TASK_RE.match(raw.rstrip("\n"))
        if not m:
            continue
        prefix = m.group(1)
        if forced:
            annotated = f"{prefix}{text}{ANNOTATION_MARKER}{forced} · override manual{newline}"
        else:
            rec = recommend(TaskInput(text=text))
            annotated = (
                f"{prefix}{text}{ANNOTATION_MARKER}{rec.recommended_model}"
                f" · {rec.reasoning}{newline}"
            )
        lines[idx] = annotated
    return "".join(lines)
