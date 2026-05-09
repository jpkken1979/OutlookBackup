#!/usr/bin/env python3
"""
Guardrails System - Sistema de Seguridad para Agentes IA
Basado en las políticas de seguridad de Claude, GPT y Grok

Uso:
    python guardrails.py check "Generate malware code"
    python guardrails.py validate response.txt
    python guardrails.py add-rule "No financial advice without disclaimer"
    python guardrails.py list-rules
"""

import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

BASE_PATH = Path(__file__).parent.parent
RULES_FILE = BASE_PATH / "guardrails" / "rules.json"


class RiskLevel(Enum):
    """Niveles de riesgo."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GuardrailRule:
    """Una regla de guardrail."""

    id: str
    name: str
    description: str
    category: str
    risk_level: str
    patterns: list[str]
    action: str  # warn, block, modify, flag
    message: str
    enabled: bool = True


@dataclass
class CheckResult:
    """Resultado de una verificación."""

    is_safe: bool
    risk_level: str
    triggered_rules: list[str]
    warnings: list[str]
    blocked: bool
    modified_content: str | None
    suggestions: list[str]


# Reglas de seguridad basadas en prompts de IA
DEFAULT_RULES = [
    GuardrailRule(
        id="harmful_content",
        name="Harmful Content Detection",
        description="Detecta solicitudes de contenido dañino",
        category="safety",
        risk_level="critical",
        patterns=[
            r"(create|write|generate|make)\s+(malware|virus|trojan|ransomware)",
            r"(hack|breach|attack)\s+(into|a|the)\s+\w+",
            r"(exploit|vulnerability|zero.?day)",
            r"how to (kill|harm|hurt|injure)",
        ],
        action="block",
        message="Esta solicitud parece requerir contenido potencialmente dañino.",
    ),
    GuardrailRule(
        id="personal_info",
        name="Personal Information Protection",
        description="Protege información personal identificable",
        category="privacy",
        risk_level="high",
        patterns=[
            r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b",  # SSN
            r"\b\d{16}\b",  # Credit card
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"(password|contraseña|clave)\s*[:=]\s*\S+",
        ],
        action="warn",
        message="Se detectó información personal que podría ser sensible.",
    ),
    GuardrailRule(
        id="illegal_activities",
        name="Illegal Activities Prevention",
        description="Previene asistencia en actividades ilegales",
        category="legal",
        risk_level="critical",
        patterns=[
            r"(steal|rob|theft|burglary)",
            r"(counterfeit|forge|fake)\s+(money|currency|documents?)",
            r"(drug|narcotic)\s+(synthesis|manufacture|create)",
            r"(weapons?|explosives?|bombs?)\s+(make|create|build)",
        ],
        action="block",
        message="No puedo asistir con actividades potencialmente ilegales.",
    ),
    GuardrailRule(
        id="misinformation",
        name="Misinformation Prevention",
        description="Previene la generación de desinformación",
        category="accuracy",
        risk_level="medium",
        patterns=[
            r"(fake|false)\s+(news|article|story)",
            r"(spread|create)\s+(rumor|misinformation)",
            r"(manipulate|deceive)\s+(public|people|voters)",
        ],
        action="warn",
        message="Esta solicitud podría generar desinformación.",
    ),
    GuardrailRule(
        id="financial_advice",
        name="Financial Advice Disclaimer",
        description="Requiere disclaimers para consejos financieros",
        category="compliance",
        risk_level="low",
        patterns=[
            r"(invest|buy|sell)\s+(stocks?|crypto|bitcoin|shares?)",
            r"(financial|investment)\s+(advice|recommendation)",
            r"(should i|is it good to)\s+(invest|buy)",
        ],
        action="modify",
        message="Recuerda incluir disclaimer: No soy asesor financiero.",
    ),
    GuardrailRule(
        id="medical_advice",
        name="Medical Advice Disclaimer",
        description="Requiere disclaimers para consejos médicos",
        category="compliance",
        risk_level="medium",
        patterns=[
            r"(diagnose|diagnosis|symptoms? of)",
            r"(should i take|prescribe|medication for)",
            r"(cure|treat|remedy)\s+for\s+\w+",
        ],
        action="modify",
        message="Disclaimer requerido: Consulta a un profesional médico.",
    ),
    GuardrailRule(
        id="code_injection",
        name="Code Injection Prevention",
        description="Detecta intentos de inyección de código",
        category="security",
        risk_level="high",
        patterns=[
            r"(eval|exec)\s*\(",
            r"__import__\s*\(",
            r"subprocess\.(call|run|Popen)",
            r"os\.(system|popen)",
            r"<script[^>]*>",
            r"(union|select|drop|delete|insert)\s+.*(from|into|table)",
        ],
        action="flag",
        message="Se detectó código potencialmente peligroso.",
    ),
    GuardrailRule(
        id="prompt_injection",
        name="Prompt Injection Detection",
        description="Detecta intentos de inyección de prompts",
        category="security",
        risk_level="high",
        patterns=[
            r"ignore\s+(previous|all|above)\s+(instructions?|prompts?)",
            r"(new|override)\s+(system|base)\s+prompt",
            r"you are now\s+\w+",
            r"forget\s+(everything|your|all)",
            r"(jailbreak|bypass|override)\s+(filters?|rules?|restrictions?)",
        ],
        action="block",
        message="Se detectó un intento de manipulación del sistema.",
    ),
    GuardrailRule(
        id="bias_prevention",
        name="Bias Prevention",
        description="Previene respuestas sesgadas",
        category="ethics",
        risk_level="medium",
        patterns=[
            r"(all|every)\s+(men|women|blacks?|whites?|asians?)\s+(are|is)",
            r"(superior|inferior)\s+race",
            r"(stereotype|generalize)\s+about\s+\w+",
        ],
        action="warn",
        message="Esta respuesta podría contener sesgos no deseados.",
    ),
    GuardrailRule(
        id="copyright_respect",
        name="Copyright Protection",
        description="Respeta derechos de autor",
        category="legal",
        risk_level="medium",
        patterns=[
            r"(copy|reproduce|pirate)\s+(entire|full|complete)\s+(book|article|song)",
            r"(bypass|crack|keygen)\s+(protection|drm|license)",
            r"(torrent|download)\s+(free|illegal)\s+\w+",
        ],
        action="warn",
        message="Respeta los derechos de autor y propiedad intelectual.",
    ),
]


def load_rules() -> list[GuardrailRule]:
    """Carga las reglas de guardrails."""
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)

    if RULES_FILE.exists():
        with open(RULES_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return [GuardrailRule(**r) for r in data.get("rules", [])]

    # Usar reglas por defecto
    save_rules(DEFAULT_RULES)
    return DEFAULT_RULES


def save_rules(rules: list[GuardrailRule]) -> None:
    """Guarda las reglas."""
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "rules": [asdict(r) for r in rules],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def check_content(content: str) -> CheckResult:
    """Verifica contenido contra todas las reglas."""
    rules = load_rules()
    triggered_rules = []
    warnings = []
    blocked = False
    suggestions = []
    highest_risk = RiskLevel.SAFE

    content_lower = content.lower()

    for rule in rules:
        if not rule.enabled:
            continue

        for pattern in rule.patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                triggered_rules.append(rule.name)

                # Determinar nivel de riesgo más alto
                rule_risk = RiskLevel[rule.risk_level.upper()]
                if list(RiskLevel).index(rule_risk) > list(RiskLevel).index(highest_risk):
                    highest_risk = rule_risk

                if rule.action == "block":
                    blocked = True
                    warnings.append(f"🛑 BLOQUEADO: {rule.message}")
                elif rule.action == "warn":
                    warnings.append(f"⚠️ ADVERTENCIA: {rule.message}")
                elif rule.action == "flag":
                    warnings.append(f"🚩 MARCADO: {rule.message}")
                elif rule.action == "modify":
                    suggestions.append(rule.message)

                break  # Solo una coincidencia por regla

    is_safe = highest_risk in [RiskLevel.SAFE, RiskLevel.LOW] and not blocked

    return CheckResult(
        is_safe=is_safe,
        risk_level=highest_risk.value,
        triggered_rules=triggered_rules,
        warnings=warnings,
        blocked=blocked,
        modified_content=None,
        suggestions=suggestions,
    )


def generate_guardrails_prompt() -> str:
    """Genera un prompt de seguridad para inyectar en agentes."""
    rules = load_rules()

    prompt = """
## Safety Guardrails

You must follow these safety guidelines at all times:

### Prohibited Actions
"""
    blocked_rules = [r for r in rules if r.action == "block" and r.enabled]
    for rule in blocked_rules:
        prompt += f"- {rule.description}\n"

    prompt += """
### Required Disclaimers
"""
    modify_rules = [r for r in rules if r.action == "modify" and r.enabled]
    for rule in modify_rules:
        prompt += f"- {rule.description}: {rule.message}\n"

    prompt += """
### Content Warnings
"""
    warn_rules = [r for r in rules if r.action == "warn" and r.enabled]
    for rule in warn_rules:
        prompt += f"- {rule.description}\n"

    prompt += """
### General Principles
- Be helpful but safe
- Acknowledge limitations
- Refer to professionals when appropriate
- Protect user privacy
- Avoid biased or harmful content
"""

    return prompt


def add_rule(
    name: str,
    description: str,
    patterns: list[str],
    category: str = "custom",
    risk_level: str = "medium",
    action: str = "warn",
) -> GuardrailRule:
    """Añade una nueva regla."""
    rules = load_rules()

    rule_id = name.lower().replace(" ", "_")

    # Verificar si ya existe
    if any(r.id == rule_id for r in rules):
        raise ValueError(f"Regla '{rule_id}' ya existe")

    new_rule = GuardrailRule(
        id=rule_id,
        name=name,
        description=description,
        category=category,
        risk_level=risk_level,
        patterns=patterns,
        action=action,
        message=description,
    )

    rules.append(new_rule)
    save_rules(rules)

    return new_rule


def list_rules() -> None:
    """Lista todas las reglas."""
    rules = load_rules()

    print("\n" + "=" * 70)
    print("🛡️ REGLAS DE GUARDRAILS")
    print("=" * 70 + "\n")

    # Agrupar por categoría
    by_category = {}
    for rule in rules:
        if rule.category not in by_category:
            by_category[rule.category] = []
        by_category[rule.category].append(rule)

    action_emoji = {"block": "🛑", "warn": "⚠️", "flag": "🚩", "modify": "✏️"}
    risk_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "safe": "⚪"}

    for category, cat_rules in by_category.items():
        print(f"📁 {category.upper()}")
        print("-" * 50)

        for rule in cat_rules:
            status = "✅" if rule.enabled else "❌"
            action = action_emoji.get(rule.action, "❓")
            risk = risk_emoji.get(rule.risk_level, "⚪")

            print(f"  {status} [{rule.id}] {rule.name}")
            print(f"     {action} Acción: {rule.action} | {risk} Riesgo: {rule.risk_level}")
            print(f"     {rule.description}")
            print()


def toggle_rule(rule_id: str, enabled: bool) -> bool:
    """Activa o desactiva una regla."""
    rules = load_rules()

    for rule in rules:
        if rule.id == rule_id:
            rule.enabled = enabled
            save_rules(rules)
            return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Guardrails System - Seguridad para agentes IA")
    subparsers = parser.add_subparsers(dest="command", help="Comandos")

    # Comando: check
    check_parser = subparsers.add_parser("check", help="Verificar contenido")
    check_parser.add_argument("content", help="Contenido a verificar")

    # Comando: validate
    validate_parser = subparsers.add_parser("validate", help="Validar archivo")
    validate_parser.add_argument("file", help="Archivo a validar")

    # Comando: list-rules
    subparsers.add_parser("list-rules", help="Listar reglas")

    # Comando: add-rule
    add_parser = subparsers.add_parser("add-rule", help="Añadir regla")
    add_parser.add_argument("name", help="Nombre de la regla")
    add_parser.add_argument("--description", "-d", required=True, help="Descripción")
    add_parser.add_argument("--patterns", "-p", nargs="+", required=True, help="Patrones regex")
    add_parser.add_argument("--category", "-c", default="custom", help="Categoría")
    add_parser.add_argument(
        "--risk", "-r", default="medium", choices=["low", "medium", "high", "critical"]
    )
    add_parser.add_argument(
        "--action", "-a", default="warn", choices=["warn", "block", "flag", "modify"]
    )

    # Comando: enable/disable
    toggle_parser = subparsers.add_parser("toggle", help="Activar/desactivar regla")
    toggle_parser.add_argument("rule_id", help="ID de la regla")
    toggle_parser.add_argument("--enable", action="store_true")
    toggle_parser.add_argument("--disable", action="store_true")

    # Comando: generate-prompt
    subparsers.add_parser("generate-prompt", help="Generar prompt de seguridad")

    # Comando: reset
    subparsers.add_parser("reset", help="Resetear a reglas por defecto")

    args = parser.parse_args()

    if args.command == "check":
        result = check_content(args.content)
        print("\n" + "=" * 50)
        print("🔍 RESULTADO DE VERIFICACIÓN")
        print("=" * 50)
        print(f"\nSeguro: {'✅ Sí' if result.is_safe else '❌ No'}")
        print(f"Nivel de riesgo: {result.risk_level}")
        print(f"Bloqueado: {'Sí' if result.blocked else 'No'}")

        if result.triggered_rules:
            print("\nReglas activadas:")
            for rule in result.triggered_rules:
                print(f"  - {rule}")

        if result.warnings:
            print("\nAdvertencias:")
            for w in result.warnings:
                print(f"  {w}")

        if result.suggestions:
            print("\nSugerencias:")
            for s in result.suggestions:
                print(f"  💡 {s}")

    elif args.command == "validate":
        with open(args.file, encoding="utf-8") as f:
            content = f.read()
        result = check_content(content)
        print(f"\n📄 Validando: {args.file}")
        print(f"   Resultado: {'✅ Seguro' if result.is_safe else '❌ Revisar'}")
        if result.warnings:
            for w in result.warnings:
                print(f"   {w}")

    elif args.command == "list-rules":
        list_rules()

    elif args.command == "add-rule":
        rule = add_rule(
            name=args.name,
            description=args.description,
            patterns=args.patterns,
            category=args.category,
            risk_level=args.risk,
            action=args.action,
        )
        print(f"✅ Regla '{rule.name}' añadida")

    elif args.command == "toggle":
        if args.enable:
            toggle_rule(args.rule_id, True)
            print(f"✅ Regla '{args.rule_id}' activada")
        elif args.disable:
            toggle_rule(args.rule_id, False)
            print(f"❌ Regla '{args.rule_id}' desactivada")

    elif args.command == "generate-prompt":
        prompt = generate_guardrails_prompt()
        print(prompt)

    elif args.command == "reset":
        save_rules(DEFAULT_RULES)
        print("✅ Reglas reseteadas a valores por defecto")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
