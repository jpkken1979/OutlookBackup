---
name: react-ui-patterns
description: Modern React UI patterns for loading states, error handling, and data fetching. Use when building UI components, handling async data, or managing UI states.
type: feature
---

# React UI Patterns

## Core Principles

1. **Never show stale UI** - Loading spinners only when actually loading
2. **Always surface errors** - Users must know when something fails
3. **Optimistic updates** - Make the UI feel instant
4. **Progressive disclosure** - Show content as it becomes available
5. **Graceful degradation** - Partial data is better than no data

## Loading State Patterns

### The Golden Rule

**Show loading indicator ONLY when there's no data to display.**

```typescript
// CORRECT - Only show loading when no data exists
const { data, loading, error } = useGetItemsQuery();

if (error) return <ErrorState error={error} onRetry={refetch} />;
if (loading && !data) return <LoadingState />;
if (!data?.items.length) return <EmptyState />;

return <ItemList items={data.items} />;
```

```typescript
// WRONG - Shows spinner even when we have cached data
if (loading) return <LoadingState />; // Flashes on refetch!
```

### Loading State Decision Tree

```
Is there an error?
  → Yes: Show error state with retry option
  → No: Continue

Is it loading AND we have no data?
  → Yes: Show loading indicator (spinner/skeleton)
  → No: Continue

Do we have data?
  → Yes, with items: Show the data
  → Yes, but empty: Show empty state
  → No: Show loading (fallback)
```

### Skeleton vs Spinner

| Use Skeleton When | Use Spinner When |
|-------------------|------------------|
| Known content shape | Unknown content shape |
| List/card layouts | Modal actions |
| Initial page load | Button submissions |
| Content placeholders | Inline operations |

## Error Handling Patterns

### The Error Handling Hierarchy

```
1. Inline error (field-level) → Form validation errors
2. Toast notification → Recoverable errors, user can retry
3. Error banner → Page-level errors, data still partially usable
4. Full error screen → Unrecoverable, needs user action
```

### Always Show Errors

**CRITICAL: Never swallow errors silently.**

```typescript
// CORRECT - Error always surfaced to user
const [createItem, { loading }] = useCreateItemMutation({
  onCompleted: () => {
    toast.success({ title: 'Item created' });
  },
  onError: (error) => {
    console.error('createItem failed:', error);
    toast.error({ title: 'Failed to create item' });
  },
});

// WRONG - Error silently caught, user has no idea
const [createItem] = useCreateItemMutation({
  onError: (error) => {
    console.error(error); // User sees nothing!
  },
});
```

### Error State Component Pattern

```typescript
interface ErrorStateProps {
  error: Error;
  onRetry?: () => void;
  title?: string;
}

const ErrorState = ({ error, onRetry, title }: ErrorStateProps) => (
  <div className="error-state">
    <Icon name="exclamation-circle" />
    <h3>{title ?? 'Something went wrong'}</h3>
    <p>{error.message}</p>
    {onRetry && (
      <Button onClick={onRetry}>Try Again</Button>
    )}
  </div>
);
```

## Button State Patterns

### Button Loading State

```tsx
<Button
  onClick={handleSubmit}
  isLoading={isSubmitting}
  disabled={!isValid || isSubmitting}
>
  Submit
</Button>
```

### Disable During Operations

**CRITICAL: Always disable triggers during async operations.**

```tsx
// CORRECT - Button disabled while loading
<Button
  disabled={isSubmitting}
  isLoading={isSubmitting}
  onClick={handleSubmit}
>
  Submit
</Button>

// WRONG - User can tap multiple times
<Button onClick={handleSubmit}>
  {isSubmitting ? 'Submitting...' : 'Submit'}
</Button>
```

## Empty States

### Empty State Requirements

Every list/collection MUST have an empty state:

```tsx
// WRONG - No empty state
return <FlatList data={items} />;

// CORRECT - Explicit empty state
return (
  <FlatList
    data={items}
    ListEmptyComponent={<EmptyState />}
  />
);
```

### Contextual Empty States

```tsx
// Search with no results
<EmptyState
  icon="search"
  title="No results found"
  description="Try different search terms"
/>

// List with no items yet
<EmptyState
  icon="plus-circle"
  title="No items yet"
  description="Create your first item"
  action={{ label: 'Create Item', onClick: handleCreate }}
/>
```

## Form Submission Pattern

```tsx
const MyForm = () => {
  const [submit, { loading }] = useSubmitMutation({
    onCompleted: handleSuccess,
    onError: handleError,
  });

  const handleSubmit = async () => {
    if (!isValid) {
      toast.error({ title: 'Please fix errors' });
      return;
    }
    await submit({ variables: { input: values } });
  };

  return (
    <form>
      <Input
        value={values.name}
        onChange={handleChange('name')}
        error={touched.name ? errors.name : undefined}
      />
      <Button
        type="submit"
        onClick={handleSubmit}
        disabled={!isValid || loading}
        isLoading={loading}
      >
        Submit
      </Button>
    </form>
  );
};
```

## Anti-Patterns

### Loading States

```typescript
// WRONG - Spinner when data exists (causes flash)
if (loading) return <Spinner />;

// CORRECT - Only show loading without data
if (loading && !data) return <Spinner />;
```

### Error Handling

```typescript
// WRONG - Error swallowed
try {
  await mutation();
} catch (e) {
  console.log(e); // User has no idea!
}

// CORRECT - Error surfaced
onError: (error) => {
  console.error('operation failed:', error);
  toast.error({ title: 'Operation failed' });
}
```

### Button States

```typescript
// WRONG - Button not disabled during submission
<Button onClick={submit}>Submit</Button>

// CORRECT - Disabled and shows loading
<Button onClick={submit} disabled={loading} isLoading={loading}>
  Submit
</Button>
```

## Checklist

Before completing any UI component:

**UI States:**
- [ ] Error state handled and shown to user
- [ ] Loading state shown only when no data exists
- [ ] Empty state provided for collections
- [ ] Buttons disabled during async operations
- [ ] Buttons show loading indicator when appropriate

**Data & Mutations:**
- [ ] Mutations have onError handler
- [ ] All user actions have feedback (toast/visual)

## Integration with Other Skills

- **graphql-schema**: Use mutation patterns with proper error handling
- **testing-patterns**: Test all UI states (loading, error, empty, success)
- **formik-patterns**: Apply form submission patterns

---

## Antigravity-Specific Patterns

### Toast con Progress Bar (Framer Motion)
```tsx
<motion.div
  initial={{ x: 80, opacity: 0, height: 0 }}
  animate={{ x: 0, opacity: 1, height: 'auto' }}
  exit={{ x: 80, opacity: 0, height: 0 }}
  className="relative overflow-hidden rounded-xl ..."
>
  {/* contenido del toast */}
  {/* Barra de progreso que consume la vida del toast (5s) */}
  <motion.div
    initial={{ scaleX: 1 }}
    animate={{ scaleX: 0 }}
    transition={{ duration: 5, ease: 'linear' }}
    style={{ transformOrigin: 'left' }}
    className="absolute bottom-0 left-0 right-0 h-0.5 bg-green-400 opacity-50"
  />
</motion.div>
```
- Usa `initial={{ height: 0 }}` + `animate={{ height: 'auto' }}` para que el toast **no salte** al aparecer
- La barra de progreso usa `scaleX` en lugar de `width` (más performante, no causa layout)
- `transformOrigin: 'left'` para que shrinkee de izquierda a derecha
- Envolver todos los toasts en `<AnimatePresence initial={false}>` para animar salida

### Skeleton Loading Inline para Datos Async
Cuando un valor puede ser `null` mientras carga (ej. `obsTotal`):
```tsx
// MAL: no renderiza nada durante la carga
{obsTotal !== null && <span>{obsTotal.toLocaleString()} obs.</span>}

// BIEN: skeleton del mismo tamaño que el número final
{obsTotal !== null
  ? <span>{obsTotal.toLocaleString()} obs.</span>
  : <span className="h-3 w-20 rounded bg-white/5 animate-pulse" />}
```
- Dar al skeleton **el mismo tamaño aproximado** que el valor real (evita CLS)
- `animate-pulse` de Tailwind es suficiente para skeleton inline
- Para listas enteras, usar `SkeletonCard` con dimensiones fijas

### Log Lines con Color Semántico
En vez de `<pre>{logs.join('\n')}</pre>`, renderizar línea por línea:
```tsx
const LOG_COLORS: Record<string, string> = {
  '[ERROR]': 'text-red-400',
  '[WARN]': 'text-yellow-400',
  '[SUCCESS]': 'text-green-400',
  '[SYSTEM]': 'text-blue-400',
  '[SERVER]': 'text-purple-400',
};

function getLineColor(line: string): string {
  const key = Object.keys(LOG_COLORS).find(k => line.includes(k));
  return key ? LOG_COLORS[key] : 'text-gray-400';
}

// JSX:
<div className="font-mono text-xs space-y-px">
  {logs.map((line, i) => (
    <div key={i} className={`px-2 py-0.5 hover:bg-white/[0.03] ${getLineColor(line)}`}>
      {line}
    </div>
  ))}
</div>
```
Ventajas:
- Hover highlight por línea individual
- Badge de conteo de errores: `const errorCount = logs.filter(l => l.includes('[ERROR]')).length;`
- Posible selección/copia por línea

### Uptime Tracking con useRef + Tick
Para mostrar tiempos de uptime sin causar re-renders innecesarios:
```typescript
// Estado y refs
const startTime = useRef<number | null>(null);
const [, setTick] = useState(0); // solo para forzar re-render

// Registrar inicio/fin con useEffect
useEffect(() => {
  startTime.current = isRunning ? (startTime.current ?? Date.now()) : null;
}, [isRunning]);

// Tick cada 60s (nivel de granularidad de minutos)
useEffect(() => {
  const id = setInterval(() => setTick(t => t + 1), 60000);
  return () => clearInterval(id);
}, []);

// Helper de formato
function formatUptime(ms: number): string {
  const mins = Math.floor((Date.now() - ms) / 60000);
  if (mins < 1) return '<1m';
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}
```

**Por qué así:**
- `useRef` no causa re-render al mutar → sin parpadeos innecesarios
- El tick de 60s es suficiente granularidad para minutos
- Resetear `startTime.current = null` al parar el servidor limpia el estado

