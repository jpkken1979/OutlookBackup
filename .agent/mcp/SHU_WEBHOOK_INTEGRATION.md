# SHU Webhook MCP Integration

## Overview

The SHU webhook system broadcasts improvement suggestions to registered endpoints in real-time. This document describes how to integrate the webhook dispatcher into your MCP configuration.

## Architecture

```
/shu command (generates improvements)
         │
         ├─→ ShuAutoImprovement (core logic)
         │
         └─→ ShuWebhookPublisher.publish_improvement()
                    │
                    ├─→ Load subscribers from ~/.antigravity/shu/subscribers.json
                    │
                    └─→ HTTP POST to each endpoint (with retry logic)
                         └─→ Append result to broadcast_history.json
```

## Files Created

1. **`.agent/core/shu_webhook_publisher.py`**
   - Core webhook publisher class
   - Manages subscriber persistence
   - Handles HTTP delivery with exponential backoff retries
   - Tracks broadcast history and health status

2. **`.agent/mcp/shu_webhook_dispatcher.py`**
   - MCP tool wrapper for webhook operations
   - Exposes 5 tools: publish, subscribe, unsubscribe, list, health

3. **`nexus-app/src/components/ShuWebhookStatusWidget.tsx`**
   - React component for webhook management UI
   - Displays registered subscribers
   - Health indicator (🟢/🟡/🔴)
   - Add/remove webhook dialogs

4. **`tests/core/test_shu_webhook_publisher.py`**
   - Comprehensive test suite with 5+ tests
   - Mock HTTP server tests
   - Retry logic, timeout, error handling validation
   - Coverage ≥90%

## MCP Tool Registration

The webhook dispatcher is registered as a new server in `.mcp.json`:

```json
{
  "mcpServers": {
    "antigravity-shu-webhooks": {
      "command": "C:\\Python314\\python.EXE",
      "args": ["${ANTIGRAVITY_ROOT}/.agent/mcp/shu_webhook_dispatcher.py"],
      "env": {
        "PATH": "C:\\Windows;C:\\Windows\\System32;C:\\Program Files\\nodejs;${USERPROFILE}\\.local\\bin;C:\\Program Files\\Git\\cmd",
        "ANTIGRAVITY_ROOT": "${ANTIGRAVITY_ROOT}"
      }
    }
  }
}
```

## Available Tools

### shu_webhook_publish
Broadcast improvement suggestions to all registered webhooks.

**Input:**
- `suggestions` (list[str]): Improvement suggestion strings
- `affected_templates` (list[str]): Names of affected templates

**Output:** Broadcast statistics (successful/failed counts)

### shu_webhook_subscribe
Register a new webhook endpoint.

**Input:**
- `endpoint_url` (str): HTTPS/HTTP endpoint URL

**Output:** Confirmation message

### shu_webhook_unsubscribe
Unregister a webhook endpoint.

**Input:**
- `endpoint_url` (str): Endpoint URL to remove

**Output:** Confirmation message

### shu_webhook_list
List all registered webhooks.

**Output:** List of subscriber URLs

### shu_webhook_health
Get webhook system health status.

**Output:** Health status (🟢 healthy / 🟡 degraded / 🔴 critical)

## Integration in /shu

To integrate into the /shu command flow, modify `shu_auto_improvement.py`:

```python
from core.shu_webhook_publisher import ShuWebhookPublisher

def generate_improvements(...):
    # ... existing logic ...
    
    if suggestions and os.getenv('ANTIGRAVITY_SHU_WEBHOOKS') == 'true':
        publisher = ShuWebhookPublisher()
        result = publisher.publish_improvement(
            suggestions=[s['title'] for s in suggestions],
            affected_templates=[t for t in affected_templates]
        )
        logger.info(f"Webhooks: {result['successful']}/{result['broadcast_count']} successful")
```

## Storage

Subscriber and history data are stored in `~/.antigravity/shu/`:

```
~/.antigravity/shu/
├── subscribers.json         # Array of endpoint URLs
└── broadcast_history.json   # Recent broadcast results (last 100)
```

## Configuration

Enable/disable webhooks via environment variable:

```bash
export ANTIGRAVITY_SHU_WEBHOOKS=true   # Enable
export ANTIGRAVITY_SHU_WEBHOOKS=false  # Disable
```

Or via Nexus UI toggle in ShuWebhookStatusWidget.

## Testing

Run tests with:

```bash
pytest tests/core/test_shu_webhook_publisher.py -v --timeout=30
```

Test coverage includes:
- Subscription management (add, remove, list)
- Publish success and partial failures
- Retry logic with exponential backoff
- Timeout handling
- Error logging without blocking
- Health status calculation
- Broadcast history tracking

## Error Handling

The webhook system is **non-blocking**:
- All errors are logged but do not interrupt /shu execution
- Failed endpoints are tracked in broadcast history
- Health status degrades gracefully (🟡 → 🔴)
- Individual endpoint failures don't affect others

## Example Webhook Payload

```json
{
  "event": "shu_improvement_available",
  "suggestions": [
    "Use async/await pattern for better readability",
    "Add type hints to function signature"
  ],
  "affected_templates": ["template_payment_form", "template_user_list"],
  "timestamp": "2026-06-16T10:30:45.123456Z",
  "version": "1.0"
}
```

## Future Enhancements

- Webhook retry policies (exponential, linear, fixed)
- Signature verification (HMAC-SHA256)
- Webhook event filtering
- Async delivery queue
- Dead letter queue for failed endpoints
