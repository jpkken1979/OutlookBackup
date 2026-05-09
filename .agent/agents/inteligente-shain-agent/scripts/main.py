"""inteligente-shain-agent — agente inteligente de recursos humanos para empresas japonesas."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import llm_summarize, main_wrapper

AGENT_NAME = "inteligente-shain-agent"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    summary = llm_summarize(
        f"Tarea de recursos humanos japonés: {task}\n"
        "Contexto: empresa japonesa, gestión de empleados (社員), nóminas, compliance",
        "Eres un agente inteligente de recursos humanos para empresas japonesas. "
        "Ayuda con lifecycle de empleados (入社, 異動, 退職), nóminas (賃金), "
        "deducciones legales, beneficios (福利厚生) y reportes regulatorios. "
        "Considera normativas laborales japonesas (労働基準法, 所得税法). "
        "Responde en español con terminología japonesa relevante.",
    )

    raw = {"task": task, "domain": "shain-hr"}

    return {
        "status": "success",
        "summary": summary or f"Tarea de recursos humanos: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)