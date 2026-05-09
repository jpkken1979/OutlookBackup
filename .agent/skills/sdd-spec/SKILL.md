---
name: sdd-spec
description: >-
type: feature
---
  Use when writing technical specifications for a change. Uses the "Delta Spec"
  pattern (Added/Modified/Removed). Triggers: write spec, technical design,
  delta spec, requirements.
metadata:
  category: architect
  author: ozy
  triggers: spec, specification, delta, sdd, requirements, technical design
  references: Rules.md, AGENTS.md, Gentle-AI patterns
---

# Spec Writer (God Mode) 📝

Expert system for writing precise, actionable Delta Specifications.

## 💎 Core Principles (Axioms)
1. **Delta-First**: Specify ONLY what changes. Use explicit headers: `### ADDED`, `### MODIFIED`, `### REMOVED`.
2. **Behavioral Contract**: Use Given/When/Then for complex logic to ensure testability.
3. **No Ambiguity**: Specify exact function signatures, types, and error states.
4. **Traceability**: Every spec point must map to a specific user requirement or architectural constraint.
5. **The Proof of Work**: A spec is not done until it defines the "Winning State" (how we know it passed).

## 🛠️ Step-by-Step implementation
1. **The Context Phase**: Read the `proposal.md` and current codebase.
2. **The Mapping Phase**: Identify the exact files and lines that will be touched.
3. **The Drafting Phase**: Write the Delta Spec using the template below.
4. **The Validation Phase**: Review the spec against the "Sharp Edges" found in Discovery.

## 🛡️ Spec Quality Checklist
- [ ] **Completeness**: Are all 3 sections (Added/Modified/Removed) addressed?
- [ ] **Precision**: Are types and signatures explicitly defined (e.g., `(user_id: string) -> Promise<Result>`)?
- [ ] **Edge Cases**: Does the spec define behavior for nulls, network failures, or unauthorized access?
- [ ] **Testability**: If an engineer reads this, can they write a failing test immediately?
- [ ] **Impact Analysis**: Does it list any Breaking Changes?

## 📚 Delta Spec Template

```markdown
# Spec: [Change Name]

## 🎯 Goal
One sentence summary.

## 🛠️ Delta Changes

### ➕ ADDED
- `file/path.ts`: New component for X.
- `api/v1/auth`: Endpoint for Y.

### 📝 MODIFIED
- `existing/file.py`: Update `validate()` to handle Z.

### 🗑️ REMOVED
- `old/utils.ts`: Deleted (deprecated).

## 🧪 Acceptance Criteria
- [ ] Given X, When Y, Then Z.
```

---
*Skill: sdd-spec v1.0 (Gentle AI Edition)*
