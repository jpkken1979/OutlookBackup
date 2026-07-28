#!/usr/bin/env python3
"""
Eval Pipeline — Sistema de evaluación de calidad de agentes y skills.

Sin evals no hay mejora sistemática. Este script:
1. Define benchmarks por tipo de agente
2. Evalúa la calidad de las respuestas con heurísticas
3. Guarda historial de scores en SQLite
4. Genera reportes con tendencias
5. Detecta regresiones automáticamente

Uso:
    python .agent/scripts/eval_pipeline.py                  # Eval todos los agentes
    python .agent/scripts/eval_pipeline.py --agent explorer  # Solo un agente
    python .agent/scripts/eval_pipeline.py --report          # Solo ver reporte
    python .agent/scripts/eval_pipeline.py --list            # Listar benchmarks
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"
EVALS_DB = PROJECT_ROOT / ".antigravity" / "evals.db"
EVALS_DIR = PROJECT_ROOT / ".antigravity" / "evals"


# =============================================================================
# Benchmarks por tipo de agente
# =============================================================================

AGENT_BENCHMARKS: dict[str, list[dict[str, Any]]] = {
    "explorer": [
        {
            "id": "explorer_001",
            "task": "Busca todos los archivos Python con más de 100 líneas en el proyecto",
            "expected_patterns": [r"\.py", r"\d+ (archivo|file)"],
            "min_length": 50,
            "timeout": 30,
        },
        {
            "id": "explorer_002",
            "task": "Encuentra todos los imports de pydantic en el proyecto",
            "expected_patterns": [r"pydantic", r"import"],
            "min_length": 30,
            "timeout": 30,
        },
    ],
    "security-auditor": [
        {
            "id": "security_001",
            "task": "Revisa el archivo mcp-server/server.py en busca de vulnerabilidades de seguridad",
            "expected_patterns": [
                r"(seguridad|security|vulnerabilidad|OWASP|risk)",
                r"(recomendaci|suggest|fix)",
            ],
            "min_length": 100,
            "timeout": 60,
        },
    ],
    "architect": [
        {
            "id": "architect_001",
            "task": "Diseña la arquitectura de un sistema de autenticación JWT para este ecosistema",
            "expected_patterns": [r"(JWT|token|auth)", r"(componente|layer|capa|arquitectura)"],
            "min_length": 200,
            "timeout": 60,
        },
    ],
    "test-engineer": [
        {
            "id": "test_001",
            "task": "Genera tests unitarios para la función _validate_args en mcp-server/server.py",
            "expected_patterns": [r"(def test_|pytest|assert)", r"(validate|args)"],
            "min_length": 100,
            "timeout": 60,
        },
    ],
    "documentation-writer": [
        {
            "id": "docs_001",
            "task": "Documenta el módulo skill_composition_engine.py con docstrings y ejemplos",
            "expected_patterns": [
                r"(\"\"\"|\'\'\')|(docstring|ejemplo|example)",
                r"Args:|Returns:",
            ],
            "min_length": 150,
            "timeout": 60,
        },
    ],
    "debugger": [
        {
            "id": "debug_001",
            "task": "El servidor MCP no responde. Analiza las causas más probables y propón soluciones",
            "expected_patterns": [r"(causa|hipótesis|posible)", r"(solución|fix|resolver)"],
            "min_length": 100,
            "timeout": 60,
        },
    ],
    "planner": [
        {
            "id": "plan_001",
            "task": "Planifica la implementación de un sistema de cache Redis para el gateway HTTP",
            "expected_patterns": [r"(paso|step|fase)", r"(Redis|cache)", r"(\d\.|1\.|primer)"],
            "min_length": 150,
            "timeout": 60,
        },
    ],
    "performance-optimizer": [
        {
            "id": "perf_001",
            "task": "Identifica cuellos de botella en el skill discovery del servidor MCP",
            "expected_patterns": [
                r"(performance|rendimiento|bottleneck|cuello)",
                r"(optimiz|mejora)",
            ],
            "min_length": 100,
            "timeout": 60,
        },
    ],
}

# Benchmarks genéricos para todos los agentes
GENERIC_BENCHMARKS: list[dict[str, Any]] = [
    {
        "id": "generic_identity",
        "task": "Describe tu rol, capacidades principales y cuándo deberías ser invocado",
        "expected_patterns": [r"(rol|role|soy|capacidad)", r"(puedo|cuando|invoca)"],
        "min_length": 80,
        "timeout": 30,
    },
]


# =============================================================================
# Modelos
# =============================================================================


@dataclass
class EvalResult:
    """Resultado de evaluar un agente contra un benchmark."""

    eval_id: str
    agent_name: str
    benchmark_id: str
    task: str
    response: str
    score: float  # 0.0 - 1.0
    score_breakdown: dict  # {criterion: score}
    passed: bool
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentEvalSummary:
    """Resumen de evaluación de un agente."""

    agent_name: str
    total_benchmarks: int
    passed: int
    failed: int
    avg_score: float
    scores: list[float]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_benchmarks if self.total_benchmarks > 0 else 0.0


# =============================================================================
# Evaluador
# =============================================================================


class AgentEvaluator:
    """Evalúa agentes contra benchmarks con scoring heurístico."""

    def __init__(self) -> None:
        EVALS_DIR.mkdir(parents=True, exist_ok=True)
        EVALS_DB.parent.mkdir(parents=True, exist_ok=True)
        self.db = self._init_db()
        self.agents = self._discover_agents()
        logger.info("AgentEvaluator: %d agentes descubiertos", len(self.agents))

    def _init_db(self) -> sqlite3.Connection:
        """Inicializa la base de datos SQLite para historial."""
        conn = sqlite3.connect(str(EVALS_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eval_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                benchmark_id TEXT NOT NULL,
                task TEXT NOT NULL,
                score REAL NOT NULL,
                passed INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                timestamp TEXT NOT NULL,
                error TEXT,
                score_breakdown TEXT,
                response_preview TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_time
            ON eval_results(agent_name, timestamp)
        """)
        conn.commit()
        return conn

    def _discover_agents(self) -> dict[str, Path]:
        """Descubre agentes disponibles."""
        agents: dict[str, Path] = {}
        if not AGENTS_DIR.exists():
            return agents
        for agent_dir in AGENTS_DIR.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue
            for doc_name in ("SYSTEM_PROMPT.md", "IDENTITY.md"):
                if (agent_dir / doc_name).exists():
                    agents[agent_dir.name] = agent_dir / doc_name
                    break
        return agents

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_response(
        self, response: str, benchmark: dict[str, Any]
    ) -> tuple[float, dict[str, float]]:
        """
        Evalúa la calidad de una respuesta con heurísticas.

        Criterios:
        1. Longitud mínima (response no vacía)
        2. Patrones esperados (keywords relevantes)
        3. Estructura (listas, headers, código)
        4. Sin errores de ejecución
        5. Coherencia (no solo repite la pregunta)

        Returns:
            Tuple (score_total: float, breakdown: dict)
        """
        breakdown: dict[str, float] = {}

        # Criterio 1: Longitud mínima (0-0.2)
        min_len = benchmark.get("min_length", 50)
        length_score = min(len(response) / max(min_len, 1), 1.0) * 0.2
        breakdown["length"] = round(length_score, 3)

        # Criterio 2: Patrones esperados (0-0.4)
        patterns = benchmark.get("expected_patterns", [])
        if patterns:
            matched = sum(1 for p in patterns if re.search(p, response, re.IGNORECASE))
            pattern_score = (matched / len(patterns)) * 0.4
        else:
            pattern_score = 0.2  # Neutral si no hay patrones
        breakdown["patterns"] = round(pattern_score, 3)

        # Criterio 3: Estructura (0-0.2)
        structure_indicators = [
            r"^#{1,3} ",  # Headers Markdown
            r"^\d+\.",  # Listas numeradas
            r"^[-*] ",  # Listas con bullet
            r"```",  # Bloques de código
            r":\n",  # Definiciones
        ]
        structure_found = sum(
            1 for p in structure_indicators if re.search(p, response, re.MULTILINE)
        )
        structure_score = min(structure_found / 3, 1.0) * 0.2
        breakdown["structure"] = round(structure_score, 3)

        # Criterio 4: Sin errores obvios (0-0.1)
        error_patterns = [
            r"(Error:|Exception:|Traceback|ModuleNotFoundError)",
            r"(No such file|Permission denied|Cannot connect)",
        ]
        has_errors = any(re.search(p, response) for p in error_patterns)
        error_score = 0.0 if has_errors else 0.1
        breakdown["no_errors"] = round(error_score, 3)

        # Criterio 5: No trivial (0-0.1)
        task = benchmark.get("task", "")
        # Si la respuesta es substancialmente diferente de la tarea, es no trivial
        task_words = set(task.lower().split())
        response_words = set(response.lower().split())
        unique_in_response = response_words - task_words
        trivial_score = min(len(unique_in_response) / 20, 1.0) * 0.1
        breakdown["non_trivial"] = round(trivial_score, 3)

        total = sum(breakdown.values())
        return round(total, 3), breakdown

    # ------------------------------------------------------------------
    # Ejecución de evaluaciones
    # ------------------------------------------------------------------

    def eval_agent(self, agent_name: str) -> AgentEvalSummary | None:
        """Evalúa un agente contra sus benchmarks."""
        if agent_name not in self.agents:
            logger.warning("Agente '%s' no encontrado", agent_name)
            return None

        benchmarks = AGENT_BENCHMARKS.get(agent_name, []) + GENERIC_BENCHMARKS
        results: list[EvalResult] = []

        logger.info("Evaluando agente '%s' con %d benchmarks...", agent_name, len(benchmarks))

        for benchmark in benchmarks:
            result = self._run_benchmark(agent_name, benchmark)
            results.append(result)
            self._save_result(result)
            status = "PASS" if result.passed else "FAIL"
            logger.info("  [%s] %s — score: %.2f", status, benchmark["id"], result.score)

        scores = [r.score for r in results]
        passed = sum(1 for r in results if r.passed)
        avg_score = sum(scores) / len(scores) if scores else 0.0

        summary = AgentEvalSummary(
            agent_name=agent_name,
            total_benchmarks=len(results),
            passed=passed,
            failed=len(results) - passed,
            avg_score=round(avg_score, 3),
            scores=scores,
        )

        logger.info(
            "Agente '%s': %d/%d pass | avg_score=%.2f",
            agent_name,
            passed,
            len(results),
            avg_score,
        )
        return summary

    def _run_benchmark(self, agent_name: str, benchmark: dict[str, Any]) -> EvalResult:
        """Ejecuta un benchmark contra un agente."""
        eval_id = f"{agent_name}_{benchmark['id']}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        task = benchmark["task"]
        _timeout = benchmark.get("timeout", 60)  # reservado para invocación real del agente

        # Simulación: leer el IDENTITY.md del agente y evaluar si contiene
        # la información necesaria para responder la tarea.
        # En producción, esto invocaría el agente via HTTP gateway o subprocess.
        doc_file = self.agents[agent_name]
        start = time.perf_counter()

        try:
            doc_content = doc_file.read_text(encoding="utf-8")
            # Simular respuesta: extraer secciones relevantes del IDENTITY
            response = self._simulate_agent_response(agent_name, doc_content, task)
            error = None
        except Exception as e:
            response = ""
            error = str(e)

        duration_ms = (time.perf_counter() - start) * 1000
        score, breakdown = self.score_response(response, benchmark)

        return EvalResult(
            eval_id=eval_id,
            agent_name=agent_name,
            benchmark_id=benchmark["id"],
            task=task,
            response=response,
            score=score,
            score_breakdown=breakdown,
            passed=score >= 0.5,
            duration_ms=round(duration_ms, 1),
            error=error,
        )

    def _simulate_agent_response(self, agent_name: str, doc_content: str, task: str) -> str:
        """
        Simula la respuesta de un agente basándose en su IDENTITY.md.

        En producción, este método haría:
        1. POST http://127.0.0.1:4747/v1/agents/{agent_name}/run
        2. O subprocess con el agente directamente

        Por ahora usa el documento de identidad como proxy de capacidad.
        """
        lines = doc_content.split("\n")
        task_lower = task.lower()

        # Extraer secciones relevantes
        relevant_lines: list[str] = []
        in_relevant_section = False

        for line in lines:
            line_lower = line.lower()
            # Activar sección si hay coincidencia con palabras de la tarea
            task_keywords = [w for w in task_lower.split() if len(w) > 4]
            if any(kw in line_lower for kw in task_keywords):
                in_relevant_section = True

            if in_relevant_section:
                relevant_lines.append(line)
                if len(relevant_lines) > 30:
                    break

        # Combinar con el inicio del documento
        response_parts = [
            f"# Respuesta del agente {agent_name}",
            f"**Tarea:** {task}",
            "",
            "## Contexto del agente",
            "\n".join(lines[:20]),
            "",
        ]

        if relevant_lines:
            response_parts.extend(
                [
                    "## Información relevante",
                    "\n".join(relevant_lines),
                ]
            )

        return "\n".join(response_parts)

    def _save_result(self, result: EvalResult) -> None:
        """Guarda un resultado en SQLite."""
        self.db.execute(
            """
            INSERT INTO eval_results
            (eval_id, agent_name, benchmark_id, task, score, passed,
             duration_ms, timestamp, error, score_breakdown, response_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.eval_id,
                result.agent_name,
                result.benchmark_id,
                result.task[:500],
                result.score,
                1 if result.passed else 0,
                result.duration_ms,
                result.timestamp,
                result.error,
                json.dumps(result.score_breakdown),
                result.response[:200],
            ),
        )
        self.db.commit()

    # ------------------------------------------------------------------
    # Reportes
    # ------------------------------------------------------------------

    def generate_report(self, days: int = 7) -> dict:
        """Genera reporte de calidad de los últimos N días."""
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        rows = self.db.execute(
            """
            SELECT agent_name, AVG(score) as avg_score,
                   COUNT(*) as total, SUM(passed) as passed,
                   MIN(timestamp) as first, MAX(timestamp) as last
            FROM eval_results
            WHERE timestamp >= ?
            GROUP BY agent_name
            ORDER BY avg_score DESC
            """,
            (since,),
        ).fetchall()

        agents_data = []
        for row in rows:
            agent_name, avg_score, total, passed, first, last = row
            # Detectar tendencia (comparar con semana anterior)
            trend = self._get_trend(agent_name, since)
            agents_data.append(
                {
                    "agent": agent_name,
                    "avg_score": round(avg_score, 3),
                    "pass_rate": round(passed / total, 3) if total > 0 else 0,
                    "total_evals": total,
                    "trend": trend,
                    "last_eval": last,
                }
            )

        # Detectar regresiones
        regressions = [a for a in agents_data if a["trend"] == "declining"]

        return {
            "report_date": datetime.now(UTC).isoformat(),
            "period_days": days,
            "agents_evaluated": len(agents_data),
            "agents": agents_data,
            "regressions_detected": len(regressions),
            "regressions": regressions,
            "top_performers": agents_data[:3],
            "needs_attention": [a for a in agents_data if a["avg_score"] < 0.5],
        }

    def _get_trend(self, agent_name: str, since: str) -> str:
        """Calcula tendencia de score: improving | stable | declining."""
        rows = self.db.execute(
            """
            SELECT score, timestamp FROM eval_results
            WHERE agent_name = ? AND timestamp >= ?
            ORDER BY timestamp
            """,
            (agent_name, since),
        ).fetchall()

        if len(rows) < 2:
            return "stable"

        # Comparar primera mitad vs segunda mitad
        mid = len(rows) // 2
        first_half = sum(r[0] for r in rows[:mid]) / mid
        second_half = sum(r[0] for r in rows[mid:]) / (len(rows) - mid)

        delta = second_half - first_half
        if delta > 0.05:
            return "improving"
        if delta < -0.05:
            return "declining"
        return "stable"

    def print_report(self, report: dict) -> None:
        """Imprime el reporte en formato legible."""
        print("\n" + "=" * 60)
        print(f"EVAL REPORT — {report['report_date'][:10]}")
        print(f"Período: últimos {report['period_days']} días")
        print(f"Agentes evaluados: {report['agents_evaluated']}")
        print("=" * 60)

        if report["agents"]:
            print("\nRanking por score promedio:")
            print(f"{'Agente':<30} {'Score':<8} {'Pass%':<8} {'Trend'}")
            print("-" * 60)
            for a in report["agents"]:
                trend_icon = {"improving": "↑", "stable": "→", "declining": "↓"}.get(
                    a["trend"], "?"
                )
                print(
                    f"{a['agent']:<30} {a['avg_score']:.3f}   "
                    f"{a['pass_rate'] * 100:.0f}%    {trend_icon} {a['trend']}"
                )

        if report["regressions_detected"] > 0:
            print(f"\n⚠️  {report['regressions_detected']} regresión(es) detectada(s):")
            for r in report["regressions"]:
                print(f"   - {r['agent']} (score: {r['avg_score']:.3f})")

        if report["needs_attention"]:
            print("\n⚡ Agentes que necesitan atención (score < 0.5):")
            for a in report["needs_attention"]:
                print(f"   - {a['agent']} (score: {a['avg_score']:.3f})")

        print("=" * 60 + "\n")


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity Eval Pipeline")
    parser.add_argument("--agent", help="Evaluar solo un agente específico")
    parser.add_argument("--report", action="store_true", help="Solo generar reporte")
    parser.add_argument("--list", action="store_true", help="Listar benchmarks disponibles")
    parser.add_argument("--days", type=int, default=7, help="Días para el reporte (default: 7)")
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Formato de salida (default: text)",
    )
    args = parser.parse_args()

    evaluator = AgentEvaluator()

    if args.list:
        print("\nBenchmarks disponibles:")
        for agent, benchmarks in AGENT_BENCHMARKS.items():
            print(f"\n  {agent}:")
            for b in benchmarks:
                print(f"    [{b['id']}] {b['task'][:70]}...")
        print(f"\n  (+ {len(GENERIC_BENCHMARKS)} benchmarks genéricos para todos)")
        return

    if args.report:
        report = evaluator.generate_report(days=args.days)
        if args.output == "json":
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            evaluator.print_report(report)
        return

    summaries: list[AgentEvalSummary] = []

    if args.agent:
        summary = evaluator.eval_agent(args.agent)
        if summary:
            summaries.append(summary)
    else:
        # Evaluar todos los agentes con benchmarks definidos
        agents_to_eval = list(AGENT_BENCHMARKS.keys())
        logger.info("Evaluando %d agentes...", len(agents_to_eval))
        for agent_name in agents_to_eval:
            if agent_name in evaluator.agents:
                summary = evaluator.eval_agent(agent_name)
                if summary:
                    summaries.append(summary)

    if args.output == "json":
        print(json.dumps([asdict(s) for s in summaries], indent=2, ensure_ascii=False))
    else:
        # Mostrar resumen final
        print("\n" + "=" * 50)
        print("RESUMEN DE EVALUACIÓN")
        print("=" * 50)
        for s in summaries:
            icon = "✓" if s.avg_score >= 0.7 else "⚠" if s.avg_score >= 0.5 else "✗"
            print(
                f"{icon} {s.agent_name:<30} "
                f"score={s.avg_score:.2f} | "
                f"{s.passed}/{s.total_benchmarks} pass"
            )

        # Generar reporte post-eval
        report = evaluator.generate_report(days=1)
        if report["regressions_detected"]:
            print(f"\n⚠️  {report['regressions_detected']} regresión(es) detectada(s)!")

    print("\nResultados guardados en:", EVALS_DB)


if __name__ == "__main__":
    main()
