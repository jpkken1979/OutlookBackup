# Skills Organization & Consolidation Map

## Overview

The Antigravity ecosystem has **941+ skills**. Some skills naturally group together around similar specializations. This document maps those groups, explains why they're organized as they are, and provides decision matrices for when to use each.

**Key principle:** Skills are **not deleted** — they're reference material (SKILL.md files are prompts). Instead, **cross-references and consolidation maps** link related skills.

---

## Skill Groups Identified

### 1. Security Scanning & Auditing — 4 Active Skills

**Theme:** Code security, dependency security, hardening, code review

| Skill | Specialization | Primary Use |
|-------|---|---|
| `security-dependencies-scan` | Dependency vulnerabilities, SBOM, supply chain | Audit third-party libraries for CVEs |
| `security-sast-scan` | Static code analysis, OWASP Top 10, framework-specific | Review custom source code |
| `security-hardening-scan` | Multi-layer hardening, defense-in-depth, 13-phase program | Complete security hardening initiative |
| `cc-skill-security-review` | Developer checklist, pre-deployment validation | Manual code review checklist |

**Deprecated skills in this group:**
- `security-scanner` → Use specialized skills instead
- `security-scanning` → Use specialized skills instead

**Consolidation document:** `.agent/skills/security-dependencies-scan/CONSOLIDATION_MAP.md`

**When to use each:**
- **Audit dependencies only** → `security-dependencies-scan`
- **Review source code** → `cc-skill-security-review` + `security-sast-scan`
- **Full hardening program** → `security-hardening-scan` (orchestrates all)
- **Quick checklist** → `cc-skill-security-review`

**Why separate:**
- Different tools (Snyk/Trivy vs. Semgrep/Bandit vs. manual)
- Different scopes (dependencies vs. code vs. infrastructure)
- Different workflows (standalone audit vs. CI/CD vs. manual review vs. orchestrated program)

---

### 2. Data Engineering — 4 Active Skills

**Theme:** Data pipelines, warehousing, transformation, feature engineering

| Skill | Specialization | Primary Use |
|-------|---|---|
| `data-engineer` | Complete modern data stack (Spark, Airflow, dbt, cloud) | Enterprise architecture & design |
| `data-engineering` | Pattern guide (markdown docs on ETL, dbt, streaming, cost) | Reference documentation |
| `data-engineering-data-driven-feature` | Feature engineering, ML pipelines, feature stores | ML-specific data engineering |
| `data-engineering-data-pipeline` | Pipeline implementation, hands-on patterns | Implement specific pipelines |

**Consolidation document:** `.agent/skills/data-engineer/CONSOLIDATION_MAP.md`

**When to use each:**
- **Design data architecture** → `data-engineer`
- **Look up pattern reference** → `data-engineering`
- **Build feature store for ML** → `data-engineering-data-driven-feature`
- **Implement specific pipeline** → `data-engineering-data-pipeline`

**Why separate:**
- Different audiences (architects vs. developers vs. ML engineers)
- Different formats (expert agent vs. markdown reference vs. implementation)
- Different depth (enterprise vs. patterns vs. specialization)

---

### 3. Prompt Engineering — 3 Active Skills

**Theme:** Prompt design, optimization, techniques, LLM systems

| Skill | Specialization | Primary Use |
|-------|---|---|
| `prompt-engineer` | Advanced techniques, constitutional AI, system prompts, red-teaming | Design & optimize prompts for AI features |
| `prompt-engineering` | Pattern guide (few-shot, chain-of-thought, templates, optimization) | Reference documentation |
| `prompt-engineering-patterns` | Advanced pattern templates, composition, RAG, multi-agent | Deep-dive specialized patterns |

**Consolidation document:** `.agent/skills/prompt-engineer/CONSOLIDATION_MAP.md`

**When to use each:**
- **Design new prompt** → `prompt-engineer`
- **Learn a pattern** → `prompt-engineering`
- **Advanced pattern deep-dive** → `prompt-engineering-patterns`

**Why separate:**
- Different formats (expert agent vs. markdown reference vs. advanced patterns)
- Different use cases (generation vs. learning vs. specialization)
- `prompt-engineer` **must** always show complete prompt text (critical requirement)

---

## Using Consolidation Maps

Each primary skill in a group has a **CONSOLIDATION_MAP.md** file that:

1. **Identifies the primary skill** — most comprehensive in that domain
2. **Lists related skills** — how they differ and when to use each
3. **Shows decision matrices** — which skill to use for different scenarios
4. **Explains why they're separate** — design rationale
5. **Provides combined workflows** — how to use multiple skills together

### Example: Security Scanning

If you need to audit a project's security:

1. **Read** `.agent/skills/security-dependencies-scan/CONSOLIDATION_MAP.md`
2. **Look up** "Audit dependencies for CVEs" → says use `security-dependencies-scan`
3. **For full hardening** → see that `security-hardening-scan` orchestrates all phases
4. **Use combined workflow** → run both for comprehensive coverage

---

## Adding New Skills to a Group

When creating a new skill that belongs to an existing group:

1. **Check** `.context/SKILLS_ORGANIZATION.md` (this file) to find the group
2. **Read** the consolidation map (e.g., `CONSOLIDATION_MAP.md`) in the primary skill folder
3. **Add your skill** to the related group with its specialization
4. **Update the consolidation map** to include your skill in the decision matrix
5. **Create a "Related Skills" section** in your new skill's SKILL.md linking to the group

---

## Related Skills Across Groups

Some skills touch multiple groups. Example:

- `security-secrets-scan` — Part of **Security Scanning** group, but used in **Data Engineering** (for data governance)
- `ml-engineer` — Part of **ML/AI** group, but uses skills from **Data Engineering** and **Prompt Engineering**

For skills that span multiple groups, include cross-references in their SKILL.md:

```markdown
## Related Skills

### Security Group
- `security-dependencies-scan` — For vulnerability scanning
- `security-sast-scan` — For code security

### Data Engineering Group
- `data-engineer` — For data pipeline architecture
```

---

## Skills Organization Strategy

### Tier 1: Grouping Rules

Skills are grouped by **specialization domain** (security, data, prompts, etc.) and **intended use** (design, reference, implementation).

### Tier 2: Primary vs. Secondary

In each group:
- **Primary skill** = most comprehensive, orchestrates others
- **Secondary skills** = complementary, specialized, or reference materials

### Tier 3: Deprecation

Deprecated skills (in `_deprecated/` folder):
- Not deleted (still useful reference material)
- Marked as redundant with newer skills
- Users are directed to the newer alternatives
- Example: `security-scanner` → use `security-sast-scan` or `security-dependencies-scan`

---

## Statistics

As of this organization effort:

| Metric | Count |
|--------|-------|
| **Total skills** | 941+ |
| **Skill groups identified** | 3 (security, data, prompts) |
| **Skills in groups** | 11 |
| **Deprecated skills** | 2 |
| **Consolidation maps created** | 3 |

---

## How to Navigate Skills

### Quick Path: Find a skill for my task

1. **Identify your task type** (security, data, prompts, etc.)
2. **Find the group** in this document
3. **Read the decision matrix** to find the right skill
4. **Read the consolidation map** for combined workflows
5. **Use the skill** (via agent, MCP, CLI)

### Example Workflows

#### Scenario: "I need to audit my project's security"

```
Task: Complete security audit
↓
Check SKILLS_ORGANIZATION.md → Security Scanning group
↓
Read security-dependencies-scan/CONSOLIDATION_MAP.md
↓
Decision matrix → "Full security hardening program" → security-hardening-scan
↓
Use combined workflow: run security-hardening-scan (orchestrates all phases)
```

#### Scenario: "I need to design a data pipeline"

```
Task: Design modern data pipeline
↓
Check SKILLS_ORGANIZATION.md → Data Engineering group
↓
Read data-engineer/CONSOLIDATION_MAP.md
↓
Decision matrix → "Design modern data stack" → data-engineer
↓
Use: run data-engineer (provides architecture), then run data-engineering (reference)
```

#### Scenario: "I need to optimize my LLM prompt"

```
Task: Improve prompt performance
↓
Check SKILLS_ORGANIZATION.md → Prompt Engineering group
↓
Read prompt-engineer/CONSOLIDATION_MAP.md
↓
Decision matrix → "Optimize prompt performance" → prompt-engineer
↓
Use: run prompt-engineer (generates optimized prompt with complete text)
```

---

## Maintenance & Updates

### When to Update This File

- **New skill created** in an existing group → add to group table
- **New group identified** → add new section with consolidation map reference
- **Skill deprecated** → move to deprecated list and add migration path
- **Consolidation map updated** → reflect changes in decision matrices

### When to Update Consolidation Maps

- **New related skill** added → add to consolidation map
- **Usage patterns change** → update decision matrix
- **Relationships clarified** → improve "Why They're Separate" section

### Ownership

- **This file (.context/SKILLS_ORGANIZATION.md):** Master index
- **Consolidation maps:** Each in the primary skill folder (e.g., `.agent/skills/security-dependencies-scan/CONSOLIDATION_MAP.md`)
- **Individual SKILL.md files:** Author of the skill

---

## Related Documents

- **Architecture reference:** `.agent/ARCHITECTURE.md`
- **Project status:** `ESTADO_PROYECTO.md`
- **Ecosystem usage rules:** `.claude/rules/ecosystem-usage.md`
- **Skill execution:** `python .agent/scripts/invoke-agent.py <agente> "<tarea>"`

---

## Quick Reference: Consolidation Map Locations

| Group | Primary Skill | Consolidation Map |
|-------|---|---|
| **Security Scanning** | `security-dependencies-scan` | `.agent/skills/security-dependencies-scan/CONSOLIDATION_MAP.md` |
| **Data Engineering** | `data-engineer` | `.agent/skills/data-engineer/CONSOLIDATION_MAP.md` |
| **Prompt Engineering** | `prompt-engineer` | `.agent/skills/prompt-engineer/CONSOLIDATION_MAP.md` |

---

**Last updated:** 2026-03-08
**Curator:** Claude Code (Antigravity Ecosystem)
