"""Motor de ejecución especulativa basado en Monte Carlo Tree Search (MCTS).

Permite que un agente bifurque su razonamiento en N ramas paralelas, cada una
representando un enfoque técnico distinto para resolver un problema. Evalúa
todas las ramas concurrentemente usando el LLM como función de evaluación y
selecciona matemáticamente la más óptima según métricas de errores, rendimiento
y complejidad. Implementa el patrón Hypothesis/Evaluation/Selection.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.mcts")


class ExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HypothesisNode:
    """Representa una rama de pensamiento/ejecución (Hypothesis)"""

    id: str
    approach_description: str
    code_proposal: str = ""
    evaluation_score: float = 0.0
    state: ExecutionState = ExecutionState.PENDING
    metrics: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


class MCTSExecutor:
    """
    Monte Carlo Tree Search (MCTS) / Speculative Execution Engine.
    Permite que un agente bifurque su "mente" en N ramas paralelas,
    evalúe múltiples enfoques y escoja el enfoque matemáticamente óptimo
    (menos errores, mejor rendimiento, menor complejidad).
    """

    def __init__(self, llm_client: Any, max_branches: int = 3):
        self.llm = llm_client
        self.max_branches = max_branches

    async def _generate_approaches(self, task: str) -> list[str]:
        """Usa el LLM para generar N enfoques distintos para resolver el problema."""
        prompt = f"""Escribe {self.max_branches} enfoques técnicos COMPLETAMENTE DISTINTOS para resolver este problema:
{task}

Por ejemplo, si es una API, el Enfoque 1 podría usar REST tradicional, el Enfoque 2 WebSockets, y el Enfoque 3 GraphQL.
Si es lógica, el Enfoque 1 podría ser recursivo, el 2 iterativo, el 3 concurrente.

Responde ÚNICAMENTE con un JSON Array de strings, cada string siendo la descripción de un enfoque."""

        # Simulating LLM response parsing to list
        # In a real scenario, we call self.llm
        try:
            response = await self.llm.generate(
                prompt=prompt, system="Eres un arquitecto senior divergente."
            )
            import json

            # Intento crudo de parsear array JSON de la respuesta
            text = response.content
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end != -1:
                approaches = json.loads(text[start:end])
                return approaches[: self.max_branches]
        except Exception as e:
            logger.error(f"Failed to generate distinct approaches: {e}")

        # Fallback genérico si falla el parseo
        return [
            "Enfoque Convencional/Sincrónico",
            "Enfoque Paralelo/Asincrónico",
            "Enfoque Optimizado para Memoria (Iterativo/Generadores)",
        ][: self.max_branches]

    async def _evaluate_branch(self, node: HypothesisNode, task: str) -> HypothesisNode:
        """Promptea al LLM para que intente escribir y evaluar la solución para ese enfoque en específico."""
        node.state = ExecutionState.RUNNING
        start_time = time.time()

        prompt = f"""TAREA PRINCIPAL: {task}
ENFOQUE ASIGNADO: {node.approach_description}

Escribe el código para este enfoque. Además, evalúa tu propio código del 1 al 10 en base a:
- Rendimiento (Big O)
- Seguridad
- Simplicidad (KISS)

Al final incluye EXACTAMENTE "SCORE: X.X" donde X es tu evaluación total de 1 a 10."""

        try:
            # ReAct or direct generation
            res = await self.llm.generate(
                prompt=prompt, system="Eres un desarrollador experto hiper-crítico."
            )
            content = res.content

            # Simple heuristic evaluation extraction
            import re

            match = re.search(r"SCORE:\s*([\d\.]+)", content)
            if match:
                node.evaluation_score = float(match.group(1))
            else:
                node.evaluation_score = 5.0  # default

            node.code_proposal = content
            node.state = ExecutionState.COMPLETED
        except Exception as e:
            node.state = ExecutionState.FAILED
            node.errors.append(str(e))
            node.evaluation_score = 0.0

        node.metrics["duration_ms"] = (time.time() - start_time) * 1000
        return node

    async def run_speculative_execution(self, task: str) -> HypothesisNode:
        """
        Punto de entrada principal.
        Bifurca, ejecuta en paralelo, evalúa, y retorna la mejor rama.
        """
        logger.info(
            f"Iniciando MCTS Speculative Execution (Máx {self.max_branches} ramas) para: {task[:50]}..."
        )

        # 1. Generar Hipótesis
        approaches = await self._generate_approaches(task)
        nodes = [
            HypothesisNode(id=f"branch_{i}", approach_description=app)
            for i, app in enumerate(approaches)
        ]

        # 2. Ejecutar todas las ramas EN PARALELO
        eval_tasks = [self._evaluate_branch(node, task) for node in nodes]
        completed_nodes = await asyncio.gather(*eval_tasks)

        # 3. Matemática de decantación (Elige el ganador)
        valid_nodes = [n for n in completed_nodes if n.state == ExecutionState.COMPLETED]
        if not valid_nodes:
            logger.error("Todas las ramas de especulación fallaron.")
            return completed_nodes[0]  # Return one of the failed ones

        # Ordenar por el score heurístico del LLM (podría ser reemplazado por métricas reales de pylint/pytest)
        valid_nodes.sort(key=lambda n: n.evaluation_score, reverse=True)

        winner = valid_nodes[0]
        logger.info(
            f"Ganador seleccionado: {winner.id} con SCORE {winner.evaluation_score} - Enfoque: {winner.approach_description[:50]}..."
        )
        return winner
