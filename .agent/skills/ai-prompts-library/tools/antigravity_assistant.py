#!/usr/bin/env python3
"""
Antigravity Assistant - Meta-Agente Inteligente Unificado
Ecosistema Antigravity v3.0

El asistente más poderoso del ecosistema. Combina:
- Auto-detección de tareas
- Selección inteligente de herramientas
- Memoria persistente
- Guardrails automáticos
- Optimización de prompts
- 12 personalidades
- Workflows automáticos
- 20 agentes especializados

Uso:
    python antigravity_assistant.py "Crea una API REST con auth"
    python antigravity_assistant.py "Investiga sobre React 19" --mode research
    python antigravity_assistant.py --interactive
    python antigravity_assistant.py "Mi prompt" --target gpt --personality nerdy
"""

import argparse
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

# Importar herramientas del ecosistema
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))

try:
    from prompt_optimizer import optimize_prompt, AI_PATTERNS
    from memory_manager import MemoryStore
    from guardrails import check_content
    from personality_engine import PERSONALITIES
except ImportError as e:
    print(f"⚠️ Algunas herramientas no disponibles: {e}")
    # Fallbacks
    MemoryStore = None
    check_content = None
    PERSONALITIES = {}


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL ASISTENTE
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class AssistantConfig:
    """Configuración del asistente."""

    personality: str = "professional"
    target_ai: str = "claude"
    auto_memory: bool = True
    auto_guardrails: bool = True
    auto_optimize: bool = True
    verbose: bool = False


@dataclass
class TaskAnalysis:
    """Resultado del análisis de tarea."""

    original_input: str
    task_type: str
    complexity: str  # simple, medium, complex
    domains: list[str]
    recommended_agents: list[str]
    recommended_tools: list[str]
    recommended_workflow: str
    confidence: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class AssistantResponse:
    """Respuesta del asistente."""

    original_input: str
    analysis: TaskAnalysis
    optimized_prompt: str
    memory_context: str
    guardrails_check: dict[str, Any]
    personality_applied: str
    recommendations: list[str]
    ready_prompt: str  # Prompt final listo para usar
    target_ai: str


# ═══════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE TAREAS
# ═══════════════════════════════════════════════════════════════════════════

TASK_PATTERNS = {
    "code": {
        "keywords": [
            "crea",
            "crear",
            "function",
            "función",
            "api",
            "código",
            "code",
            "implementa",
            "programa",
            "script",
            "clase",
            "class",
            "component",
            "endpoint",
            "database",
            "query",
            "fix",
            "bug",
            "error",
            "refactor",
        ],
        "domains": ["backend", "frontend", "database", "devops"],
        "agents": ["backend-specialist", "frontend-specialist", "database-architect"],
        "workflow": "code-review",
    },
    "research": {
        "keywords": [
            "investiga",
            "research",
            "busca",
            "encuentra",
            "analiza",
            "explica",
            "qué es",
            "cómo funciona",
            "diferencia",
            "compara",
            "pros y contras",
        ],
        "domains": ["research", "analysis"],
        "agents": ["explorer-agent"],
        "workflow": "research-deep",
    },
    "planning": {
        "keywords": [
            "planifica",
            "plan",
            "roadmap",
            "arquitectura",
            "diseña",
            "estructura",
            "organiza",
            "prioriza",
            "backlog",
            "sprint",
            "mvp",
            "prd",
        ],
        "domains": ["planning", "architecture"],
        "agents": ["planner", "product-owner", "orchestrator"],
        "workflow": "planning",
    },
    "testing": {
        "keywords": [
            "test",
            "prueba",
            "testing",
            "coverage",
            "e2e",
            "unit",
            "integración",
            "qa",
            "calidad",
            "validar",
            "verificar",
        ],
        "domains": ["testing", "qa"],
        "agents": ["test-engineer"],
        "workflow": "testing",
    },
    "security": {
        "keywords": [
            "seguridad",
            "security",
            "auth",
            "autenticación",
            "vulnerabilidad",
            "owasp",
            "pentest",
            "audit",
            "ssl",
            "jwt",
            "token",
            "password",
        ],
        "domains": ["security"],
        "agents": ["security-auditor", "penetration-tester"],
        "workflow": "security-audit",
    },
    "documentation": {
        "keywords": [
            "documenta",
            "readme",
            "docs",
            "documentación",
            "api docs",
            "changelog",
            "tutorial",
            "guía",
            "manual",
        ],
        "domains": ["documentation"],
        "agents": ["documentation-writer"],
        "workflow": "documentation",
    },
    "optimization": {
        "keywords": [
            "optimiza",
            "performance",
            "rendimiento",
            "velocidad",
            "lento",
            "rápido",
            "memoria",
            "cpu",
            "cache",
            "bundle",
            "lighthouse",
        ],
        "domains": ["performance"],
        "agents": ["performance-optimizer"],
        "workflow": "optimization",
    },
    "devops": {
        "keywords": [
            "deploy",
            "despliegue",
            "ci/cd",
            "docker",
            "kubernetes",
            "aws",
            "vercel",
            "github actions",
            "pipeline",
            "infraestructura",
            "servidor",
        ],
        "domains": ["devops", "infrastructure"],
        "agents": ["devops-engineer"],
        "workflow": "deployment",
    },
    "mobile": {
        "keywords": [
            "mobile",
            "móvil",
            "app",
            "react native",
            "flutter",
            "ios",
            "android",
            "expo",
            "nativo",
        ],
        "domains": ["mobile"],
        "agents": ["mobile-developer"],
        "workflow": "mobile-dev",
    },
    "seo": {
        "keywords": [
            "seo",
            "google",
            "ranking",
            "meta tags",
            "sitemap",
            "robots",
            "core web vitals",
            "lighthouse",
            "schema",
        ],
        "domains": ["seo", "marketing"],
        "agents": ["seo-specialist"],
        "workflow": "seo-audit",
    },
    "creative": {
        "keywords": [
            "escribe",
            "redacta",
            "genera",
            "crea contenido",
            "copy",
            "texto",
            "historia",
            "artículo",
            "blog",
            "email",
        ],
        "domains": ["creative", "content"],
        "agents": [],
        "workflow": "creative",
    },
}

COMPLEXITY_INDICATORS = {
    "simple": ["simple", "básico", "rápido", "pequeño", "una", "solo"],
    "complex": [
        "complejo",
        "completo",
        "full",
        "enterprise",
        "escalable",
        "múltiple",
        "integración",
        "sistema",
        "arquitectura",
        "microservicios",
    ],
}


def analyze_task(user_input: str) -> TaskAnalysis:
    """Analiza el input del usuario y determina tipo de tarea."""
    input_lower = user_input.lower()

    # Detectar tipos de tarea
    detected_types = {}
    for task_type, config in TASK_PATTERNS.items():
        score = sum(1 for kw in config["keywords"] if kw in input_lower)
        if score > 0:
            detected_types[task_type] = score

    # Ordenar por score
    if detected_types:
        primary_type = max(detected_types, key=detected_types.get)
        confidence = min(detected_types[primary_type] / 3, 1.0)
    else:
        primary_type = "general"
        confidence = 0.3

    # Detectar complejidad
    complexity = "medium"
    for level, indicators in COMPLEXITY_INDICATORS.items():
        if any(ind in input_lower for ind in indicators):
            complexity = level
            break

    # Si tiene muchas palabras o múltiples tareas, es complejo
    if len(user_input.split()) > 50 or user_input.count(",") > 3:
        complexity = "complex"

    # Obtener configuración del tipo
    config = TASK_PATTERNS.get(
        primary_type, {"domains": ["general"], "agents": ["orchestrator"], "workflow": "general"}
    )

    # Warnings
    warnings = []
    if confidence < 0.5:
        warnings.append("Baja confianza en detección. Considera ser más específico.")
    if complexity == "complex":
        warnings.append("Tarea compleja detectada. Considera dividirla en subtareas.")

    # Multi-domain detection
    all_domains = []
    all_agents = []
    for task_type, score in detected_types.items():
        if score > 0:
            all_domains.extend(TASK_PATTERNS[task_type]["domains"])
            all_agents.extend(TASK_PATTERNS[task_type]["agents"])

    return TaskAnalysis(
        original_input=user_input,
        task_type=primary_type,
        complexity=complexity,
        domains=list(set(all_domains)) or config["domains"],
        recommended_agents=list(set(all_agents)) or config["agents"],
        recommended_tools=get_recommended_tools(primary_type, complexity),
        recommended_workflow=config["workflow"],
        confidence=confidence,
        warnings=warnings,
    )


def get_recommended_tools(task_type: str, complexity: str) -> list[str]:
    """Recomienda herramientas basado en tipo y complejidad."""
    tools = ["memory", "guardrails"]

    if task_type in ["code", "security"]:
        tools.extend(["guardrails", "optimize"])

    if task_type == "research":
        tools.extend(["research", "memory"])

    if complexity == "complex":
        tools.append("workflow")

    return list(set(tools))


# ═══════════════════════════════════════════════════════════════════════════
# ASISTENTE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════


class AntigravityAssistant:
    """Asistente inteligente unificado."""

    def __init__(self, config: AssistantConfig | None = None):
        self.config = config or AssistantConfig()
        self.memory = MemoryStore() if MemoryStore else None
        self.check_guardrails = check_content

    def process(self, user_input: str) -> AssistantResponse:
        """Procesa el input del usuario y genera respuesta completa."""

        # 1. Analizar tarea
        analysis = analyze_task(user_input)

        # 2. Cargar contexto de memoria
        memory_context = ""
        if self.config.auto_memory and self.memory:
            try:
                memories = self.memory.get_context()
                if memories:
                    memory_context = f"\n[Contexto previo: {memories[:500]}]"
            except Exception:
                pass

        # 3. Verificar guardrails
        guardrails_result = {"risk": "safe", "passed": True}
        if self.config.auto_guardrails and self.check_guardrails:
            try:
                result = self.check_guardrails(user_input)
                guardrails_result = {"risk": result.risk_level.value, "passed": result.passed}
            except Exception:
                pass

        # 4. Optimizar prompt para IA destino
        optimized = user_input
        if self.config.auto_optimize:
            try:
                result = optimize_prompt(user_input, self.config.target_ai)
                optimized = result.optimized
            except Exception:
                pass

        # 5. Aplicar personalidad
        personality_text = ""
        try:
            if self.config.personality in PERSONALITIES:
                p = PERSONALITIES[self.config.personality]
                personality_text = f"Personality: {p.get('name', '')}. {p.get('description', '')}. Tone: {p.get('tone', '')}."
        except Exception:
            pass

        # 6. Construir prompt final
        ready_prompt = self._build_final_prompt(
            optimized, memory_context, analysis, personality_text
        )

        # 7. Generar recomendaciones
        recommendations = self._generate_recommendations(analysis)

        # 8. Guardar en memoria si es relevante
        if self.config.auto_memory and self.memory and analysis.confidence > 0.5:
            try:
                self.memory.add(
                    f"Tarea: {analysis.task_type} - {user_input[:100]}", "context", "medium"
                )
            except Exception:
                pass

        return AssistantResponse(
            original_input=user_input,
            analysis=analysis,
            optimized_prompt=optimized,
            memory_context=memory_context,
            guardrails_check=guardrails_result,
            personality_applied=self.config.personality,
            recommendations=recommendations,
            ready_prompt=ready_prompt,
            target_ai=self.config.target_ai,
        )

    def _build_final_prompt(
        self, optimized: str, memory_context: str, analysis: TaskAnalysis, personality_text: str
    ) -> str:
        """Construye el prompt final listo para usar."""

        target = self.config.target_ai

        if target == "claude":
            return f"""<system>
{personality_text}
</system>

<context>
Tipo de tarea: {analysis.task_type}
Complejidad: {analysis.complexity}
{memory_context}
</context>

<task>
{optimized}
</task>

<instructions>
- Sé específico y actionable
- Muestra código cuando sea relevante
- Explica tu razonamiento
</instructions>"""

        elif target == "gpt":
            return f"""# System
{personality_text}

# Context
- Task Type: {analysis.task_type}
- Complexity: {analysis.complexity}
{memory_context}

# Task
{optimized}

# Instructions
- Be specific and actionable
- Show code when relevant
- Explain your reasoning"""

        elif target == "grok":
            return f"""{personality_text}

Context: {analysis.task_type} task, {analysis.complexity} complexity
{memory_context}

{optimized}

Be direct. No fluff. Real answers only."""

        else:
            return f"""{personality_text}

{memory_context}

{optimized}"""

    def _generate_recommendations(self, analysis: TaskAnalysis) -> list[str]:
        """Genera recomendaciones basadas en el análisis."""
        recs = []

        # Recomendaciones de agentes
        if analysis.recommended_agents:
            agents_str = ", ".join(analysis.recommended_agents[:3])
            recs.append(f"🤖 Agentes recomendados: {agents_str}")

        # Recomendaciones de workflow
        recs.append(f"🔄 Workflow sugerido: {analysis.recommended_workflow}")

        # Recomendaciones por tipo
        if analysis.task_type == "code":
            recs.append("💡 Tip: Pide tests junto con el código")
            recs.append("🛡️ Tip: Verifica seguridad en auth/inputs")

        elif analysis.task_type == "research":
            recs.append("💡 Tip: Pide fuentes y referencias")
            recs.append("📚 Tip: Usa --depth comprehensive para más detalle")

        elif analysis.task_type == "planning":
            recs.append("💡 Tip: Define MVP vs Nice-to-have")
            recs.append("📋 Tip: Pide estimaciones de esfuerzo")

        elif analysis.task_type == "security":
            recs.append("⚠️ IMPORTANTE: Siempre verificar en ambiente seguro")
            recs.append("🔒 Tip: Pide checklist OWASP Top 10")

        # Warnings
        for warning in analysis.warnings:
            recs.append(f"⚠️ {warning}")

        return recs


# ═══════════════════════════════════════════════════════════════════════════
# MODO INTERACTIVO
# ═══════════════════════════════════════════════════════════════════════════


def interactive_mode():
    """Modo interactivo del asistente."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║         🚀 ANTIGRAVITY ASSISTANT - Modo Interactivo              ║
╠══════════════════════════════════════════════════════════════════╣
║  El asistente más inteligente del ecosistema Antigravity         ║
║                                                                  ║
║  Comandos:                                                       ║
║    /target <ai>     - Cambiar IA destino (claude/gpt/grok)      ║
║    /personality <p> - Cambiar personalidad                       ║
║    /memory          - Ver memoria actual                         ║
║    /clear           - Limpiar memoria                            ║
║    /help            - Mostrar ayuda                              ║
║    /quit            - Salir                                      ║
╚══════════════════════════════════════════════════════════════════╝
""")

    config = AssistantConfig()
    assistant = AntigravityAssistant(config)

    while True:
        try:
            user_input = input(f"\n[{config.target_ai}|{config.personality}] > ").strip()

            if not user_input:
                continue

            # Comandos
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd = parts[0].lower()

                if cmd == "/quit" or cmd == "/exit":
                    print("👋 ¡Hasta luego!")
                    break

                elif cmd == "/target" and len(parts) > 1:
                    target = parts[1].lower()
                    if target in ["claude", "gpt", "gemini", "grok", "local"]:
                        config.target_ai = target
                        assistant = AntigravityAssistant(config)
                        print(f"✅ IA destino: {target}")
                    else:
                        print("❌ Targets: claude, gpt, gemini, grok, local")

                elif cmd == "/personality" and len(parts) > 1:
                    pers = parts[1].lower()
                    if pers in PERSONALITIES:
                        config.personality = pers
                        assistant = AntigravityAssistant(config)
                        print(f"✅ Personalidad: {pers}")
                    else:
                        print(f"❌ Personalidades: {', '.join(PERSONALITIES.keys())}")

                elif cmd == "/memory":
                    try:
                        memories = assistant.memory.list_memories()
                        print(f"📝 Memorias: {len(memories)}")
                        for m in memories[:5]:
                            print(f"   - {m.get('content', '')[:50]}...")
                    except Exception:
                        print("❌ Error accediendo memoria")

                elif cmd == "/clear":
                    try:
                        assistant.memory.clear()
                        print("✅ Memoria limpiada")
                    except Exception:
                        print("⚠️ No se pudo limpiar")

                elif cmd == "/help":
                    print("""
Comandos disponibles:
  /target <ai>      - Cambiar IA (claude, gpt, grok, gemini, local)
  /personality <p>  - Cambiar personalidad (professional, nerdy, cynical, etc.)
  /memory           - Ver memorias guardadas
  /clear            - Limpiar memoria
  /quit             - Salir

Ejemplo:
  /target gpt
  /personality nerdy
  Crea una API REST con autenticación JWT
""")
                continue

            # Procesar input normal
            response = assistant.process(user_input)
            print_response(response)

        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def print_response(response: AssistantResponse):
    """Imprime la respuesta del asistente."""
    analysis = response.analysis

    print(f"\n{'=' * 60}")
    print("🎯 ANÁLISIS DE TAREA")
    print(f"{'=' * 60}")
    print(f"  Tipo: {analysis.task_type}")
    print(f"  Complejidad: {analysis.complexity}")
    print(f"  Confianza: {analysis.confidence:.0%}")
    print(f"  Dominios: {', '.join(analysis.domains)}")

    print(f"\n{'=' * 60}")
    print("📋 RECOMENDACIONES")
    print(f"{'=' * 60}")
    for rec in response.recommendations:
        print(f"  {rec}")

    print(f"\n{'=' * 60}")
    print(f"✨ PROMPT LISTO PARA {response.target_ai.upper()}")
    print(f"{'=' * 60}")
    print(response.ready_prompt)

    # Guardrails warning
    if response.guardrails_check.get("risk") in ["high", "critical"]:
        print(f"\n⚠️ ADVERTENCIA DE SEGURIDAD: {response.guardrails_check.get('risk')}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Antigravity Assistant - Meta-Agente Inteligente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python antigravity_assistant.py "Crea una API REST"
  python antigravity_assistant.py "Investiga React 19" --target gpt
  python antigravity_assistant.py "Mi prompt" --personality nerdy
  python antigravity_assistant.py --interactive
        """,
    )

    parser.add_argument("prompt", nargs="?", help="Tu prompt o tarea")
    parser.add_argument(
        "--target",
        "-t",
        choices=["claude", "gpt", "gemini", "grok", "local"],
        default="claude",
        help="IA destino",
    )
    parser.add_argument(
        "--personality", "-p", default="professional", help="Personalidad del asistente"
    )
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo interactivo")
    parser.add_argument("--no-memory", action="store_true", help="Desactivar memoria")
    parser.add_argument("--no-guardrails", action="store_true", help="Desactivar guardrails")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo verbose")
    parser.add_argument(
        "--analyze-only", "-a", action="store_true", help="Solo analizar, no generar prompt"
    )
    parser.add_argument("--output", "-o", help="Guardar prompt a archivo")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    if not args.prompt:
        parser.print_help()
        return

    # Configurar asistente
    config = AssistantConfig(
        personality=args.personality,
        target_ai=args.target,
        auto_memory=not args.no_memory,
        auto_guardrails=not args.no_guardrails,
        verbose=args.verbose,
    )

    assistant = AntigravityAssistant(config)
    response = assistant.process(args.prompt)

    if args.analyze_only:
        print(f"\n📊 Tipo: {response.analysis.task_type}")
        print(f"🎯 Complejidad: {response.analysis.complexity}")
        print(f"🤖 Agentes: {', '.join(response.analysis.recommended_agents)}")
        print(f"🔧 Tools: {', '.join(response.analysis.recommended_tools)}")
        return

    print_response(response)

    if args.output:
        with open(args.output, "w") as f:
            f.write(response.ready_prompt)
        print(f"\n✅ Guardado en {args.output}")


if __name__ == "__main__":
    main()
