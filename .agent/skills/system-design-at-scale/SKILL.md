---
name: system-design-at-scale
description: "Framework y patrones para diseñar sistemas que escalan a millones de usuarios. Covers: framework de 6 pasos (requisitos/capacidad/API/HLD/deep dive/trade-offs), patrones de escalabilidad (horizontal scaling, database scaling, caching, message queues), sistemas comunes (URL shortener, rate limiter, chat, news feed). Triggers: system design, scalability, microservices, load balancing, caching, distributed systems."
type: feature
---

# System Design at Scale

> Framework y patrones para diseñar sistemas que escalan a millones de usuarios.

## Cuándo Usar Esta Skill

- Diseñando arquitectura de sistemas distribuidos
- Entrevistas de system design
- Planificando capacidad
- Evaluando trade-offs de escalabilidad

---

## Framework de 6 Pasos

### 1. Clarificar Requisitos (5 min)

**Funcionales:**
- ¿Qué hace el sistema?
- ¿Quiénes son los usuarios?
- ¿Cuáles son los casos de uso principales?

**No Funcionales:**
- Latencia: ¿P99 < 100ms?
- Disponibilidad: ¿99.9% (8.76h downtime/año)?
- Consistencia: ¿Strong o eventual?
- Durabilidad: ¿Pérdida de datos aceptable?

### 2. Estimaciones de Capacidad (5 min)

```
Fórmulas clave:

QPS (Queries Per Second):
  QPS = DAU × queries_per_user / 86400

Storage:
  Storage = items × item_size × retention_days

Bandwidth:
  Bandwidth = QPS × avg_response_size

Ejemplo Twitter:
  - 300M DAU
  - 5 tweets/día = 1.5B tweets/día
  - Write QPS = 1.5B / 86400 = ~17K/s
  - Read QPS = ~170K/s (10x read-heavy)
```

### 3. API Design (5 min)

```
REST endpoints:
POST /api/v1/tweets
  Body: { content: string, media_ids?: string[] }
  Response: { id, created_at, ... }

GET /api/v1/users/{id}/timeline
  Query: ?cursor=xxx&limit=20
  Response: { tweets: [...], next_cursor }

GET /api/v1/tweets/{id}
  Response: { id, content, author, ... }
```

### 4. High-Level Design (10 min)

```
┌─────────────────────────────────────────────────────────────┐
│                        CDN (Cloudflare)                     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer (L7)                       │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ API GW  │         │ API GW  │         │ API GW  │
    └─────────┘         └─────────┘         └─────────┘
         │                    │                    │
    ┌─────────────────────────────────────────────────────┐
    │                   Service Mesh                       │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │
    │  │ User    │  │ Tweet   │  │Timeline │  │ Search │ │
    │  │ Service │  │ Service │  │ Service │  │Service │ │
    │  └─────────┘  └─────────┘  └─────────┘  └────────┘ │
    └─────────────────────────────────────────────────────┘
         │                    │                    │
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │  Redis  │         │PostgreSQL│        │Elastic  │
    │ (Cache) │         │(Sharded) │        │ Search  │
    └─────────┘         └─────────┘         └─────────┘
```

### 5. Deep Dive (15 min)

**Componentes críticos:**
- Caching strategy
- Database sharding
- Async processing
- Consistency guarantees

### 6. Trade-offs & Bottlenecks (5 min)

| Trade-off | Opción A | Opción B |
|-----------|----------|----------|
| Consistencia vs Disponibilidad | Strong (ACID) | Eventual (BASE) |
| Latencia vs Throughput | Optimizar latencia | Batch processing |
| Push vs Pull | Fan-out on write | Fan-out on read |

---

## Patrones de Escalabilidad

### Horizontal Scaling

```
Stateless Services:
- No sesión en servidor
- Sesiones en Redis/JWT
- Cualquier instancia puede responder

Load Balancing:
- Round Robin: Simple, igual distribución
- Least Connections: Para requests largos
- IP Hash: Sticky sessions
- Weighted: Servidores heterogéneos
```

### Database Scaling

```
Read Replicas:
┌─────────┐     ┌─────────┐
│ Primary │────▶│Replica 1│
│  (RW)   │     │  (RO)   │
└─────────┘     └─────────┘
     │          ┌─────────┐
     └─────────▶│Replica 2│
                │  (RO)   │
                └─────────┘

Sharding:
┌─────────────────────────────────────┐
│           Shard Router              │
└─────────────────────────────────────┘
     │              │              │
┌─────────┐   ┌─────────┐   ┌─────────┐
│Shard 0  │   │Shard 1  │   │Shard 2  │
│ A-H     │   │ I-P     │   │ Q-Z     │
└─────────┘   └─────────┘   └─────────┘

Sharding Strategies:
- Range: user_id 1-1M, 1M-2M, etc.
- Hash: hash(user_id) % num_shards
- Directory: lookup table
- Consistent Hashing: minimiza re-sharding
```

### Caching Patterns

```
Cache-Aside (Lazy Loading):
1. App checks cache
2. If miss → query DB → update cache
3. Return to client

Write-Through:
1. Write to cache
2. Cache writes to DB
3. Return to client

Write-Behind:
1. Write to cache
2. Return to client (async)
3. Cache writes to DB later

Cache Eviction:
- LRU: Least Recently Used
- LFU: Least Frequently Used
- TTL: Time To Live
```

### Message Queues

```
Use Cases:
- Async processing (emails, notifications)
- Decoupling services
- Load leveling (spikes)
- Event sourcing

Patterns:
- Point-to-Point: One consumer
- Pub/Sub: Multiple consumers
- Fan-out: Broadcast to all
- Dead Letter Queue: Failed messages
```

---

## Sistemas Comunes

### 1. URL Shortener (bit.ly)

```
Requirements:
- 100M URLs/día escritos
- 10B URLs/día leídos
- 5 años retención

Capacity:
- Write: 100M/86400 = ~1.2K QPS
- Read: 10B/86400 = ~116K QPS
- Storage: 100M × 365 × 5 × 500B = 91TB

Design:
┌─────────┐  POST /shorten  ┌─────────┐
│  Client │────────────────▶│  API    │
└─────────┘                 │ Server  │
     │                      └─────────┘
     │                           │
     │ GET /{short}              │
     │                      ┌─────────┐
     └─────────────────────▶│  Redis  │ ← Hot URLs
                            │  Cache  │
                            └─────────┘
                                 │
                            ┌─────────┐
                            │  DB     │ ← All URLs
                            │(Sharded)│
                            └─────────┘

Key Decisions:
- Base62 encoding para short URL
- Counter vs Random ID (counter más eficiente)
- Cache hot URLs (20% = 80% traffic)
```

### 2. Rate Limiter

```
Algorithms:

Token Bucket:
- Bucket con N tokens
- Cada request consume 1 token
- Tokens se regeneran a rate R
- Si bucket vacío → reject
✅ Permite bursts
❌ Memoria por usuario

Sliding Window:
- Ventana de tiempo (1 min)
- Counter de requests
- Si counter > limit → reject
✅ Suaviza tráfico
❌ Más cálculo

Implementation:
```python
import time
import redis

class RateLimiter:
    def __init__(self, redis_client, limit=100, window=60):
        self.redis = redis_client
        self.limit = limit
        self.window = window
    
    def is_allowed(self, user_id: str) -> bool:
        key = f"rate:{user_id}"
        current = int(time.time())
        
        pipe = self.redis.pipeline()
        pipe.zadd(key, {current: current})
        pipe.zremrangebyscore(key, 0, current - self.window)
        pipe.zcard(key)
        pipe.expire(key, self.window)
        results = pipe.execute()
        
        return results[2] <= self.limit
```

### 3. Chat System (WhatsApp)

```
Requirements:
- 1B users
- 100B messages/día
- Real-time delivery
- Offline support

Design:
┌─────────┐  WebSocket  ┌─────────┐
│  App    │◄───────────▶│ Gateway │
└─────────┘             │ Server  │
                        └─────────┘
                             │
                        ┌─────────┐
                        │ Message │
                        │ Queue   │
                        └─────────┘
                             │
                   ┌─────────┼─────────┐
                   │         │         │
              ┌─────────┐┌─────────┐┌─────────┐
              │ Chat    ││ Push    ││ Presence│
              │ Service ││ Service ││ Service │
              └─────────┘└─────────┘└─────────┘

Key Decisions:
- WebSocket para real-time
- Message queue para delivery garantizada
- Cassandra para mensajes (write-heavy)
- Redis para presence/typing
```

### 4. News Feed (Facebook)

```
Fan-out on Write:
User posts → Push to all followers' feeds
✅ Fast reads
❌ Slow writes, storage overhead
→ Good for: Normal users

Fan-out on Read:
User opens feed → Pull from followed users
✅ Fast writes
❌ Slow reads
→ Good for: Celebrities (millions of followers)

Hybrid:
- Fan-out on write para usuarios normales
- Fan-out on read para celebrities
- Pre-compute feeds en background

Timeline Cache:
user_id → [tweet_id_1, tweet_id_2, ...]
            │
            ▼
      Tweet Cache
tweet_id → {content, author, created_at, ...}
```

---

## Números a Memorizar

```
Latency:
- L1 cache: 0.5 ns
- L2 cache: 7 ns
- RAM: 100 ns
- SSD random read: 150 μs
- HDD random read: 10 ms
- Network round-trip (same DC): 500 μs
- Network round-trip (cross DC): 150 ms

Throughput:
- SSD sequential: 1 GB/s
- HDD sequential: 100 MB/s
- 1 Gbps network: 125 MB/s
- 10 Gbps network: 1.25 GB/s

Availability:
- 99%: 3.65 días/año downtime
- 99.9%: 8.76 horas/año
- 99.99%: 52.6 min/año
- 99.999%: 5.26 min/año

Scale:
- 1 server: ~10K concurrent connections
- Redis: ~100K ops/s
- PostgreSQL: ~10K queries/s
- Kafka: ~1M messages/s
```

---

## CAP Theorem

```
C - Consistency: Todos ven los mismos datos
A - Availability: Sistema siempre responde
P - Partition Tolerance: Funciona con fallos de red

Solo puedes elegir 2 de 3:

CP Systems (Consistency + Partition):
- MongoDB, HBase, Redis Cluster
- Sacrifica: Availability durante partición
- Use case: Transacciones financieras

AP Systems (Availability + Partition):
- Cassandra, DynamoDB, CouchDB
- Sacrifica: Consistency temporal
- Use case: Social media, IoT

CA Systems (sin Partition Tolerance):
- RDBMS single-node
- No existe en sistemas distribuidos reales
```

---

## Referencias

- **Libro:** "Designing Data-Intensive Applications" - Martin Kleppmann
- **GitHub:** https://github.com/donnemartin/system-design-primer
- **Blog:** https://highscalability.com/

---

*Skill: system-design-at-scale v1.0*
