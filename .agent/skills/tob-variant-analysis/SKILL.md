---
name: tob-variant-analysis
type: feature
description: >
---
  Find all variants of a known vulnerability across a codebase. Systematic
  pattern expansion from a single bug to discover similar issues using grep,
  Semgrep, and manual analysis. Use after finding a bug to check for similar ones.
source: Trail of Bits
---

# Variant Analysis

Systematically find all instances of a known vulnerability pattern across the codebase.

## Workflow

### Step 1: Characterize the Original Bug

```markdown
## Bug Profile
- **Type**: [e.g., SQL injection, buffer overflow, auth bypass]
- **Root cause**: [e.g., unsanitized user input in query string]
- **Pattern**: [e.g., string concatenation into SQL query]
- **File**: [location of original finding]
- **CWE**: [CWE-XXX]
```

### Step 2: Extract the Vulnerable Pattern

From the original bug, identify the abstract pattern:

```python
# Original bug:
cursor.execute(f"SELECT * FROM users WHERE id = {request.args['id']}")

# Abstract pattern:
# cursor.execute(<string with user input interpolated>)
# More broadly: <SQL executor>(<string concatenation with untrusted data>)
```

### Step 3: Search for Variants

#### Level 1: Exact Match (grep)
```bash
# Search for identical pattern
grep -rn "cursor.execute(f\"" --include="*.py" .
grep -rn "cursor.execute.*+" --include="*.py" .
grep -rn "\.execute.*format" --include="*.py" .
```

#### Level 2: Structural Match (Semgrep)
```yaml
rules:
  - id: sql-injection-variants
    patterns:
      - pattern-either:
          - pattern: $DB.execute(f"...", ...)
          - pattern: $DB.execute("..." + $VAR, ...)
          - pattern: $DB.execute("...".format(...), ...)
          - pattern: $DB.execute("..." % $VAR, ...)
    languages: [python]
    message: Potential SQL injection variant
    severity: ERROR
```

```bash
semgrep --config variant-rule.yaml .
```

#### Level 3: Semantic Match (Taint Analysis)
```yaml
rules:
  - id: sql-injection-taint
    mode: taint
    pattern-sources:
      - pattern: request.$ATTR[...]
      - pattern: request.$ATTR.get(...)
      - pattern: flask.request.$ATTR
    pattern-sinks:
      - pattern: $CURSOR.execute($QUERY, ...)
        focus-metavariable: $QUERY
      - pattern: $CURSOR.executemany($QUERY, ...)
        focus-metavariable: $QUERY
      - pattern: $DB.raw($QUERY)
        focus-metavariable: $QUERY
    pattern-sanitizers:
      - pattern: int(...)
      - pattern: $CURSOR.mogrify(...)
    languages: [python]
    severity: ERROR
```

#### Level 4: Cross-Language Variants
```bash
# Same vulnerability pattern in different languages
grep -rn "query.*\+" --include="*.js" --include="*.ts" .
grep -rn "query.*\$\{" --include="*.js" --include="*.ts" .
grep -rn "`.*SELECT.*\$\{" --include="*.ts" .
```

### Step 4: Categorize Findings

| Finding | File | Exploitable | Notes |
|---------|------|-------------|-------|
| Variant 1 | `api/users.py:42` | Yes | Direct user input |
| Variant 2 | `api/orders.py:88` | Maybe | Input from DB (2nd order) |
| Variant 3 | `lib/search.py:15` | No | Input is type-checked int |

### Step 5: Expand Search Patterns

After finding variants, broaden the search:

```
Original: SQL injection via string concatenation
├── Variant A: Same pattern, different SQL executor (raw(), fetchone())
├── Variant B: Same pattern, different input source (form, headers, cookies)
├── Variant C: Similar pattern, different sink (ORM raw query, template rendering)
└── Variant D: Same root cause, different language (JS backend)
```

## Pattern Expansion Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| **Same sink, different source** | Other inputs reaching same vulnerable function | request.form instead of request.args |
| **Same source, different sink** | Same untrusted data reaching other dangerous functions | User input → os.system instead of cursor.execute |
| **Same pattern, different API** | Similar vulnerability in different libraries | pymysql vs psycopg2 vs sqlite3 |
| **Cross-language** | Same logical bug in different language codebase | Python backend + Node.js microservice |
| **Temporal** | Similar pattern introduced in other commits | `git log -p --all -S 'execute(f"'` |

## Automation Script

```bash
#!/bin/bash
# variant-scan.sh — Search for variants of a known pattern

PATTERN="$1"
LANG="${2:-py}"

echo "=== Exact matches ==="
grep -rn "$PATTERN" --include="*.$LANG" .

echo ""
echo "=== Similar patterns ==="
# Generate related patterns
echo "$PATTERN" | sed 's/execute/exec/g' | xargs -I{} grep -rn "{}" --include="*.$LANG" .

echo ""
echo "=== Git history ==="
git log --oneline --all -S "$PATTERN" | head -20
```

## Reporting

```markdown
## Variant Analysis Report

**Original Finding**: [reference to original bug]
**Pattern**: [abstract vulnerability pattern]
**Scope**: [files/directories searched]

### Findings Summary
- Total variants found: X
- Confirmed exploitable: Y
- Requires investigation: Z
- False positives: W

### Detailed Findings
[Table of findings with location, severity, and status]

### Recommendations
1. Fix all confirmed variants
2. Add Semgrep rule to CI to prevent recurrence
3. Review `[related module]` for similar patterns
```
