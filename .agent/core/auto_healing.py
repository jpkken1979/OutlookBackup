"""
Auto-Healing Module for Antigravity Agents.

Provides automatic failure detection, recovery, and resilience for agents.

Features:
- Circuit breaker pattern
- Automatic retry with exponential backoff
- Fallback agent selection
- Health monitoring and metrics
- Recovery strategies (restart, delegate, skip)

Usage:
    from core.auto_healing import AutoHealer, get_healer

    healer = get_healer()

    # Execute with auto-healing
    result = await healer.execute_with_healing(
        agent_name="explorer",
        task="analyze code",
        fallback_agents=["architect", "coder"]
    )

    # Get health report
    report = healer.get_health_report()
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("auto_healing")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class RecoveryStrategy(Enum):
    """Recovery strategies for failed agents."""

    RETRY = "retry"  # Retry the same agent
    FALLBACK = "fallback"  # Use fallback agent
    DELEGATE = "delegate"  # Delegate to orchestrator
    SKIP = "skip"  # Skip and return error
    RESTART = "restart"  # Restart agent (future)


class FailureType(Enum):
    """Types of agent failures."""

    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    INVALID_RESPONSE = "invalid_response"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    DEPENDENCY_FAILED = "dependency_failed"


# Default configuration
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RECOVERY_TIMEOUT = 30  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_BACKOFF_MULTIPLIER = 2.0


# ============================================================================
# DATA MODELS
# ============================================================================


class AgentHealth(BaseModel):
    """Health metrics for a single agent."""

    agent_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    circuit_state: str = CircuitState.CLOSED.value
    average_response_time_ms: float = 0.0
    recovery_attempts: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def is_healthy(self) -> bool:
        """Check if agent is considered healthy."""
        return (
            self.circuit_state == CircuitState.CLOSED.value
            and self.consecutive_failures < DEFAULT_FAILURE_THRESHOLD
        )


@dataclass
class FailureRecord:
    """Record of a single failure."""

    agent_name: str
    failure_type: FailureType
    error_message: str
    timestamp: datetime
    task: str
    recovery_strategy: RecoveryStrategy | None = None
    recovered: bool = False


@dataclass
class HealingResult:
    """Result of an auto-healed execution."""

    success: bool
    agent_used: str
    result: Any
    attempts: int
    recovery_strategy: RecoveryStrategy | None = None
    total_time_ms: float = 0.0
    failures: list[FailureRecord] = field(default_factory=list)


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================


class CircuitBreaker:
    """
    Circuit breaker for individual agents.

    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Too many failures, calls are blocked
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        agent_name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
    ):
        self.agent_name = agent_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.success_count_in_half_open = 0

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count_in_half_open = 0
                    logger.info(f"Circuit for {self.agent_name} entering HALF_OPEN state")
                    return True
            return False

        # HALF_OPEN - allow limited calls
        return True

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_in_half_open += 1
            if self.success_count_in_half_open >= 3:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit for {self.agent_name} CLOSED (recovered)")
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit for {self.agent_name} OPEN (failed in half-open)")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit for {self.agent_name} OPEN (threshold reached)")

    def reset(self) -> None:
        """Reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count_in_half_open = 0


# ============================================================================
# AUTO HEALER
# ============================================================================


class AutoHealer:
    """
    Automatic healing and recovery system for agents.

    Provides:
    - Circuit breaker per agent
    - Retry with exponential backoff
    - Fallback agent selection
    - Health monitoring
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_multiplier = backoff_multiplier

        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.health_metrics: dict[str, AgentHealth] = {}
        self.failure_history: list[FailureRecord] = []

    def get_circuit_breaker(self, agent_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for agent."""
        if agent_name not in self.circuit_breakers:
            self.circuit_breakers[agent_name] = CircuitBreaker(agent_name)
        return self.circuit_breakers[agent_name]

    def get_health(self, agent_name: str) -> AgentHealth:
        """Get or create health metrics for agent."""
        if agent_name not in self.health_metrics:
            self.health_metrics[agent_name] = AgentHealth(agent_name=agent_name)
        return self.health_metrics[agent_name]

    def _record_success(self, agent_name: str, response_time_ms: float) -> None:
        """Record successful execution."""
        cb = self.get_circuit_breaker(agent_name)
        cb.record_success()

        health = self.get_health(agent_name)
        health.total_calls += 1
        health.successful_calls += 1
        health.consecutive_failures = 0
        health.last_success_time = datetime.now()
        health.circuit_state = cb.state.value

        # Update average response time
        if health.average_response_time_ms == 0:
            health.average_response_time_ms = response_time_ms
        else:
            health.average_response_time_ms = (
                health.average_response_time_ms * 0.9 + response_time_ms * 0.1
            )

    def _record_failure(
        self, agent_name: str, failure_type: FailureType, error_message: str, task: str
    ) -> FailureRecord:
        """Record failed execution."""
        cb = self.get_circuit_breaker(agent_name)
        cb.record_failure()

        health = self.get_health(agent_name)
        health.total_calls += 1
        health.failed_calls += 1
        health.consecutive_failures += 1
        health.last_failure_time = datetime.now()
        health.circuit_state = cb.state.value

        record = FailureRecord(
            agent_name=agent_name,
            failure_type=failure_type,
            error_message=error_message,
            timestamp=datetime.now(),
            task=task,
        )
        self.failure_history.append(record)

        # Keep only last 1000 failures
        if len(self.failure_history) > 1000:
            self.failure_history = self.failure_history[-1000:]

        return record

    async def execute_with_healing(
        self,
        agent_name: str,
        execute_fn: Callable,
        task: str,
        fallback_agents: list[str] | None = None,
        timeout: float = 60.0,
    ) -> HealingResult:
        """
        Execute agent with auto-healing capabilities.

        Args:
            agent_name: Primary agent to execute
            execute_fn: Async function to execute (receives agent_name, task)
            task: Task description
            fallback_agents: List of fallback agents if primary fails
            timeout: Execution timeout in seconds

        Returns:
            HealingResult with execution details
        """
        start_time = time.time()
        failures: list[FailureRecord] = []
        agents_to_try = [agent_name] + (fallback_agents or [])

        for current_agent in agents_to_try:
            cb = self.get_circuit_breaker(current_agent)

            # Check circuit breaker
            if not cb.can_execute():
                logger.warning(f"Circuit OPEN for {current_agent}, skipping")
                failures.append(
                    FailureRecord(
                        agent_name=current_agent,
                        failure_type=FailureType.DEPENDENCY_FAILED,
                        error_message="Circuit breaker open",
                        timestamp=datetime.now(),
                        task=task,
                    )
                )
                continue

            # Try with retries
            for attempt in range(self.max_retries):
                try:
                    # Execute with timeout
                    result = await asyncio.wait_for(
                        execute_fn(current_agent, task), timeout=timeout
                    )

                    # Success!
                    elapsed = (time.time() - start_time) * 1000
                    self._record_success(current_agent, elapsed)

                    strategy = None
                    if current_agent != agent_name:
                        strategy = RecoveryStrategy.FALLBACK

                    return HealingResult(
                        success=True,
                        agent_used=current_agent,
                        result=result,
                        attempts=attempt + 1,
                        recovery_strategy=strategy,
                        total_time_ms=elapsed,
                        failures=failures,
                    )

                except TimeoutError:
                    record = self._record_failure(
                        current_agent, FailureType.TIMEOUT, f"Timeout after {timeout}s", task
                    )
                    failures.append(record)
                    logger.warning(f"Timeout for {current_agent} (attempt {attempt + 1})")

                except Exception as e:
                    record = self._record_failure(
                        current_agent, FailureType.EXCEPTION, str(e), task
                    )
                    failures.append(record)
                    logger.warning(f"Exception in {current_agent}: {e} (attempt {attempt + 1})")

                # Wait before retry with exponential backoff
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (self.backoff_multiplier**attempt)
                    await asyncio.sleep(delay)

        # All attempts failed
        elapsed = (time.time() - start_time) * 1000
        return HealingResult(
            success=False,
            agent_used=agent_name,
            result=None,
            attempts=len(failures),
            recovery_strategy=RecoveryStrategy.SKIP,
            total_time_ms=elapsed,
            failures=failures,
        )

    def get_health_report(self) -> dict[str, Any]:
        """Get comprehensive health report."""
        healthy_agents = []
        unhealthy_agents = []

        for name, health in self.health_metrics.items():
            if health.is_healthy:
                healthy_agents.append(name)
            else:
                unhealthy_agents.append(
                    {
                        "name": name,
                        "circuit_state": health.circuit_state,
                        "consecutive_failures": health.consecutive_failures,
                        "success_rate": f"{health.success_rate * 100:.1f}%",
                    }
                )

        recent_failures = [
            {
                "agent": f.agent_name,
                "type": f.failure_type.value,
                "message": f.error_message[:100],
                "time": f.timestamp.isoformat(),
            }
            for f in self.failure_history[-10:]
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "total_agents_tracked": len(self.health_metrics),
            "healthy_agents": len(healthy_agents),
            "unhealthy_agents": len(unhealthy_agents),
            "unhealthy_details": unhealthy_agents,
            "recent_failures": recent_failures,
            "circuit_breakers": {
                name: cb.state.value for name, cb in self.circuit_breakers.items()
            },
        }

    def reset_agent(self, agent_name: str) -> None:
        """Reset health and circuit breaker for an agent."""
        if agent_name in self.circuit_breakers:
            self.circuit_breakers[agent_name].reset()

        if agent_name in self.health_metrics:
            self.health_metrics[agent_name] = AgentHealth(agent_name=agent_name)

        logger.info(f"Reset health for agent: {agent_name}")

    def reset_all(self) -> None:
        """Reset all health metrics and circuit breakers."""
        self.circuit_breakers.clear()
        self.health_metrics.clear()
        self.failure_history.clear()
        logger.info("Reset all health metrics")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_healer_instance: AutoHealer | None = None


def get_healer() -> AutoHealer:
    """Get singleton AutoHealer instance."""
    global _healer_instance
    if _healer_instance is None:
        _healer_instance = AutoHealer()
    return _healer_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


async def execute_with_retry(
    agent_name: str, execute_fn: Callable, task: str, fallback_agents: list[str] | None = None
) -> Any:
    """
    Convenience function to execute with auto-healing.

    Raises exception if all attempts fail.
    """
    healer = get_healer()
    result = await healer.execute_with_healing(
        agent_name=agent_name, execute_fn=execute_fn, task=task, fallback_agents=fallback_agents
    )

    if not result.success:
        raise RuntimeError(
            f"All attempts failed for {agent_name}. "
            f"Failures: {[f.error_message for f in result.failures]}"
        )

    return result.result


def get_agent_health(agent_name: str) -> AgentHealth:
    """Get health metrics for a specific agent."""
    return get_healer().get_health(agent_name)


def is_agent_healthy(agent_name: str) -> bool:
    """Check if agent is healthy."""
    return get_healer().get_health(agent_name).is_healthy


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import json

    healer = get_healer()
    report = healer.get_health_report()
    print(json.dumps(report, indent=2, default=str))
