"""test-engineer agent — estrategia de testing y tests automatizados."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "test-engineer"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    test_frameworks: list[str] = []
    if "python" in languages:
        test_frameworks.append("pytest")
    if "typescript" in languages:
        test_frameworks.append("Vitest")
    if "rust" in languages:
        test_frameworks.append("cargo test")

    summary = llm_summarize(
        f"Tarea de testing: {task}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}\n"
        f"Frameworks de test detectados: {', '.join(test_frameworks)}",
        "Analiza la tarea de testing. Genera tests unitarios, de integración "
        "o e2e según corresponda. Usa pytest para Python, Vitest para TypeScript. "
        "Incluye mocks, fixtures y coverage mínimo 80%. "
        "Nombra tests descriptivamente: it('rechaza tokens expirados'). "
        "Responde en español.",
    )

    raw = {"task": task, "languages": languages, "test_frameworks": test_frameworks}

    return {
        "status": "success",
        "summary": summary or f"Tarea de testing: {task}\nFrameworks: {', '.join(test_frameworks)}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)