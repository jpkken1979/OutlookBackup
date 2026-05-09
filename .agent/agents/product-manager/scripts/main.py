"""product-manager agent — roadmap, priorización y requisitos de producto."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import llm_summarize, main_wrapper

AGENT_NAME = "product-manager"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    summary = llm_summarize(
        f"Tarea de product management: {task}",
        "Analiza la tarea de gestión de producto. Proporciona análisis de "
        "priorización, roadmap, historias de usuario o recomendaciones de negocio. "
        "Responde en español.",
    )

    raw = {"task": task}

    return {
        "status": "success",
        "summary": summary or f"Tarea de product management: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)