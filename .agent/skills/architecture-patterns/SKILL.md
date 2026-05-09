---
name: architecture-patterns
description: Software architecture patterns. Domain-Driven Design, Hexagonal architecture, Event Sourcing, CQRS, microservices, system design.
category: architecture
tags: [architecture, ddd, hexagonal, event-sourcing, cqrs, microservices, system-design]
version: 1.0.0
type: feature
---

# Architecture Patterns

> Design systems that scale, evolve, and don't collapse under their own weight.
> **Architecture is for humans, not computers.**

---

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `domain-driven-design.md` | Ubiquitous language, bounded contexts, aggregates | Modeling complex business logic |
| `hexagonal.md` | Ports & adapters, dependency inversion | Clean, testable architecture |
| `event-sourcing.md` | Event store, temporal queries, audit trails | Audit-critical systems |
| `cqrs.md` | Command/Query separation, eventual consistency | Complex read/write patterns |
| `microservices.md` | Service boundaries, inter-service communication | Distributed systems |
| `system-design.md` | API design, data flow, scalability analysis | Interviewing, big picture |
| `data-consistency.md` | Strong vs eventual consistency, conflict resolution | Distributed data |
| `patterns-comparison.md` | Decision trees for architecture choices | Starting new system |

---

## 🔗 Related Skills

| Need | Skill |
|------|-------|
| Database design | `@[skills/database-design]` |
| API patterns | `@[skills/api-patterns]` |
| DevOps/Scaling | `@[skills/devops-advanced]` |
| Data engineering | `@[skills/data-engineering]` |

---

## ✅ Architecture Design Checklist

Before building a system:

- [ ] **Core business logic identified?** (domain model)
- [ ] **Bounded contexts defined?** (DDD)
- [ ] **External dependencies identified?** (ports)
- [ ] **Data consistency model chosen?** (strong vs eventual)
- [ ] **Scalability hotspots identified?** (database, cache, compute)
- [ ] **Failure modes considered?** (cascade failures, single points of failure)
- [ ] **Deployment strategy defined?** (monolith vs microservices)
- [ ] **Monitoring/observability planned?**
- [ ] **Disaster recovery designed?**
- [ ] **Team structure aligned with architecture?** (Conway's Law)

---

## Architecture Decision Tree

```
┌─ Is business logic complex?
│  ├─ YES (many rules, workflows)
│  │  └─ Use DDD with bounded contexts
│  └─ NO (CRUD operations)
│     └─ Simple layered architecture
│
├─ Do you have clear read/write patterns?
│  ├─ YES (reads >> writes, denormalization needed)
│  │  └─ Consider CQRS + Event Sourcing
│  └─ NO (balanced read/write)
│     └─ Traditional CRUD
│
├─ Do teams need independent deployment?
│  ├─ YES
│  │  └─ Microservices (cost tradeoff!)
│  └─ NO
│     └─ Monolith (simpler!)
│
└─ Need audit trail of all changes?
   ├─ YES
   │  └─ Event Sourcing
   └─ NO
      └─ State-based storage
```

---

## Domain-Driven Design

### Bounded Contexts
```
┌─────────────────────────┐
│   E-commerce System     │
│                         │
│ ┌────────────────────┐  │
│ │ Order Context      │  │  Manages order creation,
│ │                    │  │  fulfillment workflow
│ │ Entities:          │  │
│ │ - Order            │  │
│ │ - OrderItem        │  │
│ └────────────────────┘  │
│                         │
│ ┌────────────────────┐  │
│ │ Inventory Context  │  │  Manages stock, reservations
│ │                    │  │
│ │ Entities:          │  │
│ │ - Product          │  │
│ │ - Stock            │  │
│ └────────────────────┘  │
│                         │
│ ┌────────────────────┐  │
│ │ Payment Context    │  │  Handles payments,
│ │                    │  │  refunds, reconciliation
│ │ Entities:          │  │
│ │ - Payment          │  │
│ │ - Transaction      │  │
│ └────────────────────┘  │
│                         │
└─────────────────────────┘
```

### Aggregate Pattern
```typescript
// Order aggregate root
class Order {
  private id: OrderId;
  private items: OrderItem[];
  private status: OrderStatus;
  private createdAt: Date;

  // Business invariants enforced HERE
  addItem(product: Product, qty: number) {
    if (this.status !== OrderStatus.DRAFT) {
      throw new OrderAlreadySubmittedError();
    }
    if (qty <= 0) {
      throw new InvalidQuantityError();
    }
    this.items.push(new OrderItem(product, qty));
  }

  submit() {
    if (this.items.length === 0) {
      throw new CannotSubmitEmptyOrder();
    }
    this.status = OrderStatus.SUBMITTED;
    this.raiseEvent(new OrderSubmittedEvent(this.id, this.items));
  }
}
```

---

## Hexagonal Architecture (Ports & Adapters)

```
        ┌──────────────────┐
        │  User Interface  │
        │   (Web, CLI)     │
        └────────┬─────────┘
                 │ HTTP/gRPC
        ┌────────▼─────────┐
        │   Input Adapter  │
        └────────┬─────────┘
                 │
        ┌────────▼──────────────────────┐
        │   Application Core            │
        │                               │
        │  Business Logic (Domain)      │
        │  - Use Cases                  │
        │  - Entities                   │
        │  - Aggregates                 │
        └────────┬──────────────────────┘
                 │
     ┌───────────┴──────────┐
     │                      │
┌────▼────────┐    ┌────────▼───────┐
│Persistence  │    │Notification    │
│Adapter      │    │Adapter         │
│             │    │                │
│PostgreSQL   │    │Email, Webhooks │
└─────────────┘    └────────────────┘
```

---

## Event Sourcing

### Event Store Pattern
```
append(OrderCreated(id=123, customer=john, items=[...]))
append(OrderItemAdded(id=123, product=abc, qty=2))
append(OrderSubmitted(id=123, total=$45.99))
append(OrderPaid(id=123, method=cc))
append(OrderShipped(id=123, tracking=ABC123))
```

### Event Sourcing vs Traditional State

| Aspect | Event Sourcing | State-based |
|--------|----------------|------------|
| Storage | All events | Current state |
| Audit trail | Free (events are audit trail) | Requires separate logs |
| Temporal queries | Natural (replay events) | Complex (requires versioning) |
| Scalability | Read model can be scaled | Must scale storage |
| Testing | Event-driven is clear | Mocking state is complex |
| Complexity | Higher initial | Lower initial |

---

## CQRS (Command Query Responsibility Segregation)

```
Commands (Write)
  ↓
Event Store
  ↓
Read Models (denormalized)
  ↓
Queries (Read)

Advantages:
- Optimize reads independently
- Complex queries don't slow writes
- Eventual consistency OK
- Natural event sourcing fit
```

---

## Microservices Boundaries

### Anti-patterns (DON'T DO)
- One class per microservice (too granular)
- Microservice per developer (unmanageable)
- Circular dependencies between services
- Shared databases between services
- Synchronous calls across boundaries

### Good Boundaries
```
Team Ownership = Service Boundary

Teams:
- Order Team  → Order Service
- Billing Team → Billing Service
- Shipping Team → Shipping Service

Async communication (events)
Independent deployments
Separate databases
```

---

## System Design Framework

### Requirements Phase
```
Functional Requirements
  - What does the system do?
  - What are the core features?

Non-Functional Requirements
  - Scalability (QPS, data volume)
  - Latency (p99, p95)
  - Availability (uptime %)
  - Consistency (strong vs eventual)
```

### Back-of-Envelope Calculations
```
Example: Twitter-like system
- 500 million users
- 100 million daily active users
- 1000 tweets/second average (peak 10k/sec)
- 100 days data retention

Storage per tweet: 200 bytes
Daily tweets: 1000 * 86400 = 86M tweets
Daily storage: 86M * 200 = 17GB
100-day storage: 1.7TB + replication
```

### Bottleneck Analysis
```
Read-heavy (Twitter feed)
  → Cache, denormalize, CDN

Write-heavy (Event logging)
  → Message queue, batching, sharding

Large objects (Video)
  → Object storage, CDN, streaming
```

---

## ❌ Anti-Patterns

**DON'T:**
- Design for scale that doesn't exist
- Prematurely optimize
- Microservices when monolith works
- Ignore data consistency requirements
- Synchronous calls for async operations
- Shared mutable state in distributed system
- Assume success (plan for failures)
- Architecture without domain understanding
- Ignore team structure (Conway's Law)
- Design alone (get reviews!)

**DO:**
- Start simple (YAGNI)
- Measure before optimizing
- Monolith first, then if needed, split
- Understand business requirements deeply
- Async communication between boundaries
- Event sourcing for audit/temporal queries
- Design for failure scenarios
- Co-design with domain experts
- Align architecture with team structure
- Get architecture reviews

---

## Common Patterns Summary

| Pattern | Problem | Solution | Trade-off |
|---------|---------|----------|-----------|
| Layered | Monolithic coupling | Organize by layer | Can't scale independently |
| Hexagonal | Dependency injection | Ports & adapters | More boilerplate |
| Event Sourcing | Audit trail | Store all events | Complex queries, storage |
| CQRS | Mixed read/write patterns | Separate models | Eventual consistency |
| Microservices | Team independence | Service per team | Network complexity |
| Domain-Driven Design | Complex business logic | Bounded contexts | Requires domain expertise |

---

## Script

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/architecture_analyzer.py` | Analyze codebase architecture | `python scripts/architecture_analyzer.py --project <path>` |
| `scripts/ddd_context_mapper.py` | Map bounded contexts | `python scripts/ddd_context_mapper.py --config contexts.yaml` |
| `scripts/system_design_calculator.py` | Calculate system capacity | `python scripts/system_design_calculator.py --qps 10000 --latency-p99 500` |
