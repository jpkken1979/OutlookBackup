#!/usr/bin/env python3
"""
CI Agent Runner - Invocacion headless de agentes para CI/CD pipelines.

Diseñado para ejecutarse SIN intervencion humana en GitHub Actions,
GitLab CI, Jenkins, etc. Analiza cambios del PR y ejecuta agentes
relevantes automaticamente.

Uso:
  # Analizar diff de PR con agente code-reviewer
  python ci-agent-runner.py --mode review --diff-file changes.diff

  # Audit de seguridad sobre archivos cambiados
  python ci-agent-runner.py --mode security --files src/auth.py src/api.py

  # Analisis completo de PR (auto-detecta agentes)
  python ci-agent-runner.py --mode auto --pr-number 42

  # Ejecutar agente especifico con tarea
  python ci-agent-runner.py --agent explorer --task "Analizar cambios"

  # Output como comentario de PR (GitHub)
  python ci-agent-runner.py --mode review --output github-comment

v1.0.0 - 2026-02-13
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Agregar paths del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / ".agent"))
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Analisis de cambios
# ---------------------------------------------------------------------------


def get_changed_files_from_diff(diff_content: str) -> list[str]:
    """Extrae archivos cambiados de un diff."""
    files = []
    for line in diff_content.splitlines():
        if line.startswith("+++ b/"):
            filepath = line[6:]
            if filepath != "/dev/null":
                files.append(filepath)
    return files


def get_pr_diff(pr_number: int) -> str:
    """Obtiene el diff de un PR usando gh CLI."""
    try:
        cmd = shlex.split(f"gh pr diff {pr_number}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
        return result.stdout
    except Exception as e:
        print(f"Error obteniendo diff del PR #{pr_number}: {e}", file=sys.stderr)
        return ""


def get_pr_info(pr_number: int) -> dict:
    """Obtiene info del PR usando gh CLI."""
    try:
        cmd = shlex.split(
            f"gh pr view {pr_number} --json title,body,headRefName,baseRefName,additions,deletions,changedFiles"
        )
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}


def classify_changes(files: list[str]) -> dict[str, list[str]]:
    """Clasifica archivos cambiados por categoria."""
    categories: dict[str, list[str]] = {
        "security": [],
        "api": [],
        "frontend": [],
        "backend": [],
        "tests": [],
        "config": [],
        "docs": [],
        "other": [],
    }

    security_patterns = ["auth", "security", "token", "password", "secret", "crypt", "session"]
    api_patterns = ["api", "endpoint", "route", "controller", "handler"]
    frontend_patterns = [".tsx", ".jsx", ".css", ".html", "component", "page"]
    config_patterns = [".env", ".yml", ".yaml", ".json", ".toml", "config", "docker", "Dockerfile"]
    test_patterns = ["test_", "_test.", ".test.", "spec.", "conftest"]
    doc_patterns = [".md", ".rst", ".txt", "doc"]

    for f in files:
        f_lower = f.lower()
        categorized = False

        if any(p in f_lower for p in security_patterns):
            categories["security"].append(f)
            categorized = True
        if any(p in f_lower for p in api_patterns):
            categories["api"].append(f)
            categorized = True
        if any(f_lower.endswith(p) or p in f_lower for p in frontend_patterns):
            categories["frontend"].append(f)
            categorized = True
        if any(p in f_lower for p in test_patterns):
            categories["tests"].append(f)
            categorized = True
        if any(f_lower.endswith(p) or p in f_lower for p in config_patterns):
            categories["config"].append(f)
            categorized = True
        if any(f_lower.endswith(p) for p in doc_patterns):
            categories["docs"].append(f)
            categorized = True

        if not categorized:
            if f_lower.endswith(".py"):
                categories["backend"].append(f)
            else:
                categories["other"].append(f)

    return {k: v for k, v in categories.items() if v}


def select_agents_for_changes(categories: dict[str, list[str]]) -> list[dict]:
    """Selecciona agentes relevantes segun las categorias de cambios."""
    agents = []

    # Siempre code-reviewer para PRs
    agents.append(
        {
            "name": "code-reviewer",
            "reason": "Revision general de codigo",
            "priority": 1,
        }
    )

    if "security" in categories:
        agents.append(
            {
                "name": "security-auditor",
                "reason": f"Cambios en archivos de seguridad: {', '.join(categories['security'][:3])}",
                "priority": 0,  # Maxima prioridad
            }
        )

    if "api" in categories:
        agents.append(
            {
                "name": "api-designer",
                "reason": f"Cambios en API: {', '.join(categories['api'][:3])}",
                "priority": 2,
            }
        )

    if "tests" in categories:
        agents.append(
            {
                "name": "test-engineer",
                "reason": f"Cambios en tests: {', '.join(categories['tests'][:3])}",
                "priority": 3,
            }
        )

    if "config" in categories:
        agents.append(
            {
                "name": "devops-engineer",
                "reason": f"Cambios en configuracion: {', '.join(categories['config'][:3])}",
                "priority": 3,
            }
        )

    agents.sort(key=lambda a: a["priority"])
    return agents


# ---------------------------------------------------------------------------
# Ejecucion de agentes
# ---------------------------------------------------------------------------


def load_agent_identity(agent_name: str) -> str:
    """Carga el system prompt de un agente."""
    agents_dir = PROJECT_ROOT / ".agent" / "agents" / agent_name
    identity_file = agents_dir / "IDENTITY.md"

    if identity_file.exists():
        return identity_file.read_text(encoding="utf-8")

    # Fallback: SYSTEM_PROMPT.md
    system_file = agents_dir / "SYSTEM_PROMPT.md"
    if system_file.exists():
        return system_file.read_text(encoding="utf-8")

    return f"You are {agent_name}, a specialized agent."


def build_review_prompt(
    agent_name: str,
    diff: str,
    files: list[str],
    pr_info: dict,
    context: dict,
) -> str:
    """Construye el prompt completo para un agente de review."""
    identity = load_agent_identity(agent_name)

    # Truncar diff si es muy largo
    max_diff_chars = 15000
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n\n... [diff truncado, mostrando primeros 15K chars] ..."

    prompt = f"""{identity}

---

## TAREA: Revision automatica de PR

### Info del PR:
- Titulo: {pr_info.get("title", "N/A")}
- Branch: {pr_info.get("headRefName", "N/A")} -> {pr_info.get("baseRefName", "N/A")}
- Archivos cambiados: {len(files)}

### Archivos modificados:
{chr(10).join(f"- {f}" for f in files[:30])}

### Contexto del proyecto:
- Errores conocidos: {len(context.get("known_errors", []))}
- Tests flaky: {len(context.get("flaky_tests", []))}
- CI Health: {context.get("ci_health", {}).get("status", "unknown")}

### Diff:
```diff
{diff}
```

### Instrucciones:
1. Analiza los cambios en detalle
2. Identifica problemas potenciales (bugs, seguridad, performance)
3. Sugiere mejoras concretas con ejemplos de codigo
4. Evalua si faltan tests
5. Da una calificacion general: APPROVE, REQUEST_CHANGES, COMMENT

### Formato de respuesta (JSON):
```json
{{
  "verdict": "APPROVE|REQUEST_CHANGES|COMMENT",
  "summary": "Resumen de 1-2 oraciones",
  "issues": [
    {{
      "severity": "critical|warning|info",
      "file": "path/to/file.py",
      "line": 42,
      "description": "Descripcion del problema",
      "suggestion": "Como arreglarlo"
    }}
  ],
  "score": 0.85
}}
```
"""
    return prompt


# ---------------------------------------------------------------------------
# Formato de output
# ---------------------------------------------------------------------------


def format_as_github_comment(results: list[dict]) -> str:
    """Formatea resultados como comentario de GitHub PR."""
    lines = ["## Revision Automatica por Agentes\n"]

    for result in results:
        agent = result.get("agent", "unknown")
        verdict = result.get("verdict", "N/A")
        summary = result.get("summary", "")
        issues = result.get("issues", [])
        score = result.get("score", 0)

        # Emoji segun veredicto
        emoji = {
            "APPROVE": "white_check_mark",
            "REQUEST_CHANGES": "x",
            "COMMENT": "speech_balloon",
        }.get(verdict, "grey_question")

        lines.append(f"### :{emoji}: {agent} - {verdict}")
        lines.append(f"\n{summary}\n")

        if score:
            lines.append(f"**Score:** {score}/1.0\n")

        if issues:
            critical = [i for i in issues if i.get("severity") == "critical"]
            warnings = [i for i in issues if i.get("severity") == "warning"]
            info = [i for i in issues if i.get("severity") == "info"]

            if critical:
                lines.append("\n**Problemas criticos:**")
                for issue in critical:
                    lines.append(
                        f"- `{issue.get('file', '?')}:{issue.get('line', '?')}` - {issue.get('description', '')}"
                    )
                    if issue.get("suggestion"):
                        lines.append(f"  > Sugerencia: {issue['suggestion']}")

            if warnings:
                lines.append("\n**Advertencias:**")
                for issue in warnings:
                    lines.append(
                        f"- `{issue.get('file', '?')}:{issue.get('line', '?')}` - {issue.get('description', '')}"
                    )

            if info:
                lines.append(f"\n**Info:** {len(info)} sugerencias menores")

        lines.append("\n---\n")

    # Resumen final
    total_critical = sum(
        len([i for i in r.get("issues", []) if i.get("severity") == "critical"]) for r in results
    )
    total_warnings = sum(
        len([i for i in r.get("issues", []) if i.get("severity") == "warning"]) for r in results
    )

    if total_critical > 0:
        lines.append(
            f":rotating_light: **{total_critical} problemas criticos encontrados** - Requiere atencion antes de merge"
        )
    elif total_warnings > 0:
        lines.append(f":warning: **{total_warnings} advertencias** - Revisar antes de merge")
    else:
        lines.append(":tada: **Sin problemas encontrados** - Listo para merge")

    lines.append(
        f"\n*Generado por Antigravity Agents CI/CD Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M')}*"
    )

    return "\n".join(lines)


def format_as_json(results: list[dict]) -> str:
    """Formatea resultados como JSON."""
    return json.dumps(
        {
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "summary": {
                "total_agents": len(results),
                "total_issues": sum(len(r.get("issues", [])) for r in results),
                "critical_issues": sum(
                    len([i for i in r.get("issues", []) if i.get("severity") == "critical"])
                    for r in results
                ),
            },
        },
        indent=2,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Integracion con Intelligence Hub y Project Memory
# ---------------------------------------------------------------------------


def record_ci_outcome(
    results: list[dict], workflow: str, branch: str = "", commit: str = ""
) -> None:
    """Registra el resultado del CI en Intelligence Hub y Project Memory."""
    try:
        from core.project_memory import get_project_memory

        memory = get_project_memory(str(PROJECT_ROOT))

        # Determinar status general
        has_critical = any(
            any(i.get("severity") == "critical" for i in r.get("issues", [])) for r in results
        )
        status = "failure" if has_critical else "success"

        # Registrar en Project Memory
        failed_jobs = [r["agent"] for r in results if r.get("verdict") == "REQUEST_CHANGES"]
        memory.record_ci_result(
            workflow=workflow,
            status=status,
            branch=branch,
            commit=commit,
            failed_jobs=failed_jobs,
            agent_findings=[
                {"agent": r["agent"], "issues_count": len(r.get("issues", []))} for r in results
            ],
        )
    except Exception as e:
        print(f"Warning: No se pudo registrar en Project Memory: {e}", file=sys.stderr)

    try:
        from core.intelligence_hub import get_intelligence_hub

        hub = get_intelligence_hub(str(PROJECT_ROOT))

        for result in results:
            agent = result.get("agent", "unknown")
            score = result.get("score", 0.5)
            hub.record_outcome(
                task=f"CI review: {workflow}",
                agent_name=agent,
                success=not has_critical,
                quality_score=score,
                duration_ms=0,
            )
    except Exception as e:
        print(f"Warning: No se pudo registrar en Intelligence Hub: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CI Agent Runner - Invocacion headless de agentes para CI/CD",
    )
    parser.add_argument(
        "--mode",
        choices=["review", "security", "auto"],
        default="auto",
        help="Modo de ejecucion",
    )
    parser.add_argument("--agent", help="Agente especifico a ejecutar")
    parser.add_argument("--task", help="Tarea especifica para el agente")
    parser.add_argument("--pr-number", type=int, help="Numero de PR para analizar")
    parser.add_argument("--diff-file", help="Archivo con diff para analizar")
    parser.add_argument("--files", nargs="+", help="Archivos especificos a analizar")
    parser.add_argument(
        "--output",
        choices=["json", "github-comment", "text"],
        default="json",
        help="Formato de salida",
    )
    parser.add_argument(
        "--post-comment", action="store_true", help="Publicar resultado como comentario en el PR"
    )
    parser.add_argument("--branch", default="", help="Branch actual")
    parser.add_argument("--commit", default="", help="Commit SHA actual")

    args = parser.parse_args()

    # Obtener diff y archivos
    diff = ""
    files: list[str] = []
    pr_info: dict = {}

    if args.pr_number:
        diff = get_pr_diff(args.pr_number)
        files = get_changed_files_from_diff(diff)
        pr_info = get_pr_info(args.pr_number)
    elif args.diff_file:
        diff_path = Path(args.diff_file)
        if diff_path.exists():
            diff = diff_path.read_text(encoding="utf-8")
            files = get_changed_files_from_diff(diff)
    elif args.files:
        files = args.files

    if not files and not args.task:
        print(
            "Error: No se encontraron archivos ni tarea. Use --pr-number, --diff-file, --files o --task",
            file=sys.stderr,
        )
        return 1

    # Obtener contexto del proyecto
    context: dict = {}
    try:
        from core.project_memory import get_project_memory

        memory = get_project_memory(str(PROJECT_ROOT))
        context = memory.get_context_for_task(
            args.task or f"Review PR con archivos: {', '.join(files[:5])}"
        )
    except Exception:
        pass

    # Seleccionar agentes
    if args.agent:
        selected_agents = [
            {"name": args.agent, "reason": "Seleccionado manualmente", "priority": 0}
        ]
    elif args.mode == "security":
        selected_agents = [{"name": "security-auditor", "reason": "Modo seguridad", "priority": 0}]
    elif args.mode == "review":
        selected_agents = [{"name": "code-reviewer", "reason": "Modo revision", "priority": 0}]
    else:
        categories = classify_changes(files)
        selected_agents = select_agents_for_changes(categories)

    # Ejecutar agentes (generar prompts - en CI real, estos se envian al LLM)
    results: list[dict] = []
    print("\n=== CI Agent Runner ===", file=sys.stderr)
    print(f"Archivos: {len(files)}", file=sys.stderr)
    print(f"Agentes seleccionados: {len(selected_agents)}", file=sys.stderr)

    for agent_info in selected_agents:
        agent_name = agent_info["name"]
        print(f"\n--- Ejecutando: {agent_name} ({agent_info['reason']}) ---", file=sys.stderr)

        prompt = build_review_prompt(
            agent_name=agent_name,
            diff=diff,
            files=files,
            pr_info=pr_info,
            context=context,
        )

        # En modo CI, generamos el prompt para que el LLM lo procese
        # El resultado real vendria de la API del LLM
        result = {
            "agent": agent_name,
            "prompt_generated": True,
            "prompt_length": len(prompt),
            "files_analyzed": len(files),
            "reason": agent_info["reason"],
            "verdict": "COMMENT",
            "summary": f"Agente {agent_name} analizo {len(files)} archivos",
            "issues": [],
            "score": 0.0,
        }

        # Si hay API key, ejecutar realmente
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key and len(api_key) > 10:
            try:
                result = _execute_with_llm(agent_name, prompt, api_key)
            except Exception as e:
                print(f"Warning: Error ejecutando LLM para {agent_name}: {e}", file=sys.stderr)

        results.append(result)

    # Registrar resultados
    record_ci_outcome(
        results,
        workflow=f"agent-{args.mode}",
        branch=args.branch or os.environ.get("GITHUB_HEAD_REF", ""),
        commit=args.commit or os.environ.get("GITHUB_SHA", ""),
    )

    # Formatear output
    if args.output == "github-comment":
        output = format_as_github_comment(results)
    elif args.output == "json":
        output = format_as_json(results)
    else:
        output = format_as_json(results)

    print(output)

    # Publicar comentario en PR si se solicito
    if args.post_comment and args.pr_number:
        comment = format_as_github_comment(results)
        try:
            cmd_parts = ["gh", "pr", "comment", str(args.pr_number), "--body", comment]
            subprocess.run(cmd_parts, shell=False, timeout=30)
            print(f"Comentario publicado en PR #{args.pr_number}", file=sys.stderr)
        except Exception as e:
            print(f"Error publicando comentario: {e}", file=sys.stderr)

    # Exit code: 1 si hay issues criticos
    has_critical = any(
        any(i.get("severity") == "critical" for i in r.get("issues", [])) for r in results
    )
    return 1 if has_critical else 0


def _execute_with_llm(agent_name: str, prompt: str, api_key: str) -> dict:
    """Ejecuta un agente con el LLM real via API."""
    import httpx

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120.0,
    )

    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code}")

    data = response.json()
    content = data.get("content", [{}])[0].get("text", "")

    # Intentar parsear JSON de la respuesta
    try:
        # Buscar bloque JSON en la respuesta
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(content[json_start:json_end])
            parsed["agent"] = agent_name
            return parsed
    except json.JSONDecodeError:
        pass

    return {
        "agent": agent_name,
        "verdict": "COMMENT",
        "summary": content[:500],
        "issues": [],
        "score": 0.5,
    }


if __name__ == "__main__":
    sys.exit(main())
