# ShuMobile PWA Backend Sync Module

## Overview

The `shu_pwa_sync` module provides backend synchronization for the ShuMobile Progressive Web App (PWA). It manages persistent storage of user session responses via SQLite, with support for offline queueing, response merging, and session lifecycle management.

## Architecture

```
┌──────────────────────────────────────────┐
│         ShuMobile PWA Frontend           │
│      (Service Worker + IndexedDB)        │
└──────────────┬───────────────────────────┘
               │ (POST /v1/shu/pwa_sync)
               ▼
┌──────────────────────────────────────────┐
│   Gateway Handler (to be implemented)    │
│   └── Validates session_id & responses   │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│         ShuPWASync Service               │
│  ├── async_sync_responses()              │
│  ├── async_get_sessions()                │
│  ├── async_get_session()                 │
│  ├── async_create_session()              │
│  ├── async_get_offline_queue()           │
│  └── async_delete_session()              │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  SQLite Database (~/.antigravity/       │
│             pwa_sessions.db)             │
│                                          │
│  Table: pwa_sessions                     │
│  ├── session_id (PK)                     │
│  ├── goal_id                             │
│  ├── responses (JSON)                    │
│  ├── status (draft|submitted)            │
│  ├── created_at, synced_at, updated_at   │
│  └── Indices on (status, goal_id)        │
└──────────────────────────────────────────┘
```

## API Reference

### ShuPWASync Class

Main service class for managing PWA session synchronization.

#### Constructor

```python
sync_service = ShuPWASync(db_path: Optional[Path] = None)
```

**Parameters:**
- `db_path`: Optional path to SQLite database (defaults to `~/.antigravity/pwa_sessions.db`)

**Raises:**
- `ValueError`: If database initialization fails

#### Methods

##### `async_sync_responses(session_id: str, responses: dict[str, str]) -> dict[str, Any]`

Synchronize PWA responses to backend goal tracking. Merges new responses with existing ones.

**Parameters:**
- `session_id`: Unique session identifier (UUID)
- `responses`: Dictionary mapping dimension names to string answers
  - Example: `{"energy_level": "good", "mood": "positive", "sleep_hours": "8"}`

**Returns:**
```python
{
    "status": "success",
    "synced_to_goal": "goal_id_uuid"
}
```

**Errors:**
- Invalid `session_id`: `{"status": "error", "error": "Invalid session_id"}`
- Empty `responses`: `{"status": "error", "error": "Invalid responses"}`
- Session not found: `{"status": "error", "error": "Session <id> not found"}`
- Database error: `{"status": "error", "error": "Database error: ..."}`

**Behavior:**
- Creates session entry if missing (on error, does not auto-create)
- Merges responses: new values override existing ones for same key
- Sets status to "submitted"
- Updates `synced_at` timestamp

---

##### `async_get_sessions(status: Optional[Literal["draft", "submitted"]] = None) -> list[dict[str, Any]]`

Retrieve sessions, optionally filtered by status.

**Parameters:**
- `status`: Optional filter (`"draft"` | `"submitted"` | `None` for all)

**Returns:**
```python
[
    {
        "session_id": "uuid",
        "goal_id": "uuid",
        "responses": {"dim1": "ans1", "dim2": "ans2"},
        "status": "draft",
        "created_at": "2026-06-16T10:30:00",
        "synced_at": None
    },
    ...
]
```

**Raises:**
- `sqlite3.DatabaseError`: If query fails

---

##### `async_get_session(session_id: str) -> Optional[dict[str, Any]]`

Retrieve a specific session by ID.

**Parameters:**
- `session_id`: Unique session identifier

**Returns:**
```python
{
    "session_id": "uuid",
    "goal_id": "uuid",
    "responses": {"dim1": "ans1"},
    "status": "submitted",
    "created_at": "2026-06-16T10:30:00",
    "synced_at": "2026-06-16T10:35:00"
}
```

Returns `None` if session not found.

**Raises:**
- `sqlite3.DatabaseError`: If query fails

---

##### `async_create_session(session_id: str, goal_id: str, initial_responses: Optional[dict[str, str]] = None) -> dict[str, Any]`

Create a new PWA session.

**Parameters:**
- `session_id`: Unique session ID (recommend UUID4)
- `goal_id`: Goal being tracked
- `initial_responses`: Optional initial response data

**Returns:**
```python
{
    "status": "success",
    "session_id": "uuid",
    "goal_id": "uuid"
}
```

**Errors:**
- Duplicate session: `{"status": "error", "error": "Session already exists"}`
- Invalid inputs: `{"status": "error", "error": "Invalid session_id|goal_id"}`
- Database error: `{"status": "error", "error": "Database error: ..."}`

---

##### `async_get_offline_queue() -> list[dict[str, Any]]`

Retrieve all sessions in draft status (offline queue waiting for sync).

**Returns:**
```python
[
    {
        "session_id": "uuid",
        "goal_id": "uuid",
        "responses": {},
        "status": "draft",
        "created_at": "2026-06-16T10:30:00",
        "synced_at": None
    },
    ...
]
```

**Raises:**
- `sqlite3.DatabaseError`: If query fails

---

##### `async_delete_session(session_id: str) -> dict[str, Any]`

Delete a session by ID.

**Parameters:**
- `session_id`: Unique session identifier

**Returns:**
```python
{
    "status": "success",
    "session_id": "uuid"
}
```

**Errors:**
- Session not found: `{"status": "error", "error": "Session not found"}`
- Database error: `{"status": "error", "error": "Database error: ..."}`

---

### Singleton Pattern

```python
from .agent.core.shu_pwa_sync import get_pwa_sync

# Get the singleton instance
sync_service = get_pwa_sync(db_path=None)

# Subsequent calls return the same instance
sync_service2 = get_pwa_sync()
assert sync_service is sync_service2
```

---

## Data Model: ShuPWASession

Dataclass representing a PWA session.

```python
@dataclass
class ShuPWASession:
    session_id: str                           # UUID
    goal_id: str                              # UUID
    created_at: datetime                      # Creation timestamp
    responses: dict[str, str] = {}            # Dimension -> answer
    status: Literal["draft", "submitted"] = "draft"
    synced_at: Optional[datetime] = None      # Last sync timestamp
```

---

## Database Schema

### Table: `pwa_sessions`

```sql
CREATE TABLE pwa_sessions (
    session_id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    responses TEXT NOT NULL,                  -- JSON-encoded dict
    status TEXT NOT NULL DEFAULT 'draft',     -- "draft" | "submitted"
    created_at TEXT NOT NULL,                 -- ISO-8601 timestamp
    synced_at TEXT,                           -- ISO-8601 timestamp (nullable)
    updated_at TEXT NOT NULL                  -- Automatic on update
);

CREATE INDEX idx_pwa_status ON pwa_sessions(status);
CREATE INDEX idx_pwa_goal ON pwa_sessions(goal_id);
```

---

## Usage Examples

### Example 1: Create and Sync Session

```python
import asyncio
import uuid
from pathlib import Path
from agent.core.shu_pwa_sync import ShuPWASync

async def example_create_and_sync():
    sync = ShuPWASync()
    
    # Create session
    session_id = str(uuid.uuid4())
    goal_id = str(uuid.uuid4())
    
    create_result = await sync.async_create_session(
        session_id,
        goal_id,
        initial_responses={"initial": "data"}
    )
    print(f"Created: {create_result}")
    
    # Sync additional responses
    sync_result = await sync.async_sync_responses(
        session_id,
        {"energy_level": "good", "mood": "positive"}
    )
    print(f"Synced: {sync_result}")
    
    # Retrieve session
    session = await sync.async_get_session(session_id)
    print(f"Session: {session}")

asyncio.run(example_create_and_sync())
```

### Example 2: Offline Queue Management

```python
async def example_offline_queue():
    sync = ShuPWASync()
    
    # Get all sessions waiting for sync
    offline_sessions = await sync.async_get_offline_queue()
    print(f"Pending sync: {len(offline_sessions)} sessions")
    
    for session in offline_sessions:
        # Attempt to sync
        result = await sync.async_sync_responses(
            session["session_id"],
            session["responses"]
        )
        if result["status"] == "success":
            print(f"Synced {session['session_id']}")

asyncio.run(example_offline_queue())
```

### Example 3: Filter Sessions by Status

```python
async def example_filter_sessions():
    sync = ShuPWASync()
    
    # Get draft sessions (pending sync)
    drafts = await sync.async_get_sessions(status="draft")
    print(f"Draft: {len(drafts)}")
    
    # Get submitted sessions
    submitted = await sync.async_get_sessions(status="submitted")
    print(f"Submitted: {len(submitted)}")
    
    # Get all
    all_sessions = await sync.async_get_sessions()
    print(f"Total: {len(all_sessions)}")

asyncio.run(example_filter_sessions())
```

---

## Error Handling

All methods include comprehensive error handling:

1. **Invalid Input Validation:**
   - Empty or non-string `session_id` / `goal_id`
   - Non-dict or empty `responses`
   - Returns `{"status": "error", ...}` instead of raising

2. **Database Errors:**
   - Caught as `sqlite3.DatabaseError` or raised if critical
   - Logged with context (session_id, operation)
   - Clear error messages in response

3. **Conflict Detection:**
   - Duplicate session creation prevented
   - Returns `{"status": "error", "error": "Session already exists"}`

4. **Logging:**
   - All operations logged at INFO level (sync, create, delete)
   - Errors logged at ERROR level with context
   - Debug info at DEBUG level (retrieved count, etc.)

---

## Integration with Gateway (Next Step)

The HTTP endpoint integration will:

```python
# In gateway.py (to be implemented)

@app.post("/v1/shu/pwa_sync")
async def pwa_sync_handler(request: web.Request) -> web.Response:
    """Handle PWA session synchronization requests."""
    try:
        body = await request.json()
        session_id = body.get("session_id")
        responses = body.get("responses")
        
        # Validate inputs
        if not session_id or not responses:
            return web.json_response(
                {"status": "error", "error": "Missing session_id or responses"},
                status=400
            )
        
        # Sync via service
        sync = get_pwa_sync()
        result = await sync.async_sync_responses(session_id, responses)
        
        # Log
        logger.info(f"PWA sync: session={session_id}, responses={len(responses)}")
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"PWA sync error: {e}")
        return web.json_response(
            {"status": "error", "error": str(e)},
            status=500
        )
```

---

## Testing

Run tests:

```bash
pytest tests/core/test_shu_pwa_sync.py -v
```

Test coverage includes:
- Normal sync operations
- Offline queue handling
- Session retrieval and filtering
- Conflict detection
- Idempotent operations
- Response merging
- Session deletion
- Database integrity

---

## Notes

- **Timestamps:** All datetimes stored and returned as ISO-8601 UTC
- **JSON Storage:** Responses stored as JSON in SQLite (TEXT type)
- **Idempotent:** Syncing same responses multiple times is safe
- **Merge Strategy:** New responses override existing keys (last-write-wins)
- **No Auth:** Session data is unencrypted in SQLite; add encryption layer if handling sensitive data
- **Path Handling:** Uses `ANTIGRAVITY_ROOT` env var when available, falls back to `~/.antigravity/`

---

## Environment Variables

- `ANTIGRAVITY_ROOT`: Base directory for `.antigravity/` config (defaults to `$HOME`)

---

## Related Files

- **Module:** `.agent/core/shu_pwa_sync.py`
- **Tests:** `tests/core/test_shu_pwa_sync.py`
- **Gateway Integration:** (to be implemented in gateway.py)
- **Frontend PWA:** (integrates via `/v1/shu/pwa_sync` endpoint)
