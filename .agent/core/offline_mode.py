#!/usr/bin/env python3
"""
Offline Mode - Permite que el ecosistema funcione sin conexión a internet

Features:
- Detección automática de conectividad
- Cache local de respuestas LLM
- Fallback a modelos locales (Ollama)
- Queue de tareas para sincronizar cuando vuelva la conexión
- Modo degradado con capacidades limitadas
"""

import hashlib
import json
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class ConnectivityStatus(Enum):
    """Estado de conectividad"""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # Conexión lenta o inestable
    UNKNOWN = "unknown"


class OfflineCapability(Enum):
    """Capacidades disponibles offline"""

    CODE_ANALYSIS = "code_analysis"
    FILE_OPERATIONS = "file_operations"
    GIT_LOCAL = "git_local"
    CACHE_QUERIES = "cache_queries"
    LOCAL_LLM = "local_llm"
    MEMORY_ACCESS = "memory_access"


@dataclass
class QueuedTask:
    """Tarea encolada para sincronización"""

    id: str
    task_type: str
    payload: dict[str, Any]
    created_at: str
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class CachedResponse:
    """Respuesta cacheada de LLM"""

    prompt_hash: str
    response: str
    model: str
    created_at: str
    expires_at: str
    hits: int = 0


class OfflineMode:
    """Gestor de modo offline"""

    CHECK_ENDPOINTS = [
        ("https://api.anthropic.com", 443),
        ("https://api.openai.com", 443),
        ("https://google.com", 443),
    ]

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(".agent/offline")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)

        self.queue_file = self.data_dir / "task_queue.json"
        self.cache_index_file = self.data_dir / "cache_index.json"

        self._status = ConnectivityStatus.UNKNOWN
        self._last_check: datetime | None = None
        self._check_interval = 30  # segundos
        self._lock = threading.Lock()

        self._response_cache: dict[str, CachedResponse] = {}
        self._task_queue: list[QueuedTask] = []
        self._offline_handlers: dict[str, Callable] = {}

        self._load_state()

    def _load_state(self):
        """Cargar estado persistido"""
        # Cargar cache index
        if self.cache_index_file.exists():
            try:
                data = json.loads(self.cache_index_file.read_text(encoding="utf-8"))
                for key, item in data.items():
                    self._response_cache[key] = CachedResponse(**item)
            except Exception:
                pass

        # Cargar queue
        if self.queue_file.exists():
            try:
                data = json.loads(self.queue_file.read_text(encoding="utf-8"))
                self._task_queue = [QueuedTask(**item) for item in data]
            except Exception:
                pass

    def _save_state(self):
        """Guardar estado"""
        # Guardar cache index
        cache_data = {
            k: {
                "prompt_hash": v.prompt_hash,
                "response": v.response,
                "model": v.model,
                "created_at": v.created_at,
                "expires_at": v.expires_at,
                "hits": v.hits,
            }
            for k, v in self._response_cache.items()
        }
        self.cache_index_file.write_text(json.dumps(cache_data, indent=2))

        # Guardar queue
        queue_data = [
            {
                "id": t.id,
                "task_type": t.task_type,
                "payload": t.payload,
                "created_at": t.created_at,
                "priority": t.priority,
                "retry_count": t.retry_count,
                "max_retries": t.max_retries,
            }
            for t in self._task_queue
        ]
        self.queue_file.write_text(json.dumps(queue_data, indent=2))

    def check_connectivity(self, force: bool = False) -> ConnectivityStatus:
        """Verificar estado de conectividad"""
        now = datetime.now()

        # Usar cache si no ha pasado el intervalo
        if not force and self._last_check:
            elapsed = (now - self._last_check).total_seconds()
            if elapsed < self._check_interval:
                return self._status

        successful = 0
        total = len(self.CHECK_ENDPOINTS)

        for host, port in self.CHECK_ENDPOINTS:
            try:
                # Extraer hostname
                hostname = host.replace("https://", "").replace("http://", "")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((hostname, port))
                sock.close()

                if result == 0:
                    successful += 1
            except OSError:
                pass

        self._last_check = now

        if successful == total:
            self._status = ConnectivityStatus.ONLINE
        elif successful > 0:
            self._status = ConnectivityStatus.DEGRADED
        else:
            self._status = ConnectivityStatus.OFFLINE

        return self._status

    @property
    def is_online(self) -> bool:
        """Verificar si está online"""
        status = self.check_connectivity()
        return status == ConnectivityStatus.ONLINE

    @property
    def is_offline(self) -> bool:
        """Verificar si está offline"""
        status = self.check_connectivity()
        return status == ConnectivityStatus.OFFLINE

    def get_available_capabilities(self) -> list[OfflineCapability]:
        """Obtener capacidades disponibles según conectividad"""
        status = self.check_connectivity()

        # Capacidades siempre disponibles
        capabilities = [
            OfflineCapability.CODE_ANALYSIS,
            OfflineCapability.FILE_OPERATIONS,
            OfflineCapability.GIT_LOCAL,
            OfflineCapability.MEMORY_ACCESS,
        ]

        if status in [ConnectivityStatus.ONLINE, ConnectivityStatus.DEGRADED]:
            # Online: todas las capacidades
            return list(OfflineCapability)

        # Offline: capacidades limitadas
        if self._check_local_llm():
            capabilities.append(OfflineCapability.LOCAL_LLM)

        if self._response_cache:
            capabilities.append(OfflineCapability.CACHE_QUERIES)

        return capabilities

    def _check_local_llm(self) -> bool:
        """Verificar si hay un LLM local disponible (Ollama)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 11434))  # Puerto default de Ollama
            sock.close()
            return result == 0
        except OSError:
            return False

    def cache_llm_response(
        self, prompt: str, response: str, model: str = "unknown", ttl_hours: int = 24
    ):
        """Cachear respuesta de LLM"""
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:32]

        now = datetime.now()
        cached = CachedResponse(
            prompt_hash=prompt_hash,
            response=response,
            model=model,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=ttl_hours)).isoformat(),
        )

        with self._lock:
            self._response_cache[prompt_hash] = cached
            self._save_state()

        # También guardar respuesta completa
        cache_file = self.cache_dir / f"{prompt_hash}.json"
        cache_file.write_text(
            json.dumps(
                {
                    "prompt": prompt,
                    "response": response,
                    "model": model,
                    "created_at": cached.created_at,
                },
                indent=2,
            )
        )

    def get_cached_response(self, prompt: str) -> str | None:
        """Obtener respuesta cacheada"""
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:32]

        with self._lock:
            cached = self._response_cache.get(prompt_hash)

            if cached:
                # Verificar expiración
                if datetime.fromisoformat(cached.expires_at) > datetime.now():
                    cached.hits += 1
                    return cached.response
                else:
                    # Expirado
                    del self._response_cache[prompt_hash]

        return None

    def queue_task(self, task_type: str, payload: dict[str, Any], priority: int = 0) -> str:
        """Encolar tarea para sincronización posterior"""
        task_id = hashlib.sha256(
            f"{task_type}{json.dumps(payload)}{time.time()}".encode()
        ).hexdigest()[:16]

        task = QueuedTask(
            id=task_id,
            task_type=task_type,
            payload=payload,
            created_at=datetime.now().isoformat(),
            priority=priority,
        )

        with self._lock:
            self._task_queue.append(task)
            # Ordenar por prioridad
            self._task_queue.sort(key=lambda t: t.priority, reverse=True)
            self._save_state()

        return task_id

    def get_pending_tasks(self) -> list[QueuedTask]:
        """Obtener tareas pendientes"""
        return list(self._task_queue)

    def process_queue(self) -> dict[str, Any]:
        """Procesar cola de tareas (cuando vuelve la conexión)"""
        if not self.is_online:
            return {"processed": 0, "error": "Still offline"}

        processed = 0
        failed = 0
        results = []

        with self._lock:
            tasks_to_process = list(self._task_queue)

        for task in tasks_to_process:
            try:
                handler = self._offline_handlers.get(task.task_type)
                if handler:
                    result = handler(task.payload)
                    results.append({"task_id": task.id, "result": result})
                    processed += 1

                    # Remover de la cola
                    with self._lock:
                        self._task_queue = [t for t in self._task_queue if t.id != task.id]
                else:
                    failed += 1

            except Exception:
                task.retry_count += 1
                if task.retry_count >= task.max_retries:
                    with self._lock:
                        self._task_queue = [t for t in self._task_queue if t.id != task.id]
                failed += 1

        self._save_state()

        return {
            "processed": processed,
            "failed": failed,
            "remaining": len(self._task_queue),
            "results": results,
        }

    def register_handler(self, task_type: str, handler: Callable):
        """Registrar handler para tipo de tarea"""
        self._offline_handlers[task_type] = handler

    def query_with_fallback(
        self,
        prompt: str,
        online_func: Callable[[str], str],
        offline_func: Callable[[str], str] | None = None,
    ) -> dict[str, Any]:
        """Ejecutar query con fallback offline"""
        status = self.check_connectivity()

        # Intentar cache primero
        cached = self.get_cached_response(prompt)
        if cached:
            return {"response": cached, "source": "cache", "status": status.value}

        if status == ConnectivityStatus.ONLINE:
            try:
                response = online_func(prompt)
                # Cachear respuesta
                self.cache_llm_response(prompt, response)
                return {"response": response, "source": "online", "status": status.value}
            except Exception:
                # Fallback si falla
                pass

        # Modo offline
        if offline_func:
            try:
                response = offline_func(prompt)
                return {"response": response, "source": "offline_fallback", "status": status.value}
            except Exception:
                pass

        # Sin opciones
        return {
            "response": None,
            "source": "none",
            "status": status.value,
            "error": "No response available offline",
        }

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas del modo offline"""
        total_hits = sum(c.hits for c in self._response_cache.values())

        return {
            "status": self._status.value,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "cache_entries": len(self._response_cache),
            "cache_hits": total_hits,
            "pending_tasks": len(self._task_queue),
            "local_llm_available": self._check_local_llm(),
            "capabilities": [c.value for c in self.get_available_capabilities()],
        }

    def clear_cache(self):
        """Limpiar cache"""
        with self._lock:
            self._response_cache.clear()
            # Limpiar archivos
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
            self._save_state()

    def clear_queue(self):
        """Limpiar cola de tareas"""
        with self._lock:
            self._task_queue.clear()
            self._save_state()


# Singleton global
_offline_mode: OfflineMode | None = None
_om_lock = threading.Lock()


def get_offline_mode() -> OfflineMode:
    """Obtener instancia singleton"""
    global _offline_mode

    if _offline_mode is None:
        with _om_lock:
            if _offline_mode is None:
                _offline_mode = OfflineMode()

    return _offline_mode


# Decorador para funciones con fallback offline
def with_offline_fallback(cache_ttl: int = 24, queue_on_fail: bool = True):
    """Decorador para agregar soporte offline a funciones"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            om = get_offline_mode()

            # Crear key para cache
            cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"

            # Intentar cache
            cached = om.get_cached_response(cache_key)
            if cached:
                return json.loads(cached)

            if om.is_online:
                try:
                    result = func(*args, **kwargs)
                    # Cachear resultado
                    om.cache_llm_response(cache_key, json.dumps(result), ttl_hours=cache_ttl)
                    return result
                except Exception:
                    if queue_on_fail:
                        om.queue_task(func.__name__, {"args": args, "kwargs": kwargs})
                    raise

            # Offline - encolar si está configurado
            if queue_on_fail:
                om.queue_task(func.__name__, {"args": args, "kwargs": kwargs})

            raise ConnectionError("Offline and no cached response available")

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Offline Mode Manager")
    parser.add_argument("command", choices=["status", "check", "stats", "queue", "clear", "test"])
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    om = get_offline_mode()

    if args.command == "status":
        status = om.check_connectivity(force=True)
        if args.json:
            print(json.dumps({"status": status.value}))
        else:
            emoji = {"online": "🟢", "offline": "🔴", "degraded": "🟡", "unknown": "⚪"}
            print(f"{emoji.get(status.value, '•')} Status: {status.value}")

    elif args.command == "check":
        status = om.check_connectivity(force=True)
        caps = om.get_available_capabilities()
        if args.json:
            print(
                json.dumps(
                    {"status": status.value, "capabilities": [c.value for c in caps]}, indent=2
                )
            )
        else:
            print(f"Connectivity: {status.value}")
            print("Available capabilities:")
            for cap in caps:
                print(f"  ✓ {cap.value}")

    elif args.command == "stats":
        stats = om.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\n=== Offline Mode Statistics ===")
            print(f"Status: {stats['status']}")
            print(f"Cache entries: {stats['cache_entries']}")
            print(f"Cache hits: {stats['cache_hits']}")
            print(f"Pending tasks: {stats['pending_tasks']}")
            print(f"Local LLM: {'Available' if stats['local_llm_available'] else 'Not available'}")

    elif args.command == "queue":
        tasks = om.get_pending_tasks()
        if args.json:
            print(json.dumps([{"id": t.id, "type": t.task_type} for t in tasks], indent=2))
        else:
            if tasks:
                print(f"\nPending tasks ({len(tasks)}):")
                for task in tasks:
                    print(f"  [{task.id[:8]}] {task.task_type}")
            else:
                print("No pending tasks")

    elif args.command == "clear":
        om.clear_cache()
        om.clear_queue()
        print("Cache and queue cleared")

    elif args.command == "test":
        print("Testing Offline Mode...\n")

        # Test connectivity
        status = om.check_connectivity(force=True)
        print(f"✓ Connectivity check: {status.value}")

        # Test caching
        om.cache_llm_response("test prompt", "test response", "test-model")
        cached = om.get_cached_response("test prompt")
        assert cached == "test response", "Cache test failed"
        print("✓ Response caching works")

        # Test queue
        task_id = om.queue_task("test_task", {"data": "test"})
        assert task_id is not None, "Queue test failed"
        print(f"✓ Task queuing works (id: {task_id[:8]})")

        # Cleanup
        om.clear_cache()
        om.clear_queue()

        print("\n✓ All tests passed!")
