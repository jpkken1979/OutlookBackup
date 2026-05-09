---
type: feature
name: judgment-day
description: >-
---
  Use when a high-stakes changes or complex architecture needs validation.
  Triggers: judgment day, adversarial review, blind audit, conflict resolution,
  finalize review.
metadata:
  category: quality
  author: ozy
  triggers: judgment day, review, audit, verify, adversarial, judge
  references: Rules.md, AGENTS.md, Gentle-AI patterns
---

# Judgment Day (God Mode) ⚖️

Expert framework for dual adversarial review and deterministic conflict resolution.

## 💎 Core Principles (Axioms)
1. **Dual Blind Review**: Two distinct personas (e.g., Security vs DX) must review the implementation WITHOUT seeing each other's notes first.
2. **Conflict is Truth**: The "Judge" does not choose a winner; they synthesize a superior solution from the friction.
3. **No Pass without Proof**: A "Pass" requires evidence of successful test execution, not just code reading.
4. **The Fix Loop is Mandatory**: Any "Blocked" or "Critical" finding requires a re-Implementation and re-Validation cycle.
5. **Zero Hallucination**: If the reviewer is unsure about a side effect, they MUST run a test or Grep search before reporting.

## 🛠️ Step-by-Step implementation
1. **The Selection Phase**: Choose two contrasting personas (e.g., **Architect** for structure, **Security** for safety).
2. **The Audit Phase**: Each persona performs a "Deep Scan" of the implementation against the original Spec and Design.
3. **The Sentencing Phase**: Each reviewer provides a score (0-10) and a list of "Blockers".
4. **The Judgment Phase**: The Orchestrator reviews both reports, identifies conflicts, and provides a final "Verdict" with required fixes.
5. **The Clearance Phase**: Once all blockers are fixed, the change is "Cleared for Handoff".

## 🛡️ Security & Quality Checklist
- [ ] **Dual Review**: Did at least two different agents (or persona lenses) audit the change?
- [ ] **Spec Compliance**: Does the implementation match the Delta Spec Exactly?
- [ ] **Regression Check**: Did we run existing tests to ensure no breakage?
- [ ] **Conflict Log**: Are all trade-offs between reviewers documented?
- [ ] **Sentinel Pass**: Does the code pass `lint_runner.py` and `security_scan.py`?

## 📚 Examples (Few-shot)

### Example: Adversarial Conflict Report
```markdown
## Judgment Day Report
- **Reviewer A (Performance)**: "The O(n^2) loop is acceptable for this data size."
- **Reviewer B (Scalability)**: "Reject. Data size will grow 10x next month."
- **Verdict**: Refactor to O(n log n) using a hash map. Implementation Blocked.
```

### Example: Final Clearance
```markdown
## Final Verdict: CLEARED ✅
All blockers from the Security Audit (SQLi vulnerability) have 
been fixed using Parameterized Queries. Performance benchmarks 
pass. Change is ready for Handoff.
```

---
*Skill: judgment-day v1.0 (Gentle AI Edition)*
