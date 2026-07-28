#!/usr/bin/env python3
"""
Agent Teams - Peer-to-peer agent collaboration with message passing.

Enables agents to work as coordinated teams where members can:
1. Discover teammates and their capabilities
2. Send direct messages to specific teammates
3. Broadcast messages to the entire team
4. Delegate subtasks to specialized teammates
5. Build shared context through conversation threads
6. Reach consensus on decisions

Builds on existing infrastructure:
- DynamicTeamOrchestrator for team formation
- AgentMessenger for message routing
- AgentExecutor for actual execution

Usage:
    from .agent.core.agent_teams import TeamManager, spawn_team

    # Crear un equipo para una tarea
    manager = TeamManager()
    team = await manager.spawn_team(
        task="Crear API REST con autenticación OAuth",
        agents=["architect", "api-designer", "security-auditor", "coder"],
        lead="architect"
    )

    # Los agentes se comunican entre sí
    await team.send_message(
        from_agent="architect",
        to_agent="api-designer",
        content="Necesitamos endpoints RESTful para auth. ¿Puedes diseñar el contrato?"
    )

    # Broadcast a todo el equipo
    await team.broadcast(
        from_agent="architect",
        content="Decisión: usaremos JWT con refresh tokens"
    )

    # Ejecutar equipo completo
    result = await team.execute(task="Diseñar e implementar API REST con OAuth")
"""

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.agent_teams")

# Paths
AGENTS_DIR = Path(__file__).parent.parent / "agents"


# =============================================================================
# ENUMS
# =============================================================================


class TeamStatus(Enum):
    """Estado del equipo."""

    FORMING = "forming"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class MemberRole(Enum):
    """Roles dentro del equipo."""

    LEAD = "lead"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    SUPPORTER = "supporter"
    CRITIC = "critic"


class MessageType(Enum):
    """Tipos de mensaje entre agentes."""

    DIRECT = "direct"
    BROADCAST = "broadcast"
    DELEGATION = "delegation"
    RESULT = "result"
    CONSENSUS_REQUEST = "consensus_request"
    CONSENSUS_VOTE = "consensus_vote"
    STATUS_UPDATE = "status_update"
    HELP_REQUEST = "help_request"


class MessagePriority(Enum):
    """Prioridad de mensajes."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class TeamMessage:
    """Mensaje entre miembros del equipo."""

    id: str
    from_agent: str
    to_agent: str  # "*" para broadcast
    message_type: MessageType
    content: str
    priority: MessagePriority = MessagePriority.NORMAL
    thread_id: str | None = None
    reply_to: str | None = None
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Serializa el mensaje."""
        result = asdict(self)
        result["message_type"] = self.message_type.value
        result["priority"] = self.priority.value
        return result


@dataclass
class Teammate:
    """Un miembro del equipo con sus capacidades."""

    name: str
    role: MemberRole
    description: str = ""
    skills: list[str] = field(default_factory=list)
    status: str = "ready"  # ready, working, waiting, done, error
    has_executable: bool = False

    def to_dict(self) -> dict:
        """Serializa el teammate."""
        return {
            "name": self.name,
            "role": self.role.value,
            "description": self.description,
            "skills": self.skills,
            "status": self.status,
            "has_executable": self.has_executable,
        }


@dataclass
class ConsensusRequest:
    """Solicitud de consenso al equipo."""

    id: str
    topic: str
    options: list[str]
    initiator: str
    votes: dict = field(default_factory=dict)  # agent -> option
    reasoning: dict = field(default_factory=dict)  # agent -> reasoning
    deadline_seconds: int = 60
    result: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class TeamExecutionResult:
    """Resultado de la ejecución del equipo."""

    team_id: str
    task: str
    success: bool
    outputs: dict  # agent_name -> output
    messages_exchanged: int
    consensus_decisions: list[dict]
    execution_time_ms: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializa el resultado."""
        return asdict(self)


# =============================================================================
# AGENT TEAM
# =============================================================================


class AgentTeam:
    """
    Un equipo de agentes que colaboran en una tarea.

    Proporciona:
    - Comunicación peer-to-peer entre miembros
    - Broadcast a todo el equipo
    - Delegación de subtareas
    - Consenso para decisiones
    - Ejecución coordinada

    Usage:
        team = AgentTeam(
            name="auth-team",
            task="Implementar autenticación OAuth",
            members=[
                Teammate(name="architect", role=MemberRole.LEAD),
                Teammate(name="api-designer", role=MemberRole.SPECIALIST),
                Teammate(name="security-auditor", role=MemberRole.REVIEWER),
            ]
        )

        # Enviar mensaje directo
        await team.send_message("architect", "api-designer", "Diseña los endpoints")

        # Ejecutar equipo
        result = await team.execute()
    """

    def __init__(
        self,
        name: str,
        task: str,
        members: list[Teammate],
        lead: str | None = None,
        agents_dir: Path | None = None,
    ) -> None:
        self.id = hashlib.md5(
            f"{name}-{datetime.now().isoformat()}".encode(), usedforsecurity=False
        ).hexdigest()[:12]
        self.name = name
        self.task = task
        self.members = {m.name: m for m in members}
        self.lead = lead or (members[0].name if members else None)
        self.agents_dir = agents_dir or AGENTS_DIR
        self.status = TeamStatus.FORMING

        # Comunicación
        self._messages: list[TeamMessage] = []
        self._message_handlers: dict[str, list[Callable]] = {}
        self._consensus_requests: list[ConsensusRequest] = []

        # Resultados
        self._outputs: dict[str, str] = {}
        self._errors: list[str] = []

        logger.info("Equipo '%s' creado con %d miembros", name, len(members))

    # -------------------------------------------------------------------------
    # Descubrimiento de teammates
    # -------------------------------------------------------------------------

    def get_teammates(self, for_agent: str | None = None) -> list[dict]:
        """
        Lista los miembros del equipo (TeammateTool).

        Args:
            for_agent: Si se especifica, excluye a este agente de la lista.

        Returns:
            Lista de teammates con sus roles y capacidades.
        """
        teammates = []
        for name, member in self.members.items():
            if for_agent and name == for_agent:
                continue
            teammates.append(member.to_dict())
        return teammates

    def get_teammate(self, name: str) -> Teammate | None:
        """Obtiene un miembro específico del equipo."""
        return self.members.get(name)

    # -------------------------------------------------------------------------
    # Comunicación peer-to-peer (SendMessage)
    # -------------------------------------------------------------------------

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        message_type: MessageType = MessageType.DIRECT,
        priority: MessagePriority = MessagePriority.NORMAL,
        thread_id: str | None = None,
        reply_to: str | None = None,
        metadata: dict | None = None,
    ) -> TeamMessage:
        """
        Envía un mensaje directo de un agente a otro.

        Args:
            from_agent: Agente que envía el mensaje.
            to_agent: Agente destinatario.
            content: Contenido del mensaje.
            message_type: Tipo de mensaje.
            priority: Prioridad del mensaje.
            thread_id: ID del hilo de conversación (para threading).
            reply_to: ID del mensaje al que responde.
            metadata: Datos adicionales.

        Returns:
            El mensaje creado.

        Raises:
            ValueError: Si el agente no es miembro del equipo.
        """
        if from_agent not in self.members:
            raise ValueError(f"'{from_agent}' no es miembro del equipo '{self.name}'")
        if to_agent != "*" and to_agent not in self.members:
            raise ValueError(f"'{to_agent}' no es miembro del equipo '{self.name}'")

        msg = TeamMessage(
            id=str(uuid.uuid4())[:8],
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            priority=priority,
            thread_id=thread_id or str(uuid.uuid4())[:8],
            reply_to=reply_to,
            metadata=metadata or {},
        )

        self._messages.append(msg)

        # Notificar handlers registrados
        if to_agent in self._message_handlers:
            for handler in self._message_handlers[to_agent]:
                try:
                    await handler(msg)
                except Exception as e:
                    logger.warning("Error en handler de mensajes para '%s': %s", to_agent, e)

        logger.info(
            "[%s] %s → %s: %s",
            self.name,
            from_agent,
            to_agent,
            content[:80],
        )

        return msg

    async def broadcast(
        self,
        from_agent: str,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: dict | None = None,
    ) -> TeamMessage:
        """
        Envía un mensaje a todos los miembros del equipo.

        Args:
            from_agent: Agente que envía.
            content: Contenido del mensaje.
            priority: Prioridad.
            metadata: Datos adicionales.

        Returns:
            El mensaje de broadcast.
        """
        return await self.send_message(
            from_agent=from_agent,
            to_agent="*",
            content=content,
            message_type=MessageType.BROADCAST,
            priority=priority,
            metadata=metadata,
        )

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        subtask: str,
        context: dict | None = None,
    ) -> TeamMessage:
        """
        Delega una subtarea a un compañero de equipo.

        Args:
            from_agent: Agente que delega.
            to_agent: Agente que recibe la delegación.
            subtask: Descripción de la subtarea.
            context: Contexto adicional.

        Returns:
            El mensaje de delegación.
        """
        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            content=subtask,
            message_type=MessageType.DELEGATION,
            priority=MessagePriority.HIGH,
            metadata={"context": context or {}, "type": "delegation"},
        )

    def register_handler(self, agent_name: str, handler: Callable) -> None:
        """Registra un handler de mensajes para un agente."""
        if agent_name not in self._message_handlers:
            self._message_handlers[agent_name] = []
        self._message_handlers[agent_name].append(handler)

    def get_messages(
        self,
        for_agent: str | None = None,
        message_type: MessageType | None = None,
        thread_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Obtiene mensajes del equipo.

        Args:
            for_agent: Filtra mensajes dirigidos a este agente (o broadcasts).
            message_type: Filtra por tipo de mensaje.
            thread_id: Filtra por hilo de conversación.
            limit: Número máximo de mensajes.

        Returns:
            Lista de mensajes serializados.
        """
        filtered = self._messages

        if for_agent:
            filtered = [
                m
                for m in filtered
                if m.to_agent == for_agent or m.to_agent == "*" or m.from_agent == for_agent
            ]

        if message_type:
            filtered = [m for m in filtered if m.message_type == message_type]

        if thread_id:
            filtered = [m for m in filtered if m.thread_id == thread_id]

        return [m.to_dict() for m in filtered[-limit:]]

    def get_conversation_summary(self) -> str:
        """Genera un resumen de la conversación del equipo."""
        if not self._messages:
            return "No hay mensajes intercambiados."

        summary = f"## Conversación del equipo '{self.name}'\n\n"
        summary += f"**Tarea:** {self.task}\n"
        summary += f"**Mensajes:** {len(self._messages)}\n"
        summary += f"**Miembros:** {', '.join(self.members.keys())}\n\n"

        for msg in self._messages[-20:]:
            target = "todos" if msg.to_agent == "*" else msg.to_agent
            icon = {
                MessageType.DIRECT: "",
                MessageType.BROADCAST: "[BROADCAST]",
                MessageType.DELEGATION: "[DELEGACION]",
                MessageType.RESULT: "[RESULTADO]",
                MessageType.CONSENSUS_REQUEST: "[CONSENSO]",
                MessageType.HELP_REQUEST: "[AYUDA]",
            }.get(msg.message_type, "")
            summary += f"- **{msg.from_agent}** → **{target}** {icon}: {msg.content[:100]}\n"

        return summary

    # -------------------------------------------------------------------------
    # Consenso
    # -------------------------------------------------------------------------

    async def request_consensus(
        self,
        initiator: str,
        topic: str,
        options: list[str],
        deadline_seconds: int = 60,
    ) -> ConsensusRequest:
        """
        Solicita consenso del equipo sobre una decisión.

        Args:
            initiator: Agente que inicia la votación.
            topic: Tema de la decisión.
            options: Opciones disponibles.
            deadline_seconds: Tiempo límite para votar.

        Returns:
            La solicitud de consenso creada.
        """
        consensus = ConsensusRequest(
            id=str(uuid.uuid4())[:8],
            topic=topic,
            options=options,
            initiator=initiator,
            deadline_seconds=deadline_seconds,
        )
        self._consensus_requests.append(consensus)

        # Notificar a todos
        await self.broadcast(
            from_agent=initiator,
            content=f"[CONSENSO] {topic}\nOpciones: {', '.join(options)}",
            priority=MessagePriority.HIGH,
            metadata={"consensus_id": consensus.id, "options": options},
        )

        return consensus

    async def vote(
        self,
        consensus_id: str,
        agent_name: str,
        option: str,
        reasoning: str = "",
    ) -> bool:
        """
        Registra un voto de un agente.

        Args:
            consensus_id: ID de la solicitud de consenso.
            agent_name: Agente que vota.
            option: Opción elegida.
            reasoning: Razonamiento del voto.

        Returns:
            True si el voto fue registrado correctamente.
        """
        for consensus in self._consensus_requests:
            if consensus.id == consensus_id:
                if option not in consensus.options:
                    logger.warning("Opción '%s' no válida para consenso '%s'", option, consensus_id)
                    return False
                consensus.votes[agent_name] = option
                consensus.reasoning[agent_name] = reasoning
                logger.info(
                    "[%s] %s votó '%s' en consenso '%s'",
                    self.name,
                    agent_name,
                    option,
                    consensus.topic[:30],
                )
                return True
        return False

    def resolve_consensus(self, consensus_id: str) -> str | None:
        """
        Resuelve un consenso basándose en los votos.

        Returns:
            La opción ganadora, o None si no hay consenso.
        """
        for consensus in self._consensus_requests:
            if consensus.id == consensus_id:
                if not consensus.votes:
                    return None

                # Contar votos
                vote_counts: dict[str, int] = {}
                for option in consensus.votes.values():
                    vote_counts[option] = vote_counts.get(option, 0) + 1

                # Mayoría simple
                winner = max(vote_counts, key=lambda k: vote_counts[k])
                total_votes = sum(vote_counts.values())
                if vote_counts[winner] > total_votes / 2:
                    consensus.result = winner
                    return winner

                # Sin mayoría: el lead decide
                if self.lead and self.lead in consensus.votes:
                    consensus.result = consensus.votes[self.lead]
                    return consensus.result

                # Opción más votada
                consensus.result = winner
                return winner
        return None

    # -------------------------------------------------------------------------
    # Ejecución de agentes
    # -------------------------------------------------------------------------

    def _find_agent_script(self, agent_name: str) -> Path | None:
        """Busca el script ejecutable de un agente."""
        agent_dir = self.agents_dir / agent_name
        if not agent_dir.exists():
            return None

        scripts_dir = agent_dir / "scripts"
        if not scripts_dir.exists():
            return None

        # Buscar script por convención de nombres
        name_variants = [
            agent_name.replace("-", "_"),
            "main",
            agent_name,
        ]

        for name in name_variants:
            for ext in [".py", ".sh", ".js"]:
                script = scripts_dir / f"{name}{ext}"
                if script.exists():
                    return script

        return None

    def _get_agent_identity(self, agent_name: str) -> str:
        """Lee la identidad de un agente."""
        identity_file = self.agents_dir / agent_name / "IDENTITY.md"
        if identity_file.exists():
            return identity_file.read_text(encoding="utf-8")
        return f"Agente: {agent_name}"

    async def _execute_single_agent(
        self,
        agent_name: str,
        task: str,
        context: str = "",
        timeout: int = 120,
    ) -> dict:
        """
        Ejecuta un agente individual con contexto del equipo.

        Args:
            agent_name: Nombre del agente.
            task: Tarea a ejecutar.
            context: Contexto del equipo (mensajes previos).
            timeout: Timeout en segundos.

        Returns:
            Resultado de la ejecución.
        """
        start = datetime.now()
        member = self.members.get(agent_name)
        if member:
            member.status = "working"

        script = self._find_agent_script(agent_name)

        # Construir prompt con contexto del equipo
        team_context = self.get_conversation_summary() if self._messages else ""
        full_task = task
        if team_context:
            full_task = f"{task}\n\n## Contexto del equipo\n{team_context}"
        if context:
            full_task = f"{full_task}\n\n## Contexto adicional\n{context}"

        result = {
            "agent": agent_name,
            "task": task,
            "success": False,
            "output": "",
            "mode": "guidance",
            "execution_time_ms": 0,
        }

        if script:
            try:
                cmd = ["python", str(script), full_task]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                result["output"] = stdout.decode("utf-8", errors="replace")
                result["success"] = proc.returncode == 0
                result["mode"] = "script"
                if stderr:
                    result["stderr"] = stderr.decode("utf-8", errors="replace")
            except TimeoutError:
                result["output"] = f"Timeout después de {timeout}s"
                result["success"] = False
            except Exception as e:
                result["output"] = str(e)
                result["success"] = False
        else:
            # Modo guidance: retorna identidad + tarea
            identity = self._get_agent_identity(agent_name)
            result["output"] = f"[Modo Guidance]\n\nIdentidad:\n{identity}\n\nTarea:\n{full_task}"
            result["success"] = True
            result["mode"] = "guidance"

        elapsed = (datetime.now() - start).total_seconds() * 1000
        result["execution_time_ms"] = int(elapsed)

        if member:
            member.status = "done" if result["success"] else "error"

        self._outputs[agent_name] = result["output"]  # type: ignore[assignment]  # dict value type mismatch: runtime-validated

        # Notificar resultado al equipo
        await self.send_message(
            from_agent=agent_name,
            to_agent="*",
            content=f"Completé mi tarea: {task[:80]}",
            message_type=MessageType.RESULT,
            metadata={"success": result["success"], "mode": result["mode"]},
        )

        return result

    async def execute(
        self,
        task: str | None = None,
        parallel: bool = True,
        timeout_per_agent: int = 120,
    ) -> TeamExecutionResult:
        """
        Ejecuta la tarea del equipo completo.

        El lead ejecuta primero, luego los especialistas en paralelo,
        y finalmente los reviewers.

        Args:
            task: Tarea a ejecutar (usa self.task si no se especifica).
            parallel: Si True, ejecuta agentes del mismo rol en paralelo.
            timeout_per_agent: Timeout por agente en segundos.

        Returns:
            Resultado de la ejecución del equipo.
        """
        task = task or self.task
        self.status = TeamStatus.EXECUTING
        start = datetime.now()

        logger.info("Equipo '%s' ejecutando: %s", self.name, task[:80])

        # Broadcast inicio
        if self.lead:
            await self.broadcast(
                from_agent=self.lead,
                content=f"Inicio de ejecución del equipo. Tarea: {task}",
                priority=MessagePriority.HIGH,
            )

        # Agrupar por rol para ejecución ordenada
        role_order = [
            MemberRole.LEAD,
            MemberRole.SPECIALIST,
            MemberRole.SUPPORTER,
            MemberRole.CRITIC,
            MemberRole.REVIEWER,
        ]

        all_results: dict[str, dict] = {}

        for role in role_order:
            agents_in_role = [name for name, m in self.members.items() if m.role == role]

            if not agents_in_role:
                continue

            if parallel and len(agents_in_role) > 1:
                # Ejecutar en paralelo dentro del mismo rol
                tasks = [
                    self._execute_single_agent(name, task, timeout=timeout_per_agent)
                    for name in agents_in_role
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for name, res in zip(agents_in_role, results, strict=True):
                    if isinstance(res, Exception):
                        all_results[name] = {
                            "agent": name,
                            "success": False,
                            "output": str(res),
                        }
                        self._errors.append(f"{name}: {res}")
                    else:
                        all_results[name] = res  # type: ignore[assignment]  # dict value type mismatch: runtime-validated
            else:
                # Ejecutar secuencialmente
                for name in agents_in_role:
                    try:
                        res = await self._execute_single_agent(
                            name, task, timeout=timeout_per_agent
                        )
                        all_results[name] = res
                    except Exception as e:
                        all_results[name] = {
                            "agent": name,
                            "success": False,
                            "output": str(e),
                        }
                        self._errors.append(f"{name}: {e}")

        elapsed = (datetime.now() - start).total_seconds() * 1000
        all_succeeded = all(r.get("success", False) for r in all_results.values())

        self.status = TeamStatus.COMPLETED if all_succeeded else TeamStatus.FAILED

        return TeamExecutionResult(
            team_id=self.id,
            task=task,
            success=all_succeeded,
            outputs={name: r.get("output", "") for name, r in all_results.items()},
            messages_exchanged=len(self._messages),
            consensus_decisions=[
                {
                    "topic": c.topic,
                    "result": c.result,
                    "votes": c.votes,
                }
                for c in self._consensus_requests
            ],
            execution_time_ms=int(elapsed),
            errors=self._errors,
        )


# =============================================================================
# TEAM MANAGER
# =============================================================================


class TeamManager:
    """
    Gestor de equipos de agentes.

    Proporciona funciones de alto nivel para crear, gestionar
    y ejecutar equipos de agentes.

    Usage:
        manager = TeamManager()

        # Crear equipo
        team = await manager.spawn_team(
            task="Auditar seguridad del módulo de auth",
            agents=["security-auditor", "code-reviewer", "architect"],
            lead="security-auditor",
        )

        # Ejecutar
        result = await team.execute()

        # O auto-seleccionar agentes
        team = await manager.auto_team(
            task="Crear feature de notificaciones push"
        )
    """

    # Mapeo de palabras clave a agentes recomendados
    TASK_AGENT_MAP: dict[str, list[str]] = {
        "security": ["security-auditor", "penetration-tester", "code-reviewer"],
        "api": ["api-designer", "backend-specialist", "api-gateway-specialist"],
        "frontend": ["frontend-specialist", "react-specialist", "ui-ux-designer"],
        "backend": ["backend-specialist", "api-designer", "database-architect"],
        "database": ["database-architect", "data-engineer", "backend-specialist"],
        "testing": ["test-engineer", "code-reviewer", "regression-detector"],
        "performance": ["performance-optimizer", "load-testing-engineer", "backend-specialist"],
        "devops": ["devops-engineer", "infrastructure-architect", "observability-engineer"],
        "ui": ["ui-ux-designer", "frontend-specialist", "design-system-architect"],
        "auth": ["security-auditor", "backend-specialist", "api-designer"],
        "mobile": ["mobile-developer", "ui-ux-designer", "frontend-specialist"],
        "migration": ["migrator", "database-architect", "backend-specialist"],
        "refactor": ["refactor", "code-reviewer", "architect"],
        "documentation": ["docs-specialist", "documentation-writer", "content-improver"],
        "design": ["architect", "api-designer", "ui-ux-designer"],
    }

    def __init__(self, agents_dir: Path | None = None) -> None:
        self.agents_dir = agents_dir or AGENTS_DIR
        self._teams: dict[str, AgentTeam] = {}

    def _discover_agent_info(self, agent_name: str) -> Teammate:
        """Descubre información de un agente desde su IDENTITY.md."""
        agent_dir = self.agents_dir / agent_name
        identity_file = agent_dir / "IDENTITY.md"

        description = ""
        skills: list[str] = []
        has_executable = False

        if identity_file.exists():
            content = identity_file.read_text(encoding="utf-8")
            # Extraer primera línea como descripción
            lines = content.strip().split("\n")
            for line in lines:
                if line.startswith("# "):
                    description = line.lstrip("# ").strip()
                    break
            if not description and lines:
                description = lines[0][:100]

            # Detectar skills del contenido
            content_lower = content.lower()
            skill_keywords = [
                "security",
                "api",
                "frontend",
                "backend",
                "database",
                "testing",
                "performance",
                "devops",
                "design",
                "mobile",
            ]
            skills = [kw for kw in skill_keywords if kw in content_lower]

        # Verificar si tiene script ejecutable
        scripts_dir = agent_dir / "scripts"
        if scripts_dir.exists():
            for f in scripts_dir.iterdir():
                if f.suffix in [".py", ".sh", ".js"]:
                    has_executable = True
                    break

        return Teammate(
            name=agent_name,
            role=MemberRole.SPECIALIST,
            description=description,
            skills=skills,
            has_executable=has_executable,
        )

    async def spawn_team(
        self,
        task: str,
        agents: list[str],
        lead: str | None = None,
        name: str | None = None,
        roles: dict[str, MemberRole] | None = None,
    ) -> AgentTeam:
        """
        Crea un equipo con agentes específicos (spawnTeam).

        Args:
            task: Tarea del equipo.
            agents: Lista de nombres de agentes.
            lead: Agente líder (si no se especifica, usa el primero).
            name: Nombre del equipo (auto-generado si no se especifica).
            roles: Roles específicos para cada agente.

        Returns:
            El equipo creado y listo para ejecutar.
        """
        roles = roles or {}
        team_name = (
            name or f"team-{hashlib.md5(task.encode(), usedforsecurity=False).hexdigest()[:6]}"
        )

        members = []
        for agent_name in agents:
            teammate = self._discover_agent_info(agent_name)

            # Asignar rol
            if agent_name in roles:
                teammate.role = roles[agent_name]
            elif agent_name == lead:
                teammate.role = MemberRole.LEAD
            elif "review" in agent_name or "critic" in agent_name:
                teammate.role = MemberRole.REVIEWER
            elif "audit" in agent_name:
                teammate.role = MemberRole.CRITIC

            members.append(teammate)

        team = AgentTeam(
            name=team_name,
            task=task,
            members=members,
            lead=lead or agents[0],
            agents_dir=self.agents_dir,
        )
        team.status = TeamStatus.READY

        self._teams[team.id] = team
        logger.info(
            "Equipo '%s' creado: %s (lead=%s)",
            team_name,
            [m.name for m in members],
            team.lead,
        )

        return team

    async def auto_team(
        self,
        task: str,
        max_agents: int = 4,
        name: str | None = None,
    ) -> AgentTeam:
        """
        Crea un equipo auto-seleccionando agentes según la tarea.

        Analiza la tarea para detectar dominios y selecciona
        los agentes más relevantes.

        Args:
            task: Descripción de la tarea.
            max_agents: Número máximo de agentes.
            name: Nombre del equipo.

        Returns:
            El equipo creado con agentes auto-seleccionados.
        """
        task_lower = task.lower()

        # Puntuar agentes por relevancia
        agent_scores: dict[str, float] = {}
        for keyword, recommended_agents in self.TASK_AGENT_MAP.items():
            if keyword in task_lower:
                for i, agent in enumerate(recommended_agents):
                    # Verificar que el agente existe
                    agent_dir = self.agents_dir / agent
                    if agent_dir.exists():
                        score = (len(recommended_agents) - i) / len(recommended_agents)
                        agent_scores[agent] = agent_scores.get(agent, 0) + score

        # Siempre incluir architect si es una tarea compleja
        complex_keywords = ["crear", "implementar", "diseñar", "build", "create", "design"]
        if any(kw in task_lower for kw in complex_keywords):
            if (self.agents_dir / "architect").exists():
                agent_scores["architect"] = agent_scores.get("architect", 0) + 0.5

        # Seleccionar top agentes
        sorted_agents = sorted(agent_scores, key=lambda a: agent_scores[a], reverse=True)
        selected = sorted_agents[:max_agents]

        if not selected:
            # Fallback: equipo genérico
            fallback = ["architect", "coder", "code-reviewer"]
            selected = [a for a in fallback if (self.agents_dir / a).exists()][:max_agents]

        # El más relevante es el lead
        lead = selected[0] if selected else None

        return await self.spawn_team(
            task=task,
            agents=selected,
            lead=lead,
            name=name,
        )

    def get_team(self, team_id: str) -> AgentTeam | None:
        """Obtiene un equipo por su ID."""
        return self._teams.get(team_id)

    def list_teams(self) -> list[dict]:
        """Lista todos los equipos activos."""
        return [
            {
                "id": team.id,
                "name": team.name,
                "task": team.task[:80],
                "status": team.status.value,
                "members": list(team.members.keys()),
                "messages": len(team._messages),
            }
            for team in self._teams.values()
        ]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Singleton del TeamManager
_manager: TeamManager | None = None


def get_team_manager(agents_dir: Path | None = None) -> TeamManager:
    """Obtiene la instancia singleton del TeamManager."""
    global _manager
    if _manager is None:
        _manager = TeamManager(agents_dir=agents_dir)
    return _manager


async def spawn_team(
    task: str,
    agents: list[str],
    lead: str | None = None,
    **kwargs: Any,
) -> AgentTeam:
    """
    Función de conveniencia para crear un equipo.

    Usage:
        team = await spawn_team(
            task="Crear API de autenticación",
            agents=["architect", "api-designer", "security-auditor"],
            lead="architect",
        )
        result = await team.execute()
    """
    manager = get_team_manager()
    return await manager.spawn_team(task=task, agents=agents, lead=lead, **kwargs)


async def auto_team(task: str, max_agents: int = 4) -> AgentTeam:
    """
    Función de conveniencia para crear un equipo auto-seleccionado.

    Usage:
        team = await auto_team("Auditar seguridad del módulo de pagos")
        result = await team.execute()
    """
    manager = get_team_manager()
    return await manager.auto_team(task=task, max_agents=max_agents)


# =============================================================================
# TASK LIST — Sistema de tareas compartidas con file locking
# Inspirado en la arquitectura de equipos de Claude Code.
# =============================================================================

TEAMS_ROOT = Path.home() / ".antigravity" / "teams"


class TaskStatus(str, Enum):
    """Estado de una tarea en el equipo."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class TeamTask:
    """Una tarea dentro del equipo con tracking de estado."""

    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assignee: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    updated_at: str | None = None
    completed_at: str | None = None
    priority: int = 0  # 0=low, 1=medium, 2=high

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assignee": self.assignee,
            "blocked_by": self.blocked_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamTask":
        status_val = data.get("status", "pending")
        status = TaskStatus(status_val) if isinstance(status_val, str) else status_val
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=status,
            assignee=data.get("assignee"),
            blocked_by=data.get("blocked_by", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at"),
            completed_at=data.get("completed_at"),
            priority=data.get("priority", 0),
        )


@dataclass
class TeamFileLock:
    """Representa un lock sobre un archivo."""

    file_path: str
    agent_id: str
    task_id: str
    acquired_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass
class TeamEvent:
    """Un evento en el log del equipo."""

    timestamp: str
    event_type: str
    agent_id: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "payload": self.payload,
        }


class TaskListTeam:
    """Equipo basado en task list compartida con file locking.

    Extiende AgentTeam con:
    - Task list compartida (pending/in-progress/completed/blocked)
    - File locking para prevenir race conditions
    - Self-claim cuando un teammate termina una tarea
    - El lead solo orquesta, no ejecuta

    Usage:
        from antigravity.sdk.client import Client
        client = Client()

        team = TaskListTeam(name="auth-team", lead="architect")
        team.add_member("coder")
        team.add_member("reviewer")

        task = team.add_task(
            title="Implementar endpoint /login",
            description="POST /api/auth/login con JWT",
            blocked_by=[],
            priority=2,
        )

        team.claim_task(task.id, "coder")
        team.acquire_lock(".env", "coder", task.id)

        team.complete_task(task.id)  # auto-claims next pending task
    """

    def __init__(
        self,
        name: str,
        lead: str,
        members: list[str] | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        self.name = name
        self.lead = lead
        self.members: list[str] = members or []
        self.tasks: list[TeamTask] = []
        self.file_locks: dict[str, TeamFileLock] = {}
        self._created_at = datetime.now().isoformat()

        if storage_dir is None:
            storage_dir = TEAMS_ROOT / self.name
        self._storage_dir = storage_dir
        self._state_file = storage_dir / "state.json"
        self._log_file = storage_dir / "log.jsonl"
        storage_dir.mkdir(parents=True, exist_ok=True)

        self._load()

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        """Carga estado desde state.json."""
        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            self.members = data.get("members", [])
            self.tasks = [TeamTask.from_dict(t) for t in data.get("tasks", [])]
            locks_raw = data.get("file_locks", {})
            self.file_locks = {
                path: TeamFileLock(**lock_data)
                for path, lock_data in locks_raw.items()
            }
            self._created_at = data.get("created_at", self._created_at)
        except Exception as e:
            logger.warning("Failed to load task team state: %s", e)

    def save(self) -> None:
        """Guarda estado en state.json."""
        data = {
            "name": self.name,
            "lead": self.lead,
            "created_at": self._created_at,
            "members": self.members,
            "tasks": [t.to_dict() for t in self.tasks],
            "file_locks": {path: asdict(lock) for path, lock in self.file_locks.items()},
        }
        self._state_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _log(self, event_type: str, agent_id: str, payload: dict) -> None:
        """Escribe un evento en log.jsonl."""
        event = TeamEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            agent_id=agent_id,
            payload=payload,
        )
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------------
    # Member management
    # -------------------------------------------------------------------------

    def add_member(self, agent_id: str) -> bool:
        """Agrega un miembro al equipo."""
        if agent_id in self.members or agent_id == self.lead:
            return False
        self.members.append(agent_id)
        self._log("member_added", "system", {"agent_id": agent_id})
        self.save()
        return True

    def remove_member(self, agent_id: str) -> bool:
        """Remueve un miembro y libera sus locks."""
        if agent_id not in self.members:
            return False
        self.members.remove(agent_id)
        for path, lock in list(self.file_locks.items()):
            if lock.agent_id == agent_id:
                self.file_locks.pop(path)
        self._log("member_removed", "system", {"agent_id": agent_id})
        self.save()
        return True

    # -------------------------------------------------------------------------
    # Task management
    # -------------------------------------------------------------------------

    def add_task(
        self,
        title: str,
        description: str = "",
        blocked_by: list[str] | None = None,
        priority: int = 0,
    ) -> TeamTask:
        """Agrega una tarea al backlog del equipo."""
        task_id = str(uuid.uuid4())[:8]
        task = TeamTask(
            id=task_id,
            title=title,
            description=description,
            blocked_by=blocked_by or [],
            priority=priority,
        )
        self.tasks.append(task)
        self._log("task_added", self.lead, {"task_id": task_id, "title": title})
        self.save()
        return task

    def claim_task(self, task_id: str, agent_id: str) -> bool:
        """Reclama una tarea. Devuelve True si fue asignada."""
        task = self._find_task(task_id)
        if task is None:
            return False
        # Only reject if another agent already owns this task
        if task.assignee is not None and task.assignee != agent_id:
            return False
        # Pre-assign blocked tasks (unblock when blocker completes)
        task.assignee = agent_id
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now().isoformat()
        self._log(
            "task_claimed",
            agent_id,
            {"task_id": task_id, "title": task.title},
        )
        self.save()
        return True

    def complete_task(self, task_id: str) -> bool:
        """Marca tarea como completada y libera locks."""
        task = self._find_task(task_id)
        if task is None:
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now().isoformat()
        task.updated_at = task.completed_at

        # Release locks held for this task
        for path, lock in list(self.file_locks.items()):
            if lock.task_id == task_id:
                self.file_locks.pop(path)

        self._log(
            "task_completed",
            task.assignee or "unknown",
            {"task_id": task_id, "title": task.title},
        )
        self.save()

        # Self-claim: auto-buscar proxima tarea
        self._auto_claim_next(task.assignee or "unknown")
        return True

    def block_task(self, task_id: str, reason: str = "") -> bool:
        """Bloquea una tarea."""
        task = self._find_task(task_id)
        if task is None:
            return False
        task.status = TaskStatus.BLOCKED
        task.updated_at = datetime.now().isoformat()
        self._log(
            "task_blocked",
            task.assignee or "unknown",
            {"task_id": task_id, "reason": reason},
        )
        self.save()
        return True

    def unblock_task(self, task_id: str) -> bool:
        """Desbloquea una tarea."""
        task = self._find_task(task_id)
        if task is None:
            return False
        task.status = TaskStatus.PENDING
        task.assignee = None
        task.updated_at = datetime.now().isoformat()
        self._log("task_unblocked", "system", {"task_id": task_id})
        self.save()
        return True

    # -------------------------------------------------------------------------
    # File locking
    # -------------------------------------------------------------------------

    def acquire_lock(
        self,
        file_path: str,
        agent_id: str,
        task_id: str,
    ) -> tuple[bool, str]:
        """Pide lock sobre un archivo. Devuelve (success, message)."""
        if file_path in self.file_locks:
            existing = self.file_locks[file_path]
            if existing.agent_id == agent_id:
                return True, "already_held"
            return False, f"held_by:{existing.agent_id}"

        self.file_locks[file_path] = TeamFileLock(
            file_path=file_path,
            agent_id=agent_id,
            task_id=task_id,
        )
        self._log(
            "lock_acquired",
            agent_id,
            {"file_path": file_path, "task_id": task_id},
        )
        self.save()
        return True, "acquired"

    def release_lock(self, file_path: str) -> bool:
        """Libera un lock de archivo."""
        if file_path not in self.file_locks:
            return False
        lock = self.file_locks.pop(file_path)
        self._log(
            "lock_released",
            "system",
            {"file_path": file_path, "was_held_by": lock.agent_id},
        )
        self.save()
        return True

    def get_lock_holder(self, file_path: str) -> str | None:
        """Devuelve el agent_id que tiene lock, o None."""
        lock = self.file_locks.get(file_path)
        return lock.agent_id if lock else None

    # -------------------------------------------------------------------------
    # Self-claim
    # -------------------------------------------------------------------------

    def _auto_claim_next(self, agent_id: str) -> bool:
        """Auto-claim la proxima tarea libre para el mismo agente.

        Solo reclama tareas que ya estaban pending para este agente
        (que no fueron bloqueadas por una dependencia).
        Las tareas desbloqueadas por completitud de otra tarea
        se quedan en pending para que el lead las reasigne.
        """
        if agent_id not in self.members:
            return False
        # Only auto-claim tasks that were already assigned to this agent
        # (i.e. previously claimed, became available)
        owned = [
            t for t in self.tasks
            if t.assignee == agent_id
            and t.status == TaskStatus.PENDING
            and not self._is_blocked(t)
        ]
        if owned:
            owned.sort(key=lambda t: (-t.priority, t.created_at))
            return self.claim_task(owned[0].id, agent_id)
        return False

    # -------------------------------------------------------------------------
    # Status / reporting
    # -------------------------------------------------------------------------

    def status(self) -> dict:
        """Estado completo del equipo para display."""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        progress = (completed / total * 100) if total > 0 else 0.0

        return {
            "name": self.name,
            "lead": self.lead,
            "members": self.members,
            "stats": {
                "total": total,
                "completed": completed,
                "in_progress": sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS),
                "pending": sum(1 for t in self.tasks if t.status == TaskStatus.PENDING),
                "blocked": sum(1 for t in self.tasks if t.status == TaskStatus.BLOCKED),
                "progress_pct": round(progress, 1),
            },
            "tasks_by_status": {
                s.value: [t.to_dict() for t in self.tasks if t.status == s]
                for s in TaskStatus
            },
            "file_locks": {
                path: asdict(lock) for path, lock in self.file_locks.items()
            },
        }

    def tasks_for_agent(self, agent_id: str) -> list[TeamTask]:
        """Tareas asignadas a un agente especifico."""
        return [t for t in self.tasks if t.assignee == agent_id]

    def next_pending(self) -> TeamTask | None:
        """Proxima tarea disponible para reclamar."""
        available = [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING and not self._is_blocked(t)
        ]
        if not available:
            return None
        available.sort(key=lambda t: (-t.priority, t.created_at))
        return available[0]

    def _find_task(self, task_id: str) -> TeamTask | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def _is_blocked(self, task: TeamTask) -> bool:
        for blocked_id in task.blocked_by:
            blocker = self._find_task(blocked_id)
            if blocker and blocker.status != TaskStatus.COMPLETED:
                return True
        return False


class TaskListManager:
    """Gestor global de TaskListTeam. Factory y registry."""

    def __init__(self, teams_root: Path | None = None) -> None:
        self._teams_root = teams_root or TEAMS_ROOT
        self._teams_root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, TaskListTeam] = {}

    def create_team(self, name: str, lead: str) -> TaskListTeam:
        """Crea un nuevo equipo o devuelve el existente."""
        if name in self._cache:
            return self._cache[name]
        team = TaskListTeam(
            name=name,
            lead=lead,
            storage_dir=self._teams_root / name,
        )
        self._cache[name] = team
        return team

    def get_team(self, name: str) -> TaskListTeam | None:
        """Carga un equipo existente."""
        if name in self._cache:
            return self._cache[name]
        team_dir = self._teams_root / name
        if not team_dir.exists() or not (team_dir / "state.json").exists():
            return None
        team = TaskListTeam(name=name, lead="unknown", storage_dir=team_dir)
        self._cache[name] = team
        return team

    def list_teams(self) -> list[str]:
        """Lista todos los equipos en storage."""
        if not self._teams_root.exists():
            return []
        return [
            d.name for d in self._teams_root.iterdir()
            if d.is_dir() and (d / "state.json").exists()
        ]

    def delete_team(self, name: str) -> bool:
        """Elimina un equipo (borra archivos de storage)."""
        if name in self._cache:
            del self._cache[name]
        import shutil
        team_dir = self._teams_root / name
        if not team_dir.exists():
            return False
        shutil.rmtree(team_dir)
        return True
