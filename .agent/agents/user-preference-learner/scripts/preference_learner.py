#!/usr/bin/env python3
"""
User Preference Learner Agent - Aprende preferencias del usuario

Construye modelo de preferencias que mejora la experiencia.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class PreferenceSource(Enum):
    EXPLICIT = "explicit"  # Usuario lo dijo directamente
    INFERRED = "inferred"  # Inferido de comportamiento
    DEFAULT = "default"  # Valor por defecto


@dataclass
class Preference:
    key: str
    value: Any
    confidence: float  # 0-1
    source: PreferenceSource
    evidence: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PreferenceProfile:
    user_id: str
    preferences: dict[str, Preference]
    interaction_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class UserPreferenceLearner:
    """Aprende y aplica preferencias del usuario."""

    # Preferencias por defecto
    DEFAULT_PREFERENCES = {
        "code.language": "infer_from_project",
        "code.style.quotes": "infer_from_project",
        "code.style.indent": "spaces",
        "code.style.indent_size": 4,
        "commit.style": "conventional",
        "commit.language": "english",
        "communication.verbosity": "balanced",
        "communication.language": "spanish",
        "testing.coverage_target": 80,
        "documentation.auto_generate": True,
    }

    def __init__(self, profile_path: str | None = None):
        self.profile_path = (
            Path(profile_path) if profile_path else Path(".agent/memory/user_preferences.json")
        )
        self.profile = self._load_profile()

    def _load_profile(self) -> PreferenceProfile:
        """Carga perfil de preferencias."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path) as f:
                    data = json.load(f)

                preferences = {}
                for key, pref_data in data.get("preferences", {}).items():
                    preferences[key] = Preference(
                        key=key,
                        value=pref_data["value"],
                        confidence=pref_data["confidence"],
                        source=PreferenceSource(pref_data["source"]),
                        evidence=pref_data.get("evidence", []),
                        created_at=datetime.fromisoformat(
                            pref_data.get("created_at", datetime.now().isoformat())
                        ),
                        updated_at=datetime.fromisoformat(
                            pref_data.get("updated_at", datetime.now().isoformat())
                        ),
                    )

                return PreferenceProfile(
                    user_id=data.get("user_id", "default"),
                    preferences=preferences,
                    interaction_count=data.get("interaction_count", 0),
                )
            except Exception:
                pass

        # Crear perfil con defaults
        preferences = {}
        for key, value in self.DEFAULT_PREFERENCES.items():
            preferences[key] = Preference(
                key=key, value=value, confidence=0.5, source=PreferenceSource.DEFAULT
            )

        return PreferenceProfile(user_id="default", preferences=preferences)

    def _save_profile(self):
        """Guarda perfil de preferencias."""
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "user_id": self.profile.user_id,
            "interaction_count": self.profile.interaction_count,
            "created_at": self.profile.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
            "preferences": {
                key: {
                    "value": pref.value,
                    "confidence": pref.confidence,
                    "source": pref.source.value,
                    "evidence": pref.evidence[-10:],  # Ultimas 10
                    "created_at": pref.created_at.isoformat(),
                    "updated_at": pref.updated_at.isoformat(),
                }
                for key, pref in self.profile.preferences.items()
            },
        }

        with open(self.profile_path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, key: str) -> Preference | None:
        """Obtiene preferencia por clave."""
        return self.profile.preferences.get(key)

    def set(
        self,
        key: str,
        value: Any,
        source: PreferenceSource = PreferenceSource.EXPLICIT,
        evidence: str | None = None,
    ):
        """Establece preferencia."""
        existing = self.profile.preferences.get(key)

        if existing:
            # Actualizar existente
            existing.value = value
            existing.updated_at = datetime.now()

            if source == PreferenceSource.EXPLICIT:
                existing.confidence = 1.0
                existing.source = source
            elif source == PreferenceSource.INFERRED:
                # Incrementar confianza gradualmente
                existing.confidence = min(1.0, existing.confidence + 0.1)

            if evidence:
                existing.evidence.append(evidence)
        else:
            # Crear nueva
            self.profile.preferences[key] = Preference(
                key=key,
                value=value,
                confidence=1.0 if source == PreferenceSource.EXPLICIT else 0.6,
                source=source,
                evidence=[evidence] if evidence else [],
            )

        self._save_profile()

    def infer_from_code(self, code: str, file_path: str) -> list[tuple[str, Any]]:
        """Infiere preferencias del codigo."""
        inferences = []

        # Detectar quotes
        single_quotes = code.count("'")
        double_quotes = code.count('"')
        if single_quotes > double_quotes * 2:
            inferences.append(("code.style.quotes", "single"))
        elif double_quotes > single_quotes * 2:
            inferences.append(("code.style.quotes", "double"))

        # Detectar indentacion
        lines = code.split("\n")
        space_indent = 0
        tab_indent = 0
        for line in lines:
            if line.startswith("    "):
                space_indent += 1
            elif line.startswith("\t"):
                tab_indent += 1

        if space_indent > tab_indent * 2:
            inferences.append(("code.style.indent", "spaces"))
        elif tab_indent > space_indent * 2:
            inferences.append(("code.style.indent", "tabs"))

        # Detectar lenguaje
        ext = Path(file_path).suffix
        lang_map = {
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".py": "python",
            ".rs": "rust",
            ".go": "go",
        }
        if ext in lang_map:
            inferences.append(("code.language", lang_map[ext]))

        return inferences

    def infer_from_feedback(self, feedback: str):
        """Infiere preferencias del feedback del usuario."""
        feedback_lower = feedback.lower()

        # Detectar preferencias de comunicacion
        if "mas detalle" in feedback_lower or "explica mas" in feedback_lower:
            self.set(
                "communication.verbosity",
                "detailed",
                PreferenceSource.INFERRED,
                f"User asked: {feedback[:50]}",
            )
        elif "mas corto" in feedback_lower or "resumen" in feedback_lower:
            self.set(
                "communication.verbosity",
                "concise",
                PreferenceSource.INFERRED,
                f"User asked: {feedback[:50]}",
            )

        # Detectar idioma preferido
        spanish_words = ["quiero", "necesito", "por favor", "gracias", "cambiar"]
        english_words = ["want", "need", "please", "thanks", "change"]

        spanish_count = sum(1 for w in spanish_words if w in feedback_lower)
        english_count = sum(1 for w in english_words if w in feedback_lower)

        if spanish_count > english_count:
            self.set(
                "communication.language",
                "spanish",
                PreferenceSource.INFERRED,
                "Detected Spanish usage",
            )
        elif english_count > spanish_count:
            self.set(
                "communication.language",
                "english",
                PreferenceSource.INFERRED,
                "Detected English usage",
            )

    def should_apply(self, key: str, min_confidence: float = 0.7) -> bool:
        """Verifica si una preferencia debe aplicarse."""
        pref = self.get(key)
        if not pref:
            return False
        return pref.confidence >= min_confidence

    def get_all(self) -> dict[str, dict]:
        """Obtiene todas las preferencias."""
        return {
            key: {"value": pref.value, "confidence": pref.confidence, "source": pref.source.value}
            for key, pref in self.profile.preferences.items()
        }

    def execute(self, command: str) -> dict:
        """Ejecuta comando."""
        command_lower = command.lower()

        if command_lower == "show" or command_lower == "list":
            return {
                "operation": "list",
                "preferences": self.get_all(),
                "interaction_count": self.profile.interaction_count,
            }

        elif command_lower.startswith("get:"):
            key = command[4:].strip()
            pref = self.get(key)
            if pref:
                return {
                    "operation": "get",
                    "key": key,
                    "value": pref.value,
                    "confidence": pref.confidence,
                    "source": pref.source.value,
                }
            return {"operation": "get", "key": key, "error": "Preference not found"}

        elif command_lower.startswith("set:"):
            # Format: set: key=value
            parts = command[4:].strip().split("=", 1)
            if len(parts) == 2:
                key, value = parts[0].strip(), parts[1].strip()
                # Intentar parsear valor
                try:
                    value = json.loads(value)
                except Exception:
                    pass  # Mantener como string

                self.set(key, value, PreferenceSource.EXPLICIT)
                return {"operation": "set", "key": key, "value": value, "success": True}
            return {"operation": "set", "error": "Invalid format. Use: set: key=value"}

        elif command_lower.startswith("infer:"):
            feedback = command[6:].strip()
            self.infer_from_feedback(feedback)
            return {"operation": "infer", "feedback": feedback[:50], "success": True}

        elif command_lower.startswith("export:"):
            path = command[7:].strip() or "preferences_export.json"
            data = {"preferences": self.get_all(), "exported_at": datetime.now().isoformat()}
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return {"operation": "export", "path": path, "success": True}

        else:
            return {
                "operation": "unknown",
                "error": f"Unknown command: {command}",
                "available": [
                    "show",
                    "get:<key>",
                    "set:<key>=<value>",
                    "infer:<feedback>",
                    "export:<path>",
                ],
            }


def main():
    parser = argparse.ArgumentParser(
        description="User Preference Learner - Aprende preferencias del usuario"
    )
    parser.add_argument(
        "command", nargs="?", default="show", help="Comando (show, get, set, infer, export)"
    )
    parser.add_argument("--profile", help="Path al archivo de perfil")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    learner = UserPreferenceLearner(args.profile)
    result = learner.execute(args.command)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        op = result.get("operation", "unknown")

        if op == "list":
            print("User Preferences")
            print("=" * 40)
            for key, data in result.get("preferences", {}).items():
                conf = f"{data['confidence']:.0%}"
                src = data["source"][0].upper()
                print(f"  {key}: {data['value']} [{conf}, {src}]")
            print(f"\nInteractions: {result.get('interaction_count', 0)}")

        elif op == "get":
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"{result['key']}: {result['value']}")
                print(f"  Confidence: {result['confidence']:.0%}")
                print(f"  Source: {result['source']}")

        elif op in ["set", "infer", "export"]:
            status = "✓" if result.get("success") else "✗"
            print(f"[{status}] {op.title()} completed")

        else:
            print(f"Error: {result.get('error', 'Unknown')}")

    sys.exit(0)


if __name__ == "__main__":
    main()
