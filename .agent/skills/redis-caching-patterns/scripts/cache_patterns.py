#!/usr/bin/env python3
"""
Redis Caching Patterns Demo
Implementación de patrones de caching con simulador de Redis.
"""

import asyncio
import json
import logging
import time
import random
import hashlib
from typing import Any, TypeVar
from collections.abc import Callable

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# SIMULADOR DE REDIS
# =============================================================================


class RedisSimulator:
    """Simulador simple de Redis para demostración."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float | None]] = {}  # key -> (value, expire_at)
        self._sorted_sets: dict[str, dict[str, float]] = {}  # key -> {member: score}
        self.stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    def _is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, expire_at = self._store[key]
        if expire_at and time.time() > expire_at:
            del self._store[key]
            return True
        return False

    async def get(self, key: str) -> str | None:
        if self._is_expired(key):
            self.stats["misses"] += 1
            return None
        self.stats["hits"] += 1
        return self._store[key][0]

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        expire_at = time.time() + ex if ex else None
        self._store[key] = (value, expire_at)
        self.stats["sets"] += 1
        return True

    async def delete(self, key: str) -> int:
        if key in self._store:
            del self._store[key]
            self.stats["deletes"] += 1
            return 1
        return 0

    async def exists(self, key: str) -> bool:
        return not self._is_expired(key)

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._store:
            value, _ = self._store[key]
            self._store[key] = (value, time.time() + seconds)
            return True
        return False

    async def incr(self, key: str) -> int:
        if self._is_expired(key):
            await self.set(key, "0")
        value = int(self._store[key][0]) + 1
        self._store[key] = (str(value), self._store[key][1])
        return value

    async def setnx(self, key: str, value: str) -> bool:
        """SET if Not eXists."""
        if await self.exists(key):
            return False
        await self.set(key, value)
        return True

    # Sorted Sets
    async def zadd(self, key: str, score: float, member: str) -> int:
        if key not in self._sorted_sets:
            self._sorted_sets[key] = {}
        is_new = member not in self._sorted_sets[key]
        self._sorted_sets[key][member] = score
        return 1 if is_new else 0

    async def zincrby(self, key: str, increment: float, member: str) -> float:
        if key not in self._sorted_sets:
            self._sorted_sets[key] = {}
        current = self._sorted_sets[key].get(member, 0)
        new_score = current + increment
        self._sorted_sets[key][member] = new_score
        return new_score

    async def zrevrange(self, key: str, start: int, stop: int, withscores: bool = False) -> list:
        if key not in self._sorted_sets:
            return []
        sorted_items = sorted(self._sorted_sets[key].items(), key=lambda x: x[1], reverse=True)
        sliced = sorted_items[start : stop + 1]
        if withscores:
            result = []
            for member, score in sliced:
                result.extend([member, str(score)])
            return result
        return [member for member, _ in sliced]

    async def zrevrank(self, key: str, member: str) -> int | None:
        if key not in self._sorted_sets or member not in self._sorted_sets[key]:
            return None
        sorted_items = sorted(self._sorted_sets[key].items(), key=lambda x: x[1], reverse=True)
        for i, (m, _) in enumerate(sorted_items):
            if m == member:
                return i
        return None

    def get_hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        return self.stats["hits"] / total if total > 0 else 0


# =============================================================================
# CACHE-ASIDE PATTERN
# =============================================================================


class CacheAside:
    """Implementación del patrón Cache-Aside."""

    def __init__(self, redis: RedisSimulator, ttl: int = 3600):
        self.redis = redis
        self.ttl = ttl
        self._db_calls = 0

    async def get(self, key: str, fetch_fn: Callable[[], Any]) -> Any:
        """
        1. Intenta obtener del cache
        2. Si no está, llama a fetch_fn
        3. Guarda en cache
        """
        # Intentar cache
        cached = await self.redis.get(key)
        if cached:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(cached)

        logger.debug(f"Cache MISS: {key}")

        # Obtener de "DB"
        self._db_calls += 1
        value = await fetch_fn() if asyncio.iscoroutinefunction(fetch_fn) else fetch_fn()

        # Guardar en cache
        if value is not None:
            await self.redis.set(key, json.dumps(value), ex=self.ttl)

        return value

    async def invalidate(self, key: str) -> None:
        """Invalida una entrada del cache."""
        await self.redis.delete(key)
        logger.debug(f"Cache INVALIDATED: {key}")


# =============================================================================
# CACHE STAMPEDE PREVENTION
# =============================================================================


class MutexCache:
    """Cache con mutex para prevenir stampede."""

    def __init__(self, redis: RedisSimulator, ttl: int = 3600, lock_ttl: int = 10):
        self.redis = redis
        self.ttl = ttl
        self.lock_ttl = lock_ttl

    async def get_with_mutex(self, key: str, fetch_fn: Callable[[], Any]) -> Any:
        """
        Previene cache stampede usando un mutex.
        Solo un proceso regenera el cache.
        """
        # Intentar cache
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        lock_key = f"lock:{key}"

        # Intentar adquirir lock
        acquired = await self.redis.setnx(lock_key, "1")
        if acquired:
            await self.redis.expire(lock_key, self.lock_ttl)
            try:
                # Este proceso regenera el cache
                logger.info(f"Mutex acquired, fetching: {key}")
                value = await fetch_fn() if asyncio.iscoroutinefunction(fetch_fn) else fetch_fn()
                await self.redis.set(key, json.dumps(value), ex=self.ttl)
                return value
            finally:
                await self.redis.delete(lock_key)
        else:
            # Otro proceso está regenerando, esperar y reintentar
            logger.info(f"Waiting for mutex: {key}")
            await asyncio.sleep(0.1)
            return await self.get_with_mutex(key, fetch_fn)


# =============================================================================
# RATE LIMITER
# =============================================================================


class SlidingWindowRateLimiter:
    """Rate limiter con sliding window."""

    def __init__(self, redis: RedisSimulator, window_ms: int = 60000, max_requests: int = 100):
        self.redis = redis
        self.window_ms = window_ms
        self.max_requests = max_requests

    async def is_allowed(self, identifier: str) -> tuple[bool, int]:
        """
        Verifica si una request está permitida.
        Returns: (allowed, remaining_requests)
        """
        key = f"ratelimit:{identifier}"
        now = time.time() * 1000
        window_start = now - self.window_ms

        # Simular zremrangebyscore + zcard + zadd
        if key not in self.redis._sorted_sets:
            self.redis._sorted_sets[key] = {}

        # Eliminar requests fuera de la ventana
        self.redis._sorted_sets[key] = {
            k: v for k, v in self.redis._sorted_sets[key].items() if v > window_start
        }

        current_count = len(self.redis._sorted_sets[key])

        if current_count < self.max_requests:
            # Agregar request actual
            await self.redis.zadd(key, now, f"{now}:{random.random()}")
            remaining = self.max_requests - current_count - 1
            return True, max(0, remaining)
        else:
            return False, 0


# =============================================================================
# LEADERBOARD
# =============================================================================


class Leaderboard:
    """Leaderboard usando sorted sets."""

    def __init__(self, redis: RedisSimulator, name: str):
        self.redis = redis
        self.key = f"leaderboard:{name}"

    async def add_score(self, user_id: str, score: float) -> None:
        """Establece score de un usuario."""
        await self.redis.zadd(self.key, score, user_id)

    async def increment_score(self, user_id: str, increment: float) -> float:
        """Incrementa score de un usuario."""
        return await self.redis.zincrby(self.key, increment, user_id)

    async def get_top(self, count: int) -> list[dict]:
        """Obtiene top N usuarios."""
        results = await self.redis.zrevrange(self.key, 0, count - 1, withscores=True)

        leaderboard = []
        for i in range(0, len(results), 2):
            leaderboard.append(
                {"rank": i // 2 + 1, "user_id": results[i], "score": float(results[i + 1])}
            )
        return leaderboard

    async def get_rank(self, user_id: str) -> int | None:
        """Obtiene rank de un usuario (1-indexed)."""
        rank = await self.redis.zrevrank(self.key, user_id)
        return rank + 1 if rank is not None else None


# =============================================================================
# SESSION MANAGER
# =============================================================================


class SessionManager:
    """Gestor de sesiones con Redis."""

    def __init__(self, redis: RedisSimulator, ttl: int = 86400):
        self.redis = redis
        self.ttl = ttl

    async def create(self, user_id: str, data: dict) -> str:
        """Crea una nueva sesión."""
        session_id = hashlib.sha256(
            f"{user_id}:{time.time()}:{random.random()}".encode()
        ).hexdigest()[:32]

        session_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "last_access": time.time(),
            **data,
        }

        await self.redis.set(f"session:{session_id}", json.dumps(session_data), ex=self.ttl)
        logger.info(f"Session created: {session_id[:8]}...")
        return session_id

    async def get(self, session_id: str) -> dict | None:
        """Obtiene datos de sesión."""
        data = await self.redis.get(f"session:{session_id}")
        if data:
            session = json.loads(data)
            # Refresh TTL
            await self.redis.expire(f"session:{session_id}", self.ttl)
            return session
        return None

    async def destroy(self, session_id: str) -> bool:
        """Destruye una sesión."""
        result = await self.redis.delete(f"session:{session_id}")
        return result > 0


# =============================================================================
# DEMO
# =============================================================================


async def demo():
    """Demostración de patrones de caching."""
    print("\n" + "=" * 60)
    print("REDIS CACHING PATTERNS DEMO")
    print("=" * 60)

    redis = RedisSimulator()

    # =============================================================================
    # DEMO 1: Cache-Aside Pattern
    # =============================================================================
    print("\n--- DEMO 1: Cache-Aside Pattern ---")

    cache = CacheAside(redis, ttl=300)

    async def fetch_user(user_id: str):
        """Simula fetch de DB."""
        await asyncio.sleep(0.1)  # Simular latencia
        return {"id": user_id, "name": f"User {user_id}", "email": f"{user_id}@example.com"}

    # Primera llamada - MISS
    user1 = await cache.get("user:123", lambda: fetch_user("123"))
    print(f"First call (MISS): {user1['name']}")

    # Segunda llamada - HIT
    user1_cached = await cache.get("user:123", lambda: fetch_user("123"))
    print(f"Second call (HIT): {user1_cached['name']}")

    # Tercera llamada diferente - MISS
    user2 = await cache.get("user:456", lambda: fetch_user("456"))
    print(f"Third call (MISS): {user2['name']}")

    print(f"DB calls: {cache._db_calls}")
    print(f"Cache hit rate: {redis.get_hit_rate():.2%}")

    # =============================================================================
    # DEMO 2: Rate Limiter
    # =============================================================================
    print("\n--- DEMO 2: Sliding Window Rate Limiter ---")

    limiter = SlidingWindowRateLimiter(redis, window_ms=60000, max_requests=5)

    for i in range(7):
        allowed, remaining = await limiter.is_allowed("user:alice")
        status = "✅ ALLOWED" if allowed else "❌ BLOCKED"
        print(f"Request {i + 1}: {status} (remaining: {remaining})")

    # =============================================================================
    # DEMO 3: Leaderboard
    # =============================================================================
    print("\n--- DEMO 3: Leaderboard ---")

    leaderboard = Leaderboard(redis, "game-scores")

    # Añadir scores
    await leaderboard.add_score("player1", 1500)
    await leaderboard.add_score("player2", 2200)
    await leaderboard.add_score("player3", 1800)
    await leaderboard.add_score("player4", 3100)
    await leaderboard.add_score("player5", 950)

    # Incrementar score
    new_score = await leaderboard.increment_score("player1", 500)
    print(f"player1 new score: {new_score}")

    # Top 3
    top3 = await leaderboard.get_top(3)
    print("\nTop 3:")
    for entry in top3:
        print(f"  #{entry['rank']} {entry['user_id']}: {entry['score']}")

    # Rank de un jugador
    rank = await leaderboard.get_rank("player3")
    print(f"\nplayer3 rank: #{rank}")

    # =============================================================================
    # DEMO 4: Session Manager
    # =============================================================================
    print("\n--- DEMO 4: Session Manager ---")

    sessions = SessionManager(redis, ttl=3600)

    # Crear sesión
    session_id = await sessions.create(
        "user:bob", {"email": "bob@example.com", "roles": ["user", "admin"]}
    )
    print(f"Session created: {session_id[:16]}...")

    # Obtener sesión
    session_data = await sessions.get(session_id)
    print(f"Session data: user_id={session_data['user_id']}, roles={session_data['roles']}")

    # Destruir sesión
    destroyed = await sessions.destroy(session_id)
    print(f"Session destroyed: {destroyed}")

    # Verificar que no existe
    session_data = await sessions.get(session_id)
    print(f"Session after destroy: {session_data}")

    # =============================================================================
    # ESTADÍSTICAS FINALES
    # =============================================================================
    print("\n" + "=" * 60)
    print("ESTADÍSTICAS FINALES")
    print("=" * 60)
    print(f"Cache hits: {redis.stats['hits']}")
    print(f"Cache misses: {redis.stats['misses']}")
    print(f"Cache sets: {redis.stats['sets']}")
    print(f"Cache deletes: {redis.stats['deletes']}")
    print(f"Hit rate: {redis.get_hit_rate():.2%}")
    print("\nPatterns demonstrated:")
    print("  ✅ Cache-Aside (lazy loading)")
    print("  ✅ Sliding Window Rate Limiter")
    print("  ✅ Leaderboard (sorted sets)")
    print("  ✅ Session Management")


def main():
    """Entry point."""
    asyncio.run(demo())


if __name__ == "__main__":
    main()
