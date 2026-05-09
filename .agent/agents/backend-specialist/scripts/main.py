"""backend-specialist agent — APIs, lógica de negocio e integración de servicios."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "backend-specialist"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    backend_tech: list[str] = []
    if "python" in languages:
        backend_tech.append("Python (FastAPI/aiohttp)")
    if "typescript" in languages or "javascript" in languages:
        backend_tech.append("TypeScript/Node.js")

    summary = llm_summarize(
        f"Tarea de backend: {task}\n"
        f"Tecnologías detectadas: {', '.join(backend_tech)}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}",
        "Analiza la tarea de backend. Proporciona un plan de implementación "
        "con pasos concretos, archivos a crear/modificar y consideraciones de seguridad. "
        "Responde en español.",
    )

    raw = {
        "task": task,
        "languages": languages,
        "backend_tech": backend_tech,
    }

    return {
        "status": "success",
        "summary": summary or f"Tarea de backend: {task}\nTecnologías: {', '.join(backend_tech)}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)