#!/usr/bin/env python3
"""
Smart Cache - Sistema de caché inteligente con invalidación automática

Features:
- Cache por agente/tarea con TTL configurable
- Invalidación semántica (detecta cuando el contexto cambió)
- Compresión automática de valores grandes
- Estadísticas de uso para optimización
- Persistencia entre sesiones
"""

import hashlib
import json
import threading
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """Entrada individual de cache"""

    key: str
    value: Any
    created_at: float
    expires_at: float
    hits: int = 0
    last_accessed: float = 0
    compressed: bool = False
    size_bytes: int = 0
    tags: list[str] = field(default_factory=list)
    context_hash: str = ""  # Hash del contexto cuando se creó


@dataclass
class CacheStats:
    """Estadísticas del cache"""

    total_entries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    total_size_bytes: int = 0
    hit_rate: float = 0.0
    avg_entry_age_seconds: float = 0.0
    entries_by_tag: dict[str, int] = field(default_factory=dict)


class SmartCache:
    """Cache inteligente con invalidación semántica"""

    DEFAULT_TTL = 3600  # 1 hora
    MAX_ENTRY_SIZE = 1024 * 1024  # 1MB antes de comprimir
    COMPRESSION_THRESHOLD = 10 * 1024  # 10KB

    def __init__(
        self, cache_dir: Path | None = None, max_size_mb: int = 100, default_ttl: int = DEFAULT_TTL
    ):
        self.cache_dir = cache_dir or Path(".agent/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl

        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = CacheStats()

        # Cargar cache persistido
        self._load_cache()

        # Invalidadores registrados
        self._invalidators: list[Callable[[str, CacheEntry], bool]] = []

    def _generate_key(self, namespace: str, identifier: str, context: dict | None = None) -> str:
        """Generar clave única para cache"""
        base = f"{namespace}:{identifier}"
        if context:
            context_str = json.dumps(context, sort_keys=True)
            context_hash = hashlib.md5(context_str.encode(), usedforsecurity=False).hexdigest()[:8]
            base = f"{base}:{context_hash}"
        return hashlib.sha256(base.encode()).hexdigest()[:32]

    def _compute_context_hash(self, context: dict | None) -> str:
        """Calcular hash del contexto para invalidación semántica"""
        if not context:
            return ""
        return hashlib.md5(
            json.dumps(context, sort_keys=True).encode(), usedforsecurity=False
        ).hexdigest()

    def _serialize(self, value: Any) -> tuple[bytes, bool]:
        """Serialize using JSON bytes only to avoid unsafe object deserialization."""
        data = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        compressed = False

        if len(data) > self.COMPRESSION_THRESHOLD:
            compressed_data = zlib.compress(data, level=6)
            if len(compressed_data) < len(data) * 0.8:  # Solo si ahorra >20%
                data = compressed_data
                compressed = True

        return data, compressed

    def _deserialize(self, data: bytes, compressed: bool) -> Any:
        """Deserialize bytes back to original value (inverse of _serialize)."""
        if compressed:
            data = zlib.decompress(data)
        return json.loads(data.decode("utf-8"))

    def get(
        self, namespace: str, identifier: str, context: dict | None = None, default: Any = None
    ) -> Any:
        """Obtener valor del cache"""
        key = self._generate_key(namespace, identifier, context)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.total_misses += 1
                return default

            # Verificar expiración
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats.total_misses += 1
                return default

            # Verificar invalidadores
            for invalidator in self._invalidators:
                if invalidator(key, entry):
                    del self._cache[key]
                    self._stats.total_misses += 1
                    return default

            # Hit exitoso
            entry.hits += 1
            entry.last_accessed = time.time()
            self._stats.total_hits += 1

            return entry.value

    def set(
        self,
        namespace: str,
        identifier: str,
        value: Any,
        context: dict | None = None,
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Guardar valor en cache"""
        key = self._generate_key(namespace, identifier, context)
        ttl = ttl or self.default_ttl

        with self._lock:
            # Serializar
            try:
                data, compressed = self._serialize(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("Value is not JSON-serializable") from exc

            # Verificar tamaño
            if len(data) > self.MAX_ENTRY_SIZE:
                raise ValueError(f"Entry too large: {len(data)} bytes")

            # Crear entrada
            now = time.time()
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + ttl,
                compressed=compressed,
                size_bytes=len(data),
                tags=tags or [],
                context_hash=self._compute_context_hash(context),
                last_accessed=now,
            )

            # Verificar espacio
            self._ensure_space(len(data))

            self._cache[key] = entry
            self._stats.total_entries = len(self._cache)

            # Persistir periódicamente
            if len(self._cache) % 10 == 0:
                self._persist_cache()

            return key

    def invalidate(
        self,
        namespace: str | None = None,
        identifier: str | None = None,
        tags: list[str] | None = None,
        pattern: str | None = None,
    ) -> int:
        """Invalidar entradas del cache"""
        count = 0

        with self._lock:
            keys_to_delete = []

            for key, entry in self._cache.items():
                should_delete = False

                # Por tags
                if tags and any(t in entry.tags for t in tags):
                    should_delete = True

                # Por namespace/identifier (simplificado)
                if namespace and identifier:
                    test_key = self._generate_key(namespace, identifier)
                    if key.startswith(test_key[:16]):
                        should_delete = True

                if should_delete:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._cache[key]
                count += 1

            self._stats.total_entries = len(self._cache)

        return count

    def invalidate_by_context_change(self, old_context: dict, new_context: dict) -> int:
        """Invalidar entradas cuyo contexto ha cambiado"""
        old_hash = self._compute_context_hash(old_context)
        new_hash = self._compute_context_hash(new_context)
        if old_hash == new_hash:
            return 0
        count = 0

        with self._lock:
            keys_to_delete = []
            for key, entry in self._cache.items():
                if entry.context_hash == old_hash:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._cache[key]
                count += 1

        return count

    def register_invalidator(self, func: Callable[[str, CacheEntry], bool]):
        """Registrar función de invalidación personalizada"""
        self._invalidators.append(func)

    def _ensure_space(self, needed_bytes: int):
        """Asegurar espacio disponible, eliminando entradas viejas si es necesario"""
        current_size = sum(e.size_bytes for e in self._cache.values())

        if current_size + needed_bytes <= self.max_size_bytes:
            return

        # Ordenar por último acceso (LRU)
        entries = sorted(self._cache.items(), key=lambda x: x[1].last_accessed)

        freed = 0
        for key, entry in entries:
            if current_size - freed + needed_bytes <= self.max_size_bytes:
                break
            del self._cache[key]
            freed += entry.size_bytes

    def get_stats(self) -> CacheStats:
        """Obtener estadísticas del cache"""
        with self._lock:
            total_hits = self._stats.total_hits
            total_misses = self._stats.total_misses
            total = total_hits + total_misses

            self._stats.hit_rate = (total_hits / total * 100) if total > 0 else 0
            self._stats.total_entries = len(self._cache)
            self._stats.total_size_bytes = sum(e.size_bytes for e in self._cache.values())

            # Calcular edad promedio
            now = time.time()
            if self._cache:
                ages = [now - e.created_at for e in self._cache.values()]
                self._stats.avg_entry_age_seconds = sum(ages) / len(ages)

            # Contar por tags
            tag_counts: dict[str, int] = {}
            for entry in self._cache.values():
                for tag in entry.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            self._stats.entries_by_tag = tag_counts

            return self._stats

    def _persist_cache(self):
        """Persistir cache a disco"""
        cache_file = self.cache_dir / "cache_data.json"

        # Serializar solo metadata, no valores grandes
        data = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "total_hits": self._stats.total_hits,
                "total_misses": self._stats.total_misses,
            },
            "entries": {},
        }

        for key, entry in self._cache.items():
            try:
                # Solo guardar valores serializables a JSON
                serialized = json.dumps(entry.value)
                if len(serialized) < 10000:  # Solo valores pequeños
                    data["entries"][key] = {  # type: ignore[index]  # dict value assignment
                        "value": entry.value,
                        "created_at": entry.created_at,
                        "expires_at": entry.expires_at,
                        "hits": entry.hits,
                        "tags": entry.tags,
                        "context_hash": entry.context_hash,
                    }
            except (TypeError, ValueError):
                pass  # Skip non-JSON-serializable values

        cache_file.write_text(json.dumps(data, indent=2))

    def _load_cache(self):
        """Cargar cache desde disco"""
        cache_file = self.cache_dir / "cache_data.json"

        if not cache_file.exists():
            return

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            now = time.time()

            # Restaurar stats
            if "stats" in data:
                self._stats.total_hits = data["stats"].get("total_hits", 0)
                self._stats.total_misses = data["stats"].get("total_misses", 0)

            # Restaurar entradas no expiradas
            for key, entry_data in data.get("entries", {}).items():
                if entry_data["expires_at"] > now:
                    self._cache[key] = CacheEntry(
                        key=key,
                        value=entry_data["value"],
                        created_at=entry_data["created_at"],
                        expires_at=entry_data["expires_at"],
                        hits=entry_data.get("hits", 0),
                        last_accessed=now,
                        tags=entry_data.get("tags", []),
                        context_hash=entry_data.get("context_hash", ""),
                        size_bytes=len(json.dumps(entry_data["value"])),
                    )
        except Exception:
            pass  # Si falla, empezar con cache vacío

    def clear(self):
        """Limpiar todo el cache"""
        with self._lock:
            self._cache.clear()
            self._stats = CacheStats()
            cache_file = self.cache_dir / "cache_data.json"
            if cache_file.exists():
                cache_file.unlink()

    def warm_up(self, entries: list[dict]):
        """Pre-cargar entradas en el cache"""
        for entry in entries:
            self.set(
                namespace=entry.get("namespace", "default"),
                identifier=entry["identifier"],
                value=entry["value"],
                ttl=entry.get("ttl"),
                tags=entry.get("tags"),
            )


# Cache global singleton
_cache_instance: SmartCache | None = None
_cache_lock = threading.Lock()


def get_smart_cache() -> SmartCache:
    """Obtener instancia singleton del cache"""
    global _cache_instance

    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = SmartCache()

    return _cache_instance


# Decorador para cachear resultados de funciones
def cached(
    namespace: str = "function",
    ttl: int | None = None,
    tags: list[str] | None = None,
    key_func: Callable | None = None,
):
    """Decorador para cachear resultados de funciones"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_smart_cache()

            # Generar identificador
            if key_func:
                identifier = key_func(*args, **kwargs)
            else:
                identifier = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"

            # Intentar obtener del cache
            result = cache.get(namespace, identifier)
            if result is not None:
                return result

            # Ejecutar función
            result = func(*args, **kwargs)

            # Guardar en cache
            cache.set(namespace, identifier, result, ttl=ttl, tags=tags)

            return result

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# Ejemplo de uso y CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smart Cache Manager")
    parser.add_argument("command", choices=["stats", "clear", "list", "test"])
    parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    cache = get_smart_cache()

    if args.command == "stats":
        stats = cache.get_stats()
        if args.json:
            print(
                json.dumps(
                    {
                        "total_entries": stats.total_entries,
                        "total_hits": stats.total_hits,
                        "total_misses": stats.total_misses,
                        "hit_rate": round(stats.hit_rate, 2),
                        "total_size_mb": round(stats.total_size_bytes / 1024 / 1024, 2),
                        "avg_age_minutes": round(stats.avg_entry_age_seconds / 60, 1),
                        "entries_by_tag": stats.entries_by_tag,
                    },
                    indent=2,
                )
            )
        else:
            print("\n=== Smart Cache Statistics ===")
            print(f"Entries: {stats.total_entries}")
            print(f"Hits: {stats.total_hits}")
            print(f"Misses: {stats.total_misses}")
            print(f"Hit Rate: {stats.hit_rate:.1f}%")
            print(f"Size: {stats.total_size_bytes / 1024:.1f} KB")
            print(f"Avg Age: {stats.avg_entry_age_seconds / 60:.1f} min")
            if stats.entries_by_tag:
                print(f"By Tag: {stats.entries_by_tag}")

    elif args.command == "clear":
        cache.clear()
        print("Cache cleared")

    elif args.command == "list":
        with cache._lock:
            for key, entry in list(cache._cache.items())[:20]:
                print(f"{key[:16]}... | hits:{entry.hits} | tags:{entry.tags}")

    elif args.command == "test":
        # Test básico
        print("Testing Smart Cache...")

        # Test set/get
        cache.set("test", "key1", {"data": "value1"}, tags=["test"])
        result = cache.get("test", "key1")
        assert result == {"data": "value1"}, "Basic set/get failed"
        print("✓ Basic set/get works")

        # Test cache hit
        result = cache.get("test", "key1")
        assert result is not None, "Cache hit failed"
        print("✓ Cache hit works")

        # Test miss
        result = cache.get("test", "nonexistent")
        assert result is None, "Cache miss failed"
        print("✓ Cache miss works")

        # Test invalidation
        count = cache.invalidate(tags=["test"])
        assert count > 0, "Invalidation failed"
        print(f"✓ Invalidated {count} entries")

        # Test decorator
        @cached(namespace="test_func", ttl=60)
        def expensive_function(x):
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)  # Should be cached
        assert result1 == result2 == 10, "Decorator failed"
        print("✓ Decorator caching works")

        stats = cache.get_stats()
        print(f"\nFinal stats: {stats.total_hits} hits, {stats.total_misses} misses")
        print("\nAll tests passed!")
