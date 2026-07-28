"""Detección de dominios/capacidades y recomendación de agentes.

Extraído de ``IntelligentOrchestrator`` (Plan 018 — paso 2). Funciones puras:
no dependen del estado de la instancia (antes eran ``_detect_domains``,
``_detect_capabilities`` y ``_select_agents``).
"""

from __future__ import annotations


def detect_domains(task: str) -> list[str]:
    """Detecta los dominios relevantes de una tarea por keywords.

    Args:
        task: Descripción de la tarea.

    Returns:
        Lista de dominios detectados, o ``["general"]`` si ninguno matchea.
    """
    task_lower = task.lower()
    domains = []

    domain_keywords = {
        "frontend": [
            "react",
            "vue",
            "angular",
            "css",
            "html",
            "ui",
            "component",
            "tailwind",
            "nextjs",
        ],
        "backend": [
            "api",
            "server",
            "endpoint",
            "rest",
            "graphql",
            "database",
            "fastapi",
            "express",
        ],
        "database": [
            "sql",
            "postgresql",
            "mysql",
            "mongodb",
            "prisma",
            "schema",
            "migration",
            "query",
        ],
        "security": [
            "auth",
            "security",
            "vulnerability",
            "owasp",
            "encryption",
            "token",
            "jwt",
            "oauth",
        ],
        "devops": [
            "docker",
            "kubernetes",
            "ci/cd",
            "deploy",
            "pipeline",
            "terraform",
            "aws",
            "cloud",
        ],
        "testing": [
            "test",
            "spec",
            "coverage",
            "unit",
            "integration",
            "e2e",
            "playwright",
            "jest",
        ],
        "mobile": ["react native", "flutter", "ios", "android", "mobile"],
        "ml": ["machine learning", "ml", "model", "training", "inference", "ai", "neural"],
        "documentation": ["docs", "readme", "documentation", "comment", "docstring"],
    }

    for domain, keywords in domain_keywords.items():
        if any(kw in task_lower for kw in keywords):
            domains.append(domain)

    return domains if domains else ["general"]


def detect_capabilities(task: str, domains: list[str]) -> list[str]:
    """Detecta las capacidades requeridas por una tarea + sus dominios.

    Args:
        task: Descripción de la tarea.
        domains: Dominios ya detectados (agrega ``{domain}_expertise`` por cada uno).

    Returns:
        Lista de capacidades, o ``["general_execution"]`` si ninguna matchea.
    """
    capabilities = []
    task_lower = task.lower()

    capability_keywords = {
        "code_generation": ["create", "implement", "write", "generate", "build"],
        "code_analysis": ["analyze", "review", "audit", "inspect", "check"],
        "refactoring": ["refactor", "improve", "optimize", "clean"],
        "debugging": ["debug", "fix", "resolve", "troubleshoot"],
        "testing": ["test", "verify", "validate"],
        "documentation": ["document", "explain", "describe"],
        "planning": ["plan", "design", "architect"],
        "research": ["research", "investigate", "explore"],
    }

    for capability, keywords in capability_keywords.items():
        if any(kw in task_lower for kw in keywords):
            capabilities.append(capability)

    # Add domain-specific capabilities
    for domain in domains:
        capabilities.append(f"{domain}_expertise")

    return capabilities if capabilities else ["general_execution"]


def select_agents(domains: list[str], capabilities: list[str]) -> list[str]:
    """Selecciona los agentes óptimos según dominios y capacidades.

    Args:
        domains: Dominios detectados de la tarea.
        capabilities: Capacidades requeridas.

    Returns:
        Lista de hasta 5 agentes (deduplicada); al menos ``["explorer", "planner"]``.
    """
    agents = []

    domain_agents = {
        "frontend": ["frontend-specialist", "react-specialist", "ui-ux-designer"],
        "backend": ["backend-specialist", "api-designer"],
        "database": ["database-architect"],
        "security": ["security-auditor"],
        "devops": ["devops-engineer"],
        "testing": ["test-engineer", "qa-specialist"],
        "mobile": ["mobile-developer"],
        "ml": ["ml-engineer"],
        "documentation": ["documentation-writer"],
        "general": ["explorer", "planner"],
    }

    for domain in domains:
        if domain in domain_agents:
            agents.extend(domain_agents[domain][:2])  # Top 2 per domain

    # Add capability-based agents
    capability_agents = {
        "code_analysis": "code-reviewer",
        "refactoring": "refactor",
        "debugging": "debugger",
        "planning": "architect",
    }

    for cap in capabilities:
        if cap in capability_agents and capability_agents[cap] not in agents:
            agents.append(capability_agents[cap])

    # Ensure we have at least explorer
    if not agents:
        agents = ["explorer", "planner"]

    return list(set(agents))[:5]  # Max 5 agents
