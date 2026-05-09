#!/usr/bin/env python3
"""
SlidingWindowRateLimiter — 3-Window Sliding Rate Limiter with Tier Support.

Tracks requests across three time windows simultaneously:
- Lifetime: total requests ever (for free tier limits)
- Per-minute: sliding 60-second window
- Per-day: sliding 24-hour window

Each window must pass for a request to be allowed. Includes concurrent
request tracking and burst allowance for short spikes.

Inspired by G0DM0D3's multi-window rate limiting architecture.

Usage:
    from .agent.core.rate_limiter import SlidingWindowRateLimiter, RateTier

    limiter = SlidingWindowRateLimiter(default_tier=RateTier.STANDARD)
    result = limiter.check("client-123")

    if result.allowed:
        try:
            # process request
            ...
        finally:
            limiter.release("client-123")
    else:
        # return 429 with result.headers
        ...
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.core.rate_limiter")

__all__ = [
    "RateTier",
    "TierConfig",
    "RateLimitState",
    "RateLimitResult",
    "SlidingWindowRateLimiter",
    "create_rate_limit_middleware",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MINUTE_WINDOW = 60.0  # seconds
_DAY_WINDOW = 86400.0  # seconds
_INACTIVITY_EXPIRY = 86400.0  # auto-expire client state after 24h
_CLIENT_ID_HASH_KEY = b"antigravity-rate-limiter-v1"


# ---------------------------------------------------------------------------
# Enums & data structures
# ---------------------------------------------------------------------------


class RateTier(str, Enum):
    """Rate limiting tier levels.

    Attributes:
        FREE: Limited lifetime and low per-minute/day limits.
        STANDARD: No lifetime cap, moderate throughput.
        PREMIUM: High throughput with generous burst allowance.
        UNLIMITED: No rate limits applied.
    """

    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    UNLIMITED = "unlimited"


@dataclass
class TierConfig:
    """Configuration for a rate limiting tier.

    Attributes:
        name: The tier this config belongs to.
        lifetime_limit: Total requests ever allowed (0 = unlimited).
        per_minute_limit: Max requests in a sliding 60s window (0 = unlimited).
        per_day_limit: Max requests in a sliding 24h window (0 = unlimited).
        burst_allowance: Extra requests allowed beyond per_minute_limit in bursts.
        max_concurrent: Max simultaneous in-flight requests (0 = unlimited).
    """

    name: RateTier
    lifetime_limit: int = 0
    per_minute_limit: int = 60
    per_day_limit: int = 1000
    burst_allowance: int = 10
    max_concurrent: int = 5


# Default configurations per tier
DEFAULT_TIER_CONFIGS: dict[RateTier, TierConfig] = {
    RateTier.FREE: TierConfig(
        name=RateTier.FREE,
        lifetime_limit=500,
        per_minute_limit=10,
        per_day_limit=100,
        burst_allowance=3,
        max_concurrent=2,
    ),
    RateTier.STANDARD: TierConfig(
        name=RateTier.STANDARD,
        lifetime_limit=0,
        per_minute_limit=150,
        per_day_limit=5000,
        burst_allowance=20,
        max_concurrent=25,  # restored after active_requests leak fixed
    ),
    RateTier.PREMIUM: TierConfig(
        name=RateTier.PREMIUM,
        lifetime_limit=0,
        per_minute_limit=300,
        per_day_limit=10000,
        burst_allowance=30,
        max_concurrent=30,
    ),
    RateTier.UNLIMITED: TierConfig(
        name=RateTier.UNLIMITED,
        lifetime_limit=0,
        per_minute_limit=0,
        per_day_limit=0,
        burst_allowance=0,
        max_concurrent=0,
    ),
}


@dataclass
class RateLimitState:
    """Internal state tracking for a single client.

    Attributes:
        client_id: Hashed identifier for the client.
        tier: Current rate limiting tier.
        lifetime_count: Total requests made by this client.
        minute_window: Timestamps of requests within the last 60 seconds.
        day_window: Timestamps of requests within the last 24 hours.
        active_requests: Number of currently in-flight requests.
        last_request: Monotonic timestamp of the last request.
        blocked_count: Number of times this client has been blocked.
    """

    client_id: str
    tier: RateTier
    lifetime_count: int = 0
    minute_window: deque[float] = field(default_factory=deque)
    day_window: deque[float] = field(default_factory=deque)
    active_requests: int = 0
    last_request: float = 0.0
    blocked_count: int = 0


@dataclass
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is permitted.
        client_id: The client identifier (hashed).
        tier: The tier applied to this check.
        reason: Human-readable reason if blocked, None if allowed.
        remaining_minute: Requests remaining in the current minute window.
        remaining_day: Requests remaining in the current day window.
        remaining_lifetime: Requests remaining in lifetime (0 = unlimited).
        retry_after_seconds: Seconds to wait before retrying (None if allowed).
        headers: HTTP headers to include in the response (X-RateLimit-*).
    """

    allowed: bool
    client_id: str
    tier: RateTier
    reason: str | None = None
    remaining_minute: int = 0
    remaining_day: int = 0
    remaining_lifetime: int = 0
    retry_after_seconds: float | None = None
    headers: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SlidingWindowRateLimiter
# ---------------------------------------------------------------------------


class SlidingWindowRateLimiter:
    """3-window sliding rate limiter with tier support.

    Tracks requests across three time windows simultaneously:
    - Lifetime: total requests ever (for free tier limits)
    - Per-minute: sliding 60-second window
    - Per-day: sliding 24-hour window

    Each window must pass for a request to be allowed. Concurrent request
    tracking prevents a single client from monopolizing server resources.

    Thread-safe: each client state is protected by its own lock.

    Attributes:
        default_tier: Tier applied to clients without an explicit assignment.
    """

    def __init__(
        self,
        default_tier: RateTier = RateTier.STANDARD,
        custom_tiers: dict[str, TierConfig] | None = None,
    ) -> None:
        """Initialize rate limiter with tier configurations.

        Args:
            default_tier: Default tier for new clients.
            custom_tiers: Optional custom tier configs keyed by tier name string.
                          Merged with (and overrides) defaults.
        """
        self.default_tier = default_tier
        self._configs: dict[RateTier, TierConfig] = dict(DEFAULT_TIER_CONFIGS)

        if custom_tiers:
            for name, config in custom_tiers.items():
                try:
                    tier = RateTier(name)
                    self._configs[tier] = config
                except ValueError:
                    logger.warning("Unknown tier name '%s' in custom_tiers, skipping", name)

        self._states: dict[str, RateLimitState] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._client_tiers: dict[str, RateTier] = {}
        self._created_at = time.monotonic()

        logger.info(
            "SlidingWindowRateLimiter initialized: default_tier=%s, tiers=%s",
            default_tier.value,
            [t.value for t in self._configs],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, client_id: str, tier: RateTier | None = None) -> RateLimitResult:
        """Check if a request is allowed and update counters.

        Evaluates all three windows (lifetime, minute, day) plus concurrent
        request limits. All windows must pass for the request to be allowed.
        On success, the request timestamp is recorded and the concurrent
        counter is incremented.

        Args:
            client_id: Unique identifier for the client (API key or IP).
            tier: Optional tier override. If None, uses the client's assigned
                  tier or the default tier.

        Returns:
            RateLimitResult with allow/deny decision and HTTP headers.
        """
        hashed_id = self._hash_client_id(client_id)
        resolved_tier = tier or self._client_tiers.get(hashed_id, self.default_tier)
        config = self._configs[resolved_tier]
        now = time.monotonic()

        # Unlimited tier bypasses all checks
        if resolved_tier == RateTier.UNLIMITED:
            state = self._get_or_create_state(hashed_id, resolved_tier)
            lock = self._get_lock(hashed_id)
            with lock:
                state.lifetime_count += 1
                state.last_request = now
            return RateLimitResult(
                allowed=True,
                client_id=hashed_id,
                tier=resolved_tier,
                remaining_minute=0,
                remaining_day=0,
                remaining_lifetime=0,
                headers=self._build_headers(config, 0, 0, 0, None),
            )

        state = self._get_or_create_state(hashed_id, resolved_tier)
        lock = self._get_lock(hashed_id)

        with lock:
            # Purge expired timestamps from windows
            self._purge_window(state.minute_window, now, _MINUTE_WINDOW)
            self._purge_window(state.day_window, now, _DAY_WINDOW)

            minute_count = len(state.minute_window)
            day_count = len(state.day_window)

            # Compute effective minute limit (base + burst)
            effective_minute_limit = config.per_minute_limit + config.burst_allowance

            # --- Check concurrent limit ---
            if config.max_concurrent > 0 and state.active_requests >= config.max_concurrent:
                state.blocked_count += 1
                result = RateLimitResult(
                    allowed=False,
                    client_id=hashed_id,
                    tier=resolved_tier,
                    reason=f"Max concurrent requests ({config.max_concurrent}) reached",
                    remaining_minute=max(0, effective_minute_limit - minute_count),
                    remaining_day=max(0, config.per_day_limit - day_count)
                    if config.per_day_limit > 0
                    else 0,
                    remaining_lifetime=self._remaining_lifetime(state, config),
                    retry_after_seconds=1.0,
                    headers=self._build_headers(
                        config,
                        max(0, effective_minute_limit - minute_count),
                        max(0, config.per_day_limit - day_count) if config.per_day_limit > 0 else 0,
                        self._remaining_lifetime(state, config),
                        1.0,
                    ),
                )
                logger.debug(
                    "Rate limit BLOCKED (concurrent): client=%s tier=%s active=%d max=%d",
                    hashed_id[:12],
                    resolved_tier.value,
                    state.active_requests,
                    config.max_concurrent,
                )
                return result

            # --- Check lifetime limit ---
            if config.lifetime_limit > 0 and state.lifetime_count >= config.lifetime_limit:
                state.blocked_count += 1
                result = RateLimitResult(
                    allowed=False,
                    client_id=hashed_id,
                    tier=resolved_tier,
                    reason=f"Lifetime limit ({config.lifetime_limit}) exhausted",
                    remaining_minute=max(0, effective_minute_limit - minute_count),
                    remaining_day=max(0, config.per_day_limit - day_count)
                    if config.per_day_limit > 0
                    else 0,
                    remaining_lifetime=0,
                    retry_after_seconds=None,
                    headers=self._build_headers(
                        config,
                        max(0, effective_minute_limit - minute_count),
                        max(0, config.per_day_limit - day_count) if config.per_day_limit > 0 else 0,
                        0,
                        None,
                    ),
                )
                logger.info(
                    "Rate limit BLOCKED (lifetime): client=%s tier=%s count=%d limit=%d",
                    hashed_id[:12],
                    resolved_tier.value,
                    state.lifetime_count,
                    config.lifetime_limit,
                )
                return result

            # --- Check per-minute window ---
            if config.per_minute_limit > 0 and minute_count >= effective_minute_limit:
                oldest = state.minute_window[0] if state.minute_window else now
                retry_after = max(0.0, _MINUTE_WINDOW - (now - oldest))
                state.blocked_count += 1
                result = RateLimitResult(
                    allowed=False,
                    client_id=hashed_id,
                    tier=resolved_tier,
                    reason=f"Per-minute limit ({config.per_minute_limit}+{config.burst_allowance} burst) exceeded",
                    remaining_minute=0,
                    remaining_day=max(0, config.per_day_limit - day_count)
                    if config.per_day_limit > 0
                    else 0,
                    remaining_lifetime=self._remaining_lifetime(state, config),
                    retry_after_seconds=round(retry_after, 2),
                    headers=self._build_headers(
                        config,
                        0,
                        max(0, config.per_day_limit - day_count) if config.per_day_limit > 0 else 0,
                        self._remaining_lifetime(state, config),
                        retry_after,
                    ),
                )
                logger.debug(
                    "Rate limit BLOCKED (minute): client=%s tier=%s count=%d limit=%d+%d retry=%.1fs",
                    hashed_id[:12],
                    resolved_tier.value,
                    minute_count,
                    config.per_minute_limit,
                    config.burst_allowance,
                    retry_after,
                )
                return result

            # --- Check per-day window ---
            if config.per_day_limit > 0 and day_count >= config.per_day_limit:
                oldest = state.day_window[0] if state.day_window else now
                retry_after = max(0.0, _DAY_WINDOW - (now - oldest))
                state.blocked_count += 1
                result = RateLimitResult(
                    allowed=False,
                    client_id=hashed_id,
                    tier=resolved_tier,
                    reason=f"Per-day limit ({config.per_day_limit}) exceeded",
                    remaining_minute=max(0, effective_minute_limit - minute_count),
                    remaining_day=0,
                    remaining_lifetime=self._remaining_lifetime(state, config),
                    retry_after_seconds=round(retry_after, 2),
                    headers=self._build_headers(
                        config,
                        max(0, effective_minute_limit - minute_count),
                        0,
                        self._remaining_lifetime(state, config),
                        retry_after,
                    ),
                )
                logger.debug(
                    "Rate limit BLOCKED (day): client=%s tier=%s count=%d limit=%d retry=%.1fs",
                    hashed_id[:12],
                    resolved_tier.value,
                    day_count,
                    config.per_day_limit,
                    retry_after,
                )
                return result

            # --- All checks passed: record request ---
            state.minute_window.append(now)
            state.day_window.append(now)
            state.lifetime_count += 1
            state.active_requests += 1
            state.last_request = now

            remaining_min = max(0, effective_minute_limit - len(state.minute_window))
            remaining_day = (
                max(0, config.per_day_limit - len(state.day_window))
                if config.per_day_limit > 0
                else 0
            )
            remaining_life = self._remaining_lifetime(state, config)

            # Compute reset time (when the oldest entry in minute window expires)
            reset_seconds = 0.0
            if state.minute_window:
                reset_seconds = max(0.0, _MINUTE_WINDOW - (now - state.minute_window[0]))

            result = RateLimitResult(
                allowed=True,
                client_id=hashed_id,
                tier=resolved_tier,
                remaining_minute=remaining_min,
                remaining_day=remaining_day,
                remaining_lifetime=remaining_life,
                headers=self._build_headers(
                    config,
                    remaining_min,
                    remaining_day,
                    remaining_life,
                    None,
                    reset_seconds,
                ),
            )
            return result

    def release(self, client_id: str) -> None:
        """Release a concurrent request slot.

        Must be called when a request completes (success or failure)
        to free the concurrent slot.

        Args:
            client_id: The same identifier passed to check().
        """
        hashed_id = self._hash_client_id(client_id)
        lock = self._get_lock(hashed_id)
        with lock:
            state = self._states.get(hashed_id)
            if state and state.active_requests > 0:
                state.active_requests -= 1

    def get_client_state(self, client_id: str) -> RateLimitState | None:
        """Get current state for a client.

        Args:
            client_id: Client identifier.

        Returns:
            Copy of the client's RateLimitState, or None if not tracked.
        """
        hashed_id = self._hash_client_id(client_id)
        lock = self._get_lock(hashed_id)
        with lock:
            state = self._states.get(hashed_id)
            if state is None:
                return None
            # Return a snapshot (shallow copy with new deques)
            return RateLimitState(
                client_id=state.client_id,
                tier=state.tier,
                lifetime_count=state.lifetime_count,
                minute_window=deque(state.minute_window),
                day_window=deque(state.day_window),
                active_requests=state.active_requests,
                last_request=state.last_request,
                blocked_count=state.blocked_count,
            )

    def get_stats(self) -> dict[str, Any]:
        """Get overall rate limiter statistics.

        Returns:
            Dictionary with tracked_clients, total_requests, total_blocked,
            tier_distribution, and uptime_seconds.
        """
        with self._global_lock:
            client_ids = list(self._states.keys())

        total_requests = 0
        total_blocked = 0
        tier_counts: dict[str, int] = {}

        for cid in client_ids:
            lock = self._get_lock(cid)
            with lock:
                state = self._states.get(cid)
                if state is None:
                    continue
                total_requests += state.lifetime_count
                total_blocked += state.blocked_count
                tier_name = state.tier.value
                tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

        return {
            "tracked_clients": len(client_ids),
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "tier_distribution": tier_counts,
            "uptime_seconds": round(time.monotonic() - self._created_at, 2),
        }

    def reset_client(self, client_id: str) -> None:
        """Reset all limits for a client.

        Removes all tracking state. The client will start fresh on the
        next request.

        Args:
            client_id: Client identifier.
        """
        hashed_id = self._hash_client_id(client_id)
        with self._global_lock:
            self._states.pop(hashed_id, None)
            self._locks.pop(hashed_id, None)
            self._client_tiers.pop(hashed_id, None)
        logger.info("Client state reset: %s", hashed_id[:12])

    def set_client_tier(self, client_id: str, tier: RateTier) -> None:
        """Set the tier for a specific client.

        Takes effect on the next check() call. Does not reset existing
        counters.

        Args:
            client_id: Client identifier.
            tier: The tier to assign.
        """
        hashed_id = self._hash_client_id(client_id)
        with self._global_lock:
            self._client_tiers[hashed_id] = tier
        # Update state tier if it already exists
        lock = self._get_lock(hashed_id)
        with lock:
            state = self._states.get(hashed_id)
            if state:
                state.tier = tier
        logger.info("Client tier set: %s -> %s", hashed_id[:12], tier.value)

    def cleanup(self) -> None:
        """Remove expired entries from all windows and evict inactive clients.

        Clients with no activity for 24 hours are removed entirely.
        Should be called periodically (e.g., every few minutes).
        """
        now = time.monotonic()
        evicted = 0

        with self._global_lock:
            client_ids = list(self._states.keys())

        for cid in client_ids:
            lock = self._get_lock(cid)
            with lock:
                state = self._states.get(cid)
                if state is None:
                    continue

                # Evict inactive clients
                if state.last_request > 0 and (now - state.last_request) > _INACTIVITY_EXPIRY:
                    with self._global_lock:
                        self._states.pop(cid, None)
                        self._locks.pop(cid, None)
                    evicted += 1
                    continue

                # Purge expired timestamps
                self._purge_window(state.minute_window, now, _MINUTE_WINDOW)
                self._purge_window(state.day_window, now, _DAY_WINDOW)

        if evicted > 0:
            logger.info("Cleanup: evicted %d inactive clients", evicted)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_state(self, hashed_id: str, tier: RateTier) -> RateLimitState:
        """Get or create a client state entry.

        Args:
            hashed_id: Hashed client identifier.
            tier: Tier to assign if creating new state.

        Returns:
            The client's RateLimitState.
        """
        with self._global_lock:
            if hashed_id not in self._states:
                self._states[hashed_id] = RateLimitState(
                    client_id=hashed_id,
                    tier=tier,
                )
                logger.debug("New client tracked: %s tier=%s", hashed_id[:12], tier.value)
            return self._states[hashed_id]

    def _get_lock(self, hashed_id: str) -> threading.Lock:
        """Get or create a per-client lock.

        Args:
            hashed_id: Hashed client identifier.

        Returns:
            The client's dedicated Lock.
        """
        with self._global_lock:
            if hashed_id not in self._locks:
                self._locks[hashed_id] = threading.Lock()
            return self._locks[hashed_id]

    @staticmethod
    def _purge_window(window: deque[float], now: float, duration: float) -> None:
        """Remove timestamps older than the window duration.

        Args:
            window: Deque of monotonic timestamps.
            now: Current monotonic time.
            duration: Window duration in seconds.
        """
        cutoff = now - duration
        while window and window[0] < cutoff:
            window.popleft()

    @staticmethod
    def _remaining_lifetime(state: RateLimitState, config: TierConfig) -> int:
        """Compute remaining lifetime requests.

        Args:
            state: Client state.
            config: Tier configuration.

        Returns:
            Remaining lifetime count (0 if unlimited).
        """
        if config.lifetime_limit <= 0:
            return 0
        return max(0, config.lifetime_limit - state.lifetime_count)

    @staticmethod
    def _hash_client_id(client_id: str) -> str:
        """Hash a client identifier for storage using constant-time comparison.

        Uses HMAC-SHA256 to prevent timing attacks on client ID lookups.
        The hash is deterministic for the same input.

        Args:
            client_id: Raw client identifier (API key, IP, etc.).

        Returns:
            Hex-encoded HMAC hash of the client ID.
        """
        return hmac.new(
            _CLIENT_ID_HASH_KEY,
            client_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _build_headers(
        config: TierConfig,
        remaining_minute: int,
        remaining_day: int,
        remaining_lifetime: int,
        retry_after: float | None,
        reset_seconds: float = 0.0,
    ) -> dict[str, str]:
        """Build X-RateLimit-* HTTP response headers.

        Args:
            config: Tier configuration for limit values.
            remaining_minute: Remaining requests in minute window.
            remaining_day: Remaining requests in day window.
            remaining_lifetime: Remaining lifetime requests.
            retry_after: Seconds until retry is possible (None if allowed).
            reset_seconds: Seconds until the minute window resets.

        Returns:
            Dictionary of HTTP header name-value pairs.
        """
        headers: dict[str, str] = {}

        if config.per_minute_limit > 0:
            effective = config.per_minute_limit + config.burst_allowance
            headers["X-RateLimit-Limit-Minute"] = str(effective)
            headers["X-RateLimit-Remaining-Minute"] = str(remaining_minute)

        if config.per_day_limit > 0:
            headers["X-RateLimit-Limit-Day"] = str(config.per_day_limit)
            headers["X-RateLimit-Remaining-Day"] = str(remaining_day)

        if config.lifetime_limit > 0:
            headers["X-RateLimit-Limit-Lifetime"] = str(config.lifetime_limit)
            headers["X-RateLimit-Remaining-Lifetime"] = str(remaining_lifetime)

        if reset_seconds > 0:
            headers["X-RateLimit-Reset"] = str(int(reset_seconds))

        if retry_after is not None and retry_after > 0:
            headers["Retry-After"] = str(int(retry_after) + 1)

        return headers


# ---------------------------------------------------------------------------
# aiohttp middleware factory
# ---------------------------------------------------------------------------


def create_rate_limit_middleware(
    limiter: SlidingWindowRateLimiter | None = None,
    default_tier: RateTier = RateTier.STANDARD,
    header_name: str = "X-API-Key",
) -> Any:
    """Create an aiohttp middleware function for rate limiting.

    The middleware extracts the client identifier from the specified header
    (defaults to X-API-Key). If no header is present, falls back to the
    client's IP address from the request.

    Args:
        limiter: Existing SlidingWindowRateLimiter instance. If None, a new
                 one is created with the given default_tier.
        default_tier: Default tier for the limiter (used only if creating new).
        header_name: HTTP header to extract the client API key from.

    Returns:
        An aiohttp middleware coroutine function.

    Example:
        .. code-block:: python

            from aiohttp import web
            from .agent.core.rate_limiter import (
                SlidingWindowRateLimiter,
                create_rate_limit_middleware,
                RateTier,
            )

            limiter = SlidingWindowRateLimiter(default_tier=RateTier.STANDARD)
            app = web.Application(middlewares=[
                create_rate_limit_middleware(limiter=limiter),
            ])
    """
    # Lazy import to avoid hard dependency on aiohttp at module level
    try:
        from aiohttp import web
    except ImportError as exc:
        raise ImportError(
            "aiohttp is required for the rate limit middleware. "
            "Install it with: pip install aiohttp"
        ) from exc

    if limiter is None:
        limiter = SlidingWindowRateLimiter(default_tier=default_tier)

    # Capture limiter in closure — must be non-None at this point
    _limiter = limiter

    @web.middleware
    async def rate_limit_middleware(request: web.Request, handler: Any) -> web.Response:
        """Rate limiting middleware for aiohttp.

        Extracts client ID from API key header or remote IP, checks
        rate limits, and injects X-RateLimit headers into the response.

        Args:
            request: The incoming aiohttp request.
            handler: The next handler in the middleware chain.

        Returns:
            The handler's response with rate limit headers, or a 429
            response if the request is blocked.
        """
        # Extract client identifier
        api_key = request.headers.get(header_name)
        if api_key:
            client_id = api_key
        else:
            # Fallback to IP address
            peername = request.transport.get_extra_info("peername") if request.transport else None
            client_id = peername[0] if peername else "unknown"

        result = _limiter.check(client_id)

        if not result.allowed:
            logger.warning(
                "Rate limit blocked: client=%s tier=%s reason=%s",
                result.client_id[:12],
                result.tier.value,
                result.reason,
            )
            response = web.json_response(
                {
                    "error": "Rate limit excedido",
                    "reason": result.reason,
                    "retry_after": result.retry_after_seconds,
                },
                status=429,
            )
            for name, value in result.headers.items():
                response.headers[name] = value
            return response

        try:
            response = await handler(request)
        except Exception:
            _limiter.release(client_id)
            raise

        # Inject rate limit headers into successful response
        for name, value in result.headers.items():
            response.headers[name] = value

        _limiter.release(client_id)
        return response

    return rate_limit_middleware
