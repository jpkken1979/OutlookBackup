"""
Federated Learning - Cross-Agent Learning Propagation

Enables agents to share learnings with similar agents:
- Identify similar agents by capabilities
- Propagate successful strategies
- Aggregate learnings across agent groups
- Calculate relevance scores

Version: 1.0.0
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LearningCategory(Enum):
    """Categories of learnable knowledge."""

    STRATEGY = "strategy"  # Execution strategies
    PATTERN = "pattern"  # Code/design patterns
    ERROR_HANDLING = "error_handling"  # Error recovery
    OPTIMIZATION = "optimization"  # Performance improvements
    BEST_PRACTICE = "best_practice"  # General best practices
    TOOL_USAGE = "tool_usage"  # How to use tools effectively


class PropagationStatus(Enum):
    """Status of learning propagation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class LearnedStrategy:
    """A strategy learned from execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: LearningCategory = LearningCategory.STRATEGY
    name: str = ""
    description: str = ""
    source_agent: str = ""
    context: dict = field(default_factory=dict)  # When this applies
    implementation: dict = field(default_factory=dict)  # How to apply
    success_rate: float = 0.0
    sample_size: int = 0
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "source_agent": self.source_agent,
            "context": self.context,
            "implementation": self.implementation,
            "success_rate": self.success_rate,
            "sample_size": self.sample_size,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearnedStrategy":
        strategy = cls()
        strategy.id = data.get("id", strategy.id)
        strategy.category = LearningCategory(data.get("category", "strategy"))
        strategy.name = data.get("name", "")
        strategy.description = data.get("description", "")
        strategy.source_agent = data.get("source_agent", "")
        strategy.context = data.get("context", {})
        strategy.implementation = data.get("implementation", {})
        strategy.success_rate = data.get("success_rate", 0.0)
        strategy.sample_size = data.get("sample_size", 0)
        strategy.confidence = data.get("confidence", 0.5)
        strategy.tags = data.get("tags", [])
        strategy.metadata = data.get("metadata", {})
        return strategy


@dataclass
class PropagationRecord:
    """Record of learning propagation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    learning_id: str = ""
    from_agent: str = ""
    to_agents: list = field(default_factory=list)
    status: PropagationStatus = PropagationStatus.PENDING
    accepted_by: list = field(default_factory=list)
    rejected_by: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "learning_id": self.learning_id,
            "from_agent": self.from_agent,
            "to_agents": self.to_agents,
            "status": self.status.value,
            "accepted_by": self.accepted_by,
            "rejected_by": self.rejected_by,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class AgentProfile:
    """Profile of an agent for similarity matching."""

    name: str
    tier: int = 2
    capabilities: list = field(default_factory=list)
    specializations: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    learnings: list = field(default_factory=list)  # Learning IDs
    performance_score: float = 0.5

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tier": self.tier,
            "capabilities": self.capabilities,
            "specializations": self.specializations,
            "tools": self.tools,
            "learnings": self.learnings,
            "performance_score": self.performance_score,
        }


class FederatedLearning:
    """
    Share learnings across similar agents.

    Enables agents to benefit from each other's experiences
    by propagating successful strategies to similar agents.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path(".agent/data/federated")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.agent_profiles: dict[str, AgentProfile] = {}
        self.learnings: dict[str, LearnedStrategy] = {}
        self.propagation_history: list[PropagationRecord] = []
        self.propagation_threshold = 0.7  # Minimum confidence to propagate
        self._load_data()

    def _load_data(self):
        """Load stored data."""
        data_file = self.storage_path / "federated_data.json"
        if data_file.exists():
            try:
                with open(data_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Load learnings
                for l_data in data.get("learnings", []):
                    learning = LearnedStrategy.from_dict(l_data)
                    self.learnings[learning.id] = learning

                logger.info(f"Loaded {len(self.learnings)} learnings")
            except Exception as e:
                logger.error(f"Error loading federated data: {e}")

    def _save_data(self):
        """Save data to disk."""
        data_file = self.storage_path / "federated_data.json"
        try:
            data = {
                "learnings": [learning.to_dict() for learning in self.learnings.values()],
                "propagation_history": [p.to_dict() for p in self.propagation_history[-100:]],
                "last_saved": datetime.now().isoformat(),
            }
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving federated data: {e}")

    def register_agent(
        self,
        name: str,
        tier: int,
        capabilities: list[str],
        specializations: list[str] | None = None,
        tools: list[str] | None = None,
    ):
        """Register an agent's profile."""
        self.agent_profiles[name] = AgentProfile(
            name=name,
            tier=tier,
            capabilities=capabilities,
            specializations=specializations or [],
            tools=tools or [],
        )
        logger.info(f"Registered agent profile: {name}")

    def identify_similar_agents(
        self, agent: str, min_similarity: float = 0.5
    ) -> list[tuple[str, float]]:
        """
        Find agents with similar capabilities.

        Args:
            agent: Source agent name
            min_similarity: Minimum similarity threshold

        Returns:
            List of (agent_name, similarity_score) tuples
        """
        if agent not in self.agent_profiles:
            return []

        source_profile = self.agent_profiles[agent]
        similar = []

        for name, profile in self.agent_profiles.items():
            if name == agent:
                continue

            similarity = self._calculate_similarity(source_profile, profile)
            if similarity >= min_similarity:
                similar.append((name, similarity))

        # Sort by similarity descending
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar

    def _calculate_similarity(self, profile1: AgentProfile, profile2: AgentProfile) -> float:
        """Calculate similarity between two agent profiles."""
        # Capability overlap
        caps1 = set(profile1.capabilities)
        caps2 = set(profile2.capabilities)
        cap_similarity = len(caps1 & caps2) / len(caps1 | caps2) if caps1 or caps2 else 0.0

        # Specialization overlap
        specs1 = set(profile1.specializations)
        specs2 = set(profile2.specializations)
        spec_similarity = len(specs1 & specs2) / len(specs1 | specs2) if specs1 or specs2 else 0.5

        # Tier proximity (same tier = 1.0, adjacent = 0.75, etc.)
        tier_diff = abs(profile1.tier - profile2.tier)
        tier_similarity = max(0, 1.0 - tier_diff * 0.25)

        # Weighted average
        similarity = cap_similarity * 0.5 + spec_similarity * 0.3 + tier_similarity * 0.2

        return similarity

    async def contribute_learning(
        self,
        agent: str,
        category: LearningCategory,
        name: str,
        description: str,
        context: dict,
        implementation: dict,
        success_rate: float,
        sample_size: int = 1,
        tags: list[str] | None = None,
    ) -> str:
        """
        Agent contributes a learning.

        Args:
            agent: Contributing agent
            category: Learning category
            name: Short name
            description: Detailed description
            context: When this applies
            implementation: How to apply
            success_rate: Success rate from agent's experience
            sample_size: Number of samples
            tags: Searchable tags

        Returns:
            Learning ID
        """
        # Calculate confidence based on success rate and sample size
        confidence = min(success_rate * (1 - 1 / (sample_size + 1)), 0.95)

        learning = LearnedStrategy(
            category=category,
            name=name,
            description=description,
            source_agent=agent,
            context=context,
            implementation=implementation,
            success_rate=success_rate,
            sample_size=sample_size,
            confidence=confidence,
            tags=tags or [],
        )

        self.learnings[learning.id] = learning

        # Update agent's learning list
        if agent in self.agent_profiles:
            self.agent_profiles[agent].learnings.append(learning.id)

        self._save_data()
        logger.info(f"Learning contributed by {agent}: {name} (confidence: {confidence:.2f})")

        return learning.id

    async def propagate_learning(
        self, learning_id: str, to_agents: list[str] | None = None, min_relevance: float = 0.5
    ) -> PropagationRecord:
        """
        Propagate a learning to similar agents.

        Args:
            learning_id: Learning to propagate
            to_agents: Specific agents (or auto-select similar)
            min_relevance: Minimum relevance for auto-selection

        Returns:
            PropagationRecord
        """
        if learning_id not in self.learnings:
            return PropagationRecord(learning_id=learning_id, status=PropagationStatus.FAILED)

        learning = self.learnings[learning_id]

        # Check confidence threshold
        if learning.confidence < self.propagation_threshold:
            logger.warning(f"Learning {learning_id} below confidence threshold")
            return PropagationRecord(
                learning_id=learning_id,
                from_agent=learning.source_agent,
                status=PropagationStatus.REJECTED,
                rejected_by=["system:low_confidence"],
            )

        # Select target agents
        if to_agents:
            targets = to_agents
        else:
            similar = self.identify_similar_agents(learning.source_agent)
            targets = []
            for agent_name, _similarity in similar:
                relevance = self.calculate_relevance(learning, agent_name)
                if relevance >= min_relevance:
                    targets.append(agent_name)

        if not targets:
            return PropagationRecord(
                learning_id=learning_id,
                from_agent=learning.source_agent,
                status=PropagationStatus.COMPLETED,
                to_agents=[],
                accepted_by=[],
            )

        # Create propagation record
        record = PropagationRecord(
            learning_id=learning_id,
            from_agent=learning.source_agent,
            to_agents=targets,
            status=PropagationStatus.IN_PROGRESS,
        )

        # Simulate propagation to each agent
        for agent in targets:
            relevance = self.calculate_relevance(learning, agent)
            # Agents with higher relevance are more likely to accept
            if relevance >= 0.6:
                record.accepted_by.append(agent)
                # Add learning to agent's profile
                if (
                    agent in self.agent_profiles
                    and learning_id not in self.agent_profiles[agent].learnings
                ):
                    self.agent_profiles[agent].learnings.append(learning_id)
            else:
                record.rejected_by.append(agent)

        record.status = PropagationStatus.COMPLETED
        record.completed_at = datetime.now()

        self.propagation_history.append(record)
        self._save_data()

        logger.info(f"Propagated learning to {len(record.accepted_by)}/{len(targets)} agents")

        return record

    def calculate_relevance(self, learning: LearnedStrategy, target_agent: str) -> float:
        """
        Calculate how relevant a learning is to target agent.

        Args:
            learning: The learning
            target_agent: Target agent name

        Returns:
            Relevance score 0-1
        """
        if target_agent not in self.agent_profiles:
            return 0.0

        profile = self.agent_profiles[target_agent]

        # Tag overlap with capabilities
        learning_tags = set(learning.tags)
        agent_caps = set(profile.capabilities + profile.specializations)

        if learning_tags and agent_caps:
            tag_overlap = len(learning_tags & agent_caps) / len(learning_tags)
        else:
            tag_overlap = 0.3  # Default moderate relevance

        # Category relevance
        category_relevance = {
            LearningCategory.STRATEGY: 0.8,  # Useful for all
            LearningCategory.PATTERN: 0.7,  # Generally useful
            LearningCategory.ERROR_HANDLING: 0.9,  # Very useful
            LearningCategory.OPTIMIZATION: 0.6,  # Situational
            LearningCategory.BEST_PRACTICE: 0.8,  # Useful for all
            LearningCategory.TOOL_USAGE: 0.5,  # Depends on tools
        }
        cat_score = category_relevance.get(learning.category, 0.5)

        # Agent similarity to source
        if learning.source_agent in self.agent_profiles:
            source_profile = self.agent_profiles[learning.source_agent]
            similarity = self._calculate_similarity(source_profile, profile)
        else:
            similarity = 0.5

        # Weighted relevance
        relevance = tag_overlap * 0.4 + cat_score * 0.3 + similarity * 0.3

        return relevance

    async def aggregate_learnings(
        self, agents: list[str], category: LearningCategory | None = None
    ) -> list[LearnedStrategy]:
        """
        Aggregate learnings from multiple agents.

        Args:
            agents: Agents to aggregate from
            category: Optional category filter

        Returns:
            Aggregated learnings
        """
        aggregated = []
        seen_patterns = set()

        for agent in agents:
            if agent not in self.agent_profiles:
                continue

            profile = self.agent_profiles[agent]
            for learning_id in profile.learnings:
                if learning_id not in self.learnings:
                    continue

                learning = self.learnings[learning_id]

                # Category filter
                if category and learning.category != category:
                    continue

                # Dedupe by name (simple)
                if learning.name in seen_patterns:
                    continue

                seen_patterns.add(learning.name)
                aggregated.append(learning)

        # Sort by confidence
        aggregated.sort(key=lambda item: item.confidence, reverse=True)
        return aggregated

    def get_agent_learnings(self, agent: str) -> list[LearnedStrategy]:
        """Get all learnings for an agent."""
        if agent not in self.agent_profiles:
            return []

        profile = self.agent_profiles[agent]
        return [self.learnings[lid] for lid in profile.learnings if lid in self.learnings]

    def get_stats(self) -> dict:
        """Get federated learning statistics."""
        return {
            "registered_agents": len(self.agent_profiles),
            "total_learnings": len(self.learnings),
            "propagation_count": len(self.propagation_history),
            "by_category": {
                cat.value: sum(
                    1 for learning in self.learnings.values() if learning.category == cat
                )
                for cat in LearningCategory
            },
            "avg_confidence": sum(learning.confidence for learning in self.learnings.values())
            / max(len(self.learnings), 1),
        }


# Singleton instance
_federated_instance: FederatedLearning | None = None


def get_federated_learning() -> FederatedLearning:
    """Get the global FederatedLearning instance."""
    global _federated_instance
    if _federated_instance is None:
        _federated_instance = FederatedLearning()
    return _federated_instance


# Example usage
if __name__ == "__main__":

    async def demo():
        fl = get_federated_learning()

        # Register agents
        fl.register_agent(
            "backend-specialist",
            tier=2,
            capabilities=["api_design", "database", "authentication"],
            specializations=["python", "nodejs"],
        )
        fl.register_agent(
            "frontend-specialist",
            tier=2,
            capabilities=["ui_design", "react", "state_management"],
            specializations=["typescript", "css"],
        )
        fl.register_agent(
            "fullstack-developer",
            tier=2,
            capabilities=["api_design", "ui_design", "database"],
            specializations=["typescript", "python"],
        )

        # Find similar agents
        similar = fl.identify_similar_agents("backend-specialist")
        print(f"Similar to backend-specialist: {similar}")

        # Contribute learning
        learning_id = await fl.contribute_learning(
            agent="backend-specialist",
            category=LearningCategory.PATTERN,
            name="Repository Pattern",
            description="Use repository pattern for data access",
            context={"applies_to": ["api_endpoints", "data_access"]},
            implementation={"pattern": "Create abstract repository, implement concrete"},
            success_rate=0.92,
            sample_size=15,
            tags=["database", "api_design", "architecture"],
        )
        print(f"Contributed learning: {learning_id}")

        # Propagate
        record = await fl.propagate_learning(learning_id)
        print(f"Propagation: {record.to_dict()}")

        # Stats
        print(f"Stats: {fl.get_stats()}")

    asyncio.run(demo())
