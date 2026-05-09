"""documentation-writer agent — genera documentación técnica completa."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "documentation-writer"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)

    summary = llm_summarize(
        f"Tarea de documentación: {task}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}",
        "Analiza la tarea de documentación. Genera contenido estructurado "
        "en español para README, guías o documentación técnica. "
        "Incluye ejemplos de código cuando sea relevante.",
    )

    raw = {"task": task, "languages": languages}

    return {
        "status": "success",
        "summary": summary or f"Tarea de documentación: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)