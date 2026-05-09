---
name: api-design-complete
description: "Guía completa para diseñar APIs REST, GraphQL y gRPC de calidad producción. Covers: convenciones URLs, status codes, request/response format, pagination, filtering, versioning, JWT structure, OAuth 2.0 flows, rate limiting, OpenAPI specification. Triggers: api design, rest, graphql, grpc, openapi, swagger, endpoint design, http status codes."
type: feature
---

# API Design Complete Guide

> Guía completa para diseñar APIs REST, GraphQL y gRPC de calidad producción.

## Cuándo Usar Esta Skill

- Diseñando nuevas APIs
- Mejorando APIs existentes
- Documentando APIs
- Code review de APIs

---

## REST API Design

### Convenciones de URLs

```
# Recursos (sustantivos, plural)
GET    /users              # Lista usuarios
GET    /users/123          # Usuario específico
POST   /users              # Crear usuario
PUT    /users/123          # Actualizar usuario completo
PATCH  /users/123          # Actualizar parcialmente
DELETE /users/123          # Eliminar usuario

# Recursos anidados
GET    /users/123/orders   # Órdenes del usuario 123
POST   /users/123/orders   # Crear orden para usuario 123

# Acciones (verbos, cuando necesario)
POST   /users/123/activate # Acción específica
POST   /orders/123/cancel  # Cancelar orden
```

### HTTP Status Codes

```
2xx Success:
  200 OK             - GET exitoso, PUT/PATCH exitoso
  201 Created        - POST exitoso (incluir Location header)
  204 No Content     - DELETE exitoso

3xx Redirection:
  301 Moved Permanently
  304 Not Modified   - Para caching

4xx Client Error:
  400 Bad Request    - Validación fallida
  401 Unauthorized   - No autenticado
  403 Forbidden      - No autorizado
  404 Not Found      - Recurso no existe
  409 Conflict       - Conflicto (duplicado, versión)
  422 Unprocessable  - Validación de negocio fallida
  429 Too Many Requests - Rate limited

5xx Server Error:
  500 Internal Error - Error genérico
  502 Bad Gateway    - Upstream falló
  503 Unavailable    - Mantenimiento/sobrecarga
  504 Gateway Timeout
```

### Request/Response Format

```json
// Request (POST /users)
{
  "name": "John Doe",
  "email": "john@example.com",
  "role": "admin"
}

// Response (201 Created)
{
  "data": {
    "id": "123",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "admin",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "meta": {
    "request_id": "abc-123"
  }
}

// Error Response (400 Bad Request)
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      {"field": "email", "message": "Invalid email format"}
    ]
  },
  "meta": {
    "request_id": "abc-123"
  }
}
```

### Pagination

```
# Offset-based (simple pero problemas con datos cambiantes)
GET /users?offset=20&limit=10

Response:
{
  "data": [...],
  "pagination": {
    "total": 100,
    "offset": 20,
    "limit": 10,
    "has_more": true
  }
}

# Cursor-based (mejor para datos cambiantes)
GET /users?cursor=abc123&limit=10

Response:
{
  "data": [...],
  "pagination": {
    "next_cursor": "def456",
    "has_more": true
  }
}
```

### Filtering & Sorting

```
# Filtering
GET /users?status=active&role=admin
GET /users?created_at[gte]=2024-01-01
GET /users?name[contains]=john

# Sorting
GET /users?sort=created_at:desc,name:asc

# Sparse fieldsets
GET /users?fields=id,name,email
GET /users/123?include=orders,profile
```

### Versioning

```
# URL versioning (más explícito)
GET /v1/users
GET /v2/users

# Header versioning (más limpio)
GET /users
Accept: application/vnd.api+json; version=2

# Query param (fácil testing)
GET /users?version=2
```

---

## GraphQL Design

### Schema Design

```graphql
# Types
type User {
  id: ID!
  name: String!
  email: String!
  orders: [Order!]!
  profile: Profile
  createdAt: DateTime!
}

type Order {
  id: ID!
  total: Float!
  status: OrderStatus!
  items: [OrderItem!]!
  user: User!
}

enum OrderStatus {
  PENDING
  PAID
  SHIPPED
  DELIVERED
  CANCELLED
}

# Queries
type Query {
  user(id: ID!): User
  users(
    filter: UserFilter
    pagination: PaginationInput
  ): UserConnection!
}

# Mutations
type Mutation {
  createUser(input: CreateUserInput!): CreateUserPayload!
  updateUser(id: ID!, input: UpdateUserInput!): UpdateUserPayload!
  deleteUser(id: ID!): DeleteUserPayload!
}

# Input types
input CreateUserInput {
  name: String!
  email: String!
}

# Payload types (para errores)
type CreateUserPayload {
  user: User
  errors: [UserError!]!
}

type UserError {
  field: String
  message: String!
}
```

### N+1 Problem Solution

```python
# DataLoader pattern
from promise import Promise
from promise.dataloader import DataLoader

def batch_load_users(user_ids):
    users = User.objects.filter(id__in=user_ids)
    user_map = {u.id: u for u in users}
    return Promise.resolve([user_map.get(id) for id in user_ids])

user_loader = DataLoader(batch_load_users)

# En resolver
def resolve_user(order, info):
    return user_loader.load(order.user_id)
```

---

## gRPC Design

### Proto Definition

```protobuf
syntax = "proto3";

package user.v1;

service UserService {
  // Unary
  rpc GetUser(GetUserRequest) returns (User);
  rpc CreateUser(CreateUserRequest) returns (User);
  
  // Server streaming
  rpc ListUsers(ListUsersRequest) returns (stream User);
  
  // Client streaming
  rpc CreateUsers(stream CreateUserRequest) returns (CreateUsersResponse);
  
  // Bidirectional streaming
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

message User {
  string id = 1;
  string name = 2;
  string email = 3;
  google.protobuf.Timestamp created_at = 4;
}

message GetUserRequest {
  string id = 1;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
  UserFilter filter = 3;
}

message UserFilter {
  optional string status = 1;
  optional string role = 2;
}
```

---

## Authentication & Authorization

### JWT Structure

```
Header.Payload.Signature

Header:
{
  "alg": "RS256",
  "typ": "JWT"
}

Payload:
{
  "sub": "user-123",        # Subject (user ID)
  "iat": 1704067200,        # Issued at
  "exp": 1704153600,        # Expiration
  "iss": "auth.example.com", # Issuer
  "aud": "api.example.com",  # Audience
  "roles": ["admin"],        # Custom claims
  "permissions": ["read:users", "write:users"]
}
```

### OAuth 2.0 Flows

```
# Authorization Code (web apps)
1. User → App: Click "Login"
2. App → Auth Server: Redirect to /authorize
3. User → Auth Server: Login + consent
4. Auth Server → App: Redirect with code
5. App → Auth Server: Exchange code for tokens
6. Auth Server → App: access_token + refresh_token

# Client Credentials (service-to-service)
POST /oauth/token
{
  "grant_type": "client_credentials",
  "client_id": "...",
  "client_secret": "...",
  "scope": "read:users"
}
```

---

## Rate Limiting

```
Headers:
X-RateLimit-Limit: 100        # Max requests
X-RateLimit-Remaining: 95     # Remaining
X-RateLimit-Reset: 1704067200 # Reset timestamp

Response (429):
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retry_after": 60
  }
}

Algorithms:
- Token Bucket: Allows bursts
- Sliding Window: Smoother limiting
- Fixed Window: Simple but bursty at edges
```

---

## API Security Checklist

- [ ] HTTPS only
- [ ] Authentication en todos los endpoints
- [ ] Authorization (RBAC/ABAC)
- [ ] Input validation
- [ ] Output encoding
- [ ] Rate limiting
- [ ] CORS configurado
- [ ] Security headers (HSTS, CSP, etc.)
- [ ] No expose internal errors
- [ ] Audit logging

---

## OpenAPI Specification

```yaml
openapi: 3.0.3
info:
  title: User API
  version: 1.0.0
  
servers:
  - url: https://api.example.com/v1

paths:
  /users:
    get:
      summary: List users
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [active, inactive]
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/User'
    post:
      summary: Create user
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateUserInput'
      responses:
        '201':
          description: Created

components:
  schemas:
    User:
      type: object
      required: [id, name, email]
      properties:
        id:
          type: string
        name:
          type: string
        email:
          type: string
          format: email
```

---

*Skill: api-design-complete v1.0*
