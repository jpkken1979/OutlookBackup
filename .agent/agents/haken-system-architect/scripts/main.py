"""haken-system-architect — arquitectura de sistemas de dispatch japonés (派遣)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import llm_summarize, main_wrapper

AGENT_NAME = "haken-system-architect"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    summary = llm_summarize(
        f"Tarea de arquitectura de sistemas de dispatch: {task}\n"
        "Contexto: empresa japonesa, normativas laborales, sistemas HR, payroll, compliance",
        "Eres un arquitecto de sistemas de dispatch japonés. "
        "Diseña sistemas de gestión de dispatch (派遣管理システム) integrando HR, payroll, "
        "asistencia (勤怠) y compliance laboral japonés (労働基準法, 派遣法). "
        "Incluye diseño de APIs para ARARI, Kobetsu, Rirekisho y Kintai. "
        "Proporciona diagramas de arquitectura, modelos de datos y consideraciones de seguridad. "
        "Responde en español con terminología técnica.",
    )

    raw = {"task": task, "domain": "haken-system-architecture"}

    return {
        "status": "success",
        "summary": summary or f"Tarea de arquitectura de dispatch: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)