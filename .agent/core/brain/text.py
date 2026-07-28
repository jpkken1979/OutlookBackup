"""Parsing de secciones y scoring textual/semantico del Brain.

Helpers puros (sin estado) para extraer secciones de un body markdown, extraer
keywords, expandirlas con sinonimos del dominio dev/business y puntuar matches
con fuzzy matching.

Extraido del monolito ``brain.py`` (refactor 2026-05-31). Sin cambios de
comportamiento.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _ascii_slug_words(text: str) -> list[str]:
    """Extrae palabras ASCII de un texto para armar slugs, transliterando diacriticos.

    NFKD + encode-ascii preserva letras acentuadas como su base
    ("sesión" -> "sesion") en vez de descartarlas. Guiones y underscores
    actuan como separadores de palabra (filenames kebab-case). Texto sin
    caracteres latinos (ej. 100% japones) devuelve lista vacia.

    Args:
        text: Texto de origen (titulo de nodo o hint).

    Returns:
        Lista de palabras ASCII en minusculas, sin puntuacion.
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[-_]", " ", ascii_text)
    return re.sub(r"[^a-zA-Z0-9\s]", "", ascii_text.lower()).split()


def _parse_sections(body: str) -> dict[str, str]:
    """Parsea el body markdown en secciones por ## header."""
    sections: dict[str, str] = {}
    current_section = ""
    current_content: list[str] = []

    for line in body.split("\n"):
        header_match = re.match(r"^## (.+)", line)
        if header_match:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = header_match.group(1).strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _extract_keywords(text: str) -> list[str]:
    """Extrae keywords de una query eliminando stopwords basicos."""
    stopwords = {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "de",
        "del",
        "en",
        "que",
        "es",
        "por",
        "con",
        "para",
        "como",
        "se",
        "al",
        "lo",
        "su",
        "si",
        "the",
        "a",
        "an",
        "is",
        "of",
        "in",
        "to",
        "for",
        "and",
        "or",
        "it",
        "what",
        "how",
        "when",
        "where",
        "which",
        "who",
        "do",
        "does",
    }
    words = re.findall(r"\w+", text.lower())
    return [w for w in words if w not in stopwords and len(w) > 1]


def _score_match(text: str, keywords: list[str]) -> int:
    """Puntua un texto contra una lista de keywords."""
    score = 0
    for kw in keywords:
        if kw in text:
            score += 2
        # Partial match
        elif any(kw in word for word in text.split()):
            score += 1
    return score


# ---------------------------------------------------------------------------
# Semantic expansion — sinonimos del dominio dev/business
# ---------------------------------------------------------------------------

_SYNONYM_MAP: dict[str, list[str]] = {
    "auth": ["authentication", "login", "jwt", "oauth", "session", "token", "credentials"],
    "authentication": ["auth", "login", "jwt", "oauth", "session"],
    "login": ["auth", "authentication", "signin", "credentials"],
    "jwt": ["auth", "token", "bearer", "authentication"],
    "deploy": ["deployment", "release", "ci", "cd", "pipeline", "ship"],
    "deployment": ["deploy", "release", "ci", "pipeline"],
    "database": ["db", "sql", "postgres", "sqlite", "mysql", "migration", "schema"],
    "db": ["database", "sql", "postgres", "sqlite"],
    "api": ["endpoint", "rest", "graphql", "service", "route", "handler"],
    "endpoint": ["api", "route", "handler", "service"],
    "test": ["testing", "spec", "vitest", "pytest", "jest", "assertion"],
    "testing": ["test", "spec", "coverage", "assertion"],
    "error": ["bug", "fix", "issue", "problem", "failure", "crash"],
    "bug": ["error", "fix", "issue", "defect"],
    "security": ["auth", "encryption", "cors", "xss", "csrf", "vulnerability"],
    "memory": ["brain", "recall", "store", "cache", "persistence"],
    "brain": ["memory", "knowledge", "intelligence", "recall"],
    "config": ["configuration", "settings", "env", "environment"],
    "ui": ["frontend", "component", "react", "interface", "design", "ux"],
    "frontend": ["ui", "component", "react", "interface", "client"],
    "backend": ["server", "api", "service", "python", "rust"],
    "performance": ["speed", "optimization", "latency", "cache", "fast"],
    "nomina": ["payroll", "daicho", "salary", "dispatch"],
    "daicho": ["nomina", "payroll", "台帳", "ledger"],
    "dispatch": ["派遣", "haken", "assignment", "worker"],
}


def _expand_keywords(keywords: list[str]) -> list[str]:
    """Expande keywords con sinonimos del dominio.

    Args:
        keywords: Lista de keywords originales.

    Returns:
        Lista expandida (originales + sinonimos, sin duplicados).
    """
    expanded = list(keywords)
    for kw in keywords:
        synonyms = _SYNONYM_MAP.get(kw, [])
        for syn in synonyms[:3]:  # Max 3 sinonimos por keyword
            if syn not in expanded:
                expanded.append(syn)
    return expanded


def _fuzzy_match(word: str, target: str) -> bool:
    """Match fuzzy basico: prefijo comun de 3+ chars o edit distance 1.

    Args:
        word: Palabra a buscar.
        target: Texto objetivo.

    Returns:
        True si hay match fuzzy.
    """
    if len(word) < 3 or len(target) < 3:
        return False
    # Prefijo comun
    if word[:3] == target[:3] and abs(len(word) - len(target)) <= 2:
        return True
    # Contencion
    if word in target or target in word:
        return True
    return False


def _smart_score(text: str, expanded_keywords: list[str]) -> float:
    """Scoring inteligente con keywords expandidos y fuzzy matching.

    Args:
        text: Texto donde buscar (ya en lowercase).
        expanded_keywords: Keywords expandidos con sinonimos.

    Returns:
        Score float (0 = no match).
    """
    score = 0.0
    text_words = text.split()

    for kw in expanded_keywords:
        if kw in text:
            score += 2.0  # Match exacto
        elif any(_fuzzy_match(kw, tw) for tw in text_words):
            score += 0.8  # Fuzzy match
    return score


def _type_to_section(node_type: str) -> str:
    """Convierte un tipo de nodo al header de seccion del indice."""
    mapping = {
        "session": "Sessions",
        "concept": "Concepts",
        "adr": "ADRs",
        "decision": "Decisions",
        "pattern": "Patterns",
        "entity": "Entities",
    }
    return mapping.get(node_type, "Sessions")


def scrub_surrogates(obj: Any) -> Any:
    """Reemplaza surrogates sueltos (\\udcXX) para que el encode UTF-8 nunca falle.

    Aparecen cuando bytes CP1252 (p.ej. comillas tipograficas 0x92/0x94) se leyeron
    con errors='surrogateescape'. Se recuperan los bytes originales y se reinterpretan
    como CP1252 para preservar el caracter cuando es posible; si no, se reemplaza.
    Recorre dicts/listas/tuplas recursivamente. No-op si no hay surrogates.
    """
    if isinstance(obj, str):
        try:
            obj.encode("utf-8")
            return obj
        except UnicodeEncodeError:
            return obj.encode("utf-8", "surrogateescape").decode("cp1252", "replace")
    if isinstance(obj, dict):
        return {scrub_surrogates(k): scrub_surrogates(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(scrub_surrogates(x) for x in obj)
    return obj
