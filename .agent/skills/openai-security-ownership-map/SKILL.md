---
name: openai-security-ownership-map
description: >
type: feature
---
  Build bipartite ownership graphs from git history to identify bus factor,
  unmaintained code, and co-change clusters. Use when auditing code ownership,
  identifying risk areas, or planning team allocation.
source: OpenAI (codex-universal)
type: feature
---

# Security Ownership Map

Generate ownership maps from git history to identify security-critical areas with low bus factor.

## Core Concepts

### Bus Factor Analysis
- **Bus factor = 1**: Only one person has modified a file — high risk
- **Bus factor = 2**: Two contributors — moderate risk
- **Bus factor ≥ 3**: Healthy ownership — lower risk

### Co-Change Clustering
Files that frequently change together form implicit modules:
- If `auth.py` and `middleware.py` always change in the same commits, they form a cluster
- Security-critical clusters with low bus factor = highest risk

## Workflow

### Step 1: Extract Git History
```bash
git log --format='%H|%ae|%ad' --name-only --diff-filter=AMRC --since="1 year ago" > git_history.txt
```

### Step 2: Build Ownership Matrix
For each file, calculate:
- **Primary owner**: Most commits
- **Secondary owners**: Other contributors
- **Last modified**: Days since last change
- **Change frequency**: Commits per month

### Step 3: Calculate Bus Factor
```python
from collections import Counter

def bus_factor(file_commits: list[str]) -> int:
    """Calculate minimum contributors for 50% of commits."""
    counts = Counter(file_commits)
    total = sum(counts.values())
    threshold = total * 0.5
    accumulated = 0
    for _, count in counts.most_common():
        accumulated += count
        if accumulated >= threshold:
            return counts.most_common().index((_, count)) + 1
    return len(counts)
```

### Step 4: Identify Risk Areas
High-risk files have ALL of:
- Security-sensitive (auth, crypto, validation, permissions)
- Low bus factor (1-2)
- High change frequency
- Recent external-facing changes

### Step 5: Co-Change Detection
```python
from itertools import combinations

def find_co_changes(commits: dict[str, list[str]], threshold: int = 3) -> list[tuple]:
    """Find file pairs that change together frequently."""
    pair_counts: dict[tuple, int] = {}
    for files in commits.values():
        for pair in combinations(sorted(files), 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    return [(pair, count) for pair, count in pair_counts.items() if count >= threshold]
```

### Step 6: Generate Report

## Output Format

```markdown
# Ownership Map Report

## Summary
- Total files analyzed: N
- Files with bus factor = 1: N (HIGH RISK)
- Security-critical files with low ownership: N

## Critical Risk Areas
| File | Bus Factor | Primary Owner | Last Modified | Security Relevance |
|------|-----------|---------------|---------------|-------------------|
| auth/jwt.py | 1 | dev@co | 3 days ago | Authentication |

## Co-Change Clusters
| Cluster | Files | Primary Owner | Risk |
|---------|-------|---------------|------|
| Auth Module | auth.py, middleware.py, jwt.py | dev@co | HIGH |

## Recommendations
1. Increase review requirements for bus-factor-1 security files
2. Cross-train team members on critical clusters
3. Add CODEOWNERS rules for high-risk areas
```

## Integration
- Pairs with `security-threat-model` for risk prioritization
- Feeds into `differential-review` for PR risk assessment
- Use before `security-best-practices` audit to focus effort
