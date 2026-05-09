#!/usr/bin/env python3
"""
AI Toolkit - CLI Unificado para AI Prompts Library
Ecosistema Antigravity v2.0

Este toolkit proporciona acceso a todas las herramientas de la biblioteca:
- Personality Engine: Sistema de personalidades multi-estilo
- Deep Research: Agente de investigación profunda
- Memory Manager: Sistema de memoria persistente
- Prompt Mixer: Combina prompts de diferentes IAs
- Agent Builder: Genera agentes personalizados
- Guardrails: Sistema de seguridad
- Prompt Optimizer: Optimiza prompts para diferentes IAs
- Workflow Engine: Encadena herramientas automáticamente

Uso:
    python ai_toolkit.py personality --list
    python ai_toolkit.py research "Estado de la IA"
    python ai_toolkit.py memory add "Usuario prefiere Python"
    python ai_toolkit.py mix anthropic/claude-code.md openai/codex.md
    python ai_toolkit.py agent create "mi-agente" --base claude-code
    python ai_toolkit.py guard check "contenido a verificar"
    python ai_toolkit.py prompts search "memory"
    python ai_toolkit.py optimize "mi prompt" --target claude
    python ai_toolkit.py workflow "analyze,guard,optimize" --input "texto"
"""

import sys
import argparse
from pathlib import Path

# Añadir directorio de tools al path
TOOLS_DIR = Path(__file__).parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="AI Toolkit - Herramientas unificadas para AI Prompts Library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔══════════════════════════════════════════════════════════════════╗
║                    AI TOOLKIT - COMANDOS                          ║
╠══════════════════════════════════════════════════════════════════╣
║  personality  │ Sistema de personalidades (12 estilos)           ║
║  research     │ Investigación profunda automatizada              ║
║  memory       │ Memoria persistente para agentes                 ║
║  mix          │ Mezclar y combinar prompts                       ║
║  agent        │ Crear agentes personalizados                     ║
║  guard        │ Verificar seguridad del contenido                ║
║  prompts      │ Buscar en la biblioteca de prompts               ║
║  optimize     │ Optimizar prompts para Claude/GPT/Gemini/Grok    ║
║  workflow     │ Encadenar herramientas automáticamente           ║
║  assistant    │ 🚀 Meta-agente inteligente unificado             ║
║  stats        │ Estadísticas del ecosistema                      ║
╚══════════════════════════════════════════════════════════════════╝

Ejemplos:
  python ai_toolkit.py personality --style nerdy --prompt "Explica Python"
  python ai_toolkit.py research "Machine Learning en 2025" --depth comprehensive
  python ai_toolkit.py memory add "Usuario es desarrollador senior" --category facts
  python ai_toolkit.py agent create code-reviewer --base claude-code --personality cynical
  python ai_toolkit.py guard check "Cómo hackear un servidor"
  python ai_toolkit.py prompts search "tool" --provider openai
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # ═══════════════════════════════════════════════════════════════
    # PERSONALITY
    # ═══════════════════════════════════════════════════════════════
    pers_parser = subparsers.add_parser(
        "personality", aliases=["pers", "p"], help="Sistema de personalidades"
    )
    pers_parser.add_argument("--list", "-l", action="store_true", help="Listar personalidades")
    pers_parser.add_argument("--style", "-s", help="Estilo de personalidad")
    pers_parser.add_argument("--mix", "-m", help="Mezclar estilos (ej: friendly,nerdy)")
    pers_parser.add_argument("--prompt", "-p", help="Prompt a procesar")
    pers_parser.add_argument("--export", "-e", help="Exportar personalidad")

    # ═══════════════════════════════════════════════════════════════
    # RESEARCH
    # ═══════════════════════════════════════════════════════════════
    res_parser = subparsers.add_parser(
        "research", aliases=["res", "r"], help="Investigación profunda"
    )
    res_parser.add_argument("topic", nargs="?", help="Tema a investigar")
    res_parser.add_argument(
        "--depth",
        "-d",
        choices=["quick", "standard", "comprehensive"],
        default="standard",
        help="Profundidad",
    )
    res_parser.add_argument("--output", "-o", help="Archivo de salida")
    res_parser.add_argument("--local", "-l", action="store_true", help="Solo recursos locales")

    # ═══════════════════════════════════════════════════════════════
    # MEMORY
    # ═══════════════════════════════════════════════════════════════
    mem_parser = subparsers.add_parser("memory", aliases=["mem", "m"], help="Sistema de memoria")
    mem_sub = mem_parser.add_subparsers(dest="mem_action")

    mem_add = mem_sub.add_parser("add", help="Añadir memoria")
    mem_add.add_argument("content", help="Contenido")
    mem_add.add_argument("--category", "-c", default="context")
    mem_add.add_argument("--importance", "-i", default="medium")

    mem_sub.add_parser("list", help="Listar memorias")
    mem_search = mem_sub.add_parser("search", help="Buscar memorias")
    mem_search.add_argument("query", help="Término de búsqueda")
    mem_sub.add_parser("context", help="Obtener contexto")
    mem_sub.add_parser("categories", help="Ver categorías")

    # ═══════════════════════════════════════════════════════════════
    # MIX
    # ═══════════════════════════════════════════════════════════════
    mix_parser = subparsers.add_parser("mix", help="Mezclar prompts")
    mix_parser.add_argument("files", nargs="*", help="Archivos a mezclar")
    mix_parser.add_argument("--analyze", "-a", help="Analizar un prompt")
    mix_parser.add_argument("--patterns", "-p", help="Extraer patrones de directorio")
    mix_parser.add_argument("--templates", "-t", action="store_true", help="Listar templates")
    mix_parser.add_argument("--output", "-o", help="Archivo de salida")
    mix_parser.add_argument(
        "--strategy", "-s", choices=["balanced", "merge", "first"], default="balanced"
    )

    # ═══════════════════════════════════════════════════════════════
    # AGENT
    # ═══════════════════════════════════════════════════════════════
    agent_parser = subparsers.add_parser("agent", aliases=["a"], help="Crear agentes")
    agent_sub = agent_parser.add_subparsers(dest="agent_action")

    agent_create = agent_sub.add_parser("create", help="Crear agente")
    agent_create.add_argument("name", help="Nombre del agente")
    agent_create.add_argument("--base", "-b", default="claude-code")
    agent_create.add_argument("--personality", "-p", default="professional")
    agent_create.add_argument("--description", "-d")

    agent_sub.add_parser("list", help="Listar agentes")
    agent_sub.add_parser("bases", help="Listar bases disponibles")
    agent_preview = agent_sub.add_parser("preview", help="Preview de agente")
    agent_preview.add_argument("name")

    # ═══════════════════════════════════════════════════════════════
    # GUARD
    # ═══════════════════════════════════════════════════════════════
    guard_parser = subparsers.add_parser("guard", aliases=["g"], help="Sistema de guardrails")
    guard_sub = guard_parser.add_subparsers(dest="guard_action")

    guard_check = guard_sub.add_parser("check", help="Verificar contenido")
    guard_check.add_argument("content", help="Contenido a verificar")

    guard_sub.add_parser("rules", help="Listar reglas")
    guard_sub.add_parser("prompt", help="Generar prompt de seguridad")

    # ═══════════════════════════════════════════════════════════════
    # PROMPTS
    # ═══════════════════════════════════════════════════════════════
    prompts_parser = subparsers.add_parser("prompts", help="Buscar prompts")
    prompts_parser.add_argument("query", nargs="?", help="Término de búsqueda")
    prompts_parser.add_argument(
        "--provider",
        "-p",
        choices=["anthropic", "openai", "google", "xai", "perplexity", "proton", "misc"],
    )
    prompts_parser.add_argument("--list", "-l", action="store_true", help="Listar todos")
    prompts_parser.add_argument("--stats", "-s", action="store_true", help="Mostrar estadísticas")

    # ═══════════════════════════════════════════════════════════════
    # OPTIMIZE
    # ═══════════════════════════════════════════════════════════════
    opt_parser = subparsers.add_parser(
        "optimize", aliases=["opt", "o"], help="Optimizar prompts para IAs específicas"
    )
    opt_parser.add_argument("prompt", nargs="?", help="Prompt a optimizar")
    opt_parser.add_argument(
        "--target",
        "-t",
        choices=["claude", "gpt", "gemini", "grok", "local"],
        default="claude",
        help="IA destino",
    )
    opt_parser.add_argument(
        "--compare", "-c", action="store_true", help="Comparar optimización para todas las IAs"
    )
    opt_parser.add_argument("--interactive", "-i", action="store_true", help="Modo interactivo")
    opt_parser.add_argument("--file", "-f", help="Leer prompt desde archivo")
    opt_parser.add_argument("--output", "-o", help="Guardar a archivo")

    # ═══════════════════════════════════════════════════════════════
    # WORKFLOW
    # ═══════════════════════════════════════════════════════════════
    wf_parser = subparsers.add_parser(
        "workflow", aliases=["wf", "w"], help="Encadenar herramientas"
    )
    wf_parser.add_argument("chain", nargs="?", help="Cadena de tools (ej: guard,optimize,memory)")
    wf_parser.add_argument("--input", "-i", help="Input para el workflow")
    wf_parser.add_argument(
        "--list", "-l", action="store_true", help="Listar workflows predefinidos"
    )
    wf_parser.add_argument(
        "--preset",
        "-p",
        choices=["safe-prompt", "research-deep", "agent-create"],
        help="Usar workflow predefinido",
    )

    # ═══════════════════════════════════════════════════════════════
    # ASSISTANT (Meta-Agente)
    # ═══════════════════════════════════════════════════════════════
    asst_parser = subparsers.add_parser(
        "assistant", aliases=["asst", "ask"], help="Meta-agente inteligente unificado"
    )
    asst_parser.add_argument("prompt", nargs="?", help="Tu prompt o tarea")
    asst_parser.add_argument(
        "--target",
        "-t",
        choices=["claude", "gpt", "gemini", "grok", "local"],
        default="claude",
        help="IA destino",
    )
    asst_parser.add_argument("--personality", "-p", default="professional", help="Personalidad")
    asst_parser.add_argument("--interactive", "-i", action="store_true", help="Modo interactivo")
    asst_parser.add_argument(
        "--analyze-only", "-a", action="store_true", help="Solo analizar tarea"
    )

    # ═══════════════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════════════
    subparsers.add_parser("stats", help="Estadísticas del ecosistema")

    # ═══════════════════════════════════════════════════════════════
    # PARSE Y EJECUTAR
    # ═══════════════════════════════════════════════════════════════
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        show_quick_stats()
        return

    # Importar y ejecutar el módulo correspondiente
    try:
        if args.command in ["personality", "pers", "p"]:
            from personality_engine import main as pers_main

            sys.argv = ["personality_engine.py"]
            if args.list:
                sys.argv.append("--list")
            if args.style:
                sys.argv.extend(["--style", args.style])
            if args.mix:
                sys.argv.extend(["--mix", args.mix])
            if args.prompt:
                sys.argv.extend(["--prompt", args.prompt])
            if args.export:
                sys.argv.extend(["--export", args.export])
            pers_main()

        elif args.command in ["research", "res", "r"]:
            from deep_research import main as res_main

            sys.argv = ["deep_research.py"]
            if args.topic:
                sys.argv.append(args.topic)
            if args.depth:
                sys.argv.extend(["--depth", args.depth])
            if args.output:
                sys.argv.extend(["--output", args.output])
            if args.local:
                sys.argv.append("--local")
            res_main()

        elif args.command in ["memory", "mem", "m"]:
            from memory_manager import main as mem_main

            sys.argv = ["memory_manager.py"]
            if args.mem_action:
                sys.argv.append(args.mem_action)
                if args.mem_action == "add" and hasattr(args, "content"):
                    sys.argv.append(args.content)
                    if hasattr(args, "category"):
                        sys.argv.extend(["--category", args.category])
                elif args.mem_action == "search" and hasattr(args, "query"):
                    sys.argv.append(args.query)
            mem_main()

        elif args.command == "mix":
            from prompt_mixer import main as mix_main

            sys.argv = ["prompt_mixer.py"]
            if args.templates:
                sys.argv.append("--list-templates")
            elif args.analyze:
                sys.argv.extend(["--analyze", args.analyze])
            elif args.patterns:
                sys.argv.extend(["--extract-patterns", args.patterns])
            elif args.files:
                sys.argv.extend(["--mix"] + args.files)
                if args.strategy:
                    sys.argv.extend(["--strategy", args.strategy])
            if args.output:
                sys.argv.extend(["--output", args.output])
            mix_main()

        elif args.command in ["agent", "a"]:
            from agent_builder import main as agent_main

            sys.argv = ["agent_builder.py"]
            if args.agent_action:
                sys.argv.append(args.agent_action)
                if args.agent_action == "create" and hasattr(args, "name"):
                    sys.argv.append(args.name)
                    if hasattr(args, "base"):
                        sys.argv.extend(["--base", args.base])
                    if hasattr(args, "personality"):
                        sys.argv.extend(["--personality", args.personality])
                elif args.agent_action == "preview" and hasattr(args, "name"):
                    sys.argv.append(args.name)
                elif args.agent_action == "bases":
                    sys.argv = ["agent_builder.py", "list-bases"]
            agent_main()

        elif args.command in ["guard", "g"]:
            from guardrails import main as guard_main

            sys.argv = ["guardrails.py"]
            if args.guard_action:
                if args.guard_action == "check" and hasattr(args, "content"):
                    sys.argv.extend(["check", args.content])
                elif args.guard_action == "rules":
                    sys.argv.append("list-rules")
                elif args.guard_action == "prompt":
                    sys.argv.append("generate-prompt")
            guard_main()

        elif args.command == "prompts":
            from search_prompts import main as search_main

            sys.argv = ["search_prompts.py"]
            if args.stats:
                sys.argv.append("--stats")
            elif args.list or args.provider:
                sys.argv.append("--list")
                if args.provider:
                    sys.argv.extend(["--provider", args.provider])
            elif args.query:
                sys.argv.append(args.query)
                if args.provider:
                    sys.argv.extend(["--provider", args.provider])
            search_main()

        elif args.command in ["optimize", "opt", "o"]:
            from prompt_optimizer import optimize_prompt, AI_PATTERNS, main as opt_main

            if args.interactive:
                # Usar modo interactivo del script original
                sys.argv = ["prompt_optimizer.py", "--interactive"]
                opt_main()
            elif args.compare and args.prompt:
                # Comparar todas las IAs
                print(f"\n{'=' * 60}")
                print("🔄 COMPARACIÓN DE OPTIMIZACIÓN")
                print(f"{'=' * 60}\n")
                for ai in ["claude", "gpt", "gemini", "grok", "local"]:
                    result = optimize_prompt(args.prompt, ai)
                    print(f"━━━ {AI_PATTERNS[ai]['name']} ━━━")
                    print(result.optimized[:200])
                    print()
            elif args.file:
                with open(args.file) as f:
                    prompt = f.read()
                result = optimize_prompt(prompt, args.target)
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(result.optimized)
                    print(f"✅ Guardado en {args.output}")
                else:
                    print_optimized_result(result, args.target)
            elif args.prompt:
                result = optimize_prompt(args.prompt, args.target)
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(result.optimized)
                    print(f"✅ Guardado en {args.output}")
                else:
                    print_optimized_result(result, args.target)
            else:
                print("Uso: ai_toolkit.py optimize 'tu prompt' --target claude")
                print("     ai_toolkit.py optimize --interactive")
                print("     ai_toolkit.py optimize 'prompt' --compare")

        elif args.command in ["workflow", "wf", "w"]:
            if args.list:
                print_workflows()
            elif args.preset:
                run_preset_workflow(args.preset, args.input)
            elif args.chain:
                run_workflow_chain(args.chain, args.input)
            else:
                print("Uso: ai_toolkit.py workflow 'guard,optimize' --input 'texto'")
                print("     ai_toolkit.py workflow --preset safe-prompt --input 'texto'")
                print("     ai_toolkit.py workflow --list")

        elif args.command in ["assistant", "asst", "ask"]:
            from antigravity_assistant import (
                AntigravityAssistant,
                AssistantConfig,
                interactive_mode,
                print_response,
            )

            if args.interactive:
                interactive_mode()
            elif args.prompt:
                config = AssistantConfig(personality=args.personality, target_ai=args.target)
                assistant = AntigravityAssistant(config)
                response = assistant.process(args.prompt)

                if args.analyze_only:
                    print(f"\n📊 Tipo: {response.analysis.task_type}")
                    print(f"🎯 Complejidad: {response.analysis.complexity}")
                    print(f"🤖 Agentes: {', '.join(response.analysis.recommended_agents)}")
                else:
                    print_response(response)
            else:
                print("Uso: ai_toolkit.py assistant 'tu prompt' --target claude")
                print("     ai_toolkit.py assistant --interactive")

        elif args.command == "stats":
            show_full_stats()

    except ImportError as e:
        print(f"❌ Error importando módulo: {e}")
        print("   Asegúrate de estar en el directorio correcto")
    except Exception as e:
        print(f"❌ Error: {e}")


def show_quick_stats():
    """Muestra estadísticas rápidas."""
    print("\n" + "=" * 60)
    print("📊 AI TOOLKIT - ESTADÍSTICAS RÁPIDAS")
    print("=" * 60)

    base_path = Path(__file__).parent

    # Contar prompts
    prompt_count = len(list(base_path.rglob("*.md"))) - 1  # -1 por SKILL.md

    # Contar herramientas
    tools_count = len(list((base_path / "tools").glob("*.py")))

    print(f"""
  📁 Prompts de IA:     {prompt_count}+
  🔧 Herramientas:      {tools_count}
  🎭 Personalidades:    12
  🤖 Bases de agentes:  7
  🛡️ Reglas guardrails: 10+

  Usa: python ai_toolkit.py <comando> --help
""")


def show_full_stats():
    """Muestra estadísticas completas."""
    print("\n" + "=" * 70)
    print("📊 AI TOOLKIT - ESTADÍSTICAS COMPLETAS")
    print("=" * 70)

    base_path = Path(__file__).parent

    # Estadísticas por proveedor
    providers = ["anthropic", "openai", "google", "xai", "perplexity", "proton", "misc"]
    print("\n📁 PROMPTS POR PROVEEDOR:")
    print("-" * 40)

    total = 0
    for provider in providers:
        provider_path = base_path / provider
        if provider_path.exists():
            count = len(list(provider_path.rglob("*.md")))
            total += count
            bar = "█" * (count // 2)
            print(f"  {provider:12} │ {count:3} │ {bar}")

    print(f"\n  {'TOTAL':12} │ {total:3}")

    # Herramientas
    print("\n🔧 HERRAMIENTAS DISPONIBLES:")
    print("-" * 40)
    tools = [
        ("personality_engine.py", "Sistema de 12 personalidades"),
        ("deep_research.py", "Investigación automatizada"),
        ("memory_manager.py", "Memoria persistente"),
        ("prompt_mixer.py", "Combinar prompts"),
        ("agent_builder.py", "Generador de agentes"),
        ("guardrails.py", "Sistema de seguridad"),
        ("search_prompts.py", "Buscador de prompts"),
    ]
    for tool, desc in tools:
        print(f"  • {tool:25} - {desc}")

    # Uso de memoria
    print("\n💾 ALMACENAMIENTO:")
    print("-" * 40)
    memory_file = base_path / "memory" / "agent_memory.json"
    if memory_file.exists():
        size = memory_file.stat().st_size / 1024
        print(f"  Memoria: {size:.1f} KB")

    catalog_file = base_path / "catalog.json"
    if catalog_file.exists():
        size = catalog_file.stat().st_size / 1024
        print(f"  Catálogo: {size:.1f} KB")

    total_size = sum(f.stat().st_size for f in base_path.rglob("*") if f.is_file()) / 1024
    print(f"  Total: {total_size:.1f} KB")

    print("\n" + "=" * 70)


def print_optimized_result(result, target: str):
    """Imprime el resultado de optimización."""
    from prompt_optimizer import AI_PATTERNS

    ai_name = AI_PATTERNS.get(target, {}).get("name", target)

    print(f"\n{'=' * 60}")
    print(f"✨ PROMPT OPTIMIZADO para {ai_name}")
    print(f"{'=' * 60}\n")
    print(result.optimized)
    print(f"\n{'-' * 60}")
    print(f"📊 Tipo de tarea: {result.task_type}")
    print(f"🎯 Confianza: {result.confidence}")
    if result.enhancements:
        print("\n🔧 Mejoras aplicadas:")
        for e in result.enhancements:
            print(f"   • {e}")
    if result.tips:
        print(f"\n💡 Tips para {ai_name}:")
        for t in result.tips[:3]:
            print(f"   • {t}")


def print_workflows():
    """Muestra workflows predefinidos."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                 WORKFLOWS PREDEFINIDOS                            ║
╠══════════════════════════════════════════════════════════════════╣
║  safe-prompt    │ guard → optimize → output                      ║
║                 │ Verifica seguridad y optimiza para IA          ║
╠══════════════════════════════════════════════════════════════════╣
║  research-deep  │ research → memory → output                     ║
║                 │ Investiga tema y guarda en memoria             ║
╠══════════════════════════════════════════════════════════════════╣
║  agent-create   │ personality → agent → guard → output           ║
║                 │ Crea agente con personalidad y guardrails      ║
╚══════════════════════════════════════════════════════════════════╝

Uso:
  ai_toolkit.py workflow --preset safe-prompt --input "mi prompt"
  ai_toolkit.py workflow "guard,optimize,memory" --input "texto"
""")


def run_preset_workflow(preset: str, input_data: str):
    """Ejecuta un workflow predefinido."""
    PRESETS = {
        "safe-prompt": ["guard", "optimize"],
        "research-deep": ["research", "memory"],
        "agent-create": ["personality", "agent", "guard"],
    }

    if preset not in PRESETS:
        print(f"❌ Preset '{preset}' no encontrado")
        return

    chain = PRESETS[preset]
    print(f"🔄 Ejecutando workflow: {' → '.join(chain)}")
    run_workflow_chain(",".join(chain), input_data)


def run_workflow_chain(chain: str, input_data: str):
    """Ejecuta una cadena de herramientas."""
    tools = [t.strip() for t in chain.split(",")]
    current_output = input_data or ""

    print(f"\n{'=' * 60}")
    print(f"🔗 WORKFLOW: {' → '.join(tools)}")
    print(f"{'=' * 60}\n")

    for i, tool in enumerate(tools, 1):
        print(f"[{i}/{len(tools)}] Ejecutando: {tool}")
        print("-" * 40)

        try:
            if tool == "guard":
                from guardrails import Guardrails

                g = Guardrails()
                result = g.check(current_output)
                if result["risk"] in ["high", "critical"]:
                    print(f"⚠️ Contenido bloqueado: {result['risk']}")
                    print(f"   Razón: {result.get('details', 'Violación de guardrails')}")
                    return
                print(f"✅ Verificado: riesgo {result['risk']}")

            elif tool == "optimize":
                from prompt_optimizer import PromptOptimizer

                opt = PromptOptimizer()
                result = opt.optimize(current_output, "claude")
                current_output = result["optimized"]
                print("✅ Optimizado para Claude")

            elif tool == "memory":
                from memory_manager import MemoryManager

                mm = MemoryManager()
                mm.add_memory(current_output[:200], "context", "medium")
                print("✅ Guardado en memoria")

            elif tool == "personality":
                from personality_engine import PersonalityEngine

                pe = PersonalityEngine()
                result = pe.apply_personality("professional", current_output)
                current_output = result
                print("✅ Personalidad aplicada: professional")

            elif tool == "research":
                print(f"📚 Investigando: {current_output[:50]}...")
                # Research genera su propia salida
                from deep_research import DeepResearcher

                dr = DeepResearcher()
                result = dr.research(current_output, "quick")
                current_output = result.get("summary", current_output)
                print("✅ Investigación completada")

            else:
                print(f"⚠️ Tool '{tool}' no reconocida, saltando...")

        except Exception as e:
            print(f"❌ Error en {tool}: {e}")
            continue

        print()

    print(f"{'=' * 60}")
    print("📤 OUTPUT FINAL:")
    print(f"{'=' * 60}")
    print(current_output[:500] + ("..." if len(current_output) > 500 else ""))


if __name__ == "__main__":
    main()
