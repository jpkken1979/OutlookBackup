# mypy: ignore-errors
#!/usr/bin/env python3
"""
Domain Auto-Specialization - Agents auto-specialize based on usage patterns.

This module provides automatic specialization that:
1. Tracks which domains an agent handles most
2. Builds domain-specific knowledge bases
3. Adjusts agent behavior for domains
4. Recommends domain-specific tools and approaches
5. Enables cross-agent knowledge transfer

Usage:
    from .agent.core.intelligence import DomainSpecializer, specialize

    specializer = DomainSpecializer()

    # Record domain interactions
    await specializer.record_interaction(
        agent_name="architect",
        domain="security",
        task="Design auth system",
        success=True
    )

    # Get specialization recommendations
    profile = await specializer.get_profile("architect")
    print(f"Primary domain: {profile.primary_domain}")
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.domain_specialization")


class Domain(Enum):
    """Domains for specialization."""

    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    SECURITY = "security"
    DEVOPS = "devops"
    TESTING = "testing"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    MACHINE_LEARNING = "machine_learning"
    DATA_ENGINEERING = "data_engineering"
    MOBILE = "mobile"
    CLOUD = "cloud"
    API = "api"
    DOCUMENTATION = "documentation"
    GENERAL = "general"


class SpecializationLevel(Enum):
    """Levels of specialization."""

    NOVICE = "novice"  # < 10 interactions
    INTERMEDIATE = "intermediate"  # 10-50 interactions
    ADVANCED = "advanced"  # 50-200 interactions
    EXPERT = "expert"  # 200+ interactions with high success


@dataclass
class DomainInteraction:
    """A recorded interaction in a domain."""

    domain: Domain
    task: str
    success: bool
    execution_time_ms: int
    quality_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.value,
            "task": self.task[:100],
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "quality_score": self.quality_score,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DomainKnowledge:
    """Knowledge accumulated in a domain."""

    domain: Domain
    patterns: list[str]  # Common patterns learned
    tools: list[str]  # Preferred tools
    best_practices: list[str]  # Learned best practices
    common_errors: list[str]  # Known pitfalls
    reference_tasks: list[str]  # Example tasks

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.value,
            "patterns": self.patterns,
            "tools": self.tools,
            "best_practices": self.best_practices,
            "common_errors": self.common_errors,
        }


@dataclass
class DomainStats:
    """Statistics for a domain."""

    domain: Domain
    interaction_count: int
    success_count: int
    avg_quality_score: float
    avg_execution_time_ms: float
    specialization_level: SpecializationLevel
    last_interaction: datetime

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.interaction_count, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.value,
            "interaction_count": self.interaction_count,
            "success_rate": self.success_rate,
            "avg_quality_score": self.avg_quality_score,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "specialization_level": self.specialization_level.value,
        }


@dataclass
class AgentProfile:
    """Specialization profile for an agent."""

    agent_name: str
    primary_domain: Domain
    secondary_domains: list[Domain]
    domain_stats: dict[Domain, DomainStats]
    domain_knowledge: dict[Domain, DomainKnowledge]
    total_interactions: int
    overall_success_rate: float
    recommendations: list[str]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "primary_domain": self.primary_domain.value,
            "secondary_domains": [d.value for d in self.secondary_domains],
            "domain_stats": {k.value: v.to_dict() for k, v in self.domain_stats.items()},
            "total_interactions": self.total_interactions,
            "overall_success_rate": self.overall_success_rate,
            "recommendations": self.recommendations,
            "updated_at": self.updated_at.isoformat(),
        }


class DomainClassifier:
    """Classifies tasks into domains."""

    def __init__(self):
        self.domain_keywords = self._initialize_keywords()

    def _initialize_keywords(self) -> dict[Domain, list[str]]:
        """Initialize domain keywords."""
        return {
            Domain.FRONTEND: [
                "ui",
                "frontend",
                "react",
                "vue",
                "angular",
                "css",
                "html",
                "component",
                "button",
                "form",
                "layout",
                "responsive",
                "tailwind",
            ],
            Domain.BACKEND: [
                "backend",
                "server",
                "api",
                "endpoint",
                "controller",
                "service",
                "middleware",
                "express",
                "fastapi",
                "django",
                "flask",
            ],
            Domain.DATABASE: [
                "database",
                "db",
                "sql",
                "query",
                "schema",
                "migration",
                "postgres",
                "mysql",
                "mongodb",
                "redis",
                "table",
                "index",
            ],
            Domain.SECURITY: [
                "security",
                "auth",
                "authentication",
                "authorization",
                "jwt",
                "oauth",
                "encrypt",
                "password",
                "vulnerability",
                "xss",
                "injection",
            ],
            Domain.DEVOPS: [
                "devops",
                "ci",
                "cd",
                "deploy",
                "docker",
                "kubernetes",
                "k8s",
                "jenkins",
                "github actions",
                "terraform",
                "aws",
                "gcp",
                "azure",
            ],
            Domain.TESTING: [
                "test",
                "testing",
                "unit",
                "integration",
                "e2e",
                "jest",
                "pytest",
                "coverage",
                "mock",
                "stub",
                "assertion",
                "spec",
            ],
            Domain.ARCHITECTURE: [
                "architect",
                "design",
                "pattern",
                "microservice",
                "monolith",
                "scalability",
                "structure",
                "module",
                "layer",
                "dependency",
            ],
            Domain.PERFORMANCE: [
                "performance",
                "optimize",
                "speed",
                "memory",
                "cpu",
                "cache",
                "latency",
                "throughput",
                "benchmark",
                "profiling",
            ],
            Domain.MACHINE_LEARNING: [
                "ml",
                "machine learning",
                "ai",
                "model",
                "training",
                "inference",
                "tensorflow",
                "pytorch",
                "neural",
                "prediction",
            ],
            Domain.DATA_ENGINEERING: [
                "data",
                "etl",
                "pipeline",
                "airflow",
                "spark",
                "kafka",
                "warehouse",
                "analytics",
                "dbt",
                "transformation",
            ],
            Domain.MOBILE: [
                "mobile",
                "ios",
                "android",
                "react native",
                "flutter",
                "app",
                "smartphone",
                "tablet",
                "responsive",
            ],
            Domain.CLOUD: [
                "cloud",
                "aws",
                "gcp",
                "azure",
                "serverless",
                "lambda",
                "s3",
                "ec2",
                "container",
                "cloud-native",
            ],
            Domain.API: [
                "api",
                "rest",
                "graphql",
                "endpoint",
                "swagger",
                "openapi",
                "request",
                "response",
                "http",
                "grpc",
            ],
            Domain.DOCUMENTATION: [
                "document",
                "readme",
                "wiki",
                "guide",
                "tutorial",
                "docstring",
                "comment",
                "jsdoc",
                "sphinx",
                "mkdocs",
            ],
        }

    def classify(self, task: str) -> Domain:
        """Classify a task into a domain."""
        task_lower = task.lower()
        scores: dict[Domain, float] = defaultdict(float)

        for domain, keywords in self.domain_keywords.items():
            for keyword in keywords:
                if keyword in task_lower:
                    scores[domain] += 1.0

                    # Bonus for exact match
                    if f" {keyword} " in f" {task_lower} ":
                        scores[domain] += 0.5

        if scores:
            return max(scores, key=scores.get)
        return Domain.GENERAL


class KnowledgeBuilder:
    """Builds domain knowledge from interactions."""

    def build_knowledge(
        self,
        domain: Domain,
        interactions: list[DomainInteraction],
    ) -> DomainKnowledge:
        """Build knowledge from interactions."""
        patterns = []
        tools = []
        best_practices = []
        common_errors = []
        reference_tasks = []

        # Extract from successful interactions
        successful = [i for i in interactions if i.success]
        failed = [i for i in interactions if not i.success]

        # Extract patterns from successful tasks
        for interaction in successful[:20]:
            task = interaction.task.lower()

            # Common action patterns
            if "create" in task:
                patterns.append(f"Create pattern: {task[:50]}")
            elif "fix" in task or "debug" in task:
                patterns.append(f"Fix/Debug pattern: {task[:50]}")
            elif "optimize" in task:
                patterns.append(f"Optimization pattern: {task[:50]}")

        # Extract common errors from failures
        for interaction in failed[:10]:
            common_errors.append(f"Failed: {interaction.task[:50]}")

        # Add domain-specific best practices
        best_practices = self._get_domain_best_practices(domain)

        # Add domain-specific tools
        tools = self._get_domain_tools(domain)

        # Get reference tasks (high quality successes)
        high_quality = sorted(
            [i for i in successful if i.quality_score > 0.8],
            key=lambda x: x.quality_score,
            reverse=True,
        )
        reference_tasks = [i.task[:100] for i in high_quality[:5]]

        return DomainKnowledge(
            domain=domain,
            patterns=patterns[:10],
            tools=tools,
            best_practices=best_practices,
            common_errors=common_errors[:5],
            reference_tasks=reference_tasks,
        )

    def _get_domain_best_practices(self, domain: Domain) -> list[str]:
        """Get best practices for a domain."""
        practices = {
            Domain.FRONTEND: [
                "Component-based architecture",
                "State management patterns",
                "Accessibility first",
            ],
            Domain.BACKEND: [
                "RESTful design principles",
                "Error handling",
                "Input validation",
            ],
            Domain.DATABASE: [
                "Index optimization",
                "Query optimization",
                "Normalization",
            ],
            Domain.SECURITY: [
                "Input sanitization",
                "Principle of least privilege",
                "Secure by default",
            ],
            Domain.TESTING: [
                "Test isolation",
                "Meaningful assertions",
                "Coverage targets",
            ],
        }
        return practices.get(domain, ["Follow established patterns"])

    def _get_domain_tools(self, domain: Domain) -> list[str]:
        """Get recommended tools for a domain."""
        tools = {
            Domain.FRONTEND: ["React", "TypeScript", "Tailwind CSS", "Vitest"],
            Domain.BACKEND: ["Python", "FastAPI", "Node.js", "Express"],
            Domain.DATABASE: ["PostgreSQL", "Prisma", "SQLAlchemy"],
            Domain.SECURITY: ["OWASP ZAP", "Semgrep", "HashiCorp Vault"],
            Domain.DEVOPS: ["Docker", "Kubernetes", "GitHub Actions"],
            Domain.TESTING: ["pytest", "Jest", "Playwright"],
        }
        return tools.get(domain, [])


class DomainSpecializer:
    """
    Manages domain specialization for agents.

    This class:
    1. Tracks domain interactions
    2. Builds domain profiles
    3. Provides recommendations
    4. Enables knowledge transfer
    """

    # Thresholds for specialization levels
    NOVICE_THRESHOLD = 10
    INTERMEDIATE_THRESHOLD = 50
    ADVANCED_THRESHOLD = 200

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/specialization")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.classifier = DomainClassifier()
        self.knowledge_builder = KnowledgeBuilder()

        # Agent interactions
        self.interactions: dict[str, list[DomainInteraction]] = defaultdict(list)

        # Load existing data
        self._load_data()

    def _load_data(self) -> None:
        """Load saved data."""
        data_file = self.memory_dir / "specialization_data.json"
        if data_file.exists():
            try:
                with open(data_file, encoding="utf-8") as f:
                    json.load(f)
                    # Load interactions (simplified)
                    logger.info("Loaded specialization data")
            except Exception as e:
                logger.warning(f"Failed to load data: {e}")

    def _save_data(self) -> None:
        """Save data to disk."""
        data_file = self.memory_dir / "specialization_data.json"
        data = {
            "agents": list(self.interactions.keys()),
            "total_interactions": sum(len(i) for i in self.interactions.values()),
            "updated_at": datetime.now().isoformat(),
        }
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def record_interaction(
        self,
        agent_name: str,
        task: str,
        success: bool,
        quality_score: float = 0.7,
        execution_time_ms: int = 1000,
        domain: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a domain interaction.

        Args:
            agent_name: Name of the agent
            task: Task description
            success: Whether task succeeded
            quality_score: Quality of output (0-1)
            execution_time_ms: Execution time
            domain: Domain (auto-detected if None)
            metadata: Additional metadata
        """
        # Classify domain if not provided
        if domain:
            try:
                classified_domain = Domain(domain)
            except ValueError:
                classified_domain = self.classifier.classify(task)
        else:
            classified_domain = self.classifier.classify(task)

        interaction = DomainInteraction(
            domain=classified_domain,
            task=task,
            success=success,
            execution_time_ms=execution_time_ms,
            quality_score=quality_score,
            metadata=metadata or {},
        )

        self.interactions[agent_name].append(interaction)
        self._save_data()

        logger.info(
            f"Recorded interaction: {agent_name} in {classified_domain.value} (success={success})"
        )

    async def get_profile(self, agent_name: str) -> AgentProfile:
        """
        Get specialization profile for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentProfile with specialization info
        """
        agent_interactions = self.interactions.get(agent_name, [])

        if not agent_interactions:
            return AgentProfile(
                agent_name=agent_name,
                primary_domain=Domain.GENERAL,
                secondary_domains=[],
                domain_stats={},
                domain_knowledge={},
                total_interactions=0,
                overall_success_rate=0.0,
                recommendations=["Start handling tasks to build specialization"],
            )

        # Calculate domain stats
        domain_interactions: dict[Domain, list[DomainInteraction]] = defaultdict(list)
        for interaction in agent_interactions:
            domain_interactions[interaction.domain].append(interaction)

        domain_stats = {}
        for domain, interactions in domain_interactions.items():
            stats = self._calculate_domain_stats(domain, interactions)
            domain_stats[domain] = stats

        # Determine primary and secondary domains
        sorted_domains = sorted(
            domain_stats.items(),
            key=lambda x: (x[1].interaction_count, x[1].avg_quality_score),
            reverse=True,
        )

        primary_domain = sorted_domains[0][0] if sorted_domains else Domain.GENERAL
        secondary_domains = [d for d, _ in sorted_domains[1:4]]

        # Build domain knowledge
        domain_knowledge = {}
        for domain, interactions in domain_interactions.items():
            if len(interactions) >= 5:  # Only build knowledge with enough data
                knowledge = self.knowledge_builder.build_knowledge(domain, interactions)
                domain_knowledge[domain] = knowledge

        # Calculate overall stats
        total_interactions = len(agent_interactions)
        successful = sum(1 for i in agent_interactions if i.success)
        overall_success_rate = successful / total_interactions

        # Generate recommendations
        recommendations = self._generate_recommendations(
            agent_name,
            primary_domain,
            domain_stats,
        )

        return AgentProfile(
            agent_name=agent_name,
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            domain_stats=domain_stats,
            domain_knowledge=domain_knowledge,
            total_interactions=total_interactions,
            overall_success_rate=overall_success_rate,
            recommendations=recommendations,
            updated_at=datetime.now(),
        )

    def _calculate_domain_stats(
        self,
        domain: Domain,
        interactions: list[DomainInteraction],
    ) -> DomainStats:
        """Calculate stats for a domain."""
        interaction_count = len(interactions)
        success_count = sum(1 for i in interactions if i.success)

        quality_scores = [i.quality_score for i in interactions]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        execution_times = [i.execution_time_ms for i in interactions]
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0

        # Determine specialization level
        success_rate = success_count / max(interaction_count, 1)
        if interaction_count >= self.ADVANCED_THRESHOLD and success_rate > 0.85:
            level = SpecializationLevel.EXPERT
        elif interaction_count >= self.INTERMEDIATE_THRESHOLD:
            level = SpecializationLevel.ADVANCED
        elif interaction_count >= self.NOVICE_THRESHOLD:
            level = SpecializationLevel.INTERMEDIATE
        else:
            level = SpecializationLevel.NOVICE

        last_interaction = max(interactions, key=lambda x: x.timestamp)

        return DomainStats(
            domain=domain,
            interaction_count=interaction_count,
            success_count=success_count,
            avg_quality_score=avg_quality,
            avg_execution_time_ms=avg_time,
            specialization_level=level,
            last_interaction=last_interaction.timestamp,
        )

    def _generate_recommendations(
        self,
        agent_name: str,
        primary_domain: Domain,
        domain_stats: dict[Domain, DomainStats],
    ) -> list[str]:
        """Generate recommendations for the agent."""
        recommendations = []

        # Primary domain recommendations
        if primary_domain in domain_stats:
            stats = domain_stats[primary_domain]
            if stats.specialization_level == SpecializationLevel.EXPERT:
                recommendations.append(
                    f"Expert in {primary_domain.value} - consider mentoring other agents"
                )
            elif stats.success_rate < 0.7:
                recommendations.append(
                    f"Improve success rate in {primary_domain.value} "
                    f"(currently {stats.success_rate:.0%})"
                )

        # Find weak domains
        weak_domains = [
            d for d, s in domain_stats.items() if s.success_rate < 0.6 and s.interaction_count > 5
        ]
        for domain in weak_domains[:2]:
            recommendations.append(
                f"Consider delegating {domain.value} tasks to specialized agents"
            )

        # Suggest expanding expertise
        if len(domain_stats) < 3:
            recommendations.append("Explore more domains to broaden expertise")

        return recommendations[:5]

    async def suggest_agent_for_task(
        self,
        task: str,
        available_agents: list[str],
    ) -> str:
        """
        Suggest the best agent for a task.

        Args:
            task: Task description
            available_agents: List of available agent names

        Returns:
            Recommended agent name
        """
        domain = self.classifier.classify(task)

        best_agent = None
        best_score = 0.0

        for agent_name in available_agents:
            profile = await self.get_profile(agent_name)

            # Score based on domain match and expertise
            score = 0.0

            if domain in profile.domain_stats:
                stats = profile.domain_stats[domain]
                score += stats.success_rate * 0.4
                score += (stats.interaction_count / 100) * 0.3
                score += stats.avg_quality_score * 0.3

            # Bonus for primary domain match
            if profile.primary_domain == domain:
                score += 0.2

            if score > best_score:
                best_score = score
                best_agent = agent_name

        return best_agent or available_agents[0]

    def export_report(self) -> str:
        """Export specialization report as markdown."""
        lines = [
            "# Domain Specialization Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Agents tracked:** {len(self.interactions)}",
            "",
        ]

        for agent_name in self.interactions:
            # Get profile synchronously for report
            interactions = self.interactions[agent_name]

            # Simple stats
            domain_counts: dict[Domain, int] = defaultdict(int)
            for i in interactions:
                domain_counts[i.domain] += 1

            lines.extend(
                [
                    f"## {agent_name}",
                    "",
                    f"Total interactions: {len(interactions)}",
                    "",
                    "| Domain | Count |",
                    "|--------|-------|",
                ]
            )

            for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {domain.value} | {count} |")

            lines.extend(["", "---", ""])

        return "\n".join(lines)


# Convenience function
async def specialize(
    agent_name: str,
    task: str,
    success: bool,
    quality_score: float = 0.7,
) -> None:
    """Quick function to record specialization."""
    specializer = DomainSpecializer()
    await specializer.record_interaction(agent_name, task, success, quality_score)
