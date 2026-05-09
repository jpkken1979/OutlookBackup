---
name: security-bluebook-builder
description: "Build security Blue Books—comprehensive threat models, security architecture documentation, and incident response playbooks for sensitive applications. Documents assets, threats, mitigations, compliance requirements, and runbooks. Use when building security architecture documentation, creating threat models, documenting compliance controls, building incident response playbooks, or creating security reference guides for development teams."
type: feature
source: "https://github.com/SHADOWPR0/security-bluebook-builder"
risk: safe
user-invocable: true
---

# Security Blue Book Builder

Create comprehensive security documentation that serves as both threat model and operational reference for sensitive applications.

## What Is a Blue Book?

A **Blue Book** = Threat Model + Security Architecture + Runbooks

| Component | Purpose | Audience |
|-----------|---------|----------|
| Threat Model | What can go wrong? | Architects, threat analysts |
| Security Architecture | How do we defend? | Engineers, code reviewers |
| Compliance Matrix | What rules apply? | Compliance, audit, leadership |
| Incident Runbooks | What do we do? | On-call, incident commanders |

## Blue Book Structure

```
Security Blue Book for [Application Name]
├── Executive Summary (1 page)
├── 1. Asset Inventory
│   ├── Data assets (what's protected)
│   ├── System components (services, databases, etc)
│   └── Third-party integrations
├── 2. Threat Model (STRIDE framework)
│   ├── Spoofing (authentication)
│   ├── Tampering (integrity)
│   ├── Repudiation (accountability)
│   ├── Information Disclosure (confidentiality)
│   ├── Denial of Service (availability)
│   └── Elevation of Privilege (authorization)
├── 3. Security Controls
│   ├── Preventive (block attacks)
│   ├── Detective (find attacks)
│   └── Reactive (respond to incidents)
├── 4. Compliance & Standards
│   ├── Applicable regulations (SOC2, HIPAA, GDPR, PCI-DSS)
│   ├── Specific requirements
│   └── Audit schedule
├── 5. Incident Response Runbooks
│   ├── Data breach procedures
│   ├── Service outage procedures
│   ├── Account compromise procedures
│   └── Escalation matrix
└── 6. Security Contacts & Resources
```

## Section 1: Asset Inventory

### Data Assets

```
| Asset | Classification | Sensitivity | Access |
|-------|----------------|-------------|--------|
| User PII (names, emails) | Restricted | High | Auth required |
| Payment card data | PCI-DSS | Critical | Encrypted only |
| API keys/credentials | Secret | Critical | Minimal access |
| Logs | Restricted | Medium | Security team |
| Public content | Public | Low | Anyone |
```

### System Components

```
- Web Application (React/Node/etc)
- API Gateway (entry point, rate limiting, auth)
- Database (PostgreSQL, encryption, backups)
- Cache Layer (Redis, access controls)
- Message Queue (authentication, encryption)
- Monitoring/Logging (Datadog, CloudWatch, Splunk)
- CDN (DDoS protection, authentication)
```

## Section 2: Threat Model (STRIDE)

### Example: User Authentication Threat

```
Threat: Attacker steals user credentials (Spoofing)

Attack vector:
- Brute force login
- Credential stuffing (reused passwords)
- Phishing users
- Compromised database dump

Likelihood: Medium
Impact: High (account takeover)

Mitigations:
1. Rate limiting (failed login attempts)
2. Multi-factor authentication (MFA)
3. Password complexity requirements
4. Monitor for breaches (HaveIBeenPwned)
5. Alert on suspicious access (impossible travel)
```

Complete matrix: Create similar analysis for 10+ key threats across all STRIDE categories.

## Section 3: Security Controls

### Preventive Controls (Avoid the problem)

```
Authentication & Authorization
- [ ] MFA required for sensitive actions
- [ ] Session timeout after 30 min inactivity
- [ ] Role-based access control (RBAC)
- [ ] Principle of least privilege enforced

Data Protection
- [ ] Encryption at rest (AES-256)
- [ ] Encryption in transit (TLS 1.3)
- [ ] Database encryption (transparent data encryption)
- [ ] API key rotation every 90 days

Network Security
- [ ] WAF (Web Application Firewall) configured
- [ ] Rate limiting enabled
- [ ] DDoS protection active
- [ ] IP whitelisting for admin access
```

### Detective Controls (Find the attack)

```
Monitoring & Logging
- [ ] All authentication attempts logged
- [ ] Database access audited
- [ ] API calls monitored
- [ ] Error rates tracked
- [ ] Suspicious patterns alerted

Threat Intelligence
- [ ] Vulnerability scanning (SAST, DAST)
- [ ] Dependency checking (SCA - software composition analysis)
- [ ] Config reviews (IaC scanning)
- [ ] Security testing (penetration tests quarterly)
```

### Reactive Controls (Respond to incident)

```
Incident Response Plan
- [ ] Detection: Alert fired within 5 min
- [ ] Response: Team paged within 10 min
- [ ] Containment: Attack blocked within 1 hour
- [ ] Investigation: Root cause within 24 hours
- [ ] Resolution: Patch deployed, verified
```

## Section 4: Compliance Matrix

```
| Regulation | Requirement | Implementation | Owner |
|-----------|-------------|----------------|-------|
| SOC 2 Type II | Access controls | RBAC + MFA | Security |
| SOC 2 Type II | Change management | Git reviews + approval | DevOps |
| GDPR | Data retention | Auto-delete after 1 year | Data engineer |
| GDPR | Right to deletion | API endpoint exists | Backend |
| PCI-DSS (if payment processing) | Card data encryption | AES-256 | DevSecOps |
```

## Section 5: Incident Response Runbooks

### Example: Data Breach Runbook

```
TRIGGER: Unauthorized data access detected

STEP 1: CONTAINMENT (First 30 minutes)
- [ ] Isolate affected database (stop application connections)
- [ ] Disable API keys associated with breach
- [ ] Rotate compromised credentials
- [ ] Notify security team (Slack + page on-call)
- [ ] Disable external integrations temporarily

STEP 2: INVESTIGATION (Within 2 hours)
- [ ] Pull access logs (who accessed what, when)
- [ ] Determine scope (how much data leaked)
- [ ] Identify attack vector (how did attacker get in)
- [ ] Check for persistence (backdoors)
- [ ] Interview relevant team members

STEP 3: NOTIFICATION (Within 24 hours)
- [ ] Legal review of notification requirements
- [ ] Notify affected users (email, in-app notification)
- [ ] Notify regulators if required (GDPR 72-hour rule)
- [ ] Post-mortem scheduled

STEP 4: REMEDIATION (Within 1 week)
- [ ] Patch vulnerability
- [ ] Add detective controls (enhanced monitoring)
- [ ] Deploy fix to production
- [ ] Verify no further unauthorized access
- [ ] Close incident

ESCALATION:
- Security team lead: Alerted immediately
- VP Security: If > 10K records exposed
- Legal: Always (notification decisions)
- CEO: If > 100K records or media attention
```

## Building Your Blue Book

### Step 1: Identify Critical Assets

What would damage you most if compromised?
- User data? Payment data? Trade secrets? Availability?

### Step 2: Map Threats (STRIDE)

For each asset, list realistic attack vectors.

### Step 3: List Controls

For each threat, what prevents/detects/responds?

### Step 4: Compliance Checklist

What regulations apply to your business?

### Step 5: Runbooks

Write step-by-step procedures for top 5 incident scenarios.

### Step 6: Review & Update

- Quarterly: Review for new threats
- Monthly: Test one incident runbook
- Annually: Full security assessment

## Blue Book Checklist

- [ ] Current as of [date], next review [future date]
- [ ] All stakeholders reviewed (Security, Ops, Legal)
- [ ] STRIDE threats covered for critical assets
- [ ] Controls mapped to all threats
- [ ] Compliance matrix complete and current
- [ ] Incident runbooks tested within past 90 days
- [ ] Escalation contacts current
- [ ] Access controls document who has read access
- [ ] Version controlled (GitHub/GitLab)

## Metrics: How to Know Your Blue Book Works

- Incident detection time: < 10 minutes
- Incident response time: < 1 hour
- Control effectiveness: Detected 95%+ of security tests
- Compliance audit findings: < 5 minor findings
- Team confidence: 80%+ of engineers can execute runbooks

See [source repository](https://github.com/SHADOWPR0/security-bluebook-builder) for templates and automation tools.
