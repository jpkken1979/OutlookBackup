---
name: security-testing
description: Security testing methodologies and tools. OWASP Top 10, penetration testing, fuzzing, vulnerability scanning, threat modeling, security assessment.
type: feature
category: security
tags: [security, testing, owasp, penetration, vulnerability, fuzzing, threat-modeling]
version: 1.0.0
---

# Security Testing

> Find vulnerabilities BEFORE attackers do.
> **Test like you're under attack.**

---

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `owasp-top10.md` | API Top 10, Web Top 10 vulnerabilities | Starting security testing |
| `penetration-testing.md` | Scope, reconnaissance, exploitation, reporting | Authorized pentest |
| `vulnerability-scanning.md` | Tool selection, automation, false positive handling | Regular scanning |
| `fuzzing.md` | Input validation testing, protocol fuzzing | API/binary testing |
| `threat-modeling.md` | Attack trees, data flow analysis, risk scoring | Architecture design |
| `security-assessment.md` | Checklist-based testing, scoring | Quick security audit |
| `secret-detection.md` | API key leaks, credential scanning | Pre-deployment check |

---

## 🔗 Related Skills

| Need | Skill |
|------|-------|
| Secure code | `@[skills/security-hardening]` |
| Compliance mapping | `@[skills/compliance-governance]` |
| API design | `@[skills/api-patterns]` |
| Cloud security | `@[skills/devops-advanced]` |

---

## ✅ Security Testing Checklist

Before production deployment:

- [ ] **OWASP assessment completed?**
- [ ] **Input validation fuzzing done?**
- [ ] **Authentication/Authorization tested?**
- [ ] **API rate limiting verified?**
- [ ] **Secrets scanning passed?**
- [ ] **Dependency vulnerabilities checked?**
- [ ] **SQL injection tested?** (if database)
- [ ] **XSS vectors tested?** (if web)
- [ ] **CSRF tokens verified?**
- [ ] **Response headers hardened?**
- [ ] **Penetration test scheduled?** (if enterprise)

---

## OWASP API Top 10

| # | Vulnerability | Risk | Fix |
|---|---------------|------|-----|
| 1 | Broken Object Level Authorization | High | Verify ownership before returning data |
| 2 | Broken Authentication | High | Implement MFA, rate limit logins |
| 3 | Broken Object Property Level Authorization | High | Filter response fields per user role |
| 4 | Unrestricted Resource Consumption | Medium | Rate limiting, input validation |
| 5 | Broken Function Level Authorization | High | Check permissions on every endpoint |
| 6 | Unrestricted Access to Sensitive Business Flows | Medium | Risk-based auth, anomaly detection |
| 7 | Server-Side Request Forgery | Medium | Whitelist URLs, disable internal redirects |
| 8 | Security Misconfiguration | Medium | CIS benchmarks, scanning, hardening |
| 9 | Improper Inventory Management | Medium | Document all API versions, deprecations |
| 10 | Unsafe Consumption of APIs | Medium | Validate external API responses |

---

## Testing Tools & Commands

### Static Analysis
```bash
# Dependency scanning
npm audit
pip-audit
poetry audit

# Secret detection
detect-secrets scan
gitleaks detect --verbose

# Code quality
semgrep --config=p/security-audit
bandit -r . -ll
```

### Dynamic Testing
```bash
# API fuzzing
ffuf -w wordlist.txt -u http://api/api/FUZZ -mc 200

# SQL injection testing
sqlmap -u "http://api/users?id=1" --dbs

# XSS testing
zaproxy -cmd -quickurl http://app
```

### Vulnerability Scanning
```bash
# Network scan
nmap -sV -p- <target>

# Web application scan
nessus -x <policy.nessus> <target>

# Container scanning
trivy image <image-name>
grype <image-name>
```

---

## Threat Modeling Template

```
Threat Model: [System Name]
Date: [YYYY-MM-DD]

1. Assets
   - What are we protecting? (data, availability, reputation)

2. Threat Actors
   - Who might attack? (external hackers, disgruntled employees)

3. Attack Vectors
   - How could they attack? (network, physical, social engineering)

4. Likelihood
   - How likely is each threat? (1-5 scale)

5. Impact
   - What's the damage if attacked? (financial, reputational)

6. Mitigations
   - What controls prevent/reduce risk?

7. Residual Risk
   - What remains after mitigations?
```

---

## ❌ Anti-Patterns

**DON'T:**
- Only test what's obvious
- Skip security testing for "time"
- Trust user input ever
- Keep default credentials
- Disable security features for convenience
- Assume "nobody would attack us"
- Test with production data
- Ignore low-severity vulnerabilities

**DO:**
- Test like an attacker thinks
- Fuzz all input
- Verify authentication/authorization
- Use WAF/API gateway rules
- Scan dependencies regularly
- Fix high/critical immediately
- Document findings clearly
- Retest after fixes

---

## Penetration Testing Scope

### Reconnaissance
- Passive information gathering (OSINT)
- Active scanning (network mapping)
- Technology stack identification

### Enumeration
- Service identification
- Vulnerability assessment
- Configuration review

### Exploitation
- Proof of concept attacks
- Privilege escalation
- Data access verification

### Reporting
- Executive summary
- Detailed findings
- Risk scoring
- Remediation roadmap

---

## Script

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/owasp_checker.py` | OWASP Top 10 checklist | `python scripts/owasp_checker.py --project <path>` |
| `scripts/secret_scanner.py` | Detect API keys and credentials | `python scripts/secret_scanner.py <repo_path>` |
| `scripts/threat_model_generator.py` | Generate threat model template | `python scripts/threat_model_generator.py --system <name>` |
