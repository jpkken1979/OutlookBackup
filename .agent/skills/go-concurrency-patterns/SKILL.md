---
type: feature
name: go-concurrency-patterns
description: "Master Go concurrency with goroutines, channels, sync primitives, and context patterns. Covers goroutine lifecycle management, unbuffered/buffered channels, fan-out/fan-in patterns, worker pools, pipelines, context cancellation, graceful shutdown, race condition detection, and deadlock prevention. Includes patterns for concurrent map access (sync.Map), mutex locking, atomic operations, error handling in concurrent code, and timeout management. Use when building concurrent services, implementing worker pools, managing goroutine resources, handling graceful shutdown, debugging race conditions, or coordinating work across multiple goroutines."
---

# Go Concurrency Patterns

Master goroutines, channels, and synchronization primitives for building scalable concurrent systems in Go.

---

## Core Concepts: Concurrency vs Parallelism

| Aspect | Concurrency | Parallelism |
|--------|-------------|-------------|
| **Definition** | Multiple tasks interleaved | Multiple tasks simultaneously |
| **CPU Cores** | 1+ | 2+ (requires) |
| **Go Runtime** | Native (GOMAXPROCS) | Limited by cores |
| **Use Case** | I/O bound (networking, files) | CPU bound (computation) |
| **Go Tool** | Goroutines + channels | `runtime.NumCPU()` workers |

---

## Pattern 1: Goroutine Basics & Lifecycle

### Creating & Managing Goroutines

```go
package main

import (
    "fmt"
    "sync"
    "time"
)

// ❌ ANTI-PATTERN: Fire and forget (no synchronization)
func badExample() {
    go func() {
        fmt.Println("Goroutine started")
        time.Sleep(1 * time.Second)
        fmt.Println("Goroutine done")
    }()
    // Main exits immediately - goroutine may not complete
}

// ✅ CORRECT: Use WaitGroup to wait for completion
func goodExample() {
    var wg sync.WaitGroup

    for i := 0; i < 5; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            fmt.Printf("Worker %d starting\n", id)
            time.Sleep(100 * time.Millisecond)
            fmt.Printf("Worker %d done\n", id)
        }(i)
    }

    wg.Wait()  // Block until all goroutines complete
}

// Goroutine resource limits
func managedGoroutines(maxWorkers int, tasks []Task) {
    semaphore := make(chan struct{}, maxWorkers)
    var wg sync.WaitGroup

    for _, task := range tasks {
        wg.Add(1)
        go func(t Task) {
            defer wg.Done()
            semaphore <- struct{}{}        // Acquire slot
            defer func() { <-semaphore }() // Release slot

            t.Execute()
        }(task)
    }

    wg.Wait()
}
```

---

## Pattern 2: Channel Communication

### Unbuffered vs Buffered Channels

```go
// Unbuffered: Send blocks until receive (synchronous handoff)
func unbufferedExample() {
    ch := make(chan int)  // Unbuffered

    go func() {
        ch <- 42  // Blocks until main receives
    }()

    value := <-ch
    fmt.Println(value)  // Prints: 42
}

// Buffered: Send non-blocking until buffer full
func bufferedExample() {
    ch := make(chan int, 3)  // Buffer 3 items

    ch <- 1  // Non-blocking (buffer has space)
    ch <- 2
    ch <- 3
    // ch <- 4  // Would block here (buffer full)

    fmt.Println(<-ch)  // 1
    fmt.Println(<-ch)  // 2
    fmt.Println(<-ch)  // 3
}

// Direction channels: Send-only, receive-only
func directionExample(sendCh chan<- int, recvCh <-chan int) {
    sendCh <- 42        // Compiler error if trying to receive
    value := <-recvCh   // Compiler error if trying to send
}

// Close to signal completion
func closeChannelExample() {
    ch := make(chan int, 5)

    // Send some values
    for i := 1; i <= 5; i++ {
        ch <- i
    }
    close(ch)  // Signal no more sends

    // Receive until closed
    for value := range ch {
        fmt.Println(value)
    }
}
```

---

## Pattern 3: Fan-Out / Fan-In

### Distributing Work & Collecting Results

```go
// Fan-Out: Distribute work to multiple workers
func fanOut(jobs <-chan Job, numWorkers int) <-chan Result {
    results := make(chan Result, numWorkers)
    var wg sync.WaitGroup

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobs {
                results <- process(job)
            }
        }()
    }

    // Close results when all workers done
    go func() {
        wg.Wait()
        close(results)
    }()

    return results
}

// Fan-In: Merge results from multiple sources
func fanIn(channels ...<-chan Result) <-chan Result {
    results := make(chan Result)
    var wg sync.WaitGroup

    for _, ch := range channels {
        wg.Add(1)
        go func(c <-chan Result) {
            defer wg.Done()
            for result := range c {
                results <- result
            }
        }(ch)
    }

    go func() {
        wg.Wait()
        close(results)
    }()

    return results
}

// Practical example: Process multiple sources
func main() {
    ch1 := generateData(1)
    ch2 := generateData(2)

    merged := fanIn(ch1, ch2)
    for result := range merged {
        fmt.Println(result)
    }
}
```

---

## Pattern 4: Worker Pool with Queue

### Resource-Efficient Task Processing

```go
type Task interface {
    Execute() error
}

type Worker struct {
    id    int
    jobs  <-chan Task
    wg    *sync.WaitGroup
}

func (w *Worker) Start() {
    defer w.wg.Done()

    for job := range w.jobs {
        if err := job.Execute(); err != nil {
            fmt.Printf("Worker %d: error - %v\n", w.id, err)
        }
    }
}

func NewWorkerPool(numWorkers int, jobs <-chan Task) {
    var wg sync.WaitGroup

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        worker := Worker{id: i, jobs: jobs, wg: &wg}
        go worker.Start()
    }

    wg.Wait()
}

// Usage
func main() {
    jobs := make(chan Task, 100)

    // Start pool with 10 workers
    go NewWorkerPool(10, jobs)

    // Send tasks
    for _, task := range allTasks {
        jobs <- task
    }
    close(jobs)
}
```

---

## Pattern 5: Context-Based Cancellation

### Graceful Shutdown & Timeout Handling

```go
import "context"

// Timeout pattern
func fetchWithTimeout(ctx context.Context, url string) (string, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    // Request respects context
    req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    resp, err := http.DefaultClient.Do(req)
    // Returns error if context deadline exceeded
    return resp.Body, err
}

// Cancellation propagation
func processWithCancellation(ctx context.Context, items []Item) {
    var wg sync.WaitGroup

    for _, item := range items {
        wg.Add(1)
        go func(i Item) {
            defer wg.Done()

            select {
            case <-ctx.Done():
                fmt.Println("Cancelled:", ctx.Err())
                return
            default:
                i.Process()
            }
        }(item)
    }

    wg.Wait()
}

// Graceful shutdown example
func gracefulShutdown(server *http.Server) {
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

    <-sigChan  // Wait for signal

    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    if err := server.Shutdown(ctx); err != nil {
        fmt.Println("Shutdown error:", err)
    }
}
```

---

## Pattern 6: Pipeline Pattern

### Stage-Based Data Processing

```go
// Stage 1: Generate numbers
func generate(ctx context.Context, nums ...int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for _, n := range nums {
            select {
            case out <- n:
            case <-ctx.Done():
                return
            }
        }
    }()
    return out
}

// Stage 2: Square numbers
func square(ctx context.Context, in <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for n := range in {
            select {
            case out <- n * n:
            case <-ctx.Done():
                return
            }
        }
    }()
    return out
}

// Stage 3: Print results
func main() {
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    // Build pipeline
    numbers := generate(ctx, 2, 3, 4)
    squares := square(ctx, numbers)

    for result := range squares {
        fmt.Println(result)  // 4, 9, 16
    }
}
```

---

## Pattern 7: Safe Concurrent Map Access

### sync.Map vs Mutex

```go
// ❌ NOT THREAD-SAFE
var unsafeMap = make(map[string]int)

// ✅ MUTEX-PROTECTED
type SafeMap struct {
    mu    sync.RWMutex
    data  map[string]int
}

func (m *SafeMap) Get(key string) int {
    m.mu.RLock()
    defer m.mu.RUnlock()
    return m.data[key]
}

func (m *SafeMap) Set(key string, value int) {
    m.mu.Lock()
    defer m.mu.Unlock()
    m.data[key] = value
}

// ✅ SYNC.MAP (for mostly-read workloads)
func syncMapExample() {
    var m sync.Map

    // Store
    m.Store("key1", 100)

    // Load
    if value, ok := m.Load("key1"); ok {
        fmt.Println(value)
    }

    // LoadOrStore (atomic)
    actual, _ := m.LoadOrStore("key2", 200)
    fmt.Println(actual)

    // Delete
    m.Delete("key1")
}
```

---

## Race Condition Detection

### Finding Concurrency Bugs

```bash
# Build with race detector
go build -race ./cmd/myapp

# Run tests with race detector
go test -race ./...

# Run live with race detector
go run -race main.go
```

### Example Bug Detected

```go
// ❌ RACE CONDITION
var counter int

func increment() {
    counter++  // Read-modify-write not atomic
}

// ✅ FIXED with sync/atomic
var counter int64

func increment() {
    atomic.AddInt64(&counter, 1)
}
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Always use WaitGroup** | Ensure goroutines complete | `defer wg.Done()` in every goroutine |
| **Close channels from sender** | Signal completion | Only sender closes, never receiver |
| **Use context for cancellation** | Graceful shutdown | Pass context through call stack |
| **Buffer channels carefully** | Avoid deadlocks | Unbuffered for sync, buffered for async |
| **Limit goroutine count** | Prevent resource exhaustion | Use semaphore or worker pool |
| **Use sync.Map for concurrent reads** | Performance | More efficient than mutex for read-heavy |
| **Test with `-race` flag** | Catch race conditions | Always test concurrent code with race detector |
| **Avoid nested locks** | Prevent deadlocks | Establish lock ordering |
| **Use `select` with default** | Non-blocking send/receive | `select { case ch <- v: default: }` |

---

## Common Pitfalls & Solutions

| ❌ Pitfall | ✅ Solution |
|-----------|-----------|
| **Goroutine leak (fire & forget)** | Always track with WaitGroup or context |
| **Send on closed channel** | Only sender closes; receiver uses `ok` in range |
| **Deadlock (circular wait)** | Use context timeout, establish lock order |
| **Race conditions** | Test with `go test -race`, use atomic ops |
| **Unbounded channel growth** | Buffer or use semaphore to limit senders |
| **Goroutine not receiving from channel** | Use non-blocking send: `select { case: default }` |

---

## Implementation Checklist

- [ ] Choose concurrency model (goroutines, channels, callbacks)
- [ ] Use WaitGroup for goroutine lifecycle
- [ ] Implement channel-based communication
- [ ] Add context for cancellation/timeout
- [ ] Create worker pool if many tasks
- [ ] Test with `-race` flag
- [ ] Implement graceful shutdown
- [ ] Monitor goroutine count (`runtime.NumGoroutine()`)
- [ ] Document synchronization strategy
- [ ] Stress test with high load
