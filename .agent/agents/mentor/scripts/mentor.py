#!/usr/bin/env python3
"""
Mentor Agent - Agente mentor que guia a otros agentes.

Detecta cuando un agente esta atascado y proporciona ayuda:
- Sugiere agentes a consultar
- Facilita colaboracion
- Escala a humano cuando es necesario
- Documenta soluciones

Uso:
    python mentor.py diagnose <agent_name> <problem>
    python mentor.py suggest <task>
    python mentor.py escalate <context>
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# Configuracion de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.mentor")


class ProblemType(Enum):
    """Tipos de problemas que pueden tener los agentes."""

    LACK_OF_CONTEXT = "lack_of_context"
    OUT_OF_EXPERTISE = "out_of_expertise"
    DECISION_CONFLICT = "decision_conflict"
    TECHNICAL_ERROR = "technical_error"
    TASK_TOO_LARGE = "task_too_large"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN = "unknown"


class ActionType(Enum):
    """Tipos de acciones recomendadas."""

    CONSULT_AGENT = "consult_agent"
    GATHER_CONTEXT = "gather_context"
    DECOMPOSE_TASK = "decompose_task"
    INITIATE_DEBATE = "initiate_debate"
    ESCALATE_HUMAN = "escalate_human"
    RETRY_WITH_HINTS = "retry_with_hints"


@dataclass
class Diagnosis:
    """Diagnostico de un problema de agente."""

    agent_name: str
    problem_description: str
    problem_type: ProblemType
    confidence: float
    signals: list[str]
    root_cause: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["problem_type"] = self.problem_type.value
        return d


@dataclass
class Recommendation:
    """Recomendacion del mentor."""

    action_type: ActionType
    description: str
    agents_to_consult: list[str]
    context_to_gather: list[str]
    questions_for_human: list[str]
    priority: int

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action_type"] = self.action_type.value
        return d


@dataclass
class MentorResponse:
    """Respuesta completa del mentor."""

    diagnosis: Diagnosis
    recommendations: list[Recommendation]
    escalation_needed: bool
    escalation_reason: str | None
    encouragement: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "diagnosis": self.diagnosis.to_dict(),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "escalation_needed": self.escalation_needed,
            "escalation_reason": self.escalation_reason,
            "encouragement": self.encouragement,
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        """Generar respuesta en markdown."""
        lines = [
            "# Respuesta del Mentor",
            "",
            f"**Agente:** {self.diagnosis.agent_name}",
            f"**Problema:** {self.diagnosis.problem_description}",
            f"**Tipo:** {self.diagnosis.problem_type.value}",
            f"**Confianza del diagnostico:** {self.diagnosis.confidence:.0%}",
            "",
            "## Analisis",
            "",
            f"**Causa raiz:** {self.diagnosis.root_cause}",
            "",
            "**Senales detectadas:**",
        ]

        for signal in self.diagnosis.signals:
            lines.append(f"- {signal}")

        lines.extend(["", "## Recomendaciones", ""])

        for i, rec in enumerate(self.recommendations, 1):
            lines.append(f"### {i}. {rec.description}")
            lines.append(f"**Accion:** {rec.action_type.value}")
            lines.append(f"**Prioridad:** {rec.priority}")

            if rec.agents_to_consult:
                lines.append("\n**Agentes a consultar:**")
                for agent in rec.agents_to_consult:
                    lines.append(f"- `{agent}`")

            if rec.context_to_gather:
                lines.append("\n**Contexto a recopilar:**")
                for ctx in rec.context_to_gather:
                    lines.append(f"- {ctx}")

            lines.append("")

        if self.escalation_needed:
            lines.extend(
                [
                    "## Escalamiento Necesario",
                    "",
                    f"**Razon:** {self.escalation_reason}",
                    "",
                    "**Preguntas para el humano:**",
                ]
            )
            for q in self.recommendations[0].questions_for_human if self.recommendations else []:
                lines.append(f"- {q}")

        lines.extend(["", "---", "", f"> {self.encouragement}", ""])

        return "\n".join(lines)


class MentorAgent:
    """Agente mentor que guia a otros agentes."""

    # Mapeo de agentes por dominio
    DOMAIN_AGENTS = {
        "frontend": ["frontend-specialist", "react-specialist", "ui-ux-designer"],
        "backend": ["backend-specialist", "api-designer", "database-architect"],
        "security": ["security-auditor", "penetration-tester"],
        "testing": ["test-engineer", "load-testing-engineer"],
        "devops": ["devops-engineer", "infrastructure-architect"],
        "architecture": ["architect", "planner"],
        "documentation": ["documentation-writer", "docusaurus-expert"],
        "data": ["data-engineer", "ml-engineer"],
        "mobile": ["mobile-developer"],
        "compliance": ["compliance-auditor"],
    }

    # Frases de animo
    ENCOURAGEMENTS = [
        "Recuerda: cada problema es una oportunidad de aprender.",
        "Estas en el camino correcto. Sigue adelante.",
        "No tengas miedo de pedir ayuda. Es una fortaleza, no debilidad.",
        "Los mejores agentes son los que colaboran efectivamente.",
        "Divide y venceras. Un paso a la vez.",
        "La persistencia es clave. Tu puedes con esto.",
        "Confio en tu capacidad para resolver esto.",
    ]

    def __init__(self):
        self.knowledge_base: list[dict] = []
        self._load_knowledge()

    def _load_knowledge(self):
        """Cargar base de conocimiento de soluciones previas."""
        kb_path = Path(__file__).parent / "knowledge_base.json"
        if kb_path.exists():
            with contextlib.suppress(Exception):
                self.knowledge_base = json.loads(kb_path.read_text())

    def diagnose(self, agent_name: str, problem: str, context: dict = None) -> Diagnosis:
        """Diagnosticar el problema de un agente."""
        context = context or {}
        signals = []

        # Detectar tipo de problema
        problem_lower = problem.lower()

        # Falta de contexto
        if any(
            kw in problem_lower for kw in ["no se", "no entiendo", "falta informacion", "contexto"]
        ):
            problem_type = ProblemType.LACK_OF_CONTEXT
            signals.append("Palabras clave de falta de informacion detectadas")
            root_cause = "El agente no tiene suficiente contexto para completar la tarea"

        # Fuera de expertise
        elif any(
            kw in problem_lower for kw in ["no es mi area", "no tengo experiencia", "fuera de mi"]
        ):
            problem_type = ProblemType.OUT_OF_EXPERTISE
            signals.append("El agente reconoce limitaciones de expertise")
            root_cause = "La tarea requiere conocimientos especializados que el agente no posee"

        # Conflicto de decision
        elif any(
            kw in problem_lower for kw in ["no se cual elegir", "opciones", "decision", "conflicto"]
        ):
            problem_type = ProblemType.DECISION_CONFLICT
            signals.append("Multiples opciones sin criterio claro de seleccion")
            root_cause = "Hay multiples enfoques validos y se necesita consenso"

        # Error tecnico
        elif any(kw in problem_lower for kw in ["error", "fallo", "excepcion", "bug", "crash"]):
            problem_type = ProblemType.TECHNICAL_ERROR
            signals.append("Error tecnico reportado")
            root_cause = "Hay un problema tecnico que impide la ejecucion"

        # Tarea muy grande
        elif any(
            kw in problem_lower for kw in ["muy grande", "complejo", "muchos pasos", "abrumador"]
        ):
            problem_type = ProblemType.TASK_TOO_LARGE
            signals.append("La tarea parece demasiado grande para abordar directamente")
            root_cause = "La tarea necesita ser descompuesta en subtareas manejables"

        # Baja confianza
        elif context.get("confidence", 1.0) < 0.5:
            problem_type = ProblemType.LOW_CONFIDENCE
            signals.append(f"Confianza baja: {context.get('confidence', 0):.0%}")
            root_cause = "El agente tiene dudas sobre la calidad de su respuesta"

        else:
            problem_type = ProblemType.UNKNOWN
            signals.append("No se pudo categorizar el problema claramente")
            root_cause = "Se requiere mas informacion para diagnosticar"

        # Agregar senales del contexto
        if context.get("retry_count", 0) > 2:
            signals.append(f"Multiples reintentos: {context['retry_count']}")

        if context.get("execution_time_seconds", 0) > 60:
            signals.append(f"Tiempo de ejecucion alto: {context['execution_time_seconds']}s")

        return Diagnosis(
            agent_name=agent_name,
            problem_description=problem,
            problem_type=problem_type,
            confidence=0.8 if problem_type != ProblemType.UNKNOWN else 0.4,
            signals=signals,
            root_cause=root_cause,
        )

    def recommend(self, diagnosis: Diagnosis, task: str = "") -> list[Recommendation]:
        """Generar recomendaciones basadas en el diagnostico."""
        recommendations = []

        if diagnosis.problem_type == ProblemType.LACK_OF_CONTEXT:
            recommendations.append(
                Recommendation(
                    action_type=ActionType.GATHER_CONTEXT,
                    description="Recopilar mas contexto antes de continuar",
                    agents_to_consult=["explorer"],
                    context_to_gather=[
                        "Documentacion relevante del proyecto",
                        "Codigo relacionado existente",
                        "Requisitos originales de la tarea",
                    ],
                    questions_for_human=[
                        "Puedes proporcionar mas detalles sobre los requisitos?",
                        "Hay documentacion adicional que deba consultar?",
                    ],
                    priority=1,
                )
            )

        elif diagnosis.problem_type == ProblemType.OUT_OF_EXPERTISE:
            # Detectar dominio de la tarea
            relevant_agents = self._find_relevant_agents(task)
            recommendations.append(
                Recommendation(
                    action_type=ActionType.CONSULT_AGENT,
                    description="Consultar con agentes especializados",
                    agents_to_consult=relevant_agents[:3],
                    context_to_gather=["Estado actual del trabajo", "Punto especifico de bloqueo"],
                    questions_for_human=[],
                    priority=1,
                )
            )

        elif diagnosis.problem_type == ProblemType.DECISION_CONFLICT:
            recommendations.append(
                Recommendation(
                    action_type=ActionType.INITIATE_DEBATE,
                    description="Iniciar debate multi-agente para alcanzar consenso",
                    agents_to_consult=["architect", "critic", self._find_relevant_agents(task)[0]],
                    context_to_gather=["Opciones identificadas", "Pros y contras de cada una"],
                    questions_for_human=[
                        "Hay preferencias o restricciones que deba considerar?",
                        "Cual es el criterio mas importante para esta decision?",
                    ],
                    priority=1,
                )
            )

        elif diagnosis.problem_type == ProblemType.TECHNICAL_ERROR:
            recommendations.append(
                Recommendation(
                    action_type=ActionType.CONSULT_AGENT,
                    description="Consultar con debugger para resolver el error",
                    agents_to_consult=["debugger", "explorer"],
                    context_to_gather=[
                        "Stack trace completo",
                        "Estado del sistema",
                        "Logs recientes",
                    ],
                    questions_for_human=[],
                    priority=1,
                )
            )

        elif diagnosis.problem_type == ProblemType.TASK_TOO_LARGE:
            recommendations.append(
                Recommendation(
                    action_type=ActionType.DECOMPOSE_TASK,
                    description="Descomponer la tarea en subtareas manejables",
                    agents_to_consult=["planner", "architect"],
                    context_to_gather=["Objetivo final", "Restricciones conocidas"],
                    questions_for_human=["Hay un orden de prioridad para los componentes?"],
                    priority=1,
                )
            )

        elif diagnosis.problem_type == ProblemType.LOW_CONFIDENCE:
            recommendations.append(
                Recommendation(
                    action_type=ActionType.RETRY_WITH_HINTS,
                    description="Revisar y mejorar la respuesta con ayuda adicional",
                    agents_to_consult=["critic", "code-reviewer"],
                    context_to_gather=["Respuesta actual", "Puntos de duda especificos"],
                    questions_for_human=["La respuesta actual va en la direccion correcta?"],
                    priority=1,
                )
            )

        else:  # UNKNOWN
            recommendations.append(
                Recommendation(
                    action_type=ActionType.ESCALATE_HUMAN,
                    description="Escalar al humano para clarificacion",
                    agents_to_consult=[],
                    context_to_gather=["Todo el contexto disponible"],
                    questions_for_human=[
                        "Puedes describir el problema con mas detalle?",
                        "Que resultado esperas obtener?",
                        "Hay algo que haya intentado antes?",
                    ],
                    priority=1,
                )
            )

        return recommendations

    def _find_relevant_agents(self, task: str) -> list[str]:
        """Encontrar agentes relevantes para una tarea."""
        task_lower = task.lower()
        relevant = []

        for domain, agents in self.DOMAIN_AGENTS.items():
            if domain in task_lower:
                relevant.extend(agents)

        # Keywords especificas
        keyword_agents = {
            "react": ["react-specialist"],
            "api": ["api-designer", "backend-specialist"],
            "database": ["database-architect"],
            "test": ["test-engineer"],
            "deploy": ["devops-engineer"],
            "security": ["security-auditor"],
            "ui": ["ui-ux-designer"],
            "performance": ["performance-optimizer"],
        }

        for keyword, agents in keyword_agents.items():
            if keyword in task_lower:
                relevant.extend(agents)

        # Eliminar duplicados manteniendo orden
        seen = set()
        unique = []
        for agent in relevant:
            if agent not in seen:
                seen.add(agent)
                unique.append(agent)

        return unique if unique else ["explorer", "architect"]

    def suggest_agents(self, task: str) -> list[str]:
        """Sugerir agentes para una tarea."""
        return self._find_relevant_agents(task)

    def get_agent_help(self, agent_name: str) -> dict:
        """Obtener ayuda/info sobre un agente."""
        # En una impl real, esto buscaria en el registry
        return {
            "name": agent_name,
            "role": "Specialist",
            "capabilities": ["task-execution"],
            "how_to_use": f"Invocar {agent_name} con una tarea clara.",
        }

    def help(
        self, agent_name: str, problem: str, task: str = "", context: dict = None
    ) -> MentorResponse:
        """Proporcionar ayuda completa a un agente."""
        logger.info(f"Mentor ayudando a {agent_name}: {problem[:50]}...")

        context = context or {}

        # Diagnosticar
        diagnosis = self.diagnose(agent_name, problem, context)

        # Recomendar
        recommendations = self.recommend(diagnosis, task)

        # Determinar si escalar
        escalation_needed = (
            diagnosis.problem_type == ProblemType.UNKNOWN
            or diagnosis.confidence < 0.5
            or context.get("retry_count", 0) > 5
        )

        escalation_reason = None
        if escalation_needed:
            if diagnosis.problem_type == ProblemType.UNKNOWN:
                escalation_reason = "No se pudo diagnosticar el problema claramente"
            elif diagnosis.confidence < 0.5:
                escalation_reason = "Baja confianza en el diagnostico"
            else:
                escalation_reason = "Multiples intentos fallidos"

        # Seleccionar frase de animo
        import random

        encouragement = random.choice(self.ENCOURAGEMENTS)

        return MentorResponse(
            diagnosis=diagnosis,
            recommendations=recommendations,
            escalation_needed=escalation_needed,
            escalation_reason=escalation_reason,
            encouragement=encouragement,
        )


def main():
    """Entry point principal."""
    parser = argparse.ArgumentParser(description="Mentor Agent - Guia para otros agentes")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: help
    help_parser = subparsers.add_parser("help", help="Obtener ayuda para un agente")
    help_parser.add_argument("agent", help="Nombre del agente")
    help_parser.add_argument("problem", help="Descripcion del problema")
    help_parser.add_argument("--task", "-t", help="Tarea original", default="")
    help_parser.add_argument("--confidence", type=float, help="Confianza actual", default=1.0)
    help_parser.add_argument("--retries", type=int, help="Numero de reintentos", default=0)
    help_parser.add_argument("--json", action="store_true", help="Output en JSON")

    # Comando: suggest
    suggest_parser = subparsers.add_parser("suggest", help="Sugerir agentes para una tarea")
    suggest_parser.add_argument("task", help="Descripcion de la tarea")
    suggest_parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()

    mentor = MentorAgent()

    if args.command == "help":
        context = {"confidence": args.confidence, "retry_count": args.retries}

        response = mentor.help(args.agent, args.problem, args.task, context)

        if args.json:
            print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(response.to_markdown())

    elif args.command == "suggest":
        agents = mentor._find_relevant_agents(args.task)

        if args.json:
            print(json.dumps({"suggested_agents": agents}, indent=2))
        else:
            print("Agentes sugeridos para esta tarea:")
            for agent in agents:
                print(f"  - {agent}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
