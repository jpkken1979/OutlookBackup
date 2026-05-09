"""frontend-specialist agent — interfaces modernas con React, TypeScript y Tailwind."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "frontend-specialist"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    frontend_tech: list[str] = []
    if "typescript" in languages:
        frontend_tech.append("TypeScript")
    if "javascript" in languages:
        frontend_tech.append("JavaScript")

    summary = llm_summarize(
        f"Tarea de frontend: {task}\n"
        f"Tecnologías detectadas: {', '.join(frontend_tech)}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}",
        "Analiza la tarea de frontend. Proporciona código React/TypeScript "
        "con componentes funcionales, hooks, Tailwind y Framer Motion. "
        "Incluye variants de animación en archivos separados. "
        "Responde en español.",
    )

    raw = {"task": task, "languages": languages, "frontend_tech": frontend_tech}

    return {
        "status": "success",
        "summary": summary or f"Tarea de frontend: {task}\nTecnologías: {', '.join(frontend_tech)}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)