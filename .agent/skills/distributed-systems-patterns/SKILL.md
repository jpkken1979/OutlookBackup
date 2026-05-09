---
name: distributed-systems-patterns
description: "Patrones esenciales para sistemas distribuidos y microservicios: CAP/PACELC, consistencia (strong/eventual/causal), comunicación (sync/async/message queue/event sourcing/CQRS), resiliencia (circuit breaker/bulkhead/retry/backoff/timeout), patrones de datos (saga/outbox/CDC), service discovery y consensus (Raft). Triggers: distributed systems, microservices, CAP theorem, eventual consistency, saga pattern, circuit breaker, service discovery."
type: feature
---

# Distributed Systems Patterns

> Patrones esenciales para sistemas distribuidos y microservicios.

## Cuándo Usar Esta Skill

- Diseñando arquitecturas distribuidas
- Implementando microservicios
- Manejando consistencia y disponibilidad
- Debugging problemas de sistemas distribuidos

---

## Teoremas Fundamentales

### CAP Theorem

```
Solo puedes garantizar 2 de 3:

C - Consistency:    Todos los nodos ven los mismos datos
A - Availability:   El sistema siempre responde
P - Partition Tolerance: Funciona con fallos de red

┌───────────────────────────────────────┐
│              P (Network)              │
│         ┌───────────────┐             │
│    CA   │               │    CP       │
│  (N/A)  │       CAP     │  MongoDB    │
│         │    impossible │  HBase      │
│         │               │  Redis      │
│         └───────────────┘             │
│                                       │
│                  AP                   │
│            Cassandra, DynamoDB        │
└───────────────────────────────────────┘
```

### PACELC Theorem

```
Si hay Partición (P):
  → Elige entre Availability (A) y Consistency (C)
  
Else (E, sin partición):
  → Elige entre Latency (L) y Consistency (C)

Ejemplos:
- Cassandra: PA/EL (Availability + Low Latency)
- MongoDB: PC/EC (Consistency siempre)
- DynamoDB: PA/EL (configurable)
```

---

## Patrones de Consistencia

### 1. Strong Consistency

```
Todas las lecturas ven la escritura más reciente.

┌─────────┐    write(x=1)    ┌─────────┐
│ Client  │ ───────────────▶ │ Primary │
└─────────┘                  └─────────┘
     │                            │
     │      read() = 1           │ sync
     │ ◀──────────────────────   │
     │                       ┌─────────┐
     │                       │ Replica │
     └─────────────────────▶ └─────────┘

Implementación: 2PC, Raft, Paxos
Use case: Transacciones financieras
```

### 2. Eventual Consistency

```
Las lecturas eventualmente verán la escritura.

┌─────────┐    write(x=1)    ┌─────────┐
│ Client  │ ───────────────▶ │ Node A  │
└─────────┘                  └─────────┘
     │                            │
     │      read() = 0           │ async
     │ ◀──────────────────────   │ (delay)
     │                       ┌─────────┐
     │                       │ Node B  │
     └─────────────────────▶ └─────────┘

Use case: Social media feeds, caching
```

### 3. Causal Consistency

```
Operaciones causalmente relacionadas se ven en orden.

A: write(x=1)  ─────────┐
                        ▼
B: read(x)=1, write(y=2)
                        │
C: read(y)=2 implica read(x)=1

Implementación: Vector clocks, version vectors
```

---

## Patrones de Comunicación

### 1. Request-Response (Sync)

```python
# REST/gRPC
response = service.call(request)
process(response)

Pros: Simple, familiar
Cons: Acoplamiento temporal, cascading failures
```

### 2. Message Queue (Async)

```python
# Producer
queue.publish(message)

# Consumer
message = queue.consume()
process(message)

Pros: Desacoplado, resiliente
Cons: Complejidad, eventual consistency
```

### 3. Event Sourcing

```python
# En lugar de guardar estado actual, guarda eventos
events = [
    {"type": "OrderCreated", "data": {...}},
    {"type": "ItemAdded", "data": {...}},
    {"type": "OrderPaid", "data": {...}},
]

# Reconstruir estado
def rebuild_state(events):
    state = {}
    for event in events:
        state = apply_event(state, event)
    return state

Pros: Audit trail, time travel, event replay
Cons: Complejidad, storage, eventual consistency
```

### 4. CQRS (Command Query Responsibility Segregation)

```
┌─────────────────────────────────────────────┐
│                   Client                     │
└─────────────────────────────────────────────┘
        │                           │
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│   Commands    │           │    Queries    │
│  (Write API)  │           │  (Read API)   │
└───────────────┘           └───────────────┘
        │                           │
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│ Write Model   │ ──sync──▶ │  Read Model   │
│ (normalized)  │           │(denormalized) │
└───────────────┘           └───────────────┘

Use case: Alta lectura, reports complejos
```

---

## Patrones de Resiliencia

### 1. Circuit Breaker

```python
class CircuitBreaker:
    CLOSED = "closed"    # Normal
    OPEN = "open"        # Failing, rechaza requests
    HALF_OPEN = "half_open"  # Testing recovery
    
    def call(self, func):
        if self.state == OPEN:
            if time_since_open > timeout:
                self.state = HALF_OPEN
            else:
                raise CircuitOpenError()
        
        try:
            result = func()
            self.on_success()
            return result
        except Exception:
            self.on_failure()
            raise
    
    def on_failure(self):
        self.failure_count += 1
        if self.failure_count >= threshold:
            self.state = OPEN
    
    def on_success(self):
        self.state = CLOSED
        self.failure_count = 0
```

### 2. Bulkhead

```
Aislar recursos para evitar cascading failures.

┌─────────────────────────────────────────┐
│              Application                 │
├─────────────┬─────────────┬─────────────┤
│  Pool A     │  Pool B     │  Pool C     │
│  (Service A)│  (Service B)│  (Service C)│
│  10 threads │  10 threads │  10 threads │
└─────────────┴─────────────┴─────────────┘

Si Service A falla, solo Pool A se agota.
Services B y C siguen funcionando.
```

### 3. Retry with Backoff

```python
import time
import random

def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableError:
            if attempt == max_retries - 1:
                raise
            
            delay = base_delay * (2 ** attempt)  # Exponential
            delay *= (0.5 + random.random())     # Jitter
            time.sleep(delay)
```

### 4. Timeout

```python
import asyncio

async def with_timeout(coro, timeout_seconds):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        # Handle timeout (fallback, error, etc.)
        raise ServiceTimeoutError()
```

---

## Patrones de Datos

### 1. Saga Pattern

```
Para transacciones distribuidas sin 2PC.

Saga: Secuencia de transacciones locales + compensaciones.

┌─────────┐     ┌─────────┐     ┌─────────┐
│ Order   │────▶│ Payment │────▶│ Shipping│
│ Service │     │ Service │     │ Service │
└─────────┘     └─────────┘     └─────────┘
     T1              T2              T3
     C1              C2              C3

Si T3 falla:
  1. Ejecutar C2 (refund payment)
  2. Ejecutar C1 (cancel order)

Tipos:
- Choreography: Eventos, cada servicio escucha
- Orchestration: Coordinator central
```

### 2. Outbox Pattern

```
Garantizar at-least-once delivery.

┌─────────────────────────────────────────────┐
│              Single Transaction              │
│  ┌─────────────┐    ┌──────────────────┐    │
│  │ Business    │    │ Outbox Table     │    │
│  │ Table       │    │ (pending events) │    │
│  │ INSERT row  │    │ INSERT event     │    │
│  └─────────────┘    └──────────────────┘    │
└─────────────────────────────────────────────┘
                          │
                          ▼ (async worker)
                    ┌───────────┐
                    │  Message  │
                    │   Queue   │
                    └───────────┘
```

### 3. Change Data Capture (CDC)

```
Capturar cambios de DB para propagar a otros sistemas.

┌──────────┐    ┌──────────┐    ┌──────────┐
│ Database │───▶│ Debezium │───▶│  Kafka   │
│ (binlog) │    │   CDC    │    │ (events) │
└──────────┘    └──────────┘    └──────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Search   │    │ Cache    │    │ Analytics│
              │ Index    │    │ (Redis)  │    │ (DW)     │
              └──────────┘    └──────────┘    └──────────┘
```

---

## Service Discovery

```
┌─────────────────────────────────────────────┐
│              Service Registry               │
│         (Consul, etcd, Eureka)              │
│  ┌─────────────────────────────────────┐   │
│  │ service-a: [10.0.0.1, 10.0.0.2]     │   │
│  │ service-b: [10.0.0.3]               │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
         ▲                    │
         │ register           │ discover
         │                    ▼
    ┌─────────┐         ┌─────────┐
    │ Service │         │ Service │
    │    A    │         │    B    │
    └─────────┘         └─────────┘
```

---

## Distributed Consensus

### Raft Algorithm

```
1. Leader Election
   - Nodes start as Followers
   - If no heartbeat, become Candidate
   - Request votes from others
   - Majority wins → Leader

2. Log Replication
   - Client sends to Leader
   - Leader appends to log
   - Leader replicates to Followers
   - Once majority confirms → Commit

3. Safety
   - Only logs with committed entries can become leader
   - Entries committed in current term are safe
```

---

## Checklist de Distributed Systems

- [ ] ¿Qué pasa si un servicio falla?
- [ ] ¿Qué pasa si la red se parte?
- [ ] ¿Cómo manejas duplicados?
- [ ] ¿Cómo ordenas eventos?
- [ ] ¿Cómo haces rollback de transacciones distribuidas?
- [ ] ¿Cómo debuggeas problemas?
- [ ] ¿Tienes circuit breakers?
- [ ] ¿Tienes retries con backoff?
- [ ] ¿Tienes timeouts apropiados?

---

*Skill: distributed-systems-patterns v1.0*
