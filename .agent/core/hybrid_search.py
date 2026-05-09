#!/usr/bin/env python3
"""
Hybrid Search - Busqueda combinada SQLite + ChromaDB.

Combina busqueda exacta (SQLite) con busqueda semantica (ChromaDB)
para encontrar observaciones, decisiones y patrones relevantes.

El patron hibrido permite:
- SQLite: Filtros exactos por fecha, tipo, archivo, sesion
- ChromaDB: Busqueda semantica por contenido y significado
- Fusion: Combina resultados con scoring ponderado

Usage:
    from .hybrid_search import get_hybrid_search

    search = get_hybrid_search()

    # Busqueda hibrida
    results = search.search("configuracion de autenticacion", limit=10)

    # Busqueda solo SQL
    results = search.search_sql("auth", filters={"type": "file_edit"})

    # Busqueda solo semantica
    results = search.search_semantic("como se implemento el login")

v1.0.0 - 2026-02-22
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.hybrid_search")


# ---------------------------------------------------------------------------
# BM25 Scorer (Okapi BM25 — implementación pura Python)
# ---------------------------------------------------------------------------


class BM25Scorer:
    """Implementación de Okapi BM25 para scoring de texto.

    Parámetros:
        k1: Saturación de frecuencia de término (default 1.5)
        b: Normalización por longitud de documento (default 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._corpus_size: int = 0
        self._avg_doc_len: float = 0.0
        self._doc_freqs: Counter[str] = Counter()
        self._doc_count: int = 0

    def fit(self, documents: list[str]) -> None:
        """Ajusta IDF con un corpus de documentos."""
        self._corpus_size = len(documents)
        total_len = 0
        self._doc_freqs = Counter()

        for doc in documents:
            words = set(doc.lower().split())
            for w in words:
                self._doc_freqs[w] += 1
            total_len += len(doc.split())

        self._avg_doc_len = total_len / max(self._corpus_size, 1)
        self._doc_count = self._corpus_size

    def score(self, query: str, document: str) -> float:
        """Calcula BM25 score de un documento contra una query.

        Si no se ha hecho fit(), usa valores por defecto razonables.
        """
        query_words = query.lower().split()
        doc_words = document.lower().split()
        doc_len = len(doc_words)
        doc_tf = Counter(doc_words)

        if doc_len == 0 or not query_words:
            return 0.0

        avg_dl = self._avg_doc_len if self._avg_doc_len > 0 else max(doc_len, 1)
        n_docs = max(self._doc_count, 1)

        total = 0.0
        for term in query_words:
            tf = doc_tf.get(term, 0)
            if tf == 0:
                continue

            # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            df = self._doc_freqs.get(term, 1)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

            # TF con saturación y normalización por longitud
            tf_norm = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * doc_len / avg_dl)
            )

            total += idf * tf_norm

        # Normalizar a rango 0-1 (heurística)
        return min(1.0, total / max(len(query_words) * 2, 1))


# BM25 scorer singleton
_bm25_scorer = BM25Scorer()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """Resultado de busqueda unificado."""

    id: str
    source: str  # "sqlite", "chroma", "hybrid"
    content: str
    score: float  # 0.0 - 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    result_type: str = ""  # "observation", "decision", "pattern", "error"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "result_type": self.result_type,
        }


@dataclass
class SearchQuery:
    """Query de busqueda con filtros."""

    text: str
    limit: int = 10
    min_score: float = 0.1
    filters: dict[str, Any] = field(default_factory=dict)
    date_from: str | None = None
    date_to: str | None = None
    result_types: list[str] | None = None
    session_id: str | None = None


# ---------------------------------------------------------------------------
# SQLite Search Strategy
# ---------------------------------------------------------------------------


class SQLiteSearchStrategy:
    """Busqueda exacta en la base de datos SQLite de observaciones."""

    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root).resolve() if project_root else Path(".").resolve()
        self._pipeline: Any = None

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            try:
                from .observation_pipeline import get_observation_pipeline

                self._pipeline = get_observation_pipeline(str(self._root))
            except ImportError:
                logger.debug("ObservationPipeline no disponible para SQLite search")
        return self._pipeline

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Busca en observaciones SQLite."""
        pipeline = self._get_pipeline()
        if not pipeline:
            return []

        results: list[SearchResult] = []

        # Busqueda por texto
        observations = pipeline._store.search_observations(query.text, limit=query.limit * 2)

        for obs in observations:
            # Aplicar filtros adicionales
            if query.session_id and obs.session_id != query.session_id:
                continue
            if query.date_from and obs.timestamp < query.date_from:
                continue
            if query.date_to and obs.timestamp > query.date_to:
                continue
            if query.filters:
                obs_type = query.filters.get("type")
                if obs_type and obs.observation_type != obs_type:
                    continue
                tool = query.filters.get("tool")
                if tool and obs.tool_name != tool:
                    continue

            # Calcular score basado en coincidencia textual
            score = self._calculate_text_score(
                query.text,
                obs.tool_input_summary + " " + obs.tool_output_summary,
            )

            if score < query.min_score:
                continue

            results.append(
                SearchResult(
                    id=obs.id,
                    source="sqlite",
                    content=obs.to_context_string(),
                    score=score,
                    metadata={
                        "tool_name": obs.tool_name,
                        "observation_type": obs.observation_type,
                        "files_affected": obs.files_affected,
                        "session_id": obs.session_id,
                        "success": obs.success,
                    },
                    timestamp=obs.timestamp,
                    result_type="observation",
                )
            )

        # Ordenar por score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[: query.limit]

    def _calculate_text_score(self, query: str, text: str) -> float:
        """Calcula score de coincidencia usando BM25 (Okapi BM25)."""
        if not text:
            return 0.0
        q = query.lower()
        t = text.lower()
        # Boost si la query aparece como substring directa (paths, ids, etc.)
        if q in t:
            return 0.9
        return _bm25_scorer.score(query, text)


# ---------------------------------------------------------------------------
# ChromaDB Search Strategy
# ---------------------------------------------------------------------------


class ChromaSearchStrategy:
    """Busqueda semantica usando ChromaDB."""

    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root).resolve() if project_root else Path(".").resolve()
        self._collection: Any = None
        self._client: Any = None

    def _ensure_collection(self) -> bool:
        """Inicializa ChromaDB collection (lazy)."""
        if self._collection is not None:
            return True

        try:
            import chromadb

            project_hash = hashlib.sha256(str(self._root).encode()).hexdigest()[:16]
            persist_dir = str(Path.home() / ".antigravity" / "projects" / project_hash / "chroma")
            self._client = chromadb.PersistentClient(path=persist_dir)
            self._collection = self._client.get_or_create_collection(
                name="observations",
                metadata={"hnsw:space": "cosine"},
            )
            return True
        except ImportError:
            logger.debug("ChromaDB no disponible para busqueda semantica")
            return False
        except Exception as e:
            logger.debug("Error inicializando ChromaDB: %s", e)
            return False

    def index_observation(self, obs_id: str, content: str, metadata: dict) -> None:
        """Indexa una observacion en ChromaDB."""
        if not self._ensure_collection():
            return

        try:
            # Limpiar metadata para ChromaDB (solo primitivos)
            clean_meta = {}
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                elif isinstance(v, list) and v:
                    clean_meta[k] = json.dumps(v)

            self._collection.upsert(
                ids=[obs_id],
                documents=[content],
                metadatas=[clean_meta],
            )
        except Exception as e:
            logger.debug("Error indexando en ChromaDB: %s", e)

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Busca semanticamente en ChromaDB."""
        if not self._ensure_collection():
            return []

        try:
            # Construir filtros ChromaDB
            where_filter = None
            if query.filters:
                conditions = []
                for k, v in query.filters.items():
                    if isinstance(v, str):
                        conditions.append({k: v})
                if len(conditions) == 1:
                    where_filter = conditions[0]
                elif len(conditions) > 1:
                    where_filter = {"$and": conditions}  # type: ignore[dict-item]  # chromadb where syntax

            chroma_results = self._collection.query(
                query_texts=[query.text],
                n_results=min(query.limit, 20),
                where=where_filter,
            )

            results: list[SearchResult] = []
            if not chroma_results or not chroma_results.get("ids"):
                return results

            ids = chroma_results["ids"][0]
            documents = chroma_results["documents"][0]
            distances = chroma_results.get("distances", [[]])[0]
            metadatas = chroma_results.get("metadatas", [[]])[0]

            for i, doc_id in enumerate(ids):
                # Convertir distancia coseno a score (1 - distance)
                distance = distances[i] if i < len(distances) else 0.5
                score = max(0.0, 1.0 - distance)

                if score < query.min_score:
                    continue

                meta = metadatas[i] if i < len(metadatas) else {}
                results.append(
                    SearchResult(
                        id=doc_id,
                        source="chroma",
                        content=documents[i] if i < len(documents) else "",
                        score=score,
                        metadata=meta,
                        timestamp=meta.get("timestamp", ""),
                        result_type=meta.get("result_type", "observation"),
                    )
                )

            return results

        except Exception as e:
            logger.debug("Error en busqueda ChromaDB: %s", e)
            return []


# ---------------------------------------------------------------------------
# Hybrid Search (Fusion)
# ---------------------------------------------------------------------------


class HybridSearch:
    """Busqueda hibrida que combina SQLite y ChromaDB.

    Estrategia de fusion:
    - Ejecuta ambas busquedas en paralelo
    - Combina resultados con scoring ponderado
    - SQLite weight: 0.4 (precision exacta)
    - ChromaDB weight: 0.6 (relevancia semantica)
    - Deduplica por ID
    - Ordena por score combinado
    """

    SQLITE_WEIGHT = 0.4
    CHROMA_WEIGHT = 0.6

    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root).resolve() if project_root else Path(".").resolve()
        self._sqlite = SQLiteSearchStrategy(str(self._root))
        self._chroma = ChromaSearchStrategy(str(self._root))

    def search(
        self,
        query_text: str,
        limit: int = 10,
        min_score: float = 0.1,
        filters: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> list[SearchResult]:
        """Busqueda hibrida combinando SQLite y ChromaDB.

        Args:
            query_text: Texto de busqueda
            limit: Maximo de resultados
            min_score: Score minimo (0.0-1.0)
            filters: Filtros adicionales (type, tool, etc.)
            session_id: Filtrar por sesion

        Returns:
            Lista de SearchResult ordenados por score
        """
        query = SearchQuery(
            text=query_text,
            limit=limit * 2,  # Pedir mas para fusionar
            min_score=min_score,
            filters=filters or {},
            session_id=session_id,
        )

        # Ejecutar ambas busquedas
        sqlite_results = self._sqlite.search(query)
        chroma_results = self._chroma.search(query)

        # Fusionar resultados
        return self._fuse_results(sqlite_results, chroma_results, limit, min_score)

    def search_sql(
        self,
        query_text: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Busqueda solo SQLite (exacta)."""
        query = SearchQuery(
            text=query_text,
            limit=limit,
            filters=filters or {},
        )
        return self._sqlite.search(query)

    def search_semantic(
        self,
        query_text: str,
        limit: int = 10,
        min_score: float = 0.2,
    ) -> list[SearchResult]:
        """Busqueda solo ChromaDB (semantica)."""
        query = SearchQuery(
            text=query_text,
            limit=limit,
            min_score=min_score,
        )
        return self._chroma.search(query)

    def index_observation(self, obs_id: str, content: str, metadata: dict) -> None:
        """Indexa una observacion en ChromaDB para busqueda semantica."""
        self._chroma.index_observation(obs_id, content, metadata)

    # MMR parameters — λ balances relevance vs diversity (0=max diversity, 1=max relevance)
    MMR_LAMBDA = 0.7
    MMR_ENABLED = True

    # RRF constant (standard value from literature)
    RRF_K = 60

    def _fuse_results(
        self,
        sqlite_results: list[SearchResult],
        chroma_results: list[SearchResult],
        limit: int,
        min_score: float,
    ) -> list[SearchResult]:
        """Fusiona resultados usando Reciprocal Rank Fusion (RRF) + MMR diversity.

        RRF formula: score(d) = sum(1 / (k + rank_i)) para cada lista de ranking.
        Esto es más robusto que el promedio ponderado porque no depende de la
        calibración de los scores individuales.
        """
        # Calcular RRF scores
        rrf_scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        # Ranking SQLite (BM25)
        for rank, r in enumerate(sqlite_results):
            rrf_scores[r.id] = rrf_scores.get(r.id, 0.0) + 1.0 / (self.RRF_K + rank + 1)
            result_map[r.id] = r

        # Ranking ChromaDB (semántico)
        for rank, r in enumerate(chroma_results):
            rrf_scores[r.id] = rrf_scores.get(r.id, 0.0) + 1.0 / (self.RRF_K + rank + 1)
            if r.id in result_map:
                result_map[r.id].source = "hybrid"
            else:
                result_map[r.id] = r

        # Normalizar scores RRF al rango 0-1
        max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0
        for rid in rrf_scores:
            rrf_scores[rid] = rrf_scores[rid] / max_rrf if max_rrf > 0 else 0.0

        # Crear resultados finales
        fused: list[SearchResult] = []
        for rid, result in result_map.items():
            combined_score = rrf_scores.get(rid, 0.0)
            if combined_score < min_score:
                continue

            result.score = round(combined_score, 4)
            fused.append(result)

        # Ordenar por score RRF
        fused.sort(key=lambda r: r.score, reverse=True)

        # Aplicar MMR para diversificar resultados
        if self.MMR_ENABLED and len(fused) > limit:
            fused = self._apply_mmr(fused, limit)

        return fused[:limit]

    def _apply_mmr(
        self,
        results: list[SearchResult],
        limit: int,
    ) -> list[SearchResult]:
        """Aplica Maximal Marginal Relevance para diversificar resultados.

        MMR re-rankea penalizando redundancia entre documentos ya seleccionados.
        Usa similitud por n-gramas de contenido como proxy cuando no hay embeddings.

        Fórmula: MMR(d) = λ * Sim(d, Q) - (1-λ) * max(Sim(d, d_selected))

        Inspirado en el MMR de OpenClaw que combina vector + BM25 + temporal decay.

        Args:
            results: Resultados pre-ordenados por relevancia.
            limit: Cantidad deseada de resultados.

        Returns:
            Lista re-rankeada con mayor diversidad.
        """
        if len(results) <= 1:
            return results

        lam = self.MMR_LAMBDA
        selected: list[SearchResult] = [results[0]]  # El más relevante siempre entra
        candidates = list(results[1:])

        while len(selected) < limit and candidates:
            best_score = -1.0
            best_idx = 0

            for i, candidate in enumerate(candidates):
                # Relevancia: score original normalizado
                relevance = candidate.score

                # Penalización por redundancia: max similaridad con seleccionados
                max_sim = 0.0
                for s in selected:
                    sim = self._content_similarity(candidate.content, s.content)
                    max_sim = max(max_sim, sim)

                # MMR score
                mmr_score = lam * relevance - (1 - lam) * max_sim
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected.append(candidates.pop(best_idx))

        return selected

    @staticmethod
    def _content_similarity(a: str, b: str) -> float:
        """Calcula similitud entre dos textos usando n-gramas de palabras.

        Usa coeficiente de Jaccard sobre bigramas para medir solapamiento.

        Args:
            a: Primer texto.
            b: Segundo texto.

        Returns:
            Similitud entre 0.0 y 1.0.
        """

        def _bigrams(text: str) -> set[tuple[str, str]]:
            words = text.lower().split()
            if len(words) < 2:
                return {(w, "") for w in words}
            return {(words[i], words[i + 1]) for i in range(len(words) - 1)}

        bg_a = _bigrams(a)
        bg_b = _bigrams(b)

        if not bg_a or not bg_b:
            return 0.0

        intersection = len(bg_a & bg_b)
        union = len(bg_a | bg_b)
        return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_search_instances: dict[str, HybridSearch] = {}


def get_hybrid_search(project_root: str | None = None) -> HybridSearch:
    """Obtiene instancia singleton de HybridSearch."""
    root = Path(project_root).resolve() if project_root else Path(".").resolve()
    key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    if key not in _search_instances:
        _search_instances[key] = HybridSearch(str(root))
    return _search_instances[key]
