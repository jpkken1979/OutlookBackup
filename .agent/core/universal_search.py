#!/usr/bin/env python3
"""
Antigravity Universal Search — Búsqueda unificada multi-fuente
===============================================================

Busca simultáneamente en:
- Memorias markdown (`.claude/memory/`)
- Brain Network (`.agent/brain/`)
- Código del proyecto (ripgrep)
- Agentes y skills disponibles

Compatible con el servidor MCP `universal-search-server.py`.

v1.0.0 — 2026-05-09
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """Un resultado de búsqueda."""

    title: str
    content: str
    source: str  # memories | brain | code | agents
    source_label: str  # texto visible en la UI
    score: float = 0.0
    path: str = ""
    url: str = ""  # opcional: deep-link interno
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def preview(self) -> str:
        """Preview truncado para la UI (máx 120 chars)."""
        clean = self.content.replace("\r", "").replace("\n", " ").strip()
        return (clean[:117] + "…") if len(clean) > 120 else clean


# ---------------------------------------------------------------------------
# Universal Search Engine
# ---------------------------------------------------------------------------


class UniversalSearch:
    """Motor de búsqueda unificada para el ecosistema Antigravity.

    Busca en múltiples fuentes de conocimiento y retorna resultados
    ordenados por relevancia.

    Uso:
        search = UniversalSearch(Path.cwd())
        results = search.search("mem0", sources=["memories", "brain", "code"])
    """

    DEFAULT_SOURCES = ["memories", "brain", "code", "agents"]

    def __init__(self, project_root: str | Path) -> None:
        """Inicializa el motor de búsqueda.

        Args:
            project_root: Directorio raíz del proyecto Antigravity.
        """
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / ".claude" / "memory"
        self.brain_dir = self.project_root / ".agent" / "brain"
        self.agents_dir = self.project_root / ".agent" / "agents"
        self.skills_dir = self.project_root / ".agent" / "skills-custom"

    # ── Search principal ───────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        sources: list[str] | None = None,
        limit_per_source: int = 5,
    ) -> list[SearchResult]:
        """Busca en todas las fuentes especificadas.

        Args:
            query: Término de búsqueda.
            sources: Lista de fuentes a consultar.
                Valores: memories, brain, code, agents.
                Si None, usa DEFAULT_SOURCES.
            limit_per_source: Límite de resultados por fuente.

        Returns:
            Lista plana de SearchResult ordenados por score descendente.
        """
        if not query or not query.strip():
            return []

        sources = sources or self.DEFAULT_SOURCES
        results: list[SearchResult] = []

        if "memories" in sources:
            results.extend(self.search_memories(query, limit=limit_per_source))
        if "brain" in sources:
            results.extend(self.search_brain(query, limit=limit_per_source))
        if "code" in sources:
            results.extend(self.search_code(query, limit=limit_per_source))
        if "agents" in sources:
            results.extend(self.search_agents(query, limit=limit_per_source))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # ── Memorias markdown ──────────────────────────────────────────────────────

    def search_memories(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Busca en `.claude/memory/*.md`.

        Args:
            query: Término de búsqueda.
            limit: Máximo de resultados.

        Returns:
            Lista de SearchResult de memorias.
        """
        if not self.memory_dir.exists():
            return []

        q_lower = query.lower()
        results: list[tuple[float, SearchResult]] = []
        keywords = _extract_keywords(query)

        for md_file in self.memory_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                content_lower = content.lower()

                # Scoring: título > tags/metadata > body
                title_match = md_file.stem.lower().replace("_", " ").find(q_lower)
                body_count = content_lower.count(q_lower)
                keyword_count = sum(content_lower.count(k.lower()) for k in keywords)

                if title_match >= 0 or body_count > 0 or keyword_count > 0:
                    score = (10 if title_match >= 0 else 0) + body_count * 0.5 + keyword_count * 1.5

                    # Extraer título del frontmatter o del H1
                    title = _extract_title_from_markdown(content, md_file.stem)

                    # Extraer tags del frontmatter
                    tags = _extract_tags_from_frontmatter(content)

                    results.append(
                        (
                            score,
                            SearchResult(
                                title=title,
                                content=content[:500],
                                source="memories",
                                source_label="Memoria",
                                score=score,
                                path=str(md_file.relative_to(self.project_root)),
                                tags=tags,
                                metadata={"type": "memory", "match_count": body_count},
                            ),
                        )
                    )
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Error leyendo %s: %s", md_file, e)

        results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in results[:limit]]

    # ── Brain Network ───────────────────────────────────────────────────────────

    def search_brain(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Busca en `.agent/brain/` vía Brain.query().

        Args:
            query: Término de búsqueda.
            limit: Máximo de resultados.

        Returns:
            Lista de SearchResult del Brain.
        """
        if not self.brain_dir.exists():
            return []

        try:
            import sys as _sys

            _sys.path.insert(0, str(self.project_root / ".agent"))
            from core.brain import Brain

            brain = Brain(self.brain_dir, app_id="nexus-mother")
            nodes = brain.query(query, limit=limit)

            return [
                SearchResult(
                    title=n.title,
                    content=n.context or n.decisions or n.output or "",
                    source="brain",
                    source_label="Brain",
                    score=max(0.1, 10.0 - i * 1.5),
                    path=f".agent/brain/{n.slug}.md",
                    tags=n.tags,
                    metadata={
                        "type": n.type,
                        "area": n.area,
                        "status": n.status,
                    },
                )
                for i, n in enumerate(nodes)
            ]
        except Exception as e:
            logger.warning("Error en Brain.query('%s'): %s", query, e)
            return []

    # ── Código (ripgrep) ───────────────────────────────────────────────────────

    def _rg_line_to_result(
        self, line: str, seen_files: set[str]
    ) -> tuple[float, SearchResult] | None:
        """Convierte una línea JSON de ripgrep en un (score, SearchResult).

        Args:
            line: Línea de salida `rg --json`.
            seen_files: Conjunto de archivos ya vistos (deduplicación; se muta).

        Returns:
            Tupla (score, SearchResult) o None si la línea no aporta un match nuevo.
        """
        if not line.strip():
            return None
        try:
            entry = _parse_rg_json_line(line)
            if entry is None:
                return None

            file_path = entry["file"]
            if file_path in seen_files:
                return None
            seen_files.add(file_path)

            rel = str(Path(file_path).relative_to(self.project_root))
            score = 10.0
            return (
                score,
                SearchResult(
                    title=f"{rel}:{entry['line']}",
                    content=entry["text"],
                    source="code",
                    source_label="Código",
                    score=score,
                    path=rel,
                    tags=[],
                    metadata={"line": entry["line"]},
                ),
            )
        except (ValueError, KeyError):
            return None

    def search_code(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Busca en código fuente del proyecto con ripgrep.

        Args:
            query: Término de búsqueda.
            limit: Máximo de resultados.

        Returns:
            Lista de SearchResult de código.
        """
        if not self.project_root.exists():
            return []

        EXCLUDE_DIRS = [
            ".git",
            "node_modules",
            "target",
            "dist",
            "build",
            "__pycache__",
            ".venv",
            "venv",
        ]
        EXCLUDE_ARGS = [f"--exclude-dir={d}" for d in EXCLUDE_DIRS]

        try:
            cmd = [
                "rg",
                "--json",
                "--max-count",
                str(limit * 3),
                "-i",  # case insensitive
                "-e",
                query,
                str(self.project_root),
                *EXCLUDE_ARGS,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
                shell=False,  # noqa: S604 — cmd array es seguro
            )

            if result.returncode not in (0, 1):
                logger.debug("ripgrep returned %d", result.returncode)
                return []

            results: list[tuple[float, SearchResult]] = []
            seen_files: set[str] = set()

            for line in result.stdout.decode("utf-8", errors="replace").splitlines():
                entry = self._rg_line_to_result(line, seen_files)
                if entry is not None:
                    results.append(entry)

            results.sort(key=lambda x: x[0], reverse=True)
            return [r for _, r in results[:limit]]

        except FileNotFoundError:
            logger.debug("ripgrep no disponible — skipping code search")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("ripgrep timeout para query='%s'", query)
            return []
        except Exception as e:
            logger.warning("Error en search_code('%s'): %s", query, e)
            return []

    # ── Agentes y Skills ───────────────────────────────────────────────────────

    def _match_agent_dir(self, agent_dir: Path, q_lower: str) -> tuple[float, SearchResult] | None:
        """Evalúa un directorio de agente contra la query.

        Args:
            agent_dir: Directorio candidato dentro de `.agent/agents/`.
            q_lower: Término de búsqueda normalizado a minúsculas.

        Returns:
            Tupla (score, SearchResult) si matchea, o None si no aplica.
        """
        if not agent_dir.is_dir():
            return None
        identity_file = agent_dir / "IDENTITY.md"
        name = agent_dir.name.lower()

        if q_lower not in name and not identity_file.exists():
            return None

        title = name
        content = ""

        if identity_file.exists():
            try:
                content = identity_file.read_text(encoding="utf-8", errors="replace")
                title = _extract_title_from_markdown(content, name)
            except OSError:
                pass

        return (
            5.0,
            SearchResult(
                title=title,
                content=content[:400],
                source="agents",
                source_label="Agente",
                score=5.0,
                path=str(agent_dir.relative_to(self.project_root)),
                tags=["agent"],
                metadata={"type": "agent"},
            ),
        )

    def _match_skill_dir(self, skill_dir: Path, q_lower: str) -> tuple[float, SearchResult] | None:
        """Evalúa un directorio de skill custom contra la query.

        Args:
            skill_dir: Directorio candidato dentro de `.agent/skills-custom/`.
            q_lower: Término de búsqueda normalizado a minúsculas.

        Returns:
            Tupla (score, SearchResult) si matchea, o None si no aplica.
        """
        if not skill_dir.is_dir():
            return None
        skill_file = skill_dir / "SKILL.md"
        name = skill_dir.name.lower()

        if q_lower not in name and not skill_file.exists():
            return None

        content = ""
        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        return (
            4.0,
            SearchResult(
                title=name,
                content=content[:400],
                source="agents",
                source_label="Skill",
                score=4.0,
                path=str(skill_dir.relative_to(self.project_root)),
                tags=["skill"],
                metadata={"type": "skill"},
            ),
        )

    def search_agents(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Busca en `.agent/agents/` y `.agent/skills-custom/`.

        Args:
            query: Término de búsqueda.
            limit: Máximo de resultados.

        Returns:
            Lista de SearchResult de agentes/skills.
        """
        if not self.project_root.exists():
            return []

        q_lower = query.lower()
        results: list[tuple[float, SearchResult]] = []

        # Buscar en agents (por IDENTITY.md y nombre de carpeta)
        if self.agents_dir.exists():
            for agent_dir in self.agents_dir.iterdir():
                matched = self._match_agent_dir(agent_dir, q_lower)
                if matched is not None:
                    results.append(matched)

        # Buscar en skills-custom
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                matched = self._match_skill_dir(skill_dir, q_lower)
                if matched is not None:
                    results.append(matched)

        results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in results[:limit]]

    # ── Utilidades ─────────────────────────────────────────────────────────────

    def available_sources(self) -> list[dict[str, Any]]:
        """Retorna las fuentes disponibles con metadata."""
        return [
            {
                "id": "memories",
                "label": "Memorias",
                "description": "Búsqueda en .claude/memory/*.md",
                "available": self.memory_dir.exists(),
                "count": (
                    len(list(self.memory_dir.glob("*.md"))) if self.memory_dir.exists() else 0
                ),
            },
            {
                "id": "brain",
                "label": "Brain Network",
                "description": "Búsqueda en .agent/brain/ via Brain.query()",
                "available": self.brain_dir.exists(),
                "count": 0,  # se calcula en caliente
            },
            {
                "id": "code",
                "label": "Código",
                "description": "Búsqueda en código fuente con ripgrep",
                "available": True,
                "count": 0,
            },
            {
                "id": "agents",
                "label": "Agentes y Skills",
                "description": "Búsqueda en .agent/agents/ y skills-custom/",
                "available": self.agents_dir.exists(),
                "count": (
                    (len(list(self.agents_dir.glob("*"))) if self.agents_dir.exists() else 0)
                    + (len(list(self.skills_dir.glob("*"))) if self.skills_dir.exists() else 0)
                ),
            },
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEYWORD_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{2,}")


def _extract_keywords(text: str) -> list[str]:
    """Extrae palabras clave de longitud >= 3."""
    return _KEYWORD_RE.findall(text.lower())


def _extract_title_from_markdown(content: str, fallback: str) -> str:
    """Extrae título del primer H1 o del frontmatter."""
    fm_match = re.search(r"^---\s*\n.*?title:\s*([^\n]+)\s*\n", content, re.M | re.DOTALL)
    if fm_match:
        return fm_match.group(1).strip().strip('"').strip("'")

    h1_match = re.search(r"^#\s+(.+)$", content, re.M)
    if h1_match:
        return h1_match.group(1).strip()

    return fallback.replace("_", " ").replace("-", " ")


def _extract_tags_from_frontmatter(content: str) -> list[str]:
    """Extrae tags del frontmatter YAML."""
    tags_match = re.search(r"^tags:\s*\[(.+)\]$", content, re.M)
    if tags_match:
        raw = tags_match.group(1)
        return [t.strip().strip('"').strip("'") for t in raw.split(",")]
    return []


def _parse_rg_json_line(line: str) -> dict[str, Any] | None:
    """Parsea una línea JSON de ripgrep --json."""
    try:
        obj: dict[str, Any] = __import__("json").loads(line)
        if obj.get("type") != "match":
            return None
        data = obj.get("data", {})
        if not data:
            return None
        lines = data.get("lines", {})
        text = lines.get("text", "").rstrip()
        return {
            "file": data.get("path", {}).get("text", ""),
            "line": data.get("line_number", 0),
            "text": text,
        }
    except Exception:
        return None
