"""Versioned, editable global AI rules for Nexus clients."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import threading
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final = "global-ai-rules-v1"
_RULE_ID_RE: Final = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_VALID_SCOPES: Final = frozenset({"universal", "workspace"})
_WRITE_LOCK = threading.RLock()

DEFAULT_GLOBAL_RULES: Final[tuple[dict[str, object], ...]] = (
    {
        "id": "mcp_first",
        "title": "Descubre antes de inventar",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Busca primero la capacidad en Nexus/MCP y reutiliza agentes, skills, "
            "memoria o conectores existentes antes de crear otra implementación."
        ),
    },
    {
        "id": "read_context",
        "title": "Lee el contexto y respeta el alcance",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Antes de cambiar algo, lee las reglas, el estado y la documentación "
            "más cercana del proyecto; trabaja solo dentro del alcance autorizado."
        ),
    },
    {
        "id": "plan_complex_work",
        "title": "Planifica el trabajo complejo",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Para tareas de varios pasos, define criterios verificables, riesgos y "
            "orden de ejecución; mantén el plan actualizado mientras avanzas."
        ),
    },
    {
        "id": "preserve_user_content",
        "title": "Conserva el trabajo del usuario",
        "enabled": True,
        "scope": "universal",
        "text": (
            "No sobrescribas, borres ni reformatees contenido ajeno al cambio. "
            "Las inyecciones solo pueden modificar bloques Nexus administrados."
        ),
    },
    {
        "id": "root_cause_quality",
        "title": "Corrige la causa raíz",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Reproduce el problema, añade una comprobación que falle cuando sea "
            "posible y corrige la causa raíz en lugar de ocultar el síntoma."
        ),
    },
    {
        "id": "least_privilege_secrets",
        "title": "Protege secretos y privilegios",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Usa el menor privilegio posible. Nunca escribas credenciales en código, "
            "reglas, logs o manifests; guarda solo referencias a un almacén seguro."
        ),
    },
    {
        "id": "verify_proportionally",
        "title": "Verifica de menor a mayor",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Ejecuta primero la prueba más estrecha y después amplía la verificación "
            "según el riesgo. No declares éxito sin evidencia reproducible."
        ),
    },
    {
        "id": "record_decisions",
        "title": "Deja memoria útil",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Registra decisiones, límites, errores conocidos y trabajo pendiente en "
            "las fuentes de verdad del proyecto sin duplicar ni inventar estado."
        ),
    },
    {
        "id": "commit_verified_changes",
        "title": "Haz commits pequeños y verificados",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Al cerrar cada sesión con cambios propios, crea un commit local "
            "descriptivo solo si los cambios están revisados y pasan sus "
            "verificaciones; no hagas push, merge ni release sin autorización."
        ),
    },
    {
        "id": "finish_safely",
        "title": "Finaliza sin exponer ni interrumpir",
        "enabled": True,
        "scope": "universal",
        "text": (
            "Al terminar, resume evidencia y pendientes. Haz push únicamente con "
            "autorización, a un destino privado confirmado y después de comprobar "
            "que el historial no contiene secretos; nunca fuerces ni borres trabajo."
        ),
    },
)


class GlobalRulesError(RuntimeError):
    """Base error for the global rules store."""


class GlobalRulesValidationError(GlobalRulesError):
    """Raised when a rules document violates the v1 schema."""


class GlobalRulesConflictError(GlobalRulesError):
    """Raised when optimistic concurrency detects a stale editor."""

    def __init__(self, *, expected_version: int, current_version: int):
        super().__init__(
            f"stale global rules version: expected {expected_version}, current {current_version}"
        )
        self.expected_version = expected_version
        self.current_version = current_version


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_global_rules_document() -> dict[str, object]:
    """Return a fresh document containing the ten safe universal defaults."""

    return {
        "schema_version": SCHEMA_VERSION,
        "version": 1,
        "updated_at": _utc_now(),
        "rules": copy.deepcopy(list(DEFAULT_GLOBAL_RULES)),
    }


def _validate_text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GlobalRulesValidationError(f"{field} must be a non-empty string")
    if len(value) > maximum:
        raise GlobalRulesValidationError(f"{field} exceeds {maximum} characters")
    return value


def _validate_global_rule(raw_rule: object, index: int, seen: set[str]) -> dict[str, object]:
    """Valida y normaliza una unica regla del documento.

    Args:
        raw_rule: Entrada cruda de `document["rules"][index]`.
        index: Posicion de la regla, usada en los mensajes de error.
        seen: Set de ids ya vistos; se le agrega el id de esta regla si es valido.

    Returns:
        La regla normalizada (id, title, enabled, scope, text).
    """
    if not isinstance(raw_rule, Mapping):
        raise GlobalRulesValidationError(f"rules[{index}] must be an object")
    rule_id = _validate_text(
        raw_rule.get("id"),
        field=f"rules[{index}].id",
        maximum=64,
    )
    if not _RULE_ID_RE.fullmatch(rule_id):
        raise GlobalRulesValidationError(f"rules[{index}].id is invalid")
    if rule_id in seen:
        raise GlobalRulesValidationError(f"duplicate rule id: {rule_id}")
    seen.add(rule_id)

    enabled = raw_rule.get("enabled")
    if not isinstance(enabled, bool):
        raise GlobalRulesValidationError(f"rules[{index}].enabled must be boolean")
    scope = raw_rule.get("scope")
    if scope not in _VALID_SCOPES:
        raise GlobalRulesValidationError(f"rules[{index}].scope must be universal or workspace")
    return {
        "id": rule_id,
        "title": _validate_text(
            raw_rule.get("title"),
            field=f"rules[{index}].title",
            maximum=120,
        ),
        "enabled": enabled,
        "scope": scope,
        "text": _validate_text(
            raw_rule.get("text"),
            field=f"rules[{index}].text",
            maximum=2000,
        ),
    }


def validate_global_rules_document(document: object) -> dict[str, object]:
    """Validate and copy a complete global rules document."""

    if not isinstance(document, Mapping):
        raise GlobalRulesValidationError("global rules document must be an object")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise GlobalRulesValidationError(f"schema_version must be {SCHEMA_VERSION!r}")
    version = document.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise GlobalRulesValidationError("version must be a positive integer")
    _validate_text(document.get("updated_at"), field="updated_at", maximum=64)

    raw_rules = document.get("rules")
    if not isinstance(raw_rules, list) or not 1 <= len(raw_rules) <= 50:
        raise GlobalRulesValidationError("rules must contain between 1 and 50 items")

    seen: set[str] = set()
    normalized_rules = [
        _validate_global_rule(raw_rule, index, seen) for index, raw_rule in enumerate(raw_rules)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "updated_at": document["updated_at"],
        "rules": normalized_rules,
    }


def _atomic_write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode(
        "utf-8"
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_global_rules(
    path: Path,
    *,
    create_if_missing: bool = False,
) -> dict[str, object]:
    """Load the versioned document, optionally seeding a missing store."""

    with _WRITE_LOCK:
        if not path.exists():
            if not create_if_missing:
                raise FileNotFoundError(path)
            seeded = default_global_rules_document()
            _atomic_write_json(path, seeded)
            return seeded
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GlobalRulesValidationError(f"cannot read global rules document: {exc}") from exc
        return validate_global_rules_document(raw)


def update_global_rules(
    path: Path,
    *,
    rules: object,
    expected_version: int,
) -> dict[str, object]:
    """Replace the editable rule list with optimistic concurrency and atomically save."""

    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise GlobalRulesValidationError("expected_version must be an integer")
    if not isinstance(rules, list):
        raise GlobalRulesValidationError("rules must be an array")

    with _WRITE_LOCK:
        current = load_global_rules(path, create_if_missing=True)
        current_version_value = current.get("version")
        if isinstance(current_version_value, bool) or not isinstance(current_version_value, int):
            raise GlobalRulesValidationError("stored version must be an integer")
        current_version = current_version_value
        if expected_version != current_version:
            raise GlobalRulesConflictError(
                expected_version=expected_version,
                current_version=current_version,
            )
        candidate = validate_global_rules_document(
            {
                "schema_version": SCHEMA_VERSION,
                "version": current_version + 1,
                "updated_at": _utc_now(),
                "rules": rules,
            }
        )
        _atomic_write_json(path, candidate)
        return candidate


def resolve_effective_rules(
    global_document: Mapping[str, object],
    workspace_overrides: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Apply narrow workspace overrides without mutating the global document."""

    validated = validate_global_rules_document(global_document)
    validated_rules = validated.get("rules")
    if not isinstance(validated_rules, list):
        raise GlobalRulesValidationError("validated rules must be an array")
    ordered: list[dict[str, object]] = []
    for rule in validated_rules:
        if not isinstance(rule, dict):
            raise GlobalRulesValidationError("validated rule must be an object")
        ordered.append(copy.deepcopy(rule))
    by_id = {str(rule["id"]): rule for rule in ordered}
    for override in workspace_overrides or ():
        rule_id = override.get("id")
        if not isinstance(rule_id, str) or rule_id not in by_id:
            raise GlobalRulesValidationError(
                f"workspace override references unknown rule: {rule_id!r}"
            )
        target = by_id[rule_id]
        if "enabled" in override:
            if not isinstance(override["enabled"], bool):
                raise GlobalRulesValidationError(
                    f"workspace override {rule_id}.enabled must be boolean"
                )
            target["enabled"] = override["enabled"]
        for field, maximum in (("title", 120), ("text", 2000)):
            if field in override:
                target[field] = _validate_text(
                    override[field],
                    field=f"workspace override {rule_id}.{field}",
                    maximum=maximum,
                )
    return ordered
