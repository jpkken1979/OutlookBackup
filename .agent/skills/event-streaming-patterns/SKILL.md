---
name: event-streaming-patterns
description: "Master event streaming patterns with expert patterns and practices."
type: feature
---

# Event Streaming Patterns

> Patrones de arquitectura para Kafka, RabbitMQ y sistemas de mensajería enterprise.

---

## Descripción

Esta skill cubre arquitecturas de event streaming y message queues para sistemas distribuidos de alta disponibilidad. Incluye Apache Kafka, RabbitMQ, y patrones agnósticos de broker.

---

## Comparativa de Tecnologías

| Característica | Kafka | RabbitMQ | Redis Streams | AWS SQS |
|----------------|-------|----------|---------------|---------|
| **Modelo** | Log distribuido | Message broker | Stream log | Queue managed |
| **Throughput** | Millones/s | Miles/s | Miles/s | Variable |
| **Latencia** | ~5ms | ~1ms | <1ms | ~20ms |
| **Ordenamiento** | Por partición | Por queue | Por stream | No garantizado |
| **Replay** | ✅ Sí | ❌ No | ✅ Sí | ❌ No |
| **Retención** | Configurable | Hasta consumo | Configurable | 14 días máx |
| **Complejidad** | Alta | Media | Baja | Baja |

---

## Apache Kafka

### Conceptos Fundamentales

```
┌─────────────────────────────────────────────────────────────┐
│                        KAFKA CLUSTER                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Topic: orders                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ Partition 0: [msg1][msg4][msg7][msg10]...           │   │
│   ├─────────────────────────────────────────────────────┤   │
│   │ Partition 1: [msg2][msg5][msg8][msg11]...           │   │
│   ├─────────────────────────────────────────────────────┤   │
│   │ Partition 2: [msg3][msg6][msg9][msg12]...           │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
│   Consumer Group: order-processors                           │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│   │Consumer 1│  │Consumer 2│  │Consumer 3│                  │
│   │ (P0)     │  │ (P1)     │  │ (P2)     │                  │
│   └──────────┘  └──────────┘  └──────────┘                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Producer (Node.js con kafkajs)

```typescript
import { Kafka, Partitioners, CompressionTypes } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'order-service',
  brokers: process.env.KAFKA_BROKERS!.split(','),
  ssl: process.env.KAFKA_SSL === 'true',
  sasl: process.env.KAFKA_SASL_USERNAME ? {
    mechanism: 'scram-sha-256',
    username: process.env.KAFKA_SASL_USERNAME,
    password: process.env.KAFKA_SASL_PASSWORD!,
  } : undefined,
  retry: {
    initialRetryTime: 100,
    retries: 8,
  },
});

const producer = kafka.producer({
  createPartitioner: Partitioners.DefaultPartitioner,
  allowAutoTopicCreation: false,
  transactionTimeout: 30000,
});

// Conectar con retry
async function connectProducer() {
  await producer.connect();
  console.log('Kafka producer connected');
}

// Enviar evento
async function sendOrderEvent(order: Order) {
  await producer.send({
    topic: 'orders',
    messages: [{
      key: order.customerId,  // Mismo customer → misma partición
      value: JSON.stringify({
        eventType: 'ORDER_CREATED',
        payload: order,
        timestamp: Date.now(),
        correlationId: order.id,
      }),
      headers: {
        'content-type': 'application/json',
        'event-version': '1.0',
        'source': 'order-service',
      },
    }],
    compression: CompressionTypes.GZIP,
  });
}

// Batch de eventos
async function sendBatch(events: OrderEvent[]) {
  await producer.sendBatch({
    topicMessages: [{
      topic: 'orders',
      messages: events.map((event) => ({
        key: event.customerId,
        value: JSON.stringify(event),
      })),
    }],
    compression: CompressionTypes.GZIP,
  });
}

// Transacciones (exactly-once)
async function sendTransactional(events: OrderEvent[]) {
  const transaction = await producer.transaction();

  try {
    await transaction.send({
      topic: 'orders',
      messages: events.map((e) => ({
        key: e.customerId,
        value: JSON.stringify(e),
      })),
    });

    await transaction.commit();
  } catch (error) {
    await transaction.abort();
    throw error;
  }
}
```

### Consumer

```typescript
const consumer = kafka.consumer({
  groupId: 'order-processor-group',
  sessionTimeout: 30000,
  heartbeatInterval: 3000,
  maxBytesPerPartition: 1048576,  // 1MB
  retry: {
    retries: 5,
  },
});

async function startConsumer() {
  await consumer.connect();

  await consumer.subscribe({
    topics: ['orders', 'payments'],
    fromBeginning: false,
  });

  await consumer.run({
    autoCommit: false,  // Manual commit para control
    eachBatchAutoResolve: false,

    eachBatch: async ({ batch, resolveOffset, heartbeat, commitOffsetsIfNecessary }) => {
      for (const message of batch.messages) {
        try {
          const event = JSON.parse(message.value!.toString());

          // Procesar según tipo
          switch (event.eventType) {
            case 'ORDER_CREATED':
              await processNewOrder(event.payload);
              break;
            case 'ORDER_PAID':
              await processPayment(event.payload);
              break;
            default:
              console.warn(`Unknown event type: ${event.eventType}`);
          }

          // Marcar como procesado
          resolveOffset(message.offset);

          // Heartbeat para mantener sesión
          await heartbeat();

        } catch (error) {
          console.error('Failed to process message:', error);
          // Dead letter queue
          await sendToDeadLetter(message, error);
          resolveOffset(message.offset);
        }
      }

      // Commit manual
      await commitOffsetsIfNecessary();
    },
  });
}

// Graceful shutdown
async function shutdown() {
  await consumer.disconnect();
  await producer.disconnect();
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
```

### Dead Letter Queue

```typescript
const dlqProducer = kafka.producer();

async function sendToDeadLetter(originalMessage: KafkaMessage, error: Error) {
  await dlqProducer.send({
    topic: 'orders.dlq',
    messages: [{
      key: originalMessage.key,
      value: originalMessage.value,
      headers: {
        ...originalMessage.headers,
        'dlq-reason': error.message,
        'dlq-timestamp': Date.now().toString(),
        'original-topic': 'orders',
        'original-partition': originalMessage.partition?.toString(),
        'original-offset': originalMessage.offset,
      },
    }],
  });
}
```

---

## RabbitMQ

### Conceptos Fundamentales

```
┌─────────────────────────────────────────────────────────────┐
│                      RABBITMQ                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Producer → Exchange ─┬─► Queue A → Consumer 1               │
│             (topic)   ├─► Queue B → Consumer 2               │
│                       └─► Queue C → Consumer 3               │
│                                                              │
│  Exchange Types:                                             │
│  • direct  - routing key exacto                              │
│  • topic   - routing key con wildcards                       │
│  • fanout  - broadcast a todas las queues                    │
│  • headers - basado en headers del mensaje                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Setup con amqplib

```typescript
import amqp, { Connection, Channel, ConsumeMessage } from 'amqplib';

class RabbitMQService {
  private connection: Connection | null = null;
  private channel: Channel | null = null;

  async connect(): Promise<void> {
    this.connection = await amqp.connect({
      hostname: process.env.RABBITMQ_HOST,
      port: parseInt(process.env.RABBITMQ_PORT || '5672'),
      username: process.env.RABBITMQ_USER,
      password: process.env.RABBITMQ_PASS,
      vhost: process.env.RABBITMQ_VHOST || '/',
      heartbeat: 60,
    });

    this.channel = await this.connection.createChannel();

    // Prefetch para load balancing
    await this.channel.prefetch(10);

    console.log('RabbitMQ connected');
  }

  async setupTopology(): Promise<void> {
    const ch = this.channel!;

    // Exchange principal
    await ch.assertExchange('orders', 'topic', {
      durable: true,
      autoDelete: false,
    });

    // Dead Letter Exchange
    await ch.assertExchange('orders.dlx', 'direct', {
      durable: true,
    });

    // Queue con DLQ
    await ch.assertQueue('orders.process', {
      durable: true,
      deadLetterExchange: 'orders.dlx',
      deadLetterRoutingKey: 'orders.failed',
      messageTtl: 86400000,  // 24h
    });

    // Dead Letter Queue
    await ch.assertQueue('orders.dlq', {
      durable: true,
    });

    // Bindings
    await ch.bindQueue('orders.process', 'orders', 'order.*');
    await ch.bindQueue('orders.dlq', 'orders.dlx', 'orders.failed');
  }

  async publish(routingKey: string, message: object): Promise<boolean> {
    return this.channel!.publish(
      'orders',
      routingKey,
      Buffer.from(JSON.stringify(message)),
      {
        persistent: true,
        contentType: 'application/json',
        timestamp: Date.now(),
        messageId: crypto.randomUUID(),
      }
    );
  }

  async consume(
    queue: string,
    handler: (msg: ConsumeMessage) => Promise<void>
  ): Promise<void> {
    await this.channel!.consume(queue, async (msg) => {
      if (!msg) return;

      try {
        await handler(msg);
        this.channel!.ack(msg);
      } catch (error) {
        console.error('Message processing failed:', error);

        // Requeue si es primer intento, reject si ya reintentó
        const redelivered = msg.fields.redelivered;
        this.channel!.nack(msg, false, !redelivered);
      }
    });
  }

  async close(): Promise<void> {
    await this.channel?.close();
    await this.connection?.close();
  }
}

// Uso
const rabbit = new RabbitMQService();
await rabbit.connect();
await rabbit.setupTopology();

// Publicar
await rabbit.publish('order.created', {
  orderId: '123',
  customerId: 'abc',
  total: 99.99,
});

// Consumir
await rabbit.consume('orders.process', async (msg) => {
  const order = JSON.parse(msg.content.toString());
  await processOrder(order);
});
```

---

## Patrones de Mensajería

### 1. Event Sourcing

```typescript
interface DomainEvent {
  eventId: string;
  aggregateId: string;
  aggregateType: string;
  eventType: string;
  payload: unknown;
  metadata: {
    timestamp: number;
    version: number;
    userId?: string;
    correlationId?: string;
  };
}

class OrderAggregate {
  private events: DomainEvent[] = [];
  private state: OrderState = { status: 'draft', items: [] };

  // Aplicar evento
  private apply(event: DomainEvent): void {
    switch (event.eventType) {
      case 'OrderCreated':
        this.state = {
          ...this.state,
          id: event.aggregateId,
          status: 'pending',
          customerId: (event.payload as any).customerId,
        };
        break;
      case 'ItemAdded':
        this.state.items.push((event.payload as any).item);
        break;
      case 'OrderConfirmed':
        this.state.status = 'confirmed';
        break;
    }
  }

  // Reconstruir desde eventos
  static fromEvents(events: DomainEvent[]): OrderAggregate {
    const aggregate = new OrderAggregate();
    events.forEach((e) => aggregate.apply(e));
    aggregate.events = events;
    return aggregate;
  }

  // Comando → Evento
  addItem(item: OrderItem): DomainEvent {
    const event: DomainEvent = {
      eventId: crypto.randomUUID(),
      aggregateId: this.state.id!,
      aggregateType: 'Order',
      eventType: 'ItemAdded',
      payload: { item },
      metadata: {
        timestamp: Date.now(),
        version: this.events.length + 1,
      },
    };

    this.apply(event);
    this.events.push(event);

    return event;
  }
}
```

### 2. Saga Pattern

```typescript
interface SagaStep {
  name: string;
  execute: () => Promise<void>;
  compensate: () => Promise<void>;
}

class OrderSaga {
  private completedSteps: SagaStep[] = [];

  private steps: SagaStep[] = [
    {
      name: 'reserveInventory',
      execute: async () => {
        await inventoryService.reserve(this.orderId, this.items);
      },
      compensate: async () => {
        await inventoryService.release(this.orderId);
      },
    },
    {
      name: 'processPayment',
      execute: async () => {
        await paymentService.charge(this.orderId, this.amount);
      },
      compensate: async () => {
        await paymentService.refund(this.orderId);
      },
    },
    {
      name: 'createShipment',
      execute: async () => {
        await shippingService.create(this.orderId, this.address);
      },
      compensate: async () => {
        await shippingService.cancel(this.orderId);
      },
    },
  ];

  constructor(
    private orderId: string,
    private items: OrderItem[],
    private amount: number,
    private address: Address
  ) {}

  async execute(): Promise<void> {
    for (const step of this.steps) {
      try {
        console.log(`Executing step: ${step.name}`);
        await step.execute();
        this.completedSteps.push(step);
      } catch (error) {
        console.error(`Step ${step.name} failed:`, error);
        await this.compensate();
        throw error;
      }
    }
  }

  private async compensate(): Promise<void> {
    console.log('Starting compensation...');

    for (const step of this.completedSteps.reverse()) {
      try {
        console.log(`Compensating step: ${step.name}`);
        await step.compensate();
      } catch (error) {
        console.error(`Compensation for ${step.name} failed:`, error);
        // Log para manual intervention
        await this.logCompensationFailure(step, error);
      }
    }
  }
}
```

### 3. Outbox Pattern

```typescript
// En la misma transacción de DB
async function createOrder(orderData: CreateOrderDTO) {
  const transaction = await db.transaction();

  try {
    // 1. Crear orden
    const order = await Order.create(orderData, { transaction });

    // 2. Guardar evento en outbox (misma transacción)
    await Outbox.create({
      aggregateType: 'Order',
      aggregateId: order.id,
      eventType: 'OrderCreated',
      payload: JSON.stringify(order),
      createdAt: new Date(),
    }, { transaction });

    await transaction.commit();
    return order;
  } catch (error) {
    await transaction.rollback();
    throw error;
  }
}

// Outbox Relay (proceso separado)
async function relayOutboxEvents() {
  while (true) {
    const events = await Outbox.findAll({
      where: { publishedAt: null },
      order: [['createdAt', 'ASC']],
      limit: 100,
    });

    for (const event of events) {
      try {
        await kafka.send({
          topic: `${event.aggregateType.toLowerCase()}.events`,
          messages: [{
            key: event.aggregateId,
            value: event.payload,
            headers: {
              eventType: event.eventType,
              aggregateId: event.aggregateId,
            },
          }],
        });

        event.publishedAt = new Date();
        await event.save();
      } catch (error) {
        console.error('Failed to relay event:', error);
      }
    }

    await sleep(1000);
  }
}
```

---

## Garantías de Entrega

### At-Least-Once (más común)

```typescript
// Consumer con idempotencia
async function processMessage(message: Message) {
  const eventId = message.headers.eventId;

  // Check si ya procesamos
  const processed = await redis.get(`processed:${eventId}`);
  if (processed) {
    console.log(`Event ${eventId} already processed, skipping`);
    return;
  }

  // Procesar
  await handleEvent(message);

  // Marcar como procesado (con TTL)
  await redis.set(`processed:${eventId}`, '1', 'EX', 86400);
}
```

### Exactly-Once (Kafka Transactions)

```typescript
const producer = kafka.producer({
  transactionalId: 'order-processor-txn',
  maxInFlightRequests: 1,
  idempotent: true,
});

await producer.transaction();
```

---

## Monitoreo

### Métricas Kafka

```typescript
const { Kafka } = require('kafkajs');

const kafka = new Kafka({
  clientId: 'my-app',
  brokers: ['localhost:9092'],
});

const admin = kafka.admin();

// Consumer lag
async function getConsumerLag(groupId: string) {
  await admin.connect();

  const offsets = await admin.fetchOffsets({
    groupId,
    topics: ['orders'],
  });

  const topicOffsets = await admin.fetchTopicOffsets('orders');

  let totalLag = 0;
  for (const partition of offsets) {
    const latest = topicOffsets.find(
      (t) => t.partition === partition.partition
    );
    if (latest) {
      totalLag += parseInt(latest.offset) - parseInt(partition.offset);
    }
  }

  return totalLag;
}
```

---

## Referencias

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [KafkaJS](https://kafka.js.org/)
- [Event Sourcing Pattern](https://microservices.io/patterns/data/event-sourcing.html)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
