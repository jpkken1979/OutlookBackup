---
name: database-design
description: >-
type: feature
---
  Use when designing schemas, optimizing queries, or selecting database tech.
  Triggers: database schema, sql optimization, index strategy, migrations,
  drizzle, prisma, postgresql, normalization.
metadata:
  category: architect
  author: ozy
  triggers: database, SQL, schema, normalization, index, migration, drizzle, prisma, postgres, redis, N+1
  references: Rules.md, AGENTS.md
---

# Database Mastery (God Mode) 🗄️

Advanced architectural principles for data persistence, consistency, and extreme performance.

## 💎 Core Principles (Axioms)
1. **Consistency over Convenience**: Strict schemas and foreign keys are mandatory. No "orphan" data.
2. **Index with Intent**: Every index must justify its existence (Read speed vs Write overhead). Avoid indexing everything.
3. **Type-Safe Persistence**: Use ORMs that mirror your database types (Drizzle, Kysely, Diesel).
4. **Data Locality**: Keep related data close. Prefer JOINs over application-side manual filtering.
5. **Safe Evolution**: All schema changes must be versioned (migrations) and backward-compatible (expand-contract).

## 🛠️ Step-by-Step implementation
1. **The Normalization Phase**: Reach 3NF. Eliminate redundancy. Use junction tables for M-M.
2. **The Type Mapping Phase**: Define types/schemas (Drizzle/Zod). Ensure TS/Rust types match SQL exactly.
3. **The Indexing Phase**: Add indexes to `WHERE`, `JOIN`, and `ORDER BY` columns. Use `EXPLAIN ANALYZE`.
4. **The Migration Phase**: Generate and test migration scripts. Validate backfills for new `NOT NULL` columns.

## 🛡️ Security & Quality Checklist
- [ ] **SQL Injection**: Are we using parameterized queries or a safe ORM?
- [ ] **PII Protection**: Is sensitive data (emails, phones) encrypted at rest?
- [ ] **N+1 Prevention**: Are we using eager loading (joins) for related entities?
- [ ] **Connection Pooling**: Is a pooler (PgBouncer/Drizzle Pool) configured for high concurrency?
- [ ] **Audit Logs**: Do critical tables have `created_at`, `updated_at`, and `deleted_at`?

## 📚 Examples (Few-shot)

### Example: Normalization (God Mode)
```sql
// ❌ BAD: Denormalized orders
orders (id, customer_name, customer_email, product_price)

// ✅ GOOD (3NF): God Mode
customers (id, email, name)
products (id, price, category)
orders (id, customer_id, product_id, price_at_purchase)
```

### Example: Type-Safe Schema (Drizzle)
```typescript
// ✅ God Mode: Exact type mirror
export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  email: text('email').unique().notNull(),
  role: text('role', { enum: ['admin', 'user'] }).default('user'),
});
```

---
*Skill: database-design v2.0 (Bibek Poudel Edition)*
ection limits** | Database overwhelmed | Use connection pooling, limit concurrent connections |
