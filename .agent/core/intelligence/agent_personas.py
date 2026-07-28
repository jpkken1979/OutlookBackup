# mypy: ignore-errors
#!/usr/bin/env python3
"""
Agent Personas Module.

Configurable personality traits and communication styles for agents.

Features:
- Predefined personas (professional, friendly, technical, etc.)
- Custom persona creation
- Dynamic persona switching
- Communication style adaptation
- Personality trait management

Version: 1.0.0
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("agent-personas")


class CommunicationStyle(Enum):
    """Communication styles."""

    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    FRIENDLY = "friendly"
    CONCISE = "concise"
    DETAILED = "detailed"
    EMPATHETIC = "empathetic"
    DIRECT = "direct"


class PersonalityTrait(Enum):
    """Personality traits."""

    HELPFUL = "helpful"
    PATIENT = "patient"
    THOROUGH = "thorough"
    EFFICIENT = "efficient"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    CAUTIOUS = "cautious"
    BOLD = "bold"
    ENCOURAGING = "encouraging"
    HONEST = "honest"
    HUMBLE = "humble"
    CONFIDENT = "confident"
    DIRECT = "direct"


class ExpertiseLevel(Enum):
    """How agent presents expertise."""

    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"
    MENTOR = "mentor"
    PEER = "peer"


@dataclass
class PersonaConfig:
    """Configuration for an agent persona."""

    name: str
    description: str
    communication_style: CommunicationStyle
    personality_traits: list[PersonalityTrait]
    expertise_level: ExpertiseLevel
    greeting_template: str
    response_prefix: str
    error_handling_style: str
    emoji_usage: bool = False
    formality_level: float = 0.5  # 0 = very casual, 1 = very formal
    verbosity: float = 0.5  # 0 = concise, 1 = verbose
    custom_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "communication_style": self.communication_style.value,
            "personality_traits": [t.value for t in self.personality_traits],
            "expertise_level": self.expertise_level.value,
            "greeting_template": self.greeting_template,
            "response_prefix": self.response_prefix,
            "error_handling_style": self.error_handling_style,
            "emoji_usage": self.emoji_usage,
            "formality_level": self.formality_level,
            "verbosity": self.verbosity,
            "custom_rules": self.custom_rules,
        }


@dataclass
class PersonaResponse:
    """A response formatted according to persona."""

    original_content: str
    formatted_content: str
    persona_used: str
    style_adjustments: list[str]

    def to_dict(self) -> dict:
        return {
            "original_content": self.original_content,
            "formatted_content": self.formatted_content,
            "persona_used": self.persona_used,
            "style_adjustments": self.style_adjustments,
        }


# =============================================================================
# PREDEFINED PERSONAS
# =============================================================================

PREDEFINED_PERSONAS = {
    "professional": PersonaConfig(
        name="Professional",
        description="Formal, efficient, and business-focused communication",
        communication_style=CommunicationStyle.FORMAL,
        personality_traits=[
            PersonalityTrait.EFFICIENT,
            PersonalityTrait.THOROUGH,
            PersonalityTrait.HONEST,
        ],
        expertise_level=ExpertiseLevel.EXPERT,
        greeting_template="Hello. How may I assist you today?",
        response_prefix="",
        error_handling_style="I apologize for the inconvenience. Let me address this issue.",
        emoji_usage=False,
        formality_level=0.8,
        verbosity=0.5,
    ),
    "friendly": PersonaConfig(
        name="Friendly",
        description="Warm, approachable, and encouraging communication",
        communication_style=CommunicationStyle.FRIENDLY,
        personality_traits=[
            PersonalityTrait.HELPFUL,
            PersonalityTrait.ENCOURAGING,
            PersonalityTrait.PATIENT,
        ],
        expertise_level=ExpertiseLevel.PEER,
        greeting_template="Hey there! Great to see you. What can I help you with?",
        response_prefix="",
        error_handling_style="Oops, that didn't work as expected. No worries, let's figure this out together!",
        emoji_usage=True,
        formality_level=0.2,
        verbosity=0.6,
    ),
    "technical": PersonaConfig(
        name="Technical",
        description="Precise, detailed, and technically-focused communication",
        communication_style=CommunicationStyle.TECHNICAL,
        personality_traits=[
            PersonalityTrait.ANALYTICAL,
            PersonalityTrait.THOROUGH,
            PersonalityTrait.HONEST,
        ],
        expertise_level=ExpertiseLevel.EXPERT,
        greeting_template="Ready for technical assistance. Please describe the issue or task.",
        response_prefix="",
        error_handling_style="Error encountered. Analyzing root cause and potential solutions.",
        emoji_usage=False,
        formality_level=0.6,
        verbosity=0.7,
    ),
    "mentor": PersonaConfig(
        name="Mentor",
        description="Educational, patient, and explanatory communication",
        communication_style=CommunicationStyle.DETAILED,
        personality_traits=[
            PersonalityTrait.PATIENT,
            PersonalityTrait.ENCOURAGING,
            PersonalityTrait.THOROUGH,
        ],
        expertise_level=ExpertiseLevel.MENTOR,
        greeting_template="Hello! I'm here to help you learn and grow. What would you like to explore?",
        response_prefix="Let me explain this step by step. ",
        error_handling_style="This is actually a great learning opportunity! Let's understand what happened and why.",
        emoji_usage=False,
        formality_level=0.5,
        verbosity=0.8,
    ),
    "concise": PersonaConfig(
        name="Concise",
        description="Brief, to-the-point, and efficient communication",
        communication_style=CommunicationStyle.CONCISE,
        personality_traits=[
            PersonalityTrait.EFFICIENT,
            PersonalityTrait.DIRECT,
            PersonalityTrait.HONEST,
        ],
        expertise_level=ExpertiseLevel.EXPERT,
        greeting_template="Ready.",
        response_prefix="",
        error_handling_style="Error occurred. Fix: ",
        emoji_usage=False,
        formality_level=0.5,
        verbosity=0.1,
    ),
    "supportive": PersonaConfig(
        name="Supportive",
        description="Empathetic, understanding, and reassuring communication",
        communication_style=CommunicationStyle.EMPATHETIC,
        personality_traits=[
            PersonalityTrait.HELPFUL,
            PersonalityTrait.PATIENT,
            PersonalityTrait.ENCOURAGING,
        ],
        expertise_level=ExpertiseLevel.PEER,
        greeting_template="Hi there. I'm here to help, and we'll work through this together.",
        response_prefix="I understand. ",
        error_handling_style="I can see this is frustrating. Let's take a breath and tackle this step by step.",
        emoji_usage=False,
        formality_level=0.4,
        verbosity=0.6,
    ),
    "creative": PersonaConfig(
        name="Creative",
        description="Innovative, exploratory, and idea-generating communication",
        communication_style=CommunicationStyle.CASUAL,
        personality_traits=[
            PersonalityTrait.CREATIVE,
            PersonalityTrait.BOLD,
            PersonalityTrait.ENCOURAGING,
        ],
        expertise_level=ExpertiseLevel.PEER,
        greeting_template="Hey! Ready to explore some interesting ideas?",
        response_prefix="Here's an interesting approach: ",
        error_handling_style="Hmm, that didn't work, but it gives us a chance to try something different!",
        emoji_usage=True,
        formality_level=0.3,
        verbosity=0.6,
    ),
    "cautious": PersonaConfig(
        name="Cautious",
        description="Careful, risk-aware, and thorough communication",
        communication_style=CommunicationStyle.DETAILED,
        personality_traits=[
            PersonalityTrait.CAUTIOUS,
            PersonalityTrait.THOROUGH,
            PersonalityTrait.HONEST,
        ],
        expertise_level=ExpertiseLevel.EXPERT,
        greeting_template="Hello. Before we proceed, let me ensure we consider all aspects carefully.",
        response_prefix="Before proceeding, note that ",
        error_handling_style="This error occurred because [reason]. Here are the implications and safe remediation steps.",
        emoji_usage=False,
        formality_level=0.7,
        verbosity=0.8,
    ),
}


class AgentPersonas:
    """
    Manages agent personas and communication styles.

    Features:
    - Predefined personas for common scenarios
    - Custom persona creation
    - Dynamic switching based on context
    - Response formatting according to persona
    """

    def __init__(self, default_persona: str = "professional"):
        self.current_persona: PersonaConfig = PREDEFINED_PERSONAS.get(
            default_persona, PREDEFINED_PERSONAS["professional"]
        )
        self.custom_personas: dict[str, PersonaConfig] = {}
        self.persona_history: list[tuple[datetime, str]] = []

    def get_available_personas(self) -> list[str]:
        """Get list of available persona names."""
        return list(PREDEFINED_PERSONAS.keys()) + list(self.custom_personas.keys())

    def get_persona(self, name: str) -> PersonaConfig | None:
        """Get a persona by name."""
        if name in PREDEFINED_PERSONAS:
            return PREDEFINED_PERSONAS[name]
        return self.custom_personas.get(name)

    def set_persona(self, name: str) -> bool:
        """Set the current persona."""
        persona = self.get_persona(name)
        if persona:
            self.current_persona = persona
            self.persona_history.append((datetime.now(), name))
            logger.info(f"Persona switched to: {name}")
            return True
        return False

    def create_custom_persona(
        self,
        name: str,
        description: str,
        communication_style: CommunicationStyle,
        personality_traits: list[PersonalityTrait],
        **kwargs,
    ) -> PersonaConfig:
        """Create a custom persona."""
        persona = PersonaConfig(
            name=name,
            description=description,
            communication_style=communication_style,
            personality_traits=personality_traits,
            expertise_level=kwargs.get("expertise_level", ExpertiseLevel.EXPERT),
            greeting_template=kwargs.get("greeting_template", "Hello. How can I help?"),
            response_prefix=kwargs.get("response_prefix", ""),
            error_handling_style=kwargs.get(
                "error_handling_style", "An error occurred. Let me help resolve it."
            ),
            emoji_usage=kwargs.get("emoji_usage", False),
            formality_level=kwargs.get("formality_level", 0.5),
            verbosity=kwargs.get("verbosity", 0.5),
            custom_rules=kwargs.get("custom_rules", []),
        )

        self.custom_personas[name] = persona
        logger.info(f"Custom persona created: {name}")
        return persona

    def format_response(
        self, content: str, persona: PersonaConfig = None, context: dict | None = None
    ) -> PersonaResponse:
        """
        Format a response according to persona.

        Args:
            content: Original content to format
            persona: Persona to use (current if None)
            context: Additional context

        Returns:
            Formatted response
        """
        persona = persona or self.current_persona
        context = context or {}
        adjustments = []

        formatted = content

        # Apply prefix
        if persona.response_prefix and not formatted.startswith(persona.response_prefix):
            formatted = persona.response_prefix + formatted
            adjustments.append("Added response prefix")

        # Adjust formality
        if persona.formality_level > 0.7:
            formatted = self._increase_formality(formatted)
            adjustments.append("Increased formality")
        elif persona.formality_level < 0.3:
            formatted = self._decrease_formality(formatted)
            adjustments.append("Decreased formality")

        # Adjust verbosity
        if persona.verbosity < 0.3:
            formatted = self._make_concise(formatted)
            adjustments.append("Made concise")
        elif persona.verbosity > 0.7:
            formatted = self._add_detail(formatted)
            adjustments.append("Added detail")

        # Add/remove emojis
        if persona.emoji_usage:
            formatted = self._add_emojis(formatted)
            adjustments.append("Added emojis")
        else:
            formatted = self._remove_emojis(formatted)

        # Apply custom rules
        for rule in persona.custom_rules:
            formatted = self._apply_custom_rule(formatted, rule)
            adjustments.append(f"Applied rule: {rule[:20]}...")

        return PersonaResponse(
            original_content=content,
            formatted_content=formatted,
            persona_used=persona.name,
            style_adjustments=adjustments,
        )

    def _increase_formality(self, text: str) -> str:
        """Increase text formality."""
        replacements = {
            "hey": "hello",
            "hi": "hello",
            "yeah": "yes",
            "nope": "no",
            "gonna": "going to",
            "wanna": "want to",
            "gotta": "have to",
            "can't": "cannot",
            "won't": "will not",
            "don't": "do not",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "couldn't": "could not",
        }

        result = text
        for informal, formal in replacements.items():
            result = result.replace(informal, formal)
            result = result.replace(informal.capitalize(), formal.capitalize())

        return result

    def _decrease_formality(self, text: str) -> str:
        """Decrease text formality."""
        replacements = {
            "I would like to": "I'd like to",
            "cannot": "can't",
            "will not": "won't",
            "do not": "don't",
            "however": "but",
            "therefore": "so",
            "additionally": "also",
            "subsequently": "then",
            "prior to": "before",
        }

        result = text
        for formal, informal in replacements.items():
            result = result.replace(formal, informal)

        return result

    def _make_concise(self, text: str) -> str:
        """Make text more concise."""
        # Remove filler phrases
        fillers = [
            "It is important to note that ",
            "It should be noted that ",
            "As you may know, ",
            "In order to ",
            "For the purpose of ",
            "At this point in time, ",
            "Due to the fact that ",
            "In the event that ",
        ]

        result = text
        for filler in fillers:
            result = result.replace(filler, "")
            result = result.replace(filler.lower(), "")

        return result

    def _add_detail(self, text: str) -> str:
        """Add more detail/explanation."""
        # This is a simplified version - real implementation would be more sophisticated
        if not text.endswith("."):
            text += "."

        # Don't add too much
        if len(text) < 100:
            text += " Let me know if you need more details."

        return text

    def _add_emojis(self, text: str) -> str:
        """Add contextual emojis."""
        emoji_map = {
            "success": " ✅",
            "error": " ❌",
            "warning": " ⚠️",
            "tip": " 💡",
            "important": " ⭐",
            "done": " ✓",
            "note": " 📝",
        }

        result = text
        for keyword, emoji in emoji_map.items():
            if keyword in text.lower() and emoji not in text:
                result = result.replace(keyword, keyword + emoji, 1)

        return result

    def _remove_emojis(self, text: str) -> str:
        """Remove emojis from text."""
        import re

        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f700-\U0001f77f"  # alchemical symbols
            "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
            "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
            "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
            "\U0001fa00-\U0001fa6f"  # Chess Symbols
            "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027b0"  # Dingbats
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )
        return emoji_pattern.sub("", text)

    def _apply_custom_rule(self, text: str, rule: str) -> str:
        """Apply a custom formatting rule."""
        # Custom rules are in format "replace:old:new" or "prefix:text" etc.
        if rule.startswith("replace:"):
            parts = rule.split(":", 2)
            if len(parts) == 3:
                text = text.replace(parts[1], parts[2])
        elif rule.startswith("prefix:"):
            prefix = rule[7:]
            if not text.startswith(prefix):
                text = prefix + text
        elif rule.startswith("suffix:"):
            suffix = rule[7:]
            if not text.endswith(suffix):
                text = text + suffix
        return text

    def get_greeting(self, persona: PersonaConfig = None) -> str:
        """Get greeting for persona."""
        persona = persona or self.current_persona
        return persona.greeting_template

    def get_error_response(self, error: str, persona: PersonaConfig = None) -> str:
        """Get error response formatted for persona."""
        persona = persona or self.current_persona
        return f"{persona.error_handling_style}\n\nDetails: {error}"

    def export_persona(self, name: str) -> str | None:
        """Export persona as JSON."""
        persona = self.get_persona(name)
        if persona:
            return json.dumps(persona.to_dict(), indent=2)
        return None

    def import_persona(self, json_str: str) -> PersonaConfig | None:
        """Import persona from JSON."""
        try:
            data = json.loads(json_str)
            persona = PersonaConfig(
                name=data["name"],
                description=data["description"],
                communication_style=CommunicationStyle(data["communication_style"]),
                personality_traits=[PersonalityTrait(t) for t in data["personality_traits"]],
                expertise_level=ExpertiseLevel(data["expertise_level"]),
                greeting_template=data["greeting_template"],
                response_prefix=data["response_prefix"],
                error_handling_style=data["error_handling_style"],
                emoji_usage=data.get("emoji_usage", False),
                formality_level=data.get("formality_level", 0.5),
                verbosity=data.get("verbosity", 0.5),
                custom_rules=data.get("custom_rules", []),
            )
            self.custom_personas[persona.name] = persona
            return persona
        except Exception as e:
            logger.error(f"Failed to import persona: {e}")
            return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_manager: AgentPersonas | None = None


def get_persona_manager() -> AgentPersonas:
    """Get persona manager instance."""
    global _manager
    if _manager is None:
        _manager = AgentPersonas()
    return _manager


def set_persona(name: str) -> bool:
    """Set current persona."""
    return get_persona_manager().set_persona(name)


def format_with_persona(content: str, persona_name: str = None) -> str:
    """Format content with persona."""
    manager = get_persona_manager()
    persona = manager.get_persona(persona_name) if persona_name else None
    result = manager.format_response(content, persona)
    return result.formatted_content


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Agent Personas")
    parser.add_argument("--list", action="store_true", help="List available personas")
    parser.add_argument("--show", help="Show persona details")
    parser.add_argument("--format", help="Format text with persona")
    parser.add_argument("--persona", default="professional", help="Persona to use")
    args = parser.parse_args()

    manager = get_persona_manager()

    if args.list:
        print("Available Personas:")
        for name in manager.get_available_personas():
            persona = manager.get_persona(name)
            print(f"  - {name}: {persona.description}")

    elif args.show:
        persona = manager.get_persona(args.show)
        if persona:
            print(json.dumps(persona.to_dict(), indent=2))
        else:
            print(f"Persona not found: {args.show}")

    elif args.format:
        manager.set_persona(args.persona)
        result = manager.format_response(args.format)
        print(f"Original: {result.original_content}")
        print(f"Formatted: {result.formatted_content}")
        print(f"Adjustments: {result.style_adjustments}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
