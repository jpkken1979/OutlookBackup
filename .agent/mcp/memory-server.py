#!/usr/bin/env python3
"""
Antigravity Memory MCP Server — Dual Mode
==========================================
Motor de memoria del ecosistema con dos modos:

- **Modo base (siempre activo):** ChromaDB directo + sentence-transformers.
  Funciona offline sin OpenAI/Ollama. Store/recall/search sin LLM.

- **Modo mejorado (cuando Ollama esta disponible):** mem0 con Ollama local.
  Extrae hechos atomicos del texto antes de guardar, mejorando recall.
  Se activa automaticamente al detectar Ollama en localhost:11434.

Tools:
- memory_store: Guardar memoria (con extraccion de hechos si Ollama disponible)
- memory_recall: Recuperar memorias por query semantico
- memory_search: Busqueda con filtros
- memory_delete: Eliminar memoria por ID
- memory_clear_user: Eliminar todas las memorias de un usuario
- memory_stats: Estadisticas del sistema
- memory_suggest: Consulta proactiva — busca trabajo previo antes de crear codigo nuevo
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Silence ChromaDB telemetry errors (PostHog incompatibility in v1.5.5)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

_agent_dir = Path(__file__).parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

# ---------------------------------------------------------------------------
# Optional mem0 import (used when Ollama is available)
# ---------------------------------------------------------------------------
try:
    from mem0 import Memory

    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MEMORY_DIR = Path.home() / ".antigravity" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

CHROMA_PATH = str(MEMORY_DIR / "chroma")
HISTORY_DB_PATH = str(MEMORY_DIR / "history.db")

# Embedding model — local, no API needed
_HF_EMBED_MODEL = os.environ.get("MEM0_EMBED_MODEL", "multi-qa-MiniLM-L6-cos-v1")

# Ollama config


def _get_validated_ollama_base() -> str:
    """Obtiene y valida la URL base de Ollama desde env var."""
    from urllib.parse import urlparse

    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"OLLAMA_BASE_URL tiene scheme invalido '{parsed.scheme}'. "
            "Solo se permiten http:// o https://"
        )
    return url


_OLLAMA_BASE = _get_validated_ollama_base()
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")

# ---------------------------------------------------------------------------
# Lazy-initialized singletons
# ---------------------------------------------------------------------------
_chroma_client: Any = None
_collection: Any = None
_embedder: Any = None
_mem0_instance: Any = None  # mem0 Memory instance (only when Ollama available)
_mem0_mode: bool = False  # True when mem0 enhanced mode is active
_INIT_ERROR: str | None = None


def _ensure_initialized() -> bool:
    """Lazy-initialize ChromaDB and SentenceTransformer.

    Returns:
        True if initialization succeeded, False otherwise.
    """
    global _chroma_client, _collection, _embedder, _INIT_ERROR

    if _collection is not None and _embedder is not None:
        return True

    if _INIT_ERROR is not None:
        # Retry on re-import (gateway re-imports on each request)
        _INIT_ERROR = None

    try:
        import chromadb

        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name="antigravity",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB inicializado en %s", CHROMA_PATH)
    except Exception as e:
        err_msg = str(e)
        # Si ya existe una instancia o hay conflicto interno, reutilizar in-memory
        if "already exists" in err_msg or "different settings" in err_msg or "_type" in err_msg:
            try:
                import chromadb

                _chroma_client = chromadb.Client()
                _collection = _chroma_client.get_or_create_collection(
                    name="antigravity",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("ChromaDB reutilizado (instancia existente)")
            except Exception as e2:
                _INIT_ERROR = f"ChromaDB no disponible: {e2}"
                logger.error(_INIT_ERROR)
                return False
        else:
            _INIT_ERROR = f"ChromaDB no disponible: {e}"
            logger.error(_INIT_ERROR)
            return False

    try:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(_HF_EMBED_MODEL)
        logger.info("SentenceTransformer cargado: %s", _HF_EMBED_MODEL)
    except Exception as e:
        _INIT_ERROR = f"sentence-transformers no disponible: {e}"
        logger.error(_INIT_ERROR)
        _collection = None
        _chroma_client = None
        return False

    # Initialize SQLite history table
    _init_history_db()

    # Try to activate mem0 enhanced mode if Ollama is running
    _try_activate_mem0()

    return True


def _ollama_available() -> bool:
    """Check if Ollama server is running and reachable.

    Returns:
        True if Ollama responds at the configured base URL.
    """
    import urllib.request

    try:
        urllib.request.urlopen(f"{_OLLAMA_BASE}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _try_activate_mem0() -> None:
    """Activate mem0 enhanced mode if mem0ai is installed AND Ollama is running.

    When active, memory_store uses mem0 for fact extraction (better recall).
    When inactive, falls back to ChromaDB direct (always works).
    """
    global _mem0_instance, _mem0_mode

    if _mem0_mode and _mem0_instance is not None:
        return  # Already active

    if not MEM0_AVAILABLE:
        logger.info("mem0ai no instalado -- modo base (ChromaDB directo)")
        return

    if not _ollama_available():
        logger.info("Ollama no disponible -- modo base (ChromaDB directo)")
        _mem0_mode = False
        _mem0_instance = None
        return

    try:
        # mem0 uses a SEPARATE chroma path to avoid PersistentClient collision
        mem0_chroma_path = str(MEMORY_DIR / "chroma_mem0")
        mem0_config: dict[str, Any] = {
            "version": "v1.1",
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "antigravity_mem0",
                    "path": mem0_chroma_path,
                },
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": _HF_EMBED_MODEL,
                },
            },
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": _OLLAMA_MODEL,
                    "ollama_base_url": _OLLAMA_BASE,
                },
            },
        }
        _mem0_instance = Memory.from_config(mem0_config)
        _mem0_mode = True
        logger.info(
            "Modo mejorado activado: mem0 + Ollama (%s) -- extraccion de hechos habilitada",
            _OLLAMA_MODEL,
        )
    except Exception as e:
        logger.warning("mem0 fallo al inicializar con Ollama (%s) -- usando modo base", e)
        _mem0_mode = False
        _mem0_instance = None


def _init_history_db() -> None:
    """Create or migrate the SQLite history table."""
    try:
        conn = sqlite3.connect(HISTORY_DB_PATH)
        # Check if table exists and has the right schema
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
        )
        if cursor.fetchone():
            # Table exists — check if it has the 'content' column
            col_info = conn.execute("PRAGMA table_info(history)").fetchall()
            col_names = {row[1] for row in col_info}
            if "content" not in col_names:
                # Old schema — drop and recreate
                logger.info("Migrando history.db: agregando columnas faltantes")
                conn.execute("DROP TABLE history")
                conn.commit()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                user_id TEXT DEFAULT 'antigravity',
                category TEXT DEFAULT 'general',
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("No se pudo inicializar history.db: %s", e)


def _log_to_history(
    memory_id: str,
    content: str,
    user_id: str,
    category: str,
    metadata: dict[str, Any],
) -> None:
    """Log a memory operation to SQLite history.

    Args:
        memory_id: UUID of the memory.
        content: Text content stored.
        user_id: Owner of the memory.
        category: Category tag.
        metadata: Arbitrary metadata dict.
    """
    try:
        conn = sqlite3.connect(HISTORY_DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO history (id, content, user_id, category, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                memory_id,
                content,
                user_id,
                category,
                datetime.now(UTC).isoformat(),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Error escribiendo en history.db: %s", e)


def _history_counts(user_id: str | None = None) -> tuple[int, int]:
    """Count total and per-user entries in SQLite history."""
    try:
        conn = sqlite3.connect(HISTORY_DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        if user_id:
            user_total = conn.execute(
                "SELECT COUNT(*) FROM history WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
        else:
            user_total = total
        conn.close()
        return int(total), int(user_total)
    except Exception as e:
        logger.warning("No se pudo contar history.db: %s", e)
        return 0, 0


def _store_history_fallback(
    content: str,
    user_id: str,
    metadata: dict[str, Any],
    *,
    status: str,
) -> dict[str, Any]:
    """Store a memory in SQLite when semantic backends are unavailable."""
    memory_id = str(uuid.uuid4())
    category = metadata.get("category", metadata.get("type", "general"))
    _log_to_history(memory_id, content, user_id, category, metadata)
    return {
        "success": True,
        "memories_added": 1,
        "memory_id": memory_id,
        "result": {"results": [{"id": memory_id, "memory": content}]},
        "mode": "sqlite-history",
        "status": status,
    }


def _recall_history_fallback(query: str, user_id: str, limit: int) -> dict[str, Any]:
    """Perform a basic text recall against SQLite history."""
    pattern = f"%{query.lower()}%"
    try:
        conn = sqlite3.connect(HISTORY_DB_PATH)
        rows = conn.execute(
            """
            SELECT id, content, created_at, metadata
            FROM history
            WHERE user_id = ?
              AND LOWER(content) LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, pattern, limit),
        ).fetchall()
        conn.close()
    except Exception as e:
        logger.warning("No se pudo buscar en history.db: %s", e)
        rows = []

    memories = []
    for row in rows:
        raw_metadata = row[3] or "{}"
        try:
            metadata = json.loads(raw_metadata)
        except Exception:
            metadata = {"raw_metadata": raw_metadata}
        memories.append(
            {
                "id": row[0],
                "memory": row[1],
                "score": 0.2,
                "metadata": metadata,
                "created_at": row[2],
            }
        )

    return {
        "success": True,
        "memories": memories,
        "entries": memories,
        "results": memories,
        "total": len(memories),
        "mode": "sqlite-history",
        "status": f"Fallback SQLite activo: {_INIT_ERROR or 'backend semántico no disponible'}",
    }


def _embed(text: str) -> list[float]:
    """Generate embedding vector for text using the local model.

    Args:
        text: Input text to embed.

    Returns:
        List of floats representing the embedding vector.
    """
    return _embedder.encode(text).tolist()  # type: ignore[union-attr]


def _should_skip_enhanced_store(metadata: dict[str, Any]) -> bool:
    """Return True when the caller prefers low-latency storage over fact extraction."""
    if metadata.get("skip_fact_extraction") is True:
        return True
    if metadata.get("bulk_absorb") is True:
        return True
    return metadata.get("source") == "knowledge-absorber"


def _store_chromadb_direct(
    content: str, user_id: str, metadata: dict[str, Any], skip_enhanced: bool
) -> dict[str, Any]:
    """Persiste primero el texto completo y devuelve una respuesta de baja latencia."""
    try:
        memory_id = str(uuid.uuid4())
        embedding = _embed(content)
        now = datetime.now(UTC).isoformat()
        chroma_meta: dict[str, Any] = {
            "user_id": user_id,
            "created_at": now,
            "category": metadata.get("category", metadata.get("type", "general")),
        }
        for key, value in metadata.items():
            if key not in chroma_meta and isinstance(value, (str, int, float, bool)):
                chroma_meta[key] = value

        _collection.add(  # type: ignore[union-attr]
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[chroma_meta],
        )
        _log_to_history(memory_id, content, user_id, chroma_meta["category"], metadata)
        return {
            "success": True,
            "memories_added": 1,
            "memory_id": memory_id,
            "result": {"results": [{"id": memory_id, "memory": content}]},
            "mode": "chromadb-direct",
            "status": "Fast path activo: fact extraction omitida"
            if skip_enhanced
            else "Stored via chromadb-direct",
        }
    except Exception as exc:
        logger.error("memory_store error: %s", exc)
        return {"error": str(exc)}


def _extract_facts_background(
    mem0_instance: Any, content: str, user_id: str, metadata: dict[str, Any]
) -> None:
    """Ejecuta la extracción opcional sin retrasar el reconocimiento MCP."""
    try:
        mem0_instance.add(content, user_id=user_id, metadata=metadata)
    except Exception as exc:
        logger.warning("mem0 fact extraction fallo despues de persistir en ChromaDB: %s", exc)


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


def handle_memory_store(params: dict[str, Any]) -> dict[str, Any]:
    """Guarda contenido en memoria.

    Modo mejorado (Ollama activo): usa mem0 para extraer hechos atomicos.
    Modo base (sin Ollama): guarda texto completo con embeddings locales.

    Args:
        params: Diccionario con content, user_id y metadata opcionales.

    Returns:
        Diccionario con resultado de la operacion o error.
    """
    content = params.get("content", "")
    user_id = params.get("user_id", "antigravity")
    metadata = params.get("metadata", {})
    if not content:
        return {"error": "content es requerido"}

    if not _ensure_initialized():
        return _store_history_fallback(
            content,
            user_id,
            metadata,
            status=f"Fallback SQLite activo: {_INIT_ERROR or 'backend semántico no disponible'}",
        )

    skip_enhanced = _should_skip_enhanced_store(metadata)

    sync_fact_extraction = bool(
        params.get("sync_fact_extraction") or metadata.get("sync_fact_extraction")
    )

    # --- Modo mejorado: mem0 + Ollama (extraccion de hechos) ---
    if _mem0_mode and _mem0_instance is not None and not skip_enhanced:
        if sync_fact_extraction:
            try:
                result = _mem0_instance.add(content, user_id=user_id, metadata=metadata)
                added = result.get("results", [])
                memory_id = added[0].get("id", str(uuid.uuid4())) if added else str(uuid.uuid4())
                _log_to_history(
                    memory_id, content, user_id, metadata.get("category", "general"), metadata
                )
                return {
                    "success": True,
                    "memories_added": len(added),
                    "memory_id": memory_id,
                    "result": result,
                    "mode": "mem0+ollama",
                    "fact_extraction": "sync",
                }
            except Exception as exc:
                logger.warning("mem0 store fallo -- cayendo a chromadb-direct (motivo: %s)", exc)
        else:
            result = _store_chromadb_direct(content, user_id, metadata, skip_enhanced=False)
            if result.get("success"):
                threading.Thread(
                    target=_extract_facts_background,
                    args=(_mem0_instance, content, user_id, metadata),
                    daemon=True,
                ).start()
                result["fact_extraction"] = "queued"
            return result

    # --- Modo base: ChromaDB directo ---
    return _store_chromadb_direct(content, user_id, metadata, skip_enhanced)


def handle_memory_recall(params: dict[str, Any]) -> dict[str, Any]:
    """Recupera memorias relevantes mediante busqueda semantica.

    Args:
        params: Diccionario con query, user_id y limit opcionales.

    Returns:
        Diccionario con memorias encontradas o error.
    """
    query = params.get("query", "")
    user_id = params.get("user_id", "antigravity")
    limit = int(params.get("limit", 10))
    if not query:
        return {"error": "query es requerido"}

    if not _ensure_initialized():
        return _recall_history_fallback(query, user_id, limit)

    try:
        embedding = _embed(query)

        where_filter = {"user_id": user_id} if user_id else None

        results = _collection.query(  # type: ignore[union-attr]
            query_embeddings=[embedding],
            n_results=limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2)
            distance = distances[i] if i < len(distances) else 1.0
            score = 1.0 - (distance / 2.0)
            meta = metas[i] if i < len(metas) else {}
            memories.append(
                {
                    "id": doc_id,
                    "memory": docs[i] if i < len(docs) else "",
                    "score": round(score, 4),
                    "metadata": meta,
                    "created_at": meta.get("created_at", ""),
                }
            )

        return {
            "success": True,
            "memories": memories,
            "entries": memories,
            "total": len(memories),
        }
    except Exception as e:
        logger.error("memory_recall error: %s", e)
        return {"error": str(e), "memories": [], "entries": [], "total": 0}


def handle_memory_search(params: dict[str, Any]) -> dict[str, Any]:
    """Busca memorias aplicando filtros opcionales de metadata.

    Args:
        params: Diccionario con query, filters y limit opcionales.

    Returns:
        Diccionario con memorias encontradas o error.
    """
    query = params.get("query", "")
    filters = params.get("filters", {})
    limit = int(params.get("limit", 10))

    if not _ensure_initialized():
        return {"error": f"Backend no disponible: {_INIT_ERROR}"}

    try:
        embedding = _embed(query) if query else None

        # Build ChromaDB where filter from user-provided filters
        where_filter: dict[str, Any] | None = None
        if filters:
            # ChromaDB where clause expects flat key-value pairs for equality
            chroma_where: dict[str, Any] = {}
            for k, v in filters.items():
                if isinstance(v, (str, int, float, bool)):
                    chroma_where[k] = v
            if chroma_where:
                where_filter = (
                    chroma_where
                    if len(chroma_where) == 1
                    else {"$and": [{k: v} for k, v in chroma_where.items()]}
                )

        if embedding is not None:
            results = _collection.query(  # type: ignore[union-attr]
                query_embeddings=[embedding],
                n_results=limit,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        else:
            # No query text — just get entries with optional filter
            results = _collection.get(  # type: ignore[union-attr]
                where=where_filter,
                limit=limit,
                include=["documents", "metadatas"],
            )
            # Normalize get() response to match query() shape
            results = {
                "ids": [results.get("ids", [])],
                "documents": [results.get("documents", [])],
                "metadatas": [results.get("metadatas", [])],
                "distances": [[]],
            }

        memories = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 1.0
            score = 1.0 - (distance / 2.0) if distances else 1.0
            meta = metas[i] if i < len(metas) else {}
            memories.append(
                {
                    "id": doc_id,
                    "memory": docs[i] if i < len(docs) else "",
                    "score": round(score, 4),
                    "metadata": meta,
                    "created_at": meta.get("created_at", ""),
                }
            )

        return {
            "success": True,
            "memories": memories,
            "total": len(memories),
        }
    except Exception as e:
        logger.error("memory_search error: %s", e)
        return {"error": str(e)}


def handle_memory_delete(params: dict[str, Any]) -> dict[str, Any]:
    """Elimina una memoria por su ID.

    Args:
        params: Diccionario con memory_id requerido.

    Returns:
        Diccionario confirmando la eliminacion o error.
    """
    memory_id = params.get("memory_id", "")
    if not memory_id:
        return {"error": "memory_id es requerido"}

    if not _ensure_initialized():
        return {"error": f"Backend no disponible: {_INIT_ERROR}"}

    try:
        # Registrar count antes del delete para diagnóstico de inconsistencias
        count_before: int = _collection.count()  # type: ignore[union-attr]
        _collection.delete(ids=[memory_id])  # type: ignore[union-attr]
        count_after: int = _collection.count()  # type: ignore[union-attr]
        if count_after >= count_before:
            # Si el count no bajó puede indicar que el ID no existía o cache stale
            logger.warning(
                "memory_delete: count no disminuyo despues del delete "
                "(antes=%d, despues=%d, id=%s) -- el ID puede no haber existido",
                count_before,
                count_after,
                memory_id,
            )

        # Limpiar también en SQLite history (best-effort, pero con logging si falla)
        try:
            conn = sqlite3.connect(HISTORY_DB_PATH)
            conn.execute("DELETE FROM history WHERE id = ?", (memory_id,))
            conn.commit()
            conn.close()
        except Exception as sqlite_err:
            # No es fatal, pero debe ser visible para detectar inconsistencias
            logger.warning(
                "memory_delete: fallo la limpieza en history.db para id=%s: %s",
                memory_id,
                sqlite_err,
            )

        return {"success": True, "deleted": memory_id}
    except Exception as e:
        logger.error("memory_delete error: %s", e)
        return {"error": str(e)}


def handle_memory_clear_user(params: dict[str, Any]) -> dict[str, Any]:
    """Elimina todas las memorias semanticas e historial de un usuario."""
    user_id = str(params.get("user_id", "")).strip()
    if not user_id:
        return {"error": "user_id es requerido"}

    semantic_deleted = 0
    enhanced_deleted = False
    backend_error: str | None = None

    if _ensure_initialized():
        try:
            existing = _collection.get(  # type: ignore[union-attr]
                where={"user_id": user_id},
                include=[],
            )
            ids = list(existing.get("ids", []))
            if ids:
                _collection.delete(ids=ids)  # type: ignore[union-attr]
            semantic_deleted = len(ids)
        except Exception as exc:
            backend_error = str(exc)
            logger.warning("memory_clear_user: fallo ChromaDB para user_id=%s: %s", user_id, exc)

        if _mem0_instance is not None:
            try:
                _mem0_instance.delete_all(user_id=user_id)
                enhanced_deleted = True
            except Exception as exc:
                logger.warning(
                    "memory_clear_user: fallo limpieza mem0 mejorada para user_id=%s: %s",
                    user_id,
                    exc,
                )
    else:
        backend_error = _INIT_ERROR
        _init_history_db()

    history_deleted = 0
    try:
        conn = sqlite3.connect(HISTORY_DB_PATH)
        result = conn.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        history_deleted = int(result.rowcount if result.rowcount >= 0 else 0)
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning(
            "memory_clear_user: fallo history.db para user_id=%s: %s",
            user_id,
            exc,
        )
        if backend_error is None:
            backend_error = str(exc)

    return {
        "success": True,
        "user_id": user_id,
        "semantic_deleted": semantic_deleted,
        "history_deleted": history_deleted,
        "enhanced_mem0_cleared": enhanced_deleted,
        "backend_warning": backend_error,
    }


def handle_memory_stats(params: dict[str, Any]) -> dict[str, Any]:
    """Retorna estadisticas del sistema de memoria.

    Args:
        params: Diccionario con user_id opcional.

    Returns:
        Diccionario con estadisticas o error.
    """
    user_id = params.get("user_id", "antigravity")

    if not _ensure_initialized():
        total, user_total = _history_counts(user_id)
        return {
            "success": True,
            "total": user_total,
            "total_memories": total,
            "mem0_available": False,
            "backend": "sqlite-history",
            "status": f"Fallback SQLite activo: {_INIT_ERROR or 'backend semántico no disponible'}",
            "memory_dir": str(MEMORY_DIR),
            "storage_path": str(MEMORY_DIR),
            "chroma_path": CHROMA_PATH,
            "history_db": HISTORY_DB_PATH,
        }

    # If mem0 wasn't active during initial init, re-check when stats are requested.
    # This recovers cleanly when Ollama starts after the first gateway boot.
    if MEM0_AVAILABLE and _mem0_instance is None and _ollama_available():
        _try_activate_mem0()

    try:
        # Count total entries in collection
        total = _collection.count()  # type: ignore[union-attr]

        # Count entries for specific user
        user_count = total
        try:
            user_results = _collection.get(  # type: ignore[union-attr]
                where={"user_id": user_id},
                include=[],
            )
            user_count = len(user_results.get("ids", []))
        except Exception:
            pass  # If filter fails, use total

        backend = "mem0+ollama" if _mem0_mode else "chromadb-direct"
        ollama_status = (
            "connected" if _mem0_mode else ("available" if _ollama_available() else "offline")
        )
        return {
            "success": True,
            "total": user_count,
            "total_memories": total,
            "memory_dir": str(MEMORY_DIR),
            # Estado real de mem0: True solo si la librería está instalada Y la instancia activa
            "mem0_available": MEM0_AVAILABLE and _mem0_instance is not None,
            "backend": backend,
            "ollama_status": ollama_status,
            "ollama_model": _OLLAMA_MODEL if _mem0_mode else None,
            "chroma_path": CHROMA_PATH,
            "history_db": HISTORY_DB_PATH,
            "embed_model": _HF_EMBED_MODEL,
        }
    except Exception as e:
        logger.error("memory_stats error: %s", e)
        return {
            "error": str(e),
            "mem0_available": MEM0_AVAILABLE and _mem0_instance is not None,
            "total": 0,
        }


_SUGGEST_RELEVANCE_THRESHOLD = 0.4


def handle_memory_suggest(params: dict[str, Any]) -> dict[str, Any]:
    """Consulta proactiva antes de crear codigo nuevo.

    Busca en la memoria si ya existe algo similar a lo que el usuario
    quiere crear (funcion, componente, patron, modulo). Retorna
    sugerencias con relevancia para evitar trabajo duplicado.

    Args:
        params: Diccionario con intent (requerido), context y type opcionales.

    Returns:
        Diccionario con sugerencias o indicacion de que no hay trabajo previo.
    """
    intent = params.get("intent", "")
    context = params.get("context", "")
    suggest_type = params.get("type", "any")
    if not intent:
        return {"error": "intent es requerido -- describe que vas a crear"}

    query = intent
    if context:
        query = f"{intent} ({context})"
    if suggest_type != "any":
        query = f"{suggest_type}: {query}"

    if not _ensure_initialized():
        return {
            "success": True,
            "has_prior_work": False,
            "suggestions": [],
            "recommendation": "Backend de memoria no disponible. Procede a crear.",
            "query_used": query,
        }

    try:
        embedding = _embed(query)
        results = _collection.query(  # type: ignore[union-attr]
            query_embeddings=[embedding],
            n_results=5,
            include=["documents", "metadatas", "distances"],
        )

        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        suggestions = []
        for i, doc_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 1.0
            score = 1.0 - (distance / 2.0)
            if score < _SUGGEST_RELEVANCE_THRESHOLD:
                continue
            meta = metas[i] if i < len(metas) else {}
            suggestions.append(
                {
                    "memory": docs[i] if i < len(docs) else "",
                    "relevance": round(score, 2),
                    "created_at": meta.get("created_at", ""),
                    "metadata": meta,
                }
            )

        has_prior = len(suggestions) > 0
        recommendation = ""
        if has_prior:
            top = suggestions[0]["memory"]
            recommendation = (
                f'Ya existe trabajo previo similar: "{top[:120]}...". '
                "Considera reutilizarlo antes de crear desde cero."
            )
        else:
            recommendation = "No se encontro trabajo previo relacionado. Procede a crear."

        return {
            "success": True,
            "has_prior_work": has_prior,
            "suggestions": suggestions,
            "recommendation": recommendation,
            "query_used": query,
        }
    except Exception as e:
        logger.error("memory_suggest error: %s", e)
        return {"error": str(e), "has_prior_work": False, "suggestions": []}


TOOLS: dict[str, Any] = {
    "memory_store": handle_memory_store,
    "memory_recall": handle_memory_recall,
    "memory_search": handle_memory_search,
    "memory_delete": handle_memory_delete,
    "memory_clear_user": handle_memory_clear_user,
    "memory_stats": handle_memory_stats,
    "memory_suggest": handle_memory_suggest,
}

TOOL_SCHEMAS: dict[str, Any] = {
    "memory_store": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Texto o hecho a memorizar"},
            "user_id": {
                "type": "string",
                "description": "ID del usuario (default: antigravity)",
            },
            "metadata": {"type": "object", "description": "Metadatos opcionales"},
        },
        "required": ["content"],
    },
    "memory_recall": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Query semantico para recuperar memorias relevantes",
            },
            "user_id": {"type": "string", "description": "ID del usuario"},
            "limit": {
                "type": "integer",
                "description": "Maximo de resultados (default: 10)",
            },
        },
        "required": ["query"],
    },
    "memory_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Texto a buscar"},
            "filters": {
                "type": "object",
                "description": "Filtros opcionales por metadata",
            },
            "limit": {"type": "integer", "description": "Maximo de resultados"},
        },
        "required": ["query"],
    },
    "memory_delete": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "ID de la memoria a eliminar",
            },
        },
        "required": ["memory_id"],
    },
    "memory_clear_user": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "ID cuyas memorias se eliminaran por completo",
            },
        },
        "required": ["user_id"],
    },
    "memory_stats": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "ID del usuario para estadisticas",
            },
        },
    },
    "memory_suggest": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "Que vas a crear (ej: 'funcion para formatear moneda', 'componente de login')",
            },
            "context": {
                "type": "string",
                "description": "Contexto adicional (ej: 'React', 'Python FastAPI', nombre del proyecto)",
            },
            "type": {
                "type": "string",
                "enum": ["function", "component", "pattern", "module", "any"],
                "description": "Tipo de artefacto a crear (default: any)",
            },
        },
        "required": ["intent"],
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "memory_store": "Guardar memoria con embeddings locales (ChromaDB + sentence-transformers)",
    "memory_recall": "Recuperar memorias relevantes por query semantico",
    "memory_search": "Busqueda de memorias con filtros opcionales",
    "memory_delete": "Eliminar una memoria por su ID",
    "memory_clear_user": "Eliminar todas las memorias semanticas de un usuario",
    "memory_stats": "Estadisticas del sistema de memoria",
    "memory_suggest": "Consulta proactiva: busca trabajo previo similar antes de crear codigo nuevo. Llama ANTES de crear funciones, componentes o modulos.",
}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Despacha una solicitud JSON-RPC 2.0 al manejador correspondiente.

    Args:
        request: Objeto JSON-RPC con method, id y params.

    Returns:
        Respuesta JSON-RPC o None para notificaciones sin respuesta.
    """
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, msg: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-memory", "version": "2.0.0"},
            }
        )

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": TOOL_DESCRIPTIONS.get(name, name),
                "inputSchema": schema,
            }
            for name, schema in TOOL_SCHEMAS.items()
        ]
        return ok({"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_input = params.get("arguments", {})
        if tool_name not in TOOLS:
            return err(-32601, f"Tool desconocida: {tool_name}")
        try:
            result = TOOLS[tool_name](tool_input)
        except Exception as e:
            logger.error("Tool '%s' lanzo excepcion: %s", tool_name, e)
            result = {"error": f"Error interno en {tool_name}: {e}"}
        is_error = isinstance(result, dict) and "error" in result and not result.get("success")
        return ok(
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                **({"isError": True} if is_error else {}),
            }
        )

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    return err(-32601, f"Metodo desconocido: {method}")


def main() -> None:
    """Punto de entrada del servidor MCP. Lee JSON-RPC desde stdin."""
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos (rompe tokenizers: "TextEncodeInput must be
    # Union[...]") y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logger.info(
        "Antigravity Memory Server v2.1.0 (dual-mode) iniciando -- memoria en %s", MEMORY_DIR
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except json.JSONDecodeError as e:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {e}"},
                    }
                ),
                flush=True,
            )
        except Exception as e:
            logger.error("Error inesperado: %s", e)
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
