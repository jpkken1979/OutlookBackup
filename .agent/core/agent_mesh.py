"""
Agent Mesh - Peer-to-Peer Agent Communication Layer

Enables structured communication between agents:
- Request/Response patterns
- Negotiation protocols
- Task handoffs
- Collaborative problem solving

Version: 1.0.0
"""

import asyncio
import inspect
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequestType(Enum):
    """Types of inter-agent requests."""

    QUESTION = "question"  # Ask another agent for information
    REVIEW = "review"  # Request code/design review
    HANDOFF = "handoff"  # Transfer task ownership
    COLLABORATE = "collaborate"  # Work together on something
    VALIDATE = "validate"  # Validate a decision/approach
    DELEGATE = "delegate"  # Delegate subtask


class ResponseStatus(Enum):
    """Status of agent responses."""

    ACCEPTED = "accepted"  # Request accepted, will process
    COMPLETED = "completed"  # Request completed with result
    DECLINED = "declined"  # Cannot/will not handle
    PARTIAL = "partial"  # Partial answer, needs more info
    NEEDS_INFO = "needs_info"  # Need more information to proceed
    TIMEOUT = "timeout"  # Request timed out
    ERROR = "error"  # Error processing request


class Priority(Enum):
    """Request priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class AgentRequest:
    """Structured request between agents."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str = ""
    to_agent: str = ""
    request_type: RequestType = RequestType.QUESTION
    payload: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    response_timeout: int = 30  # seconds
    priority: Priority = Priority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    requires_response: bool = True

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "request_type": self.request_type.value,
            "payload": self.payload,
            "context": self.context,
            "response_timeout": self.response_timeout,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "requires_response": self.requires_response,
        }


@dataclass
class AgentResponse:
    """Response to an agent request."""

    request_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    status: ResponseStatus = ResponseStatus.COMPLETED
    payload: dict = field(default_factory=dict)
    confidence: float = 1.0
    suggestions: list = field(default_factory=list)
    follow_up_needed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "status": self.status.value,
            "payload": self.payload,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
            "follow_up_needed": self.follow_up_needed,
            "created_at": self.created_at.isoformat(),
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class Consensus:
    """Result of multi-agent negotiation."""

    topic: str = ""
    participants: list = field(default_factory=list)
    agreed_position: dict = field(default_factory=dict)
    confidence: float = 0.0
    dissenting_agents: list = field(default_factory=list)
    rounds_needed: int = 0

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "participants": self.participants,
            "agreed_position": self.agreed_position,
            "confidence": self.confidence,
            "dissenting_agents": self.dissenting_agents,
            "rounds_needed": self.rounds_needed,
        }


class AgentMesh:
    """
    Peer-to-peer agent communication layer.

    Enables structured communication between agents with:
    - Request/response patterns
    - Broadcast discovery
    - Multi-agent negotiation
    - Task handoffs
    """

    def __init__(self):
        from collections import deque

        self.registered_agents: dict[str, dict] = {}
        self.request_handlers: dict[str, Callable] = {}
        self.pending_requests: dict[str, asyncio.Future] = {}
        self.request_history: deque[AgentRequest] = deque(maxlen=1000)
        self.response_history: deque[AgentResponse] = deque(maxlen=1000)
        self._lock = asyncio.Lock()
        self._shared_memory: Any | None = None

    def set_persistence(self, shared_memory) -> None:
        """Enable persistence of request/response history."""
        self._shared_memory = shared_memory

    def register_agent(
        self,
        agent_name: str,
        capabilities: list[str],
        handler: Callable | None = None,
        metadata: dict | None = None,
    ):
        """Register an agent with its capabilities."""
        self.registered_agents[agent_name] = {
            "name": agent_name,
            "capabilities": capabilities,
            "handler": handler,
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
            "request_count": 0,
            "response_count": 0,
        }
        if handler:
            self.request_handlers[agent_name] = handler
        logger.info(f"Agent '{agent_name}' registered with capabilities: {capabilities}")

    def unregister_agent(self, agent_name: str):
        """Unregister an agent."""
        if agent_name in self.registered_agents:
            self.registered_agents.pop(agent_name, None)
        if agent_name in self.request_handlers:
            self.request_handlers.pop(agent_name, None)
        logger.info(f"Agent '{agent_name}' unregistered")

    @staticmethod
    def _normalize_handler_result(
        result: Any,
        req: AgentRequest,
        to_agent: str,
        from_agent: str,
        processing_time: int,
    ) -> AgentResponse:
        """Normaliza el resultado de un handler a un AgentResponse.

        Args:
            result: Valor retornado por el handler (AgentResponse, dict u otro).
            req: Request original (para el request_id).
            to_agent: Agente que respondió.
            from_agent: Agente solicitante.
            processing_time: Tiempo de procesamiento en ms.

        Returns:
            AgentResponse normalizado con processing_time_ms seteado.
        """
        if isinstance(result, AgentResponse):
            result.processing_time_ms = processing_time
            return result
        payload = result if isinstance(result, dict) else {"result": result}
        return AgentResponse(
            request_id=req.request_id,
            from_agent=to_agent,
            to_agent=from_agent,
            status=ResponseStatus.COMPLETED,
            payload=payload,
            processing_time_ms=processing_time,
        )

    async def request(
        self,
        from_agent: str,
        to_agent: str,
        request_type: RequestType,
        payload: dict,
        context: dict | None = None,
        timeout: int = 30,
        priority: Priority = Priority.NORMAL,
    ) -> AgentResponse:
        """
        Send a request to another agent and await response.

        Args:
            from_agent: Requesting agent name
            to_agent: Target agent name
            request_type: Type of request
            payload: Request data
            context: Additional context
            timeout: Response timeout in seconds
            priority: Request priority

        Returns:
            AgentResponse with result or error
        """
        req = AgentRequest(
            from_agent=from_agent,
            to_agent=to_agent,
            request_type=request_type,
            payload=payload,
            context=context or {},
            response_timeout=timeout,
            priority=priority,
        )

        async with self._lock:
            self.request_history.append(req)

            if from_agent in self.registered_agents:
                self.registered_agents[from_agent]["request_count"] += 1
            mem = self._shared_memory
            if mem is not None and hasattr(mem, "add_session_history"):
                mem.add_session_history(
                    {
                        "type": "a2a_request",
                        "request": req.to_dict(),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        # Check if target agent is registered
        if to_agent not in self.registered_agents:
            return AgentResponse(
                request_id=req.request_id,
                from_agent=to_agent,
                to_agent=from_agent,
                status=ResponseStatus.ERROR,
                payload={"error": f"Agent '{to_agent}' not registered"},
            )

        # Check if handler exists
        if to_agent not in self.request_handlers:
            return AgentResponse(
                request_id=req.request_id,
                from_agent=to_agent,
                to_agent=from_agent,
                status=ResponseStatus.ERROR,
                payload={"error": f"Agent '{to_agent}' has no request handler"},
            )

        # Execute handler with timeout
        start_time = datetime.now()
        try:
            handler = self.request_handlers[to_agent]
            if inspect.iscoroutinefunction(handler):
                result = await asyncio.wait_for(handler(req), timeout=timeout)
            else:
                result = handler(req)

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            response = self._normalize_handler_result(
                result, req, to_agent, from_agent, processing_time
            )

        except TimeoutError:
            response = AgentResponse(
                request_id=req.request_id,
                from_agent=to_agent,
                to_agent=from_agent,
                status=ResponseStatus.TIMEOUT,
                payload={"error": f"Request timed out after {timeout}s"},
            )
        except Exception as e:
            response = AgentResponse(
                request_id=req.request_id,
                from_agent=to_agent,
                to_agent=from_agent,
                status=ResponseStatus.ERROR,
                payload={"error": str(e)},
            )

        async with self._lock:
            self.response_history.append(response)

            if to_agent in self.registered_agents:
                self.registered_agents[to_agent]["response_count"] += 1
            mem_resp = self._shared_memory
            if mem_resp is not None and hasattr(mem_resp, "add_session_history"):
                mem_resp.add_session_history(
                    {
                        "type": "a2a_response",
                        "response": response.to_dict(),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        return response

    async def broadcast_discovery(
        self, from_agent: str, need: str, required_capabilities: list[str] | None = None
    ) -> list[str]:
        """
        Discover agents that can help with a need.

        Args:
            from_agent: Agent making the discovery request
            need: Description of what's needed
            required_capabilities: List of required capabilities

        Returns:
            List of agent names that can help
        """
        cache_key = f"discovery_cache:{need}:{','.join(sorted(required_capabilities or []))}"

        # Check cache if persistence is enabled
        mem = self._shared_memory
        if mem is not None and hasattr(mem, "get"):
            cached_result = mem.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Discovery cache hit for '{need}'")
                return [a for a in cached_result if a != from_agent]

        matching_agents = []

        for agent_name, agent_info in self.registered_agents.items():
            if agent_name == from_agent:
                continue

            # Check capabilities match
            if isinstance(required_capabilities, list) and len(required_capabilities) > 0:
                agent_caps_raw = agent_info.get("capabilities", [])
                agent_caps = set(agent_caps_raw) if isinstance(agent_caps_raw, list) else set()
                required = set(required_capabilities)
                if not required.intersection(agent_caps):
                    continue

            matching_agents.append(agent_name)

        mem2 = self._shared_memory
        if mem2 is not None and hasattr(mem2, "set"):
            # Cache the full list without filtering by from_agent so other agents get the same cached list
            from_agent_caps_raw = (
                self.registered_agents[from_agent].get("capabilities", [])
                if from_agent in self.registered_agents
                else []
            )
            from_agent_caps = (
                set(from_agent_caps_raw) if isinstance(from_agent_caps_raw, list) else set()
            )
            req_caps = (
                set(required_capabilities) if isinstance(required_capabilities, list) else set()
            )
            is_from_agent_match = not req_caps or bool(req_caps.intersection(from_agent_caps))

            all_matches = matching_agents + ([from_agent] if is_from_agent_match else [])
            mem2.set(cache_key, all_matches)

        logger.info(f"Discovery for '{need}': found {len(matching_agents)} agents")
        return matching_agents

    async def negotiate(
        self,
        initiator: str,
        agents: list[str],
        topic: str,
        initial_position: dict,
        max_rounds: int = 3,
    ) -> Consensus:
        """
        Multi-agent negotiation to reach consensus.

        Args:
            initiator: Agent initiating negotiation
            agents: List of participating agents
            topic: What we're negotiating about
            initial_position: Starting proposal
            max_rounds: Maximum negotiation rounds

        Returns:
            Consensus result
        """
        participants = [initiator] + [a for a in agents if a != initiator]
        positions: dict[str, dict] = {initiator: initial_position}

        for round_num in range(1, max_rounds + 1):
            logger.info(f"Negotiation round {round_num}/{max_rounds} for '{topic}'")

            # Gather positions from all agents
            for agent in participants:
                if agent in positions:
                    continue

                response = await self.request(
                    from_agent=initiator,
                    to_agent=agent,
                    request_type=RequestType.VALIDATE,
                    payload={"topic": topic, "current_positions": positions, "round": round_num},
                    timeout=15,
                )

                if response.status == ResponseStatus.COMPLETED:
                    positions[agent] = response.payload.get("position", {})

            # Check for consensus
            if len(positions) >= len(participants) * 0.7:  # 70% participation
                # Simple majority consensus
                # In real implementation, would use more sophisticated merging
                agreed = self._merge_positions(positions)
                dissenting = [
                    a for a, p in positions.items() if not self._positions_compatible(p, agreed)
                ]

                if len(dissenting) <= len(participants) * 0.3:  # 70% agreement
                    return Consensus(
                        topic=topic,
                        participants=participants,
                        agreed_position=agreed,
                        confidence=1.0 - (len(dissenting) / len(participants)),
                        dissenting_agents=dissenting,
                        rounds_needed=round_num,
                    )

        # No consensus reached
        return Consensus(
            topic=topic,
            participants=participants,
            agreed_position=initial_position,  # Fall back to initiator's position
            confidence=0.5,
            dissenting_agents=[a for a in participants if a != initiator],
            rounds_needed=max_rounds,
        )

    def _merge_positions(self, positions: dict[str, dict]) -> dict:
        """Merge multiple positions into consensus (simple version)."""
        if not positions:
            return {}
        # For now, just return the first position
        # In production, would use voting or weighted merging
        return list(positions.values())[0]

    def _positions_compatible(self, pos1: dict, pos2: dict) -> bool:
        """Check if two positions are compatible."""
        # Simple check - in production would be more sophisticated
        return pos1 == pos2

    async def handoff(
        self, from_agent: str, to_agent: str, task: dict, context: dict
    ) -> AgentResponse:
        """
        Hand off a task from one agent to another.

        Args:
            from_agent: Agent handing off
            to_agent: Agent receiving
            task: Task details
            context: Context and state to transfer

        Returns:
            Response indicating acceptance
        """
        return await self.request(
            from_agent=from_agent,
            to_agent=to_agent,
            request_type=RequestType.HANDOFF,
            payload={"task": task, "context": context},
            priority=Priority.HIGH,
        )

    def get_agent_stats(self, agent_name: str) -> dict | None:
        """Get statistics for an agent."""
        if agent_name not in self.registered_agents:
            return None
        return self.registered_agents[agent_name].copy()

    def get_mesh_stats(self) -> dict:
        """Get overall mesh statistics."""
        return {
            "registered_agents": len(self.registered_agents),
            "total_requests": len(self.request_history),
            "total_responses": len(self.response_history),
            "agents": list(self.registered_agents.keys()),
        }


# Singleton instance
_mesh_instance: AgentMesh | None = None


def get_agent_mesh() -> AgentMesh:
    """Get the global AgentMesh instance."""
    global _mesh_instance
    if _mesh_instance is None:
        _mesh_instance = AgentMesh()
    return _mesh_instance


# Example usage
if __name__ == "__main__":

    async def demo():
        mesh = get_agent_mesh()

        # Register agents
        def explorer_handler(req: AgentRequest) -> dict:
            return {"found": ["file1.py", "file2.py"], "analysis": "Modular structure"}

        def architect_handler(req: AgentRequest) -> dict:
            return {"recommendation": "Use microservices", "confidence": 0.85}

        mesh.register_agent(
            "explorer", capabilities=["code_analysis", "file_search"], handler=explorer_handler
        )
        mesh.register_agent(
            "architect", capabilities=["design", "architecture"], handler=architect_handler
        )

        # Make a request
        response = await mesh.request(
            from_agent="planner",
            to_agent="explorer",
            request_type=RequestType.QUESTION,
            payload={"query": "Find all Python files"},
        )
        print(f"Response: {response.to_dict()}")

        # Discover agents
        agents = await mesh.broadcast_discovery(
            from_agent="planner", need="architecture review", required_capabilities=["design"]
        )
        print(f"Discovered agents: {agents}")

        # Get stats
        print(f"Mesh stats: {mesh.get_mesh_stats()}")

    asyncio.run(demo())
