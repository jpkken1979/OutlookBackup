"""Redacted OpenTelemetry spans for decisions made by RoutingAuthority."""

from __future__ import annotations

from typing import Any

try:
    from opentelemetry.trace import get_tracer

    _tracer: Any = get_tracer("openantigravity.routing")
except ImportError:  # pragma: no cover - OpenTelemetry is optional
    _tracer = None


def record_routing_decision(
    decision: Any,
    *,
    eligible_count: int,
    dry_run: bool,
) -> None:
    """Record routing metadata only; prompts, credentials and paths are forbidden."""

    if _tracer is None:
        return
    with _tracer.start_as_current_span("nexus.routing.select") as span:
        attributes = {
            "routing.trace_id": str(decision.trace_id),
            "routing.route": str(decision.route),
            "routing.provider": str(decision.provider),
            "routing.model": str(decision.model),
            "routing.reason": str(decision.reason),
            "routing.score": float(decision.score),
            "routing.manual": bool(decision.manual),
            "routing.eligible_count": int(eligible_count),
            "routing.dry_run": dry_run,
        }
        for key, value in attributes.items():
            span.set_attribute(key, value)
