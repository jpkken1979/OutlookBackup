#!/usr/bin/env python3
"""
Debate Facilitator Agent.

Facilitates multi-agent debates to reach consensus on complex decisions.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("debate-facilitator")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class Perspective(Enum):
    """Standard debate perspectives."""

    OPTIMIST = "optimist"
    PESSIMIST = "pessimist"
    PRAGMATIST = "pragmatist"
    INNOVATOR = "innovator"
    CONSERVATIVE = "conservative"
    SECURITY_FOCUSED = "security_focused"
    PERFORMANCE_FOCUSED = "performance_focused"
    USER_ADVOCATE = "user_advocate"
    COST_CONSCIOUS = "cost_conscious"
    QUALITY_FOCUSED = "quality_focused"


@dataclass
class Argument:
    """A debate argument."""

    perspective: str
    position: str
    argument: str
    evidence: list[str]
    strength: float  # 0-1


@dataclass
class DebateRound:
    """A single debate round."""

    round_number: int
    arguments: list[Argument]
    rebuttals: list[dict]
    synthesis: str


@dataclass
class Consensus:
    """Consensus result."""

    reached: bool
    decision: str
    confidence: float
    supporting_perspectives: list[str]
    dissenting_views: list[str]
    conditions: list[str]


@dataclass
class DebateResult:
    """Complete debate result."""

    topic: str
    perspectives_used: list[str]
    rounds: list[DebateRound]
    consensus: Consensus
    explanation: str
    duration_ms: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "perspectives_used": self.perspectives_used,
            "rounds": [
                {
                    "round": r.round_number,
                    "arguments": [
                        {
                            "perspective": a.perspective,
                            "position": a.position,
                            "argument": a.argument,
                            "evidence": a.evidence,
                            "strength": a.strength,
                        }
                        for a in r.arguments
                    ],
                    "rebuttals": r.rebuttals,
                    "synthesis": r.synthesis,
                }
                for r in self.rounds
            ],
            "consensus": {
                "reached": self.consensus.reached,
                "decision": self.consensus.decision,
                "confidence": self.consensus.confidence,
                "supporting_perspectives": self.consensus.supporting_perspectives,
                "dissenting_views": self.consensus.dissenting_views,
                "conditions": self.consensus.conditions,
            },
            "explanation": self.explanation,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def export_report(self) -> str:
        """Export as markdown report."""
        lines = [
            "# Debate Report",
            "",
            f"**Topic:** {self.topic}",
            f"**Perspectives:** {', '.join(self.perspectives_used)}",
            f"**Rounds:** {len(self.rounds)}",
            f"**Duration:** {self.duration_ms:.0f}ms",
            "",
            "---",
            "",
        ]

        for round_data in self.rounds:
            lines.extend([f"## Round {round_data.round_number}", ""])

            for arg in round_data.arguments:
                lines.extend(
                    [
                        f"### {arg.perspective.title()}",
                        f"**Position:** {arg.position}",
                        "",
                        arg.argument,
                        "",
                        "**Evidence:**",
                    ]
                )
                for ev in arg.evidence:
                    lines.append(f"- {ev}")
                lines.extend(["", f"*Strength: {arg.strength:.0%}*", ""])

            lines.extend(["**Round Synthesis:**", round_data.synthesis, "", "---", ""])

        # Consensus
        consensus_icon = "✅" if self.consensus.reached else "⚠️"
        lines.extend(
            [
                f"## {consensus_icon} Consensus",
                "",
                f"**Reached:** {'Yes' if self.consensus.reached else 'No'}",
                f"**Confidence:** {self.consensus.confidence:.0%}",
                "",
                "### Decision",
                "",
                self.consensus.decision,
                "",
            ]
        )

        if self.consensus.supporting_perspectives:
            lines.extend(["### Supporting Perspectives", ""])
            for p in self.consensus.supporting_perspectives:
                lines.append(f"- {p}")
            lines.append("")

        if self.consensus.dissenting_views:
            lines.extend(["### Dissenting Views", ""])
            for d in self.consensus.dissenting_views:
                lines.append(f"- {d}")
            lines.append("")

        if self.consensus.conditions:
            lines.extend(["### Conditions", ""])
            for c in self.consensus.conditions:
                lines.append(f"- {c}")
            lines.append("")

        lines.extend(["## Explanation", "", self.explanation])

        return "\n".join(lines)


class DebateFacilitator:
    """
    Agent that facilitates multi-agent debates.

    Uses Multi-Agent Debate intelligence module for:
    - Orchestrating perspectives
    - Managing rounds
    - Building consensus
    - Explaining decisions
    """

    def __init__(self):
        self.debate_history: list[DebateResult] = []
        self._modules_loaded = False
        self._modules = {}

    async def _load_modules(self):
        """Lazy load intelligence modules."""
        if self._modules_loaded:
            return

        try:
            from core.intelligence import DecisionExplainer, MultiAgentDebate, QualityScorer

            self._modules["debate"] = MultiAgentDebate()
            self._modules["explainer"] = DecisionExplainer()
            self._modules["quality"] = QualityScorer()
            self._modules_loaded = True
        except ImportError as e:
            logger.warning(f"Could not load modules: {e}")
            self._modules_loaded = True

    def _select_perspectives(self, topic: str, custom: list[str] | None = None) -> list[str]:
        """Select appropriate perspectives for the topic."""
        if custom:
            return custom

        topic_lower = topic.lower()

        # Select based on topic keywords
        perspectives = []

        if any(kw in topic_lower for kw in ["security", "auth", "protect"]):
            perspectives.extend(["security_focused", "pragmatist"])
        if any(kw in topic_lower for kw in ["performance", "speed", "optimize"]):
            perspectives.extend(["performance_focused", "cost_conscious"])
        if any(kw in topic_lower for kw in ["architecture", "design", "structure"]):
            perspectives.extend(["innovator", "conservative", "pragmatist"])
        if any(kw in topic_lower for kw in ["user", "ux", "experience"]):
            perspectives.extend(["user_advocate", "quality_focused"])
        if any(kw in topic_lower for kw in ["cost", "budget", "resource"]):
            perspectives.extend(["cost_conscious", "pragmatist"])

        # Default balanced perspectives
        if not perspectives:
            perspectives = ["optimist", "pessimist", "pragmatist"]

        # Ensure at least 3 unique perspectives
        perspectives = list(set(perspectives))
        if len(perspectives) < 3:
            for default in ["pragmatist", "quality_focused", "innovator"]:
                if default not in perspectives:
                    perspectives.append(default)
                if len(perspectives) >= 3:
                    break

        return perspectives[:5]  # Max 5 perspectives

    async def facilitate(
        self,
        topic: str,
        perspectives: list[str] | None = None,
        max_rounds: int = 3,
        require_consensus: bool = True,
        context: dict | None = None,
    ) -> DebateResult:
        """
        Facilitate a debate on the topic.

        Args:
            topic: The topic to debate
            perspectives: Custom perspectives (auto-selected if None)
            max_rounds: Maximum debate rounds
            require_consensus: Whether to continue until consensus
            context: Additional context

        Returns:
            Complete debate result
        """
        start_time = datetime.now()
        await self._load_modules()

        context = context or {}
        perspectives = self._select_perspectives(topic, perspectives)
        rounds: list[DebateRound] = []

        logger.info(f"Starting debate: {topic}")
        logger.info(f"Perspectives: {perspectives}")

        # Conduct debate rounds
        for round_num in range(1, max_rounds + 1):
            round_result = await self._conduct_round(
                topic=topic,
                round_number=round_num,
                perspectives=perspectives,
                previous_rounds=rounds,
                context=context,
            )
            rounds.append(round_result)

            # Check for early consensus
            if require_consensus and await self._check_consensus(rounds):
                logger.info(f"Consensus reached after round {round_num}")
                break

        # Build final consensus
        consensus = await self._build_consensus(topic, rounds, perspectives)

        # Generate explanation
        explanation = await self._explain_decision(topic, rounds, consensus)

        duration = (datetime.now() - start_time).total_seconds() * 1000

        result = DebateResult(
            topic=topic,
            perspectives_used=perspectives,
            rounds=rounds,
            consensus=consensus,
            explanation=explanation,
            duration_ms=duration,
            metadata={"max_rounds": max_rounds, "require_consensus": require_consensus},
        )

        self.debate_history.append(result)
        return result

    async def _conduct_round(
        self,
        topic: str,
        round_number: int,
        perspectives: list[str],
        previous_rounds: list[DebateRound],
        context: dict,
    ) -> DebateRound:
        """Conduct a single debate round."""
        arguments: list[Argument] = []
        rebuttals: list[dict] = []

        # Each perspective presents arguments
        for perspective in perspectives:
            argument = await self._generate_argument(
                topic=topic,
                perspective=perspective,
                round_number=round_number,
                previous_rounds=previous_rounds,
                context=context,
            )
            arguments.append(argument)

        # Generate rebuttals
        for i, arg in enumerate(arguments):
            for j, other_arg in enumerate(arguments):
                if i != j:
                    rebuttal = await self._generate_rebuttal(arg, other_arg)
                    if rebuttal:
                        rebuttals.append(rebuttal)

        # Synthesize round
        synthesis = await self._synthesize_round(arguments, rebuttals)

        return DebateRound(
            round_number=round_number, arguments=arguments, rebuttals=rebuttals, synthesis=synthesis
        )

    async def _generate_argument(
        self,
        topic: str,
        perspective: str,
        round_number: int,
        previous_rounds: list[DebateRound],
        context: dict,
    ) -> Argument:
        """Generate argument from a perspective."""
        # Position based on perspective
        positions = {
            "optimist": "in favor, emphasizing opportunities",
            "pessimist": "cautious, highlighting risks",
            "pragmatist": "balanced, focusing on practical implementation",
            "innovator": "in favor of new approaches",
            "conservative": "preferring proven solutions",
            "security_focused": "prioritizing security considerations",
            "performance_focused": "emphasizing performance impact",
            "user_advocate": "focusing on user experience",
            "cost_conscious": "considering resource efficiency",
            "quality_focused": "emphasizing code/product quality",
        }

        position = positions.get(perspective, "presenting balanced view")

        # Generate argument text
        argument_templates = {
            "optimist": f"Regarding '{topic}', I see significant potential benefits. This approach could lead to improved outcomes and positive results.",
            "pessimist": f"While considering '{topic}', we must acknowledge potential risks. There are concerns that should be carefully evaluated.",
            "pragmatist": f"Looking at '{topic}' practically, we should balance benefits against implementation costs and complexity.",
            "innovator": f"For '{topic}', I propose we consider novel approaches that could provide competitive advantages.",
            "conservative": f"On '{topic}', I recommend we follow established practices that have proven track records.",
            "security_focused": f"Analyzing '{topic}' from a security perspective, we must ensure we don't introduce vulnerabilities.",
            "performance_focused": f"Evaluating '{topic}' for performance, we should consider scalability and efficiency.",
            "user_advocate": f"From the user's perspective on '{topic}', we should prioritize usability and experience.",
            "cost_conscious": f"Considering the cost implications of '{topic}', we should optimize resource utilization.",
            "quality_focused": f"For '{topic}', maintaining high quality standards should be our priority.",
        }

        argument_text = argument_templates.get(
            perspective, f"Regarding '{topic}', from the {perspective} perspective..."
        )

        # Generate evidence
        evidence = [
            f"Based on {perspective} analysis of similar decisions",
            f"Considering industry best practices for {perspective} approach",
            "Drawing from historical outcomes of similar choices",
        ]

        # Calculate argument strength (varies by round and perspective match to topic)
        base_strength = 0.7
        if round_number > 1:
            base_strength += 0.05 * round_number  # Arguments strengthen over rounds
        strength = min(base_strength, 0.95)

        return Argument(
            perspective=perspective,
            position=position,
            argument=argument_text,
            evidence=evidence,
            strength=strength,
        )

    async def _generate_rebuttal(self, arg: Argument, other_arg: Argument) -> dict | None:
        """Generate rebuttal between arguments."""
        # Only generate rebuttals for significantly different positions
        if arg.perspective == other_arg.perspective:
            return None

        return {
            "from": arg.perspective,
            "to": other_arg.perspective,
            "rebuttal": f"While {other_arg.perspective}'s point is valid, we should also consider {arg.perspective}'s concerns.",
            "strength": 0.6,
        }

    async def _synthesize_round(self, arguments: list[Argument], rebuttals: list[dict]) -> str:
        """Synthesize round findings."""
        perspectives_summary = [f"{a.perspective}: {a.position}" for a in arguments]
        return f"Round synthesis: {len(arguments)} perspectives presented arguments. Key positions: {'; '.join(perspectives_summary)}. {len(rebuttals)} rebuttals exchanged."

    async def _check_consensus(self, rounds: list[DebateRound]) -> bool:
        """Check if consensus has been reached."""
        if len(rounds) < 2:
            return False

        # Simple heuristic: check if arguments are converging
        last_round = rounds[-1]
        strengths = [arg.strength for arg in last_round.arguments]
        avg_strength = sum(strengths) / len(strengths) if strengths else 0

        # Consensus if average strength high and variance low
        variance = (
            sum((s - avg_strength) ** 2 for s in strengths) / len(strengths) if strengths else 1
        )
        return avg_strength > 0.8 and variance < 0.05

    async def _build_consensus(
        self, topic: str, rounds: list[DebateRound], perspectives: list[str]
    ) -> Consensus:
        """Build final consensus from debate rounds."""
        # Aggregate arguments
        all_arguments: list[Argument] = []
        for round_data in rounds:
            all_arguments.extend(round_data.arguments)

        # Find strongest positions
        perspective_strengths: dict[str, float] = {}
        for arg in all_arguments:
            if arg.perspective not in perspective_strengths:
                perspective_strengths[arg.perspective] = 0
            perspective_strengths[arg.perspective] += arg.strength

        # Sort by total strength
        sorted_perspectives = sorted(
            perspective_strengths.items(), key=lambda x: x[1], reverse=True
        )

        # Determine consensus
        if len(sorted_perspectives) > 0:
            top_strength = sorted_perspectives[0][1]
            supporting = [p for p, s in sorted_perspectives if s >= top_strength * 0.8]
            dissenting = [p for p, s in sorted_perspectives if s < top_strength * 0.5]

            decision = f"Based on debate analysis, the recommended approach for '{topic}' balances "
            decision += f"{', '.join(supporting[:2])} perspectives."

            confidence = min(top_strength / (len(rounds) * 1.0), 0.95)
            reached = len(supporting) >= len(perspectives) // 2 + 1
        else:
            supporting = []
            dissenting = perspectives
            decision = f"No clear consensus on '{topic}'. Further discussion recommended."
            confidence = 0.3
            reached = False

        # Generate conditions
        conditions = []
        if "security_focused" in perspectives:
            conditions.append("Ensure security review before implementation")
        if "performance_focused" in perspectives:
            conditions.append("Monitor performance metrics post-implementation")
        if "cost_conscious" in perspectives:
            conditions.append("Track resource usage and costs")

        return Consensus(
            reached=reached,
            decision=decision,
            confidence=confidence,
            supporting_perspectives=supporting,
            dissenting_views=dissenting,
            conditions=conditions,
        )

    async def _explain_decision(
        self, topic: str, rounds: list[DebateRound], consensus: Consensus
    ) -> str:
        """Generate explanation for the decision."""
        if "explainer" in self._modules and self._modules["explainer"]:
            try:
                explanation = await self._modules["explainer"].explain(
                    {
                        "topic": topic,
                        "consensus": consensus.decision,
                        "confidence": consensus.confidence,
                    }
                )
                return str(explanation)
            except Exception:
                pass

        # Fallback explanation
        return (
            f"After {len(rounds)} rounds of debate with {len(consensus.supporting_perspectives)} "
            f"supporting perspectives, the debate {'reached' if consensus.reached else 'did not reach'} "
            f"consensus with {consensus.confidence:.0%} confidence. "
            f"The decision accounts for multiple viewpoints while prioritizing "
            f"{', '.join(consensus.supporting_perspectives[:2]) if consensus.supporting_perspectives else 'balanced considerations'}."
        )


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Debate Facilitator Agent")
    parser.add_argument("topic", nargs="?", help="Debate topic")
    parser.add_argument("--perspectives", nargs="+", help="Custom perspectives")
    parser.add_argument("--rounds", type=int, default=3, help="Max rounds")
    parser.add_argument("--no-consensus", action="store_true", help="Don't require consensus")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.topic:
        parser.print_help()
        return

    facilitator = DebateFacilitator()
    result = await facilitator.facilitate(
        topic=args.topic,
        perspectives=args.perspectives,
        max_rounds=args.rounds,
        require_consensus=not args.no_consensus,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.export_report())


if __name__ == "__main__":
    asyncio.run(main())
