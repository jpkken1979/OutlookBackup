---
name: compliance-governance
description: Compliance frameworks and governance. SOC2, HIPAA, GDPR, ISO27001 requirements, audit trails, data protection, regulatory mapping.
type: feature
category: security
tags: [compliance, governance, security, audit, data-protection, regulations]
version: 1.0.0
---

# Compliance & Governance

> Master compliance frameworks and build audit-ready systems.
> **Focus: REDUCE RISK, not just tick boxes.**

---

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `soc2.md` | SOC2 Type II requirements, controls, evidence | Building for enterprise |
| `hipaa.md` | HIPAA compliance, PHI handling, encryption | Healthcare systems |
| `gdpr.md` | GDPR data subjects rights, consent, DPA | EU customer data |
| `iso27001.md` | ISO 27001 ISMS framework, controls | International certification |
| `audit-trails.md` | Event logging, immutability, retention | Compliance evidence |
| `data-protection.md` | Encryption, access controls, DLP | Data privacy |
| `vendor-assessment.md` | Third-party risk, SLA verification | Supply chain risk |

---

## 🔗 Related Skills

| Need | Skill |
|------|-------|
| Security hardening | `@[skills/security-hardening]` |
| API security | `@[skills/api-patterns]` |
| Cloud infrastructure | `@[skills/devops-advanced]` |
| Database design | `@[skills/database-design]` |

---

## ✅ Compliance Checklist

Before deploying to production:

- [ ] **Identified applicable regulations?** (GDPR, HIPAA, SOC2, etc.)
- [ ] **Data flow mapped for compliance?**
- [ ] **Encryption configured** (at rest, in transit)?
- [ ] **Audit logging enabled?**
- [ ] **Access controls documented?**
- [ ] **Data retention policy defined?**
- [ ] **Vendor assessment completed?**
- [ ] **DPA signed** (if GDPR applies)?
- [ ] **Incident response plan?**

---

## Framework Comparison

| Framework | Focus | Scope | Cost | Timeline |
|-----------|-------|-------|------|----------|
| **SOC2** | Security/Availability | IT controls | High | 6-12 mo |
| **HIPAA** | Privacy/Security | Healthcare | High | 6+ mo |
| **GDPR** | Data privacy | EU/customers | Medium | Ongoing |
| **ISO27001** | Information security | Organization-wide | Very High | 12+ mo |

---

## Key Controls

### SOC2 Controls
- Encrypted storage of sensitive data
- MFA for administrative access
- Regular vulnerability scans
- Change management process
- Incident response procedures

### HIPAA Safeguards
- PHI access restricted to authorized staff
- Audit logs for all PHI access
- Encryption of ePHI
- Data integrity controls
- Breach notification procedures

### GDPR Requirements
- Legal basis for processing
- Data subject consent management
- Right to erasure implementation
- Data portability export
- DPIA for high-risk processing

### ISO27001 Controls
- Asset management inventory
- Access control policies
- Cryptography standards
- Personnel security training
- Incident management process

---

## ❌ Anti-Patterns

**DON'T:**
- Assume "we'll do compliance later"
- Store unencrypted sensitive data
- Skip audit logging to save costs
- Use same password for multiple systems
- Forget about vendor security
- Implement compliance without architecture changes
- Store backups in same region as primary

**DO:**
- Design for compliance from day 1
- Document everything (evidence)
- Encrypt by default
- Separate duties for sensitive operations
- Regular access reviews
- Test incident response
- Verify third-party security

---

## 📚 Reference Documents

- [SOC2 Trust Services Criteria](https://us.aicpa.org/interestareas/informationsystems/pages/aicpa-soc-2-attestation-standards.aspx)
- [HIPAA Final Rule](https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/index.html)
- [GDPR Official Text](https://gdpr-info.eu/)
- [ISO 27001:2022](https://www.iso.org/standard/75652.html)

---

## Script

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/compliance_mapper.py` | Map requirements to implementation | `python scripts/compliance_mapper.py <framework>` |
| `scripts/audit_trail_validator.py` | Validate audit log completeness | `python scripts/audit_trail_validator.py <logs_dir>` |
