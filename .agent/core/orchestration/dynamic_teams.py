# mypy: ignore-errors
#!/usr/bin/env python3
"""
Hybrid Orchestration with Dynamic Teams

Implements a hybrid orchestration pattern combining:
1. Central orchestrator for high-level coordination
2. Dynamic team formation based on task requirements
3. Agent-to-agent help requests mid-execution
4. Consensus protocols for critical decisions

Based on research from:
- LangGraph: Multi-agent workflows
- CrewAI: Agent teams and delegation
- AutoGen: Dynamic conversations

Key Features:
- Dynamic team assembly based on task analysis
- Mid-execution help requests
- Consensus voting for important decisions
- Automatic conflict resolution
"""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger("antigravity.dynamic_teams")


class TeamRole(Enum):
    """Roles agents can play in a team."""

    LEAD = "lead"  # Primary decision maker
    SPECIALIST = "specialist"  # Domain expert
    REVIEWER = "reviewer"  # Quality checker
    SUPPORTER = "supporter"  # Assists lead
    CRITIC = "critic"  # Challenges decisions


class TaskComplexity(Enum):
    """Task complexity levels."""

    TRIVIAL = "trivial"  # Single agent, no team needed
    SIMPLE = "simple"  # 1-2 agents
    MODERATE = "moderate"  # 2-4 agents
    COMPLEX = "complex"  # 4-6 agents
    CRITICAL = "critical"  # Full team with consensus


class HelpRequestType(Enum):
    """Types of help requests between agents."""

    QUESTION = "question"  # Need information
    REVIEW = "review"  # Need validation
    DELEGATION = "delegation"  # Hand off subtask
    CONSULTATION = "consultation"  # Need opinion
    ESCALATION = "escalation"  # Need higher authority


class ConsensusType(Enum):
    """Types of consensus for decisions."""

    MAJORITY = "majority"  # >50% agree
    SUPERMAJORITY = "supermajority"  # >66% agree
    UNANIMOUS = "unanimous"  # 100% agree
    LEAD_DECIDES = "lead_decides"  # Lead has final say


@dataclass
class AgentCapability:
    """Describes an agent's capabilities."""

    agent_name: str
    domains: list[str]  # e.g., ["security", "backend", "python"]
    skills: list[str]  # e.g., ["code_review", "testing", "design"]
    preferred_tasks: list[str]  # Task types they excel at
    availability: float = 1.0  # 0-1 availability score
    cost_per_task: float = 1.0  # Relative cost


@dataclass
class TeamMember:
    """A member of a dynamic team."""

    agent_name: str
    role: TeamRole
    capabilities: AgentCapability
    assigned_subtasks: list[str] = field(default_factory=list)
    status: str = "ready"  # ready, working, waiting, done


@dataclass
class HelpRequest:
    """A request for help from one agent to another."""

    id: str
    request_type: HelpRequestType
    from_agent: str
    to_agent: str | None  # None = broadcast to team
    query: str
    context: dict = field(default_factory=dict)
    urgency: str = "normal"  # low, normal, high, critical
    created_at: str = ""
    response: str | None = None
    responded_at: str | None = None
    responded_by: str | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class ConsensusVote:
    """A vote in a consensus decision."""

    agent_name: str
    vote: bool  # True = approve, False = reject
    reasoning: str
    confidence: float = 1.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ConsensusDecision:
    """A decision requiring team consensus."""

    id: str
    topic: str
    description: str
    options: list[str]
    consensus_type: ConsensusType
    initiator: str
    votes: list[ConsensusVote] = field(default_factory=list)
    deadline: str | None = None
    result: str | None = None
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class DynamicTeam:
    """A dynamically formed team of agents."""

    id: str
    name: str
    task_description: str
    complexity: TaskComplexity
    members: list[TeamMember] = field(default_factory=list)
    lead: str | None = None

    # State
    status: str = "forming"  # forming, active, paused, completed, failed
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None

    # Communication
    help_requests: list[HelpRequest] = field(default_factory=list)
    consensus_decisions: list[ConsensusDecision] = field(default_factory=list)

    # Results
    outputs: dict = field(default_factory=dict)
    final_result: str | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def get_member(self, agent_name: str) -> TeamMember | None:
        """Get team member by name."""
        for member in self.members:
            if member.agent_name == agent_name:
                return member
        return None


class DynamicTeamOrchestrator:
    """
    Orchestrates dynamic team formation and coordination.

    Usage:
        orchestrator = DynamicTeamOrchestrator()

        # Register agent capabilities
        orchestrator.register_agent(AgentCapability(
            agent_name="security-auditor",
            domains=["security", "authentication"],
            skills=["vulnerability_scan", "code_review"],
            preferred_tasks=["security_audit", "penetration_test"]
        ))

        # Create team for task
        team = await orchestrator.create_team(
            task="Audit authentication module for security vulnerabilities",
            required_domains=["security", "backend"]
        )

        # Execute with dynamic coordination
        result = await orchestrator.execute_team_task(team)
    """

    # Agent registry with capabilities
    KNOWN_AGENTS: dict[str, AgentCapability] = {}

    # Domain to agent mapping (auto-built from registry)
    DOMAIN_AGENTS: dict[str, list[str]] = {}

    # Task type configurations
    TASK_CONFIGS = {
        "security_audit": {
            "required_roles": [TeamRole.LEAD, TeamRole.SPECIALIST],
            "preferred_agents": ["security-auditor", "code-reviewer"],
            "consensus_required": True,
            "min_team_size": 2,
        },
        "feature_development": {
            "required_roles": [TeamRole.LEAD, TeamRole.SPECIALIST, TeamRole.REVIEWER],
            "preferred_agents": ["architect", "coder", "test-engineer"],
            "consensus_required": False,
            "min_team_size": 2,
        },
        "bug_fix": {
            "required_roles": [TeamRole.LEAD],
            "preferred_agents": ["debugger", "coder"],
            "consensus_required": False,
            "min_team_size": 1,
        },
        "architecture_design": {
            "required_roles": [TeamRole.LEAD, TeamRole.SPECIALIST, TeamRole.CRITIC],
            "preferred_agents": ["architect", "backend-specialist", "critic"],
            "consensus_required": True,
            "min_team_size": 3,
        },
        "code_review": {
            "required_roles": [TeamRole.LEAD, TeamRole.REVIEWER],
            "preferred_agents": ["code-reviewer", "security-auditor"],
            "consensus_required": False,
            "min_team_size": 2,
        },
    }

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".antigravity" / "dynamic_teams"

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.active_teams: dict[str, DynamicTeam] = {}
        self.completed_teams: list[str] = []

        # Callbacks for agent execution
        self._agent_executors: dict[str, Callable] = {}

        self._initialize_default_agents()
        logger.info("DynamicTeamOrchestrator initialized")

    def _initialize_default_agents(self):
        """Initialize default agent capabilities."""
        default_agents = [
            AgentCapability(
                agent_name="architect",
                domains=["architecture", "design", "system"],
                skills=["system_design", "trade_off_analysis", "documentation"],
                preferred_tasks=["architecture_design", "system_planning"],
            ),
            AgentCapability(
                agent_name="security-auditor",
                domains=["security", "authentication", "authorization"],
                skills=["vulnerability_scan", "threat_modeling", "owasp"],
                preferred_tasks=["security_audit", "penetration_test"],
            ),
            AgentCapability(
                agent_name="coder",
                domains=["implementation", "backend", "frontend"],
                skills=["coding", "debugging", "optimization"],
                preferred_tasks=["feature_development", "bug_fix"],
            ),
            AgentCapability(
                agent_name="code-reviewer",
                domains=["quality", "best_practices"],
                skills=["code_review", "pattern_detection", "refactoring"],
                preferred_tasks=["code_review", "refactoring"],
            ),
            AgentCapability(
                agent_name="test-engineer",
                domains=["testing", "qa"],
                skills=["test_writing", "coverage_analysis", "automation"],
                preferred_tasks=["testing", "qa"],
            ),
            AgentCapability(
                agent_name="debugger",
                domains=["debugging", "troubleshooting"],
                skills=["root_cause_analysis", "profiling", "logging"],
                preferred_tasks=["bug_fix", "debugging"],
            ),
            AgentCapability(
                agent_name="critic",
                domains=["validation", "review"],
                skills=["challenge_assumptions", "find_flaws", "alternatives"],
                preferred_tasks=["architecture_design", "decision_validation"],
            ),
            AgentCapability(
                agent_name="explorer",
                domains=["research", "codebase"],
                skills=["code_search", "dependency_analysis", "documentation"],
                preferred_tasks=["exploration", "research"],
            ),
        ]

        for agent in default_agents:
            self.register_agent(agent)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        hash_input = f"{prefix}{datetime.now().isoformat()}"
        return f"{prefix}_{hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()[:8]}"

    def register_agent(self, capability: AgentCapability):
        """Register an agent's capabilities."""
        self.KNOWN_AGENTS[capability.agent_name] = capability

        # Update domain mapping
        for domain in capability.domains:
            if domain not in self.DOMAIN_AGENTS:
                self.DOMAIN_AGENTS[domain] = []
            if capability.agent_name not in self.DOMAIN_AGENTS[domain]:
                self.DOMAIN_AGENTS[domain].append(capability.agent_name)

        logger.debug(f"Registered agent: {capability.agent_name}")

    def register_executor(self, agent_name: str, executor: Callable):
        """Register an executor function for an agent."""
        self._agent_executors[agent_name] = executor

    def analyze_task_complexity(self, task: str) -> TaskComplexity:
        """Analyze task to determine complexity level."""
        task_lower = task.lower()

        # Critical indicators
        critical_keywords = ["security", "production", "critical", "urgent", "deploy"]
        if any(kw in task_lower for kw in critical_keywords):
            return TaskComplexity.CRITICAL

        # Complex indicators
        complex_keywords = ["architecture", "design", "migrate", "refactor", "integrate"]
        if any(kw in task_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX

        # Moderate indicators
        moderate_keywords = ["implement", "feature", "api", "endpoint", "module"]
        if any(kw in task_lower for kw in moderate_keywords):
            return TaskComplexity.MODERATE

        # Simple indicators
        simple_keywords = ["fix", "update", "change", "add", "remove"]
        if any(kw in task_lower for kw in simple_keywords):
            return TaskComplexity.SIMPLE

        return TaskComplexity.TRIVIAL

    def classify_task_type(self, task: str) -> str:
        """Classify task into a known type."""
        task_lower = task.lower()

        if any(
            kw in task_lower for kw in ["security", "audit", "vulnerab", "owasp", "penetration"]
        ):
            return "security_audit"
        if any(kw in task_lower for kw in ["architecture", "design", "structure"]):
            return "architecture_design"
        if any(kw in task_lower for kw in ["review", "check", "validate"]):
            return "code_review"
        if any(kw in task_lower for kw in ["fix", "bug", "error", "issue"]):
            return "bug_fix"

        return "feature_development"

    def find_agents_for_domains(self, domains: list[str], limit: int = 5) -> list[AgentCapability]:
        """Find agents that match required domains."""
        agent_scores: dict[str, float] = {}

        for domain in domains:
            if domain in self.DOMAIN_AGENTS:
                for agent_name in self.DOMAIN_AGENTS[domain]:
                    agent_scores[agent_name] = agent_scores.get(agent_name, 0) + 1

        # Sort by score and availability
        sorted_agents = sorted(
            agent_scores.items(),
            key=lambda x: (x[1], self.KNOWN_AGENTS[x[0]].availability),
            reverse=True,
        )

        return [self.KNOWN_AGENTS[name] for name, _ in sorted_agents[:limit]]

    def _gather_candidates(
        self,
        preferred_agents: list[str] | None,
        required_domains: list[str] | None,
        config: dict,
    ) -> list:
        """Recolecta agentes candidatos: preferidos + por dominio + de la config.

        Args:
            preferred_agents: Agentes preferidos explícitos (opcional).
            required_domains: Dominios requeridos (opcional).
            config: Configuración del tipo de tarea.

        Returns:
            Lista de capabilities de agentes candidatos, sin duplicados, en orden.
        """
        candidates: list = []
        if preferred_agents:
            for agent_name in preferred_agents:
                if agent_name in self.KNOWN_AGENTS:
                    candidates.append(self.KNOWN_AGENTS[agent_name])

        if required_domains:
            for agent in self.find_agents_for_domains(required_domains):
                if agent not in candidates:
                    candidates.append(agent)

        for agent_name in config["preferred_agents"]:
            if agent_name in self.KNOWN_AGENTS:
                agent = self.KNOWN_AGENTS[agent_name]
                if agent not in candidates:
                    candidates.append(agent)
        return candidates

    @staticmethod
    def _assign_roles(selected: list, config: dict) -> tuple[list, str | None]:
        """Asigna roles a los agentes seleccionados según los roles requeridos.

        Args:
            selected: Agentes seleccionados para el equipo.
            config: Configuración del tipo de tarea (required_roles).

        Returns:
            Tupla (lista de TeamMember, nombre del lead o None).
        """
        members: list = []
        roles_needed = list(config["required_roles"])
        lead_name = None
        for agent in selected:
            role = roles_needed.pop(0) if roles_needed else TeamRole.SUPPORTER
            members.append(TeamMember(agent_name=agent.agent_name, role=role, capabilities=agent))
            if role == TeamRole.LEAD:
                lead_name = agent.agent_name
        return members, lead_name

    async def create_team(
        self,
        task: str,
        required_domains: list[str] | None = None,
        preferred_agents: list[str] | None = None,
        min_size: int = 1,
        max_size: int = 6,
    ) -> DynamicTeam:
        """Create a dynamic team for a task."""
        team_id = self._generate_id("team")
        complexity = self.analyze_task_complexity(task)
        task_type = self.classify_task_type(task)

        # Get task configuration
        config = self.TASK_CONFIGS.get(task_type, self.TASK_CONFIGS["feature_development"])

        # Determine team size based on complexity
        size_map = {
            TaskComplexity.TRIVIAL: 1,
            TaskComplexity.SIMPLE: 2,
            TaskComplexity.MODERATE: 3,
            TaskComplexity.COMPLEX: 4,
            TaskComplexity.CRITICAL: 5,
        }
        target_size = max(min_size, min(max_size, size_map[complexity], config["min_team_size"]))

        # Find candidate agents y limitar al tamaño objetivo
        candidates = self._gather_candidates(preferred_agents, required_domains, config)
        selected = candidates[:target_size]

        # Assign roles
        members, lead_name = self._assign_roles(selected, config)

        # Create team
        team = DynamicTeam(
            id=team_id,
            name=f"Team for: {task[:50]}...",
            task_description=task,
            complexity=complexity,
            members=members,
            lead=lead_name,
        )

        self.active_teams[team_id] = team
        logger.info(f"Created team {team_id} with {len(members)} members for task: {task[:50]}...")
        return team

    async def request_help(
        self,
        team: DynamicTeam,
        from_agent: str,
        request_type: HelpRequestType,
        query: str,
        to_agent: str | None = None,
        context: dict | None = None,
        urgency: str = "normal",
    ) -> HelpRequest:
        """Request help from another agent or the team."""
        request_id = self._generate_id("help")

        request = HelpRequest(
            id=request_id,
            request_type=request_type,
            from_agent=from_agent,
            to_agent=to_agent,
            query=query,
            context=context or {},
            urgency=urgency,
        )

        team.help_requests.append(request)

        if to_agent:
            logger.info(f"Help request from {from_agent} to {to_agent}: {query[:50]}...")
        else:
            logger.info(f"Help request from {from_agent} to team: {query[:50]}...")

        return request

    async def respond_to_help(
        self, team: DynamicTeam, request_id: str, responder: str, response: str
    ) -> bool:
        """Respond to a help request."""
        for request in team.help_requests:
            if request.id == request_id and request.response is None:
                request.response = response
                request.responded_at = datetime.now().isoformat()
                request.responded_by = responder
                logger.info(f"Help request {request_id} answered by {responder}")
                return True
        return False

    async def initiate_consensus(
        self,
        team: DynamicTeam,
        topic: str,
        description: str,
        options: list[str],
        consensus_type: ConsensusType = ConsensusType.MAJORITY,
        initiator: str | None = None,
    ) -> ConsensusDecision:
        """Initiate a consensus decision."""
        decision_id = self._generate_id("cons")

        decision = ConsensusDecision(
            id=decision_id,
            topic=topic,
            description=description,
            options=options,
            consensus_type=consensus_type,
            initiator=initiator or team.lead or "system",
        )

        team.consensus_decisions.append(decision)
        logger.info(f"Consensus initiated: {topic}")
        return decision

    async def cast_vote(
        self,
        team: DynamicTeam,
        decision_id: str,
        agent_name: str,
        vote: bool,
        reasoning: str,
        confidence: float = 1.0,
    ) -> bool:
        """Cast a vote in a consensus decision."""
        for decision in team.consensus_decisions:
            if decision.id == decision_id:
                # Check if already voted
                for existing_vote in decision.votes:
                    if existing_vote.agent_name == agent_name:
                        return False

                new_vote = ConsensusVote(
                    agent_name=agent_name, vote=vote, reasoning=reasoning, confidence=confidence
                )
                decision.votes.append(new_vote)
                logger.debug(f"Vote cast by {agent_name}: {vote}")
                return True
        return False

    async def resolve_consensus(self, team: DynamicTeam, decision_id: str) -> str | None:
        """Resolve a consensus decision based on votes."""
        for decision in team.consensus_decisions:
            if decision.id == decision_id:
                if not decision.votes:
                    return None

                total_votes = len(decision.votes)
                approve_votes = sum(1 for v in decision.votes if v.vote)
                approve_ratio = approve_votes / total_votes

                if decision.consensus_type == ConsensusType.UNANIMOUS:
                    passed = approve_ratio == 1.0
                elif decision.consensus_type == ConsensusType.SUPERMAJORITY:
                    passed = approve_ratio >= 0.66
                elif decision.consensus_type == ConsensusType.MAJORITY:
                    passed = approve_ratio > 0.5
                else:  # LEAD_DECIDES
                    lead_vote = next((v for v in decision.votes if v.agent_name == team.lead), None)
                    passed = lead_vote.vote if lead_vote else False

                decision.result = "approved" if passed else "rejected"
                logger.info(
                    f"Consensus {decision_id} resolved: {decision.result} ({approve_ratio:.0%})"
                )
                return decision.result

        return None

    async def execute_team_task(self, team: DynamicTeam, timeout: float = 300.0) -> dict:
        """Execute the team's task with dynamic coordination."""
        team.status = "active"
        team.started_at = datetime.now().isoformat()

        results = {
            "team_id": team.id,
            "task": team.task_description,
            "complexity": team.complexity.value,
            "members": [m.agent_name for m in team.members],
            "outputs": {},
            "help_requests": [],
            "consensus_decisions": [],
            "success": False,
        }

        try:
            # Execute each member's part
            for member in team.members:
                member.status = "working"

                # Check if we have an executor for this agent
                if member.agent_name in self._agent_executors:
                    executor = self._agent_executors[member.agent_name]
                    output = await executor(
                        task=team.task_description,
                        role=member.role.value,
                        team_context={
                            "team_id": team.id,
                            "other_members": [m.agent_name for m in team.members if m != member],
                        },
                    )
                else:
                    # Simulated execution
                    output = f"[{member.agent_name}] Completed analysis as {member.role.value}"

                team.outputs[member.agent_name] = output
                member.status = "done"
                results["outputs"][member.agent_name] = output

            # Collect help requests and decisions
            results["help_requests"] = [
                {
                    "from": r.from_agent,
                    "to": r.to_agent,
                    "type": r.request_type.value,
                    "query": r.query,
                    "response": r.response,
                }
                for r in team.help_requests
            ]

            results["consensus_decisions"] = [
                {"topic": d.topic, "votes": len(d.votes), "result": d.result}
                for d in team.consensus_decisions
            ]

            team.status = "completed"
            team.completed_at = datetime.now().isoformat()
            results["success"] = True

        except Exception as e:
            logger.error(f"Team task failed: {e}")
            team.status = "failed"
            results["error"] = str(e)

        self.completed_teams.append(team.id)
        return results

    def get_team_status(self, team_id: str) -> dict | None:
        """Get current status of a team."""
        team = self.active_teams.get(team_id)
        if not team:
            return None

        return {
            "id": team.id,
            "status": team.status,
            "complexity": team.complexity.value,
            "members": [
                {"name": m.agent_name, "role": m.role.value, "status": m.status}
                for m in team.members
            ],
            "pending_help_requests": sum(1 for r in team.help_requests if not r.response),
            "pending_consensus": sum(1 for d in team.consensus_decisions if not d.result),
        }

    def get_stats(self) -> dict:
        """Get orchestrator statistics."""
        return {
            "registered_agents": len(self.KNOWN_AGENTS),
            "active_teams": len(self.active_teams),
            "completed_teams": len(self.completed_teams),
            "domains_covered": len(self.DOMAIN_AGENTS),
            "agent_list": list(self.KNOWN_AGENTS.keys()),
        }


# Singleton instance
_orchestrator_instance: DynamicTeamOrchestrator | None = None


def get_team_orchestrator(storage_path: Path | None = None) -> DynamicTeamOrchestrator:
    """Get or create the team orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = DynamicTeamOrchestrator(storage_path)
    return _orchestrator_instance


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate dynamic team orchestration."""
    orchestrator = DynamicTeamOrchestrator()

    print("=== Dynamic Team Formation ===")

    # Create team for a security audit
    team = await orchestrator.create_team(
        task="Audit the authentication module for security vulnerabilities and OWASP compliance",
        required_domains=["security", "authentication"],
    )

    print(f"\nTeam created: {team.id}")
    print(f"Complexity: {team.complexity.value}")
    print(f"Lead: {team.lead}")
    print("Members:")
    for member in team.members:
        print(f"  - {member.agent_name} ({member.role.value})")

    # Simulate help request
    help_req = await orchestrator.request_help(
        team=team,
        from_agent="security-auditor",
        request_type=HelpRequestType.QUESTION,
        query="What authentication library is being used?",
        to_agent="explorer",
    )

    await orchestrator.respond_to_help(
        team=team,
        request_id=help_req.id,
        responder="explorer",
        response="The project uses PyJWT for JWT authentication",
    )

    # Simulate consensus decision
    decision = await orchestrator.initiate_consensus(
        team=team,
        topic="Upgrade to RS256",
        description="Should we recommend upgrading from HS256 to RS256?",
        options=["Upgrade immediately", "Plan for next sprint", "Keep HS256"],
        consensus_type=ConsensusType.MAJORITY,
        initiator="security-auditor",
    )

    # Cast votes
    await orchestrator.cast_vote(team, decision.id, "security-auditor", True, "Better security")
    await orchestrator.cast_vote(team, decision.id, "code-reviewer", True, "Industry standard")

    # Resolve
    result = await orchestrator.resolve_consensus(team, decision.id)
    print(f"\nConsensus decision: {result}")

    # Execute
    print("\n=== Executing Team Task ===")
    results = await orchestrator.execute_team_task(team)
    print(f"Success: {results['success']}")
    print(f"Outputs: {len(results['outputs'])}")

    # Stats
    print("\n=== Orchestrator Stats ===")
    stats = orchestrator.get_stats()
    print(f"Registered agents: {stats['registered_agents']}")
    print(f"Active teams: {stats['active_teams']}")


if __name__ == "__main__":
    asyncio.run(demo())
