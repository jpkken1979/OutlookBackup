---
name: makepad-skills
description: "Comprehensive guide for building high-performance native UIs in Rust using Makepad framework. Covers project setup, UI patterns, WGSL shader programming, desktop/mobile packaging, and debugging. Use when building native Rust applications, creating cross-platform UIs, implementing custom shaders for UI, packaging Makepad apps, developing performant desktop UIs, or troubleshooting Makepad rendering issues."
source: "https://github.com/ZhangHanDong/makepad-skills"
risk: safe
user-invocable: true
type: feature
---

# Makepad: High-Performance Native UI in Rust

Build fast, responsive user interfaces for desktop and mobile using Makepad's GPU-accelerated renderer and Rust's safety guarantees.

## What Makepad Is (and Isn't)

**Makepad** = Immediate-mode UI framework + WGSL shader language + GPU rendering

| Aspect | Makepad | Web (Electron/Tauri) |
|--------|---------|----------------------|
| Performance | GPU-accelerated, 60+ FPS @ startup | CPU-bound, initial load overhead |
| Native feel | Native look & feel | Approximates native |
| Shader support | Full WGSL support | CSS only |
| Bundle size | Small (few MB) | 100+ MB with runtime |
| Learning curve | Steep (Rust + shaders) | Shallow (web devs) |

**Use Makepad when**: Performance matters, custom visuals/shaders, tiny bundle, native feel.
**Avoid Makepad if**: Need web-standard components, team is JavaScript-focused.

## Project Setup

### 1. Environment

```bash
# Install Rust (latest stable)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update

# Clone Makepad
git clone https://github.com/makepad/makepad.git
cd makepad

# Build development environment
cargo build --release
```

### 2. New Project Structure

```
my-makepad-app/
├── Cargo.toml               # Rust dependencies
├── src/
│   ├── main.rs              # App entry point
│   ├── ui/                  # UI modules
│   │   ├── mod.rs
│   │   └── widgets.rs
│   └── shaders/             # WGSL shaders (optional)
│       └── custom.wgsl
└── resources/               # Images, fonts, assets
```

## Core Patterns

### Pattern 1: Basic Window & Widgets

```rust
// Immediate-mode: describe UI, Makepad handles rendering
app_main!(app, {
    Window::default(
        BoxLayout::default().with_direction(Direction::Column), [
            Label::default().with_text("Hello, Makepad!"),
            Button::default().with_text("Click me"),
        ]
    )
})
```

### Pattern 2: State Management

```rust
// State flows down, events flow up (elm-like)
#[derive(Clone, Default)]
struct AppState {
    counter: i32,
}

// On event:
match event {
    ButtonClicked => {
        state.counter += 1;
        redraw()
    }
}
```

### Pattern 3: Custom Shaders (WGSL)

```wgsl
// my-shader.wgsl
@fragment
fn main(in: FragmentInput) -> @location(0) vec4<f32> {
    let color = vec4(sin(in.pos.x), cos(in.pos.y), 0.5, 1.0);
    return color;
}
```

## Performance Optimization

| Issue | Cause | Fix |
|-------|-------|-----|
| Frame drops (< 60 FPS) | Over-complex layout recalculation | Memoize layout, use Quad instead of nested widgets |
| Shader artifacts | WGSL precision issues | Use f32 explicitly, test on target GPU |
| High memory | Uncached textures | Implement texture caching layer |
| Slow shader compilation | Complex shaders | Profile with `wgpu::trace`, simplify |

## Packaging & Distribution

### Desktop (macOS, Linux, Windows)

```bash
# Build release
cargo build --release

# Binary at: target/release/my-makepad-app
# Size: 5-15 MB (vs 150+ MB Electron)
```

### Mobile (iOS, Android)

```bash
# iOS
cargo build --target aarch64-apple-ios

# Android (requires Android SDK)
cargo build --target aarch64-linux-android
```

## Debugging Checklist

- [ ] Shader compiles (wgpu errors in console)
- [ ] Layout not overlapping (use Inspect tool in Makepad Studio)
- [ ] Assets loading correctly (check resource paths)
- [ ] Event handlers firing (add debug logging)
- [ ] GPU memory limits (test on lower-spec devices)

## Troubleshooting Common Issues

| Problem | Diagnostic | Solution |
|---------|-----------|----------|
| Blank window | Shader compilation failed | Check wgpu console errors |
| UI elements invisible | Layout outside viewport | Debug with Inspector, check margins |
| Slow rendering | Inefficient shader or layout | Profile with Makepad's performance tools |
| Won't compile | Missing Rust toolchain | `rustup update`, check MSRV |

## Resources & Further Learning

- **Official Docs**: The Makepad Book (in repo)
- **Examples**: `/examples/` folder in Makepad repository
- **Shader Reference**: WGSL Spec (W3C standard)
- **Performance**: GPU profiling tools (RenderDoc for shaders)

See [source repository](https://github.com/ZhangHanDong/makepad-skills) for complete tutorials and starter templates.
