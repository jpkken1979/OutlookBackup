---
name: event-sourcing-architect
description: "Expert in event sourcing and CQRS architecture patterns for building scalable, auditable systems. Covers event store design, aggregate boundaries, event versioning, projections, saga orchestration, eventual consistency, snapshotting, temporal queries, and event-driven microservices. Includes patterns for bank transactions, order workflows, inventory management, and distributed sagas with compensating actions. Handles schema evolution, idempotent handlers, correlation IDs, and rebuilding projections. Use when building systems requiring complete audit trails, implementing complex workflows, enabling undo/redo, separating read/write models, building event-driven microservices, or supporting temporal queries (\"what was state at time X\")."
type: feature
---

# Event Sourcing & CQRS Architecture

Master event sourcing and CQRS patterns for building scalable, auditable systems with complete temporal awareness.

## Core Concept: Event Sourcing vs Traditional CRUD

### Traditional CRUD (Current State Only)

```
User Table: id=1, name="Alice", balance=500, updated_at=2024-01-15T10:00:00Z

Problems:
- Lost history (why did balance change?)
- Can't audit who changed what
- Can't ask "what was balance on Jan 14?"
- Concurrent updates cause conflicts
```

### Event Sourcing (Complete History)

```
Event Log:
1. UserCreated(id=1, name="Alice", balance=1000) @ 2024-01-01T10:00:00Z
2. MoneyDeposited(id=1, amount=500) @ 2024-01-15T10:00:00Z
3. MoneyWithdrawn(id=1, amount=200) @ 2024-01-15T10:05:00Z

Current state = replay all events = balance=1300

Benefits:
✓ Complete audit trail
✓ Can query "what was state at time X"
✓ Can rebuild/fix projections
✓ Enables undo/redo
✓ Temporal debugging
```

## Pattern 1: Event Store Design

### Event Structure

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class Event:
    """Immutable event stored in event log."""

    event_id: str                    # UUID
    event_type: str                  # "UserCreated", "MoneyDeposited"
    aggregate_id: str                # Which user/order/product
    aggregate_type: str              # "User", "Order", "Product"
    data: dict                       # Event payload
    metadata: dict                   # correlation_id, user_id, timestamp
    version: int                     # Version of event schema
    timestamp: datetime              # When event occurred
    committed_at: datetime           # When stored
```

### Example Events

```python
# Event 1: Order created
UserCreated = {
    "event_type": "user.created",
    "aggregate_id": "user_123",
    "aggregate_type": "User",
    "data": {
        "name": "Alice",
        "email": "alice@example.com",
        "initial_balance": 1000
    },
    "version": 1,
    "timestamp": "2024-01-01T10:00:00Z"
}

# Event 2: Money deposited
MoneyDeposited = {
    "event_type": "user.money_deposited",
    "aggregate_id": "user_123",
    "aggregate_type": "User",
    "data": {
        "amount": 500,
        "source": "bank_transfer"
    },
    "version": 1,
    "timestamp": "2024-01-15T10:00:00Z"
}

# Event 3: Money withdrawn
MoneyWithdrawn = {
    "event_type": "user.money_withdrawn",
    "aggregate_id": "user_123",
    "aggregate_type": "User",
    "data": {
        "amount": 200,
        "destination": "wallet"
    },
    "version": 1,
    "timestamp": "2024-01-15T10:05:00Z"
}
```

## Pattern 2: Aggregate & Aggregate Root

```python
class User:
    """Aggregate root - boundary for consistency."""

    def __init__(self, user_id: str):
        self.id = user_id
        self.name: str | None = None
        self.balance: float = 0
        self.version = 0
        self.uncommitted_events = []

    # Commands (requests to change state)
    def create_user(self, name: str, initial_balance: float):
        """Create new user."""
        self._apply_event({
            "event_type": "user.created",
            "name": name,
            "initial_balance": initial_balance
        })

    def deposit_money(self, amount: float):
        """Deposit money."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        self._apply_event({
            "event_type": "user.money_deposited",
            "amount": amount
        })

    def withdraw_money(self, amount: float):
        """Withdraw money."""
        if self.balance < amount:
            raise ValueError("Insufficient balance")

        self._apply_event({
            "event_type": "user.money_withdrawn",
            "amount": amount
        })

    # Event Handlers (apply events to state)
    def _apply_event(self, event_data: dict):
        """Apply event and record for persistence."""
        event_type = event_data["event_type"]

        if event_type == "user.created":
            self.name = event_data["name"]
            self.balance = event_data["initial_balance"]

        elif event_type == "user.money_deposited":
            self.balance += event_data["amount"]

        elif event_type == "user.money_withdrawn":
            self.balance -= event_data["amount"]

        # Record event for persistence
        self.version += 1
        self.uncommitted_events.append({
            **event_data,
            "aggregate_id": self.id,
            "version": self.version
        })

    @staticmethod
    def from_history(user_id: str, events: list[dict]) -> "User":
        """Rebuild aggregate from event history."""
        user = User(user_id)
        for event in events:
            user._apply_event(event)
        user.uncommitted_events = []  # Clear after rebuild
        return user
```

## Pattern 3: CQRS (Command Query Responsibility Segregation)

### Separate Write & Read Models

```python
# WRITE MODEL (Event Sourced)
class UserWriteService:
    """Handles commands, updates event store."""

    def __init__(self, event_store):
        self.event_store = event_store

    def create_user(self, user_id: str, name: str, balance: float):
        """Command: Create user."""
        user = User(user_id)
        user.create_user(name, balance)

        # Save events to event store
        self.event_store.append_events(user.id, user.uncommitted_events)

    def deposit_money(self, user_id: str, amount: float):
        """Command: Deposit money."""
        # Load aggregate from history
        events = self.event_store.get_events(user_id)
        user = User.from_history(user_id, events)

        # Apply command
        user.deposit_money(amount)

        # Save new events
        self.event_store.append_events(user.id, user.uncommitted_events)


# READ MODEL (Optimized for queries)
class UserReadModel:
    """Denormalized view for fast queries."""

    def __init__(self, database):
        self.db = database

    def get_user_balance(self, user_id: str) -> float:
        """Query: Get user balance (from read model, not event store)."""
        row = self.db.query("SELECT balance FROM user_view WHERE id = ?", user_id)
        return row["balance"] if row else 0


# PROJECTION (Updates read model from events)
class UserProjection:
    """Subscribes to events, updates read model."""

    def __init__(self, event_store, read_db):
        self.event_store = event_store
        self.read_db = read_db
        self.last_processed_position = 0

    def handle_events(self):
        """Process new events and update read model."""
        events = self.event_store.get_events_since(self.last_processed_position)

        for event in events:
            if event["event_type"] == "user.created":
                self.read_db.insert("user_view", {
                    "id": event["aggregate_id"],
                    "name": event["data"]["name"],
                    "balance": event["data"]["initial_balance"]
                })

            elif event["event_type"] == "user.money_deposited":
                self.read_db.update("user_view",
                    {"balance": balance + event["data"]["amount"]},
                    where={"id": event["aggregate_id"]}
                )

            elif event["event_type"] == "user.money_withdrawn":
                self.read_db.update("user_view",
                    {"balance": balance - event["data"]["amount"]},
                    where={"id": event["aggregate_id"]}
                )

            self.last_processed_position = event["position"]
```

## Pattern 4: Eventual Consistency & Saga Pattern

### Distributed Transaction with Saga

```python
# Problem: Transfer money between users (different aggregates)
# Can't use traditional transaction (not ACID)
# Solution: Saga (choreography or orchestration)

# ORCHESTRATION PATTERN (Central coordinator)
class TransferSaga:
    """Coordinated saga for money transfer."""

    def __init__(self, write_service, event_bus):
        self.write_service = write_service
        self.event_bus = event_bus

    def transfer_money(self, from_user_id: str, to_user_id: str, amount: float):
        """Transfer money with compensating actions."""
        try:
            # Step 1: Withdraw from source
            self.write_service.withdraw_money(from_user_id, amount)

            # Step 2: Deposit to destination
            self.write_service.deposit_money(to_user_id, amount)

        except Exception as e:
            # Compensating action: Revert withdrawal
            self.write_service.deposit_money(from_user_id, amount)
            raise

# CHOREOGRAPHY PATTERN (Event-driven)
class UserEventHandlers:
    """React to events without central coordinator."""

    def __init__(self, write_service, event_bus):
        self.write_service = write_service
        self.event_bus = event_bus

        # Subscribe to events
        event_bus.subscribe("transfer.requested", self.handle_transfer_requested)
        event_bus.subscribe("transfer.withdrawn", self.handle_transfer_withdrawn)
        event_bus.subscribe("transfer.failed", self.handle_transfer_failed)

    def handle_transfer_requested(self, event):
        """Step 1: Withdraw from source."""
        try:
            self.write_service.withdraw_money(event["from_user_id"], event["amount"])
            self.event_bus.publish({
                "event_type": "transfer.withdrawn",
                "from_user_id": event["from_user_id"],
                "to_user_id": event["to_user_id"],
                "amount": event["amount"]
            })
        except Exception as e:
            self.event_bus.publish({
                "event_type": "transfer.failed",
                "reason": str(e)
            })

    def handle_transfer_withdrawn(self, event):
        """Step 2: Deposit to destination."""
        try:
            self.write_service.deposit_money(event["to_user_id"], event["amount"])
        except Exception:
            # Compensating action
            self.write_service.deposit_money(event["from_user_id"], event["amount"])
```

## Pattern 5: Event Versioning & Schema Evolution

```python
# Version 1: Original event structure
UserCreatedV1 = {
    "event_type": "user.created",
    "version": 1,
    "data": {
        "name": "Alice",
        "email": "alice@example.com"
    }
}

# Version 2: Added phone field (backward compatible)
UserCreatedV2 = {
    "event_type": "user.created",
    "version": 2,
    "data": {
        "name": "Alice",
        "email": "alice@example.com",
        "phone": "+1234567890"  # New field
    }
}

# Handle both versions in event handler
def handle_user_created(event):
    """Handle user.created event (any version)."""
    data = event["data"]
    version = event.get("version", 1)

    if version == 1:
        # V1: name + email
        user = create_user(data["name"], data["email"])

    elif version == 2:
        # V2: name + email + phone
        user = create_user(data["name"], data["email"], phone=data.get("phone"))

    return user

# Upcasting: Upgrade V1 events to V2 when rebuilding
def upcast_event(event):
    """Upgrade event to latest version."""
    if event["event_type"] == "user.created" and event["version"] == 1:
        return {
            **event,
            "version": 2,
            "data": {
                **event["data"],
                "phone": None  # Default value
            }
        }
    return event
```

## Pattern 6: Snapshotting (Performance Optimization)

```python
class SnapshotStore:
    """Store snapshots to avoid replaying all events."""

    def __init__(self, event_store, db):
        self.event_store = event_store
        self.db = db

    def load_aggregate(self, aggregate_id: str, aggregate_type: str):
        """Load aggregate with snapshot optimization."""

        # Check for recent snapshot
        snapshot = self.db.query(
            "SELECT * FROM snapshots WHERE aggregate_id = ? ORDER BY version DESC LIMIT 1",
            aggregate_id
        )

        if snapshot:
            # Rebuild from snapshot + events after snapshot
            aggregate = self._restore_from_snapshot(snapshot)
            events = self.event_store.get_events_since(
                aggregate_id,
                snapshot["version"]
            )
        else:
            # Rebuild from all events
            aggregate = None
            events = self.event_store.get_events(aggregate_id)

        # Apply events to get current state
        for event in events:
            aggregate._apply_event(event)

        return aggregate

    def save_snapshot(self, aggregate_id: str, aggregate):
        """Save snapshot periodically."""
        self.db.insert("snapshots", {
            "aggregate_id": aggregate_id,
            "version": aggregate.version,
            "state": json.dumps(aggregate.__dict__),
            "created_at": datetime.now()
        })

    # Snapshot every 100 events
    def maybe_snapshot(self, aggregate_id: str, version: int):
        if version % 100 == 0:
            aggregate = self.load_aggregate(aggregate_id)
            self.save_snapshot(aggregate_id, aggregate)
```

## Pattern 7: Temporal Queries (Time-Travel)

```python
class TemporalQueries:
    """Query state at any point in time."""

    def __init__(self, event_store):
        self.event_store = event_store

    def get_balance_at_time(self, user_id: str, timestamp: datetime) -> float:
        """Get user balance as of specific time."""
        events = self.event_store.get_events(user_id)

        # Filter events before timestamp
        relevant_events = [e for e in events if e["timestamp"] <= timestamp]

        # Replay to get state at that time
        user = User(user_id)
        for event in relevant_events:
            user._apply_event(event)

        return user.balance

    def get_audit_trail(self, user_id: str) -> list:
        """Get complete history of all changes."""
        events = self.event_store.get_events(user_id)

        return [
            {
                "timestamp": e["timestamp"],
                "event_type": e["event_type"],
                "description": self._describe_event(e),
                "data": e["data"]
            }
            for e in events
        ]

    def _describe_event(self, event):
        if event["event_type"] == "user.created":
            return f"User created with {event['data']['initial_balance']}"
        elif event["event_type"] == "user.money_deposited":
            return f"Deposited {event['data']['amount']}"
        elif event["event_type"] == "user.money_withdrawn":
            return f"Withdrew {event['data']['amount']}"
```

## Best Practices & Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Events are immutable** | Audit trail, no rewrites | Never UPDATE/DELETE events |
| **Events are facts** | Describe what happened | "MoneyDeposited" not "BalanceIncremented" |
| **Version events** | Handle schema evolution | Include `version` field |
| **Idempotent handlers** | Replay safety | Use correlation IDs to deduplicate |
| **Correlation IDs** | Trace distributed flows | UUID per request, include in all events |
| **Rebuild projections** | Fix bugs in read model | Don't fix events, rebuild projections |
| **Snapshots** | Performance | Snapshot every N events |
| **Event store backup** | Data safety | Regular backups like database |
| **Monitor projection lag** | Eventual consistency gaps | Alert if read model > 5s behind writes |

## Implementation Checklist

- [ ] **Define events as immutable facts**: No mutations, only appends
- [ ] **Design aggregate boundaries**: Clear ownership of entities
- [ ] **Implement command handlers**: Validate, apply events
- [ ] **Build projections**: Denormalized views for queries
- [ ] **Version events**: Plan for schema evolution
- [ ] **Implement snapshotting**: For long-lived aggregates
- [ ] **Setup correlation IDs**: For distributed tracing
- [ ] **Implement idempotent handlers**: Replay safety
- [ ] **Monitor projection lag**: Watch eventual consistency
- [ ] **Test temporal queries**: Verify time-travel works
- [ ] **Document event schema**: Events are API contract
- [ ] **Plan event versioning**: Version 2 from day 1

## Common Pitfalls

| ❌ Pitfall | ✅ Fix |
|-----------|-------|
| **Deleting events** | Never delete; only archive |
| **Mutable event data** | Events are immutable facts |
| **Missing event version** | Version all events from v1 |
| **No correlation IDs** | Use UUID per request |
| **Projection rebuilding** | Keep event store, rebuild projections |
| **Assuming strong consistency** | Design for eventual consistency |
| **Large aggregates** | Split into smaller aggregates |
