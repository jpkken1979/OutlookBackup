---
name: debugging-strategies
description: "Master systematic debugging techniques and profiling tools for efficient root cause analysis. Covers binary search debugging, hypothesis-driven investigation, instrumentation strategies, log analysis, debugger usage, profiling (CPU, memory, heap), stack trace analysis, debugging distributed systems, and production debugging without code changes. Includes browser DevTools, IDE debuggers (VS Code, PyCharm), profiling tools (Python cProfile, Node.js, Chrome DevTools), flame graphs, distributed tracing, and debugging checklist. Use when investigating bugs, debugging performance issues, analyzing production incidents, tracking elusive bugs, analyzing crash dumps, profiling slow code, debugging race conditions, or debugging distributed systems."
type: feature
---

# Debugging Strategies

Transform debugging from frustrating guesswork into systematic problem-solving with proven strategies, powerful tools, and methodical approaches.

## The Scientific Debugging Method

### 1. Reproduce the Issue

**Reproducibility is your foundation.** Without reproducibility, you're chasing ghosts.

```
Step 1: Understand the symptom
  - What exactly fails? (error message, incorrect result, hang)
  - When does it fail? (always, intermittent, under load)
  - Who observes it? (specific user, all users, specific browser)

Step 2: Gather environmental data
  - OS, runtime version, dependency versions
  - Browser type/version (for frontend bugs)
  - Network conditions (for network bugs)
  - Database size/data state (for database bugs)

Step 3: Create minimal reproduction
  - Smallest code/setup that triggers the bug
  - Can reproduce locally or in staging?
  - Does it require specific user actions or data?

Step 4: Establish baseline metrics
  - Before fix: measure the symptom (latency, error rate, memory usage)
  - After fix: verify improvement against baseline
```

### 2. Form Hypotheses

Never debug without a hypothesis. You'll waste hours.

```
Bad:    "Something is wrong with this code"
Good:   "Function X returns wrong value when Y is null"

Bad:    "The app is slow"
Good:   "Database queries are slow (N+1 pattern) when loading user with 100+ posts"

Bad:    "There's a memory leak"
Good:   "Memory grows unbounded when processing messages from queue (event listeners not cleaned up)"
```

### 3. Design Experiments

Test one hypothesis at a time.

```
Hypothesis: "Function calculateTotal() doesn't handle negative quantities"

Experiment 1: Call calculateTotal(-5) with valid price
  Result: Returns -50 (should be 0 or error)
  Conclusion: Hypothesis confirmed ✓

Experiment 2: Add guard clause to reject negative quantities
  Result: Function now returns error correctly
  Conclusion: Fix works ✓
```

## Pattern 1: Binary Search Debugging

Divide and conquer: halve the problem space with each step.

### Application: "Bug appears only when processing 1000+ items"

```python
# Iteration 1: Test with 500 items
items = list(range(500))
result = process_items(items)  # Works!
# Conclusion: Bug is in second half (500-1000)

# Iteration 2: Test with 750 items
items = list(range(750))
result = process_items(items)  # Fails!
# Conclusion: Bug is in 500-750 range

# Iteration 3: Test with 625 items
items = list(range(625))
result = process_items(items)  # Fails!
# Conclusion: Bug is in 500-625 range

# Iteration 4: Test with 560 items
items = list(range(560))
result = process_items(items)  # Works!
# Conclusion: Bug triggers between 560-625 items

# Root cause: Function has O(n²) loop, hits timeout around 600 items
```

### Application: "Bug only happens in Firefox, not Chrome"

```
Hypothesis: JavaScript feature not supported in Firefox

Experiment 1: Check console errors in Firefox → "Optional chaining not supported"
Experiment 2: Replace all ?. with && checks
Result: Works in Firefox ✓

Root cause: Code used modern JavaScript not yet supported in Firefox
```

## Pattern 2: Instrumentation (Strategic Logging)

Add logging to narrow the search space.

```python
# BEFORE (no visibility)
def process_order(order_id):
    order = db.find_order(order_id)
    total = calculate_total(order)
    charged = process_payment(total)
    return send_confirmation(order)
    # ❓ Where does it fail?

# AFTER (surgical instrumentation)
import logging
logger = logging.getLogger(__name__)

def process_order(order_id):
    logger.info(f"Starting order processing: {order_id}")

    order = db.find_order(order_id)
    logger.debug(f"Found order: {order.id}, items: {len(order.items)}")

    total = calculate_total(order)
    logger.debug(f"Calculated total: ${total}")

    charged = process_payment(total)
    logger.info(f"Payment processed: {charged}")

    result = send_confirmation(order)
    logger.info(f"Order complete: {result}")

    return result

# Output shows exactly where it fails and with what data
```

## Pattern 3: Debugger Breakpoints

Use IDEs, not print statements, for complex debugging.

### Python with PyCharm/VS Code

```python
def find_user(user_id: int) -> User:
    # Set breakpoint on next line (click on line number)
    user = database.query(User).filter(User.id == user_id).first()

    # Debugger stops here, you can:
    # - Inspect variables (user, user_id)
    # - Evaluate expressions: user.email if user else "not found"
    # - Step into database.query()
    # - Set conditional breakpoints: break only if user_id < 0

    if not user:
        raise UserNotFoundError(f"User {user_id} not found")

    return user
```

### JavaScript with Chrome DevTools

```javascript
function calculateDiscount(price, quantity) {
  // Open DevTools (F12) → Sources tab
  // Click line number to set breakpoint
  const subtotal = price * quantity;

  // Debugger pauses here, inspect:
  // - Local variables (price, quantity, subtotal)
  // - Call stack (which function called us)
  // - Conditional breakpoint: break only if price < 0

  const discountPercent = quantity > 10 ? 0.15 : 0.10;
  return subtotal * (1 - discountPercent);
}
```

## Pattern 4: Profiling Tools

Find performance bottlenecks, not guesswork.

### Python: cProfile (CPU profiling)

```python
import cProfile
import pstats

# Profile a function
profiler = cProfile.Profile()
profiler.enable()

# Your code here
process_large_dataset(big_data)

profiler.disable()

# Analyze results
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')  # Sort by total time
stats.print_stats(10)  # Top 10 functions

# Output shows:
# Function        | Calls | Total Time | Per Call
# process_row     | 50000 | 4.5s       | 0.00009s  ← Bottleneck!
# calculate_tax   | 50000 | 3.2s       | 0.00006s
```

### Node.js: flamegraph

```bash
# Generate flame graph of Node.js app
node --prof app.js  # Generates isolate-*.log

# Process the log
node --prof-process isolate-*.log > processed.txt

# Visualize (top functions consuming CPU)
# Shows which functions/libraries use most CPU time
```

### Chrome DevTools: Performance tab

```javascript
// Record performance
performance.mark('database-query-start');
const result = await database.query(bigQuery);
performance.mark('database-query-end');
performance.measure('database-query', 'database-query-start', 'database-query-end');

// View timeline in Chrome DevTools → Performance tab
// Shows exactly where CPU/rendering time goes
```

## Pattern 5: Memory Profiling & Leak Detection

### Python: Memory Profiler

```python
from memory_profiler import profile

@profile
def load_users(user_ids):
    """Line-by-line memory usage."""
    users = []  # Line 1: ~0 MB

    for user_id in user_ids:
        user = db.get_user(user_id)  # Line 4: grows by ~1MB per iteration
        users.append(user)  # Line 5: grows by ~1MB per iteration

    # If 10,000 users → grows to ~10GB! (memory leak?)
    return users

# Run with memory_profiler
# python -m memory_profiler script.py
```

### JavaScript: Chrome DevTools Heap Snapshot

```javascript
// In Chrome DevTools → Memory tab:

// 1. Take heap snapshot (baseline)
// 2. Perform action that might leak memory (create listeners, load data)
// 3. Take another heap snapshot
// 4. Compare snapshots

// Look for:
// - Objects retained after they should be garbage collected
// - DOM nodes still referenced after removal
// - Event listeners still attached to removed elements
```

## Pattern 6: Debugging Distributed Systems

Trace a request across multiple services.

### Distributed Tracing with IDs

```python
import uuid

# Service A
request_id = str(uuid.uuid4())
logger.info(f"request_id={request_id}: Processing user {user_id}")

# Call Service B
response = service_b.process(user_id, trace_id=request_id)
logger.info(f"request_id={request_id}: Got response from Service B")

# Service B logs the same request_id
def service_b_process(user_id, trace_id):
    logger.info(f"trace_id={trace_id}: Received from Service A")

    # Call Service C
    result = service_c.fetch(user_id, trace_id=trace_id)
    logger.info(f"trace_id={trace_id}: Got result from Service C")

    return result

# In logs, search for trace_id=xyz to see ENTIRE request flow:
# Service A → Service B → Service C
# Each log entry shows timing, helping identify slow service
```

## Pattern 7: Stack Trace Analysis

Read stack traces to understand the call sequence.

```
Stack trace from Java exception:

Exception in thread "main" java.lang.NullPointerException: Cannot invoke
  at UserService.getUserProfile(UserService.java:45)  ← Where it failed
  at ApiController.handleGetUser(ApiController.java:32)  ← Called from here
  at DispatcherServlet.doGet(DispatcherServlet.java:201)  ← Called from here
  at HttpServer.handleRequest(HttpServer.java:78)  ← Entry point

Analysis:
1. getUserProfile at line 45 tried to call method on null object
2. Called from ApiController line 32
3. getUserProfile likely returned null, not handled properly
4. Fix: Add null check in ApiController before calling getUserProfile
```

## Pattern 8: Production Debugging (Without Code Changes)

Use debuggers and tools that don't require redeployment.

### Option 1: Remote Debugging

```python
# Python: Add to app (no code change needed, just start with --debug flag)
import pdb
import sys

def attach_debugger_on_error():
    """Attach debugger when error occurs in production."""
    sys.excepthook = lambda exc_type, exc_value, traceback: pdb.post_mortem(traceback)

# Or use logging to capture state at error point
logger.exception("Error occurred", extra={
    "user_id": user_id,
    "request_body": request_body,
    "database_state": db_state
})
```

### Option 2: Logging Context

```python
# Use structured logging to capture request context
import structlog

logger = structlog.get_logger()

def process_request(request_id, user_id, data):
    log_context = {"request_id": request_id, "user_id": user_id}
    logger.info("processing request", **log_context)

    try:
        result = complex_processing(data)
        logger.info("processing complete", result=result, **log_context)
    except Exception as e:
        logger.exception("processing failed", error=str(e), **log_context)
        raise

# When error occurs, all logs have request_id and user_id
# Can replay exact scenario in staging
```

## Debugging Checklist

### Before You Start

- [ ] **Reproduce the issue**: Can you trigger it consistently?
- [ ] **Gather data**: Logs, error messages, environment details
- [ ] **Isolate the scope**: Which component fails? (frontend, backend, database)
- [ ] **Establish metrics**: What's the baseline? (performance before bug)

### During Investigation

- [ ] **Form hypotheses**: Write down what you think is wrong
- [ ] **Design experiments**: Test one hypothesis at a time
- [ ] **Use binary search**: Halve the problem space with each iteration
- [ ] **Add instrumentation**: Strategic logging, not random debugging
- [ ] **Use proper tools**: Debuggers, profilers, traces (not print statements)

### After Finding the Bug

- [ ] **Verify the fix**: Test with original reproduction case
- [ ] **Check for side effects**: Did the fix break anything else?
- [ ] **Add a test**: Prevent regression with test case
- [ ] **Document the finding**: Help future developers understand it

## Tools Reference

| Task | Tool | Language |
|------|------|----------|
| **Line-by-line debugging** | IDE Debugger (VS Code, PyCharm) | Any |
| **CPU Profiling** | cProfile (Python), flamegraph (Node) | Python, Node |
| **Memory Profiling** | memory_profiler, Chrome DevTools | Python, JavaScript |
| **Heap Analysis** | Chrome DevTools, Java Flight Recorder | JavaScript, Java |
| **Distributed Tracing** | Jaeger, Datadog, Zipkin | Any |
| **Log Analysis** | grep, awk, ELK stack, Datadog | Any |
| **Browser Debugging** | Chrome/Firefox DevTools | JavaScript |
| **Network Debugging** | Postman, curl, Wireshark | Network |

## Common Bug Patterns & Solutions

| Pattern | Symptom | Debug Approach |
|---------|---------|----------------|
| **Null pointer exception** | Crash when accessing .property | Check where null comes from (wrong return value?) |
| **Memory leak** | Memory grows unbounded | Heap snapshot, look for retained objects |
| **Race condition** | Intermittent failures | Add thread/async logging, look for timing |
| **N+1 queries** | Slow database performance | Profile queries, count query count per request |
| **Infinite loop** | Process hangs | Debugger breakpoint, inspect loop condition |
| **Deadlock** | Threads waiting forever | Thread dump, analyze lock dependencies |
