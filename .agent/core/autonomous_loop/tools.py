# mypy: ignore-errors
"""Builders de definiciones de tools (formato unificado / Anthropic-compatible).

Extraido del monolito ``autonomous_loop.py`` (refactor 2026-05-31). Sin cambios
de comportamiento.
"""

from __future__ import annotations


def build_tools_from_agent(tools: dict) -> list[dict]:
    """
    Convert internal tool definitions to the unified tool format.

    The unified format uses {name, description, input_schema} which is
    compatible with Anthropic's API directly. For other providers (OpenAI,
    Ollama, Gemini), the LLMClient handles conversion automatically.

    Args:
        tools: Dict of {name: Tool} from AntigravityAgent

    Returns:
        List of tool definitions in unified format
    """
    api_tools = []
    for name, tool in tools.items():
        # Build input schema from args_schema or use a generic one
        input_schema = tool.args_schema or {"type": "object", "properties": {}, "required": []}

        # Ensure the schema has the right structure
        if "type" not in input_schema:
            input_schema = {"type": "object", "properties": input_schema, "required": []}

        api_tools.append(
            {
                "name": name,
                "description": tool.description,
                "input_schema": input_schema,
            }
        )

    return api_tools


# Keep backward-compatible alias
build_anthropic_tools = build_tools_from_agent


def build_default_tools() -> list[dict]:
    """Build tool definitions for the default agent tools."""
    return [
        {
            "name": "read_file",
            "description": "Read the contents of a file. Use this to understand code, configs, or documentation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read (relative to project root)",
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories if needed.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write to (relative to project root)",
                    },
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "search_codebase",
            "description": "Search for a pattern across the codebase using grep. Returns matching files and lines.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (regex supported)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default: project root)",
                        "default": ".",
                    },
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "execute_command",
            "description": "Execute a shell command safely. Use for running tests, linting, building, etc.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to execute"}
                },
                "required": ["command"],
            },
        },
        {
            "name": "blackboard_write",
            "description": "[FASE 2] Publica telepáticamente datos (JSON stringificado, esquemas, snippets) en el pizarrón compartido bajo un tópico específico para que otro agente pueda avanzar en paralelo, sin esperarte a terminar tu turno.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "El canal/tópico ej: 'backend-schema', 'shared-constants'",
                    },
                    "content": {
                        "type": "string",
                        "description": "JSON stringificado o texto a publicar",
                    },
                },
                "required": ["topic", "content"],
            },
        },
        {
            "name": "blackboard_read",
            "description": "[FASE 2] Suscribe tu mente a un tópico en el pizarrón. Esperará/bloqueará la ejecución automáticamente hasta que otro agente en paralelo suba los datos (ej: el backend con su JSON). Así no asumes ni inventas la información.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "El canal/tópico ej: 'backend-schema', 'shared-constants'",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Segundos máximos a esperar en pausa a que otro agente escriba (default 120)",
                    },
                },
                "required": ["topic"],
            },
        },
        {
            "name": "auto_heal_mcp",
            "description": "[FASE 4] Diagnostica y auto-repara crasheos críticos en los demonios MCP locales del sistema leyendo los logs, proponiendo fixes a nivel código Python, y matando los procesos stuck para forzar un reinicio del IDE cliente.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["diagnose_crash", "restart_processes"],
                        "description": "Si quieres diagnosticar usando LLM o reiniciar a nivel OS.",
                    }
                },
                "required": ["action"],
            },
        },
        {
            "name": "mcts_speculative_execution",
            "description": "[FASE 1] Fuerza al motor a bifurcar su mente en 3 hilos de pensamiento en paralelo, evaluando 3 enfoques distintos de código para la tarea dada. Descarta 2 y devuelve el código de mayor calidad, rendimiento y robustez. Úsalo ÚNICAMENTE para algoritmos complejos o lógica de negocio vital donde no te permites fallar.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "La tarea hiper-compleja que deseas ejecutar algorítmicamente en paralelo",
                    }
                },
                "required": ["task"],
            },
        },
        {
            "name": "ast_code_radar",
            "description": "[FASE 3] Analiza de forma profunda la estructura matemática (AST) de un archivo Python sin leer el texto completo. Retorna imports, clases, métodos y funciones. Alternativamente, permite buscar todas las llamadas en el repo a una función específica.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Acción a realizar: 'analyze_file' (para ver estructura) o 'find_usages' (para ver qué rompes si modificas)",
                        "enum": ["analyze_file", "find_usages"],
                    },
                    "target": {
                        "type": "string",
                        "description": "Ruta relativa del archivo (si action=analyze_file) o nombre de la función/clase (si action=find_usages)",
                    },
                },
                "required": ["action", "target"],
            },
        },
        {
            "name": "delegate_to_agent",
            "description": "Delegate a subtask to another specialist agent. The agent will execute autonomously and return results. Use when the task requires expertise you don't have.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the agent to delegate to (e.g. 'security-auditor', 'test-engineer', 'frontend-specialist')",
                    },
                    "subtask": {
                        "type": "string",
                        "description": "The subtask for the delegated agent to perform",
                    },
                },
                "required": ["agent_name", "subtask"],
            },
        },
        {
            "name": "find_best_agent",
            "description": "Finds the most suitable specialized agent for a task based on semantic matching.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_description": {"type": "string", "description": "Describe the task"}
                },
                "required": ["task_description"],
            },
        },
        {
            "name": "search_skills",
            "description": "Search the knowledge base (700+ skills) for domain expertise.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search ex: 'react', 'security'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of skill matches to return",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "read_skill",
            "description": "Read the full markdown content of a specific skill to adopt its rules.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "Exact name of the skill"}
                },
                "required": ["skill_name"],
            },
        },
        {
            "name": "decompose_task",
            "description": "Break a complex task into smaller subtasks. Returns a structured plan. Use at the beginning of complex tasks.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "The complex task to decompose"},
                    "max_subtasks": {
                        "type": "integer",
                        "description": "Maximum number of subtasks (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["task"],
            },
        },
        {
            "name": "task_complete",
            "description": "Signal that the task is complete and provide the final answer.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was accomplished",
                    },
                    "artifacts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of files created or modified",
                        "default": [],
                    },
                },
                "required": ["summary"],
            },
        },
    ]
