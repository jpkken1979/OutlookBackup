---
name: wasm-specialist
type: feature
description: WebAssembly guidance for compiling Rust/C++/Go to WASM, integrating with JavaScript runtimes, using WASI, optimizing bundle size, and deploying WASM to browsers, Node.js, or edge runtimes. Use when working on WASM architecture, wasm-pack/wasm-bindgen workflows, WASI execution, component model decisions, or performance-sensitive browser/edge modules.
---

# WebAssembly Specialist

## Purpose

Provide practical guidance for building, optimizing, and integrating WebAssembly modules across browser, server, and edge environments.

## When to Use

- Compiling Rust, C++, or Go to WASM
- Integrating WASM modules into JavaScript or TypeScript applications
- Designing WASI-based execution flows
- Evaluating component model or modular WASM architecture
- Optimizing bundle size or startup cost for WASM payloads
- Deploying WASM modules to edge runtimes

## Workflow

1. Confirm the runtime target: browser, Node.js, WASI, or edge
2. Pick the toolchain: `wasm-pack`, `wasm-bindgen`, raw target, or WASI
3. Define the JS/WASM boundary and exported API carefully
4. Optimize bundle size and debug-symbol strategy
5. Validate runtime compatibility before deployment

## Critical Patterns

- Design the exported API first; do not treat JS interop as an afterthought
- Distinguish browser-target WASM from WASI-target WASM early
- Optimize output (`wasm-opt`, stripping, compression) as part of the workflow
- Prefer explicit integration and deployment strategy for edge runtimes

## Examples

### Rust to WASM

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn fibonacci(n: u32) -> u32 {
    match n {
        0 => 0,
        1 => 1,
        _ => fibonacci(n - 1) + fibonacci(n - 2)
    }
}
```

```bash
wasm-pack build --target web
```

### JavaScript integration

```javascript
import init, { fibonacci } from './pkg/my_wasm.js';

await init();
console.log(fibonacci(10));
```

### WASI target

```rust
use std::io::{self, Read};

fn main() {
    let mut buffer = String::new();
    io::stdin().read_to_string(&mut buffer).unwrap();
    println!("Input: {}", buffer);
}
```

```bash
cargo build --target wasm32-wasi
```

### Bundle optimization

```bash
wasm-opt -Os -o output.wasm input.wasm
wasm-strip output.wasm
brotli output.wasm
```

## Resources

- Tooling: `wasm-pack`, `wasm-bindgen`, `wasm-opt`, `wit-bindgen`
- Runtime models: browser WASM, WASI, edge runtimes
- Architecture concepts: component model, JS/WASM boundaries, bundle optimization

## Validation

- Verify the chosen target matches the runtime environment
- Test the exported interface from the host language
- Check bundle size, startup time, and compression behavior
- Validate deployment assumptions for browser or edge environment
