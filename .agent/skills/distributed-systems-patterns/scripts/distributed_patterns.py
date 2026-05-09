#!/usr/bin/env python3
"""
Distributed Systems Patterns - Implementaciones Ejecutables
Patrones para sistemas distribuidos con ejemplos prácticos.
"""

import logging
import time
import random
from dataclasses import dataclass, field
from typing import TypeVar
from collections.abc import Callable
from enum import Enum
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# CIRCUIT BREAKER PATTERN
# =============================================================================


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation.
    Protege contra fallos en cascada en sistemas distribuidos.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _success_count: int = field(default=0, init=False)

    def call(self, func: Callable[[], T], *args, **kwargs) -> T:
        """Ejecuta una función con protección de circuit breaker."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: HALF_OPEN (testing)")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= 3:
                self._reset()
                logger.info("Circuit breaker: CLOSED (recovered)")
        else:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: OPEN (failures={self._failure_count})")

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    @property
    def state(self) -> CircuitState:
        return self._state


class CircuitBreakerOpenError(Exception):
    pass


# =============================================================================
# RETRY PATTERN WITH EXPONENTIAL BACKOFF
# =============================================================================


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


def retry_with_backoff(func: Callable[[], T], config: RetryConfig | None = None) -> T:
    """
    Retry Pattern con Exponential Backoff.
    Reintenta operaciones fallidas con delays incrementales.
    """
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e

            if attempt == config.max_retries:
                logger.error(f"Retry exhausted after {attempt + 1} attempts")
                raise

            delay = min(config.base_delay * (config.exponential_base**attempt), config.max_delay)

            if config.jitter:
                delay *= 0.5 + random.random()

            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s")
            time.sleep(delay)

    raise last_exception  # type: ignore


# =============================================================================
# SAGA PATTERN (Simplified)
# =============================================================================


@dataclass
class SagaStep:
    """Un paso en una saga con su compensación."""

    name: str
    action: Callable[[], bool]
    compensation: Callable[[], bool]


class Saga:
    """
    Saga Pattern Implementation.
    Maneja transacciones distribuidas con compensaciones.
    """

    def __init__(self) -> None:
        self._steps: list[SagaStep] = []
        self._completed_steps: list[SagaStep] = []

    def add_step(self, step: SagaStep) -> "Saga":
        self._steps.append(step)
        return self

    def execute(self) -> bool:
        """Ejecuta la saga, compensando en caso de fallo."""
        logger.info("Saga: Starting execution")

        for step in self._steps:
            try:
                logger.info(f"Saga: Executing step '{step.name}'")
                if step.action():
                    self._completed_steps.append(step)
                else:
                    raise Exception(f"Step '{step.name}' returned False")
            except Exception as e:
                logger.error(f"Saga: Step '{step.name}' failed: {e}")
                self._compensate()
                return False

        logger.info("Saga: All steps completed successfully")
        return True

    def _compensate(self) -> None:
        """Ejecuta compensaciones en orden inverso."""
        logger.info("Saga: Starting compensation")

        for step in reversed(self._completed_steps):
            try:
                logger.info(f"Saga: Compensating step '{step.name}'")
                step.compensation()
            except Exception as e:
                logger.error(f"Saga: Compensation for '{step.name}' failed: {e}")

        self._completed_steps.clear()


# =============================================================================
# OUTBOX PATTERN (Simplified)
# =============================================================================


@dataclass
class OutboxMessage:
    """Mensaje en el outbox para entrega garantizada."""

    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict
    created_at: datetime = field(default_factory=datetime.now)
    published: bool = False


class Outbox:
    """
    Outbox Pattern Implementation.
    Garantiza consistencia eventual entre DB y mensajería.
    """

    def __init__(self) -> None:
        self._messages: list[OutboxMessage] = []
        self._lock = threading.Lock()

    def add(self, message: OutboxMessage) -> None:
        """Añade mensaje al outbox (en la misma transacción de BD)."""
        with self._lock:
            self._messages.append(message)
            logger.info(f"Outbox: Message '{message.id}' added")

    def get_unpublished(self) -> list[OutboxMessage]:
        """Obtiene mensajes pendientes de publicar."""
        with self._lock:
            return [m for m in self._messages if not m.published]

    def mark_published(self, message_id: str) -> None:
        """Marca mensaje como publicado."""
        with self._lock:
            for msg in self._messages:
                if msg.id == message_id:
                    msg.published = True
                    logger.info(f"Outbox: Message '{message_id}' marked as published")
                    return

    def poll_and_publish(self, publisher: Callable[[OutboxMessage], bool]) -> int:
        """Publica mensajes pendientes."""
        unpublished = self.get_unpublished()
        published_count = 0

        for msg in unpublished:
            try:
                if publisher(msg):
                    self.mark_published(msg.id)
                    published_count += 1
            except Exception as e:
                logger.error(f"Outbox: Failed to publish '{msg.id}': {e}")

        return published_count


# =============================================================================
# BULKHEAD PATTERN
# =============================================================================


class Bulkhead:
    """
    Bulkhead Pattern Implementation.
    Aísla recursos para prevenir fallos en cascada.
    """

    def __init__(self, name: str, max_concurrent: int = 10) -> None:
        self.name = name
        self._semaphore = threading.Semaphore(max_concurrent)
        self._active = 0
        self._rejected = 0
        self._lock = threading.Lock()

    def execute(self, func: Callable[[], T], timeout: float = 5.0) -> T:
        """Ejecuta función dentro del bulkhead."""
        acquired = self._semaphore.acquire(timeout=timeout)

        if not acquired:
            with self._lock:
                self._rejected += 1
            raise BulkheadRejectedException(f"Bulkhead '{self.name}' rejected request")

        try:
            with self._lock:
                self._active += 1
            return func()
        finally:
            with self._lock:
                self._active -= 1
            self._semaphore.release()

    @property
    def stats(self) -> dict:
        with self._lock:
            return {"name": self.name, "active": self._active, "rejected": self._rejected}


class BulkheadRejectedException(Exception):
    pass


# =============================================================================
# DEMO
# =============================================================================


def main() -> None:
    """Demostración de patrones de sistemas distribuidos."""
    print("\n" + "=" * 60)
    print("DISTRIBUTED SYSTEMS PATTERNS - Ejemplos Ejecutables")
    print("=" * 60)

    # Circuit Breaker
    print("\n--- CIRCUIT BREAKER ---")
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)

    call_count = 0

    def flaky_service() -> str:
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise Exception("Service unavailable")
        return "Success!"

    for i in range(6):
        try:
            result = cb.call(flaky_service)
            print(f"Call {i + 1}: {result} (state={cb.state.value})")
        except Exception as e:
            print(f"Call {i + 1}: {type(e).__name__} (state={cb.state.value})")

    # Retry with Backoff
    print("\n--- RETRY WITH EXPONENTIAL BACKOFF ---")
    retry_count = 0

    def eventually_succeeds() -> str:
        nonlocal retry_count
        retry_count += 1
        if retry_count < 3:
            raise Exception("Temporary failure")
        return "Operation succeeded!"

    config = RetryConfig(max_retries=3, base_delay=0.1, jitter=False)
    result = retry_with_backoff(eventually_succeeds, config)
    print(f"Result after {retry_count} attempts: {result}")

    # Saga Pattern
    print("\n--- SAGA PATTERN ---")

    def create_order() -> bool:
        print("  -> Creating order...")
        return True

    def cancel_order() -> bool:
        print("  -> Cancelling order...")
        return True

    def reserve_inventory() -> bool:
        print("  -> Reserving inventory...")
        return True

    def release_inventory() -> bool:
        print("  -> Releasing inventory...")
        return True

    def process_payment() -> bool:
        print("  -> Processing payment...")
        return False  # Simula fallo

    def refund_payment() -> bool:
        print("  -> Refunding payment...")
        return True

    saga = Saga()
    saga.add_step(SagaStep("create_order", create_order, cancel_order))
    saga.add_step(SagaStep("reserve_inventory", reserve_inventory, release_inventory))
    saga.add_step(SagaStep("process_payment", process_payment, refund_payment))

    success = saga.execute()
    print(f"Saga completed: {success}")

    # Outbox Pattern
    print("\n--- OUTBOX PATTERN ---")
    outbox = Outbox()

    outbox.add(
        OutboxMessage(
            id="msg-001",
            aggregate_type="Order",
            aggregate_id="order-123",
            event_type="OrderCreated",
            payload={"amount": 100.00},
        )
    )
    outbox.add(
        OutboxMessage(
            id="msg-002",
            aggregate_type="Order",
            aggregate_id="order-123",
            event_type="OrderPaid",
            payload={"payment_id": "pay-456"},
        )
    )

    def mock_publisher(msg: OutboxMessage) -> bool:
        print(f"  -> Publishing {msg.event_type}: {msg.payload}")
        return True

    published = outbox.poll_and_publish(mock_publisher)
    print(f"Published {published} messages")

    # Bulkhead Pattern
    print("\n--- BULKHEAD PATTERN ---")
    bulkhead = Bulkhead("api-calls", max_concurrent=2)

    def slow_operation() -> str:
        time.sleep(0.1)
        return "Done"

    results = []
    for i in range(3):
        try:
            result = bulkhead.execute(slow_operation, timeout=0.01)
            results.append(f"Request {i + 1}: {result}")
        except BulkheadRejectedException:
            results.append(f"Request {i + 1}: Rejected by bulkhead")

    for r in results:
        print(f"  {r}")
    print(f"  Bulkhead stats: {bulkhead.stats}")

    print("\n" + "=" * 60)
    print("Todos los patrones ejecutados exitosamente")
    print("=" * 60)


if __name__ == "__main__":
    main()
