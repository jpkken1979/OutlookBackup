---
name: typescript-advanced-types
type: feature
description: Master TypeScript's advanced type system including generics, conditional types, mapped types, template literals, and utility types for building type-safe applications. Use when implementing complex type logic, creating reusable type utilities, or ensuring compile-time type safety in TypeScript projects.
---

# TypeScript Advanced Types

Comprehensive guidance for mastering TypeScript's advanced type system including generics, conditional types, mapped types, template literal types, and utility types for building robust, type-safe applications.

## When to Use This Skill

- Building type-safe libraries or frameworks
- Creating reusable generic components
- Implementing complex type inference logic
- Designing type-safe API clients
- Building form validation systems
- Creating strongly-typed configuration objects
- Implementing type-safe state management
- Migrating JavaScript codebases to TypeScript

## Core Concepts

### 1. Generics

Generics allow you to write reusable, type-safe code that works with multiple types while maintaining full type information.

```typescript
// Basic generic function
function identity<T>(value: T): T {
  return value;
}

// Generic interface
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}

// Generic class
class DataStore<T> {
  private items: T[] = [];

  add(item: T): void {
    this.items.push(item);
  }

  get(index: number): T | undefined {
    return this.items[index];
  }

  getAll(): T[] {
    return [...this.items];
  }

  filter(predicate: (item: T) => boolean): T[] {
    return this.items.filter(predicate);
  }
}

// Generic constraints
interface HasId {
  id: string;
}

function findById<T extends HasId>(items: T[], id: string): T | undefined {
  return items.find(item => item.id === id);
}

// Multiple type parameters
function map<K, V>(key: K, value: V): Map<K, V> {
  const map = new Map();
  map.set(key, value);
  return map;
}
```

### 2. Conditional Types

Conditional types allow you to create types that depend on other types, enabling sophisticated type transformations.

```typescript
// Basic conditional type
type IsString<T> = T extends string ? true : false;

type A = IsString<string>;  // true
type B = IsString<number>;  // false

// Infer keyword
type ReturnType<T> = T extends (...args: any[]) => infer R ? R : never;

function fn(x: string): number {
  return 42;
}

type R = ReturnType<typeof fn>;  // number

// Extract parameter types
type Parameters<T> = T extends (...args: infer P) => any ? P : never;

type P = Parameters<(x: string, y: number) => void>;  // [string, number]

// Conditional with union types
type Flatten<T> = T extends Array<infer U> ? U : T;

type G = Flatten<string[]>;  // string
type H = Flatten<number>;     // number

// Distributive conditional types
type ToArray<T> = T extends any ? T[] : never;

type I = ToArray<string | number>;  // string[] | number[]

// Non-distributive version
type ToArrayNonDist<T> = [T] extends [any] ? T[] : never;

type J = ToArrayNonDist<string | number>;  // (string | number)[]
```

### 3. Mapped Types

Mapped types allow you to transform existing types into new ones by iterating over keys.

```typescript
// Basic mapped type
type Partial<T> = {
  [P in keyof T]?: T[P];
};

type Readonly<T> = {
  readonly [P in keyof T]: T[P];
};

// Make specific properties optional
type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

interface User {
  id: string;
  name: string;
  email: string;
  age: number;
}

type UserCreate = PartialBy<User, 'id' | 'age'>;
// { name: string; email: string; id?: string; age?: number }

// Key remapping
type Getters<T> = {
  [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K];
};

type UserGetters = Getters<User>;
// { getId: () => string; getName: () => string; ... }

// Conditional mapped types
type NonNullable<T> = {
  [P in keyof T]-?: T[P] extends null | undefined ? never : T[P];
};

// Filter keys by value type
type FilterByValueType<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};

type StringProps = FilterByValueType<User, string>;
// { name: string; email: string; id: string }

// Transform values
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};
```

### 4. Template Literal Types

Template literal types allow you to create string types with dynamic content.

```typescript
// Basic template literal
type EventName = `on${string}`;
type CSSUnit = `${number}${'px' | 'em' | 'rem'}`;

// Event system
type PropEventSource<T> = {
  on<K extends string & keyof T>(eventName: `${K}`, callback: (value: T[K]) => void): void;
};

interface Button {
  click: string;
  focus: string;
}

const events: PropEventSource<Button> = {} as any;
events.on('click', (value) => console.log(value));  // value is string

// Union in template literal
type Direction = 'top' | 'left' | 'right' | 'bottom';
type Margin = `margin${Capitalize<Direction>}`;

type MarginTop = 'marginTop';
type MarginRight = 'marginRight';

// Extract path
type ExtractRoute<S extends string> =
  S extends `${infer Prefix}:${infer Param}/${infer Rest}`
    ? Param | ExtractRoute<`:${Rest}`>
    : S extends `${infer Prefix}:${infer Param}`
    ? Param
    : never;

type Params = ExtractRoute<'/users/:userId/posts/:postId'>;
// 'userId' | 'postId'

// String manipulation utilities
type TrimLeft<T extends string> = T extends ` ${infer Rest}` ? TrimLeft<Rest> : T;
type Trim<T extends string> = TrimLeft<` ${Trunc<Rest>}`>;

type Greeting = Trim<'  hello world  '>;  // 'hello world'
```

### 5. Utility Types (Built-in)

TypeScript provides common utility types that you should master.

```typescript
// Partial<T> - Make all properties optional
interface Config { host: string; port: number; ssl: boolean; }
type PartialConfig = Partial<Config>;

// Required<T> - Make all properties required
type RequiredConfig = Required<PartialConfig>;

// Pick<T, K> - Select subset of properties
type BasicConfig = Pick<Config, 'host' | 'port'>;

// Omit<T, K> - Remove properties
type NoSslConfig = Omit<Config, 'ssl'>;

// Record<K, V> - Create object type
type Role = 'admin' | 'user' | 'guest';
type Permissions = Record<Role, string[]>;

// Exclude<T, U> - Remove from union
type EventType = 'click' | 'focus' | 'blur' | 'keydown';
type KeyboardEvent = Exclude<EventType, 'click' | 'blur'>;

// Extract<T, U> - Keep from union
type FocusEvent = Extract<EventType, 'focus' | 'blur'>;

// NonNullable<T> - Remove null and undefined
type MaybeUser = string | null | undefined;
type User = NonNullable<MaybeUser>;

// ReturnType<T> - Extract function return type
function createUser() { return { id: '1', name: 'John' }; }
type UserType = ReturnType<typeof createUser>;

// Parameters<T> - Extract function parameters
function updateUser(id: string, name: string, age?: number) {}
type UpdateUserParams = Parameters<typeof updateUser>;
// [id: string, name: string, age?: number]

// Awaited<T> - Unwrap Promise type
async function fetchUser() { return { name: 'John' }; }
type UserData = Awaited<ReturnType<typeof fetchUser>>;
```

### 6. Type-Safe Event Emitter Pattern

```typescript
type EventMap = Record<string, any>;

class TypedEmitter<T extends EventMap> {
  private listeners: { [K in keyof T]?: Set<(data: T[K]) => void> } = {};

  on<K extends keyof T>(event: K, listener: (data: T[K]) => void): this {
    if (!this.listeners[event]) {
      this.listeners[event] = new Set();
    }
    this.listeners[event]!.add(listener);
    return this;
  }

  off<K extends keyof T>(event: K, listener: (data: T[K]) => void): this {
    this.listeners[event]?.delete(listener);
    return this;
  }

  emit<K extends keyof T>(event: K, data: T[K]): boolean {
    const listeners = this.listeners[event];
    if (!listeners) return false;
    listeners.forEach(listener => listener(data));
    return true;
  }
}

// Usage
interface AppEvents {
  userLoggedIn: { userId: string; timestamp: Date };
  userLoggedOut: { userId: string };
  error: { code: number; message: string };
}

const emitter = new TypedEmitter<AppEvents>();

emitter.on('userLoggedIn', ({ userId, timestamp }) => {
  console.log(`User ${userId} logged in at ${timestamp}`);
});

// This would be a type error:
emitter.emit('userLoggedIn', { userId: '123' });  // Missing timestamp
```

### 7. Type-Safe API Client Pattern

```typescript
// Define endpoints as a type
interface EndpointDefinition {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  response: unknown;
  body?: unknown;
}

type Endpoints = {
  getUser: EndpointDefinition & { path: '/users/:id'; response: User };
  createUser: EndpointDefinition & { method: 'POST'; path: '/users'; body: CreateUserDto; response: User };
  listPosts: EndpointDefinition & { path: '/posts'; response: Post[] };
};

// Build API client
type ApiClient = {
  [K in keyof Endpoints]: (
    ...args: Endpoints[K]['body'] extends undefined
      ? []
      : [body: Endpoints[K]['body']]
  ) => Promise<Endpoints[K]['response']>;
};

class ApiClientImpl implements ApiClient {
  constructor(private baseUrl: string) {}

  async getUser([id]: []): Promise<User> {
    const response = await fetch(`${this.baseUrl}/users/${id}`);
    return response.json();
  }

  async createUser([body]: [CreateUserDto]): Promise<User> {
    const response = await fetch(`${this.baseUrl}/users`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    return response.json();
  }

  async listPosts(): Promise<Post[]> {
    const response = await fetch(`${this.baseUrl}/posts`);
    return response.json();
  }
}
```

### 8. Builder Pattern

```typescript
// Generic builder
type BuilderState<T, K extends keyof T = keyof T> = {
  [P in K]: (value: T[P]) => BuilderState<T, Exclude<keyof T, P>>;
} & {
  build: () => T;
};

function createBuilder<T>(): BuilderState<T, never> {
  return new Proxy({} as BuilderState<T, never>, {
    get(target, prop) {
      return (value: any) => {
        const next = { ...target, [prop]: value };
        return createBuilder<T>().merge(next);
      };
    },
  }) as any;
}

// Implementation with merge helper
function createBuilder<T>(): BuilderState<T, never> {
  function builder(state: Partial<T> = {}): any {
    return new Proxy({}, {
      get(_, prop) {
        if (prop === 'build') return () => state as T;
        return (value: any) => builder({ ...state, [prop]: value });
      },
    });
  }
  return builder();
}

// Usage
interface HttpRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  headers: Record<string, string>;
  body?: unknown;
}

const request = createBuilder<HttpRequest>()
  .method('POST')
  .url('https://api.example.com/users')
  .headers({ 'Content-Type': 'application/json' })
  .body({ name: 'John' })
  .build();
```

### 9. Discriminated Unions

```typescript
// Discriminated union for state management
type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error };

function render<T>(state: AsyncState<T>): string {
  switch (state.status) {
    case 'idle': return 'Idle';
    case 'loading': return 'Loading...';
    case 'success': return `Data: ${JSON.stringify(state.data)}`;  // T is known
    case 'error': return `Error: ${state.error.message}`;
  }
}

// Exhaustive check with never
type ExhaustiveCheck<T> = T;

function assertNever(x: never): never {
  throw new Error('Unexpected value: ' + x);
}

function render2<T>(state: AsyncState<T>): string {
  switch (state.status) {
    case 'idle': return 'Idle';
    case 'loading': return 'Loading...';
    case 'success': return `Data: ${JSON.stringify(state.data)}`;
    case 'error': return `Error: ${state.error.message}`;
    default: return assertNever(state);  // Compile error if not exhaustive
  }
}
```

## Best Practices

1. **Use inference over explicit annotations** — Let TypeScript infer types when possible, only annotate when necessary.
2. **Prefer `unknown` over `any`** — Use `unknown` when you don't know the type; narrow it down before using it.
3. **Leverage conditional types for utilities** — Build reusable type utilities that handle edge cases.
4. **Use mapped types for transformations** — Transform object types cleanly without duplicating code.
5. **Prefer interfaces for object shapes** — Use `interface` for object types; use `type` for unions, intersections, and aliases.
6. **Write type tests** — Test complex types to catch regressions using conditional type assertions.
7. **Use template literal types sparingly** — They're powerful but can create overly specific types that are hard to maintain.
8. **Derive types from existing types** — Use `typeof`, `ReturnType`, `Parameters` to derive types from code rather than duplicating them.

## Limitations

- Use this skill only when the task clearly matches the scope described above.
- Do not treat the output as a substitute for environment-specific validation, testing, or expert review.
- Stop and ask for clarification if required inputs, permissions, safety boundaries, or success criteria are missing.