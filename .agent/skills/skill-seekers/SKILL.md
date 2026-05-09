---
name: skill-seekers
description: "Automatically converts documentation websites, GitHub repositories, and PDF files into Claude AI skills in minutes. Crawls documentation sites, extracts API references, code examples, and guides. Generates SKILL.md frontmatter and body with trigger keywords, descriptions, and bundled resources. Use when creating skills from existing documentation, building knowledge bases from developer docs, automating skill generation from READMEs, packaging library documentation as skills, or creating skills from technical guides and tutorials."
type: feature
source: "https://github.com/yusufkaraaslan/Skill_Seekers"
risk: safe
user-invocable: true
---

# Skill Seekers: Automatic Skill Generation

Convert any existing documentation, code repository, or technical guide into a fully-formed Claude AI skill in minutes, bypassing manual writing.

## The Conversion Pipeline

```
Input Source (website, repo, PDF)
    ↓
Extract Content (crawl, parse, summarize)
    ↓
Identify Key Concepts (APIs, functions, patterns)
    ↓
Generate Trigger Keywords (when to use this skill)
    ↓
Write Frontmatter (name, description, metadata)
    ↓
Structure Body (examples, patterns, checklists)
    ↓
Bundle Resources (code samples, links, references)
    ↓
Output: SKILL.md (ready to use)
```

## Input Sources

### Option 1: Documentation Website

```bash
skill-seekers --source "https://docs.example.com" \
              --output my-skill/ \
              --max-depth 3
```

Crawls website recursively, extracts content from:
- API reference pages
- Getting started guides
- Code examples
- Troubleshooting sections
- FAQ pages

### Option 2: GitHub Repository

```bash
skill-seekers --source "https://github.com/user/repo" \
              --output my-skill/ \
              --include-readme \
              --include-examples \
              --max-size 50MB
```

Extracts from:
- README.md (overview, examples, setup)
- `/docs/` folder (guides, tutorials)
- `/examples/` folder (code samples)
- API reference (if present)

### Option 3: PDF Document

```bash
skill-seekers --source "technical-guide.pdf" \
              --output my-skill/ \
              --extract-sections \
              --include-code-blocks
```

Parses:
- Chapter structure (becomes sections)
- Code examples (extracted for bundling)
- Tables and diagrams (preserved as reference)
- Index (becomes navigation keywords)

## Generated Skill Structure

```
generated-skill/
├── SKILL.md                 # Auto-generated + refined manually
├── references/
│   ├── api-reference.md     # From original API docs
│   ├── examples.md          # Code samples extracted
│   └── faq.md               # Troubleshooting from docs
├── scripts/
│   └── examples.py          # Runnable code from repo
└── assets/
    └── diagrams/            # Extracted images/diagrams
```

## SKILL.md Auto-Generation

### Frontmatter (Auto-Generated)

```yaml
---
name: my-library-skill           # From repo name or domain
description: "Automatically extracted from README + keywords"
source: "https://github.com/original/repo"
user-invocable: true
context: standard
---
```

### Description Optimization

Tool uses heuristics to create "pushy" description:

```
Raw: "A Python library for data processing"
Generated: "Python data processing library with pandas-compatible APIs,
lazy evaluation, and GPU acceleration. Use when processing large datasets,
implementing ETL pipelines, accelerating data workflows, or building
analytics applications."
```

Adds trigger keywords from:
- README section headers
- API function names
- Code comments
- Example use cases

### Body Generation

Auto-structures content:

```markdown
## Quick Start
[From: README Getting Started section]

## Core Concepts
[From: docs/concepts.md]

## API Reference
[From: docs/api/ or README API section]

## Code Examples
[From: /examples folder + docstrings]

## Patterns & Best Practices
[From: docs/patterns.md or extracted from examples]

## Troubleshooting
[From: docs/troubleshooting.md or FAQ]
```

## Workflow: Converting a Library

### Example: Converting Django Docs to Skill

```bash
skill-seekers --source "https://docs.djangoproject.com" \
              --output django-skill/ \
              --extract-api \
              --extract-examples \
              --max-depth 4

# Tool extracts:
# - Django admin overview
# - ORM reference
# - View/URL routing
# - Middleware documentation
# - 50+ code examples
# - Troubleshooting guide
```

### Post-Generation Refinement (Always Needed)

```
Generated SKILL.md is ~80% quality. Human refinement:
1. Add missing trigger keywords
2. Tighten description (80-200 chars usually best)
3. Reorganize sections for clarity
4. Add a checklist/pattern section
5. Test with Claude on sample tasks
```

## Source Quality vs. Output Quality

| Source Quality | Output Quality | Post-Work |
|----------------|---|---------|
| Great docs (comprehensive, examples-heavy) | 90% usable | 5 min refinement |
| Good docs (mostly complete) | 75% usable | 30 min refinement |
| Minimal docs (just API) | 50% usable | 1-2 hour rebuild |
| Poor/outdated docs | 25% usable | Rebuild from scratch |

**Rule**: Better to refine auto-generated skill than write from scratch.

## Options & Configuration

### Extraction Options

```bash
--include-code-blocks       # Extract all code samples
--extract-api               # Detect and extract API reference
--extract-examples          # Find example sections
--extract-troubleshooting   # Include common issues/fixes
--max-depth N               # How many website levels to crawl
--max-sections N            # Cap on sections (e.g., 20 max)
--filter "keyword"          # Only extract sections with keyword
```

### Output Options

```bash
--format yaml               # Frontmatter format (YAML default)
--min-lines N               # Discard sections < N lines
--merge-related             # Combine related sections
--simplify-code             # Remove verbose examples
--include-metadata          # Copy source links + timestamps
```

### Generation Options

```bash
--ai-enhance true           # Use Claude to improve generated content
--generate-keywords true    # Auto-generate trigger keywords
--generate-checklist true   # Add implementation checklist
--estimate-score            # Predict quality score
```

## Advanced: Skill Generation from Multiple Sources

```bash
skill-seekers --combine \
  --source1 "https://docs.example.com" \
  --source2 "https://github.com/user/repo" \
  --source3 "tutorials.pdf" \
  --output combined-skill/
```

Merges documentation from multiple sources into single skill:
- Removes duplicate sections
- Combines examples from all sources
- Cross-references between sources
- Prioritizes most comprehensive sections

## Output Quality Metrics

Tool provides score estimate:

```
Generated: library-skill/SKILL.md
Quality Estimate: 72/100

Strengths:
- ✓ Comprehensive API reference
- ✓ Good code examples
- ✓ Clear trigger keywords

Weaknesses:
- ⚠ Description could be more "pushy"
- ⚠ Missing common patterns section
- ⚠ Few troubleshooting items

Recommendations:
- Add 2-3 advanced patterns
- Enhance description with use-cases
- Add edge cases section
```

## Skill Distribution

Once refined, distribute:

```bash
# Local Claude Code
cp -r library-skill/ ~/.claude/skills/

# Team repository
git add library-skill/
git commit -m "feat(skills): add library-skill from auto-generation"

# Publish to marketplace (if applicable)
skill-seekers --publish library-skill/
```

## Troubleshooting Auto-Generation

| Problem | Cause | Solution |
|---------|-------|----------|
| Generated description too generic | Website/repo lacks examples | Manually enhance with use-cases |
| Too many irrelevant sections | Crawler too aggressive | Use `--filter` to target sections |
| Code examples broken | Copy-paste errors in generation | Test examples, fix before publishing |
| Missing key concepts | Documentation incomplete | Supplement from external sources |

## Best Practices

1. **Start with good sources**: Better documentation = better skill
2. **Always refine**: Auto-generated is start, not finish
3. **Test generation**: Run examples to verify correctness
4. **Version control**: Keep source docs updated, regenerate quarterly
5. **Combine sources**: Merge multiple docs for comprehensive skill

See [Skill Seekers repository](https://github.com/yusufkaraaslan/Skill_Seekers) for installation, advanced usage, and community templates.
