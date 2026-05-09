---
name: tauri-performance-optimization
description: "**Nombre:** tauri-performance-optimization"
type: feature
---

# Tauri Performance Optimization Skill

## Metadata

**Nombre:** tauri-performance-optimization
**Versión:** 1.0.0
**Tipo:** Performance Tuning
**Categoría:** Application Performance
**Enfoque:** Bundle size, Runtime performance, Memory efficiency

---

## Descripción

Skill que optimiza aplicaciones Tauri para máximo rendimiento:
- Minimización de bundle size (objetivo: < 600KB)
- Optimización de tiempo de arranque
- Memory profiling y leak detection
- IPC communication optimization
- Frontend performance tuning
- Rust backend optimization
- Cross-platform benchmarking

## Inputs

### Análisis Automático
```json
{
  "project_path": "string - Ruta al proyecto Tauri",
  "target_platforms": "array - ['windows', 'macos', 'linux']",
  "optimization_level": "enum - 'basic' | 'aggressive' | 'extreme' (default: 'aggressive')"
}
```

### Específico por Área
```json
{
  "area": "enum - 'bundle_size' | 'startup_time' | 'memory' | 'ipc_latency' | 'all'",
  "baseline_metrics": "object - Métricas actuales para comparación",
  "target_metrics": "object - Objetivos de optimización"
}
```

## Outputs

```json
{
  "current_metrics": {
    "bundle_size_windows": "number - MB",
    "bundle_size_macos": "number - MB",
    "startup_time": "number - ms",
    "memory_usage": "number - MB",
    "ipc_latency": "number - ms"
  },
  "optimization_recommendations": [
    {
      "area": "string - Área de optimización",
      "issue": "string - Problema identificado",
      "impact": "string - Impacto de aplicar optimización",
      "difficulty": "easy|medium|hard",
      "estimated_improvement": "number - % de mejora"
    }
  ],
  "optimizations_applied": [
    {
      "name": "string",
      "result": "string - Resultado obtenido",
      "file_path": "string - Archivos modificados"
    }
  ],
  "projected_metrics": {
    "bundle_size_windows": "number - MB estimado",
    "startup_time": "number - ms estimado",
    "memory_usage": "number - MB estimado"
  },
  "improvement_percentage": "number - 0-100%"
}
```

## Optimizaciones por Área

### 1. Bundle Size Optimization

**Objetivo:** < 600KB para aplicación mínima, < 2MB para aplicación promedio

**Técnicas:**

#### A. Dependency Analysis
```bash
# Identificar dependencias grandes
cargo tree --depth 1 | grep -E "kb|mb"

# Análisis de crate size
cargo bloat --release
```

**Recomendaciones:**
- Reemplazar `reqwest` por `curl-sys` si solo hace requests simples
- `serde_json` vs `simd-json` para parsing rápido
- `chrono` solo si necesita soporte timezone completo

#### B. Frontend Code Splitting
```typescript
// ❌ Bundle único enorme
import { HeavyComponent } from './components/HeavyComponent';

// ✅ Code splitting dinámico
const HeavyComponent = lazy(() => import('./components/HeavyComponent'));

// ✅ Tree-shake automático
export { utilA, utilB }; // Solo lo que se usa
```

#### C. Minification & Compression
```javascript
// vite.config.ts
export default {
  build: {
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['react', 'react-dom'],
          'utils': ['lodash', 'axios'],
        },
      },
    },
  },
};
```

#### D. Rust Binary Optimization
```toml
# Cargo.toml
[profile.release]
opt-level = 3              # Máxima optimización
lto = true                 # Link-time optimization
codegen-units = 1          # Mejor optimización (más lento compile)
strip = true               # Remover símbolos de debug
```

**Resultado esperado:**
- Windows: 40-50% reducción
- macOS: 35-45% reducción
- Linux: 30-40% reducción

### 2. Startup Time Optimization

**Objetivo:** < 500ms cold start, < 100ms warm start

**Técnicas:**

#### A. Lazy Initialization
```rust
use once_cell::sync::Lazy;

// ❌ Inicializa siempre
fn main() {
    let config = load_config(); // Tarda 200ms
    run_app(config);
}

// ✅ Inicializa solo cuando se necesita
static CONFIG: Lazy<Config> = Lazy::new(load_config);

#[tauri::command]
fn get_config() -> Config {
    CONFIG.clone()
}
```

#### B. Frontend Lazy Loading
```typescript
// Cargar componentes pesados solo cuando se necesiten
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage }))
);

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Suspense>
  );
}
```

#### C. Database Connection Pooling
```rust
use sqlx::SqlitePool;

// Crear pool una sola vez
let pool = SqlitePool::connect("sqlite://app.db").await?;

// Reutilizar conexiones
#[tauri::command]
async fn query_data(pool: State<'_, SqlitePool>) -> Result<Vec<Item>, String> {
    sqlx::query_as("SELECT * FROM items")
        .fetch_all(pool.inner())
        .await
        .map_err(|e| e.to_string())
}
```

**Resultado esperado:**
- Reducción startup: 40-60%
- Warm start mejorado: 80-90%

### 3. Memory Optimization

**Objetivo:** < 100MB idle, < 300MB normal usage

**Técnicas:**

#### A. Memory Leak Detection
```bash
# Valgrind para Linux
valgrind --leak-check=full ./target/release/app

# Profiling con perf
cargo build --release
perf record -g ./target/release/app
perf report
```

#### B. Efficient Data Structures
```rust
// ❌ Vec puede ser ineficiente
let mut items: Vec<Item> = Vec::new();

// ✅ Preallocate si conoces tamaño
let mut items: Vec<Item> = Vec::with_capacity(1000);

// ✅ Use iterator en lugar de clonar
items.iter().map(|item| process(item))

// ✅ Arc<Mutex<T>> para shared state
use std::sync::{Arc, Mutex};
let shared = Arc::new(Mutex::new(data));
```

#### C. String & Buffer Management
```rust
// ❌ Muchas allocaciones
let result = String::new();
result + "part1" + "part2" + "part3"; // 3 allocaciones

// ✅ Usar format! o escribir a buffer
let result = format!("{}{}{}","part1", "part2", "part3");

// ✅ Reutilizar buffer
let mut buffer = String::with_capacity(100);
write!(&mut buffer, "{}", data)?;
```

#### D. Garbage Collection Friendly
```typescript
// ❌ Referencias circulares
class Parent {
  child: Child;
  constructor() {
    this.child = new Child(this); // Referencia circular
  }
}

// ✅ Usar WeakMap para referencias
const parentMap = new WeakMap();
parentMap.set(child, parent); // Se garbage-recolecta automáticamente
```

**Resultado esperado:**
- Reducción memoria: 30-50%
- Cero memory leaks en monitoreo

### 4. IPC Communication Optimization

**Objetivo:** < 1ms latencia para comandos simples

**Técnicas:**

#### A. Serialization Optimization
```rust
// ❌ JSON puede ser lento para datos grandes
#[tauri::command]
fn process_large_data(data: Vec<LargeStruct>) -> Result<Vec<u8>, String> {
    // JSON serialization lento
    Ok(serde_json::to_vec(&result)?)
}

// ✅ Usar bincode para datos grandes
#[tauri::command]
fn process_large_data(data: Vec<u8>) -> Result<Vec<u8>, String> {
    let input: Vec<LargeStruct> = bincode::deserialize(&data)?;
    let result = process(input);
    Ok(bincode::serialize(&result)?)
}
```

#### B. Batching Operations
```typescript
// ❌ Múltiples IPC calls
for (const id of ids) {
    await invoke('process_item', { id }); // N calls
}

// ✅ Batch operación
const results = await invoke('process_items', { ids });
```

#### C. Streaming para Datos Grandes
```rust
use std::fs;

// ❌ Cargar todo en memoria
#[tauri::command]
fn read_large_file(path: String) -> Result<String, String> {
    fs::read_to_string(path).map_err(|e| e.to_string())
}

// ✅ Streaming con eventos
#[tauri::command]
async fn stream_large_file(
    path: String,
    window: tauri::Window,
) -> Result<(), String> {
    let file = fs::File::open(path)?;
    let reader = io::BufReader::new(file);

    for chunk in reader.lines() {
        window.emit("data_chunk", chunk?).ok();
    }

    Ok(())
}
```

**Resultado esperado:**
- Reducción latencia: 50-70%
- Mejor throughput para datos grandes

### 5. Frontend Performance

**Objetivo:** 60 FPS, Lighthouse > 90

**Técnicas:**

#### A. React Optimization
```typescript
// ✅ Memoization para prevenir re-renders
const MemoizedComponent = memo(Component);

// ✅ useCallback para funciones estables
const handleClick = useCallback(() => {
    // ...
}, [dependencies]);

// ✅ Virtual scrolling para listas grandes
import { FixedSizeList } from 'react-window';
<FixedSizeList height={600} itemCount={10000} itemSize={35}>
  {Row}
</FixedSizeList>
```

#### B. CSS Optimization
```css
/* ❌ Selector lento */
body div.container div.item { }

/* ✅ Selector directo y específico */
.item { }

/* ✅ Use transform para animaciones */
.animated {
    transform: translateX(0);
    transition: transform 300ms ease-out;
}

/* ❌ Evitar */
.animated {
    left: 0;
    transition: left 300ms;
}
```

#### C. Image Optimization
```typescript
// ✅ Lazy loading
<img src="image.jpg" loading="lazy" alt="..." />

// ✅ WebP con fallback
<picture>
    <source srcSet="image.webp" type="image/webp" />
    <img src="image.jpg" alt="..." />
</picture>

// ✅ Responsive images
<img
    srcSet="small.jpg 480w, medium.jpg 800w, large.jpg 1200w"
    sizes="(max-width: 600px) 480px, 800px"
    src="medium.jpg"
/>
```

**Resultado esperado:**
- FPS mejorado: 40→60 FPS
- Lighthouse score: +20-30 puntos

## Benchmark & Monitoring

```bash
# Generar reporte de optimización
python .agent/skills/tauri-performance-optimization/scripts/main.py \
  --project-path ./my-app \
  --area all \
  --generate-report

# Resultado: Reporte detallado con métricas y recomendaciones
```

## Checklist de Optimización

```
Bundle Size
[ ] Dependencies auditadas
[ ] Tree-shaking confirmado
[ ] Code splitting implementado
[ ] Minification activo
[ ] Compresión de assets
[ ] LTO habilitado en Rust
[ ] Símbolos de debug removidos

Startup Time
[ ] Lazy initialization implementada
[ ] Conexiones de BD pooled
[ ] Componentes frontend lazy-loaded
[ ] Service workers precacheados
[ ] Assets preloadados

Memory
[ ] Leak detection completado
[ ] Data structures optimizadas
[ ] Buffer reuse implementado
[ ] Garbage collection friendly

IPC Performance
[ ] Serialization optimizada
[ ] Batching implementado
[ ] Streaming para datos grandes
[ ] Error handling eficiente

Frontend
[ ] React memoization aplicada
[ ] Virtual scrolling para listas
[ ] CSS optimizado
[ ] Imágenes lazy-loadadas y responsive
```

## Herramientas Recomendadas

```toml
[dev-dependencies]
# Profiling
criterion = "0.5"
flamegraph = "0.10"

# Memory
valgrind = "0.1"
```

```json
{
  "devDependencies": {
    "lighthouse": "^11.0.0",
    "webpack-bundle-analyzer": "^4.10.0",
    "source-map-explorer": "^2.5.0"
  }
}
```

## Integración con Otros Agentes

- **tauri-architect** - Decisiones arquitectónicas
- **tauri-backend** - Optimización Rust
- **tauri-frontend** - Optimización JavaScript
- **performance-optimizer** - Profiling avanzado
- **test-engineer** - Tests de rendimiento

---

*Tauri Performance Optimization v1.0 - Elite Edition*
*Creado: 2026-02-03*
*Objetivo: 600KB bundles, 500ms cold start, 60 FPS runtime*
