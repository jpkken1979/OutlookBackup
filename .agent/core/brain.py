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
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Patron valido para slugs: alfanumerico, guiones y underscores, max 200 chars
# Previene path traversal y caracteres peligrosos (HIGH-01, auditoriajp 2026-05-13)
_SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,200}$")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class BrainNode:
    """Un nodo de conocimiento con frontmatter estructurado.

    Cada nodo representa una pieza de conocimiento: sesion, concepto,
    decision arquitectonica, entidad, o patron descubierto.
    """

    slug: str
    type: str  # session | concept | adr | entity | decision | pattern
    area: str
    date: str  # YYYY-MM-DD
    title: str
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    related: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    app_origin: str = "unknown"
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Temporal intelligence
    importance: str = "normal"  # critical | high | normal | low
    access_count: int = 0
    last_accessed: str = ""
    version: int = 1

    # Contenido por secciones
    context: str = ""
    decisions: str = ""
    output: str = ""
    pending: str = ""
    crossrefs: str = ""
    source_notes: str = ""

    def to_frontmatter(self) -> str:
        """Serializa el nodo como frontmatter YAML + contenido Markdown."""
        fm = {
            "type": self.type,
            "area": self.area,
            "date": self.date,
            "slug": self.slug,
            "title": self.title,
            "tags": self.tags,
            "status": self.status,
            "related": self.related,
            "sources": self.sources,
            "superseded_by": self.superseded_by,
            "app_origin": self.app_origin,
            "node_id": self.node_id,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "version": self.version,
        }
        lines = ["---"]
        lines.append(yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip())
        lines.append("---")
        lines.append("")

        if self.context:
            lines.extend(["## Contexto", "", self.context, ""])
        if self.decisions:
            lines.extend(["## Decisiones", "", self.decisions, ""])
        if self.output:
            lines.extend(["## Output", "", self.output, ""])
        if self.pending:
            lines.extend(["## Pendiente", "", self.pending, ""])
        if self.crossrefs:
            lines.extend(["## Cross-refs", "", self.crossrefs, ""])
        if self.source_notes:
            lines.extend(["## Fuentes", "", self.source_notes, ""])

        return "\n".join(lines)

    def freshness_score(self) -> float:
        """Puntaje de frescura 0-1 basado en edad y importancia.

        critical = nunca decae, high = half-life 30 dias, normal = 14, low = 7.
        """
        try:
            created = datetime.strptime(self.date, "%Y-%m-%d")
            age_days = (datetime.now(UTC).replace(tzinfo=None) - created).days
        except ValueError:
            age_days = 0

        # Half-life en dias segun importancia
        half_lives = {"critical": float("inf"), "high": 30, "normal": 14, "low": 7}
        half_life = half_lives.get(self.importance, 14)

        if half_life == float("inf"):
            return 1.0

        import math

        decay = math.exp(-0.693 * age_days / half_life)  # 0.693 = ln(2)

        # Boost por accesos recientes
        access_boost = min(self.access_count * 0.02, 0.2)

        return min(decay + access_boost, 1.0)

    def one_liner(self) -> str:
        """Genera la linea del indice para este nodo."""
        tags_str = ", ".join(self.tags[:5]) if self.tags else ""
        origin = f" [{self.app_origin}]" if self.app_origin != "unknown" else ""
        return f"- [[{self.slug}]] — {self.title} ({tags_str}){origin}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario para APIs."""
        return asdict(self)

    @classmethod
    def from_frontmatter(cls, content: str, file_path: Path | None = None) -> BrainNode:
        """Parsea un archivo markdown con frontmatter YAML a BrainNode."""
        fm_match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
        if not fm_match:
            raise ValueError(f"No se encontro frontmatter YAML en {file_path or 'contenido'}")

        fm_text, body = fm_match.group(1), fm_match.group(2)
        fm = yaml.safe_load(fm_text) or {}

        # Extraer secciones del body
        sections = _parse_sections(body)

        return cls(
            slug=fm.get("slug", ""),
            type=fm.get("type", "session"),
            area=fm.get("area", "general"),
            date=fm.get("date", ""),
            title=fm.get("title", ""),
            tags=fm.get("tags", []),
            status=fm.get("status", "active"),
            related=fm.get("related", []),
            sources=fm.get("sources", []),
            superseded_by=fm.get("superseded_by"),
            app_origin=fm.get("app_origin", "unknown"),
            node_id=fm.get("node_id", str(uuid.uuid4())[:8]),
            importance=fm.get("importance", "normal"),
            access_count=fm.get("access_count", 0),
            last_accessed=fm.get("last_accessed", ""),
            version=fm.get("version", 1),
            context=sections.get("contexto", ""),
            decisions=sections.get("decisiones", ""),
            output=sections.get("output", ""),
            pending=sections.get("pendiente", ""),
            crossrefs=sections.get("cross-refs", ""),
            source_notes=sections.get("fuentes", ""),
        )


@dataclass
class LintIssue:
    """Un hallazgo del proceso de lint."""

    severity: str  # error | warning | info
    category: str  # orphan | broken_link | stale | missing_crossref | concept_candidate
    message: str
    node_slug: str = ""
    suggestion: str = ""


@dataclass
class LintReport:
    """Resultado completo de un lint del brain."""

    issues: list[LintIssue] = field(default_factory=list)
    total_nodes: int = 0
    healthy_nodes: int = 0
    concept_candidates: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Puntaje de salud 0-10."""
        if self.total_nodes == 0:
            return 10.0
        error_nodes = {
            issue.node_slug for issue in self.issues if issue.severity == "error" and issue.node_slug
        }
        warning_nodes = {
            issue.node_slug for issue in self.issues if issue.severity == "warning" and issue.node_slug
        }
        global_errors = sum(
            1 for issue in self.issues if issue.severity == "error" and not issue.node_slug
        )
        global_warnings = sum(
            1 for issue in self.issues if issue.severity == "warning" and not issue.node_slug
        )
        penalty = (
            len(error_nodes) * 2.0
            + len(warning_nodes) * 0.35
            + global_errors * 1.0
            + global_warnings * 0.15
        ) / max(self.total_nodes, 1)
        return max(0.0, 10.0 - penalty * 10)

    def summary(self) -> str:
        """Resumen legible del lint."""
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        infos = sum(1 for i in self.issues if i.severity == "info")
        lines = [
            f"Brain Health: {self.score:.1f}/10",
            f"Nodos: {self.total_nodes} total, {self.healthy_nodes} sanos",
            f"Issues: {errors} errores, {warnings} warnings, {infos} info",
        ]
        if self.concept_candidates:
            lines.append(f"Conceptos emergentes: {', '.join(self.concept_candidates[:5])}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Brain Engine
# ---------------------------------------------------------------------------


class Brain:
    """Motor de conocimiento para una app individual.

    Cada Brain maneja su propio directorio con:
    - index.md — indice denso (one-liner por nodo)
    - sessions/ — nodos de conocimiento
    - concepts/ — nodos emergentes
    - connections/ — enlaces cross-app (solo Mother Brain)
    - sources.md — registro de fuentes
    - log.md — bitacora append-only
    - BRAIN.md — schema operacional

    Uso:
        brain = Brain(Path(".agent/brain"), app_id="nexus-mother")
        node = brain.ingest("Setup email infra", context="...", area="ops", tags=["email"])
        results = brain.query("email infrastructure")
        report = brain.lint()
    """

    def __init__(self, brain_dir: str | Path, app_id: str = "default") -> None:
        """Inicializa el brain engine.

        Args:
            brain_dir: Directorio raiz del brain.
            app_id: Identificador de la app (ej: "nexus-mother", "telegram-bot").
        """
        self.brain_dir = Path(brain_dir)
        self.app_id = app_id
        self.sessions_dir = self.brain_dir / "sessions"
        self.concepts_dir = self.brain_dir / "concepts"
        self.connections_dir = self.brain_dir / "connections"
        self.index_path = self.brain_dir / "index.md"
        self.log_path = self.brain_dir / "log.md"
        self.sources_path = self.brain_dir / "sources.md"

        # Crear estructura si no existe
        self._ensure_structure()

        # Cache del indice
        self._index_cache: dict[str, str] | None = None

    def _ensure_structure(self) -> None:
        """Crea la estructura de directorios y archivos base."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.concepts_dir.mkdir(parents=True, exist_ok=True)
        self.connections_dir.mkdir(parents=True, exist_ok=True)

        if not self.index_path.exists():
            self.index_path.write_text(
                f"# Brain Index — {self.app_id}\n\n"
                f"> Indice denso del conocimiento. Leer PRIMERO en cada operacion.\n\n"
                f"## Sessions\n\n## Concepts\n\n## Decisions\n\n## Patterns\n\n",
                encoding="utf-8",
            )

        if not self.log_path.exists():
            now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
            self.log_path.write_text(
                f"# Brain Log — {self.app_id}\n\n"
                f"## [{now}] init | brain-created\n"
                f"Brain inicializado para {self.app_id}\n\n",
                encoding="utf-8",
            )

        if not self.sources_path.exists():
            self.sources_path.write_text(
                f"# Sources — {self.app_id}\n\n"
                f"> Registro de fuentes externas referenciadas por nodos.\n\n",
                encoding="utf-8",
            )

    # ----- INGEST -----

    def ingest(
        self,
        title: str,
        *,
        context: str = "",
        decisions: str = "",
        output: str = "",
        pending: str = "",
        area: str = "general",
        tags: list[str] | None = None,
        sources: list[str] | None = None,
        node_type: str = "session",
        source_notes: str = "",
        importance: str = "normal",
    ) -> BrainNode:
        """Ingesta conocimiento nuevo como un nodo del brain.

        Args:
            title: Titulo descriptivo del nodo.
            context: Seccion de contexto/background.
            decisions: Decisiones tomadas.
            output: Resultados concretos.
            pending: Tareas pendientes.
            area: Area tematica (dev, ops, ux, etc.).
            tags: Tags libres para discovery.
            sources: Referencias a fuentes externas.
            node_type: Tipo de nodo (session, concept, adr, etc.).
            source_notes: Notas sobre fuentes.
            importance: Nivel de importancia (critical, high, normal, low).

        Returns:
            El BrainNode creado.

        Raises:
            ValueError: si node_type no esta en VALID_TYPES.
        """
        if node_type not in VALID_TYPES:
            raise ValueError(
                f"node_type invalido: {node_type!r}. Validos: {sorted(VALID_TYPES)}"
            )

        tags = (tags or [])[:MAX_TAGS]
        sources = sources or []
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Generar slug
        slug = self._generate_slug(title, today)

        # Detectar nodos relacionados
        related = self._detect_related(tags, area, slug)

        node = BrainNode(
            slug=slug,
            type=node_type,
            area=area,
            date=today,
            title=title,
            tags=tags,
            status="active",
            related=related,
            sources=sources,
            app_origin=self.app_id,
            importance=importance
            if importance in ("critical", "high", "normal", "low")
            else "normal",
            context=context,
            decisions=decisions,
            output=output,
            pending=pending,
            source_notes=source_notes,
        )

        # Persistir nodo
        target_dir = self.concepts_dir if node_type == "concept" else self.sessions_dir
        node_path = target_dir / f"{slug}.md"
        node_path.write_text(node.to_frontmatter(), encoding="utf-8")

        # Bidireccionalidad: actualizar nodos related
        self._ensure_bidirectional_refs(node)

        # Actualizar indice
        self._update_index(node)

        # Append al log
        self._append_log("ingest", slug, f"Tipo: {node_type}, Area: {area}")

        # Invalidar cache
        self._index_cache = None

        logger.info("Brain[%s] ingesto nodo: %s", self.app_id, slug)
        return node

    def update_node(
        self,
        slug: str,
        *,
        context: str | None = None,
        decisions: str | None = None,
        output: str | None = None,
        pending: str | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        related: list[str] | None = None,
    ) -> BrainNode:
        """Actualiza un nodo existente.

        Args:
            slug: Slug del nodo a actualizar.
            context: Nuevo contexto (None = no cambiar).
            decisions: Nuevas decisiones.
            output: Nuevo output.
            pending: Nuevo pendiente.
            tags: Nuevos tags.
            status: Nuevo status.
            related: Nuevos related.

        Returns:
            El nodo actualizado.

        Raises:
            FileNotFoundError: Si el nodo no existe.
        """
        node = self.get_node(slug)

        if context is not None:
            node.context = context
        if decisions is not None:
            node.decisions = decisions
        if output is not None:
            node.output = output
        if pending is not None:
            node.pending = pending
        if tags is not None:
            node.tags = tags[:MAX_TAGS]
        if status is not None and status in VALID_STATUSES:
            node.status = status
        if related is not None:
            node.related = related[:MAX_RELATED]

        # Incremental version for each update (dedup tracking)
        node.version += 1

        # Persistir
        node_path = self._find_node_file(slug)
        node_path.write_text(node.to_frontmatter(), encoding="utf-8")

        # Bidireccionalidad si cambio related
        if related is not None:
            self._ensure_bidirectional_refs(node)

        self._append_log("update", slug)
        self._index_cache = None
        return node

    # ----- QUERY -----

    def query(self, question: str, *, limit: int = 5) -> list[BrainNode]:
        """Busca nodos relevantes con scoring inteligente.

        Estrategia multi-factor:
        1. Keywords + fuzzy matching + semantic expansion
        2. Freshness scoring (nodos recientes pesan mas)
        3. Importance weighting (critical > high > normal > low)
        4. Access popularity (nodos mas consultados rankean mejor)

        Args:
            question: Pregunta o termino de busqueda.
            limit: Maximo de resultados.

        Returns:
            Lista de nodos ordenados por relevancia compuesta.
        """
        keywords = _extract_keywords(question)
        if not keywords:
            return []

        # Expandir keywords con sinonimos del dominio dev
        expanded = _expand_keywords(keywords)

        # Paso 1: Leer indice y buscar matches con scoring multi-factor
        index_entries = self._load_index()
        candidates: list[tuple[str, float]] = []

        for slug, one_liner in index_entries.items():
            # Score por keywords + fuzzy
            keyword_score = _smart_score(one_liner.lower(), expanded)
            if keyword_score <= 0:
                continue

            # Intentar leer metadata sin fetch completo (del indice)
            candidates.append((slug, keyword_score))

        # Paso 2: Fetch top candidatos y re-rankear con metadata
        candidates.sort(key=lambda x: x[1], reverse=True)
        fetch_limit = min(limit * 3, len(candidates))  # Fetch mas para re-rankear
        enriched: list[tuple[BrainNode, float]] = []

        for slug, base_score in candidates[:fetch_limit]:
            try:
                node = self.get_node(slug)
            except (FileNotFoundError, ValueError):
                continue

            # Re-score con metadata
            freshness = node.freshness_score()
            importance_mult = {"critical": 1.5, "high": 1.2, "normal": 1.0, "low": 0.7}
            imp_factor = importance_mult.get(node.importance, 1.0)

            # Score compuesto
            final_score = (
                base_score * 0.5  # Relevancia textual
                + freshness * 3.0  # Frescura temporal
                + imp_factor * 1.0  # Importancia
                + min(node.access_count * 0.05, 1.0)  # Popularidad
            )
            enriched.append((node, final_score))

        # Paso 3: Ordenar por score final
        enriched.sort(key=lambda x: x[1], reverse=True)
        return [node for node, _ in enriched[:limit]]

    def get_node(self, slug: str, *, track_access: bool = True) -> BrainNode:
        """Lee un nodo especifico por su slug.

        Args:
            slug: El slug del nodo.
            track_access: Si True, incrementa access_count y last_accessed.

        Returns:
            El BrainNode parseado.

        Raises:
            FileNotFoundError: Si el nodo no existe.
        """
        node_path = self._find_node_file(slug)
        content = node_path.read_text(encoding="utf-8")
        node = BrainNode.from_frontmatter(content, node_path)

        if track_access:
            node.access_count += 1
            node.last_accessed = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
            node_path.write_text(node.to_frontmatter(), encoding="utf-8")

        return node

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        area: str | None = None,
        status: str = "active",
        tag: str | None = None,
    ) -> list[BrainNode]:
        """Lista nodos con filtros opcionales.

        Args:
            node_type: Filtrar por tipo.
            area: Filtrar por area.
            status: Filtrar por status (default: active).
            tag: Filtrar por tag.

        Returns:
            Lista de nodos que matchean los filtros.
        """
        nodes = []
        for md_file in self._all_node_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
            except (ValueError, yaml.YAMLError):
                continue

            if node_type and node.type != node_type:
                continue
            if area and node.area != area:
                continue
            if status and node.status != status:
                continue
            if tag and tag not in node.tags:
                continue
            nodes.append(node)

        nodes.sort(key=lambda n: n.date, reverse=True)
        return nodes

    # ----- LINT -----

    def lint(self) -> LintReport:
        """Auditoria de salud del brain. Read-only, nunca modifica archivos.

        Detecta:
        - Orphan nodes (sin inbound links)
        - Broken wikilinks
        - Stale claims (pendientes vencidos)
        - Missing cross-refs
        - Conceptos emergentes (tags en 3+ nodos sin nodo propio)
        - Frontmatter invalido
        - Indice desincronizado

        Returns:
            LintReport con hallazgos y puntaje de salud.
        """
        report = LintReport()
        all_nodes: list[BrainNode] = []
        all_slugs: set[str] = set()
        inbound_links: dict[str, set[str]] = {}
        tag_counts: dict[str, int] = {}
        index_entries = self._load_index()

        # Paso 1: Cargar todos los nodos
        for md_file in self._all_node_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
                all_nodes.append(node)
                all_slugs.add(node.slug)
            except (ValueError, yaml.YAMLError) as e:
                report.issues.append(
                    LintIssue(
                        severity="error",
                        category="invalid_frontmatter",
                        message=f"Error parseando {md_file.name}: {e}",
                        node_slug=md_file.stem,
                    )
                )

        report.total_nodes = len(all_nodes)

        # Paso 2: Analizar relaciones y tags
        for node in all_nodes:
            # Verificar broken links
            for ref_slug in node.related:
                if ref_slug not in all_slugs:
                    report.issues.append(
                        LintIssue(
                            severity="error",
                            category="broken_link",
                            message=f"[[{ref_slug}]] referenciado por {node.slug} no existe",
                            node_slug=node.slug,
                            suggestion=f"Crear nodo {ref_slug} o remover referencia",
                        )
                    )
                else:
                    inbound_links.setdefault(ref_slug, set()).add(node.slug)

            # Contar tags
            for tag in node.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Verificar bidireccionalidad
            for ref_slug in node.related:
                if ref_slug in all_slugs:
                    ref_node = next((n for n in all_nodes if n.slug == ref_slug), None)
                    if ref_node and node.slug not in ref_node.related:
                        report.issues.append(
                            LintIssue(
                                severity="warning",
                                category="missing_crossref",
                                message=(f"{node.slug} → {ref_slug} sin reciproco"),
                                node_slug=node.slug,
                                suggestion=(f"Agregar {node.slug} a related de {ref_slug}"),
                            )
                        )

            # Verificar sincronia con indice
            if node.status == "active" and node.slug not in index_entries:
                report.issues.append(
                    LintIssue(
                        severity="warning",
                        category="index_desync",
                        message=f"Nodo activo {node.slug} no esta en el indice",
                        node_slug=node.slug,
                        suggestion="Ejecutar rebuild_index()",
                    )
                )

        # Paso 3: Detectar orphans
        for node in all_nodes:
            if node.slug not in inbound_links and node.status == "active":
                has_outbound = bool(node.related)
                if not has_outbound:
                    report.issues.append(
                        LintIssue(
                            severity="info",
                            category="orphan",
                            message=f"Nodo {node.slug} sin links entrantes ni salientes",
                            node_slug=node.slug,
                            suggestion="Considerar agregar cross-refs o archivar",
                        )
                    )

        # Paso 4: Detectar conceptos emergentes
        existing_concept_slugs = {n.slug for n in all_nodes if n.type == "concept"}
        for tag, count in tag_counts.items():
            if count >= 3:
                # Verificar si ya existe como concepto
                tag_slug_candidates = [
                    s
                    for s in all_slugs
                    if tag.replace(" ", "-").lower() in s.lower() and s in existing_concept_slugs
                ]
                if not tag_slug_candidates:
                    report.concept_candidates.append(tag)
                    report.issues.append(
                        LintIssue(
                            severity="info",
                            category="concept_candidate",
                            message=f"Tag '{tag}' aparece en {count} nodos, candidato a concepto",
                            suggestion=f"Crear nodo tipo concept para '{tag}'",
                        )
                    )

        # Paso 5: Contar nodos sanos
        problematic_slugs = {
            issue.node_slug
            for issue in report.issues
            if issue.severity in {"error", "warning"} and issue.node_slug
        }
        report.healthy_nodes = len([n for n in all_nodes if n.slug not in problematic_slugs])

        return report

    def rebuild_index(self) -> int:
        """Reconstruye el indice desde los nodos existentes.

        Returns:
            Numero de nodos indexados.
        """
        nodes = self.list_nodes(status="active")

        # Agrupar por tipo
        by_type: dict[str, list[BrainNode]] = {}
        for node in nodes:
            by_type.setdefault(node.type, []).append(node)

        lines = [
            f"# Brain Index — {self.app_id}",
            "",
            f"> Indice denso del conocimiento. {len(nodes)} nodos activos.",
            f"> Ultima reconstruccion: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC",
            "",
        ]

        type_labels = {
            "session": "Sessions",
            "concept": "Concepts",
            "adr": "ADRs",
            "decision": "Decisions",
            "pattern": "Patterns",
            "entity": "Entities",
        }

        for node_type, label in type_labels.items():
            type_nodes = by_type.get(node_type, [])
            lines.append(f"## {label}")
            lines.append("")
            if type_nodes:
                for node in sorted(type_nodes, key=lambda n: n.date, reverse=True):
                    lines.append(node.one_liner())
            else:
                lines.append("_Sin nodos._")
            lines.append("")

        self.index_path.write_text("\n".join(lines), encoding="utf-8")
        self._index_cache = None
        self._append_log("rebuild_index", f"{len(nodes)}-nodes")
        return len(nodes)

    # ----- STATS -----

    def stats(self) -> dict[str, Any]:
        """Estadisticas del brain."""
        nodes = []
        for md_file in self._all_node_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
                nodes.append(node)
            except (ValueError, yaml.YAMLError):
                continue

        by_type: dict[str, int] = {}
        by_area: dict[str, int] = {}
        by_status: dict[str, int] = {}
        all_tags: dict[str, int] = {}

        for node in nodes:
            by_type[node.type] = by_type.get(node.type, 0) + 1
            by_area[node.area] = by_area.get(node.area, 0) + 1
            by_status[node.status] = by_status.get(node.status, 0) + 1
            for tag in node.tags:
                all_tags[tag] = all_tags.get(tag, 0) + 1

        top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "app_id": self.app_id,
            "brain_dir": str(self.brain_dir),
            "total_nodes": len(nodes),
            "by_type": by_type,
            "by_area": by_area,
            "by_status": by_status,
            "top_tags": dict(top_tags),
            "total_connections": sum(len(n.related) for n in nodes),
        }

    # ----- GRAPH TRAVERSAL -----

    def traverse(self, slug: str, *, max_depth: int = 3) -> list[tuple[str, int]]:
        """BFS desde un nodo: descubre todo el conocimiento conectado.

        Navega el grafo de relaciones para encontrar nodos a N saltos
        de distancia. Permite descubrir conocimiento indirecto:
        "JWT" → "Token Refresh" → "Security Best Practice"

        Args:
            slug: Slug del nodo de inicio.
            max_depth: Profundidad maxima de busqueda.

        Returns:
            Lista de (slug, distancia) ordenada por distancia.
        """
        from collections import deque

        visited: set[str] = {slug}
        queue: deque[tuple[str, int]] = deque([(slug, 0)])
        results: list[tuple[str, int]] = []

        while queue:
            current, depth = queue.popleft()
            if depth > 0:
                results.append((current, depth))
            if depth < max_depth:
                try:
                    node = self.get_node(current, track_access=False)
                    for related_slug in node.related:
                        if related_slug not in visited:
                            visited.add(related_slug)
                            queue.append((related_slug, depth + 1))
                except (FileNotFoundError, ValueError):
                    pass

        return sorted(results, key=lambda x: x[1])

    def get_neighborhood(self, slug: str, *, depth: int = 2) -> dict[str, Any]:
        """Obtiene el vecindario completo de un nodo con contexto.

        Args:
            slug: Nodo central.
            depth: Profundidad de busqueda.

        Returns:
            Dict con nodo central, vecinos por nivel, y resumen.
        """
        reachable = self.traverse(slug, max_depth=depth)
        by_depth: dict[int, list[dict[str, str]]] = {}

        for r_slug, dist in reachable:
            try:
                node = self.get_node(r_slug, track_access=False)
                by_depth.setdefault(dist, []).append(
                    {
                        "slug": r_slug,
                        "title": node.title,
                        "type": node.type,
                        "area": node.area,
                    }
                )
            except (FileNotFoundError, ValueError):
                continue

        return {
            "center": slug,
            "total_reachable": len(reachable),
            "by_depth": by_depth,
        }

    # ----- CONSOLIDATION -----

    def consolidate(
        self,
        *,
        min_age_days: int = 30,
        max_orphan_age_days: int = 14,
    ) -> dict[str, Any]:
        """Consolida la memoria: archiva nodos viejos y huerfanos.

        Reglas:
        - Nodos con importancia "critical" NUNCA se archivan
        - Nodos huerfanos (sin inbound links) + viejos → archivados
        - Nodos con status "active" + edad > min_age_days + sin acceso reciente → archivados
        - Nunca elimina, solo cambia status a "archived"

        Args:
            min_age_days: Edad minima para considerar archivado.
            max_orphan_age_days: Edad para archivar huerfanos.

        Returns:
            Reporte de consolidacion.
        """
        archived: list[str] = []
        kept: list[str] = []
        all_nodes: list[BrainNode] = []
        inbound: dict[str, int] = {}

        # Cargar todos los nodos y contar inbound links
        for md_file in self._all_node_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
                all_nodes.append(node)
                for ref in node.related:
                    inbound[ref] = inbound.get(ref, 0) + 1
            except (ValueError, yaml.YAMLError):
                continue

        today = datetime.now(UTC)

        for node in all_nodes:
            if node.status != "active":
                continue
            if node.importance == "critical":
                kept.append(node.slug)
                continue

            try:
                created = datetime.strptime(node.date, "%Y-%m-%d")
                age_days = (today.replace(tzinfo=None) - created).days
            except ValueError:
                age_days = 0

            is_orphan = inbound.get(node.slug, 0) == 0 and not node.related
            should_archive = False

            # Huerfanos viejos → archivar
            if is_orphan and age_days > max_orphan_age_days:
                should_archive = True

            # Nodos low importance + viejos + sin acceso → archivar
            if node.importance == "low" and age_days > min_age_days and node.access_count < 3:
                should_archive = True

            # Nodos normales muy viejos + sin acceso → archivar
            if (
                node.importance == "normal"
                and age_days > min_age_days * 2
                and node.access_count < 2
            ):
                should_archive = True

            if should_archive:
                self.update_node(node.slug, status="archived")
                archived.append(node.slug)
            else:
                kept.append(node.slug)

        # Rebuild index sin nodos archivados
        if archived:
            self.rebuild_index()
            self._append_log(
                "consolidate",
                f"{len(archived)}-archived",
                f"Archivados: {', '.join(archived[:5])}{'...' if len(archived) > 5 else ''}",
            )

        return {
            "archived": len(archived),
            "kept": len(kept),
            "archived_slugs": archived,
            "total_before": len(all_nodes),
        }

    # ----- PRIVATE -----

    def _generate_slug(self, title: str, date: str) -> str:
        """Genera un slug unico: YYYY-MM-DD-kebab-case."""
        words = re.sub(r"[^a-zA-Z0-9\s]", "", title.lower()).split()
        slug_words = "-".join(words[:SLUG_MAX_WORDS])
        base_slug = f"{date}-{slug_words}"

        # Garantizar unicidad
        existing = {f.stem for f in self._all_node_files()}
        slug = base_slug
        counter = 2
        while slug in existing:
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def _detect_related(
        self,
        tags: list[str],
        area: str,
        exclude_slug: str = "",
    ) -> list[str]:
        """Detecta nodos relacionados por tags solapados y area."""
        candidates: list[tuple[str, int]] = []

        for md_file in self._all_node_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
            except (ValueError, yaml.YAMLError):
                continue

            if node.slug == exclude_slug or node.status != "active":
                continue

            score = 0
            # Tags solapados
            common_tags = set(tags) & set(node.tags)
            score += len(common_tags) * 2
            # Misma area
            if node.area == area:
                score += 1

            if score > 0:
                candidates.append((node.slug, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [slug for slug, _ in candidates[:MAX_RELATED]]

    def _ensure_bidirectional_refs(self, node: BrainNode) -> None:
        """Asegura que todos los related tengan el link reciproco."""
        for ref_slug in node.related:
            try:
                ref_path = self._find_node_file(ref_slug)
                content = ref_path.read_text(encoding="utf-8")
                ref_node = BrainNode.from_frontmatter(content, ref_path)
                if node.slug not in ref_node.related:
                    ref_node.related = (ref_node.related + [node.slug])[:MAX_RELATED]
                    ref_path.write_text(ref_node.to_frontmatter(), encoding="utf-8")
            except (FileNotFoundError, ValueError):
                pass  # El nodo referenciado no existe aun

    def _update_index(self, node: BrainNode) -> None:
        """Agrega o actualiza un nodo en el indice."""
        index_content = self.index_path.read_text(encoding="utf-8")
        one_liner = node.one_liner()

        # Buscar si el slug ya existe en el indice
        pattern = rf"- \[\[{re.escape(node.slug)}\]\].*"
        if re.search(pattern, index_content):
            # Actualizar linea existente
            index_content = re.sub(pattern, one_liner, index_content)
        else:
            # Agregar bajo la seccion correcta
            type_section = _type_to_section(node.type)
            section_pattern = rf"(## {type_section}\n)"
            if re.search(section_pattern, index_content):
                index_content = re.sub(
                    section_pattern,
                    rf"\1\n{one_liner}\n",
                    index_content,
                )
            else:
                # Agregar seccion si no existe
                index_content += f"\n## {type_section}\n\n{one_liner}\n"

        self.index_path.write_text(index_content, encoding="utf-8")

    def _append_log(self, operation: str, slug: str, extra: str = "") -> None:
        """Agrega una entrada al log append-only."""
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
        entry = f"## [{now}] {operation} | {slug}"
        if extra:
            entry += f"\n{extra}"
        entry += "\n\n"

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def _load_index(self) -> dict[str, str]:
        """Carga el indice como dict slug -> one_liner."""
        if self._index_cache is not None:
            return self._index_cache

        entries: dict[str, str] = {}
        if not self.index_path.exists():
            return entries

        content = self.index_path.read_text(encoding="utf-8")
        for match in re.finditer(r"- \[\[([^\]]+)\]\](.*)", content):
            slug = match.group(1)
            rest = match.group(2).strip()
            entries[slug] = f"{slug} {rest}"

        self._index_cache = entries
        return entries

    def _find_node_file(self, slug: str) -> Path:
        """Encuentra el archivo de un nodo por slug.

        Valida que slug sea alfanumerico puro para prevenir path traversal
        (HIGH-01 de auditoriajp 2026-05-13).
        """
        if not slug or not _SLUG_PATTERN.match(slug):
            raise ValueError(
                f"Slug invalido: {slug!r}. "
                f"Debe coincidir con {str(_SLUG_PATTERN.pattern)!r}"
            )
        for directory in [self.sessions_dir, self.concepts_dir, self.connections_dir]:
            path = (directory / f"{slug}.md").resolve()
            if not str(path).startswith(str(directory.resolve())):
                raise ValueError(f"Path traversal detectado en slug: {slug!r}")
            if path.exists():
                return path
        raise FileNotFoundError(f"Nodo '{slug}' no encontrado en brain {self.app_id}")

    def _all_node_files(self) -> list[Path]:
        """Lista todos los archivos de nodos."""
        files: list[Path] = []
        for directory in [self.sessions_dir, self.concepts_dir, self.connections_dir]:
            if directory.exists():
                files.extend(directory.glob("*.md"))
        return files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
