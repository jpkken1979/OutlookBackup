"""
DaemonProxy — proxy al daemon worker subprocess.

Reemplaza `core.agent_daemon.get_daemon()` en el gateway.
En vez de importar el módulo pesado (bloquea GIL 3-5s), hace
HTTP POST a daemon_worker.py que corre en proceso separado.

Uso:
    proxy = await DaemonProxy.create()  # Spawn worker si necesario
    result = proxy.get_status()         # HTTP call transparente
    result = proxy.submit_task(...)     # Igual que daemon real
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import aiohttp

log = logging.getLogger("antigravity-gateway.daemon-proxy")

WORKER_PORT = 4748
WORKER_SCRIPT = str(Path(__file__).parent / "daemon_worker.py")
WORKER_HEALTH_URL = f"http://127.0.0.1:{WORKER_PORT}/health"
WORKER_RPC_URL = f"http://127.0.0.1:{WORKER_PORT}/rpc"


class DaemonProxy:
    """Proxy transparente al daemon worker subprocess.

    Intercepta llamadas a métodos y las reenvía como HTTP RPC.
    Compatible con el patrón existente: daemon.method(args).
    """

    _instance: DaemonProxy | None = None
    _worker_process: subprocess.Popen | None = None
    _create_lock: asyncio.Lock | None = None

    def __getattr__(self, name: str):
        """Intercepta llamadas a métodos del daemon y las envía como RPC async."""
        if name.startswith("_"):
            raise AttributeError(name)

        async def rpc_call(*args, **kwargs):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        WORKER_RPC_URL,
                        json={"method": name, "args": list(args), "kwargs": kwargs},
                    ) as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            return data.get("result")
                        raise RuntimeError(data.get("error", "RPC error"))
            except aiohttp.ClientConnectionError:
                raise RuntimeError("Daemon worker no disponible")
            except TimeoutError:
                raise RuntimeError(f"Daemon worker timeout en {name}()")

        return rpc_call

    @classmethod
    async def create(cls) -> DaemonProxy | None:
        """Crea o retorna el proxy singleton, spawneando el worker si necesario.

        Usa asyncio.Lock para evitar que múltiples requests concurrentes
        spawneen workers duplicados. Health checks son async (no bloquean event loop).
        """
        # Singleton rápido (sin lock)
        if cls._instance is not None:
            if await cls._is_worker_alive_async():
                return cls._instance
            # Worker murió — limpiar
            cls._instance = None
            cls._worker_process = None

        # Lock para que solo un coroutine haga el spawn
        if cls._create_lock is None:
            cls._create_lock = asyncio.Lock()

        async with cls._create_lock:
            # Double-check después del lock
            if cls._instance is not None:
                return cls._instance

            # Intentar conectar a worker existente
            if await cls._is_worker_alive_async():
                cls._instance = cls()
                log.info("Daemon proxy conectado a worker existente en :%d", WORKER_PORT)
                return cls._instance

            # Spawn nuevo worker
            try:
                log.info("Spawning daemon worker en :%d...", WORKER_PORT)
                python = sys.executable
                cmd = [python, WORKER_SCRIPT, "--port", str(WORKER_PORT)]

                # Windows: CREATE_NO_WINDOW
                kwargs: dict = {
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                    "stdin": subprocess.DEVNULL,
                }
                if sys.platform == "win32":
                    kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

                cls._worker_process = subprocess.Popen(cmd, **kwargs)
                log.info("Daemon worker spawned (PID %d)", cls._worker_process.pid)

                # Esperar a que esté listo (max 10s — lite mode arranca en ~2s)
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if await cls._is_worker_alive_async():
                        cls._instance = cls()
                        log.info("Daemon worker listo en :%d", WORKER_PORT)
                        return cls._instance

                log.warning("Daemon worker no respondió en 10s")
                return None

            except Exception as e:
                log.error("Error spawning daemon worker: %s", e)
                return None

    @classmethod
    async def _is_worker_alive_async(cls) -> bool:
        """Health check ASYNC — no bloquea el event loop."""
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(WORKER_HEALTH_URL) as resp:
                    if resp.status != 200:
                        return False
                    data = await resp.json()
                    return data.get("ok", False)
        except Exception:
            return False

    @classmethod
    def shutdown(cls) -> None:
        """Mata el worker process."""
        if cls._worker_process is not None:
            try:
                cls._worker_process.terminate()
                cls._worker_process.wait(timeout=5)
            except Exception:
                try:
                    cls._worker_process.kill()
                except Exception:
                    pass
            cls._worker_process = None
        cls._instance = None
