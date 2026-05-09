"""feature-dev agent — orquestador del ciclo completo de feature."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent


def _invoke_agent(agent: str, task: str) -> dict:
    """Invoca otro agente via invoke-agent.py."""
    import subprocess
    import shlex

    cmd = f'python "{ROOT}/.agent/scripts/invoke-agent.py" {agent} "{task}"'
    result = subprocess.run(
        shlex.split(cmd),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300,
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout, "status": "ok"}
    return {"error": result.stderr, "status": "error"}


def _detect_scope(task: str) -> dict:
    """Analiza la tarea y detecta el scope y complejidad."""
    task_lower = task.lower()

    scope = {"complexity": "medium", "areas": [], "languages": []}

    # Detectar area por keywords
    area_map = {
        "chat": ["chat", "message", "conversation"],
        "nexus": ["nexus", "desktop", "tauri"],
        "telegram": ["telegram", "bot", "mensaje"],
        "brain": ["brain", "memory", "conocimiento"],
        "auth": ["auth", "login", "token", "session"],
        "config": ["config", "settings", "audit"],
        "api": ["api", "endpoint", "rest", "http"],
    }
    for area, keywords in area_map.items():
        if any(k in task_lower for k in keywords):
            scope["areas"].append(area)

    # Detectar lenguaje por keywords
    if any(k in task_lower for k in ["react", "tsx", "jsx", "component", "hook"]):
        scope["languages"].append("typescript")
    if any(k in task_lower for k in ["python", "api", "backend", "fastapi"]):
        scope["languages"].append("python")
    if any(k in task_lower for k in ["rust", "cargo", "tauri"]):
        scope["languages"].append("rust")

    # Detectar complejidad
    if any(k in task_lower for k in ["simple", "quick", "fix", "bug"]):
        scope["complexity"] = "low"
    elif any(k in task_lower for k in ["complex", "refactor", "architecture", "system"]):
        scope["complexity"] = "high"

    return scope


def _run_explorer(target: str) -> dict:
    """Ejecuta explorer para analizar codigo existente."""
    print(f"[feature-dev] Explorando: {target}")
    return _invoke_agent("explorer", f"Analiza el codigo relacionado con: {target}")


def _run_coder(spec: str) -> dict:
    """Ejecuta coder para implementar especificacion."""
    print("[feature-dev] Implementando via coder")
    return _invoke_agent("coder", spec)


def _run_test_runner(scope: str = ".") -> dict:
    """Ejecuta test-runner para verificar tests."""
    print(f"[feature-dev] Ejecutando tests en: {scope}")
    return _invoke_agent("test-runner", f"Ejecutar tests del proyecto en {scope}")


def _run_code_reviewer(files: list[str]) -> dict:
    """Ejecuta code-reviewer para revisar archivos."""
    files_str = ", ".join(files)
    print(f"[feature-dev] Revisando archivos: {files_str}")
    return _invoke_agent("code-reviewer", f"Revisar calidad de: {files_str}")


def execute(task: str, root: Path | None = None) -> dict:
    """Ejecuta el ciclo completo de feature development."""
    start = datetime.now()
    root = root or ROOT

    steps: list[dict] = []
    result = {
        "status": "completed",
        "feature": task,
        "files": [],
        "tests": [],
        "steps": steps,
        "blockers": [],
        "summary": "",
    }

    # === FASE 1: Analisis ===
    step = {"phase": "analisis", "status": "ok", "output": {}}
    scope = _detect_scope(task)
    step["output"] = scope
    steps.append(step)
    print(f"[feature-dev] Fase 1 - Analisis: complexity={scope['complexity']}, areas={scope['areas']}")

    # === FASE 2: Exploracion (solo si no es trivial) ===
    if scope["complexity"] != "low":
        step = {"phase": "exploracion", "status": "ok", "output": {}}
        try:
            explore_result = _run_explorer(task)
            step["output"] = explore_result
        except Exception as e:
            step["status"] = "warning"
            step["error"] = str(e)
            result["blockers"].append(f"Exploracion fallo: {e}")
        steps.append(step)
    else:
        print("[feature-dev] Skipping exploration (complejidad baja)")

    # === FASE 3: Planificacion ===
    step = {"phase": "planificacion", "status": "ok", "output": {}}
    plan = {
        "task": task,
        "scope": scope,
        "suggested_steps": [
            "1. Modificar/crear archivos necesarios",
            "2. Escribir tests para la nueva funcionalidad",
            "3. Ejecutar test-runner para verificar",
            "4. Code review si es feature compleja",
        ],
    }
    step["output"] = plan
    steps.append(step)
    print(f"[feature-dev] Fase 3 - Planificacion: {plan['suggested_steps']}")

    # === FASE 4: Implementacion ===
    step = {"phase": "implementacion", "status": "ok", "output": {}}
    try:
        # Para features simples, no usamos coder (implementamos directo)
        # Para features complejas, delegamos a coder
        if scope["complexity"] == "high":
            coder_result = _run_coder(f"Implementar: {task}")
            step["output"] = coder_result
            if coder_result.get("status") == "error":
                step["status"] = "error"
                result["status"] = "partial"
        else:
            step["output"] = {
                "message": "Implementacion delegados a usuario (complejidad media-alta requiere plan detallado)"
            }
    except Exception as e:
        step["status"] = "error"
        step["error"] = str(e)
        result["blockers"].append(f"Implementacion fallo: {e}")
        result["status"] = "partial"
    steps.append(step)

    # === FASE 5: Testing ===
    step = {"phase": "testing", "status": "ok", "output": {}}
    try:
        test_result = _run_test_runner(".")
        step["output"] = test_result
        if test_result.get("status") == "error":
            step["status"] = "error"
    except Exception as e:
        step["status"] = "warning"
        step["error"] = str(e)
    steps.append(step)

    # === FASE 6: Review (solo si hay archivos modificados y no es low complexity) ===
    if result["files"] and scope["complexity"] != "low":
        step = {"phase": "review", "status": "ok", "output": {}}
        try:
            review_result = _run_code_reviewer(result["files"])
            step["output"] = review_result
        except Exception as e:
            step["status"] = "warning"
            step["error"] = str(e)
        steps.append(step)

    # === FASE 7: Consolidacion ===
    elapsed = (datetime.now() - start).total_seconds()
    result["elapsed_seconds"] = elapsed

    # Resumen ejecutivo
    status_emoji = "✅" if result["status"] == "completed" else "⚠️"
    result["summary"] = (
        f"{status_emoji} Feature: {task}\n"
        f"Status: {result['status']}\n"
        f"Pasos completados: {len(steps)}\n"
        f"Tiempo: {elapsed:.1f}s\n"
        f"Archivos: {len(result['files'])}\n"
        f"Blockers: {len(result['blockers'])}\n"
    )
    if result["blockers"]:
        result["summary"] += "\nBlockers:\n" + "\n".join(f"  - {b}" for b in result["blockers"])

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="feature-dev agent")
    parser.add_argument("task", nargs="+", help="Descripcion de la feature")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--root", default=None, help="Directorio raiz del proyecto")
    args = parser.parse_args()

    task_text = " ".join(args.task)
    root = Path(args.root) if args.root else None

    output = execute(task_text, root)

    if args.json:
        print(json.dumps(output, indent=2, default=str))
    else:
        print(output["summary"])
        if output.get("steps"):
            print("\nPasos ejecutados:")
            for s in output["steps"]:
                print(f"  [{s['phase']}] {s['status']}")


def main() -> dict:
    """CLI entry point for feature-dev agent."""
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    return execute(task)


def main_wrapper():
    """main_wrapper-compatible entry point for feature-dev agent."""
    return main()
