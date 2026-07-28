#!/usr/bin/env python3
"""
Agent Capability Registry - Queryable registry of agent abilities.

Provides:
- Agent capability discovery
- Skill matching
- Agent recommendations
- Capability search

Usage:
    from capability_registry import CapabilityRegistry

    registry = CapabilityRegistry()
    registry.load_agents()

    # Find agents for a task
    agents = registry.find_agents_for_task("Build REST API with authentication")

    # Get agent capabilities
    caps = registry.get_capabilities("architect")

    # Search by capability
    agents = registry.search_by_capability("security")
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class AgentCapability:
    """Agent capability definition."""

    name: str
    description: str
    tier: int
    tools: list[str]
    skills: list[str]
    capabilities: list[str]
    triggers: list[str]
    personality: str = "professional"
    guardrails: str = "enabled"
    model: str = "inherit"


@dataclass
class CapabilityMatch:
    """Match result for capability search."""

    agent: str
    score: float
    matched_capabilities: list[str]
    matched_triggers: list[str]
    tier: int


class CapabilityRegistry:
    """
    Registry for agent capabilities and discovery.

    Loads agent definitions and provides search/matching functionality.
    """

    # Capability categories
    CAPABILITY_CATEGORIES = {
        "development": ["coding", "implementation", "development", "programming"],
        "architecture": ["design", "architecture", "system", "structure"],
        "testing": ["test", "qa", "quality", "validation"],
        "security": ["security", "audit", "vulnerability", "pentest"],
        "devops": ["deploy", "ci/cd", "infrastructure", "docker", "kubernetes"],
        "documentation": ["docs", "documentation", "readme", "guide"],
        "analysis": ["analyze", "review", "audit", "inspect"],
        "optimization": ["performance", "optimize", "speed", "efficiency"],
        "data": ["data", "database", "sql", "etl", "pipeline"],
        "frontend": ["ui", "ux", "frontend", "react", "css", "design"],
        "backend": ["api", "backend", "server", "rest", "graphql"],
        "mobile": ["mobile", "ios", "android", "react native", "flutter"],
    }

    def __init__(self, agents_path: str | None = None):
        """
        Initialize capability registry.

        Args:
            agents_path: Path to agents directory. Defaults to .agent/agents/
        """
        if agents_path:
            self.agents_path = Path(agents_path)
        else:
            # capability_registry.py is in .agent/core/, agents is in .agent/agents/
            self.agents_path = Path(__file__).parent.parent / "agents"

        self.agents: dict[str, AgentCapability] = {}
        self._loaded = False

    def load_agents(self, force: bool = False) -> int:
        """
        Load agent definitions from IDENTITY.md files.

        Args:
            force: Force reload even if already loaded

        Returns:
            Number of agents loaded
        """
        if self._loaded and not force:
            return len(self.agents)

        self.agents = {}

        for agent_dir in self.agents_path.iterdir():
            if not agent_dir.is_dir():
                continue
            if agent_dir.name.startswith("_"):
                continue

            identity_file = agent_dir / "IDENTITY.md"
            if not identity_file.exists():
                continue

            try:
                capability = self._parse_identity(identity_file)
                if capability:
                    self.agents[capability.name] = capability
            except Exception as e:
                logger.debug(f"Could not parse {identity_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self.agents)} agents into capability registry")
        return len(self.agents)

    def _parse_identity(self, identity_file: Path) -> AgentCapability | None:
        """Parse IDENTITY.md file to extract capabilities."""
        content = identity_file.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = parts[2]
            else:
                return None
        else:
            return None

        # Extract fields from frontmatter
        name_match = re.search(r"name:\s*(.+)", frontmatter)
        desc_match = re.search(r"description:\s*(.+)", frontmatter)
        tools_match = re.search(r"tools:\s*(.+)", frontmatter)
        skills_match = re.search(r"skills:\s*(.+)", frontmatter)
        tier_match = re.search(r"tier:\s*(\d+)", frontmatter)
        personality_match = re.search(r"personality:\s*(\w+)", frontmatter)
        guardrails_match = re.search(r"guardrails:\s*(\w+)", frontmatter)

        if not name_match:
            return None

        name = name_match.group(1).strip()
        description = desc_match.group(1).strip() if desc_match else ""
        tools = [t.strip() for t in tools_match.group(1).split(",")] if tools_match else []
        skills = [s.strip() for s in skills_match.group(1).split(",")] if skills_match else []
        tier = int(tier_match.group(1)) if tier_match else 5
        personality = personality_match.group(1) if personality_match else "professional"
        guardrails = guardrails_match.group(1) if guardrails_match else "enabled"

        # Extract capabilities from body (look for keywords)
        capabilities = self._extract_capabilities(body)

        # Extract triggers from description
        triggers = self._extract_triggers(description)

        return AgentCapability(
            name=name,
            description=description,
            tier=tier,
            tools=tools,
            skills=skills,
            capabilities=capabilities,
            triggers=triggers,
            personality=personality,
            guardrails=guardrails,
        )

    def _extract_capabilities(self, content: str) -> list[str]:
        """Extract capability keywords from content."""
        capabilities = []
        content_lower = content.lower()

        for category, keywords in self.CAPABILITY_CATEGORIES.items():
            if any(kw in content_lower for kw in keywords):
                capabilities.append(category)

        # Also extract from headers
        headers = re.findall(r"##\s+(.+)", content)
        for header in headers:
            header_lower = header.lower()
            if any(word in header_lower for word in ["skill", "capabilit", "feature", "function"]):
                capabilities.append(header.strip())

        return list(set(capabilities))

    def _extract_triggers(self, description: str) -> list[str]:
        """Extract trigger words from description."""
        # Look for "Triggers on" pattern
        trigger_match = re.search(r"[Tt]riggers?\s+on\s+(.+?)\.", description)
        if trigger_match:
            triggers = [t.strip() for t in trigger_match.group(1).split(",")]
            return triggers

        # Fall back to extracting key verbs
        verbs = [
            "build",
            "create",
            "analyze",
            "review",
            "test",
            "deploy",
            "design",
            "fix",
            "optimize",
        ]
        found = [v for v in verbs if v in description.lower()]
        return found

    def get_all_agents(self) -> list[str]:
        """Get list of all registered agents."""
        self.load_agents()
        return list(self.agents.keys())

    def get_capabilities(self, agent_name: str) -> AgentCapability | None:
        """
        Get capabilities for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentCapability or None if not found
        """
        self.load_agents()
        return self.agents.get(agent_name)

    def search_by_capability(self, capability: str) -> list[AgentCapability]:
        """
        Search agents by capability.

        Args:
            capability: Capability to search for

        Returns:
            List of agents with matching capability
        """
        self.load_agents()
        capability_lower = capability.lower()

        results = []
        for agent in self.agents.values():
            if (
                any(capability_lower in cap.lower() for cap in agent.capabilities)
                or capability_lower in agent.description.lower()
            ):
                results.append(agent)

        return results

    def search_by_skill(self, skill: str) -> list[AgentCapability]:
        """
        Search agents by skill.

        Args:
            skill: Skill name to search for

        Returns:
            List of agents with matching skill
        """
        self.load_agents()
        skill_lower = skill.lower()

        return [
            agent
            for agent in self.agents.values()
            if any(skill_lower in s.lower() for s in agent.skills)
        ]

    def find_agents_for_task(self, task_description: str, limit: int = 5) -> list[CapabilityMatch]:
        """
        Find best agents for a given task.

        Args:
            task_description: Description of the task
            limit: Maximum number of agents to return

        Returns:
            List of CapabilityMatch ordered by score
        """
        self.load_agents()
        task_lower = task_description.lower()
        task_words = set(task_lower.split())

        matches = []

        for agent in self.agents.values():
            score = 0.0
            matched_caps = []
            matched_triggers = []

            # Check triggers
            for trigger in agent.triggers:
                if trigger.lower() in task_lower:
                    score += 2.0
                    matched_triggers.append(trigger)

            # Check capabilities
            for cap in agent.capabilities:
                if cap.lower() in task_lower:
                    score += 1.5
                    matched_caps.append(cap)

            # Check description keywords
            desc_words = set(agent.description.lower().split())
            overlap = task_words & desc_words
            score += len(overlap) * 0.2

            # Check skills
            for skill in agent.skills:
                if skill.lower() in task_lower:
                    score += 1.0
                    matched_caps.append(f"skill:{skill}")

            # Bonus for lower tier (more specialized)
            if score > 0:
                score += (10 - agent.tier) * 0.1

            if score > 0:
                matches.append(
                    CapabilityMatch(
                        agent=agent.name,
                        score=round(score, 2),
                        matched_capabilities=matched_caps,
                        matched_triggers=matched_triggers,
                        tier=agent.tier,
                    )
                )

        # Sort by score (descending) then by tier (ascending)
        matches.sort(key=lambda x: (-x.score, x.tier))
        return matches[:limit]

    def get_agents_by_tier(self, tier: int) -> list[AgentCapability]:
        """
        Get all agents in a specific tier.

        Args:
            tier: Tier number (1-9)

        Returns:
            List of agents in that tier
        """
        self.load_agents()
        return [agent for agent in self.agents.values() if agent.tier == tier]

    def get_tier_summary(self) -> dict[int, list[str]]:
        """
        Get summary of agents by tier.

        Returns:
            Dict mapping tier number to list of agent names
        """
        self.load_agents()
        summary: dict[int, list[str]] = {}

        for agent in self.agents.values():
            if agent.tier not in summary:
                summary[agent.tier] = []
            summary[agent.tier].append(agent.name)

        return dict(sorted(summary.items()))

    def export_registry(self, output_path: str | None = None) -> str:
        """
        Export registry to JSON.

        Args:
            output_path: Optional file path to write to

        Returns:
            JSON string of registry
        """
        self.load_agents()

        data = {
            "agents": {name: asdict(cap) for name, cap in self.agents.items()},
            "tier_summary": self.get_tier_summary(),
            "capability_categories": self.CAPABILITY_CATEGORIES,
            "total_agents": len(self.agents),
        }

        json_str = json.dumps(data, indent=2)

        if output_path:
            Path(output_path).write_text(json_str)
            logger.info(f"Exported registry to {output_path}")

        return json_str


# Global instance
_global_registry: CapabilityRegistry | None = None


def get_registry() -> CapabilityRegistry:
    """Get global capability registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CapabilityRegistry()
        _global_registry.load_agents()
    return _global_registry


if __name__ == "__main__":
    # Demo
    registry = CapabilityRegistry()
    registry.load_agents()

    print(f"Total agents: {len(registry.agents)}")
    print(f"\nTier summary: {json.dumps(registry.get_tier_summary(), indent=2)}")

    # Find agents for a task
    task = "Build a REST API with OAuth2 authentication"
    matches = registry.find_agents_for_task(task)
    print(f"\nBest agents for '{task}':")
    for match in matches:
        print(f"  - {match.agent} (score: {match.score}, tier: {match.tier})")

    # Search by capability
    security_agents = registry.search_by_capability("security")
    print(f"\nSecurity agents: {[a.name for a in security_agents]}")
