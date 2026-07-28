#!/usr/bin/env python3
"""
Antigravity Orchestrator v3.0 - CrewAI-based Multi-Agent Orchestration.

This is the brain of the Antigravity ecosystem. It coordinates all specialist
agents using CrewAI for real task execution with:
- Intelligent task decomposition
- Parallel execution within tiers
- Shared memory across agents
- A2A protocol for agent discovery
- OpenTelemetry observability
"""

import asyncio
import logging
import re
import sys
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .intelligence_hub import IntelligenceContext, IntelligenceHub

from pydantic import BaseModel, Field

# Nota: `_discover_agents` se redefine localmente en este modulo (linea ~353)
# y la version importada quedaba opacada — quitamos el import para resolver
# el `[no-redef]` de mypy. La definicion local es la que efectivamente se usa
# en `AGENT_REGISTRY = _discover_agents()` mas abajo.
from .agent_mesh import AgentMesh, get_agent_mesh
from .memory.unified_memory import UnifiedMemory, get_unified_memory
from .shared_memory import MemoryBus, get_memory_bus

try:
    from crewai import Agent, Crew, Process, Task

    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False

try:
    from .langgraph_engine import LangGraphEngine

    HAS_LANGGRAPH = LangGraphEngine.is_available()
except ImportError:
    HAS_LANGGRAPH = False

try:
    from .autonomous_loop import AutonomousLoop

    HAS_AUTONOMOUS_LOOP = True
except ImportError:
    HAS_AUTONOMOUS_LOOP = False

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.orchestrator")


# ============================================================================
# ORCHESTRATOR EXECUTION FLOW
# ============================================================================
# Antigravity uses a 3-module orchestration architecture:
#
# 1. IntelligentOrchestrator (intelligent_orchestrator.py)
#    - Analyzes task complexity (TRIVIAL -> RESEARCH)
#    - Selects execution strategy (REACT, DEBATE, COMPOSED, etc.)
#    - Recommends agents based on task analysis
#
# 2. Orchestrator (this file)
#    - Primary execution engine with 4-tier fallback:
#      CrewAI real -> AutonomousLoop -> Script direct -> Simulation
#    - Agent registry and tier-based selection
#    - Task delegation and result synthesis
#
# 3. MetaOrchestrator (meta_orchestrator.py)
#    - Post-execution quality assessment
#    - Improvement suggestions and plan adaptation
#    - Feeds learning loop for future optimization
#
# Flow: Request -> IntelligentOrchestrator.analyze() -> Orchestrator.execute()
#       -> MetaOrchestrator.evaluate() -> IntelligenceHub.record()
# ============================================================================


# =============================================================================
# CONFIGURATION
# =============================================================================

AGENT_DIR = Path(__file__).parent.parent
AGENTS_DIR = AGENT_DIR / "agents"
SKILLS_DIR = AGENT_DIR / "skills"
MEMORY_DIR = AGENT_DIR / "memory"
AGENT_CARDS_DIR = AGENT_DIR / "agent_cards"


class AgentTier(Enum):
    """Agent specialization tiers for execution ordering."""

    PLANNING = 1  # planner, product-manager, architect
    DEVELOPMENT = 2  # frontend, backend, database, mobile
    QUALITY = 3  # testing, security, performance
    OPERATIONS = 4  # devops, documentation, debugger
    SPECIALIZED = 5  # game-dev, seo, code-archaeologist
    UNS_BUSINESS = 6  # Japanese HR specialists


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


# =============================================================================
# DATA MODELS
# =============================================================================


class AgentConfig(BaseModel):
    """Configuration for an Antigravity agent."""

    name: str
    tier: int
    role: str
    goal: str = ""
    backstory: str = ""
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    allow_delegation: bool = True
    verbose: bool = False
    max_iter: int = 15
    max_rpm: int = 10


class TaskConfig(BaseModel):
    """Configuration for a task."""

    id: str
    description: str
    expected_output: str
    agent: str | None = None
    context: list[str] = Field(default_factory=list)
    async_execution: bool = False
    human_input: bool = False


class ExecutionPlan(BaseModel):
    """Plan for executing a complex task."""

    id: str
    original_task: str
    phases: list[dict[str, Any]] = Field(default_factory=list)
    total_agents: int = 0
    estimated_complexity: str = "medium"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ExecutionResult(BaseModel):
    """Result of task execution."""

    task_id: str
    status: str
    output: str
    agent: str
    duration_seconds: float
    tokens_used: int = 0
    completed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# AGENT AUTO-DISCOVERY
# =============================================================================


def _parse_markdown_metadata(content: str) -> dict[str, Any]:
    """Extract agent metadata from Markdown content (non-YAML format).

    Parses patterns like **Nombre:** value, **Rol:** value, **Tier:** value
    from IDENTITY.md files that lack YAML frontmatter.

    Args:
        content: Raw Markdown content of the IDENTITY.md file.

    Returns:
        Dictionary with extracted metadata fields.
    """
    metadata: dict[str, Any] = {}

    # Extract **Nombre:** or **Name:** value
    name_match = re.search(r"\*\*(?:Nombre|Name)[:\s]*\*\*\s*(.+)", content, re.IGNORECASE)
    if name_match:
        metadata["name"] = name_match.group(1).strip()

    # Extract **Rol:** or **Role:** value
    role_match = re.search(r"\*\*(?:Rol|Role)[:\s]*\*\*\s*(.+)", content, re.IGNORECASE)
    if role_match:
        metadata["role"] = role_match.group(1).strip()

    # Extract **Tier:** value from various formats:
    # "**Tier:** 3 (Calidad)", "- **Tier**: 2 (Desarrollo)", "> **Tier:** 2 | ..."
    tier_match = re.search(r"\*\*Tier[:\s]*\*\*[:\s]*(\d+)", content, re.IGNORECASE)
    if tier_match:
        metadata["tier"] = int(tier_match.group(1))

    # Extraer description del formato inline: "- **Description:** texto"
    inline_desc_match = re.search(
        r"\*\*(?:Description|Descripci[oó]n|Goal|Objetivo)[:\s]*\*\*\s*(.+)",
        content,
        re.IGNORECASE,
    )
    if inline_desc_match:
        metadata["description"] = inline_desc_match.group(1).strip()[:300]

    # Extract description from common heading patterns in IDENTITY.md files
    purpose_match = re.search(
        r"##\s*(?:Prop[oó]sito|Objetivos?|Purpose|Mission|Goal|Perfil|Rol"
        r"|Description|Identidad)\s*\n+(.+?)(?:\n\n|\n##)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if purpose_match:
        desc = purpose_match.group(1).strip()
        # Clean markdown formatting
        desc = re.sub(r"\*\*|__", "", desc)
        desc = re.sub(r"\n\d+\.\s+", " ", desc)
        metadata["description"] = desc[:300]

    # Extract tools from markdown tables or lists
    tools_section = re.search(
        r"##\s*(?:Tools|Herramientas|Stack)[^\n]*\n(.*?)(?:\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if tools_section:
        tools_text = tools_section.group(1)
        tools = re.findall(r"`([^`]+)`", tools_text)
        if tools:
            metadata["tools"] = tools[:10]

    # Extract skills from Skills section (various naming conventions)
    skills_section = re.search(
        r"##\s*(?:Skills?|Capacidades|Capabilities|Skills?\s+Asociad[ao]s?"
        r"|Skills?\s+Utilizad[ao]s?)[^\n]*\n(.*?)(?:\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if skills_section:
        skills_text = skills_section.group(1)
        skills = re.findall(r"`([^`]+)`", skills_text)
        if skills:
            metadata["skills"] = skills[:20]

    return metadata


def _parse_identity_frontmatter(content: str, agent_name: str) -> tuple[dict[str, Any], str]:
    """Parsea el frontmatter YAML de un IDENTITY.md.

    Args:
        content: Contenido completo del archivo.
        agent_name: Nombre del agente (para logs).

    Returns:
        Tupla (metadata_dict, markdown_body).
    """
    metadata: dict[str, Any] = {}
    markdown_body = content

    if not content.startswith("---"):
        return metadata, markdown_body

    parts = content.split("---", 2)
    if len(parts) < 3:
        return metadata, markdown_body

    import yaml  # type: ignore[import-untyped]  # lazy import

    try:
        yaml_data = yaml.safe_load(parts[1])
    except yaml.YAMLError as yaml_err:
        logger.warning("YAML inválido en IDENTITY.md de agente %s: %s", agent_name, yaml_err)
        yaml_data = None

    if isinstance(yaml_data, dict):
        metadata = yaml_data
    markdown_body = parts[2]
    return metadata, markdown_body


def _resolve_agent_metadata(
    metadata: dict[str, Any], markdown_body: str, agent_name: str
) -> AgentConfig:
    """Construye AgentConfig a partir de metadata parseada.

    Args:
        metadata: Dict con campos del agente.
        markdown_body: Cuerpo Markdown del IDENTITY.md.
        agent_name: Nombre del directorio del agente.

    Returns:
        AgentConfig construido.
    """
    # Resolve tier
    tier = metadata.get("tier", 5)
    if isinstance(tier, str):
        tier_digits = re.search(r"\d+", str(tier))
        tier = int(tier_digits.group()) if tier_digits else 5
    tier = max(1, min(6, int(tier)))

    role = metadata.get("role", metadata.get("description", agent_name.replace("-", " ").title()))

    # Resolve list-or-string fields
    raw_skills = metadata.get("skills", [])
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",")]
    raw_tools = metadata.get("tools", [])
    if isinstance(raw_tools, str):
        raw_tools = [t.strip() for t in raw_tools.split(",")]

    goal = metadata.get("goal", metadata.get("description", ""))
    if not goal:
        first_para = re.search(r"(?:^|\n)(?!#)([A-Z\u00C0-\u024F].{20,})", markdown_body)
        if first_para:
            goal = first_para.group(1).strip()[:300]

    backstory = metadata.get("backstory", "")
    if not backstory and metadata.get("description"):
        backstory = metadata["description"]
    if not backstory and goal:
        backstory = goal

    return AgentConfig(
        name=agent_name,
        tier=tier,
        role=role,
        goal=goal,
        backstory=backstory,
        skills=raw_skills,
        tools=raw_tools,
    )


def _discover_agents(agents_dir: Path | None = None) -> dict[str, AgentConfig]:
    """Auto-discover agents from IDENTITY.md files.

    Scans .agent/agents/ directory for IDENTITY.md files and creates
    AgentConfig entries automatically. Supports two formats:

    1. YAML frontmatter (between --- markers) with fields like name, tier,
       description, tools, skills.
    2. Markdown-only format with **Nombre:**, **Rol:**, **Tier:** patterns.

    Falls back to hardcoded registry if discovery fails or finds no agents.

    Args:
        agents_dir: Directory containing agent subdirectories.
            Defaults to .agent/agents/ relative to this file.

    Returns:
        Dictionary mapping agent names to AgentConfig instances.
    """
    if agents_dir is None:
        agents_dir = Path(__file__).parent.parent / "agents"

    discovered: dict[str, AgentConfig] = {}
    if not agents_dir.exists():
        logger.warning("Agents directory not found: %s", agents_dir)
        return discovered

    deprecated_agent_names = {"project-planner", "qa-automation-engineer", "qa-specialist"}

    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith(("_", ".")):
            continue
        if agent_dir.name in deprecated_agent_names:
            logger.debug("Skipping deprecated agent in registry: %s", agent_dir.name)
            continue
        identity_file = agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            continue
        try:
            content = identity_file.read_text(encoding="utf-8")
            metadata, markdown_body = _parse_identity_frontmatter(content, agent_dir.name)

            md_metadata = _parse_markdown_metadata(markdown_body)
            for key, value in md_metadata.items():
                if key not in metadata:
                    metadata[key] = value

            if not metadata:
                logger.debug("No metadata found for agent %s", agent_dir.name)
                continue

            discovered[agent_dir.name] = _resolve_agent_metadata(
                metadata, markdown_body, agent_dir.name
            )
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to discover agent %s: %s", agent_dir.name, e)

    if discovered:
        logger.info("Auto-discovered %d agents from %s", len(discovered), agents_dir)
    return discovered


# =============================================================================
# AGENT REGISTRY (auto-discovered with hardcoded fallback)
# =============================================================================

_HARDCODED_AGENT_REGISTRY: dict[str, AgentConfig] = {
    # Tier 1: Planning
    "planner": AgentConfig(
        name="planner",
        tier=1,
        role="Dynamic Strategy Planner",
        goal="Break down complex tasks into actionable milestones with clear deliverables",
        backstory="""You are an expert project planner with 15+ years of experience in
        software development. You excel at decomposing complex requirements into
        manageable tasks, estimating effort, and creating realistic roadmaps.
        Includes WBS, estimation, roadmaps, dependency analysis, and risk management.""",
        skills=[
            "task-decomposition",
            "estimation",
            "roadmap",
            "milestones",
            "risk-assessment",
            "wbs",
        ],
        tools=["read_file", "search_codebase", "create_plan"],
    ),
    "product-manager": AgentConfig(
        name="product-manager",
        tier=1,
        role="Product Manager",
        goal="Transform business needs into clear user stories with acceptance criteria",
        backstory="""You are a seasoned product manager who bridges the gap between
        business stakeholders and development teams. You write crystal-clear user
        stories and ensure alignment with business objectives.""",
        skills=["user-stories", "requirements", "acceptance-criteria", "prioritization"],
        tools=["read_file", "create_document"],
    ),
    # product-owner: DEPRECATED -> consolidated into planner (Tier 1)
    # Tier 2: Development
    "frontend-specialist": AgentConfig(
        name="frontend-specialist",
        tier=2,
        role="Senior Frontend Developer",
        goal="Build responsive, accessible, and performant user interfaces",
        backstory="""You are a frontend expert specializing in React, Next.js, and
        modern CSS. You create beautiful, accessible interfaces that work flawlessly
        across all devices. You follow best practices for performance and SEO.""",
        skills=["react", "nextjs", "tailwind", "typescript", "accessibility", "responsive"],
        tools=["read_file", "write_file", "execute_code", "search_codebase"],
    ),
    "backend-specialist": AgentConfig(
        name="backend-specialist",
        tier=2,
        role="Senior Backend Developer",
        goal="Design and implement robust, scalable APIs and business logic",
        backstory="""You are a backend expert with deep knowledge of Node.js, Python,
        and API design patterns. You build secure, scalable systems that handle
        millions of requests. You follow SOLID principles and clean architecture.""",
        skills=["nodejs", "python", "fastapi", "rest", "graphql", "authentication", "caching"],
        tools=["read_file", "write_file", "execute_code", "database_query"],
    ),
    "database-architect": AgentConfig(
        name="database-architect",
        tier=2,
        role="Database Architect",
        goal="Design efficient database schemas and optimize query performance",
        backstory="""You are a database expert with experience in SQL and NoSQL
        databases. You design schemas that balance normalization with performance,
        and you can optimize any query to run in milliseconds.""",
        skills=["sql", "nosql", "schema-design", "optimization", "migrations", "indexing"],
        tools=["read_file", "write_file", "database_query", "explain_query"],
    ),
    "mobile-developer": AgentConfig(
        name="mobile-developer",
        tier=2,
        role="Mobile Developer",
        goal="Build native-quality mobile apps with cross-platform frameworks",
        backstory="""You are a mobile development expert specializing in React Native
        and Flutter. You create apps that feel native on both iOS and Android, with
        smooth animations and offline-first architecture.""",
        skills=["react-native", "flutter", "ios", "android", "offline-first"],
        tools=["read_file", "write_file", "execute_code"],
    ),
    # Tier 3: Quality
    "test-engineer": AgentConfig(
        name="test-engineer",
        tier=3,
        role="Test Engineer",
        goal="Ensure code quality through comprehensive testing strategies",
        backstory="""You are a testing expert who believes that untested code is
        broken code. You design test strategies that catch bugs early, from unit
        tests to integration tests to E2E tests.""",
        skills=["unit-testing", "integration-testing", "e2e-testing", "coverage", "mocking"],
        tools=["read_file", "write_file", "execute_tests", "coverage_report"],
    ),
    # qa-automation-engineer: DEPRECATED -> use test-engineer instead
    "security-auditor": AgentConfig(
        name="security-auditor",
        tier=3,
        role="Security Auditor",
        goal="Identify and remediate security vulnerabilities",
        backstory="""You are a security expert with deep knowledge of OWASP Top 10,
        secure coding practices, and vulnerability assessment. You think like an
        attacker to protect systems from real threats.""",
        skills=["owasp", "vulnerabilities", "code-review", "penetration-testing", "compliance"],
        tools=["read_file", "security_scan", "dependency_check"],
    ),
    "performance-optimizer": AgentConfig(
        name="performance-optimizer",
        tier=3,
        role="Performance Engineer",
        goal="Optimize application performance for speed and efficiency",
        backstory="""You are obsessed with performance. You profile applications to
        find bottlenecks, optimize database queries, implement caching strategies,
        and ensure sub-second response times.""",
        skills=["profiling", "caching", "lazy-loading", "bundle-optimization", "web-vitals"],
        tools=["read_file", "profile_code", "lighthouse_audit", "bundle_analyze"],
    ),
    # Tier 4: Operations
    "devops-engineer": AgentConfig(
        name="devops-engineer",
        tier=4,
        role="DevOps Engineer",
        goal="Build and maintain robust CI/CD pipelines and infrastructure",
        backstory="""You are a DevOps expert who automates everything. You design
        CI/CD pipelines that deploy multiple times per day with zero downtime. You
        love Docker, Kubernetes, and infrastructure as code.""",
        skills=["docker", "kubernetes", "ci-cd", "github-actions", "terraform", "monitoring"],
        tools=["read_file", "write_file", "execute_shell", "deploy"],
    ),
    "documentation-writer": AgentConfig(
        name="documentation-writer",
        tier=4,
        role="Technical Writer",
        goal="Create clear, comprehensive documentation",
        backstory="""You are a technical writer who makes complex systems
        understandable. You write documentation that developers actually read,
        with clear examples and diagrams.""",
        skills=["technical-writing", "api-docs", "tutorials", "diagrams", "readme"],
        tools=["read_file", "write_file", "generate_diagram"],
    ),
    "debugger": AgentConfig(
        name="debugger",
        tier=4,
        role="Debug Specialist",
        goal="Diagnose and resolve complex bugs efficiently",
        backstory="""You are a debugging expert with an uncanny ability to find the
        root cause of any bug. You use systematic approaches, logging, and tracing
        to hunt down issues that others have given up on.""",
        skills=["root-cause-analysis", "logging", "tracing", "debugging", "reproduction"],
        tools=["read_file", "execute_code", "add_logging", "trace_execution"],
    ),
    # Tier 5: Specialized
    "game-developer": AgentConfig(
        name="game-developer",
        tier=5,
        role="Game Developer",
        goal="Create engaging game mechanics and systems",
        backstory="""You are a game developer with experience in both 2D and 3D games.
        You design game loops that keep players engaged, implement physics systems,
        and create smooth animations.""",
        skills=["game-mechanics", "physics", "animation", "state-machines", "collision"],
        tools=["read_file", "write_file", "execute_code"],
    ),
    "seo-specialist": AgentConfig(
        name="seo-specialist",
        tier=5,
        role="SEO Specialist",
        goal="Optimize websites for search engine visibility",
        backstory="""You are an SEO expert who understands how search engines work.
        You optimize content, meta tags, structured data, and Core Web Vitals to
        improve rankings and drive organic traffic.""",
        skills=["seo", "meta-tags", "structured-data", "core-web-vitals", "content-optimization"],
        tools=["read_file", "write_file", "seo_audit", "lighthouse_audit"],
    ),
    "code-archaeologist": AgentConfig(
        name="code-archaeologist",
        tier=5,
        role="Code Archaeologist",
        goal="Understand and modernize legacy codebases",
        backstory="""You are an expert at navigating legacy codebases. You can read
        ancient code written in outdated patterns, understand its purpose, and
        carefully refactor it without breaking existing functionality.""",
        skills=["legacy-code", "refactoring", "migration", "code-analysis", "documentation"],
        tools=["read_file", "write_file", "search_codebase", "dependency_graph"],
    ),
    # explorer-agent: DEPRECATED alias -> use explorer (auto-discovered from agents/explorer/)
    "penetration-tester": AgentConfig(
        name="penetration-tester",
        tier=5,
        role="Penetration Tester",
        goal="Identify security weaknesses through ethical hacking",
        backstory="""You are a penetration tester who thinks like a malicious hacker
        to protect systems. You find vulnerabilities before attackers do, using
        both automated tools and creative manual testing.""",
        skills=["ethical-hacking", "vulnerability-assessment", "exploit-development", "reporting"],
        tools=["security_scan", "fuzzing", "network_scan"],
    ),
    # ui-ux-master: DEPRECATED alias -> use ui-ux-designer (auto-discovered from agents/ui-ux-designer/)
    # Tier 6: UNS Business (Japanese HR)
    "uns-hr-specialist": AgentConfig(
        name="uns-hr-specialist",
        tier=6,
        role="Japanese HR Specialist",
        goal="Manage Japanese HR processes for staffing companies",
        backstory="""You are an HR specialist for Japanese派遣 (staffing) companies.
        You understand Japanese labor laws, 36協定, visa requirements, and payroll
        calculations including住民税 and 所得税.""",
        skills=["japanese-hr", "payroll", "visa-tracking", "labor-compliance", "36kyotei"],
        tools=["calculate_payroll", "check_visa", "generate_contract"],
    ),
    "haken-document-specialist": AgentConfig(
        name="haken-document-specialist",
        tier=6,
        role="Haken Document Specialist",
        goal="Generate compliant派遣 documents and contracts",
        backstory="""You are a document specialist for Japanese派遣 companies. You
        generate legally compliant contracts (派遣契約書), work schedules, and
        official documents following Japanese business standards.""",
        skills=["contract-generation", "document-templates", "compliance", "japanese-business"],
        tools=["generate_contract", "create_schedule", "export_pdf"],
    ),
    "haken-system-architect": AgentConfig(
        name="haken-system-architect",
        tier=6,
        role="Haken System Architect",
        goal="Design systems for Japanese staffing operations",
        backstory="""You are a system architect who designs software for Japanese
        派遣 companies. You understand the unique requirements of staffing
        operations, including worker tracking, client billing, and compliance.""",
        skills=["system-design", "japanese-business", "compliance", "integration"],
        tools=["read_file", "write_file", "create_diagram"],
    ),
}

# Auto-discover agents from IDENTITY.md files, fall back to hardcoded registry
AGENT_REGISTRY: dict[str, AgentConfig] = _discover_agents()
if not AGENT_REGISTRY:
    logger.info("Using hardcoded agent registry as fallback")
    AGENT_REGISTRY = _HARDCODED_AGENT_REGISTRY
else:
    # Merge: hardcoded entries fill in any agents not found via discovery,
    # and enrich discovered agents with hardcoded goal/backstory/skills
    for name, hardcoded_config in _HARDCODED_AGENT_REGISTRY.items():
        if name not in AGENT_REGISTRY:
            AGENT_REGISTRY[name] = hardcoded_config
        else:
            # Enrich discovered config with hardcoded fields where missing
            discovered = AGENT_REGISTRY[name]
            updates: dict[str, Any] = {}
            if not discovered.goal and hardcoded_config.goal:
                updates["goal"] = hardcoded_config.goal
            if not discovered.backstory and hardcoded_config.backstory:
                updates["backstory"] = hardcoded_config.backstory
            # Merge skills: union of discovered + hardcoded (preserving order)
            if hardcoded_config.skills:
                merged_skills = list(discovered.skills)
                for skill in hardcoded_config.skills:
                    if skill not in merged_skills:
                        merged_skills.append(skill)
                updates["skills"] = merged_skills
            if updates:
                discovered = discovered.model_copy(update=updates)
            AGENT_REGISTRY[name] = discovered


# =============================================================================
# ORCHESTRATOR
# =============================================================================


class AntigravityOrchestrator:
    """
    The brain of Antigravity - coordinates all specialist agents.

    Features:
    - Intelligent task decomposition
    - Parallel execution within tiers
    - Shared memory across agents
    - A2A protocol support
    - OpenTelemetry observability
    """

    def __init__(
        self,
        verbose: bool = False,
        max_agents: int = 5,
        enable_memory: bool = True,
        enable_telemetry: bool = True,
        enable_mesh: bool = True,
        enable_memory_bus: bool = True,
    ) -> None:
        self.verbose = verbose
        self.max_agents = max_agents
        self.enable_memory = enable_memory
        self.enable_telemetry = enable_telemetry
        self.enable_mesh = enable_mesh
        self.enable_memory_bus = enable_memory_bus

        self.agents: dict[str, AgentConfig] = AGENT_REGISTRY
        self.memory: UnifiedMemory | None = self._init_memory() if enable_memory else None
        self.memory_bus: MemoryBus | None = self._init_memory_bus() if enable_memory_bus else None
        self.telemetry: dict[str, Any] | None = self._init_telemetry() if enable_telemetry else None
        self.mesh: AgentMesh | None = self._init_mesh() if enable_mesh else None
        self._intelligence_hub: "IntelligenceHub | None" = (  # noqa: UP037
            self._init_intelligence_hub()
        )

        # Pool de skills disponibles (incluye skills de plugins activados)
        self._plugin_skill_pool: dict[str, set[str]] = {}  # plugin_name -> skills
        self._plugin_manager: Any | None = self._init_plugin_manager()

        logger.info("Orchestrator initialized with %d agents", len(self.agents))

    def _init_intelligence_hub(self) -> "IntelligenceHub | None":  # noqa: UP037
        """Initialize Intelligence Hub for data-driven agent selection."""
        try:
            from .intelligence_hub import get_intelligence_hub

            return get_intelligence_hub()
        except ImportError:
            logger.debug("Intelligence Hub not available")
            return None

    def _init_memory(self) -> UnifiedMemory:
        """Initialize shared memory system."""
        memory = get_unified_memory(MEMORY_DIR)
        return memory

    def _init_plugin_manager(self) -> Any | None:
        """Initialize PluginManager and sync active plugins into skill pool."""
        try:
            from .plugin_manager import PluginManager, PluginState

            manager = PluginManager(orchestrator=self)
            manager.discover()

            for info in manager.list_plugins(state=PluginState.ACTIVE):
                self.register_plugin_skills(
                    info.metadata.name, manager._get_plugin_skill_names(info)
                )

            logger.info(
                "PluginManager initialized (%d active plugins)",
                len(manager.active_plugins),
            )
            return manager
        except Exception as exc:
            logger.warning("PluginManager not available for orchestrator: %s", exc)
            return None

    def _init_memory_bus(self) -> MemoryBus | None:
        """Initialize memory bus for semantic context when available."""
        try:
            return get_memory_bus(MEMORY_DIR)
        except (ImportError, RuntimeError, OSError) as exc:
            logger.warning("MemoryBus not available: %s", exc)
            return None

    def _init_telemetry(self) -> dict[str, Any] | None:
        """Initialize OpenTelemetry."""
        try:
            from .telemetry import setup_telemetry

            return setup_telemetry("antigravity.orchestrator")
        except ImportError:
            logger.warning("Telemetry module not available")
            return None

    def _init_mesh(self) -> AgentMesh | None:
        """Initialize agent mesh and register available agents."""
        try:
            mesh = get_agent_mesh()
            if self.memory and hasattr(self.memory, "shared_memory"):
                mesh.set_persistence(self.memory.shared_memory)
            for name, config in self.agents.items():
                mesh.register_agent(
                    agent_name=name,
                    capabilities=config.skills,
                    metadata={"tier": config.tier, "role": config.role},
                )
            return mesh
        except (ImportError, RuntimeError, AttributeError) as exc:
            logger.warning(f"Agent mesh not available: {exc}")
            return None

    # =========================================================================
    # PLUGIN INTEGRATION
    # =========================================================================

    def register_plugin_skills(self, plugin_name: str, skills: list[str]) -> None:
        """Registra las skills de un plugin activado en el pool del orquestador.

        Llamado automáticamente por PluginManager.activate() cuando hay un
        orquestador configurado. Permite que los agentes usen skills de plugins
        sin reiniciar el ecosistema.

        Args:
            plugin_name: Nombre del plugin que se activó.
            skills: Lista de nombres de skills que expone el plugin.
        """
        self._plugin_skill_pool[plugin_name] = set(skills)
        logger.info(
            "Plugin '%s' registered %d skills in orchestrator pool",
            plugin_name,
            len(skills),
        )

    def unregister_plugin_skills(self, plugin_name: str) -> None:
        """Elimina las skills de un plugin desactivado del pool.

        Args:
            plugin_name: Nombre del plugin que se desactivó.
        """
        removed = self._plugin_skill_pool.pop(plugin_name, set())
        if removed:
            logger.info(
                "Plugin '%s' unregistered %d skills from orchestrator pool",
                plugin_name,
                len(removed),
            )

    def get_available_skills(self) -> set[str]:
        """Retorna el conjunto completo de skills disponibles.

        Incluye skills base de los agentes registrados más skills de
        plugins activados.

        Returns:
            Set de nombres de skills disponibles.
        """
        base_skills: set[str] = set()
        for config in self.agents.values():
            base_skills.update(config.skills)

        plugin_skills: set[str] = set()
        for skills in self._plugin_skill_pool.values():
            plugin_skills.update(skills)

        return base_skills | plugin_skills

    def get_plugin_skill_pool(self) -> dict[str, list[str]]:
        """Retorna el mapa de plugin -> skills para inspección.

        Returns:
            Diccionario plugin_name -> lista de skills.
        """
        return {name: sorted(skills) for name, skills in self._plugin_skill_pool.items()}

    def analyze_task(self, task_description: str) -> dict[str, Any]:
        """
        Analyze a task and determine required skills and agents.

        Args:
            task_description: Natural language description of the task

        Returns:
            Analysis with detected skills, complexity, and recommended agents
        """
        # Keyword to skill mapping
        keyword_skills = {
            # Frontend
            "ui": ["react", "ui-design", "tailwind"],
            "frontend": ["react", "nextjs", "typescript"],
            "react": ["react", "nextjs"],
            "component": ["react", "ui-design"],
            "responsive": ["responsive", "tailwind"],
            "accessibility": ["accessibility", "a11y"],
            # Backend
            "api": ["rest", "graphql", "fastapi"],
            "backend": ["nodejs", "python", "fastapi"],
            "auth": ["authentication", "security"],
            "database": ["sql", "schema-design"],
            # Testing
            "test": ["unit-testing", "e2e-testing"],
            "bug": ["debugging", "root-cause-analysis"],
            # DevOps
            "deploy": ["ci-cd", "docker"],
            "docker": ["docker", "kubernetes"],
            "ci": ["ci-cd", "github-actions"],
            # Japanese HR
            "payroll": ["payroll", "japanese-hr"],
            "給与": ["payroll", "japanese-hr"],
            "visa": ["visa-tracking", "compliance"],
            "在留": ["visa-tracking", "compliance"],
            "36協定": ["labor-compliance", "36kyotei"],
            "派遣": ["japanese-business", "compliance"],
            # Excel / Office
            "excel": ["excel-super-agent"],
            "xlsx": ["excel-super-agent"],
            "xlsm": ["excel-super-agent"],
            "kobetsu": ["excel-super-agent"],
            "haken": ["excel-super-agent"],
            "planilla": ["excel-super-agent"],
            "pivot": ["excel-super-agent"],
            "dashboard": ["excel-super-agent"],
            "vba": ["excel-super-agent"],
            "dax": ["excel-super-agent"],
            "power query": ["excel-super-agent"],
            "macro": ["excel-super-agent"],
            "chart": ["excel-super-agent"],
            "formato condicional": ["excel-super-agent"],
            "個別契約": ["excel-super-agent"],
            "勤怠": ["excel-super-agent"],
            "有給": ["excel-super-agent"],
            "賃金": ["excel-super-agent"],
            "履歴書": ["excel-super-agent"],
        }

        task_lower = task_description.lower()
        detected_skills = set()

        for keyword, skills in keyword_skills.items():
            if keyword in task_lower:
                detected_skills.update(skills)

        # Calculate complexity
        if len(detected_skills) > 8:
            complexity = "high"
        elif len(detected_skills) > 4:
            complexity = "medium"
        else:
            complexity = "low"

        return {
            "description": task_description,
            "detected_skills": list(detected_skills),
            "complexity": complexity,
            "analyzed_at": datetime.now().isoformat(),
        }

    def select_agents(
        self, analysis: dict[str, Any], max_agents: int | None = None
    ) -> list[tuple[str, AgentConfig, float]]:
        """
        Select the best agents for a task based on skill matching.

        Args:
            analysis: Task analysis from analyze_task()
            max_agents: Maximum number of agents to select

        Returns:
            List of (agent_name, agent_config, score) tuples
        """
        max_agents = max_agents or self.max_agents
        required_skills = set(analysis.get("detected_skills", []))

        scored_agents: list[tuple[str, AgentConfig, float]] = []
        for name, config in self.agents.items():
            agent_skills = set(config.skills)
            matching = agent_skills & required_skills

            if matching or not required_skills:
                # Score: skill match ratio + tier bonus
                # When no skills required (task didn't match keywords), all agents score via tier bonus
                skill_score = len(matching) / len(required_skills) if required_skills else 0.5
                tier_bonus = (6 - config.tier) * 0.1  # Lower tier = higher priority
                score = skill_score * 0.7 + tier_bonus * 0.3
                scored_agents.append((name, config, round(score, 3)))

        # Sort by score descending
        scored_agents.sort(key=lambda x: x[2], reverse=True)

        # Re-rankear con Intelligence Hub si disponible (datos historicos reales)
        if self._intelligence_hub and scored_agents:
            try:
                candidates = [
                    {"name": name, "tier": cfg.tier, "skills": cfg.skills, "description": cfg.role}
                    for name, cfg, _ in scored_agents
                ]
                ranked = self._intelligence_hub.rank_agents(
                    analysis.get("description", ""), candidates, top_k=max_agents
                )
                # Rebuild con scores del hub (combina skill match + historial)
                hub_order = {r.agent_name: r.score for r in ranked}
                scored_agents.sort(
                    key=lambda x: hub_order.get(x[0], x[2]),
                    reverse=True,
                )
            except Exception as e:
                logger.debug("Intelligence Hub ranking fallback: %s", e)

        return scored_agents[:max_agents]

    def create_execution_plan(
        self, task_description: str, max_agents: int | None = None
    ) -> ExecutionPlan:
        """
        Create a detailed execution plan for a task.

        Args:
            task_description: Natural language task description
            max_agents: Maximum agents to involve

        Returns:
            ExecutionPlan with phases and agent assignments
        """
        import uuid

        analysis = self.analyze_task(task_description)
        selected_agents = self.select_agents(analysis, max_agents)

        # Group agents by tier for parallel execution
        tiers: dict[int, list[dict[str, Any]]] = {}
        for name, config, score in selected_agents:
            tier = config.tier
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(
                {
                    "agent": name,
                    "role": config.role,
                    "score": score,
                    "skills": config.skills[:5],  # Top 5 skills
                }
            )

        # Create phases (sequential between tiers, parallel within)
        phases: list[dict[str, Any]] = []
        for tier in sorted(tiers.keys()):
            agents = tiers[tier]
            phases.append(
                {
                    "phase": tier,
                    "tier_name": AgentTier(tier).name,
                    "parallel": len(agents) > 1,
                    "agents": agents,
                }
            )

        plan = ExecutionPlan(
            id=str(uuid.uuid4())[:8],
            original_task=task_description,
            phases=phases,
            total_agents=len(selected_agents),
            estimated_complexity=analysis["complexity"],
        )

        # Store decision in memory
        if self.memory:
            decision = {
                "plan_id": plan.id,
                "task": task_description,
                "agents": [a[0] for a in selected_agents],
                "timestamp": datetime.now().isoformat(),
            }
            if hasattr(self.memory, "shared_memory"):
                self.memory.shared_memory.store("decision", decision, agent="orchestrator")
            elif hasattr(self.memory, "store"):
                # NOTE: UnifiedMemory.store is async and expects MemoryType enum;
                # this call is a legacy duck-typed fallback that may target a
                # different memory backend.  Suppressed until the caller is fixed.
                self.memory.store("decision", decision, agent="orchestrator")  # type: ignore[arg-type,unused-coroutine]
            if self.memory_bus:
                self.memory_bus.store(
                    key=f"plan:{plan.id}",
                    value=decision,
                    memory_type="decision",
                    agent="orchestrator",
                )

        return plan

    async def execute(
        self,
        task_description: str,
        max_agents: int | None = None,
        dry_run: bool = False,
        callback: Callable[[str], Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a task with intelligent agent delegation.

        Args:
            task_description: What to accomplish
            max_agents: Maximum agents to use
            dry_run: If True, only plan without executing
            callback: Optional callback for progress updates

        Returns:
            Execution results with outputs from all agents
        """
        plan = self.create_execution_plan(task_description, max_agents)

        # Pre-ejecucion: consultar Intelligence Hub para contexto
        intel_context: "IntelligenceContext | None" = None  # noqa: UP037
        if self._intelligence_hub:
            try:
                intel_context = self._intelligence_hub.query_intelligence(task_description)
                if intel_context and intel_context.learned_avoidances:
                    logger.info(
                        "Intelligence Hub: %d avoidances detectados para esta tarea",
                        len(intel_context.learned_avoidances),
                    )
            except Exception as e:
                logger.debug("Intelligence Hub pre-ejecucion fallback: %s", e)

        self._print_plan(plan)

        if dry_run:
            logger.info("DRY RUN - No execution performed")
            return {"plan": plan.model_dump(), "dry_run": True}

        # Execute phases sequentially, agents within phase in parallel
        results: list[dict[str, Any]] = []
        for phase in plan.phases:
            phase_results = await self._execute_phase(phase, callback, plan.original_task)
            results.extend(phase_results)

        if self.memory and hasattr(self.memory, "shared_memory"):
            self.memory.shared_memory.add_session_history(
                {
                    "task": task_description,
                    "plan_id": plan.id,
                    "agents": [r.get("agent") for r in results],
                    "completed_at": datetime.now().isoformat(),
                    "results": results,
                }
            )
        if self.memory_bus:
            self.memory_bus.store(
                key=f"execution:{plan.id}",
                value={
                    "task": task_description,
                    "agents": [r.get("agent") for r in results],
                    "completed_at": datetime.now().isoformat(),
                },
                memory_type="context",
                agent="orchestrator",
            )

        return {
            "plan": plan.model_dump(),
            "results": results,
            "completed_at": datetime.now().isoformat(),
        }

    async def _execute_phase(
        self,
        phase: dict[str, Any],
        callback: Callable[[str], Any] | None = None,
        context_input: str = "",
    ) -> list[dict[str, Any]]:
        """Execute all agents in a phase (parallel if multiple)."""
        agents = phase.get("agents", [])

        if phase.get("parallel") and len(agents) > 1:
            # Parallel execution
            coros = [
                self._execute_agent(agent_info, callback, context_input) for agent_info in agents
            ]
            gathered: list[dict[str, Any] | BaseException] = await asyncio.gather(
                *coros,
                return_exceptions=True,
            )
            return [r for r in gathered if isinstance(r, dict)]
        else:
            # Sequential execution
            sequential_results: list[dict[str, Any]] = []
            for agent_info in agents:
                result = await self._execute_agent(agent_info, callback, context_input)
                sequential_results.append(result)
            return sequential_results

    def _should_skip_external_llm(self, context_input: str) -> tuple[bool, bool, str]:
        """Determina si se deben saltar los motores LLM externos.

        Args:
            context_input: Contexto de la tarea.

        Returns:
            Tupla (skip_external_llm, llm_enabled, llm_mode).
        """
        import os

        llm_enabled = os.getenv("ANTIGRAVITY_LLM_ENABLED", "true").lower() not in (
            "false",
            "0",
            "off",
            "no",
        )
        llm_mode = os.getenv("ANTIGRAVITY_LLM_MODE", "auto").lower()

        skip = not llm_enabled or llm_mode == "ide"
        if not HAS_CREWAI:
            skip = True
        if not str(context_input).strip():
            skip = True
        # Only skip ALL tiers if BOTH engines are missing
        if not HAS_CREWAI and not HAS_AUTONOMOUS_LOOP:
            skip = True
        return skip, llm_enabled, llm_mode

    def _record_intelligence_outcome(
        self,
        context_input: str,
        agent_name: str | None,
        success: bool,
        quality_score: float,
        duration: float,
    ) -> None:
        """Registra el resultado en Intelligence Hub si está disponible."""
        if not self._intelligence_hub:
            return
        try:
            self._intelligence_hub.record_outcome(
                task=context_input or "unknown",
                agent_name=agent_name or "unknown",
                success=success,
                quality_score=quality_score,
                duration_ms=int(duration * 1000),
            )
        except Exception:
            pass

    async def _try_crewai_execution(
        self,
        agent_name: str | None,
        agent_config: AgentConfig | None,
        context_input: str,
        start_time: datetime,
    ) -> dict[str, Any] | None:
        """Intenta ejecutar via CrewAI (Tier 1).

        Returns:
            Dict resultado si exitoso, None si falla o no aplica.
        """
        import os

        if not (
            HAS_CREWAI
            and (
                os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("OPENROUTER_API_KEY")
                or os.getenv("XAI_API_KEY")
            )
        ):
            return None

        _role = agent_config.role if agent_config else str(agent_name)
        _goal = agent_config.goal if agent_config else ""
        _backstory = self._apply_persona_modifier(agent_config.backstory if agent_config else "")
        _allow_delegation = agent_config.allow_delegation if agent_config else False

        try:
            crew_agent = Agent(
                role=_role,
                goal=_goal,
                backstory=_backstory,
                verbose=self.verbose,
                allow_delegation=_allow_delegation,
            )
            task = Task(
                description=context_input
                or f"Execute the assigned portion of the project: {agent_name}",
                expected_output="Detailed results of the agent's work",
                agent=crew_agent,
            )
            crew = Crew(
                agents=[crew_agent], tasks=[task], process=Process.sequential, verbose=self.verbose
            )

            try:
                result = await asyncio.wait_for(asyncio.to_thread(crew.kickoff), timeout=600.0)
            except TimeoutError as te:
                raise RuntimeError(f"CrewAI execution timed out after 600s: {te}") from te

            duration = (datetime.now() - start_time).total_seconds()
            self._record_intelligence_outcome(context_input, agent_name, True, 0.85, duration)
            return {
                "agent": agent_name,
                "status": "completed",
                "output": str(result),
                "duration_seconds": duration,
                "execution_mode": "crewai",
            }
        except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError) as e:
            logger.error(f"CrewAI execution failed for {agent_name}: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            self._record_intelligence_outcome(context_input, agent_name, False, 0.0, duration)
            return None

    @staticmethod
    def _apply_persona_modifier(system_prompt: str) -> str:
        """Aplica el modificador de persona al system prompt si ANTIGRAVITY_PERSONA esta definido.

        Args:
            system_prompt: Prompt original del agente.

        Returns:
            Prompt modificado con instrucciones de estilo segun la persona.
        """
        import os

        persona = os.getenv("ANTIGRAVITY_PERSONA", "").lower()
        if not persona or persona == "neutral":
            return system_prompt

        if persona == "jpkken":
            custom = os.getenv("ANTIGRAVITY_PERSONA_CUSTOM", "")
            if custom:
                return system_prompt + f"\n\n[Communication Style: Jpkken — {custom}]"
            return system_prompt

        modifiers = {
            "gentleman": (
                "\n\n[Communication Style: Gentleman — Teach, explain and guide with detail. "
                "Be thorough in your explanations, provide context and reasoning. "
                "Use a warm, educational tone. When presenting options, explain trade-offs.]"
            ),
            "concise": (
                "\n\n[Communication Style: Concise — Minimal answers, no elaboration. "
                "Skip preamble, context, and explanations unless explicitly asked. "
                "Use bullet points over paragraphs. One sentence when one sentence suffices.]"
            ),
        }
        modifier = modifiers.get(persona)
        if modifier:
            return system_prompt + modifier
        return system_prompt

    async def _try_autonomous_loop_execution(
        self,
        agent_name: str | None,
        agent_config: AgentConfig | None,
        context_input: str,
        start_time: datetime,
    ) -> dict[str, Any] | None:
        """Intenta ejecutar via AutonomousLoop (Tier 2).

        Returns:
            Dict resultado si exitoso, None si falla o no aplica.
        """
        import os

        if not (
            HAS_AUTONOMOUS_LOOP
            and agent_config
            and (
                os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
                or os.getenv("OPENROUTER_API_KEY")
                or os.getenv("XAI_API_KEY")
            )
        ):
            return None

        try:
            logger.info(f"Agent {agent_name}: using AutonomousLoop fallback (no CrewAI)")
            loop = AutonomousLoop(max_iterations=8, verbose=self.verbose)
            system_prompt = self._apply_persona_modifier(
                f"You are {agent_config.role}. {agent_config.goal}\n\n{agent_config.backstory}"
            )
            try:
                loop_result = await asyncio.wait_for(
                    loop.run(
                        task=context_input or "Execute assigned task",
                        system_prompt=system_prompt,
                        agent_name=str(agent_name) if agent_name else "",
                    ),
                    timeout=600.0,
                )
            except TimeoutError as te:
                raise RuntimeError(f"AutonomousLoop execution timed out after 600s: {te}") from te

            duration = (datetime.now() - start_time).total_seconds()
            self._record_intelligence_outcome(context_input, agent_name, True, 0.75, duration)
            return {
                "agent": agent_name,
                "status": "completed",
                "output": loop_result.final_output or str(loop_result),
                "duration_seconds": duration,
                "execution_mode": "autonomous_loop",
            }
        except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"AutonomousLoop fallback failed for {agent_name}: {e}")
            return None

    async def _try_script_execution(
        self,
        agent_name: str | None,
        context_input: str,
        start_time: datetime,
    ) -> dict[str, Any] | None:
        """Intenta ejecutar el script del agente directamente (Tier 3).

        Returns:
            Dict resultado si exitoso, None si no hay script o falla.
        """
        agent_dir: Path = AGENTS_DIR / str(agent_name)
        scripts_dir: Path = agent_dir / "scripts"
        should_run_script = bool(str(context_input).strip())
        agent_scripts = (
            list(scripts_dir.glob("*.py")) if should_run_script and scripts_dir.exists() else []
        )

        if not agent_scripts:
            return None

        logger.info(f"Agent {agent_name}: executing script directly (no LLM)")
        script = agent_scripts[0]
        try:
            cmd = [sys.executable, str(script)]
            if context_input:
                cmd.append(context_input)
            proc_result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=60.0,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc_result.communicate(), timeout=60.0)
            except TimeoutError:
                proc_result.kill()
                stdout, stderr = b"", b"Execution timed out after 60s"

            duration = (datetime.now() - start_time).total_seconds()
            success = proc_result.returncode == 0
            output = stdout.decode(errors="replace") if success else stderr.decode(errors="replace")

            self._record_intelligence_outcome(
                context_input,
                agent_name,
                success,
                0.5 if success else 0.2,
                duration,
            )
            return {
                "agent": agent_name,
                "status": "completed" if success else "failed",
                "output": output
                or f"Agent {agent_name} script exited with code {proc_result.returncode}",
                "duration_seconds": duration,
                "execution_mode": "script_direct",
            }
        except (TimeoutError, OSError, RuntimeError) as e:
            logger.warning(f"Script execution failed for {agent_name}: {e}")
            return None

    async def _execute_agent(
        self,
        agent_info: dict[str, Any],
        callback: Callable[[str], Any] | None = None,
        context_input: str = "",
    ) -> dict[str, Any]:
        """Execute a single agent's task."""
        agent_name: str | None = agent_info.get("agent")
        agent_config: AgentConfig | None = self.agents.get(agent_name) if agent_name else None

        if callback:
            callback(f"Executing {agent_name}...")

        logger.info(f"Agent {agent_name} starting execution")
        start_time = datetime.now()

        skip_external_llm, llm_enabled, llm_mode = self._should_skip_external_llm(context_input)

        if skip_external_llm:
            logger.info(
                f"Agent {agent_name}: LLM external disabled "
                f"(llm_enabled={llm_enabled}, llm_mode={llm_mode}, context_input={bool(str(context_input).strip())}). "
                f"Skipping CrewAI/AutonomousLoop."
            )

        # Tier 1: CrewAI
        if not skip_external_llm:
            crewai_result = await self._try_crewai_execution(
                agent_name,
                agent_config,
                context_input,
                start_time,
            )
            if crewai_result:
                return crewai_result

        # Tier 1.5: LangGraph
        if not skip_external_llm and HAS_LANGGRAPH:
            try:
                engine = LangGraphEngine(
                    agent_dir=AGENT_DIR,
                    config={"agents": [agent_name], "max_iterations": 10},
                )
                langgraph_result = (
                    asyncio.get_event_loop().run_until_complete(
                        engine.execute(context_input or f"Ejecutar tarea de {agent_name}")
                    )
                    if not asyncio.get_event_loop().is_running()
                    else await engine.execute(context_input or f"Ejecutar tarea de {agent_name}")
                )
                duration = (datetime.now() - start_time).total_seconds()
                return {
                    "agent": agent_name,
                    "status": langgraph_result.get("status", "completed"),
                    "output": langgraph_result.get("final_output", str(langgraph_result)),
                    "duration_seconds": duration,
                    "execution_mode": "langgraph",
                    "checkpoint_id": langgraph_result.get("checkpoint_id", ""),
                    "iterations": langgraph_result.get("iterations", 0),
                }
            except Exception as e:
                logger.warning("LangGraph execution failed for %s: %s", agent_name, e)

        # Tier 2: AutonomousLoop
        if not skip_external_llm:
            auto_result = await self._try_autonomous_loop_execution(
                agent_name,
                agent_config,
                context_input,
                start_time,
            )
            if auto_result:
                return auto_result

        # Tier 3: Script directo
        script_result = await self._try_script_execution(agent_name, context_input, start_time)
        if script_result:
            return script_result

        # Fallback 4: IDE passthrough or simulated result
        duration = (datetime.now() - start_time).total_seconds()

        if skip_external_llm and llm_mode == "ide":
            # IDE mode: return agent context for the IDE's AI to process
            identity_file: Path = AGENTS_DIR / str(agent_name) / "IDENTITY.md"
            identity_context = ""
            if identity_file.exists():
                identity_context = identity_file.read_text(encoding="utf-8")[:2000]

            logger.info(
                f"Agent {agent_name}: IDE passthrough mode. "
                f"Returning context for IDE AI to process."
            )

            result = {
                "agent": agent_name,
                "status": "ide_passthrough",
                "output": (
                    f"[IDE_MODE] Agent {agent_name} context ready.\n\n"
                    f"--- AGENT IDENTITY ---\n{identity_context}\n\n"
                    f"--- TASK ---\n{context_input or 'No task specified'}\n\n"
                    f"The IDE AI (Claude Code, Cursor, etc.) should process this "
                    f"using its own intelligence."
                ),
                "duration_seconds": duration,
                "execution_mode": "ide_passthrough",
                "identity_context": identity_context,
                "task": context_input,
            }
        else:
            logger.warning(
                f"Agent {agent_name}: returning SIMULATED result. "
                f"No script found and no LLM API key available."
            )
            await asyncio.sleep(0.1)
            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "agent": agent_name,
                "status": "simulated",
                "output": (
                    f"[SIMULATED] Agent {agent_name} - No real execution available. "
                    f"Install crewai or set an API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                    f"OPENROUTER_API_KEY, or XAI_API_KEY) for real results. "
                    f"Or set ANTIGRAVITY_LLM_MODE=ide to use your IDE's AI."
                ),
                "duration_seconds": duration,
                "simulated": True,
                "execution_mode": "simulated",
            }

        if self._intelligence_hub:
            try:
                self._intelligence_hub.record_outcome(
                    task=context_input or "unknown",
                    agent_name=agent_name or "unknown",
                    success=False,
                    quality_score=0.3,
                    duration_ms=int(duration * 1000),
                )
            except Exception:
                pass

        return result

    def _print_plan(self, plan: ExecutionPlan) -> None:
        """Print execution plan to console."""
        logger.info("\n" + "=" * 70)
        logger.info("  ANTIGRAVITY ORCHESTRATOR v3.0")
        logger.info("=" * 70)
        logger.info(f"\n  Task: {plan.original_task}")
        logger.info(f"  Complexity: {plan.estimated_complexity}")
        logger.info(f"  Total Agents: {plan.total_agents}")
        logger.info(f"  Phases: {len(plan.phases)}")

        logger.info("\n" + "-" * 50)
        logger.info("  EXECUTION PLAN:")
        logger.info("-" * 50)

        for phase in plan.phases:
            parallel = " (parallel)" if phase.get("parallel") else ""
            tier_name = phase.get("tier_name", "")
            logger.info(f"\n  Phase {phase['phase']} - {tier_name}{parallel}:")

            for agent in phase.get("agents", []):
                logger.info(f"    - {agent['agent']} (score: {agent['score']:.2f})")
                logger.info(f"      Role: {agent['role']}")

        logger.info("\n" + "=" * 70)


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Antigravity Orchestrator v3.0 - Multi-Agent Task Execution"
    )
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Plan only")
    parser.add_argument("--max-agents", "-m", type=int, default=5, help="Max agents")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--list-agents", action="store_true", help="List all agents")

    args = parser.parse_args()

    if args.list_agents:
        print("\nAvailable Agents:")
        print("-" * 50)
        for name, config in AGENT_REGISTRY.items():
            print(f"  {name} (Tier {config.tier})")
            print(f"    Role: {config.role}")
            print(f"    Skills: {', '.join(config.skills[:5])}")
            print()
        return

    if not args.task:
        print("Error: Provide a task to execute")
        print('Usage: python orchestrator.py "Your task here"')
        return

    orchestrator = AntigravityOrchestrator(verbose=args.verbose)
    asyncio.run(orchestrator.execute(args.task, max_agents=args.max_agents, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
