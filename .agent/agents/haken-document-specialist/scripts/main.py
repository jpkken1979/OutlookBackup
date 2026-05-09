"""haken-document-specialist — especializado en documentos de dispatch japonés (派遣)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import llm_summarize, main_wrapper

AGENT_NAME = "haken-document-specialist"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    summary = llm_summarize(
        f"Tarea de documentos de dispatch: {task}\n"
        "Contexto: empresa japonesa, normativas laborales, contratos 個別契約書, 派遣先Control",
        "Eres un especialista en documentos laborales japoneses. "
        "Ayuda con contratos de dispatch (個別契約書), control de asistencia (勤怠), "
        "tiempo libre (有給), 履歴書 y certificados. "
        "Incluye términos japoneses relevantes y considera compliance laboral. "
        "Responde en español con términos japoneses cuando sea necesario.",
    )

    raw = {"task": task, "domain": "haken-dispatch"}

    return {
        "status": "success",
        "summary": summary or f"Tarea de documentos de dispatch: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)