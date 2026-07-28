"""
Antigravity Brain — Motor de conocimiento estructurado por app.

Implementa el patron LLM Wiki (Karpathy) adaptado al ecosistema Antigravity:
- Nodos de conocimiento con frontmatter YAML
- Indice denso para O(indice) retrieval
- Cross-refs bidireccionales obligatorias
- Log append-only para auditoria
- Lint para salud de la base de conocimiento

Cada app (bot Telegram, Nexus, proyectos inyectados) tiene su propio Brain.
El Mother Brain (.agent/brain/) conecta todos los brains de la red.

v1.0.0 — 2026-04-13

Refactor 2026-05-31: el monolito ``brain.py`` (1553 lineas) se dividio en este
paquete sin cambios de comportamiento. La API publica se preserva: los imports
``from core.brain import Brain, BrainNode, ...`` siguen funcionando identico.

- ``constants`` — constantes y patron de slug
- ``dates``     — normalizacion de fechas heterogeneas
- ``text``      — parsing de secciones y scoring textual/semantico
- ``models``    — BrainNode, LintIssue, LintReport
- ``core``      — clase Brain
"""

from __future__ import annotations

from .constants import (
    DEFAULT_AREAS,
    MAX_RELATED,
    MAX_TAGS,
    SLUG_MAX_WORDS,
    VALID_STATUSES,
    VALID_TYPES,
    _SLUG_PATTERN,
)
from .core import Brain, _add_related_in_frontmatter
from .models import BrainNode, LintIssue, LintReport
from .text import (
    _expand_keywords,
    _extract_keywords,
    _parse_sections,
    _score_match,
    _smart_score,
    scrub_surrogates,
)

__all__ = [
    # API publica principal
    "Brain",
    "BrainNode",
    "LintIssue",
    "LintReport",
    # Constantes (parte de la superficie historica del modulo)
    "MAX_RELATED",
    "MAX_TAGS",
    "SLUG_MAX_WORDS",
    "VALID_TYPES",
    "VALID_STATUSES",
    "DEFAULT_AREAS",
    "_SLUG_PATTERN",
    # Helpers de texto consumidos por tests/herramientas
    "_add_related_in_frontmatter",
    "_parse_sections",
    "_extract_keywords",
    "_score_match",
    "_expand_keywords",
    "_smart_score",
    "scrub_surrogates",
]
