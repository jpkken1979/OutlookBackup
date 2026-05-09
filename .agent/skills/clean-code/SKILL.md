---
name: clean-code
description: "Antigravity Coding Standards. STRICT enforcement of Clean Code, SOLID, and TDD principles. Mandatory for all code modifications. Prioritizes readability, testability, and defensive programming."
type: feature
---

# Clean Code Skill - Antigravity Edition 🛡️

> **Status:** MANDATORY
> **Level:** SENIOR ENGINEER

This skill is the **absolute law** for code quality within the Antigravity ecosystem. It goes beyond basic "Clean Code" summaries and enforces a rigorous, defensive, and production-ready mindset.

---

## 🚨 AUTOMATIC REJECTION CRITERIA

**If code contains any of these, it WILL be rejected:**

1.  **Magic Numbers/Strings**: `if (status == 1)` -> `if (status == Status.ACTIVE)`.
2.  **Ambiguous Names**: `data`, `info`, `temp`, `manager` (unless specific pattern).
3.  **God Functions**: Functions > 30 lines or cyclomatic complexity > 10.
4.  **Commented-Out Code**: Delete it. Git has history.
5.  **Swallowing Exceptions**: `try { ... } catch (e) { pass }` is **FORBIDDEN**. ALWAYS log or re-raise.
6.  **Redundant Comments**: `i++; // increment i`.

---

## 🏗️ SOLID Principles (Enforced)

### 1. Single Responsibility Principle (SRP)
- **Rule:** A class/module should have **one and only one reason to change**.
- **Check:** Can you describe what this class does in one sentence without using "and"?

### 2. Open/Closed Principle (OCP)
- **Rule:** Open for extension, closed for modification.
- **Implementation:** Use Interfaces/Abstract Classes/Polymorphism instead of massive `switch/if-else` chains.

### 3. Liskov Substitution Principle (LSP)
- **Rule:** Subtypes must be substitutable for their base types without breaking behavior.
- **Check:** Does your subclass throw an exception for a method the parent supports? That violates LSP.

### 4. Interface Segregation Principle (ISP)
- **Rule:** Clients should not be forced to depend on methods they do not use.
- **Implementation:** Split large interfaces into smaller, specific ones (`IReadable`, `IWritable` vs `IFile`).

### 5. Dependency Inversion Principle (DIP)
- **Rule:** High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Implementation:** Use Dependency Injection. Never `new SqlDatabase()` inside a `UserService`.

---

## 🛡️ Defensive Programming

1.  **Validate Prompts/Inputs First**: Fail fast. `if (!user) throw new InvalidArgumentException(...)`.
2.  **Return Early**: Avoid nested `if` blocks (Arrow Code).
3.  **Immutability**: Prefer `const` / `readonly` wherever possible.
4.  **Null Safety**: Avoid returning `null`. Use `Option/Maybe` types or throw exceptions if absence is failure.

---

## 🧪 Testing Protocol (AAA Pattern)

Every test must follow the **Arrange-Act-Assert** pattern strictly.

```typescript
// ✅ GOOD
it('should calculate total price with tax', () => {
  // Arrange
  const cart = new ShoppingCart();
  cart.add(new Product("Apple", 1.00));

  // Act
  const total = cart.calculateTotal();

  // Assert
  expect(total).toBe(1.10); 
});
```

---

## 📝 Naming Conventions (Antigravity Standard)

*   **Variables**: `is[Adjective]`, `has[Noun]`, `customerList` (array). NO Hungarian notation.
*   **Functions**: `Verb[Noun]`. `getUser()`, `calculateTax()`, `isValid()`.
*   **Classes**: Noun. `userRepository`, `paymentGateway`.
*   **Interfaces**: `I` prefix is deprecated in TS/JS. Use descriptive names (`Readable`, `Repository`).

---

## 🚀 Refactoring Checklist

Before submitting ANY code change, ask:

1.  [ ] Did I leave the campsite cleaner than I found it?
2.  [ ] Did I add tests for the new behavior?
3.  [ ] Are variables named so clearly that comments are unnecessary?
4.  [ ] Did I handle edge cases (empty lists, nulls, negative numbers)?
5.  [ ] Is there any code duplication (DRY)?

---

**"It works" is not done.**
**"It works and is clean" is done.**
