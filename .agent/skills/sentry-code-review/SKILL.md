---
name: sentry-code-review
description: >
type: feature
---
  Structured code review following Sentry engineering practices. Covers runtime
  errors, performance (N+1 queries), security, test coverage, and framework-specific
  patterns for Python/Django and TypeScript/React. Use for thorough code reviews.
type: feature
source: Sentry

# Code Review — Sentry Engineering Practices

Systematic code review checklist focused on production reliability.

## Review Checklist

### 1. Runtime Errors (Priority: CRITICAL)

- [ ] **Null/undefined access** — Are all optional values checked before use?
- [ ] **Type mismatches** — Do function args match expected types?
- [ ] **Index out of bounds** — Are array/list accesses guarded?
- [ ] **Division by zero** — Are denominators validated?
- [ ] **Uncaught exceptions** — Are async errors properly handled?
- [ ] **Resource cleanup** — Are connections/files/locks properly closed?

```python
# BAD — unguarded access
user = get_user(user_id)
name = user.name  # RuntimeError if user is None

# GOOD — guarded
user = get_user(user_id)
if user is None:
    raise ValueError(f"User {user_id} not found")
name = user.name
```

### 2. Performance (Priority: HIGH)

- [ ] **N+1 queries** — Are related objects eagerly loaded?
- [ ] **Missing indexes** — Are filtered/sorted columns indexed?
- [ ] **Unbounded queries** — Do queries have LIMIT clauses?
- [ ] **Memory leaks** — Are large objects cleaned up?
- [ ] **Blocking I/O in async** — Is I/O properly awaited?

```python
# BAD — N+1 query
for order in Order.objects.all():
    print(order.customer.name)  # Query per iteration

# GOOD — eager loading
for order in Order.objects.select_related("customer").all():
    print(order.customer.name)  # Single query
```

```typescript
// BAD — fetching in a loop
for (const id of userIds) {
  const user = await db.user.findUnique({ where: { id } });
}

// GOOD — batch fetch
const users = await db.user.findMany({ where: { id: { in: userIds } } });
```

### 3. Security (Priority: HIGH)

- [ ] **SQL injection** — Are queries parameterized?
- [ ] **XSS** — Are user inputs sanitized before rendering?
- [ ] **Auth checks** — Are endpoints properly protected?
- [ ] **Secret exposure** — Are tokens/keys in env vars, not code?
- [ ] **Path traversal** — Are file paths validated?
- [ ] **SSRF** — Are external URLs validated?

```python
# BAD — SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# GOOD — parameterized
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### 4. Test Coverage (Priority: MEDIUM)

- [ ] **Happy path covered** — Do tests verify normal operation?
- [ ] **Edge cases** — Empty inputs, large inputs, boundary values?
- [ ] **Error paths** — Are error conditions tested?
- [ ] **Regression** — Does the fix include a test for the bug?
- [ ] **Integration** — Are external dependencies mocked appropriately?

```python
# Minimum test structure
def test_create_user_success():
    """Happy path."""
    ...

def test_create_user_duplicate_email():
    """Error case — duplicate."""
    ...

def test_create_user_empty_name():
    """Edge case — empty input."""
    ...
```

### 5. Code Quality (Priority: MEDIUM)

- [ ] **Single responsibility** — Does each function do one thing?
- [ ] **Naming clarity** — Are variables/functions self-documenting?
- [ ] **DRY** — Is logic duplicated unnecessarily?
- [ ] **Complexity** — Can nested conditionals be simplified?
- [ ] **Documentation** — Are complex algorithms documented?

## Framework-Specific Patterns

### Python / Django

| Pattern | Check |
|---------|-------|
| `select_related` / `prefetch_related` | Used for FK/M2M access in loops |
| `transaction.atomic()` | Multi-step DB ops are transactional |
| `F()` expressions | Used instead of read-modify-write for counters |
| QuerySet evaluation | `.exists()` instead of `len(qs) > 0` |
| Migrations | Backward-compatible, no data loss |

### TypeScript / React

| Pattern | Check |
|---------|-------|
| `useEffect` dependencies | Complete and correct dep arrays |
| Memoization | `useMemo`/`useCallback` for expensive computations |
| Error boundaries | Components wrapped for graceful failure |
| Bundle size | No unnecessary large imports |
| Key prop | Unique, stable keys in lists |

## Feedback Guidelines

1. **Be specific** — Point to exact line and explain the issue
2. **Explain why** — Not just "this is wrong" but "this causes X"
3. **Suggest fix** — Provide a concrete code alternative
4. **Prioritize** — Label: `[CRITICAL]`, `[HIGH]`, `[MEDIUM]`, `[NIT]`
5. **Be kind** — Review the code, not the person

### Feedback Template

```
[PRIORITY] **Category**: Brief description

**Problem**: What's wrong and why it matters.
**Impact**: What could happen in production.
**Suggestion**:
```python
# Suggested fix
```
```

## Review Flow

1. **Understand context** — Read PR description, linked issues
2. **Run locally** — Build and test the changes
3. **Review diff** — Go through changes file by file
4. **Check tests** — Verify coverage and quality
5. **Verify observability** — Logging, metrics, error tracking
6. **Approve or request changes** — With specific, actionable feedback
