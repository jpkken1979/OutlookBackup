"""Model Advisor: recomienda el modelo Claude (haiku/sonnet/opus) por tarea.

Combina la complejidad de la tarea con un clasificador de riesgo de calidad.
Regla de oro: modelo = max(piso_riesgo, recomendacion_complejidad).
La complejidad solo puede subir el modelo; nunca bajarlo del piso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MODEL_ORDER: list[str] = ["haiku", "sonnet", "opus"]

_COMPLEXITY_TO_MODEL: dict[str, str] = {
    "trivial": "haiku",
    "simple": "haiku",
    "moderate": "sonnet",
    "complex": "opus",
    "epic": "opus",
}


@dataclass
class TaskInput:
    """Entrada para una recomendacion de modelo.

    Args:
        text: Descripcion de la tarea.
        file_paths: Archivos que la tarea tocaria (mejora la deteccion de riesgo).
        agent_tier: Tier del agente asignado (1-6), si se conoce.
    """

    text: str
    file_paths: list[str] | None = None
    agent_tier: int | None = None


@dataclass
class ModelRecommendation:
    """Resultado de la recomendacion.

    Args:
        recommended_model: haiku | sonnet | opus.
        complexity_level: Nivel de complejidad calculado.
        risk_floor: Piso de modelo impuesto por el clasificador de riesgo.
        decision_source: Senal que gano: risk_floor | complexity | tier | override.
        confidence: 0.0-1.0.
        reasoning: Explicacion auditable en espanol.
        fallback_chain: Degradacion si el provider no tiene el modelo.
    """

    recommended_model: str
    complexity_level: str
    risk_floor: str
    decision_source: str
    confidence: float
    reasoning: str
    fallback_chain: list[str] = field(default_factory=list)


def max_model(a: str, b: str) -> str:
    """Devuelve el modelo mas fuerte segun MODEL_ORDER."""
    return a if MODEL_ORDER.index(a) >= MODEL_ORDER.index(b) else b


def map_complexity(level: str) -> str:
    """Mapea un ComplexityLevel (string) al modelo sugerido por complejidad."""
    return _COMPLEXITY_TO_MODEL.get(level.lower(), "sonnet")


def fallback_chain_for(model: str) -> list[str]:
    """Cadena de degradacion desde el modelo recomendado hacia los mas debiles."""
    idx = MODEL_ORDER.index(model)
    return list(reversed(MODEL_ORDER[: idx + 1]))


# Archivos criticos (config-guard.md): tocarlos siempre fuerza opus.
_CRITICAL_PATH_MARKERS: tuple[str, ...] = (
    ".claude/settings.json",
    ".mcp.json",
    ".env",
    "memory.rs",
    ".codex/accounts",
)

# Señales de codigo: si aparecen, "no-codigo" deja de aplicar.
_CODE_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "variable",
    "funcion",
    "función",
    "function",
    "clase",
    "class",
    "metodo",
    "método",
    "method",
    "endpoint",
    "codigo",
    "código",
    "code",
    "modulo",
    "módulo",
    "module",
    "componente",
    "component",
    "refactor",
    "bug",
    "test",
    "import",
    "query",
    "sql",
    "regex",
    "parser",
    "handler",
)
_CODE_FILE_EXTS: tuple[str, ...] = (
    ".py",
    ".ts",
    ".tsx",
    ".rs",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".sql",
)
# Extension de codigo mencionada dentro del texto de la tarea (ej. "editar foo.py").
_CODE_EXT_IN_TEXT = re.compile(r"\.(?:py|ts|tsx|rs|js|jsx|go|java|sql)\b")

# Riesgo alto -> piso opus.
_SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "auth",
    "oauth",
    "jwt",
    "token",
    "secret",
    "password",
    "credential",
    "credencial",
    "crypto",
    "seguridad",
    "security",
    "race",
    "concurrencia",
    "concurrency",
    "concurrente",
    "async",
    "mutex",
    "deadlock",
    "lock",
    "migracion",
    "migración",
    "migration",
    "schema",
    "integridad",
    "integrity",
    "nomina",
    "nómina",
    "payroll",
    "salario",
    "chingin",
    "kyuryo",
    "dinero",
    "money",
    "fiscal",
    "ipc",
    "subprocess",
    "shell",
    "traversal",
    "validacion de path",
)
# Nota: se quito el "design" suelto (ingles) por ser muy colisionable con nombres
# de skills/archivos (designer, design-system); el peso lo cargan "arquitectura",
# "architecture" y los verbos "disenar"/"disenar".
_ARCHITECTURE_KEYWORDS: tuple[str, ...] = (
    "arquitectura",
    "architecture",
    "disenar",
    "diseñar",
    "decidir",
    "cross-cutting",
    "breaking change",
    "rediseno",
    "rediseño",
)
_MULTI_FILE_MARKERS: tuple[str, ...] = (
    "multiples",
    "múltiples",
    "varios",
    "multi-archivo",
    "multi archivo",
    "cross-cutting",
)
_STANDARD_CODE_KEYWORDS: tuple[str, ...] = (
    "implementar",
    "implement",
    "feature",
    "endpoint",
    "crud",
    "componente",
    "component",
    "test",
    "fix",
    "corregir",
    "agregar funcion",
)
_MECHANICAL_KEYWORDS: tuple[str, ...] = (
    "renombrar",
    "rename",
    "formatear",
    "format",
    "ordenar import",
    "bump",
    "version",
    "versión",
)
_NON_CODE_KEYWORDS: tuple[str, ...] = (
    "docs",
    "documentar",
    "documentation",
    "readme",
    "comentario",
    "comment",
    "typo",
    "listar",
    "list",
    "resumir",
    "summarize",
    "investigar",
    "research",
    "traducir",
    "translate",
)


def _matches(text: str, keywords: tuple[str, ...]) -> str | None:
    """Primer keyword presente en text (lowercase) con limites de palabra, o None.

    Usa word-boundary (`\\b`) para evitar falsos positivos por substring
    (ej. "ipc" dentro de "descripcion", "design" dentro de "designer").
    """
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            return kw
    return None


def has_code_signal(text: str, file_paths: list[str] | None) -> bool:
    """True si la tarea evidencia que se toca codigo (keyword o archivo .code).

    Args:
        text: Descripcion de la tarea.
        file_paths: Archivos que la tarea tocaria (opcional).

    Returns:
        True si hay evidencia de que se toca codigo.
    """
    low = text.lower()
    if _matches(low, _CODE_SIGNAL_KEYWORDS):
        return True
    if _CODE_EXT_IN_TEXT.search(low):
        return True
    return any(path.lower().endswith(_CODE_FILE_EXTS) for path in file_paths or [])


def classify_risk(text: str, file_paths: list[str] | None = None) -> tuple[str, str]:
    """Determina el piso de modelo por riesgo de calidad (modo conservador).

    Args:
        text: Descripcion de la tarea.
        file_paths: Archivos que tocaria (opcional).

    Returns:
        Tupla (floor_model, trigger_reason). floor_model in MODEL_ORDER.
    """
    low = text.lower()

    for path in file_paths or []:
        plow = path.lower()
        if any(marker in plow for marker in _CRITICAL_PATH_MARKERS):
            return "opus", f"archivo critico ({path})"

    # Archivo critico mencionado en el texto (modo anotar no recibe file_paths).
    text_marker = next((m for m in _CRITICAL_PATH_MARKERS if m in low), None)
    if text_marker:
        return "opus", f"archivo critico mencionado ({text_marker})"

    hit = _matches(low, _SENSITIVE_KEYWORDS)
    if hit:
        return "opus", f"piso seguridad ({hit})"

    arch = _matches(low, _ARCHITECTURE_KEYWORDS)
    if arch:
        return "opus", f"arquitectura ({arch})"
    if "refactor" in low and _matches(low, _MULTI_FILE_MARKERS):
        return "opus", "refactor multi-archivo"

    if has_code_signal(text, file_paths):
        std = _matches(low, _STANDARD_CODE_KEYWORDS)
        if std:
            return "sonnet", f"codigo estandar ({std})"
        mech = _matches(low, _MECHANICAL_KEYWORDS)
        if mech:
            return "sonnet", f"mecanico sobre codigo ({mech})"
        return "sonnet", "codigo sin categoria clara -> piso conservador"

    non = _matches(low, _NON_CODE_KEYWORDS)
    if non:
        return "haiku", f"no-codigo ({non})"

    return "sonnet", "ambiguo -> piso conservador"


# Tier de agente -> piso de modelo (solo sube, nunca baja).
_TIER_FLOOR: dict[int, str] = {1: "opus", 2: "sonnet", 3: "sonnet"}


def _complexity_level(text: str) -> str | None:
    """Nivel de complejidad via ComplexityAnalyzer. None si no se puede importar.

    Args:
        text: Descripcion de la tarea.

    Returns:
        Nivel de complejidad como string, o None si el router no esta disponible.
    """
    try:
        from core.intelligent_router import ComplexityAnalyzer
    except Exception:
        return None
    try:
        result = ComplexityAnalyzer.analyze(text)
        level = result.get("complexity_level")
        return str(getattr(level, "value", level))
    except Exception:
        return None


def recommend(task: TaskInput) -> ModelRecommendation:
    """Recomienda el modelo para una tarea aplicando el piso de calidad.

    Args:
        task: Entrada con texto, paths opcionales y tier opcional.

    Returns:
        ModelRecommendation con modelo, razon auditable y cadena de fallback.
    """
    floor, floor_reason = classify_risk(task.text, task.file_paths)

    level = _complexity_level(task.text)
    if level is None:
        chosen, source = floor, "risk_floor"
        reasoning = f"Sin router de complejidad; piso por {floor_reason}."
        confidence = 0.6
    else:
        comp_model = map_complexity(level)
        chosen = max_model(floor, comp_model)
        if chosen == comp_model and comp_model != floor:
            source = "complexity"
            reasoning = f"Complejidad {level} sube a {chosen} (piso {floor} por {floor_reason})."
        else:
            source = "risk_floor"
            reasoning = f"Piso por {floor_reason} (complejidad {level})."
        confidence = 0.9 if floor == "opus" else 0.75

    if task.agent_tier in _TIER_FLOOR:
        tier_model = _TIER_FLOOR[task.agent_tier]
        bumped = max_model(chosen, tier_model)
        if bumped != chosen:
            chosen, source = bumped, "tier"
            reasoning += f" Tier {task.agent_tier} eleva a {chosen}."

    return ModelRecommendation(
        recommended_model=chosen,
        complexity_level=level or "desconocido",
        risk_floor=floor,
        decision_source=source,
        confidence=confidence,
        reasoning=reasoning,
        fallback_chain=fallback_chain_for(chosen),
    )
