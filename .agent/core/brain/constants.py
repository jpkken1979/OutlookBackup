"""Constantes y validadores del Brain Network.

Extraido del monolito ``brain.py`` (refactor 2026-05-31). Sin cambios de
comportamiento: solo se reubicaron las definiciones.
"""

from __future__ import annotations

import re

# Patron valido para slugs: alfanumerico, guiones y underscores, max 200 chars
# Previene path traversal y caracteres peligrosos (HIGH-01, auditoriajp 2026-05-13)
_SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,200}$")

MAX_RELATED = 7
MAX_TAGS = 15
SLUG_MAX_WORDS = 8
VALID_TYPES = {"session", "concept", "adr", "entity", "decision", "pattern"}
VALID_STATUSES = {"active", "superseded", "archived"}
DEFAULT_AREAS = {
    "dev",
    "ops",
    "ux",
    "business",
    "security",
    "testing",
    "architecture",
    "data",
    "infra",
    "docs",
    "general",
}
