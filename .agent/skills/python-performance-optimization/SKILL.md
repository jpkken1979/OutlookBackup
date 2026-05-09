---
name: python-performance-optimization
description: Profile and optimize Python code using cProfile, memory profilers, and performance best practices. Reduce latency, memory leaks, and CPU usage through systematic profiling and optimization.
type: feature
category: performance
version: 2.1.0
tags:
---
  - python
  - performance
  - profiling
  - cprofile
  - memory-optimization
  - concurrency
requires:
  python_modules:
    - cProfile
    - memory_profiler
    - line_profiler
  optional:
    - py_spy
    - scalene
    - numpy
    - numba
triggers:
  - "slow python|performance bottleneck"
  - "memory leak|high cpu|profiling"
  - "optimize python|speed up code"
---

# Python Performance Optimization

Systematic profiling, analyzing, and optimizing Python code for better performance, throughput, and resource efficiency. Master CPU profiling, memory optimization, and concurrency patterns.

## Use this skill when

- Identifying performance bottlenecks in Python applications
- Reducing application latency and response times
- Optimizing CPU-intensive operations
- Reducing memory consumption and detecting memory leaks
- Improving database query performance (connection pooling)
- Optimizing I/O operations and concurrency
- Speeding up data processing pipelines
- Implementing high-performance algorithms
- Profiling production applications without stopping them

## Do not use this skill when

- The task is unrelated to Python performance
- Python is not the bottleneck (infrastructure, network, database)
- Profiling will disrupt critical production systems

## Rule #1: Measure Before Optimizing

**Profile, don't guess.** 80% of execution time is in 20% of code.

```python
import cProfile
import pstats
from pstats import SortKey

def slow_function():
    # Your code here
    pass

# Method 1: Profiling with cProfile
cProfile.run('slow_function()', 'output.prof')

# View results
prof = pstats.Stats('output.prof')
prof.sort_stats(SortKey.CUMULATIVE).print_stats(10)
# Shows top 10 functions by cumulative time
```

## CPU Profiling Strategies

### 1. cProfile (Built-in, Full Program)

```python
# Profile entire script
import cProfile

cProfile.run('main()', sort='cumtime')

# Output format:
# ncalls      → Number of times called
# tottime     → Total time in this function (excluding subfunctions)
# cumtime     → Cumulative time (including subfunctions)
# filename:lineno(function)
```

**Example output interpretation:**
```
  10   10    0.005    0.0005    0.050    0.0050 my_module.py:25(slow_function)
                                   ↑        ↑
                            tottime    cumtime
```

### 2. line_profiler (Line-by-Line)

```python
from line_profiler import LineProfiler

@profile  # Add this decorator to function
def slow_function():
    x = sum(range(1000000))  # This line is slow
    return x

# Run: kernprof -l -v script.py
# Shows time spent on each line
```

### 3. memory_profiler (Memory Consumption)

```python
from memory_profiler import profile

@profile
def memory_intensive():
    large_list = [i for i in range(100000)]  # Memory spike here
    return sum(large_list)

# Run: python -m memory_profiler script.py
# Shows memory usage per line in MB
```

### 4. py-spy (Production Profiling)

```bash
# Attach to running process (no code changes needed!)
py-spy record -o profile.svg -p <PID>

# Generates flame graph (visual profile)
```

## CPU Optimization Patterns

### 1. Avoid String Concatenation in Loops

**Bad (O(n²) complexity):**
```python
result = ""
for item in items:
    result = result + str(item)  # Creates new string each iteration
```

**Good (O(n) complexity):**
```python
result = "".join(str(item) for item in items)  # Single allocation
```

### 2. Use List Comprehensions (5-10x faster than loops)

**Slow:**
```python
result = []
for x in items:
    if x > 10:
        result.append(x * 2)
```

**Fast:**
```python
result = [x * 2 for x in items if x > 10]
```

### 3. Cache Function Results (Memoization)

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_function(x):
    return x ** 2  # Computed once per unique x
```

### 4. Use Generators (Lazy Evaluation)

**Memory-heavy (loads all in memory):**
```python
def get_all_numbers():
    return [x for x in range(1000000)]  # ~40MB in memory
```

**Efficient (streaming):**
```python
def get_all_numbers():
    for x in range(1000000):
        yield x  # No memory overhead
```

### 5. Vectorization with NumPy (100x faster for math)

**Python loop (slow):**
```python
result = []
for x in range(1000000):
    result.append(x ** 2)
```

**NumPy (fast):**
```python
import numpy as np
x = np.arange(1000000)
result = x ** 2  # Vectorized operation
```

### 6. JIT Compilation with Numba (GPU-like speeds)

```python
from numba import jit

@jit(nopython=True)  # Compile to machine code
def compute(n):
    result = 0
    for i in range(n):
        result += i
    return result

# First call: 100ms (compilation)
# Subsequent calls: <1ms (compiled)
```

## Memory Optimization Patterns

### 1. Use `__slots__` to Reduce Memory

```python
# Bad: Each instance has __dict__ (~240 bytes overhead)
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Good: Fixed attributes only
class Point:
    __slots__ = ['x', 'y']
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Memory savings: 100k instances = ~24MB saved
```

### 2. Release Large Objects Explicitly

```python
# Bad: Object stays in memory until function ends
def process_large_file():
    data = load_large_file()  # 1GB
    result = analyze(data)
    return result

# Good: Explicit cleanup
def process_large_file():
    data = load_large_file()
    result = analyze(data)
    del data  # Free 1GB immediately
    return result
```

### 3. Use Weak References for Circular Dependencies

```python
import weakref

class Node:
    def __init__(self, parent=None):
        self.parent = weakref.ref(parent) if parent else None
        self.children = []

# Allows garbage collection (no circular reference)
```

### 4. Stream Large Files (Don't Load in Memory)

**Bad (entire file in RAM):**
```python
with open('huge_file.csv') as f:
    data = f.read()  # 10GB file → 10GB memory
```

**Good (process line-by-line):**
```python
with open('huge_file.csv') as f:
    for line in f:  # Only 1 line in memory at a time
        process(line)
```

## Concurrency Patterns (I/O Optimization)

### 1. Asyncio (Concurrent I/O)

```python
import asyncio

async def fetch_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def fetch_all(urls):
    tasks = [fetch_url(url) for url in urls]
    return await asyncio.gather(*tasks)  # Concurrent!

# Sequential: 10 URLs × 1s = 10s
# Asyncio: 10 URLs in parallel = 1s
```

### 2. Threading (Bypass GIL for I/O)

```python
from concurrent.futures import ThreadPoolExecutor

def download_file(url):
    # GIL released during I/O
    return requests.get(url).content

with ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(download_file, urls)

# 10 threads download in parallel (GIL doesn't block I/O)
```

### 3. Multiprocessing (Escape GIL for CPU)

```python
from multiprocessing import Pool

def expensive_cpu_task(x):
    return x ** 2  # CPU-bound

with Pool(processes=4) as pool:
    results = pool.map(expensive_cpu_task, range(1000))

# 4 processes run in parallel on 4 cores (true parallelism)
```

### 4. GIL (Global Interpreter Lock) - When It Matters

```python
# CPU-bound task → GIL bottleneck (single-threaded)
def cpu_task():
    return sum(range(100000000))  # Single core: 2s

# I/O-bound task → GIL released during I/O (threads work)
def io_task():
    requests.get('http://example.com')  # All cores can work
```

## Database Connection Optimization

### 1. Connection Pooling (Reuse Connections)

```python
from sqlalchemy import create_engine

# Create pool of 5-20 connections (not 1 per query!)
engine = create_engine(
    'postgresql://user:pass@localhost/db',
    pool_size=10,
    max_overflow=20,  # Additional connections if needed
    pool_pre_ping=True,  # Test connection before using
)

# Reuse: 100 queries with 10 connections = 10x faster
```

### 2. Batch Inserts (Not Row-by-Row)

**Slow (1 insert per network round-trip):**
```python
for item in items:
    cursor.execute("INSERT INTO table VALUES (?)", item)
conn.commit()
```

**Fast (bulk insert):**
```python
cursor.executemany("INSERT INTO table VALUES (?)", items)
conn.commit()
# 1000 rows: 1000ms → 10ms (100x faster)
```

## Performance Checklist

- [ ] **PROFILE**: Use cProfile to identify bottlenecks
- [ ] **CPU**: Use list comprehensions, avoid string concatenation
- [ ] **MEMORY**: Stream large files, use generators, release objects
- [ ] **CONCURRENCY**: Use asyncio for I/O, multiprocessing for CPU
- [ ] **CACHING**: Memoize expensive functions
- [ ] **VECTORIZE**: Use NumPy for numeric operations
- [ ] **DATABASE**: Use connection pooling, batch inserts
- [ ] **MONITOR**: Track memory usage and response times

## Anti-Patterns

❌ Premature optimization (optimize before profiling)
❌ Threading for CPU-bound tasks (GIL prevents parallelism)
❌ Row-by-row database operations (use bulk operations)
❌ Holding large objects indefinitely (release after use)
❌ Ignoring memory leaks (use memory_profiler)

## Best Practices

✅ **Measure first** — Profile before optimizing
✅ **Focus on hot spots** — 80% of time in 20% of code
✅ **Use appropriate tools** — Asyncio for I/O, multiprocessing for CPU
✅ **Monitor production** — Use py-spy for live profiling
✅ **Test with real data** — Dev data hides performance issues

## Profiling Tools Reference

| Tool | Use Case | Command |
|------|----------|---------|
| **cProfile** | Full program profiling | `python -m cProfile -s cumtime script.py` |
| **line_profiler** | Line-by-line analysis | `kernprof -l -v script.py` |
| **memory_profiler** | Memory per line | `python -m memory_profiler script.py` |
| **py-spy** | Production profiling | `py-spy record -p <PID>` |
| **scalene** | CPU + memory + GPU | `scalene script.py` |

## Resources

- **Detailed patterns**: See `resources/implementation-playbook.md`
- **Python docs**: https://docs.python.org/3/library/cProfile.html
- **Real Python**: https://realpython.com/python-concurrency/
- **Numba docs**: https://numba.readthedocs.io/
