---
name: async-python-patterns
description: "Master Python asyncio, concurrent programming, and async/await patterns for high-performance applications. Covers async/await syntax, event loops, tasks and coroutines, asyncio.gather/TaskGroup, queues, context managers, exception handling, timeouts, cancellation, backpressure, and testing async code. Includes patterns for web APIs (FastAPI, aiohttp), concurrent I/O operations, database queries, external APIs, file operations, WebSocket servers, background tasks, worker pools, race conditions prevention, and debugging async code. Use when building async web APIs, implementing concurrent I/O operations, creating web scrapers, developing real-time applications, processing multiple independent tasks, building microservices, optimizing I/O-bound workloads, or implementing async background tasks and queues."
type: feature
---

# Async Python Patterns

Master Python asyncio for building high-performance, non-blocking applications that handle thousands of concurrent I/O operations efficiently.

## Core Concept: Async vs Sync vs Threading

| Model | Best For | Concurrency | GIL Impact |
|-------|----------|-------------|-----------|
| **Sync** | Simple scripts, CPU-bound | None (sequential) | N/A |
| **Threading** | Mixed I/O + CPU | Limited (GIL blocks) | Blocks other threads |
| **Asyncio** | I/O-bound (web, DB, APIs) | High (thousands of tasks) | Cooperates with GIL |
| **Multiprocessing** | CPU-bound | True parallelism | Bypasses GIL |

**Rule:** Use asyncio for I/O-bound workloads (network, database, files).

## Pattern 1: Async/Await Basics

### Coroutines vs Regular Functions

```python
import asyncio

# ❌ Regular function (synchronous, blocks)
def fetch_user(user_id):
    time.sleep(1)  # Blocks for 1 second
    return {"id": user_id, "name": "User"}

# ✓ Coroutine (asynchronous, yields control)
async def fetch_user_async(user_id):
    await asyncio.sleep(1)  # Yields control, doesn't block
    return {"id": user_id, "name": "User"}

# Calling differences:
user = fetch_user(1)  # Returns immediately

coro = fetch_user_async(1)  # Returns coroutine object, not result
user = await fetch_user_async(1)  # Actually executes, waits for result

# Running async code
asyncio.run(fetch_user_async(1))  # Creates event loop, runs coroutine, closes loop
```

### The Event Loop

```python
import asyncio

async def task1():
    print("Task 1 starting")
    await asyncio.sleep(1)
    print("Task 1 done")

async def task2():
    print("Task 2 starting")
    await asyncio.sleep(0.5)
    print("Task 2 done")

async def main():
    # Sequential (2 seconds total - wrong!)
    await task1()
    await task2()

    # Concurrent (1.5 seconds total - correct!)
    await asyncio.gather(task1(), task2())

# Event loop runs:
# 1. Start task1 (await asyncio.sleep(1))
# 2. Pause task1, run task2 (await asyncio.sleep(0.5))
# 3. Task2 finishes after 0.5s
# 4. Task1 finishes after 1s
# Total: 1 second (not 1.5!)

asyncio.run(main())
```

## Pattern 2: Tasks & Gathering

### Create Multiple Tasks

```python
import asyncio

async def fetch_user(user_id):
    print(f"Fetching user {user_id}")
    await asyncio.sleep(1)
    return {"id": user_id, "name": f"User {user_id}"}

async def main():
    # Create tasks (starts immediately)
    task1 = asyncio.create_task(fetch_user(1))
    task2 = asyncio.create_task(fetch_user(2))
    task3 = asyncio.create_task(fetch_user(3))

    # Wait for all tasks to complete
    results = await asyncio.gather(task1, task2, task3)
    # Results: [{"id": 1, ...}, {"id": 2, ...}, {"id": 3, ...}]

    # Or shorter syntax:
    results = await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3)
    )

asyncio.run(main())
# Output: Fetches all 3 users concurrently in ~1 second (not 3 seconds)
```

### TaskGroup (Python 3.11+) - Better Error Handling

```python
import asyncio

async def fetch_user(user_id):
    if user_id == 2:
        raise ValueError("User 2 not found")
    return {"id": user_id}

async def main():
    # With gather: One error cancels others
    try:
        async with asyncio.TaskGroup() as tg:  # Structured concurrency
            task1 = tg.create_task(fetch_user(1))
            task2 = tg.create_task(fetch_user(2))  # Will fail
            task3 = tg.create_task(fetch_user(3))
    except ExceptionGroup as eg:
        # All exceptions from all tasks
        for exc in eg.exceptions:
            print(f"Task failed: {exc}")

asyncio.run(main())
```

## Pattern 3: Concurrency Patterns for Real Workloads

### Pattern: Fetch Multiple URLs

```python
import aiohttp
import asyncio

async def fetch_url(session, url):
    """Fetch single URL."""
    async with session.get(url) as response:
        return await response.json()

async def fetch_all_urls(urls):
    """Fetch multiple URLs concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return results

# Usage
urls = [
    "https://api.example.com/users/1",
    "https://api.example.com/users/2",
    "https://api.example.com/users/3"
]
users = asyncio.run(fetch_all_urls(urls))
# Fetches all 3 URLs concurrently instead of sequentially
```

### Pattern: Concurrent Database Queries with Batching

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def fetch_users_concurrent(user_ids):
    """Fetch multiple users concurrently."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with AsyncSession(engine) as session:
        # Create concurrent tasks for each user
        tasks = [
            session.get(User, user_id)
            for user_id in user_ids
        ]

        # Run all queries concurrently
        users = await asyncio.gather(*tasks)
        return users

# Or with batch queries (more efficient):
async def fetch_users_batch(user_ids):
    """Fetch users in single query instead of many."""
    async with AsyncSession(engine) as session:
        query = select(User).where(User.id.in_(user_ids))
        result = await session.execute(query)
        return result.scalars().all()
```

## Pattern 4: Queues & Producer-Consumer

```python
import asyncio

async def producer(queue, num_items):
    """Produce items and put in queue."""
    for i in range(num_items):
        print(f"Producing item {i}")
        await queue.put(i)
        await asyncio.sleep(0.1)

    # Signal end of items
    await queue.put(None)

async def consumer(queue, consumer_id):
    """Consume items from queue."""
    while True:
        item = await queue.get()

        if item is None:  # End signal
            break

        print(f"Consumer {consumer_id} processing {item}")
        await asyncio.sleep(0.5)  # Simulate work
        queue.task_done()

async def main():
    queue = asyncio.Queue()

    # Run 1 producer and 3 consumers concurrently
    await asyncio.gather(
        producer(queue, 10),
        consumer(queue, 1),
        consumer(queue, 2),
        consumer(queue, 3)
    )

asyncio.run(main())
```

## Pattern 5: Timeouts & Cancellation

### Timeout Pattern

```python
import asyncio

async def slow_operation():
    await asyncio.sleep(5)
    return "Done"

async def main():
    try:
        # Timeout after 2 seconds
        result = await asyncio.wait_for(
            slow_operation(),
            timeout=2.0
        )
    except asyncio.TimeoutError:
        print("Operation timed out!")

asyncio.run(main())
```

### Cancellation Pattern

```python
import asyncio

async def worker(worker_id):
    """Worker that can be cancelled."""
    try:
        while True:
            print(f"Worker {worker_id} doing work...")
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print(f"Worker {worker_id} cancelled, cleaning up...")
        # Clean up resources (close connections, etc)
        raise  # Re-raise to signal task cancelled

async def main():
    tasks = [
        asyncio.create_task(worker(1)),
        asyncio.create_task(worker(2)),
        asyncio.create_task(worker(3))
    ]

    await asyncio.sleep(3)  # Let workers run for 3 seconds

    # Cancel all tasks
    for task in tasks:
        task.cancel()

    # Wait for cancellation to complete
    await asyncio.gather(*tasks, return_exceptions=True)

asyncio.run(main())
```

## Pattern 6: Backpressure & Rate Limiting

### Semaphore Pattern (Limit Concurrent Operations)

```python
import asyncio

async def fetch_with_semaphore(sem, url):
    """Fetch with limited concurrency."""
    async with sem:  # Acquire semaphore
        print(f"Fetching {url}")
        await asyncio.sleep(1)  # Simulate fetch
        return f"Result from {url}"

async def main():
    sem = asyncio.Semaphore(3)  # Max 3 concurrent requests

    urls = [f"http://api.example.com/data/{i}" for i in range(10)]

    tasks = [fetch_with_semaphore(sem, url) for url in urls]
    results = await asyncio.gather(*tasks)

    print(results)

asyncio.run(main())
```

### Rate Limiting Pattern

```python
import time

class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, max_calls, time_window):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    async def acquire(self):
        """Wait until call is allowed."""
        now = time.time()

        # Remove old calls outside time window
        self.calls = [c for c in self.calls if now - c < self.time_window]

        if len(self.calls) >= self.max_calls:
            # Wait until oldest call is outside window
            sleep_time = self.time_window - (now - self.calls[0])
            await asyncio.sleep(sleep_time)

        self.calls.append(time.time())

async def api_call(limiter, call_id):
    await limiter.acquire()
    print(f"API call {call_id}")

async def main():
    limiter = RateLimiter(max_calls=3, time_window=1.0)  # 3 calls per second

    tasks = [api_call(limiter, i) for i in range(10)]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

## Pattern 7: Context Managers & Resource Management

```python
import asyncio
import aiofiles

class AsyncDatabaseConnection:
    """Async context manager for database."""

    async def __aenter__(self):
        print("Opening connection")
        await asyncio.sleep(0.1)  # Simulate connection
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("Closing connection")
        await asyncio.sleep(0.1)  # Simulate cleanup

    async def query(self, sql):
        await asyncio.sleep(0.5)  # Simulate query
        return "Result"

async def main():
    # Automatically manages open/close
    async with AsyncDatabaseConnection() as db:
        result = await db.query("SELECT * FROM users")
        print(result)
    # Connection automatically closed

asyncio.run(main())
```

## Pattern 8: Testing Async Code

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_fetch_user():
    """Test async function."""
    user = await fetch_user(1)
    assert user["id"] == 1

@pytest.mark.asyncio
async def test_multiple_tasks():
    """Test concurrent execution."""
    results = await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3)
    )
    assert len(results) == 3

@pytest.mark.asyncio
async def test_timeout():
    """Test timeout behavior."""
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            asyncio.sleep(10),
            timeout=1.0
        )

# Run tests:
# pytest tests/test_async.py -v
```

## Pattern 9: Error Handling in Async Code

```python
import asyncio

async def failing_task():
    await asyncio.sleep(0.1)
    raise ValueError("Task failed!")

async def main():
    # Approach 1: Catch with gather
    results = await asyncio.gather(
        failing_task(),
        asyncio.sleep(0.5),
        return_exceptions=True  # Don't raise, return as result
    )
    # results = [ValueError(...), None]

    # Approach 2: Try/except per task
    try:
        await failing_task()
    except ValueError as e:
        print(f"Caught: {e}")

    # Approach 3: TaskGroup (best, Python 3.11+)
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(failing_task())
            tg.create_task(asyncio.sleep(0.5))
    except ExceptionGroup as eg:
        for exc in eg.exceptions:
            print(f"Task failed: {exc}")

asyncio.run(main())
```

## Anti-Patterns to Avoid

| ❌ Anti-Pattern | ✅ Better Approach |
|-----------------|-------------------|
| **Forget to await** | Always use `await` with coroutines |
| **Sequential instead of concurrent** | Use `gather()`, not sequential `await` |
| **Blocking in async code** | Use `asyncio.to_thread()` for blocking code |
| **No timeout on external calls** | Always set `timeout=` on external requests |
| **Not handling cancellation** | Catch `CancelledError` and cleanup |
| **Mixing threads and asyncio** | Choose one concurrency model |
| **No error handling in gather** | Use `return_exceptions=True` or try/except |

## Async Checklist

- [ ] **Coroutines**: All I/O operations use `async`/`await`
- [ ] **Event Loop**: Using `asyncio.run()` or similar
- [ ] **Concurrency**: Using `gather()`, `TaskGroup()`, or queues
- [ ] **Timeouts**: External API calls have `timeout=`
- [ ] **Cancellation**: Handle `CancelledError` gracefully
- [ ] **Error Handling**: Use `ExceptionGroup` or `return_exceptions=True`
- [ ] **Resource Cleanup**: Context managers or explicit cleanup
- [ ] **Testing**: All async functions have test coverage
- [ ] **No Blocking**: No `time.sleep()`, `requests.get()` (use async versions)
- [ ] **Backpressure**: Semaphores or queues for limiting concurrent ops
