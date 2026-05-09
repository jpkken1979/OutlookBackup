"""
Agent Benchmark Skill — Evalúa rendimiento de agentes del ecosistema.

Uso:
    python main.py --task "architect"
    python main.py --task "all"
    python main.py --task "debugger" --benchmark-suite code
    python main.py --task "all" --json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

AGENTS_DIR = Path(__file__).parents[4] / "agents"

BENCHMARK_SUITES: dict[str, list[str]] = {
    "standard": [
        "analisis_de_codigo",
        "planificacion_feature",
        "explicacion_arquitectura",
        "debugging_traceback",
        "generacion_documentacion",
    ],
    "code": [
        "generacion_codigo",
        "refactorizacion",
        "code_review",
        "generacion_tests",
        "optimizacion_performance",
    ],
    "analysis": [
        "analisis_logs",
        "deteccion_patrones",
        "sintesis_documentos",
        "evaluacion_riesgos",
        "comparacion_alternativas",
    ],
}

# Keywords que indican cobertura de una tarea en IDENTITY.md
TASK_COVERAGE_KEYWORDS: dict[str, list[str]] = {
    "analisis_de_codigo": ["code", "review", "análisis", "codigo", "python", "refactor"],
    "planificacion_feature": ["plan", "feature", "diseño", "arquitectura", "roadmap"],
    "explicacion_arquitectura": ["arquitectura", "explicar", "documentar", "design"],
    "debugging_traceback": ["debug", "error", "traceback", "fix", "diagnos"],
    "generacion_documentacion": ["doc", "documentar", "readme", "changelog"],
    "generacion_codigo": ["generar", "implement", "crear", "code", "script"],
    "refactorizacion": ["refactor", "optimizar", "mejorar", "clean"],
    "code_review": ["review", "calidad", "best practices", "code"],
    "generacion_tests": ["test", "pytest", "unit", "coverage"],
    "optimizacion_performance": ["performance", "optimizar", "speed", "profil"],
    "analisis_logs": ["log", "analiz", "monitor", "observ"],
    "deteccion_patrones": ["pattern", "patrón", "detectar", "analiz"],
    "sintesis_documentos": ["resumen", "sintetizar", "documento", "extract"],
    "evaluacion_riesgos": ["riesgo", "risk", "seguridad", "audit"],
    "comparacion_alternativas": ["compar", "evaluar", "alternativa", "decision"],
}


@dataclass
class AgentScore:
    """Score de evaluación de un agente."""

    agent_name: str
    identity_score: float = 0.0
    coverage_score: float = 0.0
    tool_readiness: float = 0.0
    memory_ready: float = 0.0
    identity_exists: bool = False
    scripts_exist: bool = False
    memory_exists: bool = False
    covered_tasks: list[str] = field(default_factory=list)
    missing_tasks: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        return (
            self.identity_score * 0.30
            + self.coverage_score * 0.25
            + self.tool_readiness * 0.25
            + self.memory_ready * 0.20
        )


def evaluate_agent(agent_name: str, agent_dir: Path, suite_tasks: list[str]) -> AgentScore:
    """Evalúa un agente dado su directorio."""
    score = AgentScore(agent_name=agent_name)

    # 1. Verificar IDENTITY.md
    identity_path = agent_dir / "IDENTITY.md"
    if identity_path.exists():
        score.identity_exists = True
        identity_text = identity_path.read_text(encoding="utf-8", errors="ignore").lower()

        # Evaluar completitud del IDENTITY.md
        required_sections = [
            "tier",
            "capacidad",
            "especialidad",
            "objetivo",
            "skills",
            "herramienta",
        ]
        found_sections = sum(1 for s in required_sections if s in identity_text)
        score.identity_score = min(100.0, (found_sections / len(required_sections)) * 100)

        # 2. Evaluar coverage de tareas del benchmark
        covered = []
        missing = []
        for task in suite_tasks:
            keywords = TASK_COVERAGE_KEYWORDS.get(task, [])
            if any(kw in identity_text for kw in keywords):
                covered.append(task)
            else:
                missing.append(task)

        score.covered_tasks = covered
        score.missing_tasks = missing
        score.coverage_score = (len(covered) / len(suite_tasks)) * 100 if suite_tasks else 0.0
    else:
        score.issues.append("IDENTITY.md no encontrado")
        score.identity_score = 0.0

    # 3. Verificar scripts
    scripts_dir = agent_dir / "scripts"
    if scripts_dir.exists() and any(scripts_dir.iterdir()):
        score.scripts_exist = True
        score.tool_readiness = 90.0
    else:
        score.tool_readiness = 20.0
        score.issues.append("Sin scripts — agente puede ser solo contextual")

    # 4. Verificar memoria compartida
    memory_path = agent_dir / "memory" / "shared_memory.json"
    if memory_path.exists():
        score.memory_exists = True
        try:
            content = json.loads(memory_path.read_text(encoding="utf-8"))
            if content:
                score.memory_ready = 100.0
            else:
                score.memory_ready = 50.0
                score.issues.append("shared_memory.json existe pero está vacío")
        except (json.JSONDecodeError, OSError):
            score.memory_ready = 30.0
            score.issues.append("shared_memory.json inválido o ilegible")
    else:
        score.memory_ready = 10.0
        score.issues.append("Sin memoria compartida configurada")

    return score


def run_benchmark(
    agent_filter: str,
    suite_name: str = "standard",
) -> list[AgentScore]:
    """Ejecuta benchmark para uno o todos los agentes."""
    suite_tasks = BENCHMARK_SUITES.get(suite_name, BENCHMARK_SUITES["standard"])
    scores: list[AgentScore] = []

    if not AGENTS_DIR.exists():
        return scores

    # Determinar qué agentes evaluar
    if agent_filter == "all":
        agent_dirs = [d for d in AGENTS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")]
    else:
        agent_dir = AGENTS_DIR / agent_filter
        if not agent_dir.exists():
            # Intentar búsqueda fuzzy
            matches = [d for d in AGENTS_DIR.iterdir() if agent_filter in d.name.lower()]
            agent_dirs = matches if matches else []
        else:
            agent_dirs = [agent_dir]

    for agent_dir in agent_dirs:
        score = evaluate_agent(agent_dir.name, agent_dir, suite_tasks)
        scores.append(score)

    scores.sort(key=lambda s: s.total_score, reverse=True)
    return scores


def format_report(scores: list[AgentScore], suite_name: str, agent_filter: str) -> str:
    """Formatea el reporte de benchmark."""
    if not scores:
        return f"No se encontraron agentes para evaluar (filtro: '{agent_filter}').\nVerificar que existe .agent/agents/<nombre>/"

    lines: list[str] = [
        "=== AGENT BENCHMARK REPORT ===",
        f"Suite: {suite_name} | Agentes evaluados: {len(scores)}",
        "",
        "RANKING (score total):",
    ]

    for i, s in enumerate(scores, 1):
        identity_status = (
            "OK" if s.identity_score >= 60 else "WARN" if s.identity_score > 0 else "FAIL"
        )
        scripts_status = "OK" if s.scripts_exist else "WARN"
        memory_status = "OK" if s.memory_ready >= 80 else "WARN" if s.memory_ready > 20 else "FAIL"

        lines.append(
            f"  {i:>2}. {s.agent_name:<25} {s.total_score:>6.1f}/100  "
            f"[identity:{identity_status} scripts:{scripts_status} memory:{memory_status}]"
        )

    # Mostrar details para agentes individuales
    if agent_filter != "all" and len(scores) == 1:
        s = scores[0]
        lines.extend(
            [
                "",
                f"DETALLE: {s.agent_name}",
                f"  identity_score:  {s.identity_score:.1f}/100",
                f"  coverage_score:  {s.coverage_score:.1f}/100  ({len(s.covered_tasks)}/{len(s.covered_tasks) + len(s.missing_tasks)} tareas)",
                f"  tool_readiness:  {s.tool_readiness:.1f}/100",
                f"  memory_ready:    {s.memory_ready:.1f}/100",
            ]
        )
        if s.covered_tasks:
            lines.append(f"  Tareas cubiertas: {', '.join(s.covered_tasks)}")
        if s.missing_tasks:
            lines.append(f"  Tareas no cubiertas: {', '.join(s.missing_tasks)}")
        if s.issues:
            lines.append("  Issues:")
            lines.extend(f"    - {issue}" for issue in s.issues)

    # Recomendación general
    if scores:
        top = scores[0]
        lines.extend(
            [
                "",
                f"RECOMENDACION: Para suite '{suite_name}', el agente con mejor score es '{top.agent_name}' ({top.total_score:.1f}/100)",
            ]
        )

    return "\n".join(lines)


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(description="Evalua rendimiento de agentes del ecosistema.")
    parser.add_argument("--task", required=True, help="Nombre del agente o 'all' para todos")
    parser.add_argument(
        "--benchmark-suite",
        choices=list(BENCHMARK_SUITES.keys()),
        default="standard",
        help="Suite de benchmark (default: standard)",
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    args = parser.parse_args()

    scores = run_benchmark(args.task, args.benchmark_suite)

    if args.json:
        output = {
            "suite": args.benchmark_suite,
            "agent_filter": args.task,
            "agents_evaluated": len(scores),
            "results": [
                {
                    "agent_name": s.agent_name,
                    "total_score": round(s.total_score, 2),
                    "identity_score": round(s.identity_score, 2),
                    "coverage_score": round(s.coverage_score, 2),
                    "tool_readiness": round(s.tool_readiness, 2),
                    "memory_ready": round(s.memory_ready, 2),
                    "covered_tasks": s.covered_tasks,
                    "missing_tasks": s.missing_tasks,
                    "issues": s.issues,
                }
                for s in scores
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(scores, args.benchmark_suite, args.task))


if __name__ == "__main__":
    main()
