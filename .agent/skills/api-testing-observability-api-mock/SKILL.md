---
name: api-testing-observability-api-mock
description: "Expert API mocking framework for building realistic mock services that simulate production behavior, enable parallel frontend/backend development, and facilitate comprehensive integration testing. Supports request matching, response scenarios, state management, latency simulation, error injection, and contract validation. Use when mocking third-party APIs, building mock backends for frontend development, creating demo environments, validating API contracts before implementation, testing error scenarios, or building integration test fixtures."
type: feature
---

# API Mocking Framework

Create sophisticated mock API services that accurately simulate production behavior, enable parallel development workflows, and support comprehensive testing strategies.

## Core Mock Server Patterns

### Pattern 1: Simple Request → Response Matching

```javascript
// Mock server using Miragejs / MSW (Mock Service Worker)
import { setupServer } from 'msw'
import { http, HttpResponse } from 'msw'

const handlers = [
  // GET /users/:id
  http.get('https://api.example.com/users/:id', ({ params }) => {
    const { id } = params
    return HttpResponse.json(
      {
        id,
        name: `User ${id}`,
        email: `user${id}@example.com`,
        created_at: '2024-01-15T10:00:00Z'
      },
      { status: 200 }
    )
  }),

  // POST /users
  http.post('https://api.example.com/users', async ({ request }) => {
    const body = await request.json()
    // Validate minimal required fields
    if (!body.email || !body.name) {
      return HttpResponse.json(
        {
          error: 'VALIDATION_ERROR',
          details: [{ field: 'email', message: 'Required' }]
        },
        { status: 422 }
      )
    }
    return HttpResponse.json({ id: Date.now(), ...body }, { status: 201 })
  })
]

const server = setupServer(...handlers)
```

### Pattern 2: Scenario-Based Mocking (Multiple Responses)

```javascript
// Store current scenario in state
let currentScenario = 'success'

const handlers = [
  http.get('https://api.example.com/checkout', () => {
    if (currentScenario === 'success') {
      return HttpResponse.json(
        { status: 'completed', total: 99.99 },
        { status: 200 }
      )
    } else if (currentScenario === 'payment_declined') {
      return HttpResponse.json(
        { error: 'PAYMENT_DECLINED', code: 'card_declined' },
        { status: 402 }
      )
    } else if (currentScenario === 'timeout') {
      // Simulate network delay
      return new Promise(resolve =>
        setTimeout(
          () => resolve(HttpResponse.json({}, { status: 504 })),
          5000
        )
      )
    }
  }),

  // Allow switching scenarios via test utilities
  http.post('https://api.example.com/__mocks__/scenario', async ({ request }) => {
    const { scenario } = await request.json()
    currentScenario = scenario
    return HttpResponse.json({ scenario })
  })
]
```

### Pattern 3: Stateful Mocking (Memory/In-DB State)

```javascript
// Maintain in-memory state across requests
let users = [
  { id: 1, name: 'Alice', status: 'active' },
  { id: 2, name: 'Bob', status: 'inactive' }
]

const handlers = [
  // GET /users
  http.get('https://api.example.com/users', () => {
    return HttpResponse.json({ data: users })
  }),

  // POST /users (adds to in-memory list)
  http.post('https://api.example.com/users', async ({ request }) => {
    const newUser = await request.json()
    const user = { id: Math.max(...users.map(u => u.id)) + 1, ...newUser }
    users.push(user)
    return HttpResponse.json(user, { status: 201 })
  }),

  // DELETE /users/:id (removes from list)
  http.delete('https://api.example.com/users/:id', ({ params }) => {
    users = users.filter(u => u.id !== parseInt(params.id))
    return HttpResponse.json({ success: true })
  })
]
```

### Pattern 4: Conditional Response Based on Headers/Query Params

```javascript
http.get('https://api.example.com/data', ({ request }) => {
  const url = new URL(request.url)
  const apiVersion = request.headers.get('X-API-Version')
  const includeDetails = url.searchParams.get('details') === 'true'

  if (apiVersion === '1') {
    return HttpResponse.json({ id: 1, value: 100 })
  } else if (apiVersion === '2') {
    const response = {
      id: 1,
      value: 100,
      metadata: { created_at: '2024-01-15T10:00:00Z' }
    }
    if (includeDetails) {
      response.details = { source: 'database', cached: false }
    }
    return HttpResponse.json(response)
  }
})
```

## Mock Server Tools Comparison

| Tool | Type | Use Case | Complexity |
|------|------|----------|-----------|
| **MSW (Mock Service Worker)** | Browser/Node | Frontend + API unit tests | Low |
| **Miragejs** | Browser/Ember | Full app development, no backend needed | Medium |
| **Prism** | Standalone server | Spec-driven mocking (OpenAPI/AsyncAPI) | Medium |
| **Postman Mocks** | Cloud | Quick sharing with team, contract testing | Low |
| **json-server** | Standalone | Simple REST CRUD, zero config | Very Low |
| **Docker mock containers** | Docker | Complete backend stack simulation | High |

### Quick Start by Tool

```bash
# MSW (recommended for React/JS)
npm install msw
npx msw init

# json-server (simplest)
npm install json-server
echo '[{"id":1,"name":"Alice"}]' > db.json
npx json-server --watch db.json

# Prism (spec-driven)
npm install -g @stoplight/prism-cli
prism mock openapi.yaml
```

## Pattern 5: Error Injection for Testing Resilience

```javascript
// Mock failures at specific endpoints
let failureConfig = {
  'GET /payment': null,  // null = no failure
  'POST /notification': 'timeout',
  'GET /recommendation': 'rate_limit'
}

http.get('https://api.example.com/payment', ({ request }) => {
  const failure = failureConfig['GET /payment']

  if (failure === 'timeout') {
    return HttpResponse.timeout()
  } else if (failure === 'network_error') {
    return HttpResponse.error()
  } else if (failure === 'rate_limit') {
    return HttpResponse.json(
      { error: 'TOO_MANY_REQUESTS' },
      {
        status: 429,
        headers: { 'Retry-After': '60' }
      }
    )
  }
  // Normal response
  return HttpResponse.json({ status: 'success' })
})

// Test framework integration
test('handles payment timeout gracefully', async () => {
  failureConfig['GET /payment'] = 'timeout'
  // ... test timeout handling
})
```

## Pattern 6: Latency Simulation

```javascript
// Simulate network delays realistically
const simulateLatency = (ms: number) => {
  return new Promise(resolve => setTimeout(resolve, ms))
}

const latencyMap = {
  'fast': 10,      // Local cache
  'normal': 200,   // Typical API call
  'slow': 2000,    // Slow network / overloaded
  'timeout': 30000 // Will exceed typical timeout
}

http.get('https://api.example.com/search', async ({ request }) => {
  const speed = new URL(request.url).searchParams.get('speed') || 'normal'
  await simulateLatency(latencyMap[speed])

  return HttpResponse.json({
    results: [
      { id: 1, title: 'Result 1' },
      { id: 2, title: 'Result 2' }
    ]
  })
})

// Usage in tests
test('shows loading indicator during search', async () => {
  // Request with slow latency
  const response = await fetch('https://api.example.com/search?speed=slow')
  expect(screen.getByText('Loading...')).toBeInTheDocument()
})
```

## Pattern 7: Contract Testing (Validate API Spec Compliance)

```javascript
import { setupServer } from 'msw'
import { defineParametersType } from 'jest-openapi'
import spec from './openapi.json'

defineParametersType(spec)

// Mock strictly adheres to OpenAPI spec
const handlers = [
  http.post('https://api.example.com/users', async ({ request }) => {
    const body = await request.json()
    // Validate body matches schema in OpenAPI spec
    // If doesn't match → throw validation error for test failure
    return HttpResponse.json(
      {
        id: '123',
        name: body.name,
        email: body.email,
        created_at: new Date().toISOString()
      },
      { status: 201 }
    )
  })
]

// Test
test('POST /users returns valid response per spec', async () => {
  const response = await fetch('https://api.example.com/users', {
    method: 'POST',
    body: JSON.stringify({ name: 'Alice', email: 'alice@ex.com' })
  })
  expect(response).toSatisfyApiContract()  // ← Validates against spec
})
```

## Mock Data Generation

### Strategy 1: Deterministic Factories

```javascript
const userFactory = (overrides = {}) => ({
  id: Math.random().toString(36).slice(2),
  name: `User${Math.floor(Math.random() * 1000)}`,
  email: `user@example.com`,
  created_at: new Date().toISOString(),
  ...overrides
})

// In mock handlers
http.get('https://api.example.com/users/:id', ({ params }) => {
  return HttpResponse.json(userFactory({ id: params.id }))
})
```

### Strategy 2: Seed-Based Randomness

```javascript
// Same seed = same data (useful for reproducible tests)
import seedrandom from 'seedrandom'

const rng = seedrandom('test-seed-123')
const randomData = () => ({
  value: Math.floor(rng() * 1000),
  timestamp: new Date().toISOString()
})

// Every test run produces same data with same seed
```

## Implementation Checklist

- [ ] **Mock Server Setup**: Choose tool (MSW, Miragejs, json-server, Prism)
- [ ] **Request Matching**: Define URL patterns, HTTP methods, query parameters
- [ ] **Response Fixtures**: Create realistic data using factories or seed-based randomness
- [ ] **Scenario Handling**: Implement scenario switching (__mocks__/scenario endpoint)
- [ ] **Error Scenarios**: Define failure modes (timeout, 4xx, 5xx, network error)
- [ ] **Latency Simulation**: Add realistic delays for performance testing
- [ ] **State Management**: Choose in-memory (fast), SQLite (persistent), or stateless
- [ ] **Authentication**: Mock auth flows (JWT, OAuth2, API key validation)
- [ ] **Contract Validation**: Validate responses match API spec (OpenAPI/GraphQL schema)
- [ ] **Documentation**: Document available scenarios, how to switch, gotchas
- [ ] **Logging**: Log all mocked requests for debugging test failures
- [ ] **Performance**: Ensure mock server doesn't become bottleneck (cache, optimize)
- [ ] **Clean Separation**: Keep mocks clearly separated from production code

## Best Practices

| Best Practice | Why | How |
|---------------|-----|-----|
| **Don't hardcode data** | Tests should be independent, reproducible | Use factories, fixtures, seed randomness |
| **Support all scenarios** | Frontend needs to test error states | Scenario switching, error injection endpoints |
| **Document expectations** | Prevent misalignment between frontend/backend | API spec (OpenAPI), mock documentation |
| **Enable quick switching** | Easy to test different backends/mocks | Environment variable, MSW service worker toggle |
| **Use realistic latency** | Performance issues hidden until production | Simulate 100-500ms for typical APIs |
| **Mock authentication** | Frontend dev shouldn't need backend creds | Mock auth endpoints, generate fake tokens |
| **Validate contracts** | Catch API spec changes early | jest-openapi, Pact testing |
| **Keep mocks maintainable** | Mocks drift from reality over time | Auto-generate from spec, versioning |
