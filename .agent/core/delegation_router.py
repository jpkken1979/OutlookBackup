"""Quota-aware routing for MCP-delegated agent executions.

Claude Remote Control must remain on the native claude.ai connection. Provider
selection therefore applies only to work explicitly delegated to Nexus. This
module is the single decision point for that plane: it reads the saved route,
filters candidates by credentials/health/quota, respects the ordered cascade,
and exposes a secret-free LLM configuration to ``GatewayExecutor``.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass

from core import provider_cascade, provider_switch, proxy_state, quota_state
from core.routing_authority import get_routing_authority

logger = logging.getLogger(__name__)

_DEFAULT_QUOTA_COOLDOWN_S = 300.0
_QUOTA_COOLDOWN_ENV = "ANTIGRAVITY_PROXY_QUOTA_COOLDOWN_S"


@dataclass(frozen=True, slots=True)
class DelegationRoute:
    """Resolved provider/model for one delegated execution."""

    provider_id: str
    model: str
    reason: str
    rotated_from: str | None = None

    def llm_config(self) -> dict[str, str] | None:
        """Return a secret-free config understood by ``GatewayExecutor``.

        Native Claude OAuth is intentionally not converted into an SDK token.
        When Claude is selected, the host Claude session remains the intelligence
        plane and local agents degrade to their existing IDE/script behavior.
        """
        config = provider_switch.PROVIDERS.get(self.provider_id)
        if config is None or self.provider_id == "claude":
            return None
        if config.wire == "anthropic":
            runtime_provider = "anthropic"
        elif self.provider_id == "ollama":
            runtime_provider = "ollama"
        else:
            runtime_provider = "openai"
        return {
            "provider_id": self.provider_id,
            "provider": runtime_provider,
            "model": self.model,
            "base_url": config.base_url,
            "reason": self.reason,
        }


def select_ordered_quota_target(
    active_provider: str,
    *,
    cascade: tuple[str, ...],
    open_circuits: set[str],
    configured: set[str] | None,
    remaining_by_provider: dict[str, float | None],
    threshold_pct: float,
) -> str | None:
    """Select the first healthy ordered target when the active quota is low.

    Unknown quota is fail-open: it does not disqualify a configured candidate.
    This mirrors OmniRoute's candidate-pool choke point without importing its
    adaptive scoring or changing Claude's native connection.
    """
    active = active_provider.strip().lower()
    active_remaining = remaining_by_provider.get(active)
    if active_remaining is None or active_remaining > threshold_pct:
        return None
    available: set[str] = set()
    for provider in cascade:
        if provider == active:
            continue
        if configured is not None and provider not in configured:
            continue
        if provider in open_circuits:
            continue
        remaining = remaining_by_provider.get(provider)
        if remaining is not None and remaining <= threshold_pct:
            continue
        available.add(provider)
    return provider_cascade.select_failover_target(
        active,
        cascade,
        open_circuits,
        available,
    )


def _quota_cooldown_seconds() -> float:
    raw = os.environ.get(_QUOTA_COOLDOWN_ENV, str(_DEFAULT_QUOTA_COOLDOWN_S))
    try:
        return max(0.0, min(float(raw), 86_400.0))
    except ValueError:
        return _DEFAULT_QUOTA_COOLDOWN_S


def _in_quota_cooldown(provider: str, remaining: float | None, now: float) -> bool:
    if remaining is not None and remaining <= 1.0:
        return False
    last_rotation = quota_state.get_last_rotation(provider)
    return last_rotation is not None and now - last_rotation < _quota_cooldown_seconds()


def _parse_route(route: str | None) -> tuple[str, str] | None:
    if not route:
        return None
    provider, separator, model = route.partition("/")
    provider = provider.strip().lower()
    model = model.strip()
    if not separator or provider not in provider_switch.PROVIDERS or not model:
        return None
    return provider, model


def _saved_route() -> tuple[str, str]:
    authority = get_routing_authority()
    parsed = _parse_route(authority.store.manual_override())
    if parsed is not None:
        return parsed
    active = proxy_state.get_active()
    provider = str(active.get("provider") or "claude").strip().lower()
    if provider not in provider_switch.PROVIDERS:
        provider = "claude"
    model = str(active.get("model") or "").strip()
    if not model:
        model = provider_switch.resolve_provider_model(provider)
    return provider, model


def _runtime_quota_target(active_provider: str, now: float) -> str | None:
    if not provider_cascade.is_auto_failover_enabled():
        return None
    active_remaining = quota_state.get_remaining_percent(active_provider)
    if _in_quota_cooldown(active_provider, active_remaining, now):
        return None
    cascade = provider_cascade.get_cascade()
    remaining = {provider: quota_state.get_remaining_percent(provider) for provider in cascade}
    open_circuits = {
        provider
        for provider in provider_switch.PROXY_ROUTABLE
        if proxy_state.circuit_open(provider)
    }
    return select_ordered_quota_target(
        active_provider,
        cascade=cascade,
        open_circuits=open_circuits,
        configured=provider_cascade.configured_providers(),
        remaining_by_provider=remaining,
        threshold_pct=quota_state.get_threshold_pct(),
    )


def _persist_rotation(previous: str, target: str, model: str, now: float) -> None:
    provider_switch.set_hotswap(target, model)
    authority = get_routing_authority()
    authority.store.set_manual_override(target, model)
    quota_state.set_last_rotation(previous, now)
    trace_id = f"delegation-quota-{uuid.uuid4().hex}"
    authority.store.record_decision(
        trace_id=trace_id,
        route=f"{target}/{model}",
        provider=target,
        model=model,
        score=1.0,
        manual=False,
        detail={
            "reason": "delegation_quota_failover",
            "from": previous,
            "threshold_pct": quota_state.get_threshold_pct(),
        },
    )
    proxy_state.record_recovery_event(
        "auto_failover_quota_reroute",
        previous,
        f"delegation->{target}",
    )


def resolve_delegation_route(*, now: float | None = None) -> DelegationRoute:
    """Resolve and, when necessary, persist the route for a delegated task."""
    provider, model = _saved_route()
    timestamp = time.time() if now is None else now
    try:
        target = _runtime_quota_target(provider, timestamp)
        if target is not None:
            target_model = provider_switch.resolve_provider_model(target)
            _persist_rotation(provider, target, target_model, timestamp)
            logger.info(
                "delegation quota failover: %s -> %s/%s",
                provider,
                target,
                target_model,
            )
            return DelegationRoute(
                target,
                target_model,
                "delegation_quota_failover",
                rotated_from=provider,
            )
    except Exception as exc:  # noqa: BLE001 - optional routing must fail open
        logger.warning("delegation quota evaluation failed open: %s", exc)
    return DelegationRoute(provider, model, "delegation_saved_route")


def resolved_llm_config(explicit: dict | None = None) -> tuple[dict | None, DelegationRoute]:
    """Merge a saved delegation route with an optional per-request override."""
    route = resolve_delegation_route()
    base = route.llm_config()
    if base is None:
        return (dict(explicit) if explicit else None), route
    merged = dict(base)
    if explicit:
        merged.update(explicit)
    return merged, route
