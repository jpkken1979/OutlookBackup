"""uns-hr-specialist — especialista HR de UNS para el mercado japonés."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import llm_summarize, main_wrapper

AGENT_NAME = "uns-hr-specialist"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    summary = llm_summarize(
        f"Tarea HR de UNS: {task}\n"
        "Contexto: UNS (Unlimited Network System), dispatch japonés, payroll, compliance regulatorio",
        "Eres un especialista HR de UNS para el mercado japonés. "
        "Diseña e implementa sistemas de dispatch (派遣), contratos individuales (個別契約書), "
        "payroll (賃金) con deducciones legales (所得税, 社会保険, 雇用保険), "
        "y reportes de compliance. "
        "Integra con ARARI, Kobetsu y Kintai. "
        "Responde en español con terminología japonesa y técnica.",
    )

    raw = {"task": task, "domain": "uns-hr"}

    return {
        "status": "success",
        "summary": summary or f"Tarea HR de UNS: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)