---
name: skill-creator
description: >-
type: feature
---
  Use when creating, updating, or optimizing skills in the Antigravity
  ecosystem. Triggers: create skill, update skill, skill documentation, skill
  persona, God Mode conversion.
type: feature
metadata:
  category: architect
  author: ozy
  triggers: skill, creator, architect, persona, Poudel, God Mode
  references: Rules.md, AGENTS.md, Bibek Poudel Pattern

# Skill Architecture (God Mode) 🛠️

Expert system for generating deterministic, high-fidelity skills that act as execution factories.

## 💎 Core Principles (Axioms)
1. **Instruction is Action**: A skill is not a manual; it's a factory. Use imperative language starting with verbs.
2. **Deterministic Metadata**: Frontmatter triggers must be "pushy" and exhaustive. Use third-person only.
3. **The Poudel Structure**: Every `SKILL.md` MUST follow the hierarchy: Triggers -> Axioms -> Step-by-Step -> Checklist -> Few-shot Examples.
4. **Context is Expensive**: Keep the body under 500 lines. Offload technical details to `references/` files.
5. **Phase-Gated Creation**: Follow the 6 Phases: Engagement -> Discovery -> Design (Spec) -> Implementation (MD writing) -> Validation -> Handoff.

## 🛠️ Step-by-Step implementation
1. **The Engagement Phase**: Ask the user for the specific problem this skill solves and what keywords should trigger it.
2. **The Discovery Phase**: Research the technology/domain. Identify the "Axioms" (principles that never change).
3. **The Design Phase**: Create a "Spec" for the skill. Define the checklist for success.
4. **The implementation Phase**: Write the `SKILL.md` using the God Mode Template below.
5. **The Validation Phase**: Run `python .agent/scripts/score_skill.py` to ensure it meets quality targets.

## 🛡️ Quality Checklist
- [ ] **Frontmatter**: Does it have a "pushy" description and correct `allowed-tools`?
- [ ] **Axioms**: Are there at least 3 core principles that guide the model's judgment?
- [ ] **Step-by-Step**: Is it a logical flow for the specific domain?
- [ ] **Few-shot Examples**: Are there at least 2 clear, copy-pasteable examples of "God Mode" usage?
- [ ] **Zero Waste**: Have we removed all "You should" and filler phrases?

## 📚 Templates (God Mode)

### Standard SKILL.md Template
```markdown
---
name: [name]
description: [pushy description in 3rd person]
metadata:
  category: [category]
  triggers: [comma, separated, keywords]
---

# [Title] Mastery (God Mode) 🚀

[Brief impact statement]

## 💎 Core Principles (Axioms)
1. **[Axiom 1]**: [Short description]
2. **[Axiom 2]**: [Short description]
3. **[Axiom 3]**: [Short description]

## 🛠️ Step-by-Step implementation
1. **The [Phase 1] Phase**: [Action]
2. **The [Phase 2] Phase**: [Action]
...

## 🛡️ Security & Quality Checklist
- [ ] [Critical Check 1]
- [ ] [Critical Check 2]
...

## 📚 Examples (Few-shot)
[Example 1]
[Example 2]

---
*Skill: [name] v1.0 (Bibek Poudel Edition)*
```

---
*Skill: skill-creator v2.1 (Poudel + Gentle AI Edition)*
