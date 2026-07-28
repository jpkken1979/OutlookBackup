#!/usr/bin/env python3
"""
Middleware utilities for the Antigravity Gateway.
===================================================

Contiene:
- RateLimiter: Token bucket por IP para limitar requests.
- TTLCache: Cache simple con expiracion por tiempo.

Extraido de gateway_main.py para modularidad.
"""

from __future__ import annotations

import time
from typing import Any

# Constante compartida usada como default en TTLCache
CACHE_TTL_SECONDS = 300


# ============================================================
# Rate Limiter (Token Bucket por IP)
# ============================================================
class RateLimiter:
    """Rate limiter por IP usando token bucket."""

    def __init__(self, requests_per_minute: int = 60):
        self._limit = requests_per_minute
        self._buckets: dict[str, dict] = {}
        self._last_cleanup: float = time.monotonic()

    def is_allowed(self, client_ip: str) -> bool:
        """Verifica si el cliente puede hacer una request."""
        now = time.monotonic()

        # Limpieza periodica automatica cada 5 minutos
        if now - self._last_cleanup > 300:
            self.cleanup()
            self._last_cleanup = now

        bucket = self._buckets.get(client_ip)

        if bucket is None:
            self._buckets[client_ip] = {"tokens": self._limit - 1, "last": now}
            return True

        elapsed = now - bucket["last"]
        bucket["last"] = now

        # Rellenar tokens proporcionalmente al tiempo transcurrido
        bucket["tokens"] = min(
            self._limit,
            bucket["tokens"] + elapsed * (self._limit / 60.0),
        )

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False

    def cleanup(self) -> None:
        """Elimina buckets inactivos (> 5 min)."""
        now = time.monotonic()
        stale = [ip for ip, b in self._buckets.items() if now - b["last"] > 300]
        for ip in stale:
            del self._buckets[ip]


# ============================================================
# Cache con TTL
# ============================================================
class TTLCache:
    """Cache simple con expiracion por tiempo."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Obtiene valor del cache si no ha expirado."""
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        """Guarda valor en cache."""
        self._store[key] = (time.monotonic(), value)

    def invalidate(self, key: str = "") -> None:
        """Invalida una key o todo el cache."""
        if key:
            self._store.pop(key, None)
        else:
            self._store.clear()
