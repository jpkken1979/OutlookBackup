"""devops-engineer agent — automatización de despliegues y pipelines CI/CD."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "devops-engineer"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)

    summary = llm_summarize(
        f"Tarea DevOps: {task}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}",
        "Analiza la tarea DevOps. Proporciona configuración de CI/CD, "
        "Dockerfiles, pipelines, scripts de despliegue y consideraciones de infraestructura. "
        "Responde en español.",
    )

    raw = {"task": task, "languages": languages}

    return {
        "status": "success",
        "summary": summary or f"Tarea DevOps: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)