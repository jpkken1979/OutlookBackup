# mypy: ignore-errors
#!/usr/bin/env python3
"""
Cross-Agent Messaging - Direct agent-to-agent communication.

This module provides inter-agent communication that:
1. Enables direct messaging between agents
2. Supports different message types (request, response, broadcast)
3. Manages message routing and delivery
4. Tracks conversation threads
5. Handles async communication patterns

Usage:
    from .agent.core.intelligence import AgentMessenger, send_message

    messenger = AgentMessenger()

    # Send a message
    response = await messenger.send(
        from_agent="architect",
        to_agent="security-auditor",
        message="Please review this design",
        message_type=MessageType.REQUEST
    )

    # Broadcast to multiple agents
    await messenger.broadcast(
        from_agent="planner",
        to_agents=["architect", "backend", "frontend"],
        message="New requirements added"
    )
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.cross_agent_messaging")


class MessageType(Enum):
    """Types of agent messages."""

    REQUEST = "request"  # Request for action/information
    RESPONSE = "response"  # Response to a request
    BROADCAST = "broadcast"  # One-to-many notification
    NOTIFICATION = "notification"  # FYI message
    DELEGATION = "delegation"  # Task delegation
    RESULT = "result"  # Task result
    ERROR = "error"  # Error notification
    HEARTBEAT = "heartbeat"  # Alive signal


class MessagePriority(Enum):
    """Priority levels for messages."""

    CRITICAL = "critical"  # Immediate processing
    HIGH = "high"  # Process soon
    NORMAL = "normal"  # Normal processing
    LOW = "low"  # Background processing


class DeliveryStatus(Enum):
    """Message delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass
class Message:
    """An inter-agent message."""

    message_id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    priority: MessagePriority
    subject: str
    content: Any
    thread_id: str | None = None
    reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 3600  # Time to live
    status: DeliveryStatus = DeliveryStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "subject": self.subject,
            "content": self.content,
            "thread_id": self.thread_id,
            "reply_to": self.reply_to,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
        }


@dataclass
class Conversation:
    """A conversation thread between agents."""

    thread_id: str
    participants: set[str]
    messages: list[Message] = field(default_factory=list)
    topic: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    status: str = "active"

    def add_message(self, message: Message) -> None:
        """Add message to conversation."""
        self.messages.append(message)
        self.participants.add(message.from_agent)
        self.participants.add(message.to_agent)
        self.last_activity = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "participants": list(self.participants),
            "message_count": len(self.messages),
            "topic": self.topic,
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "status": self.status,
        }


class MessageRouter:
    """Routes messages between agents."""

    def __init__(self):
        self.routes: dict[str, list[str]] = {}  # agent -> [subscribed topics]
        self.handlers: dict[str, Callable] = {}  # agent -> message handler
        self.message_queue: dict[str, list[Message]] = {}  # agent -> pending messages

    def register_agent(
        self,
        agent_name: str,
        handler: Callable | None = None,
    ) -> None:
        """Register an agent for messaging."""
        if agent_name not in self.message_queue:
            self.message_queue[agent_name] = []
        if handler:
            self.handlers[agent_name] = handler
        logger.debug(f"Registered agent for messaging: {agent_name}")

    def subscribe(self, agent_name: str, topics: list[str]) -> None:
        """Subscribe agent to topics."""
        if agent_name not in self.routes:
            self.routes[agent_name] = []
        self.routes[agent_name].extend(topics)

    def route(self, message: Message) -> bool:
        """Route a message to its destination."""
        to_agent = message.to_agent

        if to_agent not in self.message_queue:
            self.register_agent(to_agent)

        self.message_queue[to_agent].append(message)
        message.status = DeliveryStatus.SENT

        # If handler registered, invoke it
        if to_agent in self.handlers:
            try:
                self.handlers[to_agent](message)
                message.status = DeliveryStatus.DELIVERED
            except Exception as e:
                logger.error(f"Handler error for {to_agent}: {e}")
                message.status = DeliveryStatus.FAILED
                return False

        return True

    def get_pending(self, agent_name: str) -> list[Message]:
        """Get pending messages for an agent."""
        if agent_name not in self.message_queue:
            return []
        messages = self.message_queue[agent_name]
        self.message_queue[agent_name] = []
        return messages


class ConversationManager:
    """Manages conversation threads."""

    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def create_thread(
        self,
        participants: list[str],
        topic: str = "",
    ) -> Conversation:
        """Create a new conversation thread."""
        thread_id = str(uuid.uuid4())[:8]
        conversation = Conversation(
            thread_id=thread_id,
            participants=set(participants),
            topic=topic,
        )
        self.conversations[thread_id] = conversation
        return conversation

    def get_thread(self, thread_id: str) -> Conversation | None:
        """Get a conversation by thread ID."""
        return self.conversations.get(thread_id)

    def add_to_thread(self, message: Message) -> None:
        """Add message to its thread."""
        if message.thread_id and message.thread_id in self.conversations:
            self.conversations[message.thread_id].add_message(message)

    def get_agent_conversations(self, agent_name: str) -> list[Conversation]:
        """Get all conversations for an agent."""
        return [c for c in self.conversations.values() if agent_name in c.participants]


class AgentMessenger:
    """
    Handles cross-agent messaging.

    This class:
    1. Provides send/receive capabilities
    2. Manages message routing
    3. Tracks conversations
    4. Handles async patterns
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/messaging")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.router = MessageRouter()
        self.conversation_manager = ConversationManager()

        # Message history
        self.message_history: list[Message] = []

        # Pending responses (for request-response pattern)
        self.pending_responses: dict[str, asyncio.Future] = {}

    def register_agent(
        self,
        agent_name: str,
        handler: Callable | None = None,
    ) -> None:
        """Register an agent for messaging."""
        self.router.register_agent(agent_name, handler)

    async def send(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        subject: str = "",
        message_type: MessageType = MessageType.REQUEST,
        priority: MessagePriority = MessagePriority.NORMAL,
        thread_id: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        wait_for_response: bool = False,
        timeout: float = 30.0,
    ) -> Message | None:
        """
        Send a message from one agent to another.

        Args:
            from_agent: Sending agent
            to_agent: Receiving agent
            content: Message content
            subject: Message subject
            message_type: Type of message
            priority: Message priority
            thread_id: Thread ID for conversation
            reply_to: Message ID being replied to
            metadata: Additional metadata
            wait_for_response: Whether to wait for response
            timeout: Timeout for response

        Returns:
            Response message if wait_for_response, None otherwise
        """
        message_id = str(uuid.uuid4())[:12]

        # Create or get thread
        if not thread_id:
            thread = self.conversation_manager.create_thread(
                participants=[from_agent, to_agent],
                topic=subject,
            )
            thread_id = thread.thread_id

        message = Message(
            message_id=message_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            priority=priority,
            subject=subject,
            content=content,
            thread_id=thread_id,
            reply_to=reply_to,
            metadata=metadata or {},
        )

        # Route message
        success = self.router.route(message)

        if success:
            self.message_history.append(message)
            self.conversation_manager.add_to_thread(message)
            logger.info(f"Message sent: {from_agent} -> {to_agent} [{message_type.value}]")

            # Wait for response if requested
            if wait_for_response and message_type == MessageType.REQUEST:
                return await self._wait_for_response(message_id, timeout)

        return message if success else None

    async def reply(
        self,
        original_message: Message,
        from_agent: str,
        content: Any,
    ) -> Message | None:
        """
        Reply to a message.

        Args:
            original_message: Message being replied to
            from_agent: Agent sending reply
            content: Reply content

        Returns:
            Reply message
        """
        return await self.send(
            from_agent=from_agent,
            to_agent=original_message.from_agent,
            content=content,
            subject=f"Re: {original_message.subject}",
            message_type=MessageType.RESPONSE,
            priority=original_message.priority,
            thread_id=original_message.thread_id,
            reply_to=original_message.message_id,
        )

    async def broadcast(
        self,
        from_agent: str,
        to_agents: list[str],
        content: Any,
        subject: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> list[Message]:
        """
        Broadcast message to multiple agents.

        Args:
            from_agent: Sending agent
            to_agents: List of receiving agents
            content: Message content
            subject: Message subject
            priority: Message priority

        Returns:
            List of sent messages
        """
        messages = []

        for to_agent in to_agents:
            message = await self.send(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                subject=subject,
                message_type=MessageType.BROADCAST,
                priority=priority,
            )
            if message:
                messages.append(message)

        logger.info(f"Broadcast from {from_agent} to {len(messages)} agents")
        return messages

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: dict[str, Any] | None = None,
        wait_for_result: bool = True,
        timeout: float = 60.0,
    ) -> Message | None:
        """
        Delegate a task to another agent.

        Args:
            from_agent: Delegating agent
            to_agent: Agent receiving task
            task: Task description
            context: Task context
            wait_for_result: Whether to wait for result
            timeout: Timeout for result

        Returns:
            Result message if wait_for_result
        """
        return await self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            content={"task": task, "context": context or {}},
            subject=f"Task: {task[:50]}",
            message_type=MessageType.DELEGATION,
            priority=MessagePriority.HIGH,
            wait_for_response=wait_for_result,
            timeout=timeout,
        )

    def get_pending_messages(self, agent_name: str) -> list[Message]:
        """Get pending messages for an agent."""
        return self.router.get_pending(agent_name)

    def get_conversation(self, thread_id: str) -> Conversation | None:
        """Get a conversation thread."""
        return self.conversation_manager.get_thread(thread_id)

    def get_agent_conversations(self, agent_name: str) -> list[Conversation]:
        """Get all conversations for an agent."""
        return self.conversation_manager.get_agent_conversations(agent_name)

    async def _wait_for_response(
        self,
        message_id: str,
        timeout: float,
    ) -> Message | None:
        """Wait for a response to a message."""
        future = asyncio.get_running_loop().create_future()
        self.pending_responses[message_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            logger.warning(f"Response timeout for message {message_id}")
            return None
        finally:
            self.pending_responses.pop(message_id, None)

    def notify_response(self, message_id: str, response: Message) -> None:
        """Notify that a response was received."""
        if message_id in self.pending_responses:
            self.pending_responses[message_id].set_result(response)

    def get_message_history(
        self,
        agent_name: str | None = None,
        limit: int = 100,
    ) -> list[Message]:
        """Get message history."""
        messages = self.message_history

        if agent_name:
            messages = [
                m for m in messages if m.from_agent == agent_name or m.to_agent == agent_name
            ]

        return messages[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """Get messaging statistics."""
        total = len(self.message_history)
        by_type = {}
        by_agent = {}

        for msg in self.message_history:
            # By type
            msg_type = msg.message_type.value
            by_type[msg_type] = by_type.get(msg_type, 0) + 1

            # By agent (sender)
            by_agent[msg.from_agent] = by_agent.get(msg.from_agent, 0) + 1

        return {
            "total_messages": total,
            "by_type": by_type,
            "by_agent": dict(sorted(by_agent.items(), key=lambda x: x[1], reverse=True)[:10]),
            "active_conversations": len(self.conversation_manager.conversations),
        }

    def export_conversation(self, thread_id: str) -> str:
        """Export conversation as markdown."""
        conversation = self.get_conversation(thread_id)
        if not conversation:
            return f"Conversation {thread_id} not found"

        lines = [
            f"# Conversation: {conversation.topic or thread_id}",
            "",
            f"**Participants:** {', '.join(conversation.participants)}",
            f"**Started:** {conversation.started_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Messages:** {len(conversation.messages)}",
            "",
            "---",
            "",
        ]

        for msg in conversation.messages:
            lines.extend(
                [
                    f"**{msg.from_agent}** → **{msg.to_agent}** [{msg.message_type.value}]",
                    f"*{msg.timestamp.strftime('%H:%M:%S')}*",
                    "",
                    str(msg.content),
                    "",
                    "---",
                    "",
                ]
            )

        return "\n".join(lines)


# Convenience function
async def send_message(
    from_agent: str,
    to_agent: str,
    content: Any,
    message_type: MessageType = MessageType.REQUEST,
) -> Message | None:
    """Quick function to send a message."""
    messenger = AgentMessenger()
    return await messenger.send(from_agent, to_agent, content, message_type=message_type)
