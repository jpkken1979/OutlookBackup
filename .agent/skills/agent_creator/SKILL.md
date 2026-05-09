---
name: Agent Creator
description: Creates and updates agents under `.agent/agents/<agent>/` by scaffolding `IDENTITY.md` and `SYSTEM_PROMPT.md`. Use when creating a new agent, migrating legacy `backend/agents` scaffolding, or standardizing an agent into the current directory-based model.
type: feature
---

# Agent Creator

Create agents the way this repository actually runs them today: as directory-based artifacts under `.agent/agents/<agent>/`.

## Canonical Agent Layout

```
.agent/agents/<agent>/
├── IDENTITY.md
└── SYSTEM_PROMPT.md
```

## Purpose

This skill helps when you need to:

- create a new agent
- migrate a legacy `backend/agents` scaffold
- normalize an existing agent into the current directory-based model
- define the identity, triggers, and behavior of a subagent

## Workflow

1. Define the agent name, role, and trigger phrases.
2. Create a new directory under `.agent/agents/<agent>/`.
3. Write `IDENTITY.md` with the canonical metadata:
   - agent name
   - description
   - version
   - tier
   - triggers
   - capabilities
4. Write `SYSTEM_PROMPT.md` with the operational behavior:
   - mission
   - scope
   - decision rules
   - output format
   - constraints
5. Validate that the agent is described in third person and that triggers match the phrases users actually say.

## Canonical Rules

- Do **not** scaffold new agents under `backend/agents/`.
- Do **not** use `BaseAgent`-era Python class templates for the current repo standard.
- Prefer concise, explicit triggers over generic descriptions.
- Keep identity and behavior separate: `IDENTITY.md` for discoverability, `SYSTEM_PROMPT.md` for execution.

## Example

To create a `notification-agent`:

1. Create `.agent/agents/notification-agent/`
2. Add `IDENTITY.md` with the agent's name, description, tier, and triggers
3. Add `SYSTEM_PROMPT.md` with the behavior and output contract
4. Keep the language direct and aligned with the repo's actual conventions
