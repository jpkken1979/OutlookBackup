---
name: memory-safety-patterns
description: "Master memory-safe programming with RAII, ownership semantics, smart pointers, and resource management across Rust, C++, and C. Covers memory errors (use-after-free, double-free, memory leaks), stack vs heap allocation, RAII pattern implementation, smart pointers (unique_ptr, shared_ptr, Box, Rc), borrow checking, lifetime management, and resource cleanup. Includes patterns for file handles, database connections, memory pools, custom allocators, and memory safety tools (valgrind, ASAN, Miri). Use when writing safe systems code, managing limited resources, preventing memory vulnerabilities, building embedded systems, or debugging memory issues and crashes."
type: feature
---

# Memory Safety Patterns: Systems Programming

Master RAII, ownership, and smart pointers to prevent memory errors across Rust, C++, and C.

---

## Memory Errors: The Problem Space

| Error | Cause | Consequence | Prevention |
|-------|-------|-------------|-----------|
| **Use-After-Free** | Access freed memory | Crash, security exploit | Ownership checking |
| **Double-Free** | Free same memory twice | Crash, heap corruption | Move semantics |
| **Buffer Overflow** | Write past bounds | Memory corruption | Bounds checking |
| **Dangling Pointer** | Pointer to freed memory | Undefined behavior | Lifetime tracking |
| **Memory Leak** | Forget to free | Exhaust resources | RAII, GC |
| **Null Dereference** | Access null pointer | Crash | Optional/Result types |

---

## Pattern 1: Stack vs Heap Allocation

### Choosing When to Allocate Where

```rust
// ✅ STACK: Known size, automatic cleanup
fn stack_allocation() {
    let small_array: [i32; 100] = [0; 100];      // On stack
    let tuple: (i32, String, bool) = (1, "hi".to_string(), false);  // On stack

    println!("{:?}", small_array);  // Valid - auto cleanup when scope ends
}

// ❌ STACK: Large data causes stack overflow
fn dangerous_stack() {
    let huge_array: [i32; 1_000_000] = [0; 1_000_000];  // Stack overflow!
}

// ✅ HEAP: Unknown size, manual cleanup
fn heap_allocation() {
    let dynamic_vec: Vec<i32> = vec![1, 2, 3, 4, 5];  // Heap
    let dynamic_string: String = "hello".to_string(); // Heap

    // Cleanup happens automatically when vec/string drop
}

// Stack small, unknown size → Box (heap)
fn box_example() {
    let boxed_int: Box<i32> = Box::new(42);  // Heap
    println!("{}", boxed_int);  // Dereference automatically
    // Freed when boxed_int goes out of scope
}
```

---

## Pattern 2: RAII (Resource Acquisition Is Initialization)

### Automatic Resource Cleanup

```rust
use std::fs::File;
use std::io::{Read, Write};

// C++ Example
class FileHandler {
public:
    FileHandler(const std::string& filename) {
        file = fopen(filename.c_str(), "r");  // Resource acquired
        if (!file) throw std::runtime_error("Failed to open");
    }

    ~FileHandler() {
        if (file) fclose(file);  // Resource released (guaranteed)
    }

private:
    FILE* file;
};

// Rust equivalent (automatic via Drop)
struct FileHandler {
    file: File,
}

impl FileHandler {
    fn new(filename: &str) -> std::io::Result<Self> {
        Ok(FileHandler {
            file: File::open(filename)?,  // Resource acquired
        })
    }
    // Drop trait automatically implemented - file closed when dropped
}

// Usage
fn process_file() -> std::io::Result<()> {
    let handler = FileHandler::new("data.txt")?;
    // handler.file is guaranteed to close when this function exits
    Ok(())
}
```

---

## Pattern 3: Ownership & Borrowing (Rust)

### Preventing Use-After-Free at Compile Time

```rust
// ❌ Ownership violation (won't compile)
fn bad_ownership() {
    let s1 = String::from("hello");
    let s2 = s1;  // s1 moved to s2
    println!("{}", s1);  // ERROR: value used after move
}

// ✅ MOVE SEMANTICS: Transfer ownership
fn move_example() {
    let s1 = String::from("hello");
    let s2 = s1;  // Ownership moves to s2, s1 invalid
    println!("{}", s2);  // OK: s2 is owner
    // s2 dropped, memory freed once
}

// ✅ BORROWING: Immutable reference
fn borrow_example() {
    let s = String::from("hello");
    let len = calculate_length(&s);  // Borrow s
    println!("'{}' has length {}", s, len);  // s still valid
}

fn calculate_length(s: &String) -> usize {
    s.len()
    // s borrowed, not moved
}

// ✅ MUTABLE BORROW: Exclusive access
fn mutable_borrow() {
    let mut s = String::from("hello");
    append_world(&mut s);  // Mutable borrow
    println!("{}", s);
}

fn append_world(s: &mut String) {
    s.push_str(" world");
}

// ❌ WON'T COMPILE: Can't have mutable + immutable borrows
fn invalid_borrows() {
    let mut s = String::from("hello");
    let r1 = &s;      // Immutable borrow
    let r2 = &mut s;  // ERROR: Can't borrow as mutable while immutable borrow exists
}
```

---

## Pattern 4: Smart Pointers

### Automatic Memory Management

```cpp
// C++ Smart Pointers

// std::unique_ptr: Single owner (move-only)
{
    std::unique_ptr<int> ptr1(new int(42));
    std::unique_ptr<int> ptr2 = std::move(ptr1);  // Move ownership
    // ptr1 is now null, ptr2 owns the memory
    // Memory freed when ptr2 destroyed
}

// std::shared_ptr: Reference counting (multiple owners)
{
    std::shared_ptr<int> ptr1 = std::make_shared<int>(42);
    std::shared_ptr<int> ptr2 = ptr1;  // Both own the memory
    // Reference count is 2
    // Memory freed only when both ptr1 and ptr2 destroyed
}

// std::weak_ptr: Non-owning reference (prevents circular references)
struct Node {
    int value;
    std::shared_ptr<Node> next;
    std::weak_ptr<Node> prev;  // Doesn't prevent node deletion
};
```

```rust
// Rust Smart Pointers

// Box<T>: Single owner on heap
fn box_example() {
    let boxed = Box::new(42);  // Allocate on heap
    let value = *boxed;        // Dereference
}  // boxed freed here

// Rc<T>: Reference counting (single-threaded)
use std::rc::Rc;

fn rc_example() {
    let data = Rc::new(vec![1, 2, 3]);
    let ref1 = Rc::clone(&data);   // Increment ref count
    let ref2 = Rc::clone(&data);   // Increment ref count
    // data, ref1, ref2 all point to same vector
    // Freed when all three dropped
}

// Arc<T>: Atomic reference counting (thread-safe)
use std::sync::Arc;

fn arc_example() {
    let data = Arc::new(vec![1, 2, 3]);
    let clone1 = Arc::clone(&data);
    // Safe to share across threads
}
```

---

## Pattern 5: Lifetime Management

### Ensuring References Are Valid

```rust
// ❌ Dangling reference (won't compile)
fn create_reference() -> &String {
    let s = String::from("hello");
    &s  // ERROR: returning reference to local variable
}

// ✅ Return owned value instead
fn return_owned() -> String {
    let s = String::from("hello");
    s  // Return ownership
}

// ✅ Lifetimes with references
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() {
        x  // Return ref with same lifetime as inputs
    } else {
        y
    }
}

// ✅ Struct with references (lifetime parameters)
struct Document<'a> {
    title: &'a str,
    content: &'a str,
}

fn process_doc<'a>(title: &'a str, content: &'a str) -> Document<'a> {
    Document { title, content }
    // All references must outlive the struct
}
```

---

## Pattern 6: Resource Pools & Custom Allocators

### Efficient Resource Reuse

```cpp
// C++ Object Pool: Reuse allocated objects
class ObjectPool {
    std::vector<std::unique_ptr<Resource>> available;
    std::vector<std::unique_ptr<Resource>> inUse;

public:
    std::shared_ptr<Resource> acquire() {
        if (!available.empty()) {
            auto resource = std::move(available.back());
            available.pop_back();
            inUse.push_back(std::move(resource));
            return std::make_shared<Resource>(*inUse.back());
        }
        return std::make_shared<Resource>();
    }

    void release(std::shared_ptr<Resource> resource) {
        auto it = std::find_if(
            inUse.begin(),
            inUse.end(),
            [&](const auto& r) { return r.get() == resource.get(); }
        );
        if (it != inUse.end()) {
            available.push_back(std::move(*it));
            inUse.erase(it);
        }
    }
};
```

```rust
// Rust Object Pool
struct ResourcePool {
    available: Vec<Resource>,
}

impl ResourcePool {
    fn acquire(&mut self) -> Option<Resource> {
        self.available.pop()  // Reuse if available
    }

    fn release(&mut self, resource: Resource) {
        self.available.push(resource);  // Return to pool
    }
}
```

---

## Pattern 7: Memory Safety Tools

### Detection & Debugging

```bash
# Valgrind (C/C++): Detect memory leaks
valgrind --leak-check=full ./my_program

# AddressSanitizer (ASAN): Detect heap issues
gcc -fsanitize=address -g my_program.c
./a.out

# Miri (Rust): Detect undefined behavior
cargo +nightly miri test

# Memory Profiler: Visualize allocations
valgrind --tool=massif ./program
ms_print massif.out.<pid>  # View graph

# LeakTracer: Real-time leak detection
export LD_PRELOAD=./LeakTracer.so
./program  # Shows allocations live
```

### Example: Using AddressSanitizer

```c
// buffer_overflow.c
#include <string.h>

int main() {
    char buffer[10];
    strcpy(buffer, "This is a very long string that overflows");  // BUG!
    return 0;
}

// Compile with ASAN
// gcc -fsanitize=address -g buffer_overflow.c -o prog
// Output: ==1234== ERROR: AddressSanitizer: stack-buffer-overflow
```

---

## Comparison: Language Safety by Design

| Language | Memory Management | Safety Guarantees | Performance |
|----------|-------------------|-------------------|-------------|
| **Rust** | Ownership + Borrow Checker | Compile-time checks, memory safe | Native |
| **C++** | Manual + Smart Pointers | Runtime checks | Native |
| **C** | Manual malloc/free | NO guarantees (your job) | Native |
| **Go** | Garbage Collector | Runtime GC | Slight overhead |
| **Python** | Reference Counting | High-level API | Interpreter |

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Use RAII** | Automatic cleanup | Constructor acquires, destructor releases |
| **Prefer stack** | Automatic, fast | Only use heap for dynamic size/large data |
| **Move semantics** | Efficient transfer | `std::move()` in C++, move by default in Rust |
| **Smart pointers** | Prevent leaks | `unique_ptr`, `shared_ptr`, Box, Rc, Arc |
| **Borrow instead of clone** | Efficiency | Use `&` instead of copying in Rust |
| **No circular references** | Prevent cycles | Use `weak_ptr` or design without cycles |
| **Test with sanitizers** | Find bugs early | ASAN, Valgrind, Miri |
| **Document lifetimes** | Clarity | Annotate lifetime parameters |

---

## Common Errors & Fixes

| ❌ Error | ✅ Fix |
|---------|--------|
| **Use-after-free** | Track ownership, use borrow checker |
| **Memory leak** | Use smart pointers (unique_ptr, Box) |
| **Double-free** | Don't manually free smart pointer |
| **Buffer overflow** | Use bounds-checked containers |
| **Dangling pointer** | Ensure referenced object outlives pointer |
| **Stack overflow** | Move large data to heap |
| **Circular references** | Use weak_ptr or redesign |

---

## Implementation Checklist

- [ ] Choose appropriate allocation strategy (stack vs heap)
- [ ] Implement RAII pattern for resource management
- [ ] Use smart pointers (no raw `new`/`delete`)
- [ ] Define clear ownership semantics
- [ ] Add lifetime annotations in Rust
- [ ] Test with memory safety tools (ASAN, Valgrind, Miri)
- [ ] Code review for memory safety
- [ ] Document resource lifetime expectations
- [ ] Monitor for memory leaks in production
- [ ] Create resource pools for reusable objects
