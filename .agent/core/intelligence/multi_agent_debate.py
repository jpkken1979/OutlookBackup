#!/usr/bin/env python3
"""
Multi-Agent Debate Module - Collaborative decision making through debate.

This module enables multiple agents to:
- Debate critical decisions from different perspectives
- Challenge assumptions and identify blind spots
- Reach consensus through structured argumentation
- Produce higher quality decisions than single-agent reasoning

Usage:
    from .agent.core.intelligence import MultiAgentDebate

    debate = MultiAgentDebate()
    result = await debate.debate(
        question="Should we use microservices or monolith?",
        perspectives=["architect", "devops", "security", "performance"]
    )
"""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.debate")


class ArgumentType(Enum):
    """Types of arguments in a debate."""

    PROPOSITION = "proposition"  # Initial position
    SUPPORT = "support"  # Supporting evidence
    CHALLENGE = "challenge"  # Counter-argument
    REBUTTAL = "rebuttal"  # Response to challenge
    CONCESSION = "concession"  # Acknowledging valid point
    SYNTHESIS = "synthesis"  # Combining perspectives


class VoteType(Enum):
    """Voting options for consensus."""

    STRONGLY_AGREE = "strongly_agree"
    AGREE = "agree"
    NEUTRAL = "neutral"
    DISAGREE = "disagree"
    STRONGLY_DISAGREE = "strongly_disagree"


@dataclass
class Argument:
    """A single argument in the debate."""

    agent_perspective: str
    argument_type: ArgumentType
    content: str
    evidence: list[str]
    confidence: float
    responding_to: int | None = None  # Index of argument being responded to
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["argument_type"] = self.argument_type.value
        return d


@dataclass
class Vote:
    """A vote from a perspective on a proposal."""

    perspective: str
    vote: VoteType
    reasoning: str
    conditions: list[str]  # Conditions for agreement


@dataclass
class DebateResult:
    """Result of a multi-agent debate."""

    question: str
    perspectives: list[str]
    arguments: list[Argument]
    consensus_reached: bool
    consensus_position: str
    confidence: float
    dissenting_views: list[str]
    key_insights: list[str]
    unresolved_tensions: list[str]
    recommended_action: str
    votes: list[Vote]
    debate_rounds: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["arguments"] = [a.to_dict() for a in self.arguments]
        d["votes"] = [asdict(v) for v in self.votes]
        for v in d["votes"]:
            v["vote"] = v["vote"].value
        return d

    def to_summary(self) -> str:
        """Generate debate summary."""
        lines = [
            f"# Debate Summary: {self.question}",
            "",
            f"**Perspectives:** {', '.join(self.perspectives)}",
            f"**Rounds:** {self.debate_rounds}",
            f"**Consensus:** {'Yes' if self.consensus_reached else 'No'}",
            f"**Confidence:** {self.confidence:.0%}",
            "",
            "## Final Position",
            self.consensus_position,
            "",
            "## Key Insights",
        ]

        for insight in self.key_insights:
            lines.append(f"- {insight}")

        if self.dissenting_views:
            lines.extend(["", "## Dissenting Views"])
            for view in self.dissenting_views:
                lines.append(f"- {view}")

        if self.unresolved_tensions:
            lines.extend(["", "## Unresolved Tensions"])
            for tension in self.unresolved_tensions:
                lines.append(f"- {tension}")

        lines.extend(["", "## Recommended Action", self.recommended_action])

        return "\n".join(lines)


class Perspective:
    """A debate perspective with its biases and priorities."""

    PERSPECTIVE_CONFIGS = {
        "architect": {
            "priorities": ["scalability", "maintainability", "simplicity", "patterns"],
            "concerns": ["over-engineering", "technical debt", "complexity"],
            "bias": "prefers elegant, well-structured solutions",
        },
        "security": {
            "priorities": ["safety", "compliance", "threat mitigation", "zero-trust"],
            "concerns": ["vulnerabilities", "data exposure", "attack surface"],
            "bias": "prefers secure, defensive solutions",
        },
        "performance": {
            "priorities": ["speed", "efficiency", "resource usage", "latency"],
            "concerns": ["bottlenecks", "memory leaks", "scaling issues"],
            "bias": "prefers fast, optimized solutions",
        },
        "devops": {
            "priorities": ["automation", "reliability", "observability", "deployment"],
            "concerns": ["operational complexity", "monitoring gaps", "downtime"],
            "bias": "prefers operable, automatable solutions",
        },
        "ux": {
            "priorities": ["usability", "accessibility", "user experience", "clarity"],
            "concerns": ["complexity for users", "friction", "confusion"],
            "bias": "prefers user-friendly, intuitive solutions",
        },
        "business": {
            "priorities": ["cost", "time-to-market", "ROI", "risk"],
            "concerns": ["budget", "delays", "market fit"],
            "bias": "prefers cost-effective, timely solutions",
        },
        "critic": {
            "priorities": ["correctness", "edge cases", "failure modes", "assumptions"],
            "concerns": ["blind spots", "untested scenarios", "false confidence"],
            "bias": "prefers thoroughly validated solutions",
        },
        "pragmatist": {
            "priorities": ["practicality", "iteration", "MVP", "learning"],
            "concerns": ["perfectionism", "analysis paralysis", "over-planning"],
            "bias": "prefers actionable, iterative solutions",
        },
    }

    @classmethod
    def get_config(cls, perspective: str) -> dict[str, Any]:
        return cls.PERSPECTIVE_CONFIGS.get(
            perspective, {"priorities": ["quality"], "concerns": ["risks"], "bias": "neutral"}
        )


class MultiAgentDebate:
    """
    Multi-Agent Debate engine for critical decision making.

    Enables structured debate between multiple perspectives
    to reach better decisions through adversarial collaboration.
    """

    MAX_ROUNDS = 5
    CONSENSUS_THRESHOLD = 0.7  # 70% agreement for consensus

    def __init__(
        self,
        llm_debater: Callable | None = None,
        memory_dir: Path | None = None,
        max_rounds: int = MAX_ROUNDS,
    ):
        self.llm_debater = llm_debater
        self.memory_dir = memory_dir or Path(".agent/memory/debates")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.max_rounds = max_rounds
        self.debate_history: list[DebateResult] = []
        logger.info("MultiAgentDebate engine initialized")

    async def debate(
        self,
        question: str,
        perspectives: list[str],
        context: dict[str, Any] | None = None,
        initial_proposal: str | None = None,
    ) -> DebateResult:
        """
        Conduct a multi-agent debate on a question.

        Args:
            question: The question or decision to debate
            perspectives: List of perspectives to include
            context: Additional context for the debate
            initial_proposal: Optional starting proposal

        Returns:
            DebateResult with consensus and insights
        """
        context = context or {}
        perspectives = perspectives or ["architect", "security", "pragmatist"]

        logger.info(f"Starting debate: {question[:50]}... with {len(perspectives)} perspectives")

        arguments: list[Argument] = []
        round_num = 0

        # Phase 1: Initial propositions
        for perspective in perspectives:
            proposition = await self._generate_proposition(
                question=question,
                perspective=perspective,
                context=context,
                initial_proposal=initial_proposal,
            )
            arguments.append(proposition)

        round_num += 1

        # Phase 2: Challenges and rebuttals
        while round_num < self.max_rounds:
            new_arguments = []

            for _i, perspective in enumerate(perspectives):
                # Each perspective challenges others
                other_args = [a for a in arguments if a.agent_perspective != perspective]
                if other_args:
                    challenge = await self._generate_challenge(
                        question=question,
                        perspective=perspective,
                        arguments=arguments,
                        context=context,
                    )
                    if challenge:
                        new_arguments.append(challenge)

            if not new_arguments:
                break

            arguments.extend(new_arguments)
            round_num += 1

        # Phase 3: Synthesis
        synthesis = await self._generate_synthesis(
            question=question,
            arguments=arguments,
            perspectives=perspectives,
        )
        arguments.append(synthesis)

        # Phase 4: Voting
        votes = await self._conduct_voting(
            question=question,
            synthesis=synthesis,
            perspectives=perspectives,
        )

        # Analyze results
        consensus_reached, consensus_position = self._determine_consensus(votes, synthesis)
        confidence = self._calculate_confidence(votes)
        dissenting = self._get_dissenting_views(votes, arguments)
        insights = self._extract_insights(arguments)
        tensions = self._identify_tensions(arguments)
        action = self._recommend_action(consensus_reached, consensus_position, tensions)

        result = DebateResult(
            question=question,
            perspectives=perspectives,
            arguments=arguments,
            consensus_reached=consensus_reached,
            consensus_position=consensus_position,
            confidence=confidence,
            dissenting_views=dissenting,
            key_insights=insights,
            unresolved_tensions=tensions,
            recommended_action=action,
            votes=votes,
            debate_rounds=round_num,
        )

        self.debate_history.append(result)
        await self._save_debate(result)

        logger.info(f"Debate complete: consensus={consensus_reached}, confidence={confidence:.0%}")
        return result

    async def _generate_proposition(
        self,
        question: str,
        perspective: str,
        context: dict[str, Any],
        initial_proposal: str | None,
    ) -> Argument:
        """Generate initial proposition from a perspective."""
        config = Perspective.get_config(perspective)

        if self.llm_debater:
            return await self._llm_generate_argument(
                question=question,
                perspective=perspective,
                config=config,
                argument_type=ArgumentType.PROPOSITION,
                context=context,
                reference=initial_proposal,
            )

        return self._heuristic_proposition(question, perspective, config, initial_proposal)

    def _heuristic_proposition(
        self,
        question: str,
        perspective: str,
        config: dict[str, Any],
        initial_proposal: str | None,
    ) -> Argument:
        """Heuristic proposition generation."""
        priorities = config["priorities"]
        bias = config["bias"]

        content = f"From the {perspective} perspective, focusing on {', '.join(priorities[:2])}: "

        if initial_proposal:
            content += f"The proposal '{initial_proposal[:50]}...' should be evaluated against {priorities[0]}."
        else:
            content += f"We should prioritize {priorities[0]} in this decision."

        return Argument(
            agent_perspective=perspective,
            argument_type=ArgumentType.PROPOSITION,
            content=content,
            evidence=[f"{perspective} best practices", bias],
            confidence=0.7,
        )

    async def _generate_challenge(
        self,
        question: str,
        perspective: str,
        arguments: list[Argument],
        context: dict[str, Any],
    ) -> Argument | None:
        """Generate a challenge to existing arguments."""
        config = Perspective.get_config(perspective)

        # Find an argument to challenge
        other_args = [a for a in arguments if a.agent_perspective != perspective]
        if not other_args:
            return None

        target = other_args[-1]  # Challenge most recent

        if self.llm_debater:
            return await self._llm_generate_argument(
                question=question,
                perspective=perspective,
                config=config,
                argument_type=ArgumentType.CHALLENGE,
                context=context,
                reference=target.content,
                responding_to=arguments.index(target),
            )

        return self._heuristic_challenge(perspective, config, target, arguments.index(target))

    def _heuristic_challenge(
        self,
        perspective: str,
        config: dict[str, Any],
        target: Argument,
        target_index: int,
    ) -> Argument:
        """Heuristic challenge generation."""
        concerns = config["concerns"]

        content = f"The {perspective} perspective challenges this: "
        content += f"Have we considered {concerns[0]}? "
        content += f"This approach may cause {concerns[1] if len(concerns) > 1 else 'issues'}."

        return Argument(
            agent_perspective=perspective,
            argument_type=ArgumentType.CHALLENGE,
            content=content,
            evidence=[f"Risk of {concerns[0]}"],
            confidence=0.65,
            responding_to=target_index,
        )

    async def _llm_generate_argument(
        self,
        question: str,
        perspective: str,
        config: dict[str, Any],
        argument_type: ArgumentType,
        context: dict[str, Any],
        reference: str | None = None,
        responding_to: int | None = None,
    ) -> Argument:
        """Use LLM to generate argument."""
        prompt = f"""
You are debating from the {perspective} perspective.

QUESTION: {question}
YOUR PRIORITIES: {config["priorities"]}
YOUR CONCERNS: {config["concerns"]}
YOUR BIAS: {config["bias"]}

ARGUMENT TYPE: {argument_type.value}
{f"REFERENCE: {reference}" if reference else ""}

Generate a {argument_type.value} argument in JSON:
{{
    "content": "Your argument",
    "evidence": ["supporting points"],
    "confidence": 0.0-1.0
}}
"""
        try:
            response = await self.llm_debater(prompt)  # type: ignore[misc]  # callable: Optional, checked at init
            data = json.loads(response)
            return Argument(
                agent_perspective=perspective,
                argument_type=argument_type,
                content=data.get("content", ""),
                evidence=data.get("evidence", []),
                confidence=float(data.get("confidence", 0.7)),
                responding_to=responding_to,
            )
        except Exception as e:
            logger.warning(f"LLM argument generation failed: {e}")
            return self._heuristic_proposition(question, perspective, config, reference)

    async def _generate_synthesis(
        self,
        question: str,
        arguments: list[Argument],
        perspectives: list[str],
    ) -> Argument:
        """Generate synthesis combining all perspectives."""
        # Collect key points from each perspective
        perspective_points: dict[str, list] = {}
        for arg in arguments:
            if arg.agent_perspective not in perspective_points:
                perspective_points[arg.agent_perspective] = []
            perspective_points[arg.agent_perspective].append(arg.content[:100])

        content = "SYNTHESIS: Combining all perspectives - "
        key_points = []

        for persp, points in perspective_points.items():
            key_points.append(f"{persp} emphasizes: {points[0][:50]}...")

        content += "; ".join(key_points[:3])

        return Argument(
            agent_perspective="synthesis",
            argument_type=ArgumentType.SYNTHESIS,
            content=content,
            evidence=[f"Input from {len(perspectives)} perspectives"],
            confidence=0.75,
        )

    async def _conduct_voting(
        self,
        question: str,
        synthesis: Argument,
        perspectives: list[str],
    ) -> list[Vote]:
        """Conduct voting on the synthesis."""
        votes = []

        for perspective in perspectives:
            config = Perspective.get_config(perspective)

            # Simple heuristic voting
            # Check if synthesis addresses their priorities
            synthesis_lower = synthesis.content.lower()
            priorities_addressed = sum(
                1 for p in config["priorities"] if p.lower() in synthesis_lower
            )

            if priorities_addressed >= 2:
                vote_type = VoteType.STRONGLY_AGREE
            elif priorities_addressed >= 1:
                vote_type = VoteType.AGREE
            else:
                vote_type = VoteType.NEUTRAL

            votes.append(
                Vote(
                    perspective=perspective,
                    vote=vote_type,
                    reasoning=f"Synthesis addresses {priorities_addressed} of my priorities",
                    conditions=[f"Must maintain focus on {config['priorities'][0]}"],
                )
            )

        return votes

    def _determine_consensus(
        self,
        votes: list[Vote],
        synthesis: Argument,
    ) -> tuple[bool, str]:
        """Determine if consensus was reached."""
        agreement_scores = {
            VoteType.STRONGLY_AGREE: 1.0,
            VoteType.AGREE: 0.75,
            VoteType.NEUTRAL: 0.5,
            VoteType.DISAGREE: 0.25,
            VoteType.STRONGLY_DISAGREE: 0.0,
        }

        if not votes:
            return False, "No votes cast"

        avg_agreement = sum(agreement_scores[v.vote] for v in votes) / len(votes)
        consensus_reached = avg_agreement >= self.CONSENSUS_THRESHOLD

        if consensus_reached:
            return True, synthesis.content
        else:
            return False, f"Partial agreement ({avg_agreement:.0%}): {synthesis.content}"

    def _calculate_confidence(self, votes: list[Vote]) -> float:
        """Calculate confidence from votes."""
        if not votes:
            return 0.5

        agreement_scores = {
            VoteType.STRONGLY_AGREE: 1.0,
            VoteType.AGREE: 0.75,
            VoteType.NEUTRAL: 0.5,
            VoteType.DISAGREE: 0.25,
            VoteType.STRONGLY_DISAGREE: 0.0,
        }

        return sum(agreement_scores[v.vote] for v in votes) / len(votes)

    def _get_dissenting_views(
        self,
        votes: list[Vote],
        arguments: list[Argument],
    ) -> list[str]:
        """Get dissenting views from the debate."""
        dissenting = []

        for vote in votes:
            if vote.vote in [VoteType.DISAGREE, VoteType.STRONGLY_DISAGREE]:
                dissenting.append(f"{vote.perspective}: {vote.reasoning}")

        # Also include strong challenges
        for arg in arguments:
            if arg.argument_type == ArgumentType.CHALLENGE and arg.confidence > 0.7:
                dissenting.append(f"{arg.agent_perspective} challenge: {arg.content[:100]}")

        return dissenting[:5]

    def _extract_insights(self, arguments: list[Argument]) -> list[str]:
        """Extract key insights from debate."""
        insights = []

        # Get high-confidence arguments
        strong_args = [a for a in arguments if a.confidence >= 0.75]

        for arg in strong_args[:3]:
            insights.append(f"[{arg.agent_perspective}] {arg.content[:100]}")

        # Get evidence points
        all_evidence = []
        for arg in arguments:
            all_evidence.extend(arg.evidence)

        # Unique evidence
        unique_evidence = list(set(all_evidence))[:3]
        insights.extend(unique_evidence)

        return insights[:5]

    def _identify_tensions(self, arguments: list[Argument]) -> list[str]:
        """Identify unresolved tensions."""
        tensions = []

        # Find challenge-rebuttal pairs without resolution
        challenges = [a for a in arguments if a.argument_type == ArgumentType.CHALLENGE]

        for challenge in challenges:
            # Check if there's a corresponding rebuttal or concession
            rebuttals = [
                a
                for a in arguments
                if a.responding_to == arguments.index(challenge)
                and a.argument_type in [ArgumentType.REBUTTAL, ArgumentType.CONCESSION]
            ]

            if not rebuttals:
                tensions.append(
                    f"Unaddressed challenge from {challenge.agent_perspective}: {challenge.content[:80]}"
                )

        return tensions[:3]

    def _recommend_action(
        self,
        consensus: bool,
        position: str,
        tensions: list[str],
    ) -> str:
        """Generate recommended action."""
        if consensus and not tensions:
            return f"PROCEED: Consensus reached. {position[:100]}"
        elif consensus and tensions:
            return f"PROCEED WITH CAUTION: Consensus reached but unresolved tensions exist. Address: {tensions[0][:50]}"
        else:
            return f"ESCALATE: No consensus. Recommend human decision on: {position[:50]}"

    async def _save_debate(self, result: DebateResult) -> None:
        """Save debate result."""
        try:
            filename = f"debate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.memory_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

            # Save summary
            summary_path = self.memory_dir / filename.replace(".json", "_summary.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(result.to_summary())
        except Exception as e:
            logger.warning(f"Failed to save debate: {e}")


# Quick debate function
async def quick_debate(
    question: str,
    perspectives: list[str] | None = None,
) -> DebateResult:
    """Quick multi-agent debate."""
    debate = MultiAgentDebate()
    return await debate.debate(
        question=question,
        perspectives=perspectives or ["architect", "security", "pragmatist"],
    )
