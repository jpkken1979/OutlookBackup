# mypy: ignore-errors
"""
Validador de contexto /shu.

Verifica que las respuestas a las 6 preguntas del comando /shu
sean suficientes antes de proceder con la ejecución autónoma.

Campos evaluados:
  - goal         → OBLIGATORIO (bloquea ejecución si está vacío)
  - scope        → RECOMENDADO (warning si vacío)
  - restrictions → RECOMENDADO (warning si vacío)
  - validation   → OBLIGATORIO para commits/tests (bloquea si vacío)
  - priority     → RECOMENDADO (warning si vacío)
  - historical   → RECOMENDADO (warning si vacío)

Usage:
    validator = ContextValidator(responses)
    is_valid, missing, warnings = validator.validate()
    if validator.blocks_execution():
        print("Contexto insuficiente — completar antes de ejecutar")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.shu_context_validator")

# ─────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────

# Mínimo de caracteres para considerar que un campo tiene contenido real
MIN_FIELD_LENGTH = 5

# Palabras que indican respuesta vacía/irrelevante
EMPTY_MARKERS = {
    "n/a",
    "na",
    "ninguna",
    "ninguno",
    "no",
    "nada",
    "-",
    "—",
    "desconocido",
    "unknown",
    "none",
    "null",
    "sin restricciones",
    "no aplica",
    "sin contexto",
}

# Log de validaciones (relativo a REPO_ROOT)
VALIDATION_LOG_PATH = Path(".omc") / "shu_validations.jsonl"


# ─────────────────────────────────────────────────────────
# Resultado de validación
# ─────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Resultado completo de una validación de contexto /shu."""

    is_valid: bool
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "blocking_reason": self.blocking_reason,
        }


# ─────────────────────────────────────────────────────────
# Validador principal
# ─────────────────────────────────────────────────────────


class ContextValidator:
    """
    Valida el contexto /shu antes de generar un plan de ejecución.

    Args:
        responses: Diccionario con las respuestas a las 6 preguntas del /shu.
                   Claves esperadas: goal, scope, restrictions, validation,
                   priority, historical.
        repo_root: Raíz del repo para escribir el log de validaciones.
                   Si es None, no se persiste el log.
    """

    REQUIRED_FIELDS: list[str] = ["goal", "validation"]
    RECOMMENDED_FIELDS: list[str] = ["scope", "restrictions", "priority", "historical"]

    # Términos que indican que el paso incluye commits o tests
    COMMIT_TERMS: frozenset[str] = frozenset(
        [
            "commit",
            "commitear",
            "push",
            "merge",
            "pr",
            "test",
            "tests",
            "pytest",
            "vitest",
            "ci",
        ]
    )

    def __init__(
        self,
        responses: dict[str, str],
        repo_root: Path | None = None,
    ) -> None:
        self._responses = {k: (v or "").strip() for k, v in responses.items()}
        self._repo_root = repo_root
        self._result: ValidationResult | None = None

    # ─────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────

    def _is_empty(self, value: str) -> bool:
        """Retorna True si el valor se considera vacío o inútil."""
        if not value or len(value) < MIN_FIELD_LENGTH:
            return True
        return value.lower().strip() in EMPTY_MARKERS

    def _goal_requires_validation_field(self) -> bool:
        """
        Retorna True si el objetivo menciona commits, tests u otras
        operaciones que requieren criterios de validación explícitos.
        """
        goal_lower = self._responses.get("goal", "").lower()
        return any(term in goal_lower for term in self.COMMIT_TERMS)

    # ─────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, list[str], list[str]]:
        """
        Valida el contexto /shu.

        Returns:
            Tupla (is_valid, missing_fields, warnings) donde:
              - is_valid: False si algún campo OBLIGATORIO está vacío.
              - missing_fields: lista de campos obligatorios faltantes.
              - warnings: lista de advertencias sobre campos recomendados.
        """
        missing: list[str] = []
        warnings: list[str] = []
        blocking_reason = ""

        # ── Campos OBLIGATORIOS ──────────────────────────
        goal_value = self._responses.get("goal", "")
        if self._is_empty(goal_value):
            missing.append("goal")
            blocking_reason = (
                "El campo 'goal' es obligatorio: describe el objetivo principal de la tarea."
            )

        # 'validation' es obligatorio cuando el goal menciona commits/tests,
        # o cuando no hay goal (contexto totalmente vacío).
        validation_value = self._responses.get("validation", "")
        validation_empty = self._is_empty(validation_value)

        if validation_empty and (self._goal_requires_validation_field() or not goal_value):
            missing.append("validation")
            if not blocking_reason:
                blocking_reason = (
                    "El campo 'validation' es obligatorio cuando el objetivo incluye "
                    "commits, tests u operaciones críticas: describe cómo verificar el resultado."
                )

        # ── Campos RECOMENDADOS ──────────────────────────
        for field_name in self.RECOMMENDED_FIELDS:
            if self._is_empty(self._responses.get(field_name, "")):
                warnings.append(
                    f"Campo '{field_name}' no provisto — se recomienda completarlo para "
                    "mejorar la precisión del plan."
                )

        is_valid = len(missing) == 0
        self._result = ValidationResult(
            is_valid=is_valid,
            missing_fields=missing,
            warnings=warnings,
            blocking_reason=blocking_reason,
        )

        self._log_validation()

        logger.info(
            "Validacion /shu: valid=%s, missing=%s, warnings=%d",
            is_valid,
            missing,
            len(warnings),
        )

        return is_valid, missing, warnings

    def blocks_execution(self) -> bool:
        """
        Retorna True si el contexto es insuficiente para proceder con la ejecución.

        Llama validate() internamente si aún no se ejecutó.
        """
        if self._result is None:
            self.validate()
        return not self._result.is_valid  # type: ignore[union-attr]

    def format_blocking_message(self) -> str:
        """
        Genera un mensaje legible para mostrar al usuario cuando la ejecución está bloqueada.
        """
        if self._result is None:
            self.validate()

        result = self._result  # type: ignore[union-attr]
        if result.is_valid:
            return ""

        lines = [
            "[SHU VALIDATOR] Contexto insuficiente — ejecucion bloqueada.",
            f"  Razon: {result.blocking_reason}",
        ]
        if result.missing_fields:
            lines.append(f"  Campos obligatorios faltantes: {', '.join(result.missing_fields)}")
        if result.warnings:
            lines.append("  Advertencias:")
            for w in result.warnings:
                lines.append(f"    - {w}")
        lines.append("\n  Completa los campos faltantes en /shu y vuelve a intentarlo.")
        return "\n".join(lines)

    def format_warnings_message(self) -> str:
        """
        Genera un mensaje con las advertencias (campos recomendados vacíos),
        para mostrar aunque la ejecución no esté bloqueada.
        """
        if self._result is None:
            self.validate()

        result = self._result  # type: ignore[union-attr]
        if not result.warnings:
            return ""

        lines = ["[SHU VALIDATOR] Advertencias de contexto:"]
        for w in result.warnings:
            lines.append(f"  - {w}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────
    # Persistencia del log
    # ─────────────────────────────────────────────────────

    def _log_validation(self) -> None:
        """Persiste el resultado de validación en .omc/shu_validations.jsonl."""
        if self._result is None or self._repo_root is None:
            return

        log_path = self._repo_root / VALIDATION_LOG_PATH
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "goal": self._responses.get("goal", ""),
                **self._result.to_dict(),
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("No se pudo escribir shu_validations.jsonl: %s", exc)
