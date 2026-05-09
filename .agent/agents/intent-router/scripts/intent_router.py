#!/usr/bin/env python3
"""
Intent Router Agent.

Routes requests to optimal agents based on intent analysis.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("intent-router")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class IntentType(Enum):
    """Types of user intent."""

    CREATE = "create"
    FIX = "fix"
    ANALYZE = "analyze"
    REFACTOR = "refactor"
    TEST = "test"
    DOCUMENT = "document"
    DEPLOY = "deploy"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class RoutingDecision:
    """A routing decision."""

    intent: IntentType
    confidence: float
    primary_agent: str
    backup_agents: list[str]
    reasoning: str
    estimated_complexity: str

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "primary_agent": self.primary_agent,
            "backup_agents": self.backup_agents,
            "reasoning": self.reasoning,
            "estimated_complexity": self.estimated_complexity,
        }


class IntentRouter:
    """
    Routes requests to optimal agents.
    """

    def __init__(self):
        self.routing_history: list[RoutingDecision] = []

        # Agent capabilities
        self.agent_capabilities = {
            "architect": ["design", "architecture", "structure", "plan"],
            "frontend-specialist": ["react", "vue", "ui", "css", "html"],
            "backend-specialist": ["api", "server", "database", "endpoint"],
            "security-auditor": ["security", "auth", "vulnerability"],
            "test-engineer": ["test", "coverage", "spec"],
            "debugger": ["debug", "fix", "error", "bug"],
            "refactor": ["refactor", "improve", "clean", "optimize"],
            "documentation-writer": ["document", "readme", "explain"],
            "explorer": ["analyze", "investigate", "find", "search"],
            "devops-engineer": ["deploy", "ci", "docker", "kubernetes"],
        }

        # Intent to agent mapping
        self.intent_agents = {
            IntentType.CREATE: ["architect", "frontend-specialist", "backend-specialist"],
            IntentType.FIX: ["debugger", "backend-specialist", "frontend-specialist"],
            IntentType.ANALYZE: ["explorer", "security-auditor", "code-reviewer"],
            IntentType.REFACTOR: ["refactor", "architect", "code-reviewer"],
            IntentType.TEST: ["test-engineer", "qa-specialist"],
            IntentType.DOCUMENT: ["documentation-writer", "docusaurus-expert"],
            IntentType.DEPLOY: ["devops-engineer", "mcp-integrator"],
            IntentType.HELP: ["explorer", "documentation-writer"],
            IntentType.UNKNOWN: ["explorer", "planner"],
        }

    def _detect_intent(self, request: str) -> tuple[IntentType, float]:
        """Detect intent from request."""
        request_lower = request.lower()

        intent_keywords = {
            IntentType.CREATE: ["create", "add", "implement", "build", "make", "new"],
            IntentType.FIX: ["fix", "bug", "error", "broken", "issue", "problem"],
            IntentType.ANALYZE: ["analyze", "review", "check", "audit", "investigate"],
            IntentType.REFACTOR: ["refactor", "improve", "clean", "optimize"],
            IntentType.TEST: ["test", "spec", "coverage", "verify"],
            IntentType.DOCUMENT: ["document", "readme", "explain", "describe"],
            IntentType.DEPLOY: ["deploy", "release", "publish", "ship"],
            IntentType.HELP: ["help", "how", "what", "?"],
        }

        scores = {}
        for intent, keywords in intent_keywords.items():
            score = sum(1 for kw in keywords if kw in request_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            return IntentType.UNKNOWN, 0.5

        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent] / 3, 0.95)
        return best_intent, confidence

    def _select_agents(self, intent: IntentType, request: str) -> tuple[str, list[str]]:
        """Select primary and backup agents."""
        candidates = self.intent_agents.get(intent, self.intent_agents[IntentType.UNKNOWN])
        request_lower = request.lower()

        # Score candidates based on capability match
        scored = []
        for agent in candidates:
            capabilities = self.agent_capabilities.get(agent, [])
            score = sum(1 for cap in capabilities if cap in request_lower)
            scored.append((agent, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        agents = [a for a, _ in scored]

        return agents[0], agents[1:3]

    def _estimate_complexity(self, request: str) -> str:
        """Estimate request complexity."""
        word_count = len(request.split())

        if word_count < 10:
            return "simple"
        elif word_count < 30:
            return "moderate"
        else:
            return "complex"

    async def route(self, request: str, context: dict | None = None) -> RoutingDecision:
        """
        Route request to optimal agent.

        Args:
            request: User request
            context: Additional context

        Returns:
            Routing decision
        """
        # Detect intent
        intent, confidence = self._detect_intent(request)

        # Select agents
        primary, backups = self._select_agents(intent, request)

        # Estimate complexity
        complexity = self._estimate_complexity(request)

        # Generate reasoning
        reasoning = f"Detected {intent.value} intent with {confidence:.0%} confidence. "
        reasoning += f"Routing to {primary} based on capability match."

        decision = RoutingDecision(
            intent=intent,
            confidence=confidence,
            primary_agent=primary,
            backup_agents=backups,
            reasoning=reasoning,
            estimated_complexity=complexity,
        )

        self.routing_history.append(decision)
        return decision


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Intent Router Agent")
    parser.add_argument("request", nargs="?", help="Request to route")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.request:
        parser.print_help()
        return

    router = IntentRouter()
    decision = await router.route(args.request)

    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print(f"Intent: {decision.intent.value} ({decision.confidence:.0%})")
        print(f"Primary Agent: {decision.primary_agent}")
        print(f"Backups: {', '.join(decision.backup_agents)}")
        print(f"Complexity: {decision.estimated_complexity}")
        print(f"\nReasoning: {decision.reasoning}")


if __name__ == "__main__":
    asyncio.run(main())
