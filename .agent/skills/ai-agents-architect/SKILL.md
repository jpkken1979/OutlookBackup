---
name: ai-agents-architect
description: >-
type: feature
---
  Use when designing autonomous agents, tool-use systems, or multi-agent
  orchestrations. Triggers: agent, autonomous, tool use, function calling,
  ReAct, planning, multi-agent.
metadata:
  category: ai
  author: ozy
  triggers: agents, tools, planning, ReAct, multi-agent, autonomy
  references: Rules.md, AGENTS.md
type: feature
---

# AI Agent Architecture (God Mode) 🧠

Expert principles for building reliable, autonomous, and controllable AI agent systems.

## 💎 Core Principles (Axioms)
1. **Controllable Autonomy**: Agents must have clear "guardrails". Use iteration limits and mandatory human-in-the-loop for destructive actions.
2. **Deterministic Tooling**: Tool descriptions must be hyper-specific. The model should know exactly when and how to call each tool.
3. **The ReAct Loop**: Every decision must follow a "Thought -> Action -> Observation" cycle to ensure reasoning precedes execution.
4. **Planning is Mandatory**: For complex tasks, the agent must generate a plan *before* using tools. Execute, validate, and replan if necessary.
5. **Memory is Context**: Manage agent memory aggressively. Summarize old history to stay within context windows and prioritize current task relevance.

## 🛠️ Step-by-Step implementation
1. **The Persona Phase**: Define the agent's identity, constraints, and specific goals in the System Prompt.
2. **The Tooling Phase**: Define high-fidelity tools (functions) with strict JSON schemas and descriptive docstrings.
3. **The Framework Phase**: Implement the ReAct loop or use orchestrators like LangGraph or CrewAI for multi-agent flows.
4. **The Evaluation Phase**: Test the agent against "failure scenarios" to ensure it handles errors and dead-ends gracefully.

## 🛡️ Security & Quality Checklist
- [ ] **Iteration Limit**: Does the agent have a hard stop (e.g., max 10 steps) to prevent infinite loops?
- [ ] **Tool Safety**: Are tools that mutate state or delete data protected by confirmation gates?
- [ ] **Error Propagation**: Are tool errors returned as "Observations" so the agent can self-correct?
- [ ] **Privacy Check**: Is sensitive data (PII) being masked before being sent to the LLM?
- [ ] **Truthfulness**: Is the agent instructed to say "I don't know" instead of hallucinating tool results?

## 📚 Examples (Few-shot)

### Example: High-Fidelity Tool Definition (Python)
```python
def search_database(query: str, limit: int = 5):
    """
    Searches the internal knowledge base for the given query.
    Use this when the user asks about project specifications or technical docs.
    Arguments:
        query: The semantic search term.
        limit: Number of results (max 10).
    """
    # implementation...
```

### Example: ReAct Reasoning Pattern
```text
Thought: I need to find the user's latest order to check the shipping status.
Action: get_order_history(user_id="123")
Observation: Found order #9988, status: "Shipped", tracking: "XYZ-789"
Thought: The order is shipped. I should now check the tracking info.
Action: track_shipment(tracking_number="XYZ-789")
...
```

---
*Skill: ai-agents-architect v2.0 (Bibek Poudel Edition)*
