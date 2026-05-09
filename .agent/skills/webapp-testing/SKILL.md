---
name: webapp-testing
type: feature
description: >-
---
  Use when validating web features, debugging flaky workflows, or setting up
  test suites. Triggers: playwright, vitest, cypress, e2e test, component test,
  integration test, flaky test, stability.
metadata:
  category: quality
  author: ozy
  triggers: testing, playwright, vitest, E2E, integration, component, TDD, flakiness, CI/CD
  references: Rules.md, AGENTS.md
---

# Web Reliability Mastery (God Mode) 🛡️

Expert principles for building bulletproof web applications with high-fidelity testing.

## 💎 Core Principles (Axioms)
1. **Test Behavior, Not implementation**: Assert what the user sees, not the component's internal state.
2. **Determinism over Speed**: A slow passing test is better than a fast flaky test. Use auto-waiting exclusively.
3. **The Stability Pyramid**: Majority of tests should be fast Unit/Component tests. Save E2E for critical "money paths".
4. **Isolate or Fail**: Tests must never depend on each other. Clean state (DB/LocalStorage) before every run.
5. **No data-testid, No party**: Use stable, dedicated attributes for selectors. Never use CSS classes or HTML structure.

## 🛠️ Step-by-Step implementation
1. **The Discovery Phase**: Map all routes and API endpoints. Identify the "Critical User Flows".
2. **The Component Phase**: Write Vitest/Jest tests for individual UI logic and complex helpers (Unit).
3. **The Integration Phase**: Validate that components work together and talk to the API correctly.
4. **The E2E Phase**: Use Playwright to simulate the full user journey (Login -> Checkout -> Logout).

## 🛡️ Security & Quality Checklist
- [ ] **Flakiness Check**: Does the test pass 10/10 times locally?
- [ ] **Selector Stability**: Are we using `data-testid` or accessible labels (`getByRole`)?
- [ ] **Wait Strategy**: Did we avoid `page.waitForTimeout()`? Use `expect(locator).toBeVisible()` instead.
- [ ] **Resource Cleanup**: Does the test clean up the database or session after finishing?
- [ ] **Parallel Readiness**: Can tests run in parallel without race conditions on shared data?

## 📚 Examples (Few-shot)

### Example: Stable Playwright Test
```typescript
// ✅ God Mode: Stable, Behavior-Driven
test('user can complete purchase', async ({ page }) => {
  await page.goto('/shop');
  await page.getByRole('button', { name: /add to cart/i }).click(); // Accessible & Stable
  await page.getByTestId('checkout-btn').click(); // Dedicated ID
  await expect(page.getByText('Success')).toBeVisible(); // Auto-waiting assertion
});
```

### Example: Component Test (Vitest)
```typescript
// ✅ God Mode: Pure logic validation
test('calculateTax returns correct amount', () => {
  expect(calculateTax(100, 0.2)).toBe(20);
  expect(calculateTax(0, 0.2)).toBe(0);
});
```

---
*Skill: webapp-testing v2.0 (Bibek Poudel Edition)*
