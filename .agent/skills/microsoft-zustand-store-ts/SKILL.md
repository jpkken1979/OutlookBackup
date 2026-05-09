---
name: microsoft-zustand-store-ts
description: "Patrones de Zustand store en TypeScript. State management ligero con slices, middleware, devtools, persist, immer y best practices de rendimiento."
type: feature
---

# Microsoft Zustand Store Patterns

Patrones para state management con Zustand en aplicaciones TypeScript/React.

## Instalación

```bash
npm install zustand
npm install immer  # Opcional, para updates inmutables
```

## Store Básico

```typescript
import { create } from "zustand";

interface CounterState {
  count: number;
  increment: () => void;
  decrement: () => void;
  reset: () => void;
}

export const useCounterStore = create<CounterState>()((set) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
  decrement: () => set((state) => ({ count: state.count - 1 })),
  reset: () => set({ count: 0 }),
}));
```

## Slice Pattern

Dividir stores grandes en slices:

```typescript
import { create, type StateCreator } from "zustand";

// --- Auth Slice ---
interface AuthSlice {
  user: User | null;
  isAuthenticated: boolean;
  login: (credentials: Credentials) => Promise<void>;
  logout: () => void;
}

const createAuthSlice: StateCreator<
  AppState,
  [],
  [],
  AuthSlice
> = (set) => ({
  user: null,
  isAuthenticated: false,
  login: async (credentials) => {
    const user = await authService.login(credentials);
    set({ user, isAuthenticated: true });
  },
  logout: () => set({ user: null, isAuthenticated: false }),
});

// --- UI Slice ---
interface UISlice {
  theme: "light" | "dark";
  sidebarOpen: boolean;
  toggleTheme: () => void;
  toggleSidebar: () => void;
}

const createUISlice: StateCreator<
  AppState,
  [],
  [],
  UISlice
> = (set) => ({
  theme: "dark",
  sidebarOpen: true,
  toggleTheme: () =>
    set((state) => ({
      theme: state.theme === "dark" ? "light" : "dark",
    })),
  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),
});

// --- Combined Store ---
type AppState = AuthSlice & UISlice;

export const useAppStore = create<AppState>()((...args) => ({
  ...createAuthSlice(...args),
  ...createUISlice(...args),
}));
```

## Middleware

### Devtools

```typescript
import { devtools } from "zustand/middleware";

export const useStore = create<MyState>()(
  devtools(
    (set) => ({
      count: 0,
      increment: () =>
        set(
          (state) => ({ count: state.count + 1 }),
          false,
          "increment" // Action name para devtools
        ),
    }),
    { name: "MyStore" }
  )
);
```

### Persist

```typescript
import { persist, createJSONStorage } from "zustand/middleware";

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: "dark",
      language: "es",
      setTheme: (theme: string) => set({ theme }),
      setLanguage: (lang: string) => set({ language: lang }),
    }),
    {
      name: "settings-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        theme: state.theme,
        language: state.language,
      }),
    }
  )
);
```

### Immer

```typescript
import { immer } from "zustand/middleware/immer";

interface TodoState {
  todos: Todo[];
  addTodo: (text: string) => void;
  toggleTodo: (id: string) => void;
  removeTodo: (id: string) => void;
}

export const useTodoStore = create<TodoState>()(
  immer((set) => ({
    todos: [],
    addTodo: (text) =>
      set((state) => {
        state.todos.push({
          id: crypto.randomUUID(),
          text,
          done: false,
        });
      }),
    toggleTodo: (id) =>
      set((state) => {
        const todo = state.todos.find((t) => t.id === id);
        if (todo) todo.done = !todo.done;
      }),
    removeTodo: (id) =>
      set((state) => {
        state.todos = state.todos.filter((t) => t.id !== id);
      }),
  }))
);
```

### Combined Middleware

```typescript
export const useStore = create<MyState>()(
  devtools(
    persist(
      immer((set) => ({
        // ... state and actions
      })),
      { name: "my-store" }
    ),
    { name: "MyStore" }
  )
);
```

## Selectors (Rendimiento)

```typescript
// ❌ MAL — re-renderiza en cada cambio del store
const { count, user, theme } = useAppStore();

// ✅ BIEN — solo re-renderiza cuando count cambia
const count = useAppStore((state) => state.count);

// ✅ BIEN — selector con múltiples valores
const { user, isAuthenticated } = useAppStore(
  (state) => ({
    user: state.user,
    isAuthenticated: state.isAuthenticated,
  })
);

// ✅ MEJOR — con shallow comparison para objetos
import { useShallow } from "zustand/react/shallow";

const { user, isAuthenticated } = useAppStore(
  useShallow((state) => ({
    user: state.user,
    isAuthenticated: state.isAuthenticated,
  }))
);
```

## Async Actions

```typescript
interface DataState {
  data: Item[];
  isLoading: boolean;
  error: string | null;
  fetchData: () => Promise<void>;
}

export const useDataStore = create<DataState>()((set) => ({
  data: [],
  isLoading: false,
  error: null,
  fetchData: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch("/api/data");
      const data = await response.json();
      set({ data, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Unknown error",
        isLoading: false,
      });
    }
  },
}));
```

## Acceso Fuera de React

```typescript
// Leer estado fuera de un componente
const count = useCounterStore.getState().count;

// Actualizar estado fuera
useCounterStore.getState().increment();

// Suscribirse a cambios
const unsubscribe = useCounterStore.subscribe(
  (state) => console.log("Count changed:", state.count)
);
```

## Testing

```typescript
import { renderHook, act } from "@testing-library/react";

describe("useCounterStore", () => {
  beforeEach(() => {
    // Reset store entre tests
    useCounterStore.setState({ count: 0 });
  });

  it("should increment count", () => {
    const { result } = renderHook(() =>
      useCounterStore((s) => ({ count: s.count, increment: s.increment }))
    );

    act(() => result.current.increment());
    expect(result.current.count).toBe(1);
  });
});
```

## Anti-Patterns

- **NO** poner lógica de UI en el store — solo estado y acciones
- **NO** desestructurar todo el store — usar selectors
- **NO** anidar estado profundamente — aplanar cuando sea posible
- **NO** mutar estado directamente sin immer
- **NO** crear un store por componente — usar stores compartidos

## Recursos

- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [Zustand GitHub](https://github.com/pmndrs/zustand)
- [Zustand Best Practices](https://zustand.docs.pmnd.rs/guides/practice-with-no-store-actions)
