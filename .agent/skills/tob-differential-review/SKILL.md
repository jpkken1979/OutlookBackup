---
name: tob-differential-review
type: feature
description: >
---
  Security-focused differential code review in 6 phases: triage, code analysis,
  test coverage, blast radius, adversarial thinking, and reporting. Uses STRIDE
  threat model and risk matrices. Use for security-oriented PR/diff reviews.
source: Trail of Bits
---

# Differential Security Review

6-phase security-focused code review for pull requests and diffs.

## Phase 1: Triage

Assess the change scope and determine review depth.

### Size Strategy

| Diff Size | Lines | Strategy |
|-----------|-------|----------|
| Small | < 100 | Full line-by-line review |
| Medium | 100-500 | Focus on security-relevant files |
| Large | 500-2000 | Prioritize auth, crypto, input handling |
| Massive | 2000+ | Split review, focus on high-risk areas |

### Quick Risk Assessment

```
HIGH RISK indicators:
- Auth/authz changes
- Crypto/hashing changes
- Input parsing/deserialization
- SQL/database queries
- File system operations
- Network/HTTP handlers
- Dependency updates
- Configuration changes

LOW RISK indicators:
- Documentation only
- Test-only changes
- Formatting/style
- Comment updates
```

## Phase 2: Code Analysis

### STRIDE Threat Model per Change

For each modified function/endpoint, evaluate:

| Threat | Question |
|--------|----------|
| **S**poofing | Can identity be faked? |
| **T**ampering | Can data be modified in transit/at rest? |
| **R**epudiation | Can actions be denied? (logging adequate?) |
| **I**nformation Disclosure | Can sensitive data leak? |
| **D**enial of Service | Can the system be overwhelmed? |
| **E**levation of Privilege | Can access controls be bypassed? |

### Security Anti-Patterns to Flag

```python
# 🚫 Hardcoded secrets
API_KEY = "sk-1234567890"

# 🚫 SQL injection
query = f"SELECT * FROM users WHERE id = {user_input}"

# 🚫 Command injection
os.system(f"convert {filename} output.png")
subprocess.run(command, shell=True)

# 🚫 Path traversal
file_path = base_dir + "/" + user_input

# 🚫 Insecure deserialization
data = pickle.loads(user_input)
obj = yaml.load(user_input)  # Missing Loader

# 🚫 Weak crypto
hashlib.md5(password.encode()).hexdigest()
random.randint(0, 999999)  # For security token
```

## Phase 3: Test Coverage

Verify the diff includes adequate tests:

- [ ] **New code paths** — Are new branches tested?
- [ ] **Error conditions** — Are failures tested?
- [ ] **Boundary values** — Edge cases covered?
- [ ] **Security-relevant** — Auth bypass, injection tested?
- [ ] **Regression** — Bug fix includes regression test?

### Coverage Assessment

```bash
# Check coverage on changed files only
git diff --name-only HEAD~1 | grep '\.py$' | while read f; do
    pytest --cov="$f" tests/ --cov-report=term-missing 2>/dev/null
done
```

## Phase 4: Blast Radius

Map the impact of changes across the codebase:

```bash
# Find all callers of changed functions
git diff --name-only HEAD~1 | while read f; do
    # Get changed function names
    git diff HEAD~1 -- "$f" | grep "^+.*def " | sed 's/.*def \(\w\+\).*/\1/' | while read fn; do
        echo "=== Callers of $fn ==="
        grep -rn "$fn" --include="*.py" . | grep -v "def $fn"
    done
done

# Check for breaking changes in public API
git diff HEAD~1 -- "*.py" | grep "^-.*def " | head -20
```

### Blast Radius Matrix

| Change Type | Check |
|------------|-------|
| Function signature | All callers updated? |
| Return type | All consumers handle new type? |
| Exception type | All handlers catch new exception? |
| Config format | All parsers updated? |
| API endpoint | All clients updated? |
| DB schema | Migration provided? Rollback plan? |

## Phase 5: Adversarial Thinking

Think like an attacker:

1. **What if inputs are malicious?** — Test with crafted payloads
2. **What if timing matters?** — Race conditions, TOCTOU
3. **What if state is corrupted?** — Partial failures, crashes mid-operation
4. **What if resources are exhausted?** — Memory, disk, file descriptors
5. **What if dependencies are compromised?** — Supply chain attacks

### Common Attack Vectors per Change Type

| Change | Attack Vector |
|--------|--------------|
| New API endpoint | Auth bypass, input injection, rate limiting |
| File upload | Path traversal, size bomb, malicious content |
| DB query | SQL injection, excessive data extraction |
| Auth flow | Token reuse, session fixation, bypass |
| Config parsing | YAML/JSON injection, env var override |
| Dependency update | Typosquatting, known CVEs, behavior change |

## Phase 6: Report

### Finding Template

```markdown
## [SEVERITY] Title

**Location**: `path/to/file.py:42`
**CWE**: CWE-XXX (Category Name)
**STRIDE**: [Category]

### Description
What the issue is and why it matters.

### Impact
What an attacker could do / what could go wrong.

### Reproduction
Steps or payload to trigger the issue.

### Recommendation
```python
# Suggested fix
```

### Risk Assessment
- Likelihood: HIGH/MEDIUM/LOW
- Impact: HIGH/MEDIUM/LOW
- Risk: likelihood × impact
```

### Severity Scale

| Severity | Criteria |
|----------|----------|
| CRITICAL | Remote code execution, auth bypass, data breach |
| HIGH | Privilege escalation, sensitive data leak, injection |
| MEDIUM | DoS, information disclosure, missing validation |
| LOW | Best practice violation, minor info leak |
| INFO | Code quality, style, documentation |
