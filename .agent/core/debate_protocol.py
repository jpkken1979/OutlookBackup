"""
Debate Protocol - Multi-Agent Conflict Resolution

Enables structured debate between agents when they disagree:
- Position declaration
- Evidence presentation
- Challenge/response cycles
- Consensus building
- Moderator-based resolution

Version: 1.0.0
"""
# mypy: ignore-errors

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DebateStatus(Enum):
    """Status of a debate."""

    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    CONSENSUS_REACHED = "consensus_reached"
    NO_CONSENSUS = "no_consensus"
    ESCALATED = "escalated"
    TIMED_OUT = "timed_out"


class VoteType(Enum):
    """Types of votes in debate resolution."""

    AGREE = "agree"
    DISAGREE = "disagree"
    ABSTAIN = "abstain"
    CONDITIONAL = "conditional"


@dataclass
class DebatePosition:
    """An agent's position in a debate."""

    agent: str
    position: str
    arguments: list = field(default_factory=list)
    evidence: list = field(default_factory=dict)
    confidence: float = 0.5
    priorities: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "position": self.position,
            "arguments": self.arguments,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "priorities": self.priorities,
            "constraints": self.constraints,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Challenge:
    """A challenge to another agent's position."""

    challenger: str
    target_agent: str
    target_argument: str
    challenge_type: str  # "factual", "logical", "relevance", "completeness"
    challenge_text: str
    evidence: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "challenger": self.challenger,
            "target_agent": self.target_agent,
            "target_argument": self.target_argument,
            "challenge_type": self.challenge_type,
            "challenge_text": self.challenge_text,
            "evidence": self.evidence,
        }


@dataclass
class DebateRound:
    """One round of debate."""

    round_number: int
    positions: list = field(default_factory=list)
    challenges: list = field(default_factory=list)
    responses: list = field(default_factory=list)
    synthesis: str = ""

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "positions": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.positions],
            "challenges": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.challenges],
            "responses": self.responses,
            "synthesis": self.synthesis,
        }


@dataclass
class Resolution:
    """Result of debate resolution."""

    status: DebateStatus
    final_position: dict
    confidence: float
    supporting_agents: list
    dissenting_agents: list
    key_points: list
    compromises: list
    unresolved_issues: list

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "final_position": self.final_position,
            "confidence": self.confidence,
            "supporting_agents": self.supporting_agents,
            "dissenting_agents": self.dissenting_agents,
            "key_points": self.key_points,
            "compromises": self.compromises,
            "unresolved_issues": self.unresolved_issues,
        }


@dataclass
class Debate:
    """A complete debate record."""

    debate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    description: str = ""
    initiator: str = ""
    participants: list = field(default_factory=list)
    rounds: list = field(default_factory=list)
    status: DebateStatus = DebateStatus.INITIATED
    resolution: Resolution | None = None
    created_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "debate_id": self.debate_id,
            "topic": self.topic,
            "description": self.description,
            "initiator": self.initiator,
            "participants": self.participants,
            "rounds": [r.to_dict() for r in self.rounds],
            "status": self.status.value,
            "resolution": self.resolution.to_dict() if self.resolution else None,
            "created_at": self.created_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "metadata": self.metadata,
        }


class DebateProtocol:
    """
    Structured multi-agent debate system.

    Enables agents to formally disagree, present evidence,
    challenge each other, and reach consensus or escalate.
    """

    def __init__(self, position_handler: Callable | None = None):
        self.active_debates: dict[str, Debate] = {}
        self.completed_debates: list[Debate] = []
        self.position_handler = position_handler  # Function to get agent positions
        self._lock = asyncio.Lock()

    async def initiate_debate(
        self,
        topic: str,
        description: str,
        initiator: str,
        participants: list[str],
        initial_position: dict | None = None,
        max_rounds: int = 3,
        consensus_threshold: float = 0.7,
    ) -> Debate:
        """
        Initiate a new debate.

        Args:
            topic: What we're debating
            description: Detailed description
            initiator: Agent starting the debate
            participants: Agents participating
            initial_position: Initiator's starting position
            max_rounds: Maximum debate rounds
            consensus_threshold: Required agreement ratio

        Returns:
            The created Debate object
        """
        debate = Debate(
            topic=topic,
            description=description,
            initiator=initiator,
            participants=participants,
            status=DebateStatus.IN_PROGRESS,
            metadata={"max_rounds": max_rounds, "consensus_threshold": consensus_threshold},
        )

        # Add initiator's position if provided
        if initial_position:
            position = DebatePosition(
                agent=initiator,
                position=initial_position.get("position", ""),
                arguments=initial_position.get("arguments", []),
                evidence=initial_position.get("evidence", []),
                confidence=initial_position.get("confidence", 0.5),
            )
            round_1 = DebateRound(round_number=1, positions=[position])
            debate.rounds.append(round_1)

        async with self._lock:
            self.active_debates[debate.debate_id] = debate

        logger.info(f"Debate initiated: {topic} ({len(participants)} participants)")
        return debate

    async def submit_position(
        self,
        debate_id: str,
        agent: str,
        position: str,
        arguments: list[str],
        evidence: list | None = None,
        confidence: float = 0.5,
    ) -> bool:
        """
        Submit an agent's position to the debate.

        Args:
            debate_id: Debate ID
            agent: Agent submitting
            position: Position statement
            arguments: Supporting arguments
            evidence: Supporting evidence
            confidence: Confidence in position

        Returns:
            Success status
        """
        if debate_id not in self.active_debates:
            return False

        debate = self.active_debates[debate_id]

        if agent not in debate.participants and agent != debate.initiator:
            logger.warning(f"Agent {agent} not a participant in debate {debate_id}")
            return False

        pos = DebatePosition(
            agent=agent,
            position=position,
            arguments=arguments,
            evidence=evidence or [],
            confidence=confidence,
        )

        async with self._lock:
            # Add to current or new round
            if not debate.rounds:
                debate.rounds.append(DebateRound(round_number=1))
            debate.rounds[-1].positions.append(pos)

        return True

    async def submit_challenge(
        self,
        debate_id: str,
        challenger: str,
        target_agent: str,
        target_argument: str,
        challenge_type: str,
        challenge_text: str,
        evidence: list | None = None,
    ) -> bool:
        """
        Submit a challenge to another agent's argument.

        Args:
            debate_id: Debate ID
            challenger: Challenging agent
            target_agent: Agent being challenged
            target_argument: Specific argument being challenged
            challenge_type: Type of challenge
            challenge_text: The challenge
            evidence: Supporting evidence

        Returns:
            Success status
        """
        if debate_id not in self.active_debates:
            return False

        debate = self.active_debates[debate_id]

        challenge = Challenge(
            challenger=challenger,
            target_agent=target_agent,
            target_argument=target_argument,
            challenge_type=challenge_type,
            challenge_text=challenge_text,
            evidence=evidence or [],
        )

        async with self._lock:
            if debate.rounds:
                debate.rounds[-1].challenges.append(challenge)
            else:
                round_1 = DebateRound(round_number=1, challenges=[challenge])
                debate.rounds.append(round_1)

        return True

    async def run_debate(
        self, debate_id: str, position_getter: Callable | None = None
    ) -> Resolution:
        """
        Run a complete debate to resolution.

        Args:
            debate_id: Debate to run
            position_getter: Async function to get agent positions

        Returns:
            Resolution result
        """
        if debate_id not in self.active_debates:
            return Resolution(
                status=DebateStatus.NO_CONSENSUS,
                final_position={},
                confidence=0.0,
                supporting_agents=[],
                dissenting_agents=[],
                key_points=[],
                compromises=[],
                unresolved_issues=["Debate not found"],
            )

        debate = self.active_debates[debate_id]
        debate.metadata.get("max_rounds", 3)
        threshold = debate.metadata.get("consensus_threshold", 0.7)

        # Collect positions if we have a getter
        if position_getter:
            for agent in debate.participants:
                try:
                    pos_data = await position_getter(agent, debate.topic)
                    if pos_data:
                        await self.submit_position(
                            debate_id=debate_id,
                            agent=agent,
                            position=pos_data.get("position", ""),
                            arguments=pos_data.get("arguments", []),
                            evidence=pos_data.get("evidence", []),
                            confidence=pos_data.get("confidence", 0.5),
                        )
                except Exception as e:
                    logger.error(f"Error getting position from {agent}: {e}")

        # Try to reach consensus
        resolution = await self._attempt_consensus(debate, threshold)

        # Update debate status
        async with self._lock:
            debate.status = resolution.status
            debate.resolution = resolution
            debate.ended_at = datetime.now()

            # Move to completed
            self.completed_debates.append(debate)
            del self.active_debates[debate_id]

        return resolution

    async def _attempt_consensus(self, debate: Debate, threshold: float) -> Resolution:
        """Attempt to reach consensus from current positions."""
        if not debate.rounds or not debate.rounds[-1].positions:
            return Resolution(
                status=DebateStatus.NO_CONSENSUS,
                final_position={},
                confidence=0.0,
                supporting_agents=[],
                dissenting_agents=debate.participants,
                key_points=[],
                compromises=[],
                unresolved_issues=["No positions submitted"],
            )

        positions = debate.rounds[-1].positions
        all_agents = set(debate.participants + [debate.initiator])
        participating = {p.agent for p in positions}

        # Check participation
        if len(participating) < len(all_agents) * 0.5:
            return Resolution(
                status=DebateStatus.NO_CONSENSUS,
                final_position={},
                confidence=0.0,
                supporting_agents=list(participating),
                dissenting_agents=list(all_agents - participating),
                key_points=[],
                compromises=[],
                unresolved_issues=["Insufficient participation"],
            )

        # Group similar positions
        position_groups = self._group_positions(positions)

        if not position_groups:
            return Resolution(
                status=DebateStatus.NO_CONSENSUS,
                final_position={},
                confidence=0.0,
                supporting_agents=[],
                dissenting_agents=list(all_agents),
                key_points=[],
                compromises=[],
                unresolved_issues=["Could not group positions"],
            )

        # Find majority position
        largest_group = max(position_groups, key=lambda g: len(g["agents"]))
        agreement_ratio = len(largest_group["agents"]) / len(participating)

        if agreement_ratio >= threshold:
            # Consensus reached
            return Resolution(
                status=DebateStatus.CONSENSUS_REACHED,
                final_position=largest_group["position"],
                confidence=agreement_ratio,
                supporting_agents=largest_group["agents"],
                dissenting_agents=[
                    p.agent for p in positions if p.agent not in largest_group["agents"]
                ],
                key_points=self._extract_key_points(positions),
                compromises=[],
                unresolved_issues=[],
            )
        else:
            # No consensus - try to find compromises
            compromises = self._find_compromises(positions)
            return Resolution(
                status=DebateStatus.NO_CONSENSUS,
                final_position=largest_group["position"],  # Majority position
                confidence=agreement_ratio,
                supporting_agents=largest_group["agents"],
                dissenting_agents=[
                    p.agent for p in positions if p.agent not in largest_group["agents"]
                ],
                key_points=self._extract_key_points(positions),
                compromises=compromises,
                unresolved_issues=self._find_unresolved(positions),
            )

    def _group_positions(self, positions: list[DebatePosition]) -> list[dict]:
        """Group similar positions together."""
        groups = []

        for pos in positions:
            # Simple grouping - exact match on position text
            # In production, would use semantic similarity
            found_group = False
            for group in groups:
                if group["position_text"].lower() == pos.position.lower():
                    group["agents"].append(pos.agent)
                    group["total_confidence"] += pos.confidence
                    found_group = True
                    break

            if not found_group:
                groups.append(
                    {
                        "position_text": pos.position,
                        "position": {
                            "statement": pos.position,
                            "arguments": pos.arguments,
                            "evidence": pos.evidence,
                        },
                        "agents": [pos.agent],
                        "total_confidence": pos.confidence,
                    }
                )

        return groups

    def _extract_key_points(self, positions: list[DebatePosition]) -> list[str]:
        """Extract key points from all positions."""
        key_points = []
        for pos in positions:
            for arg in pos.arguments[:2]:  # Top 2 arguments per position
                if arg not in key_points:
                    key_points.append(arg)
        return key_points[:10]  # Top 10 overall

    def _find_compromises(self, positions: list[DebatePosition]) -> list[str]:
        """Find potential compromises between positions."""
        # Simple implementation - find common elements
        all_priorities = []
        for pos in positions:
            all_priorities.extend(pos.priorities)

        # Count occurrences
        priority_counts = {}
        for p in all_priorities:
            priority_counts[p] = priority_counts.get(p, 0) + 1

        # Shared priorities are potential compromise points
        shared = [p for p, count in priority_counts.items() if count > 1]
        return shared[:5]

    def _find_unresolved(self, positions: list[DebatePosition]) -> list[str]:
        """Find unresolved issues."""
        # Simple: constraints that conflict
        all_constraints = []
        for pos in positions:
            all_constraints.extend(pos.constraints)
        return list(set(all_constraints))[:5]

    async def resolve_conflict(
        self, positions: list[DebatePosition], moderator: str | None = None
    ) -> Resolution:
        """
        Resolve conflicting agent opinions.

        Args:
            positions: Conflicting positions
            moderator: Optional moderator agent

        Returns:
            Resolution
        """
        # Create a temporary debate
        debate = Debate(topic="Conflict Resolution", participants=[p.agent for p in positions])
        if moderator:
            debate.metadata["moderator"] = moderator
        debate.rounds.append(DebateRound(round_number=1, positions=positions))

        return await self._attempt_consensus(debate, threshold=0.6)

    def get_active_debates(self) -> list[dict]:
        """Get all active debates."""
        return [d.to_dict() for d in self.active_debates.values()]

    def get_debate_history(self, limit: int = 10) -> list[dict]:
        """Get recent completed debates."""
        return [d.to_dict() for d in self.completed_debates[-limit:]]


# Singleton instance
_protocol_instance: DebateProtocol | None = None


def get_debate_protocol() -> DebateProtocol:
    """Get the global DebateProtocol instance."""
    global _protocol_instance
    if _protocol_instance is None:
        _protocol_instance = DebateProtocol()
    return _protocol_instance


# Example usage
if __name__ == "__main__":

    async def demo():
        protocol = get_debate_protocol()

        # Initiate debate
        debate = await protocol.initiate_debate(
            topic="Should we use microservices or monolith?",
            description="Architectural decision for new system",
            initiator="architect",
            participants=["backend-specialist", "devops-engineer", "performance-optimizer"],
            initial_position={
                "position": "Use microservices for scalability",
                "arguments": [
                    "Better horizontal scaling",
                    "Independent deployments",
                    "Technology flexibility",
                ],
                "confidence": 0.8,
            },
        )
        print(f"Debate initiated: {debate.debate_id}")

        # Submit other positions
        await protocol.submit_position(
            debate_id=debate.debate_id,
            agent="devops-engineer",
            position="Start with monolith, split later",
            arguments=["Lower initial complexity", "Faster time to market", "Easier debugging"],
            confidence=0.75,
        )

        await protocol.submit_position(
            debate_id=debate.debate_id,
            agent="backend-specialist",
            position="Use microservices for scalability",
            arguments=["Team autonomy", "Clear boundaries"],
            confidence=0.7,
        )

        # Run debate to resolution
        resolution = await protocol.run_debate(debate.debate_id)
        print(f"Resolution: {resolution.to_dict()}")

    asyncio.run(demo())
