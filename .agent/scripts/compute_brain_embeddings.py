#!/usr/bin/env python3
"""Compute real semantic embeddings for Brain nodes (Fase 6 full — sentence-transformers).

Reemplaza el proxy TF-IDF del MVP por ``sentence-transformers``
(``multi-qa-MiniLM-L6-cos-v1``). Los vectores por nodo se cachean en
``<brain_dir>/.embeddings_cache.npz`` (numpy, regenerable, no versionado) y se
invalidan automaticamente cuando ``index.md`` cambia (firma mtime+size, mismo
patron que ``Brain._load_index``).

Uso:
    python compute_brain_embeddings.py --brain-dir .agent/brain
    python compute_brain_embeddings.py --quiet  # Sin output

API publica (usada por ``core.brain.Brain.query()``):
    - compute_embeddings(brain_dir) -> dict[str, float]   # score de centralidad por nodo (legado/CLI)
    - load_node_vectors(brain_dir)  -> (slugs, vectors) | None
    - embed_text(text)              -> np.ndarray | None
    - query_similarity(brain_dir, question, slugs) -> dict[str, float]  # usado en runtime de query()

Si ``sentence-transformers``/``torch`` no estan instalados, todas las funciones
devuelven ``{}``/``None`` en vez de lanzar — el caller debe caer de vuelta a
scoring por keywords (ver ``Brain.query()``).
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "multi-qa-MiniLM-L6-cos-v1"
CACHE_FILENAME = ".embeddings_cache.npz"

_model: Any = None  # SentenceTransformer singleton (lazy)


def embeddings_status() -> dict[str, Any]:
    """Reporta si el modelo de embeddings esta disponible, sin descargarlo ni cargarlo.

    Solo intenta el import de ``sentence_transformers`` (chequeo liviano) — nunca
    instancia ``SentenceTransformer`` ni descarga pesos. Util para observabilidad
    (CLI, health checks) sin pagar el costo/latencia de cargar el modelo.

    Returns:
        ``{"available": bool, "model": MODEL_NAME, "reason": str}``. ``reason`` es
        ``""`` cuando ``available`` es ``True``, o el motivo del fallo si no.
    """
    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        return {"available": False, "model": MODEL_NAME, "reason": str(exc)}
    return {"available": True, "model": MODEL_NAME, "reason": ""}


def _get_model() -> Any:
    """Carga (una vez) el modelo de sentence-transformers.

    Import local a proposito: mantiene el modulo importable sin que
    sentence-transformers/torch esten instalados (fallback no-fatal).
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _load_index_texts(brain_dir: Path) -> dict[str, str]:
    """Lee ``index.md`` y devuelve ``{slug: one_liner}`` (mismo formato que ``Brain._load_index``)."""
    index_path = brain_dir / "index.md"
    entries: dict[str, str] = {}
    if not index_path.is_file():
        return entries
    content = index_path.read_text(encoding="utf-8")
    for match in re.finditer(r"- \[\[([^\]]+)\]\](.*)", content):
        slug = match.group(1)
        rest = match.group(2).strip()
        entries[slug] = f"{slug} {rest}"
    return entries


def _cache_path(brain_dir: Path) -> Path:
    return brain_dir / CACHE_FILENAME


def _index_signature(brain_dir: Path) -> tuple[float, int]:
    """Firma ``(mtime, size)`` de ``index.md`` — invalida el cache cuando cambia."""
    try:
        st = (brain_dir / "index.md").stat()
        return (st.st_mtime, st.st_size)
    except OSError:
        return (0.0, 0)


def build_node_vectors(brain_dir: Path) -> tuple[list[str], np.ndarray] | None:
    """Encodea el one-liner de cada nodo y persiste el cache en disco.

    Returns:
        ``(slugs, vectors)`` donde ``vectors`` esta L2-normalizado (fila por slug,
        mismo orden), o ``None`` si el modelo no esta disponible.
    """
    entries = _load_index_texts(brain_dir)
    if not entries:
        return [], np.zeros((0, 0), dtype="float32")

    try:
        model = _get_model()
    except Exception as exc:
        logger.warning("sentence-transformers no disponible, sin embeddings: %s", exc)
        return None

    slugs = list(entries.keys())
    texts = [entries[slug] for slug in slugs]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
    vectors = np.asarray(vectors, dtype="float32")

    mtime, size = _index_signature(brain_dir)
    try:
        np.savez_compressed(
            _cache_path(brain_dir),
            slugs=np.array(slugs, dtype=object),
            vectors=vectors,
            signature=np.array([mtime, size], dtype="float64"),
        )
    except OSError as exc:
        logger.warning("No se pudo escribir el cache de embeddings: %s", exc)

    return slugs, vectors


def load_node_vectors(
    brain_dir: Path, *, rebuild: bool = False
) -> tuple[list[str], np.ndarray] | None:
    """Carga los vectores cacheados, recalculando si el indice cambio o ``rebuild=True``.

    Returns:
        ``(slugs, vectors)`` o ``None`` si el modelo no esta disponible.
    """
    cache_path = _cache_path(brain_dir)
    if not rebuild and cache_path.is_file():
        try:
            with np.load(cache_path, allow_pickle=True) as data:
                cached_signature = tuple(float(v) for v in data["signature"].tolist())
                if cached_signature == _index_signature(brain_dir):
                    return list(data["slugs"]), data["vectors"]
        except Exception as exc:
            logger.debug("Cache de embeddings invalido, recalculando: %s", exc)

    return build_node_vectors(brain_dir)


def embed_text(text: str) -> np.ndarray | None:
    """Encodea un texto arbitrario (p.ej. una query) con el mismo modelo."""
    if not text or not text.strip():
        return None
    try:
        model = _get_model()
    except Exception as exc:
        logger.debug("No se pudo cargar el modelo de embeddings: %s", exc)
        return None
    vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vector[0], dtype="float32")


def query_similarity(brain_dir: Path, question: str, slugs: list[str]) -> dict[str, float]:
    """Similaridad coseno real entre ``question`` y cada nodo de ``slugs``.

    Usado en runtime por ``Brain.query()`` para el rank fusion. Devuelve ``{}``
    (no lanza) si los embeddings no estan disponibles — el caller debe usar su
    propio fallback (proxy ``keyword_score``).
    """
    if not slugs:
        return {}

    loaded = load_node_vectors(brain_dir)
    if not loaded:
        return {}
    all_slugs, all_vectors = loaded
    if not all_slugs:
        return {}

    query_vector = embed_text(question)
    if query_vector is None:
        return {}

    index_by_slug = {slug: i for i, slug in enumerate(all_slugs)}
    scores: dict[str, float] = {}
    for slug in slugs:
        idx = index_by_slug.get(slug)
        if idx is None:
            continue
        # Vectores L2-normalizados -> el producto punto es la similitud coseno.
        similarity = float(np.dot(all_vectors[idx], query_vector))
        scores[slug] = max(0.0, min(1.0, similarity))
    return scores


def compute_embeddings(brain_dir: Path) -> dict[str, float]:
    """Genera un score de embedding por nodo (interfaz legado para CLI/consumidores).

    Cada score es la similaridad coseno promedio de ese nodo contra el resto del
    corpus (centralidad semantica) — mantiene la firma previa del MVP TF-IDF,
    ahora respaldada por sentence-transformers reales en vez del proxy TF-IDF.
    Como side-effect, persiste/actualiza ``.embeddings_cache.npz`` (usado en
    runtime por ``query_similarity()``).

    Returns:
        ``{slug: score}`` con score en ``[0, 1]``. ``{}`` si el modelo no esta
        disponible o no hay nodos.
    """
    loaded = build_node_vectors(brain_dir)
    if not loaded:
        return {}
    slugs, vectors = loaded
    if len(slugs) < 2:
        return dict.fromkeys(slugs, 0.5)

    similarity_matrix = vectors @ vectors.T
    np.fill_diagonal(similarity_matrix, np.nan)
    avg_similarity = np.nanmean(similarity_matrix, axis=1)
    scores = np.clip(avg_similarity, 0.0, 1.0)
    return dict(zip(slugs, (float(s) for s in scores), strict=True))


def main() -> int:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brain-dir", type=Path, default=Path(".agent/brain"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not args.quiet:
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    if not args.brain_dir.is_dir():
        logger.error("Brain dir not found: %s", args.brain_dir)
        return 1

    embeddings = compute_embeddings(args.brain_dir)
    if not args.quiet:
        if embeddings:
            cache_path = _cache_path(args.brain_dir)
            logger.info("Modelo cargado: %s", MODEL_NAME)
            logger.info("Computed %d embedding scores", len(embeddings))
            logger.info("Cache: %s", cache_path)
        else:
            logger.warning("Sin embeddings (sentence-transformers no disponible o brain vacio)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
