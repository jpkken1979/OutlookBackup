"""performance-optimizer agent — análisis y optimización de performance."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "performance-optimizer"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)

    summary = llm_summarize(
        f"Tarea de optimización de performance: {task}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}",
        "Analiza la tarea de performance. Identifica bottlenecks, propone "
        "optimizaciones concretas (caching, queries, rendering) y estima impacto. "
        "Responde en español.",
    )

    raw = {"task": task, "languages": languages}

    return {
        "status": "success",
        "summary": summary or f"Tarea de optimización: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)