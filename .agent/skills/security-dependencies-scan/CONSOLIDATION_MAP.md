# Consolidation Map — Security Scanning Skills Group

## Primary Skill

This is the **Dependency Vulnerability & Supply Chain Security** specialist skill.

**Name:** `security-dependencies-scan`
**Focus:** Vulnerability analysis, SBOM generation, supply chain security
**Best for:** Auditing dependencies, license compliance, remediation planning

---

## Related Skills in This Group

### 1. `security-sast-scan` — Static Application Security Testing

**Relationship:** **Complementary — Different scope**

- **Overlap:** Both perform code security scanning
- **Difference:**
  - `security-sast-scan`: Analyzes **source code** for vulnerabilities (SQL injection, XSS, hardcoded secrets, path traversal)
  - `security-dependencies-scan`: Analyzes **dependencies** for known CVEs and license risks
- **When to use each:**
  - Use `security-sast-scan` for **custom code review**
  - Use `security-dependencies-scan` for **third-party library security**
- **Combined workflow:**
  1. Run `security-dependencies-scan` to identify vulnerable dependencies
  2. Run `security-sast-scan` to find custom code issues
  3. Prioritize by CVSS score across both results

---

### 2. `security-hardening-scan` — Multi-Layer Defense-in-Depth

**Relationship:** **Orchestrator — Dependency scanning is one phase**

- **Overlap:** Includes dependency scanning as Phase 1
- **Difference:**
  - `security-hardening-scan`: **Coordinates** 13-phase hardening program (assessment → remediation → validation)
  - `security-dependencies-scan`: **Specializes** in dependency analysis only
- **When to use each:**
  - Use `security-hardening-scan` for **complete security program** across app, infra, CI/CD
  - Use `security-dependencies-scan` for **focused dependency audit**
- **Combined workflow:**
  1. Start with `security-hardening-scan` for full program
  2. Let it delegate to `security-dependencies-scan` in Phase 1 (dependency scanning)
  3. Continue with Phases 2-4 for remediation and compliance

---

### 3. `cc-skill-security-review` — Code Security Checklist

**Relationship:** **Complementary — Different level**

- **Overlap:** Both address security
- **Difference:**
  - `cc-skill-security-review`: **Checklist** for developers (secrets, input validation, XSS, CSRF, auth)
  - `security-dependencies-scan`: **Automated scanning** for dependency vulnerabilities
- **When to use each:**
  - Use `cc-skill-security-review` when **writing/reviewing code**
  - Use `security-dependencies-scan` when **auditing project dependencies**
- **Combined workflow:**
  - Use both in PRs:
    1. `cc-skill-security-review`: Manual developer checklist before commit
    2. `security-dependencies-scan`: Automated CI/CD step to verify dependencies

---

### 4. `security-scanning` — DEPRECATED

- **Status:** Moved to `_deprecated/` folder
- **Reason:** Redundant with `security-sast-scan` and `security-dependencies-scan`
- **Migration:** Use specific skills instead

---

### 5. `security-scanner` — DEPRECATED

- **Status:** Moved to `_deprecated/` folder
- **Reason:** Replaced by specialized skills (`security-sast-scan`, `security-dependencies-scan`, etc.)
- **Migration:** Use specific skills instead

---

## Decision Matrix

| Scenario | Primary Skill | Secondary Skills |
|----------|---------------|------------------|
| **Audit dependencies for CVEs** | `security-dependencies-scan` | — |
| **Generate SBOM** | `security-dependencies-scan` | `cc-skill-security-review` (for license checks) |
| **Review source code** | `cc-skill-security-review` | `security-sast-scan` (automated) |
| **Full security hardening program** | `security-hardening-scan` | All of the above (delegates) |
| **Fix specific CVE in dependency** | `security-dependencies-scan` | `security-sast-scan` (if code impact) |
| **Pre-deployment security check** | `cc-skill-security-review` | `security-dependencies-scan` |

---

## Why They're Separate (Not Merged)

1. **Different specializations:** Dependency analysis ≠ code analysis ≠ hardening orchestration
2. **Tool chains:** Each uses different tools (Snyk/Trivy vs Semgrep/Bandit vs manual review)
3. **Reusability:** Can be invoked independently or as part of larger workflows
4. **Maintenance:** Easier to update one tool in isolation
5. **CLI/API usage:** Different entry points and parameters

---

## Recommended Usage Pattern

```python
# In orchestration or skill composition:

# Step 1: Dependency audit
await run_skill("security-dependencies-scan", {
    "target": "project_path",
    "sbom": True,
    "remediation": True
})

# Step 2: Code review checklist (manual developer step)
await run_skill("cc-skill-security-review", {
    "checklist": "pre-deployment"
})

# Step 3: Automated code scanning (CI/CD)
await run_skill("security-sast-scan", {
    "languages": ["python", "javascript"],
    "tool": "semgrep"
})

# Result: Comprehensive security coverage
```

---

## Cross-References

- **Data source:** `.agent/skills/security-dependencies-scan/SKILL.md`
- **Related group:** `security-sast-scan`, `cc-skill-security-review`, `security-hardening-scan`
- **Deprecated:** `security-scanner`, `security-scanning` (in `_deprecated/`)
- **Organization doc:** `.context/SKILLS_ORGANIZATION.md` (master index)
