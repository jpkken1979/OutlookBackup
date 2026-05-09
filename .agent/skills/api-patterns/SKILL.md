---
name: api-patterns
description: >-
type: feature
---
  Use when designing or implementing APIs (REST, GraphQL, tRPC). Triggers:
  design API, endpoint creation, trpc router, graphql schema, response format,
  api versioning, rate limiting.
metadata:
  category: reference
  author: ozy
  triggers: REST, GraphQL, tRPC, API design, versioning, pagination, JWT, OAuth, token bucket
  references: Rules.md, AGENTS.md
type: feature
---

# API Excellence (God Mode) 🚀

Expert principles for designing scalable, type-safe, and secure APIs for 2026.

## 💎 Core Principles (Axioms)
1. **Type-Safety by Default**: Prefer type-safe protocols like tRPC or GraphQL for internal services. Use OpenAPI for public REST.
2. **Resource-Oriented**: REST endpoints must represent resources (nouns), never actions (verbs).
3. **Fail Fast & Explicitly**: Use appropriate HTTP status codes (4xx/5xx) and consistent error envelopes.
4. **Idempotency is Key**: Ensure PUT/DELETE and idempotent POST operations don't cause side effects on retry.
5. **Security First**: Never expose internal IDs (use UUIDs); always rate limit; always validate at the boundary.

## 🛠️ Step-by-Step Selection
1. **Internal TS Project?** -> Use **tRPC**. (Full type-safety, zero boilerplate).
2. **Public / Mobile App?** -> Use **REST** + OpenAPI. (Universal compatibility).
3. **Complex / Graph Data?** -> Use **GraphQL**. (Flexible queries, solves over-fetching).
4. **Define Envelope**: Standardize `{ data: T, error: string | null, meta: any }`.
5. **Set Security**: Implement Auth (JWT/OAuth) + Rate Limiting before exposing.

## 🛡️ Security & Quality Checklist
- [ ] **Boundary Validation**: Are all inputs validated (Zod/Pydantic/Rust types)?
- [ ] **Rate Limiting**: Is there a token bucket or leaking bucket implementation?
- [ ] **Versioning**: Is the API versioned in the URI (v1) or Headers?
- [ ] **PII Leakage**: Are we accidentally returning passwords, internal IDs, or secrets?
- [ ] **Pagination**: Are lists paginated (cursor-based preferred for high scale)?

## 📚 Examples (Few-shot)

### Example: Resource-Oriented REST
```http
// ❌ BAD
POST /getUsersByRole?role=admin
GET /delete_user/123

// ✅ GOOD (God Mode)
GET /users?role=admin
DELETE /users/uuid-456
```

### Example: tRPC Router (Type-Safe)
```typescript
// ✅ God Mode: Type-safe boundary
export const userRouter = router({
  getById: publicProcedure
    .input(z.string().uuid()) // Strong validation
    .query(async ({ input }) => {
      return await db.users.findUnique(input);
    }),
});
```

---
*Skill: api-patterns v2.0 (Bibek Poudel Edition)*
