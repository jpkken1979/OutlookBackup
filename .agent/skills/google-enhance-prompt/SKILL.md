---
type: feature
name: google-enhance-prompt
description: >
---
  Enhance and optimize LLM prompts for clarity, specificity, and effectiveness.
  Covers prompt engineering patterns, chain-of-thought, few-shot examples,
  structured outputs, and common anti-patterns. Use when improving prompts.
source: Google Labs
---

# Prompt Enhancement

Systematic prompt optimization for better LLM outputs.

## Enhancement Workflow

1. **Analyze** — Identify what the prompt is trying to achieve
2. **Diagnose** — Find weaknesses (vague, ambiguous, missing context)
3. **Restructure** — Apply proven patterns
4. **Test** — Verify improved output quality

## Prompt Patterns

### Role + Task + Format

```
You are a [specific role] with expertise in [domain].

Your task is to [specific action] given the following [input type]:

<input>
{content}
</input>

Provide your response in the following format:
- [format specification]
```

### Chain-of-Thought

```
Analyze the following code for security vulnerabilities.

Think step by step:
1. First, identify all user inputs
2. Then, trace how each input flows through the code
3. Check if inputs are validated/sanitized before use
4. Identify potential injection points
5. Assess the severity of each finding

<code>
{code}
</code>

For each vulnerability found, provide:
- Location (file:line)
- Vulnerability type
- Severity (CRITICAL/HIGH/MEDIUM/LOW)
- Recommended fix
```

### Few-Shot Examples

```
Classify the following support ticket by priority.

Examples:
- "Server is down, all users affected" → CRITICAL
- "Login page shows wrong logo" → LOW
- "Payment processing fails for some users" → HIGH
- "Typo in footer text" → LOW

Now classify:
"{ticket_text}" →
```

### Structured Output

```
Analyze the following function and respond with valid JSON:

```json
{
  "function_name": "string",
  "complexity": "O(?) time, O(?) space",
  "bugs": ["list of bugs found"],
  "improvements": ["list of suggested improvements"],
  "test_cases": ["list of edge cases to test"]
}
```
```

### Constraint-Based

```
Refactor the following code. You MUST:
- Maintain the same public API (function signatures unchanged)
- Keep all existing tests passing
- Not add any new dependencies
- Follow PEP 8 style guidelines

You MUST NOT:
- Change the function's return type
- Remove any existing functionality
- Use global variables
```

## Anti-Patterns to Fix

| Anti-Pattern | Problem | Enhanced Version |
|-------------|---------|-----------------|
| "Make it better" | Too vague | "Improve performance by reducing O(n²) to O(n log n)" |
| "Fix the code" | No context | "Fix the null pointer exception on line 42 when input is empty" |
| "Write a function" | Underspecified | "Write a function that takes a list of integers and returns the top K elements using a min-heap" |
| "Explain this" | No audience | "Explain this async/await pattern to a developer familiar with callbacks but new to promises" |
| Wall of text | Hard to parse | Use sections, bullets, code blocks |

## Enhancement Checklist

- [ ] **Specific task** — Is the desired action crystal clear?
- [ ] **Context provided** — Does the LLM have all needed information?
- [ ] **Output format defined** — Is the expected format specified?
- [ ] **Constraints stated** — Are limitations and requirements explicit?
- [ ] **Examples included** — Are there few-shot examples for complex tasks?
- [ ] **Edge cases addressed** — Are ambiguous cases handled?
- [ ] **Evaluation criteria** — Can you judge if the output is correct?

## System Prompts

```
# Effective system prompt structure:

You are [role] working on [project context].

Rules:
1. [Hard constraint - MUST follow]
2. [Hard constraint - MUST NOT do]
3. [Preference - SHOULD prefer]

Style:
- [Communication style]
- [Output format preference]
- [Language/terminology]

When uncertain:
- [Fallback behavior]
- [When to ask for clarification]
```

## Temperature Guide

| Task Type | Temperature | Why |
|-----------|-------------|-----|
| Code generation | 0.0 - 0.2 | Deterministic, correct output |
| Code review | 0.0 - 0.1 | Consistent analysis |
| Creative writing | 0.7 - 1.0 | Varied, creative output |
| Translation | 0.0 - 0.3 | Accurate, faithful |
| Brainstorming | 0.8 - 1.0 | Diverse ideas |
| Classification | 0.0 | Consistent labels |
| Summarization | 0.0 - 0.3 | Faithful to source |

## Prompt Optimization for Code Tasks

```
# Before (weak)
"Write a Python function to process data"

# After (strong)
"Write a Python 3.11+ function called `process_records` that:
- Takes a list of dicts with keys 'name' (str), 'value' (int), 'timestamp' (str ISO format)
- Filters out records where value < 0
- Groups remaining records by date (extracted from timestamp)
- Returns a dict[str, list[dict]] mapping dates to records
- Uses type hints on all parameters and return value
- Includes a Google-style docstring
- Handles empty input gracefully (returns empty dict)

Do NOT use pandas or any external libraries."
```
