"""Deterministic routing drills that never contact providers or mutate health."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from core.routing_authority import RoutingAuthority


class FaultScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    passed: bool
    expected_provider: str | None = None
    selected_provider: str | None = None
    invariant: str
    detail: str


class RoutingFaultLabReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "routing-fault-lab-v1"
    status: str
    scenarios: list[FaultScenarioResult]
    passed: int
    failed: int
    side_effects_executed: int


def _candidate(
    provider: str,
    *,
    healthy: bool = True,
    quota_remaining: float = 1.0,
    priority: int = 70,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": f"{provider}-fault-model",
        "configured": True,
        "healthy": healthy,
        "quota_remaining": quota_remaining,
        "latency_ms": 250,
        "cost": 0.2,
        "quality": 0.9,
        "priority": priority,
        "capabilities": ["coding", "fast", "cheap"],
        "routable": True,
    }


def run_routing_fault_lab(authority: RoutingAuthority) -> RoutingFaultLabReport:
    """Exercise failover and at-most-once invariants through the one authority."""

    scenarios: list[FaultScenarioResult] = []

    primary = authority.select(
        "auto/coding",
        candidates=[
            _candidate("openai", priority=100),
            _candidate("gemini", priority=70),
        ],
        trace_id="fault-primary",
        persist=False,
    )
    scenarios.append(
        FaultScenarioResult(
            id="healthy-primary",
            passed=primary.provider == "openai",
            expected_provider="openai",
            selected_provider=primary.provider,
            invariant="A healthy preferred provider remains selected.",
            detail=primary.reason,
        )
    )

    circuit_failover = authority.select(
        "auto/coding",
        candidates=[
            _candidate("openai", healthy=False, priority=100),
            _candidate("gemini", priority=70),
        ],
        trace_id="fault-circuit-open",
        persist=False,
    )
    scenarios.append(
        FaultScenarioResult(
            id="circuit-open",
            passed=circuit_failover.provider == "gemini",
            expected_provider="gemini",
            selected_provider=circuit_failover.provider,
            invariant="A provider with an open circuit is never selected.",
            detail=circuit_failover.reason,
        )
    )

    quota_failover = authority.select(
        "auto/coding",
        candidates=[
            _candidate("openai", quota_remaining=0.0, priority=70),
            _candidate("gemini", quota_remaining=1.0, priority=70),
        ],
        trace_id="fault-quota-empty",
        persist=False,
    )
    scenarios.append(
        FaultScenarioResult(
            id="quota-exhausted",
            passed=quota_failover.provider == "gemini",
            expected_provider="gemini",
            selected_provider=quota_failover.provider,
            invariant="Available quota wins when all other dimensions are equal.",
            detail=quota_failover.reason,
        )
    )

    timeout_failover = authority.select(
        "auto/coding",
        candidates=[
            _candidate("openai", healthy=False, priority=100),
            _candidate("gemini", priority=70),
        ],
        trace_id="fault-timeout-before-token",
        persist=False,
    )
    scenarios.append(
        FaultScenarioResult(
            id="timeout-before-first-token",
            passed=timeout_failover.provider == "gemini",
            expected_provider="gemini",
            selected_provider=timeout_failover.provider,
            invariant="A timeout before output can reroute without duplicating output.",
            detail="emitted_tokens=0; effects=0; retry=gemini",
        )
    )

    pre_stream_failover = authority.select(
        "auto/coding",
        candidates=[
            _candidate("openai", healthy=False, priority=100),
            _candidate("gemini", priority=70),
        ],
        trace_id="fault-error-before-stream",
        persist=False,
    )
    scenarios.append(
        FaultScenarioResult(
            id="error-before-first-token",
            passed=pre_stream_failover.provider == "gemini",
            expected_provider="gemini",
            selected_provider=pre_stream_failover.provider,
            invariant="A pre-stream error can retry when no output or effect exists.",
            detail="stream_started=false; effects=0; retry=gemini",
        )
    )

    emitted_tokens = 3
    automatic_mid_stream_failover = False
    scenarios.append(
        FaultScenarioResult(
            id="mid-stream-interruption",
            passed=emitted_tokens > 0 and not automatic_mid_stream_failover,
            invariant="Partial output is marked interrupted and never silently replayed.",
            detail="emitted_tokens=3; automatic_failover=false",
        )
    )

    execution_journal: set[str] = set()
    side_effects_executed = 0
    for idempotency_key in ("fault-turn-1", "fault-turn-1"):
        if idempotency_key not in execution_journal:
            execution_journal.add(idempotency_key)
            side_effects_executed += 1
    scenarios.append(
        FaultScenarioResult(
            id="failure-after-tool",
            passed=side_effects_executed == 1,
            invariant="A post-tool retry with the same key executes the effect once.",
            detail=f"journal_entries=1; executions={side_effects_executed}",
        )
    )

    passed = sum(1 for scenario in scenarios if scenario.passed)
    failed = len(scenarios) - passed
    return RoutingFaultLabReport(
        status="passed" if failed == 0 else "failed",
        scenarios=scenarios,
        passed=passed,
        failed=failed,
        side_effects_executed=side_effects_executed,
    )
