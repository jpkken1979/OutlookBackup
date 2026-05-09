---
description: Use when coordinating multiple specialized perspectives to solve high-complexity architectural or engineering problems. Triggers: orchestrate, multicomponent, fullstack, architecture design, complex refactor.
universal: true
metadata:
  category: workflow
  author: ozy
  triggers: orchestrate, complex, architectural, multi-agent, phases, SDD
  references: Rules.md, AGENTS.md, Gentle-AI patterns
---

# Multi-Perspective Orchestration (God Mode) 🎭

Expert framework for systematic problem solving through specialized personas and phase-gated execution.

## 💎 Core Principles (Axioms)
1. **The Phase Gate is Sacred**: Never bridge into Implementation without a signed-off Design. Never bridge into Design without a clear Discovery.
2. **Conflict is a Signal**: Divergence between perspectives (e.g., Backend vs Frontend) is where the most critical bugs hide. Force consensus.
3. **The Guardian Axiom**: The Orchestrator does not code; it validates and routes. It ensures each specialist follows their own God Mode checklists.
4. **Assume Zero Context**: Every phase transition must "summarize and refresh" context to prevent agent drift.
5. **Validation is the Final Word**: No task is complete until it passes the "Verification Phase" with a concrete report.

## 🛠️ The 6 Phases of Engineering (Step-by-Step)
1. **Engagement 🤝**: Understand the goal, constraints, and success metrics. Ask minimum 3 strategic questions.
2. **Discovery 🔍**: Research the current codebase. Map entry points, dependencies, and "Sharp Edges".
3. **Design 🏗️**: Create the architecture/spec. No code yet. Define the "Plan of Action".
4. **Implementation 💻**: Execute tasks in 5-minute units (TDD cycle).
5. **Validation ✅**: Run the "High Fidelity Checklist". Verify against success metrics.
6. **Handoff 📦**: Summarize changes, update `ESTADO_PROYECTO.md`, and clean up temporary artifacts.

## 🛡️ Security & Quality Checklist
- [ ] **Phase Integrity**: Did we skip any of the 6 phases?
- [ ] **Perspective Diversity**: Did at least 3 distinct personas (e.g., Security, Backend, UX) review the Design?
- [ ] **Conflict Resolution**: Are all trade-offs documented and resolved?
- [ ] **Task Atomicity**: Is the Implementation plan broken down into independent, testable units?
- [ ] **Memory Trigger**: Did we save a project snapshot in `ESTADO_PROYECTO.md` before finalizing?

## 📚 Examples (Few-shot)

### Example: Phase-Gated Transition
```markdown
## Orchestrator Update
Phase: **Discovery Complete** ✅
Next: **Design Phase** 🏗️

I have mapped the auth flow. Before I write the Spec, I need 
the Security Persona to review the Token Rotation strategy 
recommended in Discovery.
```

### Example: Multi-Persona Synthesis
```markdown
## Synthesis Report
| Perspective | Core Requirement | Risk |
|-------------|------------------|------|
| Backend     | Redis Caching    | Stale Data |
| UX          | Optimistic UI    | Desync |
| Security    | Rate Limiting   | UX friction |

**Consensus**: Implement Redis with 5s TTL + Optimistic UI with rollback on 429 errors.
```

---
*Workflow: orchestrate v3.0 (Gentle AI + God Mode Edition)*
