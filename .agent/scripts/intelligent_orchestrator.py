#!/usr/bin/env python3
"""
Intelligent Orchestrator - Orquestador Unificado con Todas las Mejoras.

Este script combina:
- ExecutionEngine con Learning Loop
- MemoryBus para memoria compartida
- AgentMessageBus para comunicacion inter-agente
- FeedbackCollector para retroalimentacion
- ErrorRecovery para recuperacion automatica

Uso:
    python intelligent_orchestrator.py "Tu tarea aqui"
    python intelligent_orchestrator.py "Auditar seguridad" --agents security-auditor
    python intelligent_orchestrator.py "Crear API" --feedback

Version: 1.0.0
"""

import asyncio
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger("intelligent-orchestrator")


class IntelligentOrchestrator:
    """
    Orquestador inteligente que integra todos los sistemas mejorados.

    Caracteristicas:
    - Ejecuta tareas con multiples agentes
    - Aprende de cada ejecucion
    - Comparte contexto entre agentes
    - Recupera automaticamente de errores
    - Recopila feedback del usuario
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._initialize_components()

    def _initialize_components(self):
        """Inicializa todos los componentes."""
        # Execution Engine
        try:
            from .agent.core.execution_engine import get_engine

            self.engine = get_engine()
            logger.info("ExecutionEngine inicializado")
        except ImportError as e:
            logger.warning(f"ExecutionEngine no disponible: {e}")
            self.engine = None

        # Memory Bus
        try:
            from .agent.core.memory import get_memory_bus

            self.memory_bus = get_memory_bus()
            logger.info("MemoryBus inicializado")
        except ImportError as e:
            logger.warning(f"MemoryBus no disponible: {e}")
            self.memory_bus = None

        # Message Bus
        try:
            from .agent.core.a2a import get_message_bus

            self.message_bus = get_message_bus()
            logger.info("MessageBus inicializado")
        except ImportError as e:
            logger.warning(f"MessageBus no disponible: {e}")
            self.message_bus = None

        # Feedback Collector
        try:
            from .agent.core.feedback import get_feedback_collector

            self.feedback_collector = get_feedback_collector()
            logger.info("FeedbackCollector inicializado")
        except ImportError as e:
            logger.warning(f"FeedbackCollector no disponible: {e}")
            self.feedback_collector = None

        # Learning Pipeline
        try:
            from .agent.core.autonomous_learning import get_learning_pipeline

            self.learning_pipeline = get_learning_pipeline()
            logger.info("LearningPipeline inicializado")
        except ImportError as e:
            logger.warning(f"LearningPipeline no disponible: {e}")
            self.learning_pipeline = None

        # Error Recovery
        try:
            from .agent.core.intelligence.error_recovery import ErrorRecovery

            self.error_recovery = ErrorRecovery()
            logger.info("ErrorRecovery inicializado")
        except ImportError as e:
            logger.warning(f"ErrorRecovery no disponible: {e}")
            self.error_recovery = None

    async def execute(
        self, task: str, custom_agents: list | None = None, collect_feedback: bool = False
    ) -> dict:
        """
        Ejecuta una tarea con orquestacion inteligente.

        Args:
            task: Descripcion de la tarea
            custom_agents: Lista de agentes especificos (opcional)
            collect_feedback: Recopilar feedback al final

        Returns:
            Reporte de ejecucion
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Iniciando tarea: {task[:50]}...")

        # Cargar contexto previo del MemoryBus
        prior_context = {}
        if self.memory_bus:
            prior_context = self.memory_bus.retrieve(task, memory_type="context", limit=5)
            if prior_context:
                logger.info(f"Contexto previo encontrado: {len(prior_context)} memorias")

        # Suscribir al MessageBus para ver comunicacion inter-agente
        messages_received = []
        if self.message_bus:
            self.message_bus.subscribe("*", lambda msg: messages_received.append(msg))

        # Crear y ejecutar plan
        if not self.engine:
            return {"error": "ExecutionEngine no disponible"}

        plan = self.engine.create_plan(task, custom_agents)
        logger.info(
            f"Plan creado: {len(plan.agents)} agentes en {len(plan.parallel_groups)} grupos"
        )

        if self.verbose:
            for i, group in enumerate(plan.parallel_groups, 1):
                agents_str = " + ".join(group) if len(group) > 1 else group[0]
                logger.info(f"  Grupo {i}: [{agents_str}]")

        # Ejecutar plan
        report = await self.engine.execute_plan(plan)

        # Procesar resultados
        result = {
            "task_id": task_id,
            "task": task,
            "status": report.status.value,
            "total_time_ms": report.total_time_ms,
            "success_count": report.success_count,
            "failure_count": report.failure_count,
            "agents_executed": [r.agent_name for r in report.results],
            "messages_exchanged": len(messages_received),
            "results": [],
        }

        for r in report.results:
            agent_result = {
                "agent": r.agent_name,
                "status": r.status.value,
                "execution_time_ms": r.execution_time_ms,
                "output_preview": r.output[:200] if r.output else None,
            }

            # Incluir info de recovery si hay error
            if r.error and r.metadata.get("recovery"):
                agent_result["recovery_suggestion"] = r.metadata["recovery"]

            result["results"].append(agent_result)

        # Guardar resultado en MemoryBus
        if self.memory_bus:
            self.memory_bus.store(
                key=f"execution:{task_id}",
                value={
                    "task": task,
                    "status": report.status.value,
                    "agents": result["agents_executed"],
                    "time_ms": report.total_time_ms,
                },
                memory_type="decision",
                task_id=task_id,
            )

        # Registrar para feedback si se solicita
        if collect_feedback and self.feedback_collector:
            feedback_url = await self.feedback_collector.register_execution(
                task_id=task_id,
                execution_data={
                    "task": task,
                    "agents_used": result["agents_executed"],
                    "success": report.status.value == "success",
                },
            )
            result["feedback_url"] = feedback_url
            logger.info(f"Feedback habilitado: {feedback_url}")

        # Log resumen
        logger.info(
            f"Ejecucion completada: {report.status.value} "
            f"({report.success_count}/{len(report.results)} agentes exitosos) "
            f"en {report.total_time_ms}ms"
        )

        return result

    async def submit_feedback(
        self, task_id: str, rating: int, accepted: bool = True, corrections: str | None = None
    ) -> bool:
        """Enviar feedback para una ejecucion."""
        if not self.feedback_collector:
            logger.warning("FeedbackCollector no disponible")
            return False

        return await self.feedback_collector.submit_feedback(
            task_id=task_id, rating=rating, accepted=accepted, corrections=corrections
        )

    async def run_learning_cycle(self):
        """Ejecutar ciclo de aprendizaje."""
        if not self.learning_pipeline:
            logger.warning("LearningPipeline no disponible")
            return

        logger.info("Ejecutando ciclo de aprendizaje...")
        await self.learning_pipeline.run_learning_cycle()
        logger.info("Ciclo de aprendizaje completado")

    def get_learning_stats(self) -> dict:
        """Obtener estadisticas de aprendizaje."""
        if not self.learning_pipeline:
            return {}

        return {
            "patterns": len(self.learning_pipeline.patterns),
            "strategies": len(self.learning_pipeline.strategies),
            "preferences": len(self.learning_pipeline.preferences),
            "learning_events": len(self.learning_pipeline.learning_events),
        }

    def get_system_status(self) -> dict:
        """Obtener estado del sistema."""
        return {
            "execution_engine": self.engine is not None,
            "memory_bus": self.memory_bus is not None,
            "message_bus": self.message_bus is not None,
            "feedback_collector": self.feedback_collector is not None,
            "learning_pipeline": self.learning_pipeline is not None,
            "error_recovery": self.error_recovery is not None,
            "learning_stats": self.get_learning_stats(),
        }


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Intelligent Orchestrator - Orquestacion Inteligente de Agentes"
    )
    parser.add_argument("task", nargs="?", help="Tarea a ejecutar")
    parser.add_argument("--agents", "-a", nargs="+", help="Agentes especificos")
    parser.add_argument("--feedback", "-f", action="store_true", help="Recopilar feedback")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo verbose")
    parser.add_argument("--json", action="store_true", help="Output en JSON")
    parser.add_argument("--status", action="store_true", help="Mostrar estado del sistema")
    parser.add_argument("--learn", action="store_true", help="Ejecutar ciclo de aprendizaje")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadisticas")

    args = parser.parse_args()

    orchestrator = IntelligentOrchestrator(verbose=args.verbose)

    if args.status:
        status = orchestrator.get_system_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("\n=== Estado del Sistema ===\n")
            for component, available in status.items():
                if component == "learning_stats":
                    continue
                icon = "OK" if available else "X"
                print(f"  [{icon}] {component}")

            if status.get("learning_stats"):
                print("\n=== Estadisticas de Aprendizaje ===\n")
                for key, value in status["learning_stats"].items():
                    print(f"  {key}: {value}")
        return

    if args.learn:
        await orchestrator.run_learning_cycle()
        return

    if args.stats:
        stats = orchestrator.get_learning_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\n=== Estadisticas de Aprendizaje ===\n")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        return

    if not args.task:
        parser.print_help()
        print("\nEjemplos:")
        print("  python intelligent_orchestrator.py 'Auditar seguridad del codigo'")
        print(
            "  python intelligent_orchestrator.py 'Crear API REST' --agents api-designer architect"
        )
        print("  python intelligent_orchestrator.py 'Refactorizar auth' --feedback")
        print("  python intelligent_orchestrator.py --status")
        return

    # Ejecutar tarea
    result = await orchestrator.execute(
        task=args.task, custom_agents=args.agents, collect_feedback=args.feedback
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n=== Resultado: {result['status'].upper()} ===\n")
        print(f"Tarea: {result['task'][:80]}...")
        print(f"Tiempo total: {result['total_time_ms']}ms")
        print(f"Agentes: {result['success_count']}/{len(result['results'])} exitosos")

        if result.get("messages_exchanged", 0) > 0:
            print(f"Mensajes inter-agente: {result['messages_exchanged']}")

        print("\nResultados por agente:")
        for r in result["results"]:
            icon = "OK" if r["status"] == "success" else "X"
            print(f"  [{icon}] {r['agent']} ({r['execution_time_ms']}ms)")

            if r.get("recovery_suggestion"):
                print(f"      > Sugerencia: {r['recovery_suggestion'].get('strategy', 'N/A')}")

        if result.get("feedback_url"):
            print(f"\nFeedback URL: {result['feedback_url']}")


if __name__ == "__main__":
    asyncio.run(main())
