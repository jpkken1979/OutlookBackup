---
name: frontend-design-galaxy
description: >-
type: feature
---
  Use when you need to source, compare, cache, and operationalize high-fidelity
  design references inspired by real products. Triggers: design direction,
  style selection, DESIGN.md bootstrap, visual tokens, premium UI, Vercel,
  Linear, Stripe, Claude, Supabase, Cursor.
metadata:
  category: reference
  author: Antigravity
  triggers: design system, design reference, visual source, frontend tokens, style sourcing, DESIGN.md bootstrap
  references: awesome-design-md, getdesign.md
---

# Frontend Design Galaxy

Remote-first design reference system for OpenAntigravity. This skill does **not**
replace implementation skills. It gives agents a reliable way to pick a visual
direction, normalize it into local references, and bootstrap project artifacts.

## What This Skill Owns

This skill is responsible for:

1. **Sourcing references** from curated public DESIGN.md collections.
2. **Normalizing** each reference into a local catalog entry.
3. **Caching** selected references inside `designs/`.
4. **Bootstrapping artifacts** like `DESIGN.md` or `design-system/MASTER.md`.

## What This Skill Does Not Own

- It does **not** synthesize a DESIGN.md from an existing product UI. That is
  the job of the `design-md` skill.
- It does **not** implement components by itself. Use this skill together with
  `ui-ux-designer`, `design-system-architect`, or `frontend-specialist`.

## Complementary UI Sources

After this skill selects the visual direction, agents should source concrete UI
patterns from the modern component ecosystem in this order:

1. **shadcn/ui** - open code, composition, AI-ready defaults
2. **OriginUI** - strong extensions for product UI
3. **Magic UI** - tasteful motion and animated primitives
4. **Aceternity UI** - high-impact storytelling blocks
5. **Radix / cmdk / dnd-kit / Recharts / Lucide** - specialized interaction and visualization layers

This skill chooses the **visual north star**. The registries above help execute
that direction with production-ready components.

## Selection Heuristics

- Prefer **open-code systems** over black-box UI kits.
- Prefer **accessible primitives** over visual gimmicks.
- Use **Motion** to reinforce hierarchy and response, not to show off.
- Reserve **hero-level spectacle** for moments that deserve it.

## Catalog Layout

- `resources/catalog_seed.json` - Curated seed metadata
- `resources/catalog.schema.json` - Schema contract
- `resources/catalog.json` - Generated normalized catalog
- `designs/*.md` - Cached local references ready for agents to read

## Recommended Workflow

### 1. Source the visual direction

List or sync the catalog:

```bash
python .agent/scripts/create_design_galaxy.py list
python .agent/scripts/create_design_galaxy.py sync
```

If you want fresher upstream excerpts:

```bash
python .agent/scripts/create_design_galaxy.py sync --refresh-remote
```

### 2. Pick a primary reference

Choose 1 primary reference and optionally 1 secondary reference for nuance.

- **Vercel** - monochrome precision
- **Linear** - dark product density
- **Stripe** - gradient premium fintech
- **Claude** - warm editorial AI
- **Supabase** - developer dark emerald
- **Cursor** - IDE-like AI tooling
- **VoltAgent** - terminal-native agent ops

### 3. Cache the references you actually use

```bash
python .agent/scripts/create_design_galaxy.py fetch --slug vercel
python .agent/scripts/create_design_galaxy.py fetch --slug claude
```

This writes normalized markdown files to:

```text
.agent/skills/frontend-design-galaxy/designs/
```

### 4. Bootstrap project artifacts

Generate project-level visual source files:

```bash
python .agent/scripts/create_design_galaxy.py materialize --slug vercel --project-dir . --project-name "Nexus" --format both
```

Outputs:

- `DESIGN.md`
- `design-system/MASTER.md`

### 5. Hand off to implementation agents

Once the reference is selected:

1. `ui-ux-designer` translates the direction into product-specific UI choices.
2. `design-system-architect` converts that direction into semantic tokens.
3. `frontend-specialist` implements components and pages with those tokens.

## Decision Rules

### When to use this skill

- User wants a page "in the style of" a known product.
- A team needs aesthetic direction before coding UI.
- You want to bootstrap `DESIGN.md` quickly from a proven visual reference.
- A design system needs inspiration without copying branding blindly.

### When to use `design-md` instead

- There is already a product, mockup, or Stitch screen to analyze.
- You need to reverse-engineer an existing interface into a semantic design file.
- The design source is private or project-specific rather than a public reference.

## Quality Guardrails

- Translate references into **semantic tokens**, not raw cloned branding.
- Preserve **WCAG** and interaction clarity over style mimicry.
- Use references as **directional systems**, not as permission to copy.
- Prefer one strong primary reference over mixing many styles at once.

## Fast Reference Mapping

| Need | Recommended Reference |
|------|------------------------|
| AI chat / editorial | Claude |
| Infra / docs / platform | Vercel |
| Dense B2B dashboard | Linear |
| Premium fintech | Stripe |
| Dev tooling / docs + code | Supabase |
| AI coding tool | Cursor |
| Agent operations / terminal feel | VoltAgent |

## Example Prompting Pattern

```text
Use frontend-design-galaxy.
Select a primary reference for a developer-facing dashboard.
Cache it locally, then generate DESIGN.md and design-system/MASTER.md.
Finally convert the result into semantic tokens and implementation rules.
```
