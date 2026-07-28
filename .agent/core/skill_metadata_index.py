"""
Skill Metadata Index — Carga en dos fases (Progressive Disclosure).

Fase 1: parsea solo el frontmatter YAML (~2KB). Siempre en memoria.
Fase 2: carga el cuerpo completo solo cuando la skill es seleccionada.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _normalise_yaml_value(value: Any) -> Any:
    """Normaliza un valor parseado por PyYAML al formato esperado.

    Args:
        value: Valor crudo proveniente de ``yaml.safe_load``.

    Returns:
        El valor escalar tal cual, las listas convertidas a listas de ``str``
        (compatibilidad con ``SkillRecord``), los dicts tal cual, o ``None`` si
        el valor debe descartarse.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        # Normalise list items to strings for SkillRecord compatibility
        return [str(item) for item in value]
    if isinstance(value, dict):
        return value
    return None


def _parse_yaml_with_pyyaml(text: str) -> dict[str, Any] | None:
    """Parsea frontmatter con PyYAML (soporta listas y estructuras anidadas).

    Args:
        text: Texto del frontmatter YAML.

    Returns:
        El dict normalizado, o ``None`` si PyYAML no pudo parsear el texto.
    """
    import yaml  # type: ignore[import-untyped]

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return {}
    result: dict[str, Any] = {}
    for k, v in parsed.items():
        normalised = _normalise_yaml_value(v)
        if normalised is not None:
            result[k] = normalised
    return result


def _parse_simple_yaml_fallback(text: str) -> dict[str, Any]:
    """Parser simple original para frontmatter no estandar.

    Args:
        text: Texto del frontmatter.

    Returns:
        Dict con los pares clave/valor, soportando bloques literales ``|``.
    """
    result: dict[str, Any] = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line:
            i += 1
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value == "|":
            block: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or lines[i] == ""):
                block.append(lines[i].lstrip())
                i += 1
            result[key] = " ".join(b for b in block if b).strip()
        else:
            result[key] = value.strip('"').strip("'")
        i += 1
    return result


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parser YAML tolerante. Intenta PyYAML safe_load primero; fallback al parser
    simple original si falla (compatibilidad hacia atrás con frontmatter no estándar)."""
    parsed = _parse_yaml_with_pyyaml(text)
    if parsed is not None:
        return parsed
    return _parse_simple_yaml_fallback(text)


class SkillMetadataIndex:
    """
    Índice de metadata con carga en dos fases.

    Uso:
        index = SkillMetadataIndex(skills_dir)
        meta = index.get_metadata("api-patterns")   # O(1), solo frontmatter
        body = index.get_full_body("api-patterns")  # carga completa bajo demanda
    """

    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = Path(skills_dir)
        self._metadata: dict[str, dict[str, Any]] = {}
        self._build_index()

    def _build_index(self) -> None:
        if not self._skills_dir.exists():
            logger.warning("Skills dir no existe: %s", self._skills_dir)
            return
        count = 0
        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            meta = self._extract_metadata(skill_dir.name, skill_md)
            if meta:
                self._metadata[skill_dir.name] = meta
                count += 1
        logger.info("SkillMetadataIndex: %d skills indexadas", count)

    def _extract_metadata(self, skill_name: str, skill_md: Path) -> dict[str, Any] | None:
        try:
            with skill_md.open(encoding="utf-8") as f:
                header = f.read(2048)  # solo primeros 2KB
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("No se pudo leer %s: %s", skill_md, e)
            return None

        match = _FRONTMATTER_RE.match(header)
        if match:
            parsed = _parse_simple_yaml(match.group(1))
            return {
                "name": parsed.get("name", skill_name),
                "description": parsed.get("description", "").strip(),
                "path": str(skill_md),
                "has_frontmatter": True,
            }

        # Fallback: primera línea no-comentario
        first_line = next(
            (
                line.strip()[:200]
                for line in header.split("\n")
                if line.strip() and not line.strip().startswith(("#", "---"))
            ),
            skill_name,
        )
        return {
            "name": skill_name,
            "description": first_line,
            "path": str(skill_md),
            "has_frontmatter": False,
        }

    def get_metadata(self, skill_name: str) -> dict[str, Any] | None:
        """Retorna metadata (sin body). O(1)."""
        return self._metadata.get(skill_name)

    def get_full_body(self, skill_name: str) -> str:
        """Carga y retorna el cuerpo completo sin el frontmatter. Fase 2."""
        meta = self._metadata.get(skill_name)
        if not meta:
            return ""
        try:
            content = Path(meta["path"]).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
        if meta.get("has_frontmatter"):
            content = _FRONTMATTER_RE.sub("", content, count=1)
        return content.strip()

    def list_all(self) -> list[dict[str, Any]]:
        """Lista metadata de todas las skills indexadas."""
        return list(self._metadata.values())

    def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Búsqueda por keywords sobre name+description. No carga body."""
        query_lower = query.lower()
        scored: list[tuple[float, dict[str, Any]]] = []
        for meta in self._metadata.values():
            score = 0.0
            for word in query_lower.split():
                if len(word) < 3:
                    continue
                if word in meta["name"].lower():
                    score += 3.0
                if word in meta["description"].lower():
                    score += 1.0
            if score > 0:
                scored.append((score, meta))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:max_results]]
