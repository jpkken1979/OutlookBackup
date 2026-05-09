#!/usr/bin/env python3
"""
Agent Builder - Generador de Agentes basado en Prompts de IA
Crea agentes personalizados usando patrones de Claude, GPT, Grok, etc.

Uso:
    python agent_builder.py create "code-reviewer" --base claude-code --personality cynical
    python agent_builder.py create "researcher" --base deep-research --personality nerdy
    python agent_builder.py list-bases
    python agent_builder.py preview "my-agent"
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

BASE_PATH = Path(__file__).parent.parent
AGENTS_OUTPUT = BASE_PATH / "agents"


@dataclass
class AgentConfig:
    """Configuración de un agente."""

    name: str
    description: str
    base_template: str
    personality: str
    capabilities: list[str]
    tools: list[str]
    constraints: list[str]
    output_format: str
    created_at: str
    version: str = "1.0"


# Bases de agentes extraídas de los prompts de IA
AGENT_BASES = {
    "claude-code": {
        "source": "anthropic/claude-code.md",
        "description": "Asistente de código estilo Claude Code",
        "default_capabilities": [
            "Read and analyze code",
            "Write and edit code",
            "Execute bash commands",
            "Search codebase",
            "Git operations",
        ],
        "default_tools": ["read", "write", "edit", "bash", "grep", "glob"],
        "system_template": """
You are {name}, an AI coding assistant based on Claude Code patterns.

## Core Identity
{description}

## Capabilities
{capabilities}

## Available Tools
{tools}

## Response Guidelines
- Be direct and helpful
- Write clean, working code
- Explain your reasoning when helpful
- Follow best practices for the language
- Consider security implications

## Constraints
{constraints}
""",
    },
    "gpt-agent": {
        "source": "openai/ChatGPT-GPT-5-Agent-mode-System-Prompt.md",
        "description": "Agente autónomo estilo GPT-5",
        "default_capabilities": [
            "Multi-step task execution",
            "Tool orchestration",
            "Memory and context management",
            "Error recovery",
        ],
        "default_tools": ["python", "web_search", "file_operations"],
        "system_template": """
You are {name}, an autonomous AI agent built on GPT-5 patterns.

## Identity
{description}

## Agent Capabilities
{capabilities}

## Tool Access
{tools}

## Execution Mode
- Break complex tasks into steps
- Execute tools as needed
- Verify results before proceeding
- Handle errors gracefully
- Report progress and completion

## Constraints
{constraints}
""",
    },
    "deep-research": {
        "source": "openai/tool-deep-research.md",
        "description": "Agente de investigación profunda",
        "default_capabilities": [
            "Comprehensive research",
            "Multi-source analysis",
            "Fact verification",
            "Synthesis and reporting",
        ],
        "default_tools": ["web_search", "document_analysis", "data_extraction"],
        "system_template": """
You are {name}, a Deep Research Agent.

## Mission
{description}

## Research Capabilities
{capabilities}

## Research Tools
{tools}

## Methodology
1. Query decomposition
2. Multi-source information gathering
3. Cross-reference verification
4. Analysis and synthesis
5. Structured reporting

## Output Format
- Executive Summary
- Key Findings
- Detailed Analysis
- Confidence Levels
- Sources

## Constraints
{constraints}
""",
    },
    "grok-unfiltered": {
        "source": "xai/grok-4.md",
        "description": "Asistente directo y sin filtros estilo Grok",
        "default_capabilities": [
            "Direct answers",
            "Real-time information",
            "Unfiltered responses",
            "Humor and wit",
        ],
        "default_tools": ["web_search", "x_integration"],
        "system_template": """
You are {name}, an AI assistant inspired by Grok's direct style.

## Identity
{description}

## Style
- Be direct and honest
- Use humor when appropriate
- Don't be preachy
- Question assumptions
- Give real answers, not hedged non-answers

## Capabilities
{capabilities}

## Tools
{tools}

## Constraints
{constraints}
""",
    },
    "coding-mentor": {
        "source": "anthropic/claude-code.md",
        "description": "Mentor de programación paciente y educativo",
        "default_capabilities": [
            "Code explanation",
            "Step-by-step teaching",
            "Best practices guidance",
            "Code review",
        ],
        "default_tools": ["read", "write", "explain"],
        "system_template": """
You are {name}, a patient coding mentor.

## Teaching Philosophy
{description}

## Teaching Capabilities
{capabilities}

## Approach
- Break down complex concepts
- Use analogies and examples
- Encourage experimentation
- Celebrate progress
- Guide rather than just give answers

## Tools
{tools}

## Constraints
{constraints}
""",
    },
    "devops-agent": {
        "source": "openai/codex-cli.md",
        "description": "Especialista en DevOps y automatización",
        "default_capabilities": [
            "Infrastructure as code",
            "CI/CD pipelines",
            "Container orchestration",
            "Monitoring and logging",
        ],
        "default_tools": ["bash", "docker", "kubernetes", "terraform"],
        "system_template": """
You are {name}, a DevOps automation specialist.

## Expertise
{description}

## Capabilities
{capabilities}

## Tool Proficiency
{tools}

## Approach
- Automate everything possible
- Infrastructure as code first
- Security by default
- Monitoring and observability
- Documentation for all changes

## Constraints
{constraints}
""",
    },
    "data-analyst": {
        "source": "openai/tool-python.md",
        "description": "Analista de datos con Python",
        "default_capabilities": [
            "Data analysis",
            "Visualization",
            "Statistical analysis",
            "Report generation",
        ],
        "default_tools": ["python", "pandas", "matplotlib", "sql"],
        "system_template": """
You are {name}, a data analysis specialist.

## Expertise
{description}

## Analysis Capabilities
{capabilities}

## Tools
{tools}

## Methodology
1. Understand the question
2. Explore and clean data
3. Analyze patterns
4. Visualize findings
5. Draw conclusions

## Constraints
{constraints}
""",
    },
}

# Personalidades disponibles (del personality_engine)
PERSONALITIES = {
    "professional": "Formal, precise, business-oriented",
    "friendly": "Warm, approachable, encouraging",
    "nerdy": "Technical, detailed, enthusiastic about knowledge",
    "cynical": "Direct, skeptical, no-nonsense",
    "efficient": "Concise, action-oriented, minimal fluff",
    "quirky": "Creative, playful, unique perspectives",
    "mentor": "Patient, educational, empowering",
}


def create_agent(
    name: str,
    base: str = "claude-code",
    personality: str = "professional",
    description: str | None = None,
    capabilities: list[str] | None = None,
    tools: list[str] | None = None,
    constraints: list[str] | None = None,
) -> AgentConfig:
    """Crea un nuevo agente."""
    if base not in AGENT_BASES:
        raise ValueError(f"Base '{base}' no encontrada. Usa --list-bases para ver opciones.")

    base_config = AGENT_BASES[base]

    config = AgentConfig(
        name=name,
        description=description or f"AI agent based on {base} with {personality} personality",
        base_template=base,
        personality=personality,
        capabilities=capabilities or base_config["default_capabilities"],
        tools=tools or base_config["default_tools"],
        constraints=constraints or ["Be helpful and accurate", "Acknowledge limitations"],
        output_format="markdown",
        created_at=datetime.now().isoformat(),
    )

    return config


def generate_system_prompt(config: AgentConfig) -> str:
    """Genera el system prompt completo para un agente."""
    base_config = AGENT_BASES.get(config.base_template, AGENT_BASES["claude-code"])
    template = base_config["system_template"]

    # Formatear capacidades y herramientas
    capabilities_str = "\n".join(f"- {c}" for c in config.capabilities)
    tools_str = "\n".join(f"- {t}" for t in config.tools)
    constraints_str = "\n".join(f"- {c}" for c in config.constraints)

    # Añadir personalidad
    personality_desc = PERSONALITIES.get(config.personality, "Balanced and helpful")

    prompt = template.format(
        name=config.name,
        description=config.description,
        capabilities=capabilities_str,
        tools=tools_str,
        constraints=constraints_str,
    )

    # Añadir sección de personalidad
    prompt += f"""

## Personality: {config.personality.title()}
{personality_desc}
"""

    return prompt


def save_agent(config: AgentConfig) -> Path:
    """Guarda un agente en el directorio de agentes."""
    AGENTS_OUTPUT.mkdir(parents=True, exist_ok=True)

    agent_dir = AGENTS_OUTPUT / config.name
    agent_dir.mkdir(exist_ok=True)

    # Guardar configuración
    config_path = agent_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)

    # Guardar system prompt
    prompt_path = agent_dir / "SYSTEM_PROMPT.md"
    prompt = generate_system_prompt(config)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    # Crear archivo de identidad
    identity_path = agent_dir / "IDENTITY.md"
    identity = f"""# {config.name}

## Description
{config.description}

## Base Template
{config.base_template}

## Personality
{config.personality}

## Capabilities
{chr(10).join(f"- {c}" for c in config.capabilities)}

## Tools
{chr(10).join(f"- {t}" for t in config.tools)}

## Created
{config.created_at}

---
*Generated by Agent Builder - Antigravity Ecosystem*
"""
    with open(identity_path, "w", encoding="utf-8") as f:
        f.write(identity)

    return agent_dir


def list_bases() -> None:
    """Lista las bases de agentes disponibles."""
    print("\n" + "=" * 60)
    print("🤖 BASES DE AGENTES DISPONIBLES")
    print("=" * 60 + "\n")

    for name, config in AGENT_BASES.items():
        print(f"  [{name}]")
        print(f"    {config['description']}")
        print(f"    Fuente: {config['source']}")
        print(f"    Capacidades: {', '.join(config['default_capabilities'][:3])}...")
        print()


def list_personalities() -> None:
    """Lista las personalidades disponibles."""
    print("\n" + "=" * 60)
    print("🎭 PERSONALIDADES DISPONIBLES")
    print("=" * 60 + "\n")

    for name, desc in PERSONALITIES.items():
        print(f"  [{name}] - {desc}")
    print()


def list_agents() -> None:
    """Lista agentes creados."""
    if not AGENTS_OUTPUT.exists():
        print("No hay agentes creados aún.")
        return

    print("\n" + "=" * 60)
    print("📁 AGENTES CREADOS")
    print("=" * 60 + "\n")

    for agent_dir in AGENTS_OUTPUT.iterdir():
        if agent_dir.is_dir():
            config_file = agent_dir / "config.json"
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                print(f"  [{config['name']}]")
                print(f"    Base: {config['base_template']}")
                print(f"    Personalidad: {config['personality']}")
                print(f"    Creado: {config['created_at'][:10]}")
                print()


def preview_agent(name: str) -> None:
    """Muestra preview de un agente."""
    agent_dir = AGENTS_OUTPUT / name

    if not agent_dir.exists():
        print(f"❌ Agente '{name}' no encontrado")
        return

    prompt_file = agent_dir / "SYSTEM_PROMPT.md"
    if prompt_file.exists():
        print("\n" + "=" * 60)
        print(f"👁️ PREVIEW: {name}")
        print("=" * 60)
        print(prompt_file.read_text())


def main():
    parser = argparse.ArgumentParser(description="Agent Builder - Genera agentes IA personalizados")
    subparsers = parser.add_subparsers(dest="command", help="Comandos")

    # Comando: create
    create_parser = subparsers.add_parser("create", help="Crear nuevo agente")
    create_parser.add_argument("name", help="Nombre del agente")
    create_parser.add_argument(
        "--base",
        "-b",
        default="claude-code",
        choices=list(AGENT_BASES.keys()),
        help="Base template a usar",
    )
    create_parser.add_argument(
        "--personality",
        "-p",
        default="professional",
        choices=list(PERSONALITIES.keys()),
        help="Personalidad del agente",
    )
    create_parser.add_argument("--description", "-d", help="Descripción del agente")
    create_parser.add_argument("--capabilities", "-c", nargs="+", help="Capacidades")
    create_parser.add_argument("--tools", "-t", nargs="+", help="Herramientas")

    # Comando: list-bases
    subparsers.add_parser("list-bases", help="Listar bases disponibles")

    # Comando: list-personalities
    subparsers.add_parser("list-personalities", help="Listar personalidades")

    # Comando: list
    subparsers.add_parser("list", help="Listar agentes creados")

    # Comando: preview
    preview_parser = subparsers.add_parser("preview", help="Preview de agente")
    preview_parser.add_argument("name", help="Nombre del agente")

    # Comando: delete
    delete_parser = subparsers.add_parser("delete", help="Eliminar agente")
    delete_parser.add_argument("name", help="Nombre del agente")

    args = parser.parse_args()

    if args.command == "create":
        config = create_agent(
            name=args.name,
            base=args.base,
            personality=args.personality,
            description=args.description,
            capabilities=args.capabilities,
            tools=args.tools,
        )
        agent_dir = save_agent(config)
        print(f"\n✅ Agente '{args.name}' creado exitosamente!")
        print(f"   Ubicación: {agent_dir}")
        print(f"   Base: {args.base}")
        print(f"   Personalidad: {args.personality}")
        print("\n   Archivos generados:")
        print("   - config.json")
        print("   - SYSTEM_PROMPT.md")
        print("   - IDENTITY.md")

    elif args.command == "list-bases":
        list_bases()

    elif args.command == "list-personalities":
        list_personalities()

    elif args.command == "list":
        list_agents()

    elif args.command == "preview":
        preview_agent(args.name)

    elif args.command == "delete":
        import shutil

        agent_dir = AGENTS_OUTPUT / args.name
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
            print(f"✅ Agente '{args.name}' eliminado")
        else:
            print(f"❌ Agente '{args.name}' no encontrado")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
