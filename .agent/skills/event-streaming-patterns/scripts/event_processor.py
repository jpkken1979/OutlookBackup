#!/usr/bin/env python3
"""
Event Streaming Processor Demo
Simulación de procesamiento de eventos con patrones Kafka/RabbitMQ.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections.abc import Callable, Awaitable
from collections import defaultdict
import secrets
import time

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# MODELOS DE EVENTOS
# =============================================================================


@dataclass
class Event:
    """Evento del sistema."""

    event_id: str = field(default_factory=lambda: secrets.token_hex(8))
    event_type: str = ""
    aggregate_type: str = ""
    aggregate_id: str = ""
    payload: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Event":
        return cls(**json.loads(data))


@dataclass
class Message:
    """Mensaje de la cola."""

    message_id: str
    topic: str
    partition: int
    offset: int
    key: str | None
    value: str
    headers: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# SIMULADOR DE KAFKA
# =============================================================================


class KafkaSimulator:
    """Simulador simple de Kafka para demostración."""

    def __init__(self):
        self.topics: dict[str, list[list[Message]]] = {}  # topic -> partitions -> messages
        self.consumer_groups: dict[str, dict[str, int]] = {}  # group -> topic:partition -> offset
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def create_topic(self, name: str, partitions: int = 3):
        """Crea un topic con N particiones."""
        self.topics[name] = [[] for _ in range(partitions)]
        logger.info(f"Topic '{name}' created with {partitions} partitions")

    def _get_partition(self, key: str | None, num_partitions: int) -> int:
        """Determina partición basado en key."""
        if key is None:
            return hash(time.time()) % num_partitions
        return hash(key) % num_partitions

    async def produce(
        self, topic: str, key: str | None, value: str, headers: dict = None
    ) -> Message:
        """Produce un mensaje."""
        if topic not in self.topics:
            self.create_topic(topic)

        partitions = self.topics[topic]
        partition_id = self._get_partition(key, len(partitions))
        partition = partitions[partition_id]

        message = Message(
            message_id=secrets.token_hex(8),
            topic=topic,
            partition=partition_id,
            offset=len(partition),
            key=key,
            value=value,
            headers=headers or {},
        )

        partition.append(message)
        logger.info(f"Produced to {topic}[{partition_id}] offset={message.offset}")

        # Trigger handlers
        for handler in self._handlers[topic]:
            await handler(message)

        return message

    def subscribe(self, topic: str, handler: Callable[[Message], Awaitable[None]]):
        """Suscribe un handler a un topic."""
        self._handlers[topic].append(handler)
        logger.info(f"Subscribed to topic '{topic}'")

    def get_messages(self, topic: str, partition: int, from_offset: int = 0) -> list[Message]:
        """Obtiene mensajes de una partición."""
        if topic not in self.topics:
            return []
        return self.topics[topic][partition][from_offset:]

    def get_stats(self) -> dict:
        """Estadísticas del broker."""
        stats = {}
        for topic, partitions in self.topics.items():
            stats[topic] = {
                "partitions": len(partitions),
                "messages": sum(len(p) for p in partitions),
                "per_partition": [len(p) for p in partitions],
            }
        return stats


# =============================================================================
# SAGA PATTERN
# =============================================================================


@dataclass
class SagaStep:
    """Paso de una saga."""

    name: str
    execute: Callable[[], Awaitable[bool]]
    compensate: Callable[[], Awaitable[bool]]


class Saga:
    """Implementación del patrón Saga."""

    def __init__(self, name: str):
        self.name = name
        self.steps: list[SagaStep] = []
        self.completed_steps: list[SagaStep] = []
        self.status = "pending"

    def add_step(self, step: SagaStep) -> "Saga":
        self.steps.append(step)
        return self

    async def execute(self) -> bool:
        """Ejecuta la saga."""
        logger.info(f"Saga '{self.name}': Starting execution")
        self.status = "running"

        for step in self.steps:
            try:
                logger.info(f"Saga '{self.name}': Executing step '{step.name}'")
                success = await step.execute()

                if not success:
                    raise Exception(f"Step '{step.name}' returned False")

                self.completed_steps.append(step)

            except Exception as e:
                logger.error(f"Saga '{self.name}': Step '{step.name}' failed - {e}")
                await self._compensate()
                self.status = "failed"
                return False

        self.status = "completed"
        logger.info(f"Saga '{self.name}': Completed successfully")
        return True

    async def _compensate(self):
        """Ejecuta compensaciones en orden inverso."""
        logger.info(f"Saga '{self.name}': Starting compensation")

        for step in reversed(self.completed_steps):
            try:
                logger.info(f"Saga '{self.name}': Compensating '{step.name}'")
                await step.compensate()
            except Exception as e:
                logger.error(f"Saga '{self.name}': Compensation for '{step.name}' failed - {e}")

        self.completed_steps.clear()


# =============================================================================
# OUTBOX PATTERN
# =============================================================================


@dataclass
class OutboxEntry:
    """Entrada en el outbox."""

    id: str = field(default_factory=lambda: secrets.token_hex(8))
    aggregate_type: str = ""
    aggregate_id: str = ""
    event_type: str = ""
    payload: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    published_at: str | None = None


class Outbox:
    """Implementación del patrón Outbox."""

    def __init__(self, kafka: KafkaSimulator):
        self.entries: list[OutboxEntry] = []
        self.kafka = kafka

    def add(self, entry: OutboxEntry):
        """Añade entrada al outbox (en la misma transacción de DB)."""
        self.entries.append(entry)
        logger.info(f"Outbox: Added entry {entry.id}")

    def get_unpublished(self) -> list[OutboxEntry]:
        """Obtiene entradas no publicadas."""
        return [e for e in self.entries if e.published_at is None]

    async def relay(self):
        """Publica entradas pendientes a Kafka."""
        unpublished = self.get_unpublished()
        logger.info(f"Outbox: Relaying {len(unpublished)} entries")

        for entry in unpublished:
            try:
                topic = f"{entry.aggregate_type.lower()}.events"
                await self.kafka.produce(
                    topic=topic,
                    key=entry.aggregate_id,
                    value=entry.payload,
                    headers={"event_type": entry.event_type},
                )
                entry.published_at = datetime.now().isoformat()
                logger.info(f"Outbox: Published {entry.id} to {topic}")

            except Exception as e:
                logger.error(f"Outbox: Failed to publish {entry.id} - {e}")


# =============================================================================
# DEMO
# =============================================================================


async def demo():
    """Demostración de event streaming patterns."""
    print("\n" + "=" * 60)
    print("EVENT STREAMING PATTERNS DEMO")
    print("=" * 60)

    # Crear Kafka simulator
    kafka = KafkaSimulator()
    kafka.create_topic("orders.events", partitions=3)
    kafka.create_topic("inventory.events", partitions=2)

    # Consumer handler
    processed_events = []

    async def order_event_handler(message: Message):
        event = Event.from_json(message.value)
        processed_events.append(event)
        logger.info(f"Consumer: Processed {event.event_type} for {event.aggregate_id}")

    kafka.subscribe("orders.events", order_event_handler)

    # =============================================================================
    # DEMO 1: Producir eventos
    # =============================================================================
    print("\n--- DEMO 1: Event Production ---")

    for i in range(5):
        event = Event(
            event_type="OrderCreated",
            aggregate_type="Order",
            aggregate_id=f"order-{i}",
            payload={"total": 100 + i * 10, "items": i + 1},
        )
        await kafka.produce("orders.events", key=event.aggregate_id, value=event.to_json())

    print(f"\nKafka stats: {kafka.get_stats()}")

    # =============================================================================
    # DEMO 2: Saga Pattern
    # =============================================================================
    print("\n--- DEMO 2: Saga Pattern ---")

    order_id = "saga-order-123"
    inventory_reserved = False
    payment_processed = False

    async def reserve_inventory():
        nonlocal inventory_reserved
        logger.info(f"  -> Reserving inventory for {order_id}")
        inventory_reserved = True
        return True

    async def release_inventory():
        nonlocal inventory_reserved
        logger.info(f"  -> Releasing inventory for {order_id}")
        inventory_reserved = False
        return True

    async def process_payment():
        nonlocal payment_processed
        logger.info(f"  -> Processing payment for {order_id}")
        # Simular fallo
        raise Exception("Payment gateway timeout")

    async def refund_payment():
        nonlocal payment_processed
        logger.info(f"  -> Refunding payment for {order_id}")
        payment_processed = False
        return True

    saga = Saga("CreateOrder")
    saga.add_step(SagaStep("reserve_inventory", reserve_inventory, release_inventory))
    saga.add_step(SagaStep("process_payment", process_payment, refund_payment))

    result = await saga.execute()
    print(f"\nSaga result: {'Success' if result else 'Failed (compensated)'}")
    print(f"Inventory reserved: {inventory_reserved}")  # Should be False after compensation

    # =============================================================================
    # DEMO 3: Outbox Pattern
    # =============================================================================
    print("\n--- DEMO 3: Outbox Pattern ---")

    outbox = Outbox(kafka)

    # Simular creación de orden con evento en outbox
    order_data = {"id": "outbox-order-456", "total": 250.00}

    # En transacción real: INSERT order + INSERT outbox
    outbox.add(
        OutboxEntry(
            aggregate_type="Order",
            aggregate_id=order_data["id"],
            event_type="OrderCreated",
            payload=json.dumps({"order": order_data}),
        )
    )

    outbox.add(
        OutboxEntry(
            aggregate_type="Order",
            aggregate_id=order_data["id"],
            event_type="OrderPaid",
            payload=json.dumps({"order_id": order_data["id"], "amount": 250.00}),
        )
    )

    print(f"Outbox entries: {len(outbox.entries)}")
    print(f"Unpublished: {len(outbox.get_unpublished())}")

    # Relay (proceso separado en producción)
    await outbox.relay()

    print(f"Unpublished after relay: {len(outbox.get_unpublished())}")

    # =============================================================================
    # DEMO 4: Event Sourcing (simplificado)
    # =============================================================================
    print("\n--- DEMO 4: Event Sourcing ---")

    class OrderAggregate:
        def __init__(self):
            self.id: str | None = None
            self.status = "draft"
            self.items: list = []
            self.total = 0.0
            self.events: list[Event] = []

        def apply(self, event: Event):
            if event.event_type == "OrderCreated":
                self.id = event.aggregate_id
                self.status = "pending"
            elif event.event_type == "ItemAdded":
                self.items.append(event.payload["item"])
                self.total += event.payload["item"]["price"]
            elif event.event_type == "OrderConfirmed":
                self.status = "confirmed"
            self.events.append(event)

        @classmethod
        def from_events(cls, events: list[Event]) -> "OrderAggregate":
            aggregate = cls()
            for event in events:
                aggregate.apply(event)
            return aggregate

    # Crear eventos
    events = [
        Event(event_type="OrderCreated", aggregate_type="Order", aggregate_id="es-order-789"),
        Event(
            event_type="ItemAdded",
            aggregate_type="Order",
            aggregate_id="es-order-789",
            payload={"item": {"name": "Widget", "price": 29.99}},
        ),
        Event(
            event_type="ItemAdded",
            aggregate_type="Order",
            aggregate_id="es-order-789",
            payload={"item": {"name": "Gadget", "price": 49.99}},
        ),
        Event(event_type="OrderConfirmed", aggregate_type="Order", aggregate_id="es-order-789"),
    ]

    # Reconstruir agregado desde eventos
    order = OrderAggregate.from_events(events)
    print(f"Order ID: {order.id}")
    print(f"Status: {order.status}")
    print(f"Items: {len(order.items)}")
    print(f"Total: ${order.total:.2f}")
    print(f"Event count: {len(order.events)}")

    # =============================================================================
    # RESUMEN
    # =============================================================================
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Total events produced: {sum(t['messages'] for t in kafka.get_stats().values())}")
    print(f"Events processed by consumer: {len(processed_events)}")
    print("\nPatterns demonstrated:")
    print("  ✅ Event Production (Kafka-style)")
    print("  ✅ Saga Pattern (with compensation)")
    print("  ✅ Outbox Pattern (transactional outbox)")
    print("  ✅ Event Sourcing (aggregate reconstruction)")


def main():
    """Entry point."""
    asyncio.run(demo())


if __name__ == "__main__":
    main()
