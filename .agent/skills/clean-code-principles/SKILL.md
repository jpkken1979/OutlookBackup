---
name: clean-code-principles
description: >-
type: feature
---
  Use when writing new code, refactoring legacy systems, or performing code
  reviews. Triggers: code review, refactor, technical debt, modularity, SOLID,
  naming, clean functions, code quality.
metadata:
  category: discipline
  author: ozy
  triggers: clean code, refactoring, code quality, naming conventions, DRY, KISS, SOLID, YAGNI, code smells
  references: Rules.md, AGENTS.md
---

# Clean Code Excellence (God Mode) 💎

Principles and practices for writing code that is clean, maintainable, and professional across all languages (TS, Rust, Python, Go).

## 💎 Core Principles (Axioms)
1. **Meaning over Mechanism**: Prioritize "what" the code does over "how" it does it. Use descriptive names.
2. **Singleness of Purpose**: Every function/class/module must have exactly one reason to change (SRP).
3. **Simplicity is the Ultimate Sophistication**: Prefer the simplest solution that works (KISS). Avoid premature optimization.
4. **Boy Scout Rule**: Always leave the code cleaner than you found it. Refactor small things during features.
5. **No Broken Windows**: Do not tolerate "hacks" or poor code. Fix technical debt before it accumulates.

## 🛠️ Step-by-Step implementation
1. **The Naming Phase**: Choose names that reveal intent. If you need a comment to explain a name, the name is wrong.
2. **The Functional Phase**: Keep functions small (<15 lines). If a function has more than 3 arguments, use a configuration object.
3. **The SOLID Phase**: Validate your architecture against SOLID principles (Single Responsibility, Open/Closed, etc.).
4. **The Refactoring Loop**: Write the logic -> Make it work -> Make it clean (Make it fast only if profiling requires it).

## 🛡️ Security & Quality Checklist
- [ ] **No Side Effects**: Ensure functions don't modify global state or unrelated objects unless explicitly documented.
- [ ] **Error Handling**: Use specific exceptions/types (Result/Option in Rust/TS) instead of generic `Error` or `null`.
- [ ] **DRY (Don't Repeat Yourself)**: Abstract logic that appears 3+ times, but avoid "premature abstraction".
- [ ] **Magic Values**: All constants must be named. No "magic strings" or numbers in logic.

## 📚 Examples (Few-shot)

### Example: Intent-Revealing Names (TS)
```typescript
// ❌ BAD
const d = 86400; // seconds per day?
function check(u: User) {
  if (u.age > 18 && u.active) return true;
}

// ✅ GOOD (God Mode)
const SECONDS_PER_DAY = 86400;
function isUserEligibleForService(user: User): boolean {
  const isAdult = user.age >= 18;
  return isAdult && user.isActive;
}
```

### Example: Small Focused Functions (Rust)
```rust
// ❌ BAD: One big function doing everything
fn process_order(order: Order) { /* ... 50 lines of validation, calculation, saving ... */ }

// ✅ GOOD (God Mode): Small, testable units
fn process_order(order: Order) -> Result<(), Error> {
    validate_order(&order)?;
    let total = calculate_total(&order);
    save_to_db(order, total)?;
    notify_customer(order)?;
    Ok(())
}
```

---
*Skill: clean-code-principles v2.0 (Bibek Poudel Edition)*
