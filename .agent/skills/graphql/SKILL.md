---
type: feature
name: graphql
description: "Master GraphQL API design, schema architecture, resolvers, and client integration. Covers schema design with proper nullability, DataLoader for N+1 prevention, query complexity limiting, federation for microservices, subscriptions, caching strategies, and security hardening. Includes Apollo Server, Apollo Client, urql patterns, type generation with graphql-codegen, and operational concerns (monitoring, error handling, performance). Use when designing GraphQL APIs, building schema-first applications, integrating GraphQL with databases, federating microservices, preventing N+1 queries, securing GraphQL endpoints, or optimizing client caching."
source: vibeship-spawner-skills (Apache 2.0)
---

# GraphQL: Query Language for Modern APIs

Build production-grade GraphQL APIs with proper schema design, N+1 prevention, security hardening, and operational excellence.

## GraphQL vs REST Decision Matrix

| Aspect | REST | GraphQL |
|--------|------|---------|
| **Data fetching** | Multiple requests, over-fetching | Single request, exact data needed |
| **Caching** | HTTP cache (natural) | Client-managed (needs strategy) |
| **Real-time** | WebSockets separate | Built-in Subscriptions |
| **Versioning** | API v1, v2, v3 | Schema evolution (backwards-compatible) |
| **Complexity** | Simple endpoints | Complex query composition |
| **Learning curve** | Easier | Steeper |
| **Best for** | Simple CRUD, public APIs | Complex data graphs, mobile apps |

## Core Concept: Schema Design

### Principle 1: Nullability Matters

```graphql
# ❌ BAD: Everything nullable (can't distinguish error from missing data)
type User {
  id: ID
  email: String
  name: String
  posts: [Post]
}

# ✓ GOOD: Explicit nullability (know what's guaranteed)
type User {
  id: ID!                  # Always present
  email: String!           # Always present, required
  name: String!
  posts: [Post!]!          # List always present, items always present
  bio: String              # Can be null (optional bio)
}

# Query safety: If field is non-null (!) and resolver returns null → GraphQL error
# This forces clients to handle errors, prevents silent failures
```

### Principle 2: Schema as Contract

```graphql
# Your schema IS your API documentation
# Type system serves as self-documenting contract

type Query {
  """Fetch user by ID. Returns null if not found."""
  user(id: ID!): User

  """Search posts with pagination."""
  posts(
    query: String!
    limit: Int = 10
    offset: Int = 0
  ): PostConnection!
}

type PostConnection {
  """Items in current page."""
  edges: [Post!]!

  """Total count across all pages."""
  total: Int!

  """Whether more pages exist."""
  hasNextPage: Boolean!
}
```

## Pattern 1: DataLoader (Prevent N+1 Queries)

### The N+1 Problem

```javascript
// ❌ BAD: Without DataLoader
const resolvers = {
  Query: {
    posts: async () => {
      return db.query('SELECT * FROM posts')  // 1 query
    }
  },
  Post: {
    author: async (post) => {
      return db.query('SELECT * FROM users WHERE id = ?', post.author_id)  // N queries!
    }
  }
}

// Query:
// {
//   posts {
//     title
//     author { name }
//   }
// }
// Executes: 1 (posts) + N (authors for each post)
```

### DataLoader Solution

```javascript
import DataLoader from 'dataloader'

// Create loader that batches requests
const userLoader = new DataLoader(async (userIds) => {
  // Called with array of IDs: [1, 2, 3, 1, 2]
  const users = await db.query('SELECT * FROM users WHERE id IN (?)', [userIds])

  // Return in same order as input, with duplicates
  return userIds.map(id => users.find(u => u.id === id))
})

const resolvers = {
  Query: {
    posts: async () => db.query('SELECT * FROM posts')  // 1 query
  },
  Post: {
    author: async (post, _, { userLoader }) => {
      return userLoader.load(post.author_id)  // Batched!
    }
  }
}

// Same query now executes: 1 (posts) + 1 (all authors, batched)
// DataLoader deduplicates and batches within single event loop tick
```

### Per-Request DataLoader Context

```javascript
// Create fresh loaders for each request (important for auth context)
const server = new ApolloServer({
  resolvers,
  context: async ({ req }) => {
    return {
      userLoader: new DataLoader(async (ids) => { /* ... */ }),
      postLoader: new DataLoader(async (ids) => { /* ... */ }),
      user: await authenticateUser(req)  // Auth context
    }
  }
})
```

## Pattern 2: Query Complexity & Depth Limiting

### Problem: Malicious Queries

```graphql
# Without depth limiting, this query takes minutes:
{
  user {
    posts {
      comments {
        author {
          posts {
            comments {
              author {
                posts { ... }
              }
            }
          }
        }
      }
    }
  }
}

# Exponential growth: 1 user → 10 posts → 100 comments → 100 authors → ...
# = millions of database queries
```

### Solutions: Depth & Complexity Limits

```javascript
import { getComplexity, simpleEstimator } from 'graphql-query-complexity'

const server = new ApolloServer({
  plugins: {
    didResolveOperation: ({ request, document }) => {
      // Method 1: Limit depth
      const depth = getQueryDepth(document)
      if (depth > 7) throw new Error('Query too deep')

      // Method 2: Limit complexity (cost per field)
      const complexity = getComplexity({
        schema,
        operationName: request.operationName,
        query: document,
        variables: request.variables,
        estimators: [
          simpleEstimator({ defaultComplexity: 1 }),
          // Custom cost for expensive fields:
          {
            Query: {
              expensiveSearch: () => 5  // Costs 5 points
            }
          }
        ]
      })
      if (complexity > 1000) throw new Error('Query too complex')
    }
  }
})

# Schema can also define complexity:
type Query {
  users(limit: Int = 10): [User!]! @cost(complexity: "limit")
  search(query: String!): [SearchResult!]! @cost(complexity: 10)  # Always costs 10
}
```

## Pattern 3: Authorization (Field-Level & Query-Level)

### ❌ Anti-Pattern: Authorization in Schema

```graphql
# Don't do this - directives alone don't secure data
directive @auth(requires: Role!) on FIELD_DEFINITION

type User {
  id: ID!
  email: String! @auth(requires: AUTHENTICATED)
  salary: Float! @auth(requires: ADMIN)
}
```

### ✓ Authorization in Resolvers

```javascript
const resolvers = {
  User: {
    email: (user, _, { user: currentUser }) => {
      // Check: Can current user see this field?
      if (currentUser.id === user.id || currentUser.role === 'ADMIN') {
        return user.email
      }
      return null  // Or throw error
    },
    salary: (user, _, { user: currentUser }) => {
      // Only admins can see salaries
      if (currentUser.role !== 'ADMIN') {
        throw new ForbiddenError('Not authorized')
      }
      return user.salary
    }
  }
}

// Middleware pattern (reusable):
const requireAuth = (resolver) => (parent, args, context, info) => {
  if (!context.user) throw new UnauthenticatedError()
  return resolver(parent, args, context, info)
}

const requireRole = (role) => (resolver) => (parent, args, context, info) => {
  if (!context.user || context.user.role !== role) {
    throw new ForbiddenError()
  }
  return resolver(parent, args, context, info)
}

// Usage:
{
  Query: {
    adminData: requireRole('ADMIN')((parent, args, context) => {
      return getAdminData()
    })
  }
}
```

## Pattern 4: Federation (Microservices)

### Apollo Federation Architecture

```
User Service (users: User!)
    ↓
Product Service (products: [Product!]!)
    ↓
Apollo Gateway (composes subgraphs)
    ↓
Client (single GraphQL endpoint)
```

### User Service (Subgraph)

```javascript
// users-service/schema.graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.0")

type Query {
  user(id: ID!): User
}

type User @key(fields: "id") {
  id: ID!
  email: String!
  name: String!
}
```

### Product Service (Subgraph)

```javascript
// products-service/schema.graphql
type Query {
  product(id: ID!): Product
}

type Product @key(fields: "id") {
  id: ID!
  name: String!
  author: User!  # Reference to User service
}

type User @external {
  id: ID!
}
```

### Apollo Gateway (Composes Subgraphs)

```javascript
const gateway = new ApolloGatewayWithCore({
  supergraphSdl: gql`
    schema {
      query: Query
    }

    type Query {
      user(id: ID!): User
      product(id: ID!): Product
    }
  `,
  buildService({ url }) {
    return new DataSourceCache({
      cache: new InMemoryLRUCache(),
    }).getDataSource({ url })
  }
})

const server = new ApolloServer({ gateway })
```

## Pattern 5: Subscriptions (Real-time)

```javascript
// Schema
type Subscription {
  postCreated: Post!
  messageReceived(userId: ID!): Message!
}

// Resolver
const resolvers = {
  Subscription: {
    postCreated: {
      subscribe: (_, __, { pubsub }) => {
        return pubsub.asyncIterator(['POST_CREATED'])
      },
      resolve: (payload) => payload.post
    },
    messageReceived: {
      subscribe: (_, { userId }, { pubsub }) => {
        return pubsub.asyncIterator([`MESSAGES_${userId}`])
      },
      resolve: (payload) => payload.message
    }
  }
}

// Publishing from other resolvers
{
  Mutation: {
    createPost: async (_, { input }, { pubsub }) => {
      const post = await db.createPost(input)
      pubsub.publish('POST_CREATED', { post })  // Notify subscribers
      return post
    }
  }
}

// Client subscription
const subscription = gql`
  subscription OnPostCreated {
    postCreated {
      id
      title
      author { name }
    }
  }
`
```

## Pattern 6: Caching Strategy (Apollo Client)

### Cache Normalization

```javascript
import { ApolloClient, InMemoryCache, gql } from '@apollo/client'

const client = new ApolloClient({
  cache: new InMemoryCache({
    typePolicies: {
      User: {
        keyFields: ['id'],  // Unique identifier for cache
        fields: {
          posts: {
            merge: (existing = [], incoming) => {
              // Custom merge strategy for pagination
              return [...existing, ...incoming]
            }
          }
        }
      }
    }
  })
})

// Example cache flow:
// Query: { user(id: 1) { posts { id title } } }
// Cache stores: {
//   "User:1": { id: 1, posts: [Post:1, Post:2] },
//   "Post:1": { id: 1, title: "..." },
//   "Post:2": { id: 2, title: "..." }
// }
//
// Next query for same user → served from cache instantly
```

## Pattern 7: Error Handling

```javascript
// Schema with error types
type Query {
  user(id: ID!): UserResult!
}

union UserResult = User | UserNotFoundError | PermissionError

type User {
  id: ID!
  name: String!
}

type UserNotFoundError {
  message: String!
  code: String!
}

type PermissionError {
  message: String!
  requiredRole: String!
}

// Resolver returning union
{
  Query: {
    user: async (_, { id }, { user: currentUser }) => {
      // Check auth
      if (!currentUser) {
        return {
          __typename: 'PermissionError',
          message: 'Not authenticated',
          requiredRole: 'USER'
        }
      }

      // Fetch user
      const user = await db.getUser(id)
      if (!user) {
        return {
          __typename: 'UserNotFoundError',
          message: `User ${id} not found`,
          code: 'USER_NOT_FOUND'
        }
      }

      return { __typename: 'User', ...user }
    }
  }
}

// Client handles union:
const query = gql`
  query GetUser($id: ID!) {
    user(id: $id) {
      ... on User {
        id
        name
      }
      ... on UserNotFoundError {
        message
        code
      }
    }
  }
`
```

## Production Checklist

- [ ] **Schema frozen**: Breaking changes backwards-compatible only
- [ ] **DataLoader enabled**: No N+1 queries
- [ ] **Query depth limited**: Max 7-10 levels
- [ ] **Query complexity limited**: Max 1000-5000 points
- [ ] **Introspection disabled**: In production (not in dev)
- [ ] **Field-level authorization**: Checked in resolvers, not schema
- [ ] **Error messages sanitized**: Don't expose stack traces
- [ ] **Rate limiting enabled**: Max 100 queries per minute per IP
- [ ] **Logging enabled**: Track slow queries, errors, auth failures
- [ ] **Monitoring**: Alert on high error rates, slow resolvers
- [ ] **Type generation**: graphql-codegen for client types
- [ ] **Testing**: Unit tests for resolvers, integration tests for queries

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| **Everything nullable** | Can't trust any field | Design nullability intentionally |
| **No DataLoader** | N+1 queries kill performance | Batch database queries |
| **No depth limiting** | Nested queries DoS server | Set maxQueryDepth = 7 |
| **Auth only in schema** | Fields still accessible via introspection | Check auth in resolvers |
| **Introspection in production** | Schema exposed to attackers | Disable in production |
| **Errors expose stack traces** | Security vulnerability | Return generic error messages |
| **No caching strategy** | Same query fetches data multiple times | Normalize Apollo cache, use @cached directive |
| **Subscriptions leak memory** | Subscribers never unsubscribed | Properly cleanup connections |
