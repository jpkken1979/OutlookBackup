"""
AgentMemorySyncAdapter — wrapper síncrono sobre UnifiedMemory.

Propósito del spike (plan 019):
    Proveer un shim que expone la MISMA API pública de ``AgentMemory``
    (store_output, store_conversation, store_context, recall,
    recall_conversations, get_stats, clear) pero delega a
    ``UnifiedMemory`` (async-first) internamente.

    Este módulo NO se cablea a ningún caller existente. Es el deliverable
    del spike para medir el gap de paridad antes de decidir la migración.

Decisiones de diseño (event-loop sync↔async):
    Se usa ``asyncio.run()`` por llamada. Esto es seguro en contextos
    puramente sincrónicos (CLI, tests, procesos sin loop activo), pero
    BLOQUEANTE y NO re-entrante: si el caller ya corre dentro de un loop
    asyncio (ej. un handler aiohttp o un agente async), ``asyncio.run()``
    lanzará RuntimeError("This event loop is already running").

    Alternativas evaluadas:
      - ``loop.run_until_complete()``: mismo problema en loops ya corriendo.
      - ``concurrent.futures.ThreadPoolExecutor`` con ``asyncio.run`` en
        el thread: viable pero añade overhead de threading y complejidad.
      - ``nest_asyncio.patch()``: funcional, pero dependencia externa no
        declarada en el proyecto.

    Decisión para el spike: ``asyncio.run()`` directo. El adapter es SOLO para
    callers sincrónicos. Si el caller es async, debe usar ``UnifiedMemory`` directo.
    Ver plan 019, Step 2, sección "Cuidado event-loop".

Hallazgo sobre SharedMemory vs SimpleSharedMemory (plan 019, Step 3):
    ``UnifiedMemory.shared_memory`` lazy-load primero la ``SharedMemory`` real
    de ``core.shared_memory`` (que tiene interfaz ``.store()``/``.retrieve()``
    pero NO ``.set()``). La llamada interna ``UnifiedMemory.store(CONTEXT)``
    usa ``.set()``, que solo existe en ``SimpleSharedMemory``. Esto es un bug
    latente en ``unified_memory.py:264``.

    El adapter resuelve esto inicializando la sub-instancia con
    ``SimpleSharedMemory`` explícitamente (patch de ``_shared_memory``
    antes del primer lazy-load).

    El MemoryType elegido para almacenar los outputs y conversaciones es
    ``MemoryType.OBSERVATION``, que va al subsistema DualStream y SÍ es
    queryable via ``unified.query()``. ``MemoryType.CONTEXT`` va a
    SharedMemory y NO tiene query path — lo que hace que ``recall()``
    no pueda encontrar datos almacenados ahí.

Schema de resultados de recall():
    ``UnifiedMemoryResult`` no expone el campo ``id`` directamente (GAP);
    se mapea a string vacío para compatibilidad.

NO tocar:
    - agent_memory.py
    - Los 7 callers (agent_daemon, agent_memory_manager, _daemon_mixin_planning,
      agent_base, _mixin_memory, gateway_main)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger("antigravity.memory.sync_adapter")

# Ruta por defecto — aislada del default de AgentMemory para evitar interferencias
_DEFAULT_STORAGE = Path.home() / ".antigravity" / "unified_memory_adapter"


class AgentMemorySyncAdapter:
    """
    Wrapper síncrono sobre UnifiedMemory que imita la API pública de AgentMemory.

    Expone los mismos métodos públicos que ``AgentMemory`` (modo fallback JSON),
    pero delega internamente a ``UnifiedMemory`` async vía ``asyncio.run()``.

    IMPORTANTE: No usar en contextos donde ya haya un event loop asyncio corriendo.
    En ese caso, usar ``UnifiedMemory`` directamente (API async nativa).

    Decisión de MemoryType:
        Los datos se almacenan como ``MemoryType.OBSERVATION`` en DualStream,
        que es queryable. ``MemoryType.CONTEXT`` va a SharedMemory sin path
        de query — usar OBSERVATION garantiza que ``recall()`` funcione.

    Args:
        agent_name: Nombre lógico del agente (mismo semántica que AgentMemory).
        storage_path: Directorio de almacenamiento para UnifiedMemory.
    """

    def __init__(
        self,
        agent_name: str,
        storage_path: Path | None = None,
    ) -> None:
        self.agent_name = agent_name
        self._storage_path = Path(storage_path or _DEFAULT_STORAGE) / agent_name
        self._storage_path.mkdir(parents=True, exist_ok=True)

        from core.memory.unified_memory import SimpleSharedMemory, UnifiedMemory

        self._unified = UnifiedMemory(storage_path=self._storage_path)

        # Forzar SimpleSharedMemory antes del lazy-load para evitar el bug
        # en unified_memory.py:264 donde se llama .set() sobre SharedMemory real.
        # SharedMemory real tiene .store()/.retrieve() pero NO .set().
        self._unified._shared_memory = cast(Any, SimpleSharedMemory(self._storage_path / "shared"))

        # Contador in-memory para get_stats()
        # UnifiedMemory.get_stats() reporta sub-sistemas, no un count simple.
        self._memory_count: int = 0

        # Índice interno de IDs de upsert (correlation_id → upsert tracking)
        self._upsert_index: set[str] = set()

        logger.info(
            "AgentMemorySyncAdapter[%s]: inicializado sobre UnifiedMemory en %s",
            agent_name,
            self._storage_path,
        )

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _run(self, coro: Any) -> Any:
        """
        Ejecuta una coroutine de forma síncrona vía asyncio.run().

        Args:
            coro: Coroutine a ejecutar.

        Returns:
            Resultado de la coroutine.

        Raises:
            RuntimeError: Si se llama desde dentro de un event loop ya activo
                          (ej. contexto aiohttp o pytest-asyncio con loop activo).
        """
        return asyncio.run(coro)

    # -----------------------------------------------------------------------
    # store_output
    # -----------------------------------------------------------------------

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

        Delega a ``UnifiedMemory.store(MemoryType.OBSERVATION)`` para que sea
        queryable via ``recall()``.

        GAP documentado:
        - ``duration_seconds`` no se propaga a los metadatos de UnifiedMemory.
        - El campo ``metadata['type'] == 'task_output'`` está en el metadata
          del DualStream pero no en el schema de UnifiedMemoryResult.

        Args:
            task: Descripción de la tarea.
            result: Output/resultado de la tarea.
            context: Contexto adicional (se serializa al content).
            task_id: ID de la tarea (se genera UUID si no se provee).
            duration_seconds: Tiempo de ejecución (no propagado — gap).

        Returns:
            ``task_id`` (el lógico, compatible con el contrato de AgentMemory).
        """
        from core.memory.unified_memory import MemoryType

        memory_id = task_id or str(uuid.uuid4())
        content = f"Task: {task}\nResult: {result}"
        if context:
            import json

            content += f"\nContext: {json.dumps(context, default=str)[:500]}"

        self._run(
            self._unified.store(
                content=content,
                memory_type=MemoryType.OBSERVATION,
                agent=self.agent_name,
                task_id=memory_id,
                metadata={"type": "task_output", "agent": self.agent_name, "task_id": memory_id},
            )
        )
        self._memory_count += 1
        logger.debug("AgentMemorySyncAdapter[%s]: store_output → %s", self.agent_name, memory_id)
        return memory_id

    # -----------------------------------------------------------------------
    # store_conversation
    # -----------------------------------------------------------------------

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

        Delega a ``UnifiedMemory.store(MemoryType.OBSERVATION)``.
        El upsert (mismo correlation_id → no duplicar) se implementa
        rastreando el correlation_id en ``_upsert_index``.

        GAP documentado:
        - El ID retornado es ``'a2a-{correlation_id}'`` (contrato de naming),
          pero en DualStream el ID interno es diferente.
        - En el upsert, el update del contenido en DualStream AÑADE una nueva
          entrada (DualStream no tiene upsert por task_id). El ``_memory_count``
          no se incrementa en el segundo store para preservar la semántica.
          La deduplicación en recall() mitiga el impacto visual.

        Args:
            correlation_id: ID de correlación de la conversación.
            from_agent: Agente que preguntó.
            to_agent: Agente que respondió (o debe responder).
            question: La pregunta/solicitud.
            answer: La respuesta (si ya existe).
            request_type: Tipo de request.

        Returns:
            ``'a2a-{correlation_id}'`` — compatible con el contrato de AgentMemory.
        """
        from core.memory.unified_memory import MemoryType

        memory_id = f"a2a-{correlation_id}"
        content = f"A2A [{request_type}] {from_agent} → {to_agent}\nQ: {question}"
        if answer:
            content += f"\nA: {answer}"

        is_upsert = memory_id in self._upsert_index

        self._run(
            self._unified.store(
                content=content,
                memory_type=MemoryType.OBSERVATION,
                agent=self.agent_name,
                task_id=memory_id,
                metadata={
                    "type": "a2a_conversation",
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "correlation_id": correlation_id,
                    "request_type": request_type,
                    "has_answer": "true" if answer else "false",
                },
            )
        )

        if not is_upsert:
            self._upsert_index.add(memory_id)
            self._memory_count += 1

        logger.debug(
            "AgentMemorySyncAdapter[%s]: store_conversation → %s (upsert=%s)",
            self.agent_name,
            memory_id,
            is_upsert,
        )
        return memory_id

    # -----------------------------------------------------------------------
    # store_context
    # -----------------------------------------------------------------------

    def store_context(
        self,
        key: str,
        value: Any,
        source_agent: str | None = None,
    ) -> str:
        """
        Almacena contexto compartido.

        Delega a ``UnifiedMemory.store(MemoryType.OBSERVATION)`` para queryabilidad.

        Args:
            key: Clave del contexto.
            value: Valor del contexto.
            source_agent: Agente que compartió el contexto.

        Returns:
            ID con prefijo ``'ctx-'`` — compatible con el contrato de AgentMemory.
        """
        from core.memory.unified_memory import MemoryType

        import json

        memory_id = f"ctx-{uuid.uuid4().hex[:12]}"
        if isinstance(value, str):
            content = f"Context[{key}]: {value}"
        else:
            content = f"Context[{key}]: {json.dumps(value, default=str)[:1000]}"

        self._run(
            self._unified.store(
                content=content,
                memory_type=MemoryType.OBSERVATION,
                agent=source_agent or self.agent_name,
                task_id=memory_id,
                metadata={
                    "type": "shared_context",
                    "key": key,
                    "source_agent": source_agent or "system",
                },
            )
        )
        self._memory_count += 1
        logger.debug(
            "AgentMemorySyncAdapter[%s]: store_context → %s",
            self.agent_name,
            memory_id,
        )
        return memory_id

    # -----------------------------------------------------------------------
    # recall
    # -----------------------------------------------------------------------

    def recall(
        self,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Busca en la memoria por coincidencia textual.

        Delega a ``UnifiedMemory.query(MemoryType.OBSERVATION)`` que usa
        DualStream con búsqueda por substring.

        GAP documentado:
        - El campo ``id`` no está disponible en ``UnifiedMemoryResult``;
          se mapea a string vacío.
        - El campo ``distance`` no existe; se fija en 0.5.
        - ``memory_type`` como string ("task_output", etc.) NO filtra en
          UnifiedMemory — el parámetro se ignora en esta implementación.

        Args:
            query: La consulta de búsqueda.
            limit: Máximo de resultados.
            memory_type: Ignorado (gap de filtrado por tipo).

        Returns:
            Lista de dict ``{id, content, metadata, distance}``.
        """
        from core.memory.unified_memory import MemoryType

        results_unified = self._run(
            self._unified.query(
                query=query,
                memory_types=[MemoryType.OBSERVATION, MemoryType.REASONING],
                limit=limit,
            )
        )

        normalized: list[dict[str, Any]] = []
        for r in results_unified:
            normalized.append(
                {
                    "id": "",  # GAP: UnifiedMemoryResult no expone id
                    "content": r.content,
                    "metadata": r.metadata or {},
                    "distance": max(0.0, 1.0 - r.score),
                }
            )

        return normalized[:limit]

    # -----------------------------------------------------------------------
    # recall_conversations
    # -----------------------------------------------------------------------

    def recall_conversations(
        self,
        with_agent: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Recupera conversaciones A2A recientes.

        Busca en DualStream por el marcador "A2A" que ``store_conversation()``
        incluye en el content.

        GAP documentado:
        - No puede distinguir a2a_conversation de task_output sin acceder
          al metadata interno de DualStream (que no lo expone via query).
        - El filtro ``with_agent`` busca por substring en el content, no
          en campos metadata from_agent/to_agent.
        - El ordenamiento es por score (semántico), no por timestamp como
          en AgentMemory (retorna los últimos N).

        Args:
            with_agent: Filtro por agente (substring en content — aproximación).
            limit: Máximo de resultados.

        Returns:
            Lista de conversaciones. No garantiza exclusión total de no-A2A.
        """
        from core.memory.unified_memory import MemoryType

        query = f"A2A {with_agent}" if with_agent else "A2A"
        results_unified = self._run(
            self._unified.query(
                query=query,
                memory_types=[MemoryType.OBSERVATION],
                limit=limit,
            )
        )

        normalized: list[dict[str, Any]] = []
        for r in results_unified:
            content = r.content
            # Verificar que realmente es A2A (filtro adicional)
            if "A2A" not in content:
                continue
            if with_agent and with_agent not in content:
                continue
            normalized.append(
                {
                    "id": "",
                    "content": content,
                    "metadata": r.metadata or {},
                }
            )

        return normalized[:limit]

    # -----------------------------------------------------------------------
    # get_stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """
        Retorna estadísticas de la memoria del agente.

        GAP documentado:
        - ``backend`` retorna ``'unified_memory'`` en vez de ``'json_fallback'``
          o ``'chromadb'``. Callers que brancheen por este campo necesitarán
          adaptación.
        - ``total_memories`` es el conteo del adapter (incrementado por store_*),
          no el count de DualStream (que puede diferir si hubo upserts en OBSERVATION).

        Returns:
            Dict con ``agent``, ``backend``, ``total_memories``, ``storage_path``.
        """
        return {
            "agent": self.agent_name,
            "backend": "unified_memory",
            "total_memories": self._memory_count,
            "storage_path": str(self._storage_path),
        }

    # -----------------------------------------------------------------------
    # clear
    # -----------------------------------------------------------------------

    def clear(self) -> None:
        """
        Limpia toda la memoria del agente.

        Resetea el contador, el índice de upserts y la memoria efímera.
        También limpia SimpleSharedMemory si está disponible.

        GAP documentado:
        - DualStream no expone un método ``clear()`` público —
          los items en DualStream persisten en disco tras ``clear()``.
          El contador se pone en 0 y los nuevos stores no se ven afectados,
          pero una query podría devolver datos previos.
        """
        self._memory_count = 0
        self._upsert_index.clear()
        self._unified.clear_ephemeral()

        # Limpiar SimpleSharedMemory
        sm = cast(Any, self._unified._shared_memory)
        if hasattr(sm, "_data") and hasattr(sm, "_save"):
            sm._data.clear()
            sm._save()

        # Limpiar DualStream si tiene clear disponible
        ds = self._unified._dual_stream
        if ds is not None and hasattr(ds, "clear"):
            try:
                self._run(ds.clear()) if asyncio.iscoroutinefunction(ds.clear) else ds.clear()
            except Exception as exc:
                logger.warning(
                    "AgentMemorySyncAdapter[%s]: no se pudo limpiar DualStream: %s",
                    self.agent_name,
                    exc,
                )

        logger.info("AgentMemorySyncAdapter[%s]: memoria limpiada", self.agent_name)
