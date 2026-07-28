#!/usr/bin/env python3
"""
Vite Agents Orchestrator
Coordinador inteligente multi-agente para proyectos Vite
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Tipos de tareas que puede orquestar"""

    NEW_PROJECT = "NEW_PROJECT"
    ADD_FEATURE = "ADD_FEATURE"
    CONFIG_OPTIMIZATION = "CONFIG_OPTIMIZATION"
    PERFORMANCE_OPTIMIZATION = "PERFORMANCE_OPTIMIZATION"
    PLUGIN_DEVELOPMENT = "PLUGIN_DEVELOPMENT"
    BUILD_ANALYSIS = "BUILD_ANALYSIS"
    CONTENT_IMPROVEMENT = "CONTENT_IMPROVEMENT"
    UNKNOWN = "UNKNOWN"


@dataclass
class AgentTask:
    """Definición de tarea para un agente"""

    agent_name: str
    priority: int
    description: str
    inputs: dict[str, Any]
    estimated_duration: int  # en segundos


@dataclass
class OrchestrationResult:
    """Resultado de orquestación"""

    task_type: TaskType
    agents_sequence: list[AgentTask]
    total_estimated_time: int
    complexity: str  # LOW, MEDIUM, HIGH, EXTREME
    report: str


class ViteOrchestrator:
    """Orquestador inteligente para Vite"""

    def __init__(self):
        self.agents_registry = self._load_registry()
        self.execution_log = []

    def _load_registry(self) -> dict[str, Any]:
        """Carga registro de agentes"""
        registry_path = Path(__file__).parent.parent / "config" / "VITE_AGENTS_REGISTRY.json"
        if registry_path.exists():
            with open(registry_path) as f:
                return json.load(f)
        logger.warning(f"Registry no encontrado en {registry_path}")
        return self._default_registry()

    def _default_registry(self) -> dict[str, Any]:
        """Registro por defecto de agentes Vite"""
        return {
            "agents": {
                "vite-architect": {
                    "name": "vite-architect",
                    "role": "Diseño de arquitectura Vite",
                    "priority": 1,
                    "capabilities": ["project_design", "config_strategy", "framework_integration"],
                },
                "vite-plugin-developer": {
                    "name": "vite-plugin-developer",
                    "role": "Desarrollo de plugins Vite",
                    "priority": 2,
                    "capabilities": ["plugin_development", "hook_selection", "optimization"],
                },
                "vite-performance": {
                    "name": "vite-performance",
                    "role": "Optimización de performance",
                    "priority": 3,
                    "capabilities": ["bundle_analysis", "code_splitting", "optimization"],
                },
                "content-improver": {
                    "name": "content-improver",
                    "role": "Mejora de contenido y prompts",
                    "priority": 4,
                    "capabilities": ["documentation", "prompt_optimization", "code_examples"],
                },
            },
            "skills": {
                "vite-config-generator": "Genera configuraciones Vite optimizadas",
                "vite-build-optimizer": "Optimiza builds existentes",
                "vite-plugin-patterns": "Patrones probados de plugins",
            },
        }

    def classify_task(self, task_description: str) -> TaskType:
        """Clasifica el tipo de tarea basado en descripción"""
        task_lower = task_description.lower()

        keywords = {
            TaskType.NEW_PROJECT: ["crear", "nuevo", "proyecto", "setup", "iniciar"],
            TaskType.ADD_FEATURE: ["agregar", "añadir", "feature", "funcionalidad", "implement"],
            TaskType.CONFIG_OPTIMIZATION: [
                "config",
                "configuración",
                "optimize config",
                "vite.config",
            ],
            TaskType.PERFORMANCE_OPTIMIZATION: [
                "performance",
                "optimización",
                "bundle",
                "size",
                "speed",
            ],
            TaskType.PLUGIN_DEVELOPMENT: ["plugin", "crear plugin", "desarrollar plugin"],
            TaskType.BUILD_ANALYSIS: ["analizar", "análisis", "build", "bundle", "diagnóstico"],
            TaskType.CONTENT_IMPROVEMENT: [
                "mejorar",
                "documentación",
                "prompt",
                "contenido",
                "ejemplos",
            ],
        }

        for task_type, keywords_list in keywords.items():
            if any(kw in task_lower for kw in keywords_list):
                return task_type

        return TaskType.UNKNOWN

    def orchestrate(self, task_description: str) -> OrchestrationResult:
        """Orquesta secuencia de agentes para la tarea"""
        task_type = self.classify_task(task_description)
        logger.info(f"Tarea clasificada como: {task_type.value}")

        agents_sequence = self._get_agent_sequence(task_type)
        complexity = self._estimate_complexity(task_type, task_description)
        total_time = sum(agent.estimated_duration for agent in agents_sequence)

        report = self._generate_report(task_type, agents_sequence, complexity)

        return OrchestrationResult(
            task_type=task_type,
            agents_sequence=agents_sequence,
            total_estimated_time=total_time,
            complexity=complexity,
            report=report,
        )

    def _get_agent_sequence(self, task_type: TaskType) -> list[AgentTask]:
        """Define secuencia de agentes según tipo de tarea"""

        sequences = {
            TaskType.NEW_PROJECT: [
                AgentTask(
                    agent_name="vite-architect",
                    priority=1,
                    description="Diseñar arquitectura del proyecto",
                    inputs={"project_type": "spa", "framework": "react"},
                    estimated_duration=120,
                ),
                AgentTask(
                    agent_name="vite-config-generator",
                    priority=2,
                    description="Generar configuración Vite optimizada",
                    inputs={"optimization_level": "aggressive"},
                    estimated_duration=60,
                ),
                AgentTask(
                    agent_name="content-improver",
                    priority=3,
                    description="Mejorar documentación inicial",
                    inputs={"content_type": "readme"},
                    estimated_duration=45,
                ),
            ],
            TaskType.ADD_FEATURE: [
                AgentTask(
                    agent_name="vite-architect",
                    priority=1,
                    description="Analizar arquitectura existente",
                    inputs={"analyze_current": True},
                    estimated_duration=90,
                ),
                AgentTask(
                    agent_name="vite-plugin-developer",
                    priority=2,
                    description="Desarrollar plugin si es necesario",
                    inputs={"feature_type": "plugin"},
                    estimated_duration=180,
                ),
                AgentTask(
                    agent_name="vite-performance",
                    priority=3,
                    description="Validar performance",
                    inputs={"validate": True},
                    estimated_duration=60,
                ),
            ],
            TaskType.CONFIG_OPTIMIZATION: [
                AgentTask(
                    agent_name="vite-architect",
                    priority=1,
                    description="Revisar arquitectura de config",
                    inputs={"review_config": True},
                    estimated_duration=60,
                ),
                AgentTask(
                    agent_name="vite-build-optimizer",
                    priority=2,
                    description="Optimizar configuración",
                    inputs={"optimization_level": "aggressive"},
                    estimated_duration=120,
                ),
                AgentTask(
                    agent_name="content-improver",
                    priority=3,
                    description="Documentar cambios",
                    inputs={"content_type": "documentation"},
                    estimated_duration=45,
                ),
            ],
            TaskType.PERFORMANCE_OPTIMIZATION: [
                AgentTask(
                    agent_name="vite-performance",
                    priority=1,
                    description="Analizar performance actual",
                    inputs={"analyze_current": True, "optimization_level": "extreme"},
                    estimated_duration=150,
                ),
                AgentTask(
                    agent_name="vite-build-optimizer",
                    priority=2,
                    description="Aplicar optimizaciones",
                    inputs={"apply_optimizations": True},
                    estimated_duration=120,
                ),
                AgentTask(
                    agent_name="content-improver",
                    priority=3,
                    description="Generar reporte de mejoras",
                    inputs={"content_type": "report"},
                    estimated_duration=60,
                ),
            ],
            TaskType.PLUGIN_DEVELOPMENT: [
                AgentTask(
                    agent_name="vite-plugin-developer",
                    priority=1,
                    description="Diseñar arquitectura del plugin",
                    inputs={"design_plugin": True},
                    estimated_duration=120,
                ),
                AgentTask(
                    agent_name="vite-plugin-patterns",
                    priority=2,
                    description="Aplicar patrones probados",
                    inputs={"pattern_type": "all"},
                    estimated_duration=90,
                ),
                AgentTask(
                    agent_name="content-improver",
                    priority=3,
                    description="Documentar plugin",
                    inputs={"content_type": "api_docs"},
                    estimated_duration=60,
                ),
            ],
            TaskType.BUILD_ANALYSIS: [
                AgentTask(
                    agent_name="vite-performance",
                    priority=1,
                    description="Analizar build actual",
                    inputs={"analyze_current": True},
                    estimated_duration=120,
                ),
                AgentTask(
                    agent_name="vite-build-optimizer",
                    priority=2,
                    description="Generar reporte de análisis",
                    inputs={"generate_report": True},
                    estimated_duration=90,
                ),
                AgentTask(
                    agent_name="content-improver",
                    priority=3,
                    description="Documentar hallazgos",
                    inputs={"content_type": "analysis_report"},
                    estimated_duration=45,
                ),
            ],
            TaskType.CONTENT_IMPROVEMENT: [
                AgentTask(
                    agent_name="content-improver",
                    priority=1,
                    description="Analizar contenido actual",
                    inputs={"analyze_content": True},
                    estimated_duration=60,
                ),
                AgentTask(
                    agent_name="content-improver",
                    priority=2,
                    description="Generar mejoras",
                    inputs={"generate_improvements": True},
                    estimated_duration=90,
                ),
            ],
        }

        return sequences.get(
            task_type,
            [
                AgentTask(
                    agent_name="vite-architect",
                    priority=1,
                    description="Analizar tarea",
                    inputs={},
                    estimated_duration=60,
                )
            ],
        )

    def _estimate_complexity(self, task_type: TaskType, description: str) -> str:
        """Estima complejidad de la tarea"""
        complexity_map = {
            TaskType.NEW_PROJECT: "MEDIUM",
            TaskType.ADD_FEATURE: "MEDIUM",
            TaskType.CONFIG_OPTIMIZATION: "LOW",
            TaskType.PERFORMANCE_OPTIMIZATION: "HIGH",
            TaskType.PLUGIN_DEVELOPMENT: "HIGH",
            TaskType.BUILD_ANALYSIS: "LOW",
            TaskType.CONTENT_IMPROVEMENT: "LOW",
            TaskType.UNKNOWN: "MEDIUM",
        }

        base_complexity = complexity_map.get(task_type, "MEDIUM")

        # Ajustar según keywords
        if any(
            word in description.lower() for word in ["complejo", "avanzado", "extreme", "custom"]
        ):
            complexity_levels = ["LOW", "MEDIUM", "HIGH", "EXTREME"]
            current_idx = complexity_levels.index(base_complexity)
            if current_idx < 3:
                return complexity_levels[current_idx + 1]

        return base_complexity

    def _generate_report(
        self, task_type: TaskType, agents: list[AgentTask], complexity: str
    ) -> str:
        """Genera reporte de orquestación"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║           VITE ORCHESTRATOR - Reporte de Ejecución           ║
╚══════════════════════════════════════════════════════════════╝

Timestamp: {timestamp}
Tipo de Tarea: {task_type.value}
Complejidad: {complexity}
Agentes en Secuencia: {len(agents)}
Tiempo Estimado: {sum(a.estimated_duration for a in agents)}s

──────────────────────────────────────────────────────────────
SECUENCIA DE EJECUCIÓN:
──────────────────────────────────────────────────────────────
"""

        for i, agent in enumerate(agents, 1):
            report += f"\n[{i}] {agent.agent_name} (Prioridad: {agent.priority})"
            report += f"\n    Descripción: {agent.description}"
            report += f"\n    Tiempo: ~{agent.estimated_duration}s"
            report += f"\n    Inputs: {json.dumps(agent.inputs, ensure_ascii=False, indent=6)}\n"

        report += """
──────────────────────────────────────────────────────────────
RECOMENDACIONES:
──────────────────────────────────────────────────────────────
"""

        if complexity == "EXTREME":
            report += "⚠️  Tarea de alta complejidad. Recomendado:\n"
            report += "   • Revisar paso a paso cada salida de agente\n"
            report += "   • Validar cambios de configuración\n"
            report += "   • Hacer backup antes de aplicar\n"
        elif complexity == "HIGH":
            report += "ℹ️  Tarea compleja. Recomendado:\n"
            report += "   • Revisar salidas intermedias\n"
            report += "   • Validar antes de proceeder\n"
        else:
            report += "✓ Tarea de complejidad baja-media. Ejecución estándar.\n"

        report += f"\n{'=' * 60}\n"

        return report

    def execute(self, task_description: str) -> None:
        """Ejecuta orquestación y muestra resultado"""
        logger.info(f"Iniciando orquestación para: {task_description}")

        result = self.orchestrate(task_description)

        print(result.report)

        logger.info(f"Orquestación completada. Complejidad: {result.complexity}")

        # Guardar en log
        self.execution_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "task_description": task_description,
                "task_type": result.task_type.value,
                "complexity": result.complexity,
                "agents_count": len(result.agents_sequence),
                "estimated_time": result.total_estimated_time,
            }
        )


def main():
    """Punto de entrada del orquestador"""
    import sys

    orchestrator = ViteOrchestrator()

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        orchestrator.execute(task)
    else:
        # Modo interactivo
        print("\n╔═══════════════════════════════════════════════════════════╗")
        print("║       Vite Agents Orchestrator - Modo Interactivo        ║")
        print("╚═══════════════════════════════════════════════════════════╝\n")

        while True:
            try:
                task = input("Describe tu tarea (o 'salir' para terminar): ").strip()

                if task.lower() in ["salir", "exit", "quit"]:
                    logger.info("Orquestador terminado")
                    break

                if not task:
                    continue

                orchestrator.execute(task)

            except KeyboardInterrupt:
                print("\n\nOrquestador interrumpido por usuario")
                break
            except Exception as e:
                logger.error(f"Error durante orquestación: {e}")


if __name__ == "__main__":
    main()
