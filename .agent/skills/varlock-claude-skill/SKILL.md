---
name: varlock-claude-skill
type: feature
description: "Implements secure environment variable management that prevents secrets, API keys, credentials, and sensitive data from being exposed in Claude sessions, terminal output, logs, or git commits. Manages .env files, vault integration, secret rotation, and automatic sanitization. Use when handling API keys, database credentials, tokens, managing secrets in development, preventing secret leaks in code reviews, or securing environment-based configuration."
source: "https://github.com/wrsmith108/varlock-claude-skill"
risk: safe
user-invocable: true
---

# Varlock: Secure Environment Management

Prevent secret exposure across all system boundaries: Claude conversations, terminal output, logs, version control, and monitoring systems.

## Threat Model: Where Secrets Leak

### 1. **Claude Context Windows**
```
❌ Don't: Print API key: sk_prod_12345 in code
❌ Don't: Paste .env content for debugging
❌ Don't: Show DB passwords in connection strings

✓ Do: Show redacted version: API key: sk_prod_****
✓ Do: Use ${ENV_VAR} syntax, not values
✓ Do: Reference "see .env file" instead of pasting
```

### 2. **Terminal Output & Logs**
```
❌ Bad: echo "Password: $DB_PASSWORD"
❌ Bad: curl -H "Authorization: Bearer $TOKEN"

✓ Good: echo "Password: [REDACTED]"
✓ Good: curl -H "Authorization: Bearer ****$(echo $TOKEN | tail -c 4)"
```

### 3. **Git Commits**
```
❌ Never: git add .env (env files always in .gitignore)
❌ Never: commit "updated credentials" with plaintext
✓ Always: .env → .gitignore from day 1
✓ Always: .env.example with dummy values

If secret leaked in history:
1. git filter-branch --force (remove from all history)
2. Force push to remote
3. Rotate the secret immediately
```

### 4. **Error Messages & Tracebacks**
```
❌ Error: "Connection failed: postgres://user:password@host/db"
✓ Error: "Connection failed: database (credential redacted)"
✓ Log the error code, not the credentials
```

## Implementation Strategy

### Layer 1: Load Time (Secure by Default)

```python
# Bad
import os
TOKEN = os.getenv('API_TOKEN')  # Could be printed/exposed
print(f"Using token: {TOKEN}")

# Good
import os
TOKEN = os.getenv('API_TOKEN')
print(f"Using token: {TOKEN[:8]}****")  # Only show first 8 chars
```

### Layer 2: Transmission (No Leakage in Code)

```bash
# Bad
curl https://api.example.com \
  -H "Authorization: Bearer $API_KEY"  # Shows in bash history!

# Good
curl https://api.example.com \
  -H "Authorization: Bearer $(cat .env | grep API_KEY | cut -d= -f2)"
  # Or better: Use .netrc or credentials file
```

### Layer 3: Storage (Encrypted at Rest)

| Storage Type | Security | When to Use |
|--------------|----------|------------|
| **.env file** (plaintext) | ❌ Low | Development only, in .gitignore |
| **.env.vault** (encrypted) | ✓ Medium | Team development with shared secrets |
| **HashiCorp Vault** | ✓✓ High | Production, audit logs, rotation |
| **AWS Secrets Manager** | ✓✓ High | AWS deployments, automatic rotation |
| **1Password/Vault** | ✓ High | Team vaults with audit trail |

### Layer 4: Redaction (Sanitize Output)

Pattern to sanitize secrets in all output:

```python
# Common patterns to redact automatically
PATTERNS = [
  r'sk_[a-z0-9]{20,}',  # Stripe keys
  r'Bearer [A-Za-z0-9_-]{20,}',  # JWT tokens
  r'[A-Za-z0-9]{32}=[A-Za-z0-9]{32}',  # AWS credentials
  r'password["\']?\s*[:=]\s*["\']?[^"\']*["\']?',  # Password assignments
]

def sanitize_output(text):
    for pattern in PATTERNS:
        text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
    return text
```

## Management Workflows

### Dev Environment Setup
1. Create `.env` file locally (never commit)
2. Add to `.gitignore`: `*.env`, `.env*`, `credentials*`
3. Create `.env.example` with placeholder values
4. Document required variables in README

### Team Sharing
- **Option A**: Use 1Password/Vault share specific secrets
- **Option B**: Use Secrets Manager with per-team access
- **Option C**: Never share secrets; each dev gets own credentials with same access level

### Secret Rotation Checklist
- [ ] Old secret still works (30-day overlap)
- [ ] All services updated to new secret
- [ ] All logs rotated (old logs with old secret archived)
- [ ] Passwords changed in password manager
- [ ] Old secret fully disabled

### Monitoring & Alerts

```
Set up alerts for:
1. Secret mentioned in code (pre-commit hook)
2. Secret printed to stdout (grep logs)
3. Secret in error traceback
4. Failed auth attempts (indicates wrong credential)
```

## Pre-Commit Hook (Automatic Protection)

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Prevent committing .env files
if git diff --cached --name-only | grep -E '\.env|secrets|credentials'; then
  echo "❌ Blocked: .env or credentials file in commit"
  exit 1
fi

# Prevent committing common secret patterns
if git diff --cached | grep -E 'sk_live_|password=|api_key='; then
  echo "❌ Blocked: Potential secrets in diff"
  exit 1
fi
```

## Troubleshooting: Secret Already Exposed

If a secret was committed:

1. **Stop using it immediately**
2. **Rotate in the service** (change password, revoke API key)
3. **Remove from git history**: `git filter-branch --force --prune-empty --index-filter "git rm -r -f --cached --ignore-unmatch filename" HEAD`
4. **Force push**: `git push origin master --force` (only if allowed)
5. **Update team**: Everyone force-pulls the clean history
6. **Monitor**: Watch service logs for unauthorized access attempts

## Quick Reference

| Scenario | Action | Don't |
|----------|--------|-------|
| Need to show code to Claude | Redact values, show `.env` structure | Paste actual credentials |
| Deploying to production | Use Secrets Manager, validate load | Commit .env to repo |
| Team collaborating | Share via vault, unique per-person secrets | Email credentials |
| Error in logs | Show error code, redact context | Log the full error with secrets |

See [source repository](https://github.com/wrsmith108/varlock-claude-skill) for implementation tools and integration examples.
