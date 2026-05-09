---
name: openai-security-threat-model
description: >
type: feature
---
  Repo-grounded threat modeling with trust boundaries, abuse paths,
  and prioritized mitigations. 8-step workflow from scope definition to
  quality check. Use when analyzing security architecture, identifying
  attack surfaces, or planning security hardening.
source: OpenAI (codex-universal)
type: feature
---

# Security Threat Model

Build threat models grounded in actual repository code, not abstract diagrams.

## 8-Step Workflow

### Step 1: Define Scope
- Identify the system boundary (repo, service, module)
- List entry points: APIs, CLI args, file inputs, IPC, network listeners
- List exit points: external calls, file writes, database queries

### Step 2: Identify Trust Boundaries
Map where trust levels change:
```
[Untrusted]          [Trust Boundary]       [Trusted]
User Input    →      Validation Layer  →    Business Logic
External API  →      Auth Middleware   →    Internal Service
File Upload   →      Sanitization     →    Storage Layer
```

### Step 3: Calibrate Risk
Based on:
- Data sensitivity (PII, credentials, financial)
- Exposure (internet-facing vs internal)
- Blast radius (single user vs all users)
- Reversibility (data loss vs temporary disruption)

### Step 4: Enumerate Threats (STRIDE)

| Category | Question | Example |
|----------|----------|---------|
| **S**poofing | Can identity be faked? | JWT without signature verification |
| **T**ampering | Can data be modified? | Unsigned API parameters |
| **R**epudiation | Can actions be denied? | Missing audit logs |
| **I**nformation Disclosure | Can data leak? | Error messages with stack traces |
| **D**enial of Service | Can availability be affected? | Unbounded file upload |
| **E**levation of Privilege | Can permissions be bypassed? | IDOR on user endpoints |

### Step 5: Prioritize
Use risk matrix:

| | Low Impact | Medium Impact | High Impact |
|---|-----------|---------------|-------------|
| **High Likelihood** | Medium | High | Critical |
| **Medium Likelihood** | Low | Medium | High |
| **Low Likelihood** | Info | Low | Medium |

### Step 6: Validate Against Code
For each threat:
- Find the actual code path (file:line)
- Check existing mitigations
- Verify test coverage
- Assess exploitability

### Step 7: Recommend Mitigations
Prioritized by:
1. Critical + no existing mitigation
2. High + partial mitigation
3. Medium + easy fix
4. Low + tracking needed

### Step 8: Quality Check
- [ ] Every entry point has at least one threat
- [ ] Every critical threat has a mitigation plan
- [ ] Findings reference specific code locations
- [ ] Risk ratings are justified
- [ ] No generic/template threats without evidence

## Output Template

```markdown
# Threat Model: [System Name]

## Scope
- **Boundary**: [what's included]
- **Entry Points**: [list with code refs]
- **Data Assets**: [what's protected]

## Trust Boundaries
[Diagram or description]

## Threat Inventory
| ID | Category | Threat | Risk | Location | Mitigation |
|----|----------|--------|------|----------|------------|
| T1 | Spoofing | ... | HIGH | auth.py:42 | Implement JWT validation |

## Recommended Actions
1. [Highest priority action]
2. [Next priority]
```

## Integration
- Use `security-best-practices` for code-level fixes
- Use `security-ownership-map` for identifying unmaintained high-risk areas
- Use `differential-review` for ongoing PR security review
