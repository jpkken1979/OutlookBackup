"""debugger agent — diagnóstico y resolución de bugs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import detect_languages, llm_summarize, main_wrapper

AGENT_NAME = "debugger"

# Common error patterns per language
ERROR_PATTERNS: dict[str, list[str]] = {
    "python": [
        r"Traceback \(most recent call last\)",
        r"(\w+Error): (.+)",
        r"  File \"(.+)\", line (\d+)",
        r"ImportError|ModuleNotFoundError",
        r"TypeError|ValueError|AttributeError",
        r"KeyError|IndexError",
    ],
    "typescript": [
        r"TypeError: (.+)",
        r"SyntaxError: (.+)",
        r"ReferenceError: (.+)",
        r"Cannot read property '(\w+)' of undefined",
        r"Module not found: (.+)",
    ],
    "rust": [
        r"error\[E\d+\]: (.+)",
        r"thread '(.+)' panicked at (.+)",
        r"panicked at (.+)",
        r"expected (.+), found (.+)",
    ],
}


def _detect_errors(text: str) -> list[dict]:
    """Detect error patterns in text."""
    findings: list[dict] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for lang, patterns in ERROR_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, line, re.IGNORECASE):
                    findings.append(
                        {
                            "line": i + 1,
                            "content": line.strip(),
                            "language": lang,
                            "pattern": pat,
                        }
                    )
                    break
    return findings


def execute(task: str, root: Path) -> dict:
    """Main execution logic."""
    languages = detect_languages(root)
    detected_errors = _detect_errors(task)

    summary = llm_summarize(
        f"Tarea de debugging: {task}\n"
        f"Lenguajes en proyecto: {', '.join(languages)}\n"
        f"Errores detectados en la descripción: {detected_errors}",
        "Eres un agente de debugging experto. Analiza el problema reportado, "
        "identifica la causa raíz y proporciona:\n"
        "1. Diagnóstico del error\n"
        "2. Root cause identificado\n"
        "3. Fix propuesto con código\n"
        "4. Test de regresión sugerido\n"
        "5. Cómo prevenir bugs similares\n\n"
        "Responde en español con código cuando sea necesario.",
    )

    raw = {
        "task": task,
        "languages": languages,
        "detected_errors": detected_errors,
    }

    return {
        "status": "success",
        "summary": summary or f"Tarea de debugging: {task}",
        "raw": raw,
        "llm_used": "auto" if summary else "none",
    }


if __name__ == "__main__":
    main_wrapper(AGENT_NAME, execute)