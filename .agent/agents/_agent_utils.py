"""
Utilidades compartidas para agentes ejecutables del ecosistema Antigravity.

Provee:
- Detección de LLM disponible (Ollama → Cloud → ninguno)
- Función llm_summarize() con fallback
- Output JSON estandarizado
- Detección de lenguaje del proyecto
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def detect_project_root() -> Path:
    """Detecta la raíz del proyecto (busca .git o .agent/)."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists() or (parent / ".agent").exists():
            return parent
    return cwd


def detect_languages(root: Path) -> list[str]:
    """Detecta lenguajes presentes en el proyecto."""
    langs = []
    patterns = {
        "python": ["*.py"],
        "typescript": ["*.ts", "*.tsx"],
        "rust": ["*.rs"],
        "javascript": ["*.js", "*.jsx"],
    }
    for lang, globs in patterns.items():
        for g in globs:
            if list(root.rglob(g))[:1]:
                langs.append(lang)
                break
    return langs or ["unknown"]


def detect_llm() -> dict[str, Any]:
    """Detecta qué LLM está disponible.

    Returns:
        {"provider": "ollama"|"anthropic"|"openai"|"none",
         "model": str, "base_url": str|None}
    """
    # 1. Check env vars from Nexus (apply_ai_runtime_env)
    provider = os.environ.get("ANTIGRAVITY_LLM_PROVIDER", "")
    model = os.environ.get("ANTIGRAVITY_LLM_MODEL", "")
    enabled = os.environ.get("ANTIGRAVITY_LLM_ENABLED", "true").lower() == "true"

    if not enabled:
        return {"provider": "none", "model": "", "base_url": None}

    # 2. Ollama (local)
    if provider == "ollama" or os.environ.get("OPENAI_BASE_URL", "").startswith(
        "http://localhost:11434"
    ):
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        model = model or "gpt-oss:20b"
        # Verify ollama is running
        try:
            import urllib.request

            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return {"provider": "ollama", "model": model, "base_url": base_url}
        except Exception:
            pass

    # 3. Cloud APIs
    for env_key, prov in [
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OPENAI_API_KEY", "openai"),
        ("OPENROUTER_API_KEY", "openrouter"),
    ]:
        if os.environ.get(env_key):
            return {"provider": prov, "model": model or "auto", "base_url": None}

    return {"provider": "none", "model": "", "base_url": None}


def llm_summarize(raw_data: str, prompt: str, max_tokens: int = 1000) -> str | None:
    """Envía datos a un LLM para resumen/interpretación.

    Args:
        raw_data: Datos crudos de herramientas.
        prompt: Instrucción para el LLM.
        max_tokens: Máximo de tokens en la respuesta.

    Returns:
        Resumen del LLM o None si no hay LLM disponible.
    """
    llm = detect_llm()
    if llm["provider"] == "none":
        return None

    full_prompt = f"{prompt}\n\nDatos:\n{raw_data[:8000]}"

    try:
        if llm["provider"] == "ollama":
            return _call_ollama(llm["model"], full_prompt, max_tokens)
        else:
            return _call_openai_compatible(llm, full_prompt, max_tokens)
    except Exception as e:
        return f"[LLM error: {e}]"


def _call_ollama(model: str, prompt: str, max_tokens: int) -> str:
    """Llama a Ollama via API."""
    import urllib.request

    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
    ).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        return data.get("response", "").strip()


def _call_openai_compatible(llm: dict, prompt: str, max_tokens: int) -> str:
    """Llama a API compatible con OpenAI (Claude, OpenRouter, etc.)."""
    import urllib.request

    base_url = llm.get("base_url") or "https://api.openai.com/v1"
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or ""
    )

    payload = json.dumps(
        {
            "model": llm["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
    ).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()


def run_command(cmd: list[str], cwd: str | Path | None = None, timeout: int = 60) -> dict[str, Any]:
    """Ejecuta un comando y captura output.

    Returns:
        {"ok": bool, "stdout": str, "stderr": str, "code": int}
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            shell=False,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[:50000],
            "stderr": result.stderr[:10000],
            "code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "code": -1}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"command not found: {cmd[0]}", "code": -2}


def agent_output(
    agent_name: str,
    status: str,
    summary: str,
    raw: Any,
    llm_used: str = "none",
    duration_ms: int = 0,
) -> str:
    """Genera output JSON estandarizado para un agente.

    Args:
        agent_name: Nombre del agente.
        status: "success" | "warning" | "error".
        summary: Resumen legible (generado por LLM o formato básico).
        raw: Datos crudos de las herramientas.
        llm_used: Identificador del LLM usado o "none".
        duration_ms: Duración de ejecución en ms.

    Returns:
        JSON string para stdout.
    """
    return json.dumps(
        {
            "agent": agent_name,
            "status": status,
            "summary": summary,
            "raw": raw,
            "llm_used": llm_used,
            "duration_ms": duration_ms,
        },
        ensure_ascii=False,
        indent=2,
    )


def main_wrapper(agent_name: str, execute_fn):
    """Wrapper estándar para el main de cada agente.

    Args:
        agent_name: Nombre del agente.
        execute_fn: Función(task: str, root: Path) -> dict con keys:
            status, summary, raw, llm_used
    """
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not task:
        print(json.dumps({"error": "Uso: python main.py <tarea>", "agent": agent_name}))
        sys.exit(1)

    root = detect_project_root()
    start = time.time()

    try:
        result = execute_fn(task, root)
        duration_ms = int((time.time() - start) * 1000)
        print(
            agent_output(
                agent_name=agent_name,
                status=result.get("status", "success"),
                summary=result.get("summary", ""),
                raw=result.get("raw", {}),
                llm_used=result.get("llm_used", "none"),
                duration_ms=duration_ms,
            )
        )
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        print(
            agent_output(
                agent_name=agent_name,
                status="error",
                summary=f"Error: {e}",
                raw={"exception": str(e)},
                duration_ms=duration_ms,
            )
        )
        sys.exit(1)
