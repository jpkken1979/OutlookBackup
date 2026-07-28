#!/usr/bin/env python3
"""
Antigravity A2A Protocol - Agent-to-Agent Communication.

Implements Google's Agent2Agent (A2A) Protocol for:
- Agent discovery via Agent Cards
- Inter-agent communication
- Task delegation between agents
- Capability advertisement

Based on: https://a2a-protocol.org/
"""

import asyncio
import hashlib
import hmac
import inspect
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from pydantic import BaseModel, Field

logger = logging.getLogger("antigravity.a2a")


# =============================================================================
# A2A PROTOCOL MODELS
# =============================================================================


class AgentCapability(str, Enum):
    """Standard agent capabilities."""

    STREAMING = "streaming"
    PUSH_NOTIFICATIONS = "pushNotifications"
    STATE_TRANSITION_HISTORY = "stateTransitionHistory"


class AuthenticationType(str, Enum):
    """Supported authentication types."""

    API_KEY = "apiKey"
    OAUTH2 = "oauth2"
    BEARER = "bearer"
    NONE = "none"


class TaskState(str, Enum):
    """Task execution states per A2A protocol."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# =============================================================================
# AGENT CARD (A2A Discovery)
# =============================================================================


class AgentProvider(BaseModel):
    """Provider information for Agent Card."""

    organization: str
    url: str | None = None


class AgentAuthentication(BaseModel):
    """Authentication configuration for Agent Card."""

    schemes: list[str] = Field(default_factory=lambda: ["none"])
    credentials: str | None = None  # Reference to credentials location


class AgentSkill(BaseModel):
    """A skill/capability that an agent can perform."""

    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)  # Example prompts


class AgentCard(BaseModel):
    """
    Agent Card - A2A Protocol discovery document.

    This is the "business card" of an agent that allows other agents
    to discover its capabilities and know how to communicate with it.
    """

    # Required fields
    name: str
    description: str
    url: str  # Service endpoint URL

    # Optional metadata
    version: str = "1.0.0"
    provider: AgentProvider | None = None
    documentationUrl: str | None = None
    iconUrl: str | None = None

    # Capabilities
    capabilities: dict = Field(
        default_factory=lambda: {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        }
    )

    # Authentication
    authentication: AgentAuthentication = Field(
        default_factory=lambda: AgentAuthentication(schemes=["none"])
    )

    # Default input/output modes
    defaultInputModes: list[str] = Field(default_factory=lambda: ["text"])
    defaultOutputModes: list[str] = Field(default_factory=lambda: ["text"])

    # Skills this agent can perform
    skills: list[AgentSkill] = Field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        """Export as JSON string."""
        return self.model_dump_json(indent=indent)

    def save(self, path: Path) -> None:
        """Save Agent Card to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"Agent Card saved to {path}")

    @classmethod
    def load(cls, path: Path) -> "AgentCard":
        """Load Agent Card from file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


# =============================================================================
# A2A MESSAGES
# =============================================================================


class TextPart(BaseModel):
    """Text content part."""

    type: str = "text"
    text: str


class FilePart(BaseModel):
    """File content part."""

    type: str = "file"
    file: dict  # {name, mimeType, bytes or uri}


class Message(BaseModel):
    """A2A Protocol message."""

    role: str  # "user" or "agent"
    parts: list[dict]  # TextPart, FilePart, etc.


class TaskStatus(BaseModel):
    """Status of a task."""

    state: TaskState
    message: Message | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class Task(BaseModel):
    """A2A Protocol task."""

    id: str
    sessionId: str | None = None
    status: TaskStatus
    history: list[TaskStatus] = Field(default_factory=list)
    artifacts: list[dict] = Field(default_factory=list)


class TaskSendParams(BaseModel):
    """Parameters for sending a task."""

    id: str
    sessionId: str | None = None
    message: Message
    acceptedOutputModes: list[str] = Field(default_factory=lambda: ["text"])
    pushNotification: dict | None = None


# =============================================================================
# A2A PROTOCOL IMPLEMENTATION
# =============================================================================


class A2AProtocol:
    """
    A2A Protocol client/server implementation.

    Handles:
    - Agent Card management
    - Task submission and tracking
    - Inter-agent communication
    """

    # Secret DEBE configurarse via ANTIGRAVITY_A2A_SECRET en env vars
    _DEFAULT_DEV_SECRET = os.environ.get("ANTIGRAVITY_A2A_SECRET", "")

    def __init__(self, agent_cards_dir: Path, own_agent_card: AgentCard | None = None):
        self.agent_cards_dir = Path(agent_cards_dir)
        self.agent_cards_dir.mkdir(parents=True, exist_ok=True)
        self.own_card = own_agent_card
        self.known_agents: dict[str, AgentCard] = {}
        self._a2a_secret: str = os.environ.get("ANTIGRAVITY_A2A_SECRET", self._DEFAULT_DEV_SECRET)
        self._load_known_agents()

    def _sign_message(self, payload: dict) -> str:
        """Generate an HMAC-SHA256 signature for a message payload.

        Args:
            payload: Dictionary to sign (serialized as canonical JSON).

        Returns:
            Hex-encoded HMAC signature string.
        """
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hmac.new(
            self._a2a_secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_signature(self, payload: dict, signature: str) -> bool:
        """Verify an HMAC-SHA256 signature against a message payload.

        Args:
            payload: Dictionary that was signed.
            signature: Hex-encoded HMAC signature to verify.

        Returns:
            True if the signature is valid, False otherwise.
        """
        expected = self._sign_message(payload)
        return hmac.compare_digest(expected, signature)

    def _load_known_agents(self) -> None:
        """Load all known agent cards from directory."""
        for card_file in self.agent_cards_dir.glob("*.json"):
            try:
                card = AgentCard.load(card_file)
                self.known_agents[card.name] = card
                logger.debug(f"Loaded agent card: {card.name}")
            except Exception as e:
                logger.warning(f"Error loading {card_file}: {e}")

        logger.info(f"Loaded {len(self.known_agents)} agent cards")

    def register_agent(self, card: AgentCard) -> None:
        """Register a new agent card in the A2A protocol registry.

        Args:
            card: AgentCard with name, description, URL, and capabilities.
        """
        self.known_agents[card.name] = card
        card.save(self.agent_cards_dir / f"{card.name}.json")
        logger.info(f"Registered agent: {card.name}")

    def discover_agent(self, name: str) -> AgentCard | None:
        """Discover an agent by name in the A2A registry.

        Args:
            name: Agent name to search for.

        Returns:
            AgentCard if found, None otherwise.
        """
        return self.known_agents.get(name)

    def discover_by_skill(self, skill_tag: str) -> list[AgentCard]:
        """Discover agents that have a specific skill tag.

        Args:
            skill_tag: Skill tag to search for (case-insensitive).

        Returns:
            List of AgentCard objects matching the skill tag.
        """
        matching = []
        for card in self.known_agents.values():
            for skill in card.skills:
                if skill_tag.lower() in [t.lower() for t in skill.tags]:
                    matching.append(card)
                    break
        return matching

    def discover_by_capability(self, query: str) -> list[AgentCard]:
        """Discover agents by searching skill descriptions and agent descriptions.

        Args:
            query: Search query (case-insensitive) to match against agent and skill descriptions.

        Returns:
            List of AgentCard objects matching the query.
        """
        query_lower = query.lower()
        matching = []

        for card in self.known_agents.values():
            # Check agent description
            if query_lower in card.description.lower():
                matching.append(card)
                continue

            # Check skills
            for skill in card.skills:
                if query_lower in skill.description.lower() or query_lower in skill.name.lower():
                    matching.append(card)
                    break

        return matching

    def list_agents(self) -> list[dict]:
        """List all known agents with their basic information.

        Returns:
            List of dicts with agent name, description, skills, and service URL.
        """
        return [
            {
                "name": card.name,
                "description": card.description,
                "skills": [s.name for s in card.skills],
                "url": card.url,
            }
            for card in self.known_agents.values()
        ]

    async def _retry_request(
        self,
        url: str,
        payload: dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> dict[str, Any] | None:
        """Send HTTP request with exponential backoff retry.

        Args:
            url: Target URL for the POST request.
            payload: JSON payload to send.
            max_retries: Maximum number of retry attempts after the initial try.
            base_delay: Base delay in seconds for exponential backoff.

        Returns:
            Parsed JSON response dict on success, None on failure.
        """
        import aiohttp

        for attempt in range(max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                        if response.status >= 500 and attempt < max_retries:
                            delay = base_delay * (2**attempt)
                            logger.warning(
                                "A2A request failed (attempt %d/%d, status %d), retrying in %.1fs",
                                attempt + 1,
                                max_retries + 1,
                                response.status,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.error("A2A request failed: status %d", response.status)
                        return None
            except (aiohttp.ClientError, TimeoutError) as e:
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "A2A request error (attempt %d/%d): %s, retrying in %.1fs",
                        attempt + 1,
                        max_retries + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "A2A request failed after %d retries: %s",
                        max_retries + 1,
                        e,
                    )
                    return None
        return None

    async def send_task(
        self, agent_name: str, message: str, session_id: str | None = None
    ) -> Task | None:
        """
        Send a task to another agent.

        Args:
            agent_name: Target agent name
            message: Task message
            session_id: Optional session for context continuity

        Returns:
            Task object with status
        """
        import uuid

        agent = self.discover_agent(agent_name)
        if not agent:
            logger.error("Agent not found: %s", agent_name)
            return None

        task_id = str(uuid.uuid4())

        params = TaskSendParams(
            id=task_id,
            sessionId=session_id,
            message=Message(role="user", parts=[{"type": "text", "text": message}]),
        )

        url = urljoin(agent.url, "/tasks/send")
        request_body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": params.model_dump(),
            "id": task_id,
        }
        # Sign the request params for authentication
        signature = self._sign_message(request_body["params"])
        request_body["signature"] = signature

        result = await self._retry_request(url, request_body)
        if result is not None:
            return Task(**result.get("result", {}))

        # Return local task for tracking on failure
        return Task(
            id=task_id,
            sessionId=session_id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=Message(
                    role="agent",
                    parts=[{"type": "text", "text": f"Failed to send task to {agent_name}"}],
                ),
            ),
        )

    def verify_incoming_task(self, request_body: dict) -> bool:
        """Verify the HMAC signature of an incoming task request.

        Args:
            request_body: Full JSON-RPC request body including 'params' and 'signature'.

        Returns:
            True if the signature is valid or absent (backward-compatible), False if invalid.
        """
        signature = request_body.get("signature")
        if signature is None:
            # No signature present: allow for backward compatibility but log warning
            logger.warning("Incoming task has no signature - skipping verification")
            return True

        params = request_body.get("params", {})
        if not self._verify_signature(params, signature):
            logger.error("Invalid HMAC signature on incoming task")
            return False

        return True

    def create_task_response(
        self, task_id: str, state: TaskState, message: str, artifacts: list | None = None
    ) -> dict:
        """Create a task response in A2A format with HMAC signature."""
        response = {
            "id": task_id,
            "status": {
                "state": state.value,
                "message": {"role": "agent", "parts": [{"type": "text", "text": message}]},
                "timestamp": datetime.now().isoformat(),
            },
            "artifacts": artifacts or [],
        }
        # Sign the response so the caller can verify authenticity
        response["signature"] = self._sign_message(
            {
                "id": response["id"],
                "status": response["status"],
            }
        )
        return response


# =============================================================================
# AGENT MESSAGE BUS - Real-time Inter-Agent Communication
# =============================================================================


@dataclass
class AgentMessage:
    """A message between agents."""

    id: str
    sender: str
    topic: str
    message: dict
    timestamp: str
    priority: int = 0  # 0=normal, 1=high, 2=critical


class AgentMessageBus:
    """
    Real-time messaging between agents during execution.

    Enables agents to:
    - Broadcast discoveries to all agents
    - Subscribe to specific topics
    - Send direct messages to specific agents
    - Share intermediate results

    Topics:
    - "critical_finding" - Urgent discoveries
    - "context_update" - Shared context changes
    - "delegation" - Task delegation requests
    - "result" - Partial results
    - "error" - Error notifications
    """

    def __init__(self):
        self.subscribers: dict[str, list[Callable]] = {}
        self.direct_subscribers: dict[str, list[Callable]] = {}  # agent_name -> callbacks
        self.message_history: list[AgentMessage] = []
        self.max_history = 1000
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        """Start the message bus processor."""
        self._running = True
        asyncio.create_task(self._process_queue())
        logger.info("AgentMessageBus started")

    async def stop(self):
        """Stop the message bus."""
        self._running = False
        logger.info("AgentMessageBus stopped")

    async def publish(self, sender: str, topic: str, message: dict, priority: int = 0) -> str:
        """
        Publish a message to a topic.

        Args:
            sender: Agent sending the message
            topic: Topic to publish to
            message: Message content
            priority: Message priority (0=normal, 1=high, 2=critical)

        Returns:
            Message ID
        """
        import uuid

        msg_id = str(uuid.uuid4())[:12]

        msg = AgentMessage(
            id=msg_id,
            sender=sender,
            topic=topic,
            message=message,
            timestamp=datetime.now().isoformat(),
            priority=priority,
        )

        # Store in history
        self.message_history.append(msg)
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history // 2 :]

        # Notify subscribers
        await self._notify_subscribers(msg)

        logger.debug(f"Message published: {sender} -> {topic}")
        return msg_id

    async def send_direct(self, sender: str, recipient: str, message: dict) -> str:
        """
        Send a direct message to a specific agent.

        Args:
            sender: Agent sending the message
            recipient: Target agent
            message: Message content

        Returns:
            Message ID
        """
        import uuid

        msg_id = str(uuid.uuid4())[:12]

        msg = AgentMessage(
            id=msg_id,
            sender=sender,
            topic=f"direct:{recipient}",
            message=message,
            timestamp=datetime.now().isoformat(),
            priority=1,
        )

        self.message_history.append(msg)

        # Notify direct subscribers
        if recipient in self.direct_subscribers:
            for callback in self.direct_subscribers[recipient]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(msg)
                    else:
                        callback(msg)
                except Exception as e:
                    logger.warning(f"Direct message callback error: {e}")

        return msg_id

    def subscribe(self, topic: str, callback: Callable) -> None:
        """
        Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Function to call when message received
        """
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        logger.debug(f"Subscribed to topic: {topic}")

    def subscribe_direct(self, agent_name: str, callback: Callable) -> None:
        """
        Subscribe to direct messages for an agent.

        Args:
            agent_name: Agent to receive messages for
            callback: Function to call when message received
        """
        if agent_name not in self.direct_subscribers:
            self.direct_subscribers[agent_name] = []
        self.direct_subscribers[agent_name].append(callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe a callback from a topic.

        Args:
            topic: Topic to unsubscribe from.
            callback: Function to remove from topic subscribers.
        """
        if topic in self.subscribers:
            self.subscribers[topic] = [cb for cb in self.subscribers[topic] if cb != callback]

    async def _notify_subscribers(self, msg: AgentMessage) -> None:
        """Notify all subscribers of a message."""
        # Topic subscribers
        if msg.topic in self.subscribers:
            for callback in self.subscribers[msg.topic]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(msg)
                    else:
                        callback(msg)
                except Exception as e:
                    logger.warning(f"Subscriber callback error for {msg.topic}: {e}")

        # Wildcard subscribers (subscribe to "*")
        if "*" in self.subscribers:
            for callback in self.subscribers["*"]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(msg)
                    else:
                        callback(msg)
                except Exception as e:
                    logger.warning(f"Wildcard callback error: {e}")

    async def _process_queue(self):
        """Process queued messages."""
        while self._running:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                await self._notify_subscribers(msg)
            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    def get_messages_for(
        self, agent: str, since: datetime | None = None, topics: list[str] | None = None
    ) -> list[AgentMessage]:
        """
        Get messages relevant to an agent.

        Args:
            agent: Agent to get messages for
            since: Only get messages after this time
            topics: Filter by topics

        Returns:
            List of relevant messages
        """
        messages = []

        for msg in self.message_history:
            # Skip own messages
            if msg.sender == agent:
                continue

            # Time filter
            if since:
                msg_time = datetime.fromisoformat(msg.timestamp)
                if msg_time < since:
                    continue

            # Topic filter - skip if not in topics and not a direct message
            if topics and msg.topic not in topics and not msg.topic.startswith(f"direct:{agent}"):
                continue

            messages.append(msg)

        return messages

    def get_recent_by_topic(self, topic: str, limit: int = 10) -> list[AgentMessage]:
        """Get recent messages from a specific topic.

        Args:
            topic: Topic to retrieve messages from.
            limit: Maximum number of recent messages to return (default 10).

        Returns:
            List of AgentMessage objects from the topic, ordered by recency.
        """
        topic_messages = [m for m in self.message_history if m.topic == topic]
        return topic_messages[-limit:]

    def broadcast_finding(self, sender: str, finding_type: str, details: dict) -> asyncio.Task:
        """
        Convenience method to broadcast a critical finding.

        Args:
            sender: Agent that found something
            finding_type: Type of finding
            details: Finding details

        Returns:
            Async task for the broadcast
        """
        return asyncio.create_task(
            self.publish(
                sender=sender,
                topic="critical_finding",
                message={"type": finding_type, "details": details},
                priority=2,
            )
        )


# Singleton instance
_message_bus: AgentMessageBus | None = None


def get_message_bus() -> AgentMessageBus:
    """Get the global singleton AgentMessageBus instance.

    Creates the instance on first call. Subsequent calls return the same instance.

    Returns:
        The global AgentMessageBus singleton.
    """
    global _message_bus
    if _message_bus is None:
        _message_bus = AgentMessageBus()
    return _message_bus


# =============================================================================
# AGENT CARD GENERATOR
# =============================================================================


def generate_agent_card(
    name: str,
    role: str,
    description: str,
    skills: list[dict],
    base_url: str = "http://localhost:8080",
) -> AgentCard:
    """
    Generate an Agent Card for an Antigravity agent.

    Args:
        name: Agent name (e.g., "frontend-specialist")
        role: Agent role (e.g., "Senior Frontend Developer")
        description: Detailed description
        skills: List of skill dicts with name, description, tags
        base_url: Service endpoint URL

    Returns:
        AgentCard ready for registration
    """
    agent_skills = [
        AgentSkill(
            id=f"{name}-{s['name']}",
            name=s["name"],
            description=s.get("description", ""),
            tags=s.get("tags", []),
            examples=s.get("examples", []),
        )
        for s in skills
    ]

    return AgentCard(
        name=name,
        description=f"{role}: {description}",
        url=f"{base_url}/agents/{name}",
        version="3.0.0",
        provider=AgentProvider(
            organization="Antigravity Agents", url="https://github.com/jokken79/OpenAntigravity"
        ),
        skills=agent_skills,
        capabilities={
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
    )


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    """Generate and test Agent Cards for the A2A protocol.

    Demonstrates:
    - Creating Agent Cards with skills and capabilities
    - Registering agents in the A2A protocol
    - Discovering agents by name, skill tag, and capability
    - Listing all known agents
    """
    import tempfile

    print("Generating Agent Cards for Antigravity agents...\n")

    # Create some agent cards
    cards = [
        generate_agent_card(
            name="frontend-specialist",
            role="Senior Frontend Developer",
            description="Expert in React, Next.js, and modern web development",
            skills=[
                {
                    "name": "react-development",
                    "description": "Build React components and applications",
                    "tags": ["react", "frontend", "ui"],
                    "examples": ["Create a dashboard component", "Build a form with validation"],
                },
                {
                    "name": "nextjs-optimization",
                    "description": "Optimize Next.js applications for performance",
                    "tags": ["nextjs", "performance", "ssr"],
                    "examples": ["Implement ISR for product pages", "Set up image optimization"],
                },
            ],
        ),
        generate_agent_card(
            name="backend-specialist",
            role="Senior Backend Developer",
            description="Expert in Node.js, Python, and API development",
            skills=[
                {
                    "name": "api-design",
                    "description": "Design and implement RESTful and GraphQL APIs",
                    "tags": ["api", "rest", "graphql"],
                    "examples": [
                        "Create a CRUD API for users",
                        "Implement authentication endpoints",
                    ],
                },
                {
                    "name": "database-integration",
                    "description": "Integrate and optimize database operations",
                    "tags": ["database", "sql", "orm"],
                    "examples": ["Set up Prisma with PostgreSQL", "Optimize slow queries"],
                },
            ],
        ),
        generate_agent_card(
            name="uns-hr-specialist",
            role="Japanese HR Specialist",
            description="Expert in Japanese labor law and 派遣 staffing operations",
            skills=[
                {
                    "name": "payroll-calculation",
                    "description": "Calculate Japanese payroll with 所得税, 住民税, and social insurance",
                    "tags": ["payroll", "給与計算", "japanese-hr"],
                    "examples": ["Calculate monthly salary for worker", "Generate 給与明細"],
                },
                {
                    "name": "36kyotei-compliance",
                    "description": "Check and ensure 36協定 overtime compliance",
                    "tags": ["36協定", "labor-law", "compliance"],
                    "examples": ["Verify monthly overtime limits", "Generate compliance report"],
                },
            ],
        ),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        cards_dir = Path(tmpdir)

        # Initialize A2A protocol
        a2a = A2AProtocol(cards_dir)

        # Register agents
        for card in cards:
            a2a.register_agent(card)
            print(f"Registered: {card.name}")

        # Test discovery
        print("\n--- Discovery Tests ---")

        # By name
        agent = a2a.discover_agent("frontend-specialist")
        if agent:
            print(f"\nFound by name: {agent.name}")
            print(f"  Skills: {[s.name for s in agent.skills]}")

        # By skill tag
        api_agents = a2a.discover_by_skill("api")
        print(f"\nAgents with 'api' skill: {[a.name for a in api_agents]}")

        # By capability query
        hr_agents = a2a.discover_by_capability("payroll")
        print(f"Agents matching 'payroll': {[a.name for a in hr_agents]}")

        # List all
        print("\n--- All Agents ---")
        for agent_info in a2a.list_agents():
            print(f"  {agent_info['name']}: {agent_info['skills']}")

    print("\nA2A Protocol tests complete!")


if __name__ == "__main__":
    main()
