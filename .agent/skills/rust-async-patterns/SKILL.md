---
name: rust-async-patterns
description: "Master Rust async programming with Tokio runtime, tasks, channels, streams, and concurrent patterns. Covers async/await syntax, spawning tasks, channels (mpsc, broadcast, watch), select!, timeouts, streams with combinators, error handling in async code, backpressure, graceful shutdown, and deadlock prevention. Includes patterns for async web services (HTTP clients, servers), database access (SQLx), middleware, concurrency control (semaphores, mutexes), and debugging async issues. Use when building async Rust applications, implementing high-concurrency services, creating network protocols, handling real-time data processing, or optimizing CPU/memory usage in concurrent systems."
type: feature
---

# Rust Async Patterns with Tokio

Master async Rust for building scalable, high-performance concurrent systems.

---

## Async/Await Fundamentals

### Async Functions & Futures

```rust
// Async function returns Future<Output = T>
async fn fetch_data(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    let response = reqwest::get(url).await?;
    let body = response.text().await?;
    Ok(body)
}

// Awaiting makes code sequential (reads like sync code)
async fn main() {
    match fetch_data("https://api.example.com/data").await {
        Ok(data) => println!("Data: {}", data),
        Err(e) => eprintln!("Error: {}", e),
    }
}

// .await blocks until future completes (non-blocking)
// ❌ WRONG: async fn without .await (just calls, doesn't run)
async fn wrong_example() {
    let _future = fetch_data("...");  // Creates future but doesn't execute
}

// ✅ CORRECT
async fn right_example() {
    let result = fetch_data("...").await;  // Actually executes
}
```

---

## Pattern 1: Spawning Tasks

### Concurrent Execution with tokio::spawn

```rust
use tokio::task;

async fn process_items(items: Vec<String>) {
    let mut handles = vec![];

    for item in items {
        let handle = task::spawn(async move {
            println!("Processing: {}", item);
            // Do CPU-bound or I/O-bound work
            item.len()  // Return result
        });
        handles.push(handle);
    }

    // Wait for all tasks
    for handle in handles {
        match handle.await {
            Ok(result) => println!("Task result: {}", result),
            Err(e) => eprintln!("Task panicked: {}", e),
        }
    }
}

// Better: JoinSet (Rust 1.70+) - cleaner API
use tokio::task::JoinSet;

async fn better_example(items: Vec<String>) {
    let mut set = JoinSet::new();

    for item in items {
        set.spawn(async move {
            process_item(&item).await
        });
    }

    while let Some(result) = set.join_next().await {
        match result {
            Ok(value) => println!("Result: {}", value),
            Err(_) => eprintln!("Task failed"),
        }
    }
}
```

---

## Pattern 2: Channels for Communication

### Different Channel Types & When to Use

```rust
use tokio::sync::mpsc;
use tokio::sync::broadcast;
use tokio::sync::watch;

// MPSC (Multi-Producer, Single-Consumer): One receiver, many senders
async fn mpsc_example() {
    let (tx, mut rx) = mpsc::channel(100);  // Buffer 100 messages

    tokio::spawn(async move {
        for i in 0..5 {
            tx.send(i).await.ok();
        }
        // tx dropped = channel closes
    });

    while let Some(value) = rx.recv().await {
        println!("Received: {}", value);
    }
}

// BROADCAST: Many senders, many receivers (all see all messages)
async fn broadcast_example() {
    let (tx, mut rx1) = broadcast::channel(10);
    let mut rx2 = tx.subscribe();  // New receiver

    tx.send("Hello").ok();
    tx.send("World").ok();

    println!("{}", rx1.recv().await.unwrap());  // "Hello"
    println!("{}", rx2.recv().await.unwrap());  // "Hello"
}

// WATCH: Latest value, many readers (useful for config updates)
async fn watch_example() {
    let (tx, mut rx) = watch::channel("initial");

    tokio::spawn(async move {
        for msg in &["config_v1", "config_v2", "config_v3"] {
            tx.send(*msg).ok();
            tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
        }
    });

    while rx.changed().await.is_ok() {
        println!("Config updated: {}", *rx.borrow());
    }
}
```

---

## Pattern 3: Select! for Multiple Async Operations

### Racing & Coordinating Futures

```rust
use tokio::select;

async fn select_example() {
    let mut fut1 = async { "task1" };
    let mut fut2 = async { "task2" };

    match select!(&mut fut1 => fut1, &mut fut2 => fut2) {
        "task1" => println!("Task 1 won"),
        "task2" => println!("Task 2 won"),
        _ => {}
    }
}

// Common pattern: Timeout with select!
async fn with_timeout() {
    select! {
        result = fetch_data() => {
            println!("Got data: {:?}", result);
        }
        _ = tokio::time::sleep(std::time::Duration::from_secs(5)) => {
            println!("Timeout!");
        }
    }
}

// Cancel remaining tasks when one completes
async fn race_tasks(tasks: Vec<impl Future>) {
    select! {
        biased;  // Prefer earlier branches (deterministic)
        _ = tasks[0] => println!("Task 0 done"),
        _ = tasks[1] => println!("Task 1 done"),
        _ = tasks[2] => println!("Task 2 done"),
    }
}
```

---

## Pattern 4: Streams & Combinators

### Processing Async Sequences

```rust
use tokio_stream::StreamExt;
use tokio_stream::wrappers::ReceiverStream;

async fn stream_example() {
    let (tx, rx) = tokio::sync::mpsc::channel(10);
    let mut stream = ReceiverStream::new(rx);

    // Combinators work like iterators but async
    let result: Vec<_> = stream
        .map(|x| x * 2)           // Transform
        .filter(|x| x % 3 == 0)   // Filter
        .take(5)                   // Limit
        .collect()
        .await;

    println!("{:?}", result);
}

// Custom stream with generator
use futures::stream::{self, StreamExt};

async fn custom_stream() {
    let stream = stream::iter(1..=5)
        .then(async move |i| async move {
            // Simulate async work
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
            i * 2
        });

    stream.for_each(|x| async move {
        println!("Value: {}", x);
    }).await;
}
```

---

## Pattern 5: Backpressure & Concurrency Control

### Managing Load with Semaphores

```rust
use tokio::sync::Semaphore;
use std::sync::Arc;

async fn rate_limited_tasks(urls: Vec<String>) {
    let semaphore = Arc::new(Semaphore::new(5));  // Max 5 concurrent
    let mut handles = vec![];

    for url in urls {
        let sem = Arc::clone(&semaphore);

        let handle = tokio::spawn(async move {
            let _permit = sem.acquire().await.unwrap();  // Wait for slot
            // Now max 5 tasks are in this section

            make_request(&url).await;
            // Slot released when permit dropped
        });

        handles.push(handle);
    }

    // Wait for all
    for h in handles {
        let _ = h.await;
    }
}

// Bounded queue (backpressure via buffer size)
async fn bounded_queue_backpressure() {
    let (tx, rx) = tokio::sync::mpsc::channel(10);  // Max 10 buffered

    tokio::spawn(async move {
        for i in 0..1000 {
            tx.send(i).await.ok();  // Blocks if buffer full
        }
    });

    // Receiver processes: produces backpressure by consuming slowly
    tokio::time::sleep(std::time::Duration::from_secs(10)).await;
}
```

---

## Pattern 6: Error Handling in Async Code

### Propagating & Recovering from Errors

```rust
// ❌ WRONG: Losing errors
async fn wrong_error_handling() {
    let handle = tokio::spawn(async {
        dangerous_operation().await
    });

    let _ = handle.await;  // Ignores error if task panics
}

// ✅ CORRECT: Propagating errors
async fn right_error_handling() -> Result<(), Box<dyn std::error::Error>> {
    let handle = tokio::spawn(async {
        dangerous_operation().await
    });

    match handle.await {
        Ok(Ok(result)) => Ok(result),
        Ok(Err(e)) => Err(e.into()),
        Err(join_error) => Err(format!("Task panicked: {}", join_error).into()),
    }
}

// Error handling with select!
async fn resilient_operations() {
    select! {
        result = operation1() => match result {
            Ok(v) => println!("Op1 succeeded: {}", v),
            Err(e) => eprintln!("Op1 failed: {}", e),
        },
        result = operation2() => match result {
            Ok(v) => println!("Op2 succeeded: {}", v),
            Err(e) => eprintln!("Op2 failed: {}", e),
        }
    }
}

// Retry pattern
async fn with_retry<T, F, Fut>(
    mut f: F,
    max_retries: u32,
) -> Result<T, Box<dyn std::error::Error>>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<T, Box<dyn std::error::Error>>>,
{
    let mut attempt = 0;

    loop {
        match f().await {
            Ok(result) => return Ok(result),
            Err(e) => {
                attempt += 1;
                if attempt >= max_retries {
                    return Err(e);
                }
                tokio::time::sleep(std::time::Duration::from_millis(100 * attempt as u64)).await;
            }
        }
    }
}
```

---

## Pattern 7: Graceful Shutdown

### Coordinated Task Cancellation

```rust
use tokio::signal;
use tokio::sync::broadcast;

async fn server_with_graceful_shutdown() {
    let (shutdown_tx, _) = broadcast::channel(1);
    let mut handles = vec![];

    // Worker tasks
    for i in 0..5 {
        let mut rx = shutdown_tx.subscribe();

        let handle = tokio::spawn(async move {
            loop {
                select! {
                    _ = rx.recv() => {
                        println!("Worker {} shutting down", i);
                        break;
                    }
                    _ = work() => {
                        println!("Worker {} did work", i);
                    }
                }
            }
        });

        handles.push(handle);
    }

    // Listen for SIGTERM
    signal::ctrl_c().await.ok();
    println!("Shutdown signal received");

    // Broadcast shutdown
    drop(shutdown_tx);  // Drop sender, triggers recv() in all workers

    // Wait for graceful completion
    for h in handles {
        let _ = h.await;
    }
}
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Always .await** | Futures don't run without await | Never call async fn without .await |
| **Use JoinSet** | Cleaner task management | Instead of manually tracking handles |
| **Handle task errors** | Panics don't propagate | Check join handle result |
| **Limit concurrency** | Prevent resource exhaustion | Use Semaphore, bounded channels |
| **Select! with timeouts** | Prevent hangs | Always have timeout branch |
| **Clone Arc, not data** | Cheap reference sharing | Arc<T> > cloning large T |
| **Graceful shutdown** | Clean resource cleanup | Broadcast channel + select! |
| **Test with `#[tokio::test]`** | Async test support | Proper runtime setup |

---

## Common Gotchas

| ❌ Gotcha | ✅ Fix |
|---------|--------|
| **Not awaiting** | Add .await after async call |
| **Blocking the runtime** | Never use blocking ops in async (use tokio::task::block_in_place) |
| **Panic in task** | Task panics silently unless checked via join |
| **Unbounded channel growth** | Use bounded channels (buffer_size limit) |
| **Holding locks across await** | Release lock before await |
| **Race conditions** | Use proper sync primitives (Arc<Mutex>, channels) |

---

## Implementation Checklist

- [ ] Set up Tokio runtime (main attr or Runtime::new)
- [ ] Identify I/O-bound vs CPU-bound work
- [ ] Choose appropriate channel type (mpsc/broadcast/watch)
- [ ] Implement task spawning with error handling
- [ ] Add timeouts with select!
- [ ] Implement graceful shutdown pattern
- [ ] Test with async-aware test framework
- [ ] Profile for blocking calls
- [ ] Monitor task count (runtime.metrics())
- [ ] Document error handling strategy
