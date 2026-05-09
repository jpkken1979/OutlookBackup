# mypy: ignore-errors
"""Pizarrón compartido inter-agentes (Shared Blackboard Architecture).

Implementa una memoria de escritura/lectura concurrente usando SQLite con WAL,
que permite a múltiples agentes publicar y consumir mensajes JSON estructurados
bajo tópicos sin necesidad de esperar a que otro agente complete su ejecución.
Diseñado para comunicación asíncrona de baja latencia entre procesos del ecosistema.
"""

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class TelepathyBlackboard:
    """
    Shared Blackboard Architecture (Fase 2).
    Una memoria compartida inter-procesos utilizando SQLite.
    Permite a múltiples agentes "hablar telepáticamente" publicando y
    leyendo JSONs estructurados (ej. schemas de base de datos, APIs) en tiempo real,
    sin tener que esperar a que otro agente termine su ejecución completa.
    """

    def __init__(self, db_path: str = ".antigravity_blackboard.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO blackboard (topic, sender, content_json, timestamp) VALUES (?, ?, ?, ?)",
                (topic, sender, json.dumps(content), time.time()),
            )
            conn.commit()
            return cursor.lastrowid

    def read_topic(self, topic: str, since_timestamp: float = 0.0) -> list[dict[str, Any]]:
        """Lee todos los mensajes de un tópico específico desde un momento dado."""
        with sqlite3.connect(self.db_path) as conn:
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

    def clear_topic(self, topic: str):
        """Limpia un tópico (útil para iniciar un nuevo proyecto/tarea)."""
        with sqlite3.connect(self.db_path) as conn:
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


# Instancia global (Singleton-like pattern para acceso rápido, aunque la DB maneja concurrencia)
global_blackboard = TelepathyBlackboard()
