---
name: openai-security-best-practices
description: >
type: feature
---
  Language and framework-specific security reviews with three modes:
  secure-by-default coding guidance, passive vulnerability detection during
  normal development, and full security report generation. Use when writing
  security-sensitive code, reviewing PRs for vulnerabilities, or generating
  security audit reports.
source: OpenAI (codex-universal)
type: feature
---

# Security Best Practices

Perform language-specific and framework-specific security reviews with three operational modes.

## Modes of Operation

### 1. Secure-by-Default Coding
When writing new code, apply security patterns by default:
- Use parameterized queries (never string interpolation for SQL)
- Validate and sanitize all user input
- Use constant-time comparison for secrets
- Apply principle of least privilege
- Default to deny for access control

### 2. Passive Detection
During normal development, silently detect:
- Hardcoded credentials or API keys
- SQL injection patterns
- XSS vulnerabilities in templates
- Insecure deserialization
- Path traversal risks
- Command injection via `shell=True` or equivalent
- Insecure cryptographic defaults
- Missing authentication/authorization checks

### 3. Full Security Report
Generate comprehensive report with:
- Vulnerability inventory (CRITICAL/HIGH/MEDIUM/LOW)
- Attack scenarios for each finding
- Remediation recommendations with code examples
- Compliance mapping (OWASP Top 10, CWE)

## Language-Specific Patterns

### Python
| Risk | Pattern | Fix |
|------|---------|-----|
| Command Injection | `subprocess.run(cmd, shell=True)` | `subprocess.run(shlex.split(cmd), shell=False)` |
| SQL Injection | `f"SELECT * FROM users WHERE id={uid}"` | `cursor.execute("SELECT * FROM users WHERE id=?", (uid,))` |
| Path Traversal | `open(user_path)` | Validate path with `Path.resolve()` and check prefix |
| Secrets | `API_KEY = "sk-..."` | `API_KEY = os.environ["API_KEY"]` |
| Deserialization | `pickle.loads(data)` | Use `json.loads()` or validated schemas |
| SSRF | `requests.get(user_url)` | Allowlist domains, validate URL scheme |

### TypeScript/JavaScript
| Risk | Pattern | Fix |
|------|---------|-----|
| XSS | `innerHTML = userInput` | Use `textContent` or sanitize with DOMPurify |
| Prototype Pollution | `Object.assign({}, userObj)` | Validate keys, use `Object.create(null)` |
| Path Traversal | `fs.readFile(userPath)` | Use `path.resolve()` + prefix check |
| ReDoS | Complex regex on user input | Use `re2` or limit input length |
| Injection | Template literals with user data | Use parameterized queries/templates |

### Go
| Risk | Pattern | Fix |
|------|---------|-----|
| SQL Injection | `fmt.Sprintf("SELECT... %s", input)` | Use `db.Query("SELECT... $1", input)` |
| Race Condition | Shared state without mutex | Use `sync.Mutex` or channels |
| Integer Overflow | Unchecked arithmetic | Use `math.SafeAdd` patterns |

## Report Template

```markdown
# Security Review Report

## Summary
- **Scope**: [files/modules reviewed]
- **Risk Level**: [CRITICAL/HIGH/MEDIUM/LOW]
- **Findings**: [count by severity]

## Findings

### [SEVERITY] Finding Title
- **Location**: `file.py:42`
- **CWE**: CWE-XXX
- **Description**: What the vulnerability is
- **Impact**: What an attacker could do
- **Remediation**: How to fix with code example
- **OWASP**: Category mapping

## Recommendations
[Prioritized list of actions]
```

## Integration

Works with:
- `security-threat-model` skill for architectural analysis
- `security-ownership-map` skill for identifying high-risk areas
- `differential-review` skill for PR-level security review
