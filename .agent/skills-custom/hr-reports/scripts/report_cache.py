"""Report caching engine for HR Reports (PHASE 3 optimization).

Implements in-memory caching with 30-minute TTL and LRU eviction.
"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default cache settings
DEFAULT_CACHE_SIZE_MB = 100
DEFAULT_TTL_MINUTES = 30


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""

    data: Any
    timestamp: float
    size_bytes: int

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if entry has expired.

        Args:
            ttl_seconds: Time-to-live in seconds.

        Returns:
            True if expired, False otherwise.
        """
        return time.time() - self.timestamp > ttl_seconds


class ReportCache:
    """In-memory cache for HR reports with TTL and LRU eviction.

    PHASE 3 optimization: Reduces redundant report generation.
    """

    def __init__(
        self,
        max_size_mb: int = DEFAULT_CACHE_SIZE_MB,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
    ) -> None:
        """Initialize cache.

        Args:
            max_size_mb: Maximum cache size in MB.
            ttl_minutes: Time-to-live for entries in minutes.
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.ttl_seconds = ttl_minutes * 60
        self.cache: dict[str, CacheEntry] = {}
        self.current_size = 0

        logger.info(f"ReportCache initialized: {max_size_mb}MB, {ttl_minutes}min TTL")

    def _generate_key(
        self,
        operation: str,
        date_from: str,
        date_to: str,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Generate cache key from parameters.

        Args:
            operation: Report operation (e.g., 'attendance', 'payroll').
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).
            filters: Optional filter dict.

        Returns:
            Cache key (SHA256 hash).
        """
        key_str = f"{operation}:{date_from}:{date_to}"
        if filters:
            filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_str += f":{filter_str}"

        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(
        self,
        operation: str,
        date_from: str,
        date_to: str,
        filters: dict[str, Any] | None = None,
    ) -> Any | None:
        """Get cached report.

        Args:
            operation: Report operation.
            date_from: Start date.
            date_to: End date.
            filters: Optional filters.

        Returns:
            Cached data or None if expired/not found.
        """
        key = self._generate_key(operation, date_from, date_to, filters)

        if key not in self.cache:
            logger.debug(f"Cache miss: {key[:8]}...")
            return None

        entry = self.cache[key]

        # Check expiration
        if entry.is_expired(self.ttl_seconds):
            del self.cache[key]
            self.current_size -= entry.size_bytes
            logger.info(f"Cache entry expired: {key[:8]}...")
            return None

        logger.info(f"Cache hit: {key[:8]}...")
        return entry.data

    def put(
        self,
        data: Any,
        operation: str,
        date_from: str,
        date_to: str,
        filters: dict[str, Any] | None = None,
        size_estimate_bytes: int | None = None,
    ) -> None:
        """Store data in cache.

        Args:
            data: Data to cache.
            operation: Report operation.
            date_from: Start date.
            date_to: End date.
            filters: Optional filters.
            size_estimate_bytes: Optional size estimate (auto-estimate if None).
        """
        key = self._generate_key(operation, date_from, date_to, filters)

        # Estimate size if not provided
        if size_estimate_bytes is None:
            size_estimate_bytes = len(str(data).encode())

        # Evict if adding would exceed limit (LRU)
        while self.current_size + size_estimate_bytes > self.max_size_bytes and self.cache:
            # Find oldest entry
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].timestamp,
            )
            oldest_entry = self.cache.pop(oldest_key)
            self.current_size -= oldest_entry.size_bytes
            logger.debug(f"LRU evicted: {oldest_key[:8]}...")

        # Store entry
        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            size_bytes=size_estimate_bytes,
        )
        self.cache[key] = entry
        self.current_size += size_estimate_bytes

        logger.info(
            f"Cached: {key[:8]}... ({size_estimate_bytes / 1024:.1f}KB, "
            f"total: {self.current_size / 1024 / 1024:.1f}MB)"
        )

    def invalidate(
        self,
        operation: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> int:
        """Invalidate cache entries.

        Args:
            operation: Specific operation to invalidate (or None for all).
            date_from: Date range start (or None).
            date_to: Date range end (or None).

        Returns:
            Number of entries invalidated.
        """
        keys_to_remove = []

        for key, entry in self.cache.items():
            # If operation specified, match it
            if operation:
                key_parts = key.split(":")
                if key_parts[0] != operation:
                    continue

            keys_to_remove.append(key)

        # Remove invalidated entries
        for key in keys_to_remove:
            entry = self.cache.pop(key)
            self.current_size -= entry.size_bytes

        logger.info(f"Invalidated {len(keys_to_remove)} cache entries")
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.current_size = 0
        logger.info("Cache cleared")

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache stats (size, entries, etc).
        """
        expired_count = sum(
            1 for entry in self.cache.values() if entry.is_expired(self.ttl_seconds)
        )

        return {
            "entries": len(self.cache),
            "expired_entries": expired_count,
            "current_size_mb": self.current_size / 1024 / 1024,
            "max_size_mb": self.max_size_bytes / 1024 / 1024,
            "utilization_percent": (self.current_size / self.max_size_bytes * 100)
            if self.max_size_bytes > 0
            else 0,
        }


# Global cache instance
_report_cache: ReportCache | None = None


def get_cache() -> ReportCache:
    """Get or create global report cache.

    Returns:
        ReportCache instance.
    """
    global _report_cache
    if _report_cache is None:
        _report_cache = ReportCache()
    return _report_cache


def init_cache(max_size_mb: int = DEFAULT_CACHE_SIZE_MB) -> ReportCache:
    """Initialize global cache with custom size.

    Args:
        max_size_mb: Maximum cache size in MB.

    Returns:
        Initialized ReportCache instance.
    """
    global _report_cache
    _report_cache = ReportCache(max_size_mb=max_size_mb)
    return _report_cache
