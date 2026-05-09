---
name: tob-property-based-testing
type: feature
description: >
---
  Property-based testing strategies using Hypothesis (Python), fast-check (JS/TS),
  and proptest (Rust). Covers property catalogs (roundtrip, idempotence, invariant,
  commutativity), auto-detection of testable patterns, and decision trees.
source: Trail of Bits
---

# Property-Based Testing

Generate thousands of test cases automatically by defining properties that must always hold.

## Property Catalog

### 1. Roundtrip (Encode/Decode)

If you encode then decode, you get the original back.

```python
from hypothesis import given
import hypothesis.strategies as st

@given(st.text())
def test_json_roundtrip(s):
    import json
    assert json.loads(json.dumps(s)) == s

@given(st.binary())
def test_base64_roundtrip(data):
    import base64
    assert base64.b64decode(base64.b64encode(data)) == data

@given(st.text())
def test_url_encode_roundtrip(s):
    from urllib.parse import quote, unquote
    assert unquote(quote(s)) == s
```

```typescript
import fc from 'fast-check';

test('JSON roundtrip', () => {
  fc.assert(
    fc.property(fc.anything(), (value) => {
      expect(JSON.parse(JSON.stringify(value))).toEqual(value);
    })
  );
});
```

### 2. Idempotence

Applying the operation twice gives the same result as once.

```python
@given(st.text())
def test_strip_idempotent(s):
    assert s.strip().strip() == s.strip()

@given(st.lists(st.integers()))
def test_sort_idempotent(lst):
    assert sorted(sorted(lst)) == sorted(lst)

@given(st.text())
def test_normalize_idempotent(s):
    result = normalize(s)
    assert normalize(result) == result
```

### 3. Invariants

Properties that must always hold regardless of input.

```python
@given(st.lists(st.integers()))
def test_sort_preserves_length(lst):
    assert len(sorted(lst)) == len(lst)

@given(st.lists(st.integers()))
def test_sort_preserves_elements(lst):
    assert sorted(lst) == sorted(sorted(lst))
    assert set(sorted(lst)) == set(lst)

@given(st.lists(st.integers(), min_size=1))
def test_sort_ordered(lst):
    result = sorted(lst)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]
```

### 4. Commutativity

Order of operations doesn't matter.

```python
@given(st.integers(), st.integers())
def test_addition_commutative(a, b):
    assert a + b == b + a

@given(st.sets(st.integers()), st.sets(st.integers()))
def test_union_commutative(a, b):
    assert a | b == b | a

@given(st.text(), st.text())
def test_merge_commutative(a, b):
    # Only if your merge is designed to be commutative
    assert merge(a, b) == merge(b, a)
```

### 5. Equivalence (Oracle)

Two implementations should produce the same result.

```python
@given(st.lists(st.integers()))
def test_custom_sort_matches_stdlib(lst):
    assert my_sort(lst) == sorted(lst)

@given(st.text())
def test_optimized_search_matches_naive(text):
    assert optimized_search(text) == naive_search(text)
```

### 6. Metamorphic

Known relationship between modified input and output.

```python
@given(st.lists(st.integers()), st.integers())
def test_sort_append(lst, x):
    """Adding an element preserves sortedness."""
    result = sorted(lst + [x])
    assert x in result
    assert len(result) == len(lst) + 1

@given(st.text(), st.text())
def test_concat_length(a, b):
    assert len(a + b) == len(a) + len(b)
```

## Auto-Detection: When to Use Each Property

| Code Pattern | Property Type |
|-------------|--------------|
| `serialize` / `deserialize` | Roundtrip |
| `parse` / `format` | Roundtrip |
| `encode` / `decode` | Roundtrip |
| `compress` / `decompress` | Roundtrip |
| `normalize`, `clean`, `sanitize` | Idempotence |
| `sort`, `deduplicate` | Idempotence |
| `format`, `prettify` | Idempotence |
| `add`, `insert`, `remove` | Invariant (size, membership) |
| `transform`, `map` | Invariant (structure preserved) |
| Set operations (`union`, `intersect`) | Commutativity |
| Math operations | Commutativity |
| Any refactored/optimized code | Equivalence |

## Hypothesis Strategies (Python)

```python
from hypothesis import given, settings, assume
import hypothesis.strategies as st

# Primitives
st.integers()
st.floats(allow_nan=False)
st.text(min_size=1, max_size=100)
st.binary(min_size=1, max_size=1024)
st.booleans()

# Collections
st.lists(st.integers(), min_size=0, max_size=50)
st.dictionaries(st.text(), st.integers())
st.tuples(st.integers(), st.text())
st.sets(st.integers())

# Constrained
st.integers(min_value=0, max_value=100)
st.text(alphabet=st.characters(whitelist_categories=("L", "N")))

# Complex / composite
@st.composite
def user_strategy(draw):
    name = draw(st.text(min_size=1, max_size=50))
    age = draw(st.integers(min_value=0, max_value=150))
    email = draw(st.emails())
    return {"name": name, "age": age, "email": email}

# Usage
@given(user_strategy())
def test_user_processing(user):
    result = process_user(user)
    assert result["name"] == user["name"]
```

## fast-check Strategies (TypeScript)

```typescript
import fc from 'fast-check';

// Primitives
fc.integer()
fc.float()
fc.string()
fc.boolean()

// Collections
fc.array(fc.integer())
fc.dictionary(fc.string(), fc.integer())

// Complex
const userArb = fc.record({
  name: fc.string({ minLength: 1, maxLength: 50 }),
  age: fc.integer({ min: 0, max: 150 }),
  email: fc.emailAddress(),
});

test('user processing', () => {
  fc.assert(
    fc.property(userArb, (user) => {
      const result = processUser(user);
      expect(result.name).toBe(user.name);
    })
  );
});
```

## Decision Tree

```
Is there an encode/decode or serialize/deserialize pair?
  → YES → Write ROUNDTRIP test

Is the function supposed to be self-stable (running twice = running once)?
  → YES → Write IDEMPOTENCE test

Does the function preserve some structural property?
  → YES → Write INVARIANT test (length, membership, ordering)

Is there a known mathematical relationship?
  → YES → Write COMMUTATIVITY or METAMORPHIC test

Is there another implementation to compare against?
  → YES → Write EQUIVALENCE (oracle) test

None of the above?
  → Write INVARIANT tests on output properties
  → Write "does not crash" tests (no exceptions on any input)
```

## Best Practices

1. **Start with roundtrips** — Highest value-to-effort ratio
2. **Use `assume()` sparingly** — Prefer constrained strategies over filtering
3. **Set reasonable sizes** — `max_size=100` prevents slow tests
4. **Seed failures** — Add `@example(failing_input)` for regression
5. **Combine with unit tests** — PBT complements, doesn't replace
6. **Run more examples in CI** — `@settings(max_examples=1000)` in CI
