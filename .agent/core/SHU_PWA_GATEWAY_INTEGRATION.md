# ShuMobile PWA Gateway Integration Guide

## Overview

This document provides step-by-step instructions for integrating the ShuPWASync module into the gateway HTTP server. The module is complete and tested; only the endpoint handler needs to be added to `gateway.py`.

---

## Prerequisites

✓ Module complete: `.agent/core/shu_pwa_sync.py`
✓ Tests complete: `tests/core/test_shu_pwa_sync.py`
✓ Documentation complete: `.agent/core/SHU_PWA_SYNC.md`

---

## Step 1: Add Import to Gateway

In `gateway.py`, add at the top with other imports:

```python
from agent.core.shu_pwa_sync import get_pwa_sync, ShuPWASync
```

---

## Step 2: Create Endpoint Handler

Add this route handler to the gateway app (the exact location depends on your gateway structure, but typically near other route definitions):

### Option A: Using aiohttp (Recommended)

If using aiohttp web framework:

```python
async def handle_pwa_sync(request: web.Request) -> web.Response:
    """
    Handle PWA session synchronization requests.
    
    POST /v1/shu/pwa_sync
    
    Request body:
    {
        "session_id": "uuid-string",
        "responses": {
            "dimension_name": "answer_value",
            ...
        }
    }
    
    Response (success):
    {
        "status": "success",
        "synced_to_goal": "goal-uuid"
    }
    
    Response (error):
    {
        "status": "error",
        "error": "error message"
    }
    """
    try:
        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"PWA sync: invalid JSON - {e}")
            return web.json_response(
                {
                    "status": "error",
                    "error": "Invalid JSON in request body"
                },
                status=400
            )
        
        # Validate required fields
        session_id = body.get("session_id")
        responses = body.get("responses")
        
        if not session_id or not isinstance(session_id, str):
            logger.warning(f"PWA sync: missing or invalid session_id")
            return web.json_response(
                {
                    "status": "error",
                    "error": "Missing or invalid session_id (must be string)"
                },
                status=400
            )
        
        if not responses or not isinstance(responses, dict):
            logger.warning(f"PWA sync: missing or invalid responses for {session_id}")
            return web.json_response(
                {
                    "status": "error",
                    "error": "Missing or invalid responses (must be non-empty dict)"
                },
                status=400
            )
        
        # Validate response values are strings
        if not all(isinstance(v, str) for v in responses.values()):
            logger.warning(f"PWA sync: non-string response values for {session_id}")
            return web.json_response(
                {
                    "status": "error",
                    "error": "All response values must be strings"
                },
                status=400
            )
        
        # Sync responses
        sync_service = get_pwa_sync()
        result = await sync_service.async_sync_responses(session_id, responses)
        
        # Log the sync
        if result["status"] == "success":
            logger.info(
                f"PWA sync successful: session={session_id}, "
                f"num_responses={len(responses)}, goal={result['synced_to_goal']}"
            )
            return web.json_response(result, status=200)
        else:
            logger.warning(
                f"PWA sync failed: session={session_id}, "
                f"error={result.get('error', 'unknown')}"
            )
            return web.json_response(result, status=400)
    
    except Exception as e:
        logger.error(f"PWA sync: unexpected error - {e}", exc_info=True)
        return web.json_response(
            {
                "status": "error",
                "error": "Internal server error"
            },
            status=500
        )


# Register the route with the app
app.router.add_post("/v1/shu/pwa_sync", handle_pwa_sync)
```

### Option B: Using FastAPI

If using FastAPI:

```python
from fastapi import APIRouter, HTTPException, Body
from typing import Dict

router = APIRouter(prefix="/v1", tags=["shu"])

@router.post("/shu/pwa_sync")
async def pwa_sync(
    session_id: str = Body(...),
    responses: Dict[str, str] = Body(...)
) -> Dict[str, str]:
    """
    Synchronize PWA responses to backend goal tracking.
    
    Args:
        session_id: UUID of the PWA session
        responses: Dictionary mapping dimension names to string answers
    
    Returns:
        {"status": "success", "synced_to_goal": "goal-uuid"}
        or
        {"status": "error", "error": "error message"}
    
    Raises:
        HTTPException: If validation fails
    """
    if not session_id or not isinstance(session_id, str):
        logger.warning("PWA sync: invalid session_id")
        raise HTTPException(status_code=400, detail="Invalid session_id")
    
    if not responses or not isinstance(responses, dict):
        logger.warning(f"PWA sync: invalid responses for {session_id}")
        raise HTTPException(status_code=400, detail="Invalid responses")
    
    if not all(isinstance(v, str) for v in responses.values()):
        logger.warning(f"PWA sync: non-string response values")
        raise HTTPException(status_code=400, detail="All response values must be strings")
    
    try:
        sync_service = get_pwa_sync()
        result = await sync_service.async_sync_responses(session_id, responses)
        
        if result["status"] == "success":
            logger.info(
                f"PWA sync: session={session_id}, "
                f"num_responses={len(responses)}"
            )
            return result
        else:
            logger.warning(f"PWA sync failed: {result.get('error')}")
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Sync failed")
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PWA sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

app.include_router(router)
```

### Option C: Using Flask

If using Flask:

```python
from flask import request, jsonify

@app.route("/v1/shu/pwa_sync", methods=["POST"])
def pwa_sync():
    """Handle PWA session synchronization requests."""
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("PWA sync: empty request body")
            return jsonify({
                "status": "error",
                "error": "Empty request body"
            }), 400
        
        session_id = data.get("session_id")
        responses = data.get("responses")
        
        # Validate
        if not session_id or not isinstance(session_id, str):
            logger.warning("PWA sync: invalid session_id")
            return jsonify({
                "status": "error",
                "error": "Invalid session_id"
            }), 400
        
        if not responses or not isinstance(responses, dict):
            logger.warning(f"PWA sync: invalid responses")
            return jsonify({
                "status": "error",
                "error": "Invalid responses"
            }), 400
        
        # Sync (need to handle async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sync_service = get_pwa_sync()
            result = loop.run_until_complete(
                sync_service.async_sync_responses(session_id, responses)
            )
        finally:
            loop.close()
        
        if result["status"] == "success":
            logger.info(f"PWA sync: session={session_id}, num_responses={len(responses)}")
            return jsonify(result), 200
        else:
            logger.warning(f"PWA sync failed: {result.get('error')}")
            return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"PWA sync error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": "Internal server error"
        }), 500
```

---

## Step 3: Add to Routes List

If your gateway maintains a list of routes, add:

```python
ROUTES = {
    ...
    "/v1/shu/pwa_sync": {
        "method": "POST",
        "handler": handle_pwa_sync,
        "description": "Synchronize PWA session responses to goal tracking"
    }
    ...
}
```

---

## Step 4: Add Health Check Integration (Optional)

If your gateway includes a health check endpoint, consider adding PWA sync status:

```python
@app.route("/v1/health")
async def health_check():
    """Health check including PWA sync module status."""
    try:
        sync_service = get_pwa_sync()
        
        # Check database is accessible
        sessions = await sync_service.async_get_sessions()
        pwa_healthy = True
        pwa_sessions = len(sessions)
    except Exception as e:
        logger.error(f"PWA health check failed: {e}")
        pwa_healthy = False
        pwa_sessions = -1
    
    return jsonify({
        "status": "healthy",
        "components": {
            ...
            "pwa_sync": {
                "status": "healthy" if pwa_healthy else "unhealthy",
                "sessions": pwa_sessions
            }
            ...
        }
    })
```

---

## Step 5: Add Monitoring/Metrics (Optional)

For production deployments, consider adding metrics:

```python
from prometheus_client import Counter, Histogram

pwa_sync_requests = Counter(
    'pwa_sync_requests_total',
    'Total PWA sync requests',
    ['status']
)

pwa_sync_duration = Histogram(
    'pwa_sync_duration_seconds',
    'Duration of PWA sync operations'
)

async def handle_pwa_sync(request: web.Request) -> web.Response:
    """Handle PWA session synchronization requests."""
    start_time = time.time()
    
    try:
        # ... validation code ...
        
        sync_service = get_pwa_sync()
        result = await sync_service.async_sync_responses(session_id, responses)
        
        pwa_sync_requests.labels(status=result["status"]).inc()
        pwa_sync_duration.observe(time.time() - start_time)
        
        return web.json_response(result)
    
    except Exception as e:
        pwa_sync_requests.labels(status="error").inc()
        pwa_sync_duration.observe(time.time() - start_time)
        raise
```

---

## Step 6: Test the Integration

### Manual Test with curl

```bash
# Test successful sync
curl -X POST http://localhost:4747/v1/shu/pwa_sync \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "responses": {
      "energy_level": "good",
      "mood": "positive",
      "sleep_hours": "8"
    }
  }'

# Expected response:
# {"status": "success", "synced_to_goal": "..."}

# Test with invalid session
curl -X POST http://localhost:4747/v1/shu/pwa_sync \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "nonexistent",
    "responses": {"test": "data"}
  }'

# Expected response:
# {"status": "error", "error": "Session nonexistent not found"}
```

### Unit Test

Add to your test suite:

```python
@pytest.mark.asyncio
async def test_pwa_sync_endpoint(client):
    """Test PWA sync endpoint."""
    # Create a session first
    sync = get_pwa_sync()
    session_id = str(uuid.uuid4())
    goal_id = str(uuid.uuid4())
    await sync.async_create_session(session_id, goal_id, {})
    
    # Sync via endpoint
    response = await client.post(
        "/v1/shu/pwa_sync",
        json={
            "session_id": session_id,
            "responses": {"test": "data"}
        }
    )
    
    assert response.status == 200
    data = await response.json()
    assert data["status"] == "success"
    assert data["synced_to_goal"] == goal_id
```

---

## Step 7: Update API Documentation

Add to your API docs (e.g., OpenAPI/Swagger):

```yaml
/v1/shu/pwa_sync:
  post:
    summary: Synchronize PWA session responses
    description: |
      Synchronize responses from ShuMobile PWA to backend goal tracking.
      Responses are merged with existing data; new values override old ones.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - session_id
              - responses
            properties:
              session_id:
                type: string
                format: uuid
                description: Unique session identifier
                example: "550e8400-e29b-41d4-a716-446655440000"
              responses:
                type: object
                description: Dimension -> answer mapping
                additionalProperties:
                  type: string
                example:
                  energy_level: "good"
                  mood: "positive"
                  sleep_hours: "8"
    responses:
      '200':
        description: Sync successful
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
                  enum: ["success"]
                synced_to_goal:
                  type: string
                  format: uuid
      '400':
        description: Invalid request
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
                  enum: ["error"]
                error:
                  type: string
      '500':
        description: Server error
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
                  enum: ["error"]
                error:
                  type: string
    tags:
      - ShuMobile PWA
```

---

## Verification Checklist

- [ ] Import statement added
- [ ] Handler function created
- [ ] Route registered with app
- [ ] Input validation implemented
- [ ] Error handling with appropriate HTTP status codes
- [ ] Logging added (INFO for success, WARNING/ERROR for failures)
- [ ] Manual testing with curl successful
- [ ] Unit tests passing
- [ ] API documentation updated
- [ ] Health check integrated (if applicable)
- [ ] Monitoring/metrics added (if applicable)

---

## Troubleshooting

### "ShuPWASync not found" error
- Verify import statement at top of gateway.py
- Verify `.agent/core/shu_pwa_sync.py` file exists
- Check Python path includes `.agent/`

### "Session not found" responses
- Verify session was created first (in tests, call `async_create_session`)
- Check database file is being created: `~/.antigravity/pwa_sessions.db`

### Database locked errors
- Ensure only one gateway instance is running
- Check permissions on `~/.antigravity/` directory
- Consider enabling WAL mode in SQLite

### Async/await issues
- Ensure handler is `async def`
- Use `await` when calling ShuPWASync methods
- Verify event loop is running (depending on framework)

---

## Database Management

### View sessions in database

```bash
sqlite3 ~/.antigravity/pwa_sessions.db
sqlite> SELECT session_id, goal_id, status, created_at FROM pwa_sessions;
sqlite> .quit
```

### Clean up old sessions

```bash
sqlite3 ~/.antigravity/pwa_sessions.db
sqlite> DELETE FROM pwa_sessions WHERE status = 'draft' AND created_at < datetime('now', '-30 days');
sqlite> VACUUM;
sqlite> .quit
```

### Reset database

```bash
rm ~/.antigravity/pwa_sessions.db
# Database will be recreated on first sync
```

---

## Performance Tuning

### Enable WAL mode (concurrent reads)

```python
def enable_wal_mode():
    import sqlite3
    conn = sqlite3.connect(Path.home() / ".antigravity" / "pwa_sessions.db")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.close()

# Call once during startup
enable_wal_mode()
```

### Increase busy timeout (reduces lock contention)

```python
# In ShuPWASync.__init__
conn = sqlite3.connect(self.db_path)
conn.execute("PRAGMA busy_timeout = 5000;")  # 5 seconds
```

### Batch operations

For syncing multiple sessions:

```python
async def batch_sync(sessions_data: list[dict]):
    sync = get_pwa_sync()
    results = []
    for data in sessions_data:
        result = await sync.async_sync_responses(
            data["session_id"],
            data["responses"]
        )
        results.append(result)
    return results
```

---

## Next Steps

1. Choose your framework (aiohttp/FastAPI/Flask)
2. Copy the appropriate handler code
3. Add to your gateway.py file
4. Test locally with curl
5. Run existing test suite
6. Deploy to production
7. Monitor sync success rates

---

## Support

For issues or questions:
- See `.agent/core/SHU_PWA_SYNC.md` for detailed API reference
- See `.agent/core/SHU_PWA_ARCHITECTURE.txt` for architecture details
- Run tests: `pytest tests/core/test_shu_pwa_sync.py -v`
- Check logs in `~/.antigravity/` directory

---

**Status:** Ready for gateway integration. All module code and tests are complete.
