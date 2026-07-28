"""
AgentMemory - Memoria persistente per-agente sobre ChromaDB.

DEPRECATED (Ola 2b parte 1, 2026-04-18):
    El canonico del ecosistema para memoria unificada es
    ``core.memory.unified_memory.UnifiedMemory`` (facade async-first con
    MemoryType, cross-system query, fusion de DualStream + TemporalGraph +
    SharedMemory y stats unificados). ``AgentMemory`` se mantiene por
    compatibilidad con 4 callers actuales (agent_daemon, 3 mixins gateway,
    memory_autosave_hook) y sera migrado en Ola 2b parte 2.

    No migramos la implementacion ahora porque:
      1. UnifiedMemory es async, AgentMemory es sync — mezcla requiere
         resolver event-loop handling en cada caller.
      2. UnifiedMemory no reproduce el backend ChromaDB por-coleccion-por-agente
         (un detalle que varios callers asumen).
      3. Los tests actuales asertan sobre `_fallback_data` interno; una
         delegacion fire-and-forget invisible dejaria los tests verdes
         pero pudriria la integracion.

    Migracion sugerida para Ola 2b parte 2:
        from core.memory.unified_memory import get_unified_memory, MemoryType
        unified = get_unified_memory()
        await unified.store(
            content=result, memory_type=MemoryType.CONTEXT,
            agent=agent_name, task_id=task,
        )
        results = await unified.query(
            query, memory_types=[MemoryType.CONTEXT],
            agent_filter=agent_name, limit=limit,
        )

Cada agente tiene su propia colección en ChromaDB. Almacena:
  - Outputs de tareas anteriores (para que alimenten el siguiente ciclo)
  - Conversaciones A2A (request-reply)
  - Contexto compartido recibido de otros agentes
  - Observaciones y razonamientos

Esto permite que los agentes:
  1. Recuerden lo que hicieron y los resultados que obtuvieron
  2. Busquen contexto relevante antes de ejecutar una nueva tarea
  3. Mantengan hilos de conversación A2A persistentes

Usage:
    memory = AgentMemory("security-auditor")
    memory.store_output(task="revisar auth", result="JWT es seguro", context={...})
    memory.store_conversation(corr_id, from_agent="architect", question="...", answer="...")

    # Buscar contexto relevante para una nueva tarea
    relevant = memory.recall("vulnerabilidades JWT", limit=5)
"""

import json
import logging
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.agent_memory")

# Directorio por defecto para la persistencia
_DEFAULT_STORAGE = Path(__file__).parent.parent / "data" / "agent_memory"


class AgentMemory:
    """
    Memoria persistente para un agente individual.

    Usa ChromaDB para almacenamiento vectorial con búsqueda semántica.
    Si ChromaDB no está disponible, usa un fallback JSON simple.

    .. deprecated::
        Migrar a ``core.memory.unified_memory.UnifiedMemory`` en Ola 2b
        parte 2. Ver docstring del modulo para detalles de migracion.
    """

    def __init__(
        self,
        agent_name: str,
        storage_path: Path | None = None,
    ) -> None:
        warnings.warn(
            "AgentMemory is deprecated; migrate to "
            "core.memory.unified_memory.UnifiedMemory via get_unified_memory() "
            "in Ola 2b part 2.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.agent_name = agent_name
        self.storage_path = Path(storage_path or _DEFAULT_STORAGE)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._collection = None
        self._client = None
        self._use_chroma = False
        self._fallback_file = self.storage_path / f"{agent_name}_memory.json"
        self._fallback_data: list[dict[str, Any]] = []

        self._init_backend()

    def _init_backend(self) -> None:
        """Inicializa ChromaDB o el fallback JSON."""
        try:
            import chromadb

            try:
                from chromadb.config import Settings

                settings = Settings(anonymized_telemetry=False)
            except (ImportError, TypeError, ValueError):
                settings = None  # type: ignore[assignment]

            kwargs: dict[str, object] = {"path": str(self.storage_path / "chroma")}
            if settings is not None:
                kwargs["settings"] = settings
            self._client = chromadb.PersistentClient(**kwargs)  # type: ignore[assignment,arg-type]
            collection_name = f"agent_{self.agent_name.replace('-', '_')}"
            self._collection = self._client.get_or_create_collection(  # type: ignore[union-attr,attr-defined]  # chromadb: dep opcional
                name=collection_name,
                metadata={"agent": self.agent_name, "type": "agent_memory"},
            )
            self._use_chroma = True
            logger.info("AgentMemory[%s]: ChromaDB inicializado", self.agent_name)
        except (ImportError, Exception) as exc:
            logger.info(
                "AgentMemory[%s]: ChromaDB no disponible (%s), usando fallback JSON",
                self.agent_name,
                exc,
            )
            self._load_fallback()

    def _load_fallback(self) -> None:
        """Carga datos del fallback JSON."""
        if self._fallback_file.exists():
            try:
                with open(self._fallback_file, encoding="utf-8") as f:
                    self._fallback_data = json.load(f)
            except Exception as e:
                logger.warning("Error cargando fallback JSON: %s", e)
                self._fallback_data = []
        else:
            self._fallback_data = []

    def _save_fallback(self) -> None:
        """Persiste el fallback JSON."""
        try:
            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump(self._fallback_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Error guardando fallback JSON: %s", e)

    # --------------------------------------------------------
    # Almacenar output de tareas
    # --------------------------------------------------------
    def store_output(
        self,
        task: str,
        result: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
        duration_seconds: float | None = None,
    ) -> str:
        """
        Almacena el resultado de una tarea ejecutada por el agente.

        Args:
            task: Descripción de la tarea.
            result: Output/resultado de la tarea.
            context: Contexto adicional de la ejecución.
            task_id: ID de la tarea (opcional, se genera si no se provee).
            duration_seconds: Tiempo de ejecución en segundos.

        Returns:
            ID del registro en memoria.
        """
        memory_id = task_id or str(uuid.uuid4())
        metadata = {
            "type": "task_output",
            "agent": self.agent_name,
            "task": task[:200],
            "task_id": memory_id,
            "timestamp": datetime.now().isoformat(),
        }
        if duration_seconds is not None:
            metadata["duration_seconds"] = str(duration_seconds)
        if context:
            metadata["context_keys"] = ",".join(context.keys())

        content = f"Task: {task}\nResult: {result}"
        if context:
            ctx_summary = json.dumps(context, default=str)[:500]
            content += f"\nContext: {ctx_summary}"

        return self._store(memory_id, content, metadata)

    # --------------------------------------------------------
    # Almacenar conversaciones A2A
    # --------------------------------------------------------
    def store_conversation(
        self,
        correlation_id: str,
        from_agent: str,
        to_agent: str,
        question: str,
        answer: str | None = None,
        request_type: str = "question",
    ) -> str:
        """
        Almacena una conversación A2A (request y/o reply).

        Args:
            correlation_id: ID de correlación de la conversación.
            from_agent: Agente que preguntó.
            to_agent: Agente que respondió (o debe responder).
            question: La pregunta/solicitud.
            answer: La respuesta (si ya existe).
            request_type: Tipo de request (question, review, validate, delegate).

        Returns:
            ID del registro en memoria.
        """
        memory_id = f"a2a-{correlation_id}"
        metadata = {
            "type": "a2a_conversation",
            "agent": self.agent_name,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "correlation_id": correlation_id,
            "request_type": request_type,
            "timestamp": datetime.now().isoformat(),
            "has_answer": "true" if answer else "false",
        }

        content = f"A2A [{request_type}] {from_agent} → {to_agent}\nQ: {question}"
        if answer:
            content += f"\nA: {answer}"

        return self._store(memory_id, content, metadata)

    # --------------------------------------------------------
    # Almacenar contexto compartido
    # --------------------------------------------------------
    def store_context(
        self,
        key: str,
        value: Any,
        source_agent: str | None = None,
    ) -> str:
        """
        Almacena contexto compartido (recibido de otro agente o del sistema).

        Args:
            key: Clave del contexto.
            value: Valor del contexto.
            source_agent: Agente que compartió el contexto.

        Returns:
            ID del registro en memoria.
        """
        memory_id = f"ctx-{uuid.uuid4().hex[:12]}"
        metadata = {
            "type": "shared_context",
            "agent": self.agent_name,
            "key": key,
            "source_agent": source_agent or "system",
            "timestamp": datetime.now().isoformat(),
        }

        if isinstance(value, str):
            content = f"Context[{key}]: {value}"
        else:
            content = f"Context[{key}]: {json.dumps(value, default=str)[:1000]}"

        return self._store(memory_id, content, metadata)

    # --------------------------------------------------------
    # Recall — búsqueda semántica
    # --------------------------------------------------------
    def recall(
        self,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Busca en la memoria del agente por relevancia semántica.

        Args:
            query: La consulta de búsqueda.
            limit: Máximo de resultados.
            memory_type: Filtro opcional por tipo (task_output, a2a_conversation, shared_context).

        Returns:
            Lista de dict con content, metadata y distance/score.
        """
        if self._use_chroma and self._collection is not None:
            where_filter = None
            if memory_type:
                where_filter = {"type": memory_type}
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_filter,
                )
            except Exception as e:
                logger.warning("Error en recall ChromaDB: %s", e)
                return []

            memories = []
            docs = results.get("documents", [[]])[0]
            ids = results.get("ids", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            for i, doc in enumerate(docs):
                memories.append(
                    {
                        "id": ids[i] if i < len(ids) else "",
                        "content": doc,
                        "metadata": metas[i] if i < len(metas) else {},
                        "distance": dists[i] if i < len(dists) else None,
                    }
                )
            return memories

        # Fallback: búsqueda simple por texto
        query_lower = query.lower()
        matches = []
        for entry in self._fallback_data:
            if memory_type and entry.get("metadata", {}).get("type") != memory_type:
                continue
            content = entry.get("content", "")
            if query_lower in content.lower():
                matches.append(
                    {
                        "id": entry.get("id", ""),
                        "content": content,
                        "metadata": entry.get("metadata", {}),
                        "distance": 0.5,
                    }
                )
        return matches[:limit]

    # --------------------------------------------------------
    # Recall por conversación A2A
    # --------------------------------------------------------
    def recall_conversations(
        self,
        with_agent: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Recupera conversaciones A2A recientes.

        Args:
            with_agent: Filtro opcional por agente (from o to).
            limit: Máximo de resultados.

        Returns:
            Lista de conversaciones con metadata.
        """
        if self._use_chroma and self._collection is not None:
            where_filter: dict[str, Any] = {"type": "a2a_conversation"}
            if with_agent:
                # ChromaDB no soporta OR nativo, buscamos por from_agent
                where_filter = {
                    "$and": [
                        {"type": "a2a_conversation"},
                        {
                            "$or": [
                                {"from_agent": with_agent},
                                {"to_agent": with_agent},
                            ]
                        },
                    ]
                }
            try:
                results = self._collection.get(
                    where=where_filter,
                    limit=limit,
                )
            except Exception as e:
                logger.warning("Error en recall_conversations: %s", e)
                return []

            conversations = []
            for i, doc in enumerate(results.get("documents", [])):
                conversations.append(
                    {
                        "id": results["ids"][i] if i < len(results.get("ids", [])) else "",
                        "content": doc,
                        "metadata": results["metadatas"][i]
                        if i < len(results.get("metadatas", []))
                        else {},
                    }
                )
            return conversations

        # Fallback
        convs = [
            e
            for e in self._fallback_data
            if e.get("metadata", {}).get("type") == "a2a_conversation"
        ]
        if with_agent:
            convs = [
                c
                for c in convs
                if c.get("metadata", {}).get("from_agent") == with_agent
                or c.get("metadata", {}).get("to_agent") == with_agent
            ]
        return convs[-limit:]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas de la memoria del agente."""
        if self._use_chroma and self._collection is not None:
            count = self._collection.count()
            return {
                "agent": self.agent_name,
                "backend": "chromadb",
                "total_memories": count,
                "storage_path": str(self.storage_path),
            }

        return {
            "agent": self.agent_name,
            "backend": "json_fallback",
            "total_memories": len(self._fallback_data),
            "storage_path": str(self._fallback_file),
        }

    def clear(self) -> None:
        """Limpia toda la memoria del agente."""
        if self._use_chroma and self._client is not None:
            collection_name = f"agent_{self.agent_name.replace('-', '_')}"
            try:
                self._client.delete_collection(collection_name)
                self._collection = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"agent": self.agent_name, "type": "agent_memory"},
                )
            except Exception as e:
                logger.error("Error limpiando ChromaDB: %s", e)
        else:
            self._fallback_data = []
            self._save_fallback()
        logger.info("AgentMemory[%s]: memoria limpiada", self.agent_name)

    # --------------------------------------------------------
    # Internals
    # --------------------------------------------------------
    def _store(self, memory_id: str, content: str, metadata: dict) -> str:
        """Almacena un documento en el backend."""
        if self._use_chroma and self._collection is not None:
            # Upsert para permitir actualizaciones (ej. A2A con answer)
            self._collection.upsert(
                ids=[memory_id],
                documents=[content],
                metadatas=[metadata],
            )
        else:
            # Actualizar o insertar en fallback
            existing = next(
                (e for e in self._fallback_data if e.get("id") == memory_id),
                None,
            )
            if existing:
                existing["content"] = content
                existing["metadata"] = metadata
            else:
                self._fallback_data.append(
                    {
                        "id": memory_id,
                        "content": content,
                        "metadata": metadata,
                    }
                )
            self._save_fallback()

        return memory_id


# ============================================================
# Registry global de AgentMemory (un singleton por agente)
# ============================================================
_memory_instances: dict[str, AgentMemory] = {}


def get_agent_memory(
    agent_name: str,
    storage_path: Path | None = None,
) -> AgentMemory:
    """
    Obtiene la instancia de AgentMemory para un agente (singleton por nombre).

    Args:
        agent_name: Nombre del agente.
        storage_path: Directorio de almacenamiento (opcional).

    Returns:
        Instancia de AgentMemory para el agente.
    """
    if agent_name not in _memory_instances:
        _memory_instances[agent_name] = AgentMemory(
            agent_name=agent_name,
            storage_path=storage_path,
        )
    return _memory_instances[agent_name]


def reset_agent_memory(agent_name: str | None = None) -> None:
    """Reset de instancias de AgentMemory (útil para tests)."""
    if agent_name:
        _memory_instances.pop(agent_name, None)
    else:
        _memory_instances.clear()
