---
name: writing-plans
type: feature
description: >-
---
  Use when you have a spec or requirements for a multi-step task, before
  touching code. Triggers: plan, architectural design, task breakdown,
  multi-step execution.
metadata:
  category: workflow
  author: ozy
  triggers: planning, architecture, roadmap, implementation, TDD
  references: Rules.md, AGENTS.md
---

# Strategic Planning Mastery (God Mode) 🗺️

Expert principles for creating deterministic, high-fidelity implementation plans.

## 💎 Core Principles (Axioms)
1. **The Plan is the Code**: A plan must be so specific that execution becomes a clerical task. No "add logic" - specify the exact function and validation.
2. **Deterministic Granularity**: Break tasks into 5-minute units. Each unit must follow: Test (Fail) -> Implement -> Test (Pass) -> Commit.
3. **Architecture Before Action**: Define the system and tech stack *before* listing tasks. Ensure alignment with `ARCHITECTURE.md`.
4. **Assume Zero Context**: Write for an engineer who knows the language but not this codebase. Include exact file paths and line ranges.
5. **Fail-Fast Testing**: Every task must include the exact command to run the test and the expected failing/passing output.

## 🛠️ Step-by-Step implementation
1. **The Discovery Phase**: Use `grep` and `ls` to find the exact files to touch. Map dependencies.
2. **The Specification Phase**: Define the goal, architecture, and tech stack in the plan header.
3. **The Task Breakdown**: List tasks following the TDD Red-Green-Refactor cycle. Use code snippets for tests and minimal code.
4. **The Review Phase**: Before saving, verify all paths are absolute or correctly relative to the root.

## 🛡️ Security & Quality Checklist
- [ ] **Path Accuracy**: Verified that all file paths exist or planned correctly?
- [ ] **TDD Cycle**: Does every logical change include a corresponding test step?
- [ ] **Commit Strategy**: Are there frequent commits (one per task) to allow easy reverts?
- [ ] **Subagent Ready**: Is the plan formatted for `subagent-driven-development` or `executing-plans`?
- [ ] **DRY/YAGNI Check**: Does the plan avoid over-engineering or code duplication?

## 📚 Examples (Few-shot)

### Example: High-Fidelity Task
```markdown
### Task 1: Validation Helper
**Files:**
- Create: `src/utils/validator.py`
- Test: `tests/test_validator.py`

**Step 1: Write failing test**
```python
def test_email_validation():
    assert validate_email("invalid") == False
```

**Step 2: Run test** 
`pytest tests/test_validator.py` -> Expected: `NameError: validate_email not defined`

**Step 3: Implement minimal code**
```python
def validate_email(email: str) -> bool:
    return "@" in email
```

**Step 4: Commit**
`git add . && git commit -m "feat: add email validator"`
```

---
*Skill: writing-plans v2.0 (Bibek Poudel Edition)*
