"""Motor Brain: clase principal de conocimiento estructurado por app.

Extraido del monolito ``brain.py`` (refactor 2026-05-31). Sin cambios de
comportamiento: la clase ``Brain`` se movio verbatim y los helpers/modelos/
constantes ahora se importan de sus submodulos (``constants``, ``dates``,
``text``, ``models``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .constants import (
    MAX_RELATED,
    MAX_TAGS,
    SLUG_MAX_WORDS,
    VALID_STATUSES,
    VALID_TYPES,
    _SLUG_PATTERN,
)
from .dates import _date_sort_key, _parse_date_value
from .models import BrainNode, LintIssue, LintReport
from .text import (
    _ascii_slug_words,
    _expand_keywords,
    _extract_keywords,
    _smart_score,
    _type_to_section,
    scrub_surrogates,
)

logger = logging.getLogger(__name__)

_embeddings_unavailable_warned = False  # Guard modulo: avisa una sola vez, no en cada query()


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
        # Stats de acceso en sidecar (gitignored): evita reescribir los .md
        # versionados en cada read/query (churn). Ver get_node / _track_access.
        self.access_stats_path = self.brain_dir / ".access_stats.json"

        # Crear estructura si no existe
        self._ensure_structure()

        # Cache del indice
        self._index_cache: dict[str, str] | None = None
        # Firma (mtime, size) de index.md cuando se cargó el cache — detecta
        # escrituras externas (otra instancia/proceso) para no servir stale.
        self._index_signature: tuple[float, int] | None = None

        # Cache del indice de metadatos (type, area, status, tags) por slug.
        # Se construye una vez leyendo todos los frontmatters y se invalida
        # en los mismos puntos donde se invalida _index_cache.
        self._meta_index_cache: dict[str, dict[str, Any]] | None = None
        # Firma del directorio (cantidad + mtime máximo) cuando se construyó el cache.
        # Detecta cambios EXTERNOS (otra instancia/proceso ingestó) para no servir
        # un meta_index stale cross-instancia. Ver _node_meta_index().
        self._meta_index_signature: tuple[int, float] | None = None

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
        slug_hint: str = "",
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
            slug_hint: Texto alternativo para derivar el slug cuando el
                titulo no aporta palabras ASCII (ej. titulos en japones).

        Returns:
            El BrainNode creado.

        Raises:
            ValueError: si node_type no esta en VALID_TYPES.
        """
        if node_type not in VALID_TYPES:
            raise ValueError(f"node_type invalido: {node_type!r}. Validos: {sorted(VALID_TYPES)}")

        tags = (tags or [])[:MAX_TAGS]
        sources = sources or []
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Generar slug
        slug = self._generate_slug(title, today, hint=slug_hint)

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

        # Invalidar caches
        self._index_cache = None
        self._meta_index_cache = None

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
        self._meta_index_cache = None
        return node

    # ----- QUERY -----

    def query(self, question: str, *, limit: int = 5) -> list[BrainNode]:
        """Busca nodos relevantes con scoring inteligente + rank fusion.

        Estrategia multi-factor:
        1. Keywords + fuzzy matching + semantic expansion
        2. Embedding similarity real (sentence-transformers, con fallback
           best-effort a un proxy de keyword_score si el modelo no esta disponible)
        3. Rank fusion: hybrid score combining keyword + embedding relevance
        4. Freshness scoring (nodos recientes pesan mas)
        5. Importance weighting (critical > high > normal > low)
        6. Access popularity (nodos mas consultados rankean mejor)

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
        keyword_scores: dict[str, float] = {}

        for slug, one_liner in index_entries.items():
            # Score por keywords + fuzzy
            score = _smart_score(one_liner.lower(), expanded)
            if score > 0:
                keyword_scores[slug] = score

        if not keyword_scores:
            return []

        # Embedding real (sentence-transformers) para los candidatos que ya pasaron
        # el filtro de keywords. Best-effort: si no hay modelo disponible, devuelve
        # {} y cada candidato cae al proxy `keyword_score * 0.9` (comportamiento MVP).
        embedding_scores = self._embedding_scores(question, list(keyword_scores.keys()))

        candidates: list[tuple[str, float]] = []
        for slug, keyword_score in keyword_scores.items():
            embedding_score = embedding_scores.get(slug, keyword_score * 0.9)

            # Rank fusion: hybrid score (60% embedding + 40% keyword)
            hybrid_score = embedding_score * 0.6 + keyword_score * 0.4

            candidates.append((slug, hybrid_score))

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

            # Score compuesto: mayor peso a relevancia hibrida
            final_score = (
                base_score * 0.6  # Relevancia hibrida (keyword + embedding)
                + freshness * 2.5  # Frescura temporal
                + imp_factor * 1.0  # Importancia
                + min(node.access_count * 0.05, 1.0)  # Popularidad
            )
            enriched.append((node, final_score))

        # Paso 3: Ordenar por score final
        enriched.sort(key=lambda x: x[1], reverse=True)
        return [node for node, _ in enriched[:limit]]

    def _embedding_scores(self, question: str, slugs: list[str]) -> dict[str, float]:
        """Similaridad semantica real (sentence-transformers) para el rank fusion.

        Delega a ``compute_brain_embeddings.query_similarity`` (``.agent/scripts/``),
        que cachea los vectores por nodo en ``<brain_dir>/.embeddings_cache.npz``.
        Best-effort y no-fatal: si sentence-transformers/torch no estan instalados,
        o cualquier otra falla ocurre, devuelve ``{}`` para que ``query()`` caiga
        de vuelta al proxy ``keyword_score * 0.9`` — Brain sigue siendo standalone.

        Args:
            question: Pregunta original del usuario.
            slugs: Slugs candidatos (ya filtrados por keyword match).

        Returns:
            ``{slug: cosine_similarity}`` en ``[0, 1]``, o ``{}`` si no disponible.
        """
        if not slugs:
            return {}
        try:
            scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
            scripts_path = str(scripts_dir)
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)
            from compute_brain_embeddings import query_similarity  # type: ignore[import-not-found]

            return query_similarity(self.brain_dir, question, slugs)
        except Exception as exc:  # noqa: BLE001 — best-effort, nunca debe romper query()
            global _embeddings_unavailable_warned
            if not _embeddings_unavailable_warned:
                logger.warning(
                    "Brain corriendo en modo keyword-only: embeddings no disponibles (%s)", exc
                )
                _embeddings_unavailable_warned = True
            else:
                logger.debug("Embeddings no disponibles, fallback a keyword proxy: %s", exc)
            return {}

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
            self._track_access(node)

        return node

    def _load_access_stats(self) -> dict[str, dict[str, Any]]:
        """Carga el sidecar de stats de acceso (tolerante a ausencia/corrupcion)."""
        try:
            return json.loads(self.access_stats_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_access_stats(self, stats: dict[str, dict[str, Any]]) -> None:
        """Persiste el sidecar de stats de acceso (gitignored)."""
        try:
            self.access_stats_path.write_text(
                json.dumps(scrub_surrogates(stats), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.warning("No se pudo escribir %s", self.access_stats_path)

    def _track_access(self, node: BrainNode) -> None:
        """Registra un acceso al nodo en el sidecar, sin reescribir el .md versionado.

        Antes get_node reescribia el archivo del nodo en cada read, ensuciando git en
        cada query/test (churn recurrente). Ahora el contador vive en
        `.access_stats.json` (gitignored). El conteo se siembra del frontmatter la
        primera vez y luego se incrementa en el sidecar.
        """
        stats = self._load_access_stats()
        entry = stats.get(node.slug, {})
        count = int(entry.get("count", node.access_count)) + 1
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
        stats[node.slug] = {"count": count, "last_accessed": now}
        self._save_access_stats(stats)
        node.access_count = count
        node.last_accessed = now

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
        # Filtrar slugs usando el índice de metadatos (sin leer el body del nodo).
        # Solo se leen los archivos completos para los slugs que superan el filtro.
        meta_index = self._node_meta_index()
        matching_files: list[Path] = []
        for slug, meta in meta_index.items():
            if node_type and meta["type"] != node_type:
                continue
            if area and meta["area"] != area:
                continue
            if status and meta["status"] != status:
                continue
            if tag and tag not in meta["tags"]:
                continue
            matching_files.append(meta["file"])

        nodes = []
        for md_file in matching_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
            except (ValueError, yaml.YAMLError):
                continue
            nodes.append(node)

        nodes.sort(key=_date_sort_key, reverse=True)
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
        inbound_links: dict[str, set[str]] = {}
        tag_counts: dict[str, int] = {}
        index_entries = self._load_index()

        # Paso 1: Cargar todos los nodos
        all_nodes, all_slugs = self._lint_load_nodes(report)
        report.total_nodes = len(all_nodes)

        # Paso 2: Analizar relaciones y tags
        for node in all_nodes:
            self._lint_check_node_relations(
                node, all_nodes, all_slugs, index_entries, inbound_links, tag_counts, report
            )

        # Paso 3: Detectar orphans
        self._lint_detect_orphans(all_nodes, inbound_links, report)

        # Paso 4: Detectar conceptos emergentes
        self._lint_detect_emerging_concepts(all_nodes, all_slugs, tag_counts, report)

        # Paso 5: Contar nodos sanos
        problematic_slugs = {
            issue.node_slug
            for issue in report.issues
            if issue.severity in {"error", "warning"} and issue.node_slug
        }
        report.healthy_nodes = len([n for n in all_nodes if n.slug not in problematic_slugs])

        return report

    def _lint_load_nodes(self, report: LintReport) -> tuple[list[BrainNode], set[str]]:
        """Carga todos los nodos del brain y registra frontmatter invalido.

        Args:
            report: Reporte de lint a enriquecer con issues de parseo.

        Returns:
            Tupla con la lista de nodos cargados y el set de sus slugs.
        """
        all_nodes: list[BrainNode] = []
        all_slugs: set[str] = set()
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
        return all_nodes, all_slugs

    def _lint_check_node_relations(
        self,
        node: BrainNode,
        all_nodes: list[BrainNode],
        all_slugs: set[str],
        index_entries: dict[str, str],
        inbound_links: dict[str, set[str]],
        tag_counts: dict[str, int],
        report: LintReport,
    ) -> None:
        """Audita links, tags, bidireccionalidad y sincronia con indice de un nodo.

        Args:
            node: Nodo a auditar.
            all_nodes: Todos los nodos cargados (para resolver referencias).
            all_slugs: Set de slugs existentes.
            index_entries: Slugs presentes en el indice.
            inbound_links: Acumulador de links entrantes (se muta in-place).
            tag_counts: Acumulador de conteo de tags (se muta in-place).
            report: Reporte de lint a enriquecer con issues.
        """
        # Verificar broken links y registrar inbound
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

    def _lint_detect_orphans(
        self,
        all_nodes: list[BrainNode],
        inbound_links: dict[str, set[str]],
        report: LintReport,
    ) -> None:
        """Detecta nodos activos sin links entrantes ni salientes.

        Args:
            all_nodes: Todos los nodos cargados.
            inbound_links: Mapa de slug → slugs que lo referencian.
            report: Reporte de lint a enriquecer con issues.
        """
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

    def _lint_detect_emerging_concepts(
        self,
        all_nodes: list[BrainNode],
        all_slugs: set[str],
        tag_counts: dict[str, int],
        report: LintReport,
    ) -> None:
        """Detecta tags frecuentes (3+ nodos) sin un nodo concepto propio.

        Args:
            all_nodes: Todos los nodos cargados.
            all_slugs: Set de slugs existentes.
            tag_counts: Conteo de tags acumulado.
            report: Reporte de lint a enriquecer con candidatos e issues.
        """
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
                for node in sorted(type_nodes, key=_date_sort_key, reverse=True):
                    lines.append(node.one_liner())
            else:
                lines.append("_Sin nodos._")
            lines.append("")

        self.index_path.write_text(scrub_surrogates("\n".join(lines)), encoding="utf-8")
        self._index_cache = None
        self._meta_index_cache = None
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

        # Cargar todos los nodos y contar inbound links
        all_nodes, inbound = self._load_nodes_with_inbound()

        today = datetime.now(UTC)

        for node in all_nodes:
            if node.status != "active":
                continue
            if node.importance == "critical":
                kept.append(node.slug)
                continue

            created = _parse_date_value(node.date)
            if created is None:
                age_days = 0
            else:
                age_days = (today.replace(tzinfo=None) - created).days

            is_orphan = inbound.get(node.slug, 0) == 0 and not node.related

            if self._should_archive_node(
                node,
                age_days=age_days,
                is_orphan=is_orphan,
                min_age_days=min_age_days,
                max_orphan_age_days=max_orphan_age_days,
            ):
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

    def _load_nodes_with_inbound(self) -> tuple[list[BrainNode], dict[str, int]]:
        """Carga todos los nodos y cuenta sus links entrantes.

        Returns:
            Tupla con la lista de nodos cargados y un mapa slug → cantidad de
            referencias entrantes. Los nodos con frontmatter invalido se ignoran.
        """
        all_nodes: list[BrainNode] = []
        inbound: dict[str, int] = {}
        for md_file in self._all_node_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
                all_nodes.append(node)
                for ref in node.related:
                    inbound[ref] = inbound.get(ref, 0) + 1
            except (ValueError, yaml.YAMLError):
                continue
        return all_nodes, inbound

    def _should_archive_node(
        self,
        node: BrainNode,
        *,
        age_days: int,
        is_orphan: bool,
        min_age_days: int,
        max_orphan_age_days: int,
    ) -> bool:
        """Decide si un nodo debe archivarse segun las reglas de consolidacion.

        Args:
            node: Nodo candidato a archivar.
            age_days: Edad del nodo en dias.
            is_orphan: True si el nodo no tiene links entrantes ni salientes.
            min_age_days: Edad minima para considerar archivado.
            max_orphan_age_days: Edad para archivar huerfanos.

        Returns:
            True si el nodo cumple alguna regla de archivado.
        """
        # Huerfanos viejos → archivar
        if is_orphan and age_days > max_orphan_age_days:
            return True

        # Nodos low importance + viejos + sin acceso → archivar
        if node.importance == "low" and age_days > min_age_days and node.access_count < 3:
            return True

        # Nodos normales muy viejos + sin acceso → archivar
        if node.importance == "normal" and age_days > min_age_days * 2 and node.access_count < 2:
            return True

        return False

    # ----- PRIVATE -----

    def _generate_slug(self, title: str, date: str, *, hint: str = "") -> str:
        """Genera un slug unico: YYYY-MM-DD-kebab-case.

        Titulos sin caracteres latinos (ej. 100% japoneses) no aportan
        palabras ASCII; en ese caso se usa ``hint`` (ej. el stem del archivo
        fuente en el repo-crawler) y, como ultimo recurso, un hash corto
        estable del titulo — nunca se emite un slug vacio tipo "YYYY-MM-DD-".

        Args:
            title: Titulo del nodo.
            date: Fecha YYYY-MM-DD que prefija el slug.
            hint: Texto alternativo para derivar palabras si el titulo no aporta.

        Returns:
            Slug unico dentro del brain.
        """
        words = _ascii_slug_words(title)
        if not words and hint:
            words = _ascii_slug_words(hint)
        if words:
            slug_words = "-".join(words[:SLUG_MAX_WORDS])
        else:
            slug_words = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
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
        """Asegura que todos los related tengan el link reciproco.

        Edita SOLO el campo `related` del frontmatter del nodo referenciado y
        preserva el body markdown byte-a-byte. NO hace round-trip por
        ``BrainNode.from_frontmatter`` -> ``to_frontmatter``, que descartaba
        secciones no canonicas (preambulo, ``## Que se hizo``,
        ``## Descubrimientos``, etc.) y causaba perdida silenciosa de datos en
        el nodo enlazado (bugfix 2026-05-30).
        """
        for ref_slug in node.related:
            try:
                ref_path = self._find_node_file(ref_slug)
            except (FileNotFoundError, ValueError):
                continue  # El nodo referenciado no existe aun (o slug invalido)
            try:
                content = ref_path.read_text(encoding="utf-8")
            except OSError:
                continue
            updated = _add_related_in_frontmatter(content, node.slug)
            if updated is not None and updated != content:
                ref_path.write_text(updated, encoding="utf-8")

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

        self.index_path.write_text(scrub_surrogates(index_content), encoding="utf-8")

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
        """Carga el indice como dict slug -> one_liner.

        Cacheado, pero la firma ``(mtime, size)`` de ``index.md`` se chequea en cada
        llamada: si otra instancia/proceso reescribió el índice, se recarga (evita
        servir un cache stale cross-instancia).
        """
        try:
            st = self.index_path.stat()
            signature = (st.st_mtime, st.st_size)
        except OSError:
            signature = (0.0, 0)
        if self._index_cache is not None and self._index_signature == signature:
            return self._index_cache

        entries: dict[str, str] = {}
        if not self.index_path.exists():
            self._index_cache = entries
            self._index_signature = signature
            return entries

        content = self.index_path.read_text(encoding="utf-8")
        for match in re.finditer(r"- \[\[([^\]]+)\]\](.*)", content):
            slug = match.group(1)
            rest = match.group(2).strip()
            entries[slug] = f"{slug} {rest}"

        self._index_cache = entries
        self._index_signature = signature
        return entries

    def _find_node_file(self, slug: str) -> Path:
        """Encuentra el archivo de un nodo por slug.

        Valida que slug sea alfanumerico puro para prevenir path traversal
        (HIGH-01 de auditoriajp 2026-05-13).
        """
        if not slug or not _SLUG_PATTERN.match(slug):
            raise ValueError(
                f"Slug invalido: {slug!r}. Debe coincidir con {str(_SLUG_PATTERN.pattern)!r}"
            )
        for directory in [self.sessions_dir, self.concepts_dir, self.connections_dir]:
            path = (directory / f"{slug}.md").resolve()
            if not str(path).startswith(str(directory.resolve())):
                raise ValueError(f"Path traversal detectado en slug: {slug!r}")
            if path.exists():
                return path
        raise FileNotFoundError(f"Nodo '{slug}' no encontrado en brain {self.app_id}")

    def _node_meta_index(self) -> dict[str, dict[str, Any]]:
        """Retorna un índice de metadatos de nodos, cacheado hasta la próxima escritura.

        El índice tiene la forma ``{slug: {"type", "area", "status", "tags"}}`` y
        se construye leyendo todos los frontmatters una sola vez. Se invalida en los
        mismos puntos que ``_index_cache`` (ingest, update, rebuild_index) Y cuando
        cambia la firma del directorio (cantidad de archivos + mtime máximo), lo que
        detecta escrituras de OTRA instancia/proceso sobre el mismo brain_dir —
        evita servir un índice stale cross-instancia.

        Returns:
            Diccionario slug → metadatos mínimos necesarios para filtrar.
        """
        files = self._all_node_files()
        # Firma barata: (cantidad, mtime máximo). Detecta add/remove/modify externos
        # sin re-parsear frontmatters. Mucho más barato que leer+parsear los nodos.
        signature = (len(files), max((f.stat().st_mtime for f in files), default=0.0))
        if self._meta_index_cache is not None and self._meta_index_signature == signature:
            return self._meta_index_cache

        index: dict[str, dict[str, Any]] = {}
        for md_file in files:
            try:
                content = md_file.read_text(encoding="utf-8")
                node = BrainNode.from_frontmatter(content, md_file)
            except (ValueError, yaml.YAMLError):
                continue
            index[node.slug] = {
                "type": node.type,
                "area": node.area,
                "status": node.status,
                "tags": node.tags,
                "file": md_file,
            }
        self._meta_index_cache = index
        self._meta_index_signature = signature
        logger.debug("Brain[%s] meta_index construido: %d nodos", self.app_id, len(index))
        return index

    def _all_node_files(self) -> list[Path]:
        """Lista todos los archivos de nodos."""
        files: list[Path] = []
        for directory in [self.sessions_dir, self.concepts_dir, self.connections_dir]:
            if directory.exists():
                files.extend(directory.glob("*.md"))
        return files


def _add_related_in_frontmatter(content: str, new_ref: str) -> str | None:
    """Agrega ``new_ref`` al campo ``related`` del frontmatter sin tocar el body.

    Parsea SOLO el bloque YAML del frontmatter, le agrega la referencia y
    reensambla el archivo conservando el body markdown exactamente como estaba.
    Esto evita la perdida de secciones no canonicas que ocurria al re-serializar
    el nodo completo via ``BrainNode.to_frontmatter`` (bugfix 2026-05-30).

    Args:
        content: Contenido completo del archivo del nodo (frontmatter + body).
        new_ref: Slug a agregar en ``related``.

    Returns:
        El contenido actualizado, o ``None`` si no hay frontmatter valido o si
        ``new_ref`` ya estaba presente (en cuyo caso no hay nada que escribir).
    """
    fm_match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not fm_match:
        return None
    fm_text, body = fm_match.group(1), fm_match.group(2)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    related = fm.get("related")
    if not isinstance(related, list):
        related = []
    if new_ref in related:
        return None  # ya enlazado: sin cambios
    fm["related"] = (related + [new_ref])[:MAX_RELATED]
    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{new_fm}\n---\n{body}"
