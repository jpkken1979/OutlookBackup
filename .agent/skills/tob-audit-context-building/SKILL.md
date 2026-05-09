---
name: tob-audit-context-building
description: >
type: feature
---
  Build security audit context for a codebase before deep review. Systematic
  reconnaissance to understand attack surface, architecture, dependencies,
  and trust boundaries. Use before performing security audits.
source: Trail of Bits
type: feature
---

# Security Audit Context Building

Pre-audit reconnaissance to map attack surface and architecture.

## Phase 1: Repository Reconnaissance

```bash
# Basic info
wc -l $(find . -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.go") 2>/dev/null | tail -1
find . -name "*.py" | wc -l
find . -name "*.ts" -o -name "*.tsx" | wc -l

# Framework detection
grep -r "from flask" --include="*.py" -l | head -5
grep -r "from django" --include="*.py" -l | head -5
grep -r "from fastapi" --include="*.py" -l | head -5
grep -r '"express"' --include="package.json" | head -5
grep -r '"next"' --include="package.json" | head -5
```

## Phase 2: Map Architecture

### Entry Points
```bash
# HTTP endpoints / routes
grep -rn "app.route\|@router\|@app.get\|@app.post" --include="*.py" .
grep -rn "app.get\|app.post\|app.put\|app.delete" --include="*.ts" --include="*.js" .
grep -rn "export.*GET\|export.*POST" --include="*.ts" .  # Next.js route handlers

# CLI entry points
grep -rn "argparse\|click\|typer\|if __name__" --include="*.py" .

# Event handlers / webhooks
grep -rn "webhook\|event.*handler\|on_message\|on_event" --include="*.py" .
```

### Data Stores
```bash
# Databases
grep -rn "DATABASE_URL\|POSTGRES\|MYSQL\|SQLITE\|MONGO" --include="*.py" --include="*.env*" .
grep -rn "create_engine\|sessionmaker\|connect" --include="*.py" .

# Caches
grep -rn "REDIS\|MEMCACHE\|cache" --include="*.py" --include="*.env*" .

# File storage
grep -rn "open(\|Path(\|os.path" --include="*.py" .
grep -rn "S3\|BUCKET\|blob\|storage" --include="*.py" .
```

### External Services
```bash
# API calls
grep -rn "requests.get\|requests.post\|httpx\|aiohttp\|fetch(" --include="*.py" --include="*.ts" .

# Environment variables (potential service connections)
grep -rn "os.environ\|os.getenv\|process.env" --include="*.py" --include="*.ts" . | \
  grep -oP '([\w_]+_URL|[\w_]+_KEY|[\w_]+_SECRET|[\w_]+_TOKEN)' | sort -u
```

## Phase 3: Trust Boundaries

Map where untrusted data enters the system:

| Boundary | Source | Trust Level |
|----------|--------|-------------|
| HTTP requests | Users | UNTRUSTED |
| Webhook payloads | External services | LOW TRUST |
| Database queries | Internal | MEDIUM TRUST |
| Config files | Operators | HIGH TRUST |
| Environment vars | Infrastructure | HIGH TRUST |
| IPC messages | Internal processes | MEDIUM TRUST |

### Auth & Access Control
```bash
# Authentication mechanisms
grep -rn "authenticate\|login\|jwt\|token\|session\|oauth\|api.key" --include="*.py" .
grep -rn "middleware\|auth\|permission\|role\|guard" --include="*.py" --include="*.ts" .

# Authorization checks
grep -rn "is_admin\|has_permission\|require_role\|@login_required" --include="*.py" .
```

## Phase 4: Dependency Audit

```bash
# Python dependencies
pip-audit 2>/dev/null || pip install pip-audit && pip-audit
safety check 2>/dev/null

# Node dependencies
npm audit
npx better-npm-audit audit

# Check for known vulnerable versions
grep -E "requests==|django==|flask==" requirements.txt pyproject.toml 2>/dev/null
```

## Phase 5: Sensitive Operations

```bash
# Crypto usage
grep -rn "hashlib\|hmac\|encrypt\|decrypt\|AES\|RSA\|bcrypt\|argon2" --include="*.py" .
grep -rn "crypto\|createHash\|createCipher" --include="*.ts" --include="*.js" .

# Subprocess / command execution
grep -rn "subprocess\|os.system\|os.popen\|exec(" --include="*.py" .
grep -rn "child_process\|exec\|spawn" --include="*.ts" --include="*.js" .

# Deserialization
grep -rn "pickle\|yaml.load\|json.loads\|eval(" --include="*.py" .
grep -rn "JSON.parse\|eval(" --include="*.ts" --include="*.js" .

# File operations with user input
grep -rn "open.*request\|Path.*request\|send_file" --include="*.py" .
```

## Output: Audit Context Document

```markdown
# Security Audit Context: [Project Name]

## Overview
- Language: Python 3.11 + TypeScript
- Framework: FastAPI + React
- LoC: ~25,000
- Dependencies: 45 Python, 120 npm

## Attack Surface
- 15 HTTP endpoints (8 authenticated, 7 public)
- 2 webhook receivers
- 1 CLI tool
- WebSocket connections

## Trust Boundaries
[Diagram or table]

## Data Stores
- PostgreSQL (user data, transactions)
- Redis (sessions, cache)
- S3 (file uploads)

## High-Risk Areas
1. File upload handler (path traversal risk)
2. Custom JWT implementation (crypto review needed)
3. Admin API (privilege escalation surface)
4. Webhook signature validation (SSRF risk)

## Dependencies of Concern
- [package@version] — Known CVE-XXXX-XXXX
- [package] — Unmaintained (last update 2 years ago)

## Prioritized Audit Plan
1. [HIGH] Auth/authz flow
2. [HIGH] File upload handling
3. [MEDIUM] API input validation
4. [MEDIUM] Dependency vulnerabilities
5. [LOW] Logging/error handling
```
