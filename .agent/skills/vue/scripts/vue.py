#!/usr/bin/env python3
"""
Vue.js Skill

Genera componentes, composables, y stores para Vue 3.
"""

import argparse
import json
import sys
from pathlib import Path


# Component templates
COMPONENT_TEMPLATES = {
    "composition": """<script setup lang="ts">
import {{ ref, computed, onMounted }} from 'vue';

// Props
interface Props {{
  title?: string;
}}

const props = withDefaults(defineProps<Props>(), {{
  title: '{name}',
}});

// Emits
const emit = defineEmits<{{
  (e: 'update', value: string): void;
  (e: 'close'): void;
}}>()

// State
const count = ref(0);
const items = ref<string[]>([]);

// Computed
const doubleCount = computed(() => count.value * 2);

// Methods
function increment() {{
  count.value++;
  emit('update', `Count: ${{count.value}}`);
}}

// Lifecycle
onMounted(() => {{
  console.log('{name} mounted');
}});
</script>

<template>
  <div class="{name_kebab}">
    <h2>{{{{ props.title }}}}</h2>

    <p>Count: {{{{ count }}}} (Double: {{{{ doubleCount }}}})</p>

    <button @click="increment">
      Increment
    </button>

    <ul>
      <li v-for="item in items" :key="item">
        {{{{ item }}}}
      </li>
    </ul>

    <slot></slot>
  </div>
</template>

<style scoped>
.{name_kebab} {{
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
}}

button {{
  padding: 0.5rem 1rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
}}

button:hover {{
  background: #2563eb;
}}
</style>
""",
    "options": """<script lang="ts">
import {{ defineComponent, ref, computed }} from 'vue';

export default defineComponent({{
  name: '{name}',

  props: {{
    title: {{
      type: String,
      default: '{name}',
    }},
  }},

  emits: ['update', 'close'],

  setup(props, {{ emit }}) {{
    const count = ref(0);

    const doubleCount = computed(() => count.value * 2);

    function increment() {{
      count.value++;
      emit('update', `Count: ${{count.value}}`);
    }}

    return {{
      count,
      doubleCount,
      increment,
    }};
  }},
}});
</script>

<template>
  <div class="{name_kebab}">
    <h2>{{{{ title }}}}</h2>
    <p>Count: {{{{ count }}}}</p>
    <button @click="increment">Increment</button>
  </div>
</template>

<style scoped>
.{name_kebab} {{
  padding: 1rem;
}}
</style>
""",
}

# Composable template
COMPOSABLE_TEMPLATE = """import {{ ref, computed, onMounted, onUnmounted }} from 'vue';

interface {name_cap}Options {{
  // Add options here
  initialValue?: string;
}}

interface {name_cap}Return {{
  // Define return type
  value: Ref<string>;
  isLoading: Ref<boolean>;
  error: Ref<Error | null>;
  execute: () => Promise<void>;
  reset: () => void;
}}

export function {name}(options: {name_cap}Options = {{}}): {name_cap}Return {{
  // State
  const value = ref(options.initialValue ?? '');
  const isLoading = ref(false);
  const error = ref<Error | null>(null);

  // Methods
  async function execute() {{
    isLoading.value = true;
    error.value = null;

    try {{
      // Implementar: lógica del componente
      await new Promise(resolve => setTimeout(resolve, 1000));
      value.value = 'Result';
    }} catch (e) {{
      error.value = e as Error;
    }} finally {{
      isLoading.value = false;
    }}
  }}

  function reset() {{
    value.value = options.initialValue ?? '';
    error.value = null;
  }}

  // Lifecycle hooks (if needed)
  onMounted(() => {{
    // Setup
  }});

  onUnmounted(() => {{
    // Cleanup
  }});

  return {{
    value,
    isLoading,
    error,
    execute,
    reset,
  }};
}}
"""

# Common composables
COMMON_COMPOSABLES = {
    "useAsync": """import { ref, Ref } from 'vue';

type AsyncFn<T> = (...args: any[]) => Promise<T>;

interface UseAsyncReturn<T> {{
  data: Ref<T | null>;
  isLoading: Ref<boolean>;
  error: Ref<Error | null>;
  execute: (...args: any[]) => Promise<T | null>;
}}

export function useAsync<T>(fn: AsyncFn<T>): UseAsyncReturn<T> {{
  const data = ref<T | null>(null) as Ref<T | null>;
  const isLoading = ref(false);
  const error = ref<Error | null>(null);

  async function execute(...args: any[]): Promise<T | null> {{
    isLoading.value = true;
    error.value = null;

    try {{
      data.value = await fn(...args);
      return data.value;
    }} catch (e) {{
      error.value = e as Error;
      return null;
    }} finally {{
      isLoading.value = false;
    }}
  }}

  return {{ data, isLoading, error, execute }};
}}
""",
    "useFetch": """import { ref, Ref, watchEffect } from 'vue';

interface UseFetchReturn<T> {{
  data: Ref<T | null>;
  isLoading: Ref<boolean>;
  error: Ref<Error | null>;
  refetch: () => Promise<void>;
}}

export function useFetch<T>(url: string | Ref<string>): UseFetchReturn<T> {{
  const data = ref<T | null>(null) as Ref<T | null>;
  const isLoading = ref(false);
  const error = ref<Error | null>(null);

  async function doFetch() {{
    isLoading.value = true;
    error.value = null;

    try {{
      const urlValue = typeof url === 'string' ? url : url.value;
      const response = await fetch(urlValue);
      if (!response.ok) throw new Error(response.statusText);
      data.value = await response.json();
    }} catch (e) {{
      error.value = e as Error;
    }} finally {{
      isLoading.value = false;
    }}
  }}

  watchEffect(() => {{
    doFetch();
  }});

  return {{ data, isLoading, error, refetch: doFetch }};
}}
""",
    "useLocalStorage": """import { ref, watch, Ref } from 'vue';

export function useLocalStorage<T>(key: string, defaultValue: T): Ref<T> {{
  const stored = localStorage.getItem(key);
  const value = ref<T>(stored ? JSON.parse(stored) : defaultValue) as Ref<T>;

  watch(value, (newValue) => {{
    localStorage.setItem(key, JSON.stringify(newValue));
  }}, {{ deep: true }});

  return value;
}}
""",
}

# Pinia store template
PINIA_STORE_TEMPLATE = """import {{ defineStore }} from 'pinia';
import {{ ref, computed }} from 'vue';

interface {name_cap} {{
  id: string;
  // Add properties
}}

export const use{name_cap}Store = defineStore('{name}', () => {{
  // State
  const items = ref<{name_cap}[]>([]);
  const currentItem = ref<{name_cap} | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  // Getters
  const itemCount = computed(() => items.value.length);

  const itemById = computed(() => {{
    return (id: string) => items.value.find(item => item.id === id);
  }});

  // Actions
  async function fetchItems() {{
    isLoading.value = true;
    error.value = null;

    try {{
      // Implementar: llamada API
      const response = await fetch('/api/{name}s');
      items.value = await response.json();
    }} catch (e) {{
      error.value = (e as Error).message;
    }} finally {{
      isLoading.value = false;
    }}
  }}

  async function createItem(data: Omit<{name_cap}, 'id'>) {{
    isLoading.value = true;

    try {{
      const response = await fetch('/api/{name}s', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data),
      }});
      const newItem = await response.json();
      items.value.push(newItem);
      return newItem;
    }} catch (e) {{
      error.value = (e as Error).message;
      throw e;
    }} finally {{
      isLoading.value = false;
    }}
  }}

  async function updateItem(id: string, data: Partial<{name_cap}>) {{
    const index = items.value.findIndex(item => item.id === id);
    if (index === -1) return;

    try {{
      const response = await fetch(`/api/{name}s/${{id}}`, {{
        method: 'PATCH',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data),
      }});
      const updated = await response.json();
      items.value[index] = updated;
      return updated;
    }} catch (e) {{
      error.value = (e as Error).message;
      throw e;
    }}
  }}

  async function deleteItem(id: string) {{
    try {{
      await fetch(`/api/{name}s/${{id}}`, {{ method: 'DELETE' }});
      items.value = items.value.filter(item => item.id !== id);
    }} catch (e) {{
      error.value = (e as Error).message;
      throw e;
    }}
  }}

  function setCurrentItem(item: {name_cap} | null) {{
    currentItem.value = item;
  }}

  function $reset() {{
    items.value = [];
    currentItem.value = null;
    isLoading.value = false;
    error.value = null;
  }}

  return {{
    // State
    items,
    currentItem,
    isLoading,
    error,
    // Getters
    itemCount,
    itemById,
    // Actions
    fetchItems,
    createItem,
    updateItem,
    deleteItem,
    setCurrentItem,
    $reset,
  }};
}});
"""

# Router template
ROUTER_TEMPLATE = """import {{ createRouter, createWebHistory }} from 'vue-router';
import type {{ RouteRecordRaw }} from 'vue-router';

const routes: RouteRecordRaw[] = [
  {{
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
  }},
  {{
    path: '/about',
    name: 'about',
    component: () => import('@/views/AboutView.vue'),
  }},
  {{
    path: '/{name}s',
    name: '{name}s',
    component: () => import('@/views/{name_cap}ListView.vue'),
  }},
  {{
    path: '/{name}s/:id',
    name: '{name}',
    component: () => import('@/views/{name_cap}DetailView.vue'),
    props: true,
  }},
  {{
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  }},
];

export const router = createRouter({{
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {{
    if (savedPosition) {{
      return savedPosition;
    }}
    return {{ top: 0 }};
  }},
}});

// Navigation guards
router.beforeEach((to, from) => {{
  // Implementar: verificación de autenticación
  return true;
}});
"""


def to_kebab_case(name: str) -> str:
    """Convert PascalCase to kebab-case."""
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()


def generate_component(name: str, composition: bool = True) -> str:
    """Genera componente Vue."""
    template_key = "composition" if composition else "options"
    template = COMPONENT_TEMPLATES.get(template_key, COMPONENT_TEMPLATES["composition"])
    return template.format(name=name, name_kebab=to_kebab_case(name))


def generate_composable(name: str) -> str:
    """Genera composable Vue."""
    # Ensure name starts with 'use'
    if not name.startswith("use"):
        name = f"use{name[0].upper()}{name[1:]}"

    name_cap = name[3:]  # Remove 'use' prefix for type name

    return COMPOSABLE_TEMPLATE.format(name=name, name_cap=name_cap)


def generate_store(name: str) -> str:
    """Genera store Pinia."""
    name_lower = name.lower()
    name_cap = name[0].upper() + name[1:]

    return PINIA_STORE_TEMPLATE.format(name=name_lower, name_cap=name_cap)


def generate_router(name: str = "item") -> str:
    """Genera configuración de router."""
    name_lower = name.lower()
    name_cap = name[0].upper() + name[1:]

    return ROUTER_TEMPLATE.format(name=name_lower, name_cap=name_cap)


def main():
    parser = argparse.ArgumentParser(description="Vue.js Skill - Genera componentes Vue 3")

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # component
    comp_parser = subparsers.add_parser("component", help="Genera componente")
    comp_parser.add_argument("--name", "-n", required=True, help="Nombre del componente")
    comp_parser.add_argument(
        "--composition",
        "-c",
        action="store_true",
        default=True,
        help="Usar Composition API (default)",
    )
    comp_parser.add_argument("--options", "-o", action="store_true", help="Usar Options API")

    # composable
    compos_parser = subparsers.add_parser("composable", help="Genera composable")
    compos_parser.add_argument("--name", "-n", required=True, help="Nombre (ej: useAuth)")

    # store
    store_parser = subparsers.add_parser("store", help="Genera Pinia store")
    store_parser.add_argument("--name", "-n", required=True, help="Nombre del store")

    # router
    router_parser = subparsers.add_parser("router", help="Genera configuración router")
    router_parser.add_argument("--name", "-n", default="item", help="Nombre base para rutas")

    # patterns
    subparsers.add_parser("patterns", help="Lista composables comunes")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "component":
        use_composition = not args.options
        output = generate_component(args.name, use_composition)

    elif args.command == "composable":
        output = generate_composable(args.name)

    elif args.command == "store":
        output = generate_store(args.name)

    elif args.command == "router":
        output = generate_router(args.name)

    elif args.command == "patterns":
        if args.json:
            output = json.dumps(list(COMMON_COMPOSABLES.keys()), indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" VUE 3 COMMON COMPOSABLES")
            print(f"{'=' * 60}\n")
            for name, code in COMMON_COMPOSABLES.items():
                print(f"📘 {name}")
                print("-" * 40)
                print(code)
                print()

    # Output
    if output:
        if hasattr(args, "output") and args.output:
            Path(args.output).write_text(output)
            print(f"✓ Escrito en {args.output}")
        else:
            print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
