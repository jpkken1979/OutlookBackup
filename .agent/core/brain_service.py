"""BrainService — query gateway /v1/brain with local caching and formatting."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, UTC
from pathlib import Path
from typing import Any

import aiohttp

log = logging.getLogger(__name__)


@dataclass
class BrainNode:
    """Represents a Brain Network node."""

    slug: str
    title: str
    type: str
    area: str
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    importance: str = "normal"
    date: str = ""
    status: str = "active"
    version: int = 1
    topic_key: str = ""
    superseded_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "slug": self.slug,
            "title": self.title,
            "type": self.type,
            "area": self.area,
            "tags": self.tags,
            "related": self.related,
            "importance": self.importance,
            "date": self.date,
            "status": self.status,
            "version": self.version,
            "topic_key": self.topic_key,
            "superseded_by": self.superseded_by,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> BrainNode:
        """Create from dictionary."""
        return BrainNode(
            slug=data.get("slug", ""),
            title=data.get("title", ""),
            type=data.get("type", ""),
            area=data.get("area", ""),
            tags=data.get("tags", []),
            related=data.get("related", []),
            importance=data.get("importance", "normal"),
            date=data.get("date", ""),
            status=data.get("status", "active"),
            version=data.get("version", 1),
            topic_key=data.get("topic_key", ""),
            superseded_by=data.get("superseded_by"),
        )


@dataclass
class BrainQueryResult:
    """Result from Brain query."""

    query: str
    count: int
    results: list[BrainNode] = field(default_factory=list)
    cached: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "count": self.count,
            "results": [r.to_dict() for r in self.results],
            "cached": self.cached,
            "timestamp": self.timestamp,
        }


class BrainQueryCache:
    """SQLite-based cache for Brain queries."""

    def __init__(self, cache_path: Path | None = None):
        """Initialize query cache.

        Args:
            cache_path: Path to the cache database or an existing directory that
                should contain it. Defaults to ~/.antigravity/brain_query_cache.db.
        """
        if cache_path is None:
            cache_path = Path.home() / ".antigravity" / "brain_query_cache.db"
        else:
            cache_path = Path(cache_path)
            if cache_path.is_dir():
                cache_path /= "brain_query_cache.db"

        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_cache()

    def _init_cache(self) -> None:
        """Initialize cache schema."""
        conn = sqlite3.connect(str(self.cache_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL UNIQUE,
                    results TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ttl_seconds INTEGER DEFAULT 3600
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_brain_queries_timestamp
                ON brain_queries(timestamp DESC)
                """
            )
            conn.commit()
            log.info("Brain query cache initialized at %s", self.cache_path)
        finally:
            conn.close()

    async def get(self, query: str, ttl_seconds: int = 3600) -> BrainQueryResult | None:
        """Get cached query result if valid.

        Args:
            query: Query string
            ttl_seconds: Time-to-live for cache entries (default 1 hour)

        Returns:
            BrainQueryResult if found and valid, None otherwise
        """

        def _get() -> BrainQueryResult | None:
            conn = sqlite3.connect(str(self.cache_path))
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT results, timestamp FROM brain_queries
                    WHERE query = ?
                    """,
                    (query,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                cached_time = datetime.fromisoformat(row["timestamp"])
                if (datetime.now(UTC) - cached_time).total_seconds() > ttl_seconds:
                    # Cache expired
                    return None

                data = json.loads(row["results"])
                result = BrainQueryResult(
                    query=data["query"],
                    count=data["count"],
                    results=[BrainNode.from_dict(r) for r in data["results"]],
                    cached=True,
                    timestamp=row["timestamp"],
                )
                return result
            finally:
                conn.close()

        return await asyncio.to_thread(_get)

    async def set(self, result: BrainQueryResult, ttl_seconds: int = 3600) -> None:
        """Cache query result.

        Args:
            result: BrainQueryResult to cache
            ttl_seconds: Time-to-live for cache entry
        """

        def _set() -> None:
            conn = sqlite3.connect(str(self.cache_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO brain_queries
                    (query, results, timestamp, ttl_seconds)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        result.query,
                        json.dumps(result.to_dict()),
                        result.timestamp,
                        ttl_seconds,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_set)

    async def clear_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """

        def _clear() -> int:
            conn = sqlite3.connect(str(self.cache_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM brain_queries
                    WHERE datetime(timestamp) < datetime('now', '-1 hour')
                    """
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

        return await asyncio.to_thread(_clear)


class BrainService:
    """Service to query Brain Network from gateway with caching."""

    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:4747",
        cache_path: Path | None = None,
        cache_ttl_seconds: int = 3600,
    ):
        """Initialize Brain service.

        Args:
            gateway_url: Gateway base URL
            cache_path: Path to cache database
            cache_ttl_seconds: Cache TTL in seconds
        """
        self.gateway_url = gateway_url.rstrip("/")
        self.cache = BrainQueryCache(cache_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close aiohttp session."""
        if self._session:
            await self._session.close()

    async def query(
        self,
        query: str,
        limit: int = 5,
        use_cache: bool = True,
    ) -> BrainQueryResult:
        """Query Brain Network.

        Args:
            query: Search query
            limit: Max results
            use_cache: Whether to use cache

        Returns:
            BrainQueryResult with nodes and metadata
        """
        # Check cache first
        if use_cache:
            cached = await self.cache.get(query, self.cache_ttl_seconds)
            if cached:
                log.debug("Brain query cache hit for: %s", query)
                return cached

        # Query gateway
        url = f"{self.gateway_url}/v1/brain/query"
        params: dict[str, str | int] = {"q": query, "limit": min(limit, 20)}

        try:
            session = await self._get_session()
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    log.error("Brain query failed: HTTP %d", resp.status)
                    return BrainQueryResult(query=query, count=0, results=[])

                data = await resp.json()
                if data.get("status") != "ok":
                    log.error("Brain query error: %s", data.get("error"))
                    return BrainQueryResult(query=query, count=0, results=[])

                query_data = data.get("data", {})
                results = [BrainNode.from_dict(r) for r in query_data.get("results", [])]

                result = BrainQueryResult(
                    query=query,
                    count=len(results),
                    results=results,
                    cached=False,
                )

                # Cache the result
                if use_cache and results:
                    await self.cache.set(result, self.cache_ttl_seconds)

                return result

        except TimeoutError:
            log.error("Brain query timeout for: %s", query)
            return BrainQueryResult(query=query, count=0, results=[])
        except Exception as e:
            log.exception("Brain query exception: %s", e)
            return BrainQueryResult(query=query, count=0, results=[])

    async def get_node(self, slug: str) -> BrainNode | None:
        """Get full node details.

        Args:
            slug: Node slug

        Returns:
            BrainNode if found, None otherwise
        """
        url = f"{self.gateway_url}/v1/brain/node/{slug}"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    log.error("Get node failed: HTTP %d", resp.status)
                    return None

                data = await resp.json()
                if data.get("status") != "ok":
                    log.error("Get node error: %s", data.get("error"))
                    return None

                node_data = data.get("data", {})
                return BrainNode.from_dict(node_data)

        except Exception as e:
            log.exception("Get node exception: %s", e)
            return None

    async def get_stats(self) -> dict[str, Any]:
        """Get Brain Network statistics.

        Returns:
            Dictionary with stats
        """
        url = f"{self.gateway_url}/v1/brain/stats"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    log.error("Get stats failed: HTTP %d", resp.status)
                    return {}

                data = await resp.json()
                if data.get("status") != "ok":
                    return {}

                return data.get("data", {})

        except Exception as e:
            log.exception("Get stats exception: %s", e)
            return {}

    async def timeline(
        self,
        slug: str | None = None,
        topic_key: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get timeline of nodes.

        Args:
            slug: Optional node slug
            topic_key: Optional topic key
            limit: Max results

        Returns:
            List of timeline items
        """
        url = f"{self.gateway_url}/v1/brain/timeline"
        params: dict[str, Any] = {"limit": min(limit, 100)}

        if slug:
            params["slug"] = slug
        if topic_key:
            params["topic_key"] = topic_key

        try:
            session = await self._get_session()
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    log.error("Timeline query failed: HTTP %d", resp.status)
                    return []

                data = await resp.json()
                if data.get("status") != "ok":
                    return []

                return data.get("data", {}).get("items", [])

        except Exception as e:
            log.exception("Timeline query exception: %s", e)
            return []
