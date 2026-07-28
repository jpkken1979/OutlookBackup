# ShuMobile PWA Sync — Quick Reference

## HTTP Endpoint (When Implemented)

```
POST /v1/shu/pwa_sync
Content-Type: application/json

{
  "session_id": "uuid-string",
  "responses": {
    "dimension_name": "answer"
  }
}
```

---

## Python API (Direct Use)

### Import

```python
from agent.core.shu_pwa_sync import ShuPWASync, get_pwa_sync
import asyncio
import uuid
```

### Quick Start

```python
async def main():
    # Get singleton instance
    sync = get_pwa_sync()
    
    # Create session
    session_id = str(uuid.uuid4())
    goal_id = str(uuid.uuid4())
    
    create_result = await sync.async_create_session(
        session_id, goal_id, 
        initial_responses={"initial": "data"}
    )
    # Returns: {"status": "success", "session_id": "...", "goal_id": "..."}
    
    # Sync responses
    sync_result = await sync.async_sync_responses(
        session_id,
        {"energy": "good", "mood": "positive"}
    )
    # Returns: {"status": "success", "synced_to_goal": "..."}
    
    # Get session
    session = await sync.async_get_session(session_id)
    print(session)
    # Returns: {
    #   "session_id": "...",
    #   "goal_id": "...",
    #   "responses": {"energy": "good", "mood": "positive"},
    #   "status": "submitted",
    #   "synced_at": "2026-06-16T10:35:00"
    # }
    
    # List all sessions
    all_sessions = await sync.async_get_sessions()
    
    # Get draft sessions (offline queue)
    drafts = await sync.async_get_offline_queue()
    
    # Delete session
    await sync.async_delete_session(session_id)

asyncio.run(main())
```

---

## Methods Cheatsheet

### Create Session
```python
result = await sync.async_create_session(
    session_id: str,
    goal_id: str,
    initial_responses: dict[str, str] = None
) -> dict
# Returns: {"status": "success", "session_id": "...", "goal_id": "..."}
# Errors: {"status": "error", "error": "..."}
```

### Sync Responses
```python
result = await sync.async_sync_responses(
    session_id: str,
    responses: dict[str, str]
) -> dict
# Returns: {"status": "success", "synced_to_goal": "..."}
# Errors: {"status": "error", "error": "..."}
```

### Get Session
```python
session = await sync.async_get_session(
    session_id: str
) -> dict | None
# Returns: {
#   "session_id": str,
#   "goal_id": str,
#   "responses": dict[str, str],
#   "status": "draft" | "submitted",
#   "created_at": str (ISO-8601),
#   "synced_at": str | None (ISO-8601)
# }
# Returns None if not found
```

### Get All Sessions
```python
sessions = await sync.async_get_sessions(
    status: "draft" | "submitted" | None = None
) -> list[dict]
# Returns list of session dicts
```

### Get Offline Queue (Draft Sessions)
```python
drafts = await sync.async_get_offline_queue() -> list[dict]
# Returns list of draft sessions waiting for sync
# Equivalent to: async_get_sessions(status="draft")
```

### Delete Session
```python
result = await sync.async_delete_session(
    session_id: str
) -> dict
# Returns: {"status": "success", "session_id": "..."}
# Errors: {"status": "error", "error": "..."}
```

---

## Database Location

**Default:** `~/.antigravity/pwa_sessions.db`

**Custom:** Pass `db_path` to `ShuPWASync()` constructor

```python
sync = ShuPWASync(db_path=Path("/custom/path/pwa.db"))
```

---

## Error Handling

All methods return `dict` with `"status"` key:
- `"success"` — Operation succeeded
- `"error"` — Operation failed

Error dict includes `"error"` key with description.

### Common Errors

| Scenario | Response |
|----------|----------|
| Empty session_id | `{"status": "error", "error": "Invalid session_id"}` |
| Session not found | `{"status": "error", "error": "Session ... not found"}` |
| Empty responses | `{"status": "error", "error": "Invalid responses"}` |
| Duplicate session | `{"status": "error", "error": "Session already exists"}` |
| Database error | `{"status": "error", "error": "Database error: ..."}` |

---

## Response Merging

When you sync multiple times:

```python
# Initial
await sync.async_create_session(sid, gid, {"a": "1"})

# First sync
await sync.async_sync_responses(sid, {"b": "2"})
# Result: {"a": "1", "b": "2"}

# Second sync (overwrites "a")
await sync.async_sync_responses(sid, {"a": "1_updated", "c": "3"})
# Result: {"a": "1_updated", "b": "2", "c": "3"}
```

**Strategy:** Last-write-wins (new values override existing keys)

---

## Offline Queue Pattern

```python
# Get all unsynced sessions
offline = await sync.async_get_offline_queue()

for session in offline:
    # Try to sync each
    result = await sync.async_sync_responses(
        session["session_id"],
        session["responses"]
    )
    if result["status"] == "success":
        print(f"Synced {session['session_id']}")
    else:
        print(f"Failed: {result['error']}")
        # Keep in draft for retry
```

---

## Status Values

| Status | Meaning |
|--------|---------|
| `"draft"` | Session created but not submitted to backend |
| `"submitted"` | Responses synced to goal |

**Lifecycle:** `draft` → `submitted` (one-way, no transition back)

---

## Session ID Best Practices

Use UUID4 (recommended):

```python
import uuid
session_id = str(uuid.uuid4())

# Or
from uuid import uuid4
session_id = str(uuid4())
```

Session IDs are:
- Immutable once created
- Used as primary key in SQLite
- Must be unique per PWA instance

---

## Singleton Pattern

```python
from agent.core.shu_pwa_sync import get_pwa_sync

# First call (creates instance)
sync1 = get_pwa_sync()

# Subsequent calls (returns same instance)
sync2 = get_pwa_sync()
assert sync1 is sync2  # True

# To pass custom db_path, do on first call:
sync = get_pwa_sync(db_path=Path("/custom/pwa.db"))
```

---

## Logging

Module logs at three levels:

| Level | Example |
|-------|---------|
| `INFO` | `"Synced 4 responses for session abc123 (total: 6)"` |
| `ERROR` | `"Database error during sync for session abc123: ..."` |
| `DEBUG` | `"Retrieved 12 sessions"` |

Enable debug logging:

```python
import logging
logging.getLogger("agent.core.shu_pwa_sync").setLevel(logging.DEBUG)
```

---

## Type Hints

All methods are fully typed:

```python
from typing import Optional, Literal
from pathlib import Path

# Constructor
sync: ShuPWASync = ShuPWASync(db_path: Optional[Path] = None)

# Methods return dicts
result: dict[str, Any] = await sync.async_sync_responses(...)
sessions: list[dict[str, Any]] = await sync.async_get_sessions(...)
session: Optional[dict[str, Any]] = await sync.async_get_session(...)
```

---

## Testing

Run all tests:

```bash
pytest tests/core/test_shu_pwa_sync.py -v
```

Run specific test:

```bash
pytest tests/core/test_shu_pwa_sync.py::test_sync_responses -v
```

Run with coverage:

```bash
pytest tests/core/test_shu_pwa_sync.py --cov=agent.core.shu_pwa_sync
```

---

## Environment Variables

- `ANTIGRAVITY_ROOT` — Base directory for `.antigravity/` config
  - Defaults to `$HOME` if not set
  - Database stored at `$ANTIGRAVITY_ROOT/.antigravity/pwa_sessions.db`

---

## Full Documentation

See `.agent/core/SHU_PWA_SYNC.md` for:
- Complete API reference
- Architecture diagrams
- Advanced usage patterns
- Error handling details
- Database schema documentation
