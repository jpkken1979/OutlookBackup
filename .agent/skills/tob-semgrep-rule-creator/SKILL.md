---
name: tob-semgrep-rule-creator
type: feature
description: >
---
  Create custom Semgrep rules with taint mode prioritized. Test-first mandatory
  workflow with AST analysis. Covers 7-step creation process, anti-patterns,
  and strict quality requirements. Use when writing Semgrep security rules.
source: Trail of Bits
---

# Semgrep Rule Creator

Create high-quality custom Semgrep rules with a test-first, taint-mode-prioritized approach.

## 7-Step Workflow

### Step 1: Define the Vulnerability

```yaml
# What are you detecting?
vulnerability: SQL injection via string concatenation
language: python
cwe: CWE-89
severity: ERROR
```

### Step 2: Write Test Cases FIRST

```python
# test_sql_injection.py

# ruleid: sql-injection-concat
cursor.execute("SELECT * FROM users WHERE id = " + user_input)

# ruleid: sql-injection-fstring
cursor.execute(f"SELECT * FROM users WHERE id = {user_input}")

# ok: sql-parameterized
cursor.execute("SELECT * FROM users WHERE id = %s", (user_input,))

# ok: sql-constant
cursor.execute("SELECT * FROM users WHERE id = 1")
```

### Step 3: Analyze the AST

```bash
# View the AST to understand pattern structure
semgrep --dump-ast python test_sql_injection.py

# Or use semgrep playground: https://semgrep.dev/playground
```

### Step 4: Choose Rule Type

| Type | When to Use |
|------|-------------|
| **Taint** (preferred) | Data flows from source to sink |
| **Pattern** | Structural code matching |
| **Pattern + metavariable** | Conditional structural matching |
| **Join** | Cross-file/cross-function patterns |

### Step 5: Write the Rule (Taint Mode Preferred)

```yaml
rules:
  - id: sql-injection-concat
    message: >
      Potential SQL injection: user-controlled data flows into SQL query
      without parameterization. Use parameterized queries instead.
    severity: ERROR
    languages: [python]
    metadata:
      cwe:
        - CWE-89: SQL Injection
      category: security
      technology:
        - python
      confidence: HIGH
    mode: taint
    pattern-sources:
      - patterns:
          - pattern: |
              def $FUNC(..., $PARAM, ...):
                  ...
      - pattern: flask.request.$ATTR
      - pattern: request.args.get(...)
      - pattern: request.form[...]
    pattern-sinks:
      - patterns:
          - pattern: $CURSOR.execute($QUERY, ...)
          - focus-metavariable: $QUERY
    pattern-sanitizers:
      - pattern: int(...)
      - pattern: str(int(...))
```

### Step 6: Test the Rule

```bash
# Run against test file
semgrep --config rule.yaml test_sql_injection.py

# Verify true positives (ruleid: comments)
# Verify true negatives (ok: comments)

# Run against real codebase
semgrep --config rule.yaml /path/to/project
```

### Step 7: Iterate and Refine

```bash
# Check for false positives
semgrep --config rule.yaml /path/to/project --json | \
  jq '.results | length'

# Verbose output for debugging
semgrep --config rule.yaml --verbose test_file.py
```

## Pattern-Based Rule (Alternative)

```yaml
rules:
  - id: subprocess-shell-true
    patterns:
      - pattern: subprocess.$FUNC(..., shell=True, ...)
    message: >
      subprocess called with shell=True. Use shell=False with
      shlex.split() to prevent command injection.
    severity: WARNING
    languages: [python]
    metadata:
      cwe:
        - CWE-78: OS Command Injection
```

## Common Taint Sources

```yaml
# Web frameworks
- pattern: flask.request.$ATTR
- pattern: request.GET[...]
- pattern: request.POST[...]
- pattern: request.args.get(...)
- pattern: $REQ.query.$PARAM
- pattern: $REQ.body.$PARAM
- pattern: $REQ.params.$PARAM

# Environment / config
- pattern: os.environ[...]
- pattern: os.getenv(...)

# File / network
- pattern: $FILE.read()
- pattern: $SOCKET.recv(...)
- pattern: json.loads(...)
- pattern: yaml.safe_load(...)
```

## Common Taint Sinks

```yaml
# SQL
- pattern: $CURSOR.execute($QUERY, ...)
- pattern: $DB.raw($QUERY)

# Command execution
- pattern: subprocess.run($CMD, ...)
- pattern: os.system($CMD)
- pattern: os.popen($CMD)

# File operations
- pattern: open($PATH, ...)
- pattern: pathlib.Path($PATH)

# HTML rendering
- pattern: $RESPONSE.write($DATA)
- pattern: render_template_string($TPL)
```

## Quality Requirements

1. **Test-first** — Every rule must have test cases before implementation
2. **No false positives** — All `ok:` test cases must pass silently
3. **All true positives caught** — All `ruleid:` test cases must trigger
4. **Taint over pattern** — Prefer taint mode for data flow issues
5. **Metadata complete** — CWE, category, technology, confidence required
6. **Message actionable** — Tell the developer what to do, not just what's wrong
7. **Severity calibrated** — ERROR for exploitable, WARNING for risky, INFO for style

## Anti-Patterns

| Anti-Pattern | Problem |
|-------------|---------|
| Overly broad patterns | Too many false positives |
| Missing sanitizers | Flags safe code as vulnerable |
| No test cases | Can't verify correctness |
| Pattern when taint needed | Misses data flow through variables |
| `...` overuse | Matches unintended code |
| Missing `focus-metavariable` | Highlights wrong part of match |
