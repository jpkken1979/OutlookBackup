---
name: webgpu-expert
type: feature
description: WebGPU guidance for compute shaders, render pipelines, WGSL, GPU performance, and browser-side ML/graphics workloads. Use when designing WebGPU architecture, writing WGSL shaders, building compute or render pipelines, optimizing CPU/GPU transfer, or integrating WebGPU into browser-based graphics and ML applications.
---

# WebGPU Expert

## Purpose

Provide practical guidance for WebGPU architecture, shader authoring, compute/render pipelines, and performance-sensitive browser GPU workloads.

## When to Use

- Building WebGPU-powered graphics or compute features
- Writing WGSL shaders
- Designing compute pipelines for browser ML
- Building render pipelines beyond simple canvas rendering
- Optimizing GPU transfers and execution patterns
- Integrating low-level GPU workflows into web apps

## Workflow

1. Confirm whether the task is graphics, compute, or hybrid
2. Initialize adapter/device and define the resource model
3. Design the WGSL shader interface and bindings
4. Build render or compute pipelines explicitly
5. Validate CPU/GPU synchronization and data transfer cost
6. Test compatibility and performance in the target browsers

## Critical Patterns

- Treat GPU/CPU data movement as a first-class performance constraint
- Keep shader bindings and buffer layouts explicit
- Separate compute and render concerns when possible
- Validate browser/device support before committing to architecture

## Examples

### Compute pipeline

```javascript
const adapter = await navigator.gpu.requestAdapter();
const device = await adapter.requestDevice();

const shaderModule = device.createShaderModule({
  code: `
    @compute @workgroup_size(64)
    fn main(@builtin(global_invocation_id) id: vec3<u32>) {
      // Compute logic
    }
  `
});

const pipeline = device.createComputePipeline({
  layout: 'auto',
  compute: { module: shaderModule, entryPoint: 'main' }
});
```

### Render pipeline

```javascript
const pipeline = device.createRenderPipeline({
  layout: 'auto',
  vertex: {
    module: shaderModule,
    entryPoint: 'vertexMain',
    buffers: [vertexBufferLayout]
  },
  fragment: {
    module: shaderModule,
    entryPoint: 'fragmentMain',
    targets: [{ format: presentationFormat }]
  }
});
```

### Browser ML with compute shaders

```javascript
const matmulShader = `
@group(0) @binding(0) var<storage, read> A: array<f32>;
@group(0) @binding(1) var<storage, read> B: array<f32>;
@group(0) @binding(2) var<storage, read_write> C: array<f32>;

@compute @workgroup_size(8, 8)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let row = gid.x;
  let col = gid.y;
  // Matrix multiply logic
}
`;
```

## Resources

- API surfaces: WebGPU, WGSL, device/pipeline/buffer model
- Workload types: rendering, compute, browser ML
- Integration concerns: browser support, framework integration, performance tuning

## Validation

- Verify adapter/device availability on target browsers
- Confirm shader bindings and buffer layouts are correct
- Measure CPU/GPU transfer cost and pipeline behavior
- Validate the workload under realistic browser/device conditions
