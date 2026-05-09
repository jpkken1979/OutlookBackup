---
name: sequential-thinking
description: Use when complex problems require systematic step-by-step reasoning. This skill enforces a structured "Thinking Protocol" to break down problems, hypothesis testing, and self-correction before taking action.
type: feature
---

# Sequential Thinking Protocol

This skill enables deep, structured reasoning for complex problem-solving. Unlike standard chain-of-thought, this protocol enforces **explicit** step-by-step analysis with revision and branching capabilities.

## 🧠 Core Philosophy

1.  **Decomposition**: Never tackle a complex problem in one bite. Break it down.
2.  **Hypothesis Testing**: Treat assumptions as hypotheses to be verified, not facts.
3.  **Self-Correction**: It is acceptable and encouraged to find flaws in previous thoughts and correct them.
4.  **Branching**: Explore multiple paths if the solution space is ambiguous.

## 🛠️ How to Apply

Since you cannot access the original MCP tool in this environment, you must **simulate** the tool's behavior using the following specific Markdown structure in your responses:

```markdown
### 🧠 Sequential Thinking

**Step 1: Analysis**
[Analyze the current state/input]

**Step 2: Hypothesis Generation**
- Hypothesis A: [Description]
- Hypothesis B: [Description]

**Step 3: Evaluation**
[Critique the hypotheses based on known facts]

**Step 4: Revision (if needed)**
[If a previous assumption was wrong, explicitly correct it here]

**Step 5: Conclusion/Next Action**
[Determine the logical next step]
```

## 🚦 When to Use

- **Debugging**: When the root cause is hidden or has multiple possibilities.
- **Architecture**: When deciding between multiple design patterns or technologies.
- **Refactoring**: When planning a large-scale change that affects multiple files.
- **Security Analysis**: When tracing potential attack vectors (using the "Branching" technique).

## ⚡ Advanced Techniques

### The "Branching" Pattern
If you are unsure between two causes, explicitly branch:

> **Step X: Branching**
> - **Path A (Network Issue)**: If the logs show timeout... then check firewall.
> - **Path B (App Logic)**: If the logs show 500 error... then check code trace.

### The "Revision" Pattern
If you realize you were wrong:

> **Step Y: Revision**
> 🛑 **Correction**: In Step 2, I assumed the user was logged in. However, the headers are missing the token.
> **New Plan**: I must verify the auth flow first.

## 📄 Example Usage

**User**: "My app crashes only on Tuesdays."

**Agent Response**:
### 🧠 Sequential Thinking
**Step 1: Deconstruct**
"Only on Tuesdays" implies a time-dependent trigger.
**Step 2: Hypotheses**
- H1: Cron job running only on Tuesdays.
- H2: Date formatting bug (e.g., day index 2 handling).
- H3: External API dependency maintenance window.
**Step 3: Investigation Plan**
Check system crontab, then grep codebase for "Tuesday" or day index checks.
