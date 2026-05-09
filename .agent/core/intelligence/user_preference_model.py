"""
User Preference Model - Modelo de preferencias del usuario

Aprende y aplica preferencias para personalizar la experiencia.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class PreferenceSource(Enum):
    """Fuente de una preferencia."""

    EXPLICIT = "explicit"  # Usuario lo dijo directamente
    INFERRED = "inferred"  # Inferido de comportamiento
    DEFAULT = "default"  # Valor por defecto
    INHERITED = "inherited"  # Heredado de configuracion


class ConfidenceLevel(Enum):
    """Nivel de confianza."""

    CERTAIN = "certain"  # >= 0.95
    HIGH = "high"  # >= 0.80
    MEDIUM = "medium"  # >= 0.60
    LOW = "low"  # >= 0.40
    UNCERTAIN = "uncertain"  # < 0.40


@dataclass
class Preference:
    """Una preferencia del usuario."""

    key: str
    value: Any
    confidence: float
    source: PreferenceSource
    evidence: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Obtiene nivel de confianza."""
        if self.confidence >= 0.95:
            return ConfidenceLevel.CERTAIN
        if self.confidence >= 0.80:
            return ConfidenceLevel.HIGH
        if self.confidence >= 0.60:
            return ConfidenceLevel.MEDIUM
        if self.confidence >= 0.40:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.UNCERTAIN


@dataclass
class UserProfile:
    """Perfil completo del usuario."""

    user_id: str
    preferences: dict[str, Preference]
    interaction_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class UserPreferenceModel:
    """
    Modelo de preferencias del usuario.

    Funcionalidades:
    - Inferencia de preferencias desde comportamiento
    - Almacenamiento persistente
    - Aplicacion contextual de preferencias
    - Decay temporal de confianza
    """

    # Preferencias por defecto
    DEFAULT_PREFERENCES = {
        # Codigo
        "code.language": ("auto", 0.5),
        "code.style.quotes": ("auto", 0.5),
        "code.style.indent": ("spaces", 0.6),
        "code.style.indent_size": (4, 0.6),
        "code.comments.language": ("english", 0.5),
        # Git
        "git.commit.style": ("conventional", 0.7),
        "git.commit.language": ("english", 0.6),
        "git.branch.prefix": ("feature/", 0.5),
        # Comunicacion
        "communication.language": ("auto", 0.5),
        "communication.verbosity": ("balanced", 0.6),
        "communication.formality": ("professional", 0.6),
        # Testing
        "testing.coverage_target": (80, 0.5),
        "testing.style": ("unit_first", 0.5),
        # Documentacion
        "docs.auto_generate": (True, 0.5),
        "docs.style": ("concise", 0.5),
    }

    def __init__(self, storage_path: str | None = None):
        self.storage_path = (
            Path(storage_path) if storage_path else Path(".agent/memory/user_model.json")
        )
        self.profile = self._load_or_create_profile()
        self.observation_buffer: list[dict] = []

    def _load_or_create_profile(self) -> UserProfile:
        """Carga o crea perfil de usuario."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    data = json.load(f)

                prefs = {}
                for key, pref_data in data.get("preferences", {}).items():
                    prefs[key] = Preference(
                        key=key,
                        value=pref_data["value"],
                        confidence=pref_data["confidence"],
                        source=PreferenceSource(pref_data["source"]),
                        evidence=pref_data.get("evidence", []),
                    )

                return UserProfile(
                    user_id=data.get("user_id", "default"),
                    preferences=prefs,
                    interaction_count=data.get("interaction_count", 0),
                )
            except Exception:
                pass

        # Crear con defaults
        prefs = {}
        for key, (value, conf) in self.DEFAULT_PREFERENCES.items():
            prefs[key] = Preference(
                key=key, value=value, confidence=conf, source=PreferenceSource.DEFAULT
            )

        return UserProfile(user_id="default", preferences=prefs)

    def _save_profile(self):
        """Guarda perfil a disco."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "user_id": self.profile.user_id,
            "interaction_count": self.profile.interaction_count,
            "updated_at": datetime.now().isoformat(),
            "preferences": {
                key: {
                    "value": pref.value,
                    "confidence": pref.confidence,
                    "source": pref.source.value,
                    "evidence": pref.evidence[-20:],
                }
                for key, pref in self.profile.preferences.items()
            },
        }

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get(self, key: str, default: Any = None) -> tuple[Any, float]:
        """
        Obtiene preferencia.

        Args:
            key: Clave de la preferencia
            default: Valor por defecto si no existe

        Returns:
            Tuple de (valor, confianza)
        """
        pref = self.profile.preferences.get(key)
        if pref:
            pref.access_count += 1
            return pref.value, pref.confidence
        return default, 0.0

    def set(
        self,
        key: str,
        value: Any,
        source: PreferenceSource = PreferenceSource.EXPLICIT,
        evidence: str | None = None,
    ):
        """
        Establece preferencia.

        Args:
            key: Clave de la preferencia
            value: Valor
            source: Fuente (explicit, inferred, etc.)
            evidence: Evidencia que soporta esta preferencia
        """
        existing = self.profile.preferences.get(key)

        if existing:
            # Actualizar existente
            if source == PreferenceSource.EXPLICIT:
                existing.value = value
                existing.confidence = 1.0
                existing.source = source
            elif source == PreferenceSource.INFERRED:
                # Solo actualizar si aumenta confianza o cambia valor
                if value == existing.value:
                    existing.confidence = min(1.0, existing.confidence + 0.1)
                else:
                    # Nuevo valor inferido, menor confianza inicial
                    existing.value = value
                    existing.confidence = 0.6

            existing.updated_at = datetime.now()
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

    def observe(self, observation_type: str, data: dict):
        """
        Registra observacion para inferencia.

        Args:
            observation_type: Tipo de observacion
            data: Datos de la observacion
        """
        self.observation_buffer.append(
            {"type": observation_type, "data": data, "timestamp": datetime.now().isoformat()}
        )

        self.profile.interaction_count += 1

        # Procesar inferencias cada N observaciones
        if len(self.observation_buffer) >= 5:
            self._process_observations()

    def _process_observations(self):
        """Procesa buffer de observaciones para inferir preferencias."""
        for obs in self.observation_buffer:
            obs_type = obs["type"]
            data = obs["data"]

            if obs_type == "code_written":
                self._infer_from_code(data)
            elif obs_type == "feedback":
                self._infer_from_feedback(data)
            elif obs_type == "commit":
                self._infer_from_commit(data)

        self.observation_buffer.clear()
        self._save_profile()

    def _infer_from_code(self, data: dict):
        """Infiere preferencias del codigo escrito."""
        code = data.get("code", "")
        data.get("file_path", "")

        # Detectar quotes
        single = code.count("'")
        double = code.count('"')
        if single > double * 2:
            self.set(
                "code.style.quotes",
                "single",
                PreferenceSource.INFERRED,
                f"Code uses {single} single vs {double} double quotes",
            )
        elif double > single * 2:
            self.set(
                "code.style.quotes",
                "double",
                PreferenceSource.INFERRED,
                f"Code uses {double} double vs {single} single quotes",
            )

        # Detectar indentacion
        lines = code.split("\n")
        spaces = sum(1 for l in lines if l.startswith("    "))
        tabs = sum(1 for l in lines if l.startswith("\t"))
        if spaces > tabs * 2:
            self.set(
                "code.style.indent",
                "spaces",
                PreferenceSource.INFERRED,
                f"Code uses {spaces} space indents",
            )
        elif tabs > spaces * 2:
            self.set(
                "code.style.indent",
                "tabs",
                PreferenceSource.INFERRED,
                f"Code uses {tabs} tab indents",
            )

    def _infer_from_feedback(self, data: dict):
        """Infiere preferencias del feedback."""
        text = data.get("text", "").lower()

        # Detectar preferencia de verbosidad
        if "mas detalle" in text or "explica" in text:
            self.set(
                "communication.verbosity",
                "detailed",
                PreferenceSource.INFERRED,
                f"User requested: {text[:50]}",
            )
        elif "mas corto" in text or "resumen" in text:
            self.set(
                "communication.verbosity",
                "concise",
                PreferenceSource.INFERRED,
                f"User requested: {text[:50]}",
            )

        # Detectar idioma
        spanish_markers = ["quiero", "necesito", "por favor", "gracias"]
        english_markers = ["want", "need", "please", "thanks"]

        spanish_count = sum(1 for m in spanish_markers if m in text)
        english_count = sum(1 for m in english_markers if m in text)

        if spanish_count > english_count:
            self.set(
                "communication.language",
                "spanish",
                PreferenceSource.INFERRED,
                "Detected Spanish in feedback",
            )
        elif english_count > spanish_count:
            self.set(
                "communication.language",
                "english",
                PreferenceSource.INFERRED,
                "Detected English in feedback",
            )

    def _infer_from_commit(self, data: dict):
        """Infiere preferencias del commit."""
        message = data.get("message", "")

        # Detectar estilo de commit
        if re.match(r"^(feat|fix|docs|style|refactor|test|chore)", message):
            self.set(
                "git.commit.style",
                "conventional",
                PreferenceSource.INFERRED,
                f"Commit follows conventional: {message[:30]}",
            )

        # Detectar idioma de commits
        spanish_words = ["agregado", "corregido", "actualizado", "añadido"]
        english_words = ["added", "fixed", "updated", "removed"]

        message_lower = message.lower()
        spanish = sum(1 for w in spanish_words if w in message_lower)
        english = sum(1 for w in english_words if w in message_lower)

        if spanish > english:
            self.set(
                "git.commit.language",
                "spanish",
                PreferenceSource.INFERRED,
                f"Commit in Spanish: {message[:30]}",
            )
        elif english > spanish:
            self.set(
                "git.commit.language",
                "english",
                PreferenceSource.INFERRED,
                f"Commit in English: {message[:30]}",
            )

    def should_apply(self, key: str, min_confidence: float = 0.7) -> bool:
        """
        Verifica si se debe aplicar una preferencia.

        Args:
            key: Clave de la preferencia
            min_confidence: Confianza minima requerida

        Returns:
            True si debe aplicarse
        """
        pref = self.profile.preferences.get(key)
        if not pref:
            return False
        return pref.confidence >= min_confidence

    def get_applicable_preferences(
        self, context: str | None = None, min_confidence: float = 0.7
    ) -> dict[str, Any]:
        """
        Obtiene preferencias aplicables.

        Args:
            context: Contexto opcional (e.g., "code", "git")
            min_confidence: Confianza minima

        Returns:
            Dict de preferencias aplicables
        """
        applicable = {}

        for key, pref in self.profile.preferences.items():
            if pref.confidence < min_confidence:
                continue

            if context:
                if not key.startswith(context):
                    continue

            applicable[key] = pref.value

        return applicable

    def decay_confidence(self, decay_factor: float = 0.99):
        """
        Aplica decay temporal a confianzas.

        Preferencias no usadas/actualizadas pierden confianza.
        """
        now = datetime.now()

        for pref in self.profile.preferences.values():
            if pref.source == PreferenceSource.INFERRED:
                days_old = (now - pref.updated_at).days
                if days_old > 7:
                    pref.confidence = max(0.3, pref.confidence * decay_factor)

        self._save_profile()

    def export_profile(self) -> dict:
        """Exporta perfil como dict."""
        return {
            "user_id": self.profile.user_id,
            "interaction_count": self.profile.interaction_count,
            "preferences": {
                key: {
                    "value": pref.value,
                    "confidence": pref.confidence,
                    "confidence_level": pref.confidence_level.value,
                    "source": pref.source.value,
                }
                for key, pref in self.profile.preferences.items()
            },
        }


# Singleton
_user_preference_model: UserPreferenceModel | None = None


def get_user_preference_model() -> UserPreferenceModel:
    """Obtiene instancia singleton."""
    global _user_preference_model
    if _user_preference_model is None:
        _user_preference_model = UserPreferenceModel()
    return _user_preference_model
