# mypy: ignore-errors
"""Pizarrón compartido inter-agentes (Shared Blackboard Architecture).

Implementa una memoria de escritura/lectura concurrente usando SQLite con WAL,
que permite a múltiples agentes publicar y consumir mensajes JSON estructurados
bajo tópicos sin necesidad de esperar a que otro agente complete su ejecución.
Diseñado para comunicación asíncrona de baja latencia entre procesos del ecosistema.
"""

import asyncio
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_worker_segment(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return sanitized[:80] or "unknown"


def default_blackboard_db_path() -> Path:
    """Resolve a stable production path and an isolated path per pytest worker."""

    override = os.environ.get("ANTIGRAVITY_BLACKBOARD_DB")
    if override:
        return Path(override)

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        run_uid = _safe_worker_segment(os.environ.get("PYTEST_XDIST_TESTRUNUID", "standalone"))
        worker_id = _safe_worker_segment(worker)
        return (
            Path(tempfile.gettempdir())
            / "openantigravity-pytest"
            / run_uid
            / f"blackboard-{worker_id}.db"
        )

    return _repo_root() / ".antigravity_blackboard.db"


class TelepathyBlackboard:
    """
    Shared Blackboard Architecture (Fase 2).
    Una memoria compartida inter-procesos utilizando SQLite.
    Permite a múltiples agentes "hablar telepáticamente" publicando y
    leyendo JSONs estructurados (ej. schemas de base de datos, APIs) en tiempo real,
    sin tener que esperar a que otro agente termine su ejecución completa.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_blackboard_db_path()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10.0)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blackboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            # Index for faster topic lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_topic ON blackboard(topic)")
            conn.commit()

    def post_message(self, topic: str, sender: str, content: dict[str, Any]) -> int:
        """Publica un mensaje (JSON) en el pizarrón bajo un tópico."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO blackboard (topic, sender, content_json, timestamp) VALUES (?, ?, ?, ?)",
                (topic, sender, json.dumps(content), time.time()),
            )
            conn.commit()
            return cursor.lastrowid

    def read_topic(self, topic: str, since_timestamp: float = 0.0) -> list[dict[str, Any]]:
        """Lee todos los mensajes de un tópico específico desde un momento dado."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, sender, content_json, timestamp FROM blackboard WHERE topic = ? AND timestamp > ? ORDER BY timestamp ASC",
                (topic, since_timestamp),
            )
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                messages.append(
                    {
                        "id": row[0],
                        "sender": row[1],
                        "content": json.loads(row[2]),
                        "timestamp": row[3],
                    }
                )
            return messages

    def clear_topic(self, topic: str) -> None:
        """Limpia un tópico (útil para iniciar un nuevo proyecto/tarea)."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM blackboard WHERE topic = ?", (topic,))
            conn.commit()

    def wait_for_data(
        self, topic: str, timeout_seconds: int = 120, poll_interval: float = 2.0
    ) -> list[dict[str, Any]] | None:
        """
        [MECANISMO DE TELEPATÍA]
        Pausa la ejecución del agente actual (ej: Frontend) bloqueando el hilo
        hasta que el dato (ej: Schema del Backend) aparezca en el pizarrón.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            data = self.read_topic(topic)
            if data:
                return data
            time.sleep(poll_interval)
        return None

    async def wait_for_data_async(
        self, topic: str, timeout_seconds: int = 120, poll_interval: float = 2.0
    ) -> list[dict[str, Any]] | None:
        """Espera hasta que haya datos en el topic — version no bloqueante.

        Version async de wait_for_data() para uso desde contextos async.
        Usa asyncio.sleep() en vez de time.sleep() para no bloquear el event loop.

        Args:
            topic: Topico a escuchar en el blackboard.
            timeout_seconds: Tiempo maximo de espera en segundos.
            poll_interval: Intervalo de polling en segundos.

        Returns:
            Lista de mensajes si se encontraron datos antes del timeout, None si timeout.
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            data = self.read_topic(topic)
            if data:
                return data
            await asyncio.sleep(poll_interval)
        return None


_global_blackboard: TelepathyBlackboard | None = None
_global_blackboard_lock = threading.Lock()


def get_global_blackboard() -> TelepathyBlackboard:
    """Create the process-local handle only on first use, never at import time."""

    global _global_blackboard
    if _global_blackboard is None:
        with _global_blackboard_lock:
            if _global_blackboard is None:
                _global_blackboard = TelepathyBlackboard()
    return _global_blackboard


class _LazyBlackboardProxy:
    """Compatibility proxy for callers importing ``global_blackboard``."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_global_blackboard(), name)


global_blackboard = _LazyBlackboardProxy()
