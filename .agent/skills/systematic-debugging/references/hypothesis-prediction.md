# Hypothesis Prediction in Debugging

## Core Principle

Before fixing, predict what WILL happen if your fix is correct. If prediction fails, the hypothesis was wrong.

## Example

Hypothesis: NullPointerException because user object is not populated in session
Prediction: If we add null check on user, the stack trace will show a different line on second run
Link confidence: HIGH (we saw user=null in session storage)

## Causal Chain Gate

Every fix requires:
1. Root cause identified
2. Prediction written
3. Fix applied
4. Prediction verified

If step 4 fails, go back to step 1.

## When Multiple Hypotheses

Rank by confidence:
- HIGH: direct evidence (stack trace, logs)
- MEDIUM: circumstantial (timing, patterns)
- LOW: speculation

Test highest confidence first.
