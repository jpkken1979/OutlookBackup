"""security-auditor agent — auditoría de seguridad OWASP, CVE y hardening."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "security-auditor"


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)

    summary = llm_summarize(
        f"Tarea de auditoría de seguridad: {task}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}",
        "Analiza la tarea de seguridad. Realiza auditoría OWASP Top 10, "
        "detecta CVEs, revisa configuraciones y genera reporte de hardening. "
        "Prioriza hallazgos por severidad. Responde en español.",
    )

    raw = {"task": task, "languages": languages}

    return {
        "status": "success",
        "summary": summary or f"Tarea de auditoría de seguridad: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)