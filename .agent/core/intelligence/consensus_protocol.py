# mypy: ignore-errors
#!/usr/bin/env python3
"""
Consensus Protocol Module.

Handles reaching consensus when multiple agents disagree.

Strategies:
- Voting: Democratic majority wins
- Weighted Voting: Expertise-weighted votes
- Deliberation: Structured debate until agreement
- Arbitration: Designated arbitrator decides
- Synthesis: Combine best elements from each position

Version: 1.0.0
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("consensus-protocol")


class ConsensusStrategy(Enum):
    """Consensus strategies."""

    VOTING = "voting"
    WEIGHTED_VOTING = "weighted_voting"
    DELIBERATION = "deliberation"
    ARBITRATION = "arbitration"
    SYNTHESIS = "synthesis"
    AUTOMATIC = "automatic"


class VoteType(Enum):
    """Vote types."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"
    CONDITIONAL = "conditional"


@dataclass
class AgentVote:
    """An agent's vote."""

    agent_id: str
    vote: VoteType
    position: str
    reasoning: str
    confidence: float
    weight: float = 1.0
    conditions: list[str] = field(default_factory=list)


@dataclass
class ConsensusProposal:
    """A proposal for consensus."""

    proposal_id: str
    topic: str
    options: list[str]
    context: dict
    created_at: datetime
    deadline: datetime | None = None


@dataclass
class ConsensusResult:
    """Result of consensus process."""

    proposal_id: str
    topic: str
    strategy_used: ConsensusStrategy
    consensus_reached: bool
    final_decision: str
    confidence: float
    votes: list[AgentVote]
    dissenting_agents: list[str]
    synthesis_notes: str | None
    duration_ms: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "topic": self.topic,
            "strategy_used": self.strategy_used.value,
            "consensus_reached": self.consensus_reached,
            "final_decision": self.final_decision,
            "confidence": self.confidence,
            "votes": [
                {
                    "agent_id": v.agent_id,
                    "vote": v.vote.value,
                    "position": v.position,
                    "reasoning": v.reasoning,
                    "confidence": v.confidence,
                    "weight": v.weight,
                }
                for v in self.votes
            ],
            "dissenting_agents": self.dissenting_agents,
            "synthesis_notes": self.synthesis_notes,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def export_report(self) -> str:
        """Export as markdown report."""
        lines = [
            "# Consensus Report",
            "",
            f"**Topic:** {self.topic}",
            f"**Strategy:** {self.strategy_used.value}",
            f"**Consensus Reached:** {'Yes' if self.consensus_reached else 'No'}",
            f"**Confidence:** {self.confidence:.0%}",
            "",
            "## Final Decision",
            "",
            self.final_decision,
            "",
            "## Votes",
            "",
        ]

        for vote in self.votes:
            icon = (
                "✅"
                if vote.vote == VoteType.APPROVE
                else "❌"
                if vote.vote == VoteType.REJECT
                else "⚪"
            )
            lines.append(f"### {icon} {vote.agent_id}")
            lines.append(f"**Position:** {vote.position}")
            lines.append(f"**Reasoning:** {vote.reasoning}")
            lines.append(f"**Confidence:** {vote.confidence:.0%}")
            lines.append("")

        if self.dissenting_agents:
            lines.extend(["## Dissenting Agents", ""])
            for agent in self.dissenting_agents:
                lines.append(f"- {agent}")
            lines.append("")

        if self.synthesis_notes:
            lines.extend(["## Synthesis Notes", "", self.synthesis_notes])

        return "\n".join(lines)


class ConsensusProtocol:
    """
    Protocol for reaching consensus among multiple agents.

    Supports multiple strategies for different scenarios:
    - Simple voting for clear choices
    - Weighted voting when expertise matters
    - Deliberation for complex decisions
    - Arbitration for deadlocks
    - Synthesis for combining ideas
    """

    def __init__(self, default_strategy: ConsensusStrategy = ConsensusStrategy.AUTOMATIC):
        self.default_strategy = default_strategy
        self.consensus_history: list[ConsensusResult] = []
        self.agent_weights: dict[str, dict[str, float]] = {}  # agent -> domain -> weight

    def set_agent_weight(self, agent_id: str, domain: str, weight: float):
        """Set expertise weight for an agent in a domain."""
        if agent_id not in self.agent_weights:
            self.agent_weights[agent_id] = {}
        self.agent_weights[agent_id][domain] = weight

    def get_agent_weight(self, agent_id: str, domain: str) -> float:
        """Get expertise weight for an agent."""
        return self.agent_weights.get(agent_id, {}).get(domain, 1.0)

    def _select_strategy(
        self, proposal: ConsensusProposal, votes: list[AgentVote]
    ) -> ConsensusStrategy:
        """Automatically select best strategy."""
        # If few options and clear majority, use voting
        if len(proposal.options) <= 3 and len(votes) >= 3:
            approve_count = sum(1 for v in votes if v.vote == VoteType.APPROVE)
            if approve_count > len(votes) * 0.7 or approve_count < len(votes) * 0.3:
                return ConsensusStrategy.VOTING

        # If high expertise variance, use weighted voting
        weights = [v.weight for v in votes]
        if max(weights) > min(weights) * 2:
            return ConsensusStrategy.WEIGHTED_VOTING

        # If many conditional votes, use deliberation
        conditional_count = sum(1 for v in votes if v.vote == VoteType.CONDITIONAL)
        if conditional_count > len(votes) * 0.3:
            return ConsensusStrategy.DELIBERATION

        # Default to synthesis for complex cases
        return ConsensusStrategy.SYNTHESIS

    async def reach_consensus(
        self,
        topic: str,
        votes: list[AgentVote],
        options: list[str] = None,
        strategy: ConsensusStrategy = None,
        context: dict = None,
    ) -> ConsensusResult:
        """
        Reach consensus on a topic.

        Args:
            topic: The topic to reach consensus on
            votes: Agent votes/positions
            options: Available options (if any)
            strategy: Strategy to use (auto if None)
            context: Additional context

        Returns:
            Consensus result
        """
        start_time = datetime.now()
        context = context or {}
        options = options or []

        proposal = ConsensusProposal(
            proposal_id=hashlib.sha256(
                f"{topic}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16],
            topic=topic,
            options=options,
            context=context,
            created_at=datetime.now(),
        )

        # Select strategy
        if strategy is None or strategy == ConsensusStrategy.AUTOMATIC:
            strategy = self._select_strategy(proposal, votes)

        logger.info(f"Using consensus strategy: {strategy.value}")

        # Execute strategy
        if strategy == ConsensusStrategy.VOTING:
            result = await self._voting_consensus(proposal, votes)
        elif strategy == ConsensusStrategy.WEIGHTED_VOTING:
            result = await self._weighted_voting_consensus(proposal, votes)
        elif strategy == ConsensusStrategy.DELIBERATION:
            result = await self._deliberation_consensus(proposal, votes)
        elif strategy == ConsensusStrategy.ARBITRATION:
            result = await self._arbitration_consensus(proposal, votes)
        elif strategy == ConsensusStrategy.SYNTHESIS:
            result = await self._synthesis_consensus(proposal, votes)
        else:
            result = await self._voting_consensus(proposal, votes)

        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.consensus_history.append(result)

        return result

    async def _voting_consensus(
        self, proposal: ConsensusProposal, votes: list[AgentVote]
    ) -> ConsensusResult:
        """Simple majority voting."""
        approve_count = sum(1 for v in votes if v.vote == VoteType.APPROVE)
        reject_count = sum(1 for v in votes if v.vote == VoteType.REJECT)
        total_votes = len([v for v in votes if v.vote != VoteType.ABSTAIN])

        consensus_reached = False
        final_decision = ""

        if total_votes > 0:
            if approve_count > total_votes / 2:
                consensus_reached = True
                # Find most popular position
                positions = [v.position for v in votes if v.vote == VoteType.APPROVE]
                final_decision = (
                    max(set(positions), key=positions.count)
                    if positions
                    else proposal.options[0]
                    if proposal.options
                    else "Approved"
                )
            elif reject_count > total_votes / 2:
                consensus_reached = True
                final_decision = "Rejected"

        confidence = abs(approve_count - reject_count) / total_votes if total_votes > 0 else 0
        dissenting = [
            v.agent_id
            for v in votes
            if (v.vote == VoteType.REJECT and approve_count > reject_count)
            or (v.vote == VoteType.APPROVE and reject_count > approve_count)
        ]

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            topic=proposal.topic,
            strategy_used=ConsensusStrategy.VOTING,
            consensus_reached=consensus_reached,
            final_decision=final_decision,
            confidence=confidence,
            votes=votes,
            dissenting_agents=dissenting,
            synthesis_notes=None,
            duration_ms=0,
        )

    async def _weighted_voting_consensus(
        self, proposal: ConsensusProposal, votes: list[AgentVote]
    ) -> ConsensusResult:
        """Expertise-weighted voting."""
        # Apply domain weights
        domain = self._extract_domain(proposal.topic)
        for vote in votes:
            vote.weight = self.get_agent_weight(vote.agent_id, domain)

        # Calculate weighted votes
        weighted_approve = sum(v.weight for v in votes if v.vote == VoteType.APPROVE)
        weighted_reject = sum(v.weight for v in votes if v.vote == VoteType.REJECT)
        total_weight = sum(v.weight for v in votes if v.vote != VoteType.ABSTAIN)

        consensus_reached = False
        final_decision = ""

        if total_weight > 0:
            if weighted_approve > total_weight / 2:
                consensus_reached = True
                # Weighted position selection
                position_weights: dict[str, float] = {}
                for v in votes:
                    if v.vote == VoteType.APPROVE:
                        position_weights[v.position] = (
                            position_weights.get(v.position, 0) + v.weight
                        )
                final_decision = (
                    max(position_weights, key=position_weights.get)
                    if position_weights
                    else "Approved"
                )
            elif weighted_reject > total_weight / 2:
                consensus_reached = True
                final_decision = "Rejected"

        confidence = (
            abs(weighted_approve - weighted_reject) / total_weight if total_weight > 0 else 0
        )
        dissenting = [
            v.agent_id
            for v in votes
            if (v.vote == VoteType.REJECT and weighted_approve > weighted_reject)
        ]

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            topic=proposal.topic,
            strategy_used=ConsensusStrategy.WEIGHTED_VOTING,
            consensus_reached=consensus_reached,
            final_decision=final_decision,
            confidence=confidence,
            votes=votes,
            dissenting_agents=dissenting,
            synthesis_notes=f"Weights applied for domain: {domain}",
            duration_ms=0,
        )

    async def _deliberation_consensus(
        self, proposal: ConsensusProposal, votes: list[AgentVote]
    ) -> ConsensusResult:
        """Structured deliberation until agreement."""
        rounds = 0
        max_rounds = 5
        current_votes = votes.copy()

        while rounds < max_rounds:
            rounds += 1

            # Check for consensus
            positions = {}
            for v in current_votes:
                if v.vote in [VoteType.APPROVE, VoteType.CONDITIONAL]:
                    positions[v.position] = positions.get(v.position, 0) + 1

            if positions:
                top_position = max(positions, key=positions.get)
                agreement_rate = positions[top_position] / len(current_votes)

                if agreement_rate >= 0.8:
                    return ConsensusResult(
                        proposal_id=proposal.proposal_id,
                        topic=proposal.topic,
                        strategy_used=ConsensusStrategy.DELIBERATION,
                        consensus_reached=True,
                        final_decision=top_position,
                        confidence=agreement_rate,
                        votes=current_votes,
                        dissenting_agents=[
                            v.agent_id for v in current_votes if v.position != top_position
                        ],
                        synthesis_notes=f"Consensus reached after {rounds} rounds of deliberation",
                        duration_ms=0,
                    )

            # Simulate deliberation (in real implementation, would prompt agents)
            # Move conditional votes toward majority position
            for vote in current_votes:
                if vote.vote == VoteType.CONDITIONAL:
                    vote.vote = VoteType.APPROVE

        # No consensus after max rounds
        positions = {}
        for v in current_votes:
            positions[v.position] = positions.get(v.position, 0) + 1
        top_position = max(positions, key=positions.get) if positions else "No decision"

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            topic=proposal.topic,
            strategy_used=ConsensusStrategy.DELIBERATION,
            consensus_reached=False,
            final_decision=f"Deadlock - majority position: {top_position}",
            confidence=positions.get(top_position, 0) / len(current_votes) if current_votes else 0,
            votes=current_votes,
            dissenting_agents=[v.agent_id for v in current_votes if v.position != top_position],
            synthesis_notes=f"Deliberation concluded after {max_rounds} rounds without full consensus",
            duration_ms=0,
        )

    async def _arbitration_consensus(
        self, proposal: ConsensusProposal, votes: list[AgentVote]
    ) -> ConsensusResult:
        """Designated arbitrator decides."""
        # Select arbitrator (highest weight or designated)
        arbitrator = max(votes, key=lambda v: v.weight) if votes else None

        if arbitrator:
            return ConsensusResult(
                proposal_id=proposal.proposal_id,
                topic=proposal.topic,
                strategy_used=ConsensusStrategy.ARBITRATION,
                consensus_reached=True,
                final_decision=arbitrator.position,
                confidence=arbitrator.confidence,
                votes=votes,
                dissenting_agents=[
                    v.agent_id
                    for v in votes
                    if v.agent_id != arbitrator.agent_id and v.position != arbitrator.position
                ],
                synthesis_notes=f"Decision made by arbitrator: {arbitrator.agent_id}",
                duration_ms=0,
            )

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            topic=proposal.topic,
            strategy_used=ConsensusStrategy.ARBITRATION,
            consensus_reached=False,
            final_decision="No arbitrator available",
            confidence=0,
            votes=votes,
            dissenting_agents=[],
            synthesis_notes="Arbitration failed - no suitable arbitrator",
            duration_ms=0,
        )

    async def _synthesis_consensus(
        self, proposal: ConsensusProposal, votes: list[AgentVote]
    ) -> ConsensusResult:
        """Synthesize best elements from each position."""
        # Extract unique elements from all positions
        elements: dict[str, list[str]] = {"pros": [], "cons": [], "conditions": []}

        for vote in votes:
            # Extract key points from reasoning
            reasoning_lower = vote.reasoning.lower()
            if (
                "benefit" in reasoning_lower
                or "advantage" in reasoning_lower
                or "pro" in reasoning_lower
            ):
                elements["pros"].append(f"{vote.agent_id}: {vote.reasoning[:100]}")
            if (
                "risk" in reasoning_lower
                or "concern" in reasoning_lower
                or "con" in reasoning_lower
            ):
                elements["cons"].append(f"{vote.agent_id}: {vote.reasoning[:100]}")
            elements["conditions"].extend(vote.conditions)

        # Build synthesized decision
        synthesis_parts = []
        if elements["pros"]:
            synthesis_parts.append("Benefits acknowledged: " + "; ".join(elements["pros"][:3]))
        if elements["cons"]:
            synthesis_parts.append("Concerns addressed: " + "; ".join(elements["cons"][:3]))
        if elements["conditions"]:
            synthesis_parts.append(
                "Conditions: " + "; ".join(list(set(elements["conditions"]))[:3])
            )

        # Determine synthesized decision
        positions = [v.position for v in votes]
        unique_positions = list(set(positions))

        if len(unique_positions) == 1:
            synthesized = unique_positions[0]
        else:
            # Combine elements
            synthesized = f"Hybrid approach combining: {', '.join(unique_positions[:3])}"

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            topic=proposal.topic,
            strategy_used=ConsensusStrategy.SYNTHESIS,
            consensus_reached=True,
            final_decision=synthesized,
            confidence=0.8,
            votes=votes,
            dissenting_agents=[],
            synthesis_notes="\n".join(synthesis_parts),
            duration_ms=0,
        )

    def _extract_domain(self, topic: str) -> str:
        """Extract domain from topic."""
        topic_lower = topic.lower()
        domains = {
            "frontend": ["react", "vue", "css", "ui", "html"],
            "backend": ["api", "server", "database", "endpoint"],
            "security": ["auth", "security", "encrypt"],
            "devops": ["deploy", "docker", "kubernetes"],
            "architecture": ["design", "architect", "structure"],
        }

        for domain, keywords in domains.items():
            if any(kw in topic_lower for kw in keywords):
                return domain
        return "general"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_protocol: ConsensusProtocol | None = None


def get_consensus_protocol() -> ConsensusProtocol:
    """Get consensus protocol instance."""
    global _protocol
    if _protocol is None:
        _protocol = ConsensusProtocol()
    return _protocol


async def reach_consensus(
    topic: str, votes: list[AgentVote], strategy: ConsensusStrategy = None
) -> ConsensusResult:
    """Reach consensus on a topic."""
    protocol = get_consensus_protocol()
    return await protocol.reach_consensus(topic, votes, strategy=strategy)


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI entry point."""
    print("Consensus Protocol - Demo")
    print("=" * 40)

    # Create sample votes
    votes = [
        AgentVote(
            agent_id="architect",
            vote=VoteType.APPROVE,
            position="Use microservices",
            reasoning="Better scalability and maintainability",
            confidence=0.8,
            weight=1.5,
        ),
        AgentVote(
            agent_id="pragmatist",
            vote=VoteType.CONDITIONAL,
            position="Use microservices with caution",
            reasoning="Good but need to consider team size",
            confidence=0.6,
            conditions=["team has experience", "proper monitoring"],
        ),
        AgentVote(
            agent_id="conservative",
            vote=VoteType.REJECT,
            position="Keep monolith",
            reasoning="Risk of over-engineering for current scale",
            confidence=0.7,
        ),
    ]

    result = await reach_consensus(
        topic="Should we migrate to microservices?",
        votes=votes,
        strategy=ConsensusStrategy.SYNTHESIS,
    )

    print(result.export_report())


if __name__ == "__main__":
    asyncio.run(main())
