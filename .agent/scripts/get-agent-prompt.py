#!/usr/bin/env python3
"""
Get Agent Prompt - Extrae el prompt de un agente para usar con cualquier LLM.

Uso:
    python get-agent-prompt.py explorer
    python get-agent-prompt.py explorer --task "Analizar módulo de auth"
    python get-agent-prompt.py explorer --json
    python get-agent-prompt.py explorer --copy  # Copia al clipboard
    python get-agent-prompt.py --list

Compatible con: Gemini, OpenAI, Codex, LLaMA, Ollama, cualquier LLM.
"""

import argparse
import json
import sys
from pathlib import Path

# Detectar directorio de agentes
SCRIPT_DIR = Path(__file__).parent
AGENTS_DIR = SCRIPT_DIR.parent / "agents"


def get_available_agents() -> list[dict]:
    """Lista todos los agentes disponibles."""
    agents = []
    if not AGENTS_DIR.exists():
        return agents

    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if agent_dir.is_dir() and agent_dir.name != "_planned":
            identity_file = agent_dir / "IDENTITY.md"
            if identity_file.exists():
                content = identity_file.read_text(encoding="utf-8")
                description = extract_description(content)
                agents.append(
                    {"name": agent_dir.name, "description": description, "path": str(identity_file)}
                )
    return agents


def extract_description(content: str) -> str:
    """Extrae la descripción del frontmatter YAML."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 2:
            for line in parts[1].strip().split("\n"):
                if line.startswith("description:"):
                    return line.replace("description:", "").strip()
    return ""


def get_agent_prompt(agent_name: str, task: str = None) -> str:
    """Obtiene el prompt completo de un agente."""
    identity_file = AGENTS_DIR / agent_name / "IDENTITY.md"

    if not identity_file.exists():
        print(f"Error: Agente '{agent_name}' no encontrado", file=sys.stderr)
        print("Usa --list para ver agentes disponibles", file=sys.stderr)
        sys.exit(1)

    prompt = identity_file.read_text(encoding="utf-8")

    if task:
        prompt += f"\n\n---\n\n## TAREA ASIGNADA\n\n{task}"

    return prompt


def copy_to_clipboard(text: str) -> bool:
    """Intenta copiar al clipboard."""
    try:
        import subprocess

        # Windows
        process = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
        process.communicate(text.encode("utf-8"))
        return True
    except Exception:
        try:
            # macOS
            import subprocess

            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
            return True
        except Exception:
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Extrae prompts de agentes para usar con cualquier LLM"
    )
    parser.add_argument(
        "agent", nargs="?", help="Nombre del agente (ej: explorer, critic, planner)"
    )
    parser.add_argument("--task", "-t", help="Tarea a incluir en el prompt")
    parser.add_argument(
        "--list", "-l", action="store_true", help="Lista todos los agentes disponibles"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en formato JSON")
    parser.add_argument("--copy", "-c", action="store_true", help="Copia el prompt al clipboard")

    args = parser.parse_args()

    if args.list:
        agents = get_available_agents()
        if args.json:
            print(json.dumps(agents, indent=2, ensure_ascii=False))
        else:
            print("\n🤖 AGENTES DISPONIBLES\n")
            print(f"{'Nombre':<25} {'Descripción'}")
            print("-" * 80)
            for agent in agents:
                desc = (
                    agent["description"][:50] + "..."
                    if len(agent["description"]) > 50
                    else agent["description"]
                )
                print(f"{agent['name']:<25} {desc}")
            print(f"\nTotal: {len(agents)} agentes")
            print("\nUso: python get-agent-prompt.py <nombre> [--task 'tarea']")
        return

    if not args.agent:
        parser.print_help()
        return

    prompt = get_agent_prompt(args.agent, args.task)

    if args.json:
        output = {
            "agent": args.agent,
            "task": args.task,
            "prompt": prompt,
            "usage": {
                "openai": "Usa como 'system' message",
                "gemini": "Usa como parte del prompt",
                "ollama": "Usa con --system flag",
                "anthropic": "Usa como system prompt",
            },
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.copy:
        if copy_to_clipboard(prompt):
            print(f"✅ Prompt del agente '{args.agent}' copiado al clipboard")
            print(f"   Longitud: {len(prompt)} caracteres")
        else:
            print("❌ No se pudo copiar al clipboard")
            print(
                "   Instala pyperclip o usa redirección: python get-agent-prompt.py agent > prompt.txt"
            )
    else:
        print(prompt)


if __name__ == "__main__":
    main()
