# MCP Integration with Agent Skills

How to integrate Vercel Agent Skills with Model Context Protocol (MCP) servers in the Antigravity ecosystem.

## Overview

**Model Context Protocol (MCP)** provides standardized tool access for AI agents. **Agent Skills** provide workflow instructions and organizational patterns. Together, they create a powerful combination:

- **MCP**: Provides tools (APIs, file operations, system access)
- **Skills**: Provides workflows (how to use tools effectively)

## Architecture Integration

```
┌─────────────────────────────────────────────┐
│ Agent (Claude, GPT, Gemini, etc.)          │
├─────────────────────────────────────────────┤
│ ┌─────────────────┐   ┌─────────────────┐  │
│ │ Agent Skills    │   │ MCP Servers     │  │
│ │ (Instructions)  │◄──┤ (Tools)         │  │
│ └─────────────────┘   └─────────────────┘  │
│         ▲                      ▲            │
│         │                      │            │
│         │  ┌──────────────────┐│            │
│         └──┤ Orchestrator     ├┘            │
│            └──────────────────┘             │
└─────────────────────────────────────────────┘
```

## Skill-MCP Coordination Patterns

### Pattern 1: Skill Declares Required MCP Servers

Skills can declare which MCP servers they need:

```yaml
---
name: github-pr-workflow
description: "Create pull requests following organizational standards"
version: 1.0.0

# Declare required MCP servers
requires:
  mcp_servers:
    - github
    - linear
  tools:
    - github.create_pr
    - github.list_issues
    - linear.create_issue
---

# GitHub PR Workflow

This skill uses the GitHub MCP server to create pull requests.

## Instructions

1. Use `github.get_repo_info` to check branch protection rules
2. Use `github.create_pr` with our standard template
3. Use `linear.create_issue` to track the PR in Linear
```

### Pattern 2: Skill Guides Tool Usage

Skills provide best practices for using MCP tools:

```markdown
## Creating a Pull Request

### Step 1: Gather Context
```bash
# Use GitHub MCP server
Tool: github.get_repo_info
Args: { repository: "org/repo" }

# Check current branch status
Tool: github.get_branch
Args: { repository: "org/repo", branch: "feature/new-feature" }
```

### Step 2: Create PR
```bash
Tool: github.create_pr
Args: {
  repository: "org/repo",
  title: "feat: Add new feature",
  body: "$(cat <<'EOF'
## Summary
- Feature 1
- Feature 2

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass

🤖 Generated with Claude Code
EOF
)",
  base: "main",
  head: "feature/new-feature",
  draft: false
}
```

### Step 3: Add Labels and Reviewers
```bash
# Our organizational standard: all PRs need these labels
Tool: github.add_labels
Args: {
  repository: "org/repo",
  issue_number: $PR_NUMBER,
  labels: ["ready-for-review", "needs-qa"]
}

# Auto-assign reviewers based on CODEOWNERS
Tool: github.request_reviewers
Args: {
  repository: "org/repo",
  pull_number: $PR_NUMBER,
  reviewers: ["tech-lead", "senior-engineer"]
}
```
```

### Pattern 3: Skill Validates Tool Outputs

Skills can include validation logic:

```markdown
## Validation

After creating the PR, verify:

1. **PR created successfully**
   ```bash
   Tool: github.get_pr
   Args: { repository: "org/repo", pull_number: $PR_NUMBER }

   Expected: status = "open"
   Expected: draft = false
   Expected: labels include ["ready-for-review"]
   ```

2. **Branch protection checks passed**
   ```bash
   Tool: github.get_pr_status
   Args: { repository: "org/repo", pull_number: $PR_NUMBER }

   Expected: required_status_checks all passing
   Expected: required_reviews = 2
   ```

3. **CI/CD triggered**
   ```bash
   Tool: github.list_check_runs
   Args: { repository: "org/repo", ref: $HEAD_SHA }

   Expected: at least one check run with status = "in_progress"
   ```
```

## Antigravity MCP Server Integration

### Available MCP Servers in Antigravity

From `.claude/settings.json`:

```json
{
  "mcpServers": {
    "antigravity-agents": {
      "command": "python",
      "args": [".agent/mcp/agents-server.py"],
      "description": "35 agentes como herramientas MCP"
    },
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "linear": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-linear"],
      "env": {
        "LINEAR_API_KEY": "${LINEAR_API_KEY}"
      }
    }
  }
}
```

### Skill Declaration for Antigravity

Extended YAML frontmatter:

```yaml
---
name: feature-implementation-workflow
description: "Complete workflow for implementing new features"
version: 1.0.0

# Standard Vercel fields
tags: [development, workflow, feature]
author: Antigravity Team

# Antigravity extensions
antigravity:
  tier: 2                           # Development Core tier
  compatible_agents:
    - planner
    - architect
    - frontend-specialist
    - backend-specialist

  # MCP integration
  required_mcp_servers:
    - github                        # For repository operations
    - linear                        # For issue tracking

  required_tools:
    - github.create_branch
    - github.create_pr
    - github.get_repo_info
    - linear.create_issue
    - linear.update_issue

  optional_tools:
    - github.create_issue_comment   # For PR discussions
    - linear.create_comment         # For issue updates

  # Resource requirements
  memory_usage: medium
  estimated_tokens: 3000
  estimated_duration: "10-30 minutes"
---
```

## Dynamic MCP Server Discovery

Skills can query available MCP servers at runtime:

```markdown
## Pre-Flight Check

Before executing this skill, verify MCP servers are available:

1. **Check GitHub MCP server**
   ```
   Query: Is github MCP server connected?
   Fallback: Use Bash with `gh` CLI if MCP unavailable
   ```

2. **Check Linear MCP server**
   ```
   Query: Is linear MCP server connected?
   Fallback: Skip Linear integration, log warning
   ```

## Execution Decision Tree

```
IF github MCP available:
  → Use github.create_pr (preferred)
ELSE IF gh CLI available:
  → Use Bash: gh pr create (fallback)
ELSE:
  → Fail with error: "Cannot create PR, no GitHub access"
```
```

## Skill-Driven MCP Configuration

Skills can suggest MCP server configurations:

```markdown
## Required Setup

This skill requires the GitHub MCP server. To configure:

1. **Install MCP server**
   ```bash
   npm install -g @modelcontextprotocol/server-github
   ```

2. **Add to .claude/settings.json**
   ```json
   {
     "mcpServers": {
       "github": {
         "command": "npx",
         "args": ["@modelcontextprotocol/server-github"],
         "env": {
           "GITHUB_TOKEN": "${GITHUB_TOKEN}"
         }
       }
     }
   }
   ```

3. **Set environment variable**
   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```

4. **Verify connection**
   ```bash
   # Agent should be able to call:
   github.get_user → returns authenticated user info
   ```
```

## Multi-Server Orchestration

Skills can coordinate multiple MCP servers:

```markdown
## Cross-Platform Workflow

This skill orchestrates GitHub (code) and Linear (project management):

### Step 1: Create Linear Issue
```bash
Tool: linear.create_issue
Args: {
  teamId: "${LINEAR_TEAM_ID}",
  title: "Implement feature X",
  description: "Detailed requirements...",
  priority: 1,
  labels: ["feature", "in-progress"]
}

Output: issue_id = "ISS-123"
```

### Step 2: Create GitHub Branch
```bash
Tool: github.create_branch
Args: {
  repository: "org/repo",
  branch: "feature/ISS-123-feature-x",
  from_branch: "main"
}
```

### Step 3: Link Issue to Branch
```bash
Tool: linear.update_issue
Args: {
  issueId: "ISS-123",
  branchName: "feature/ISS-123-feature-x",
  gitBranchFormat: "org/repo/feature/ISS-123-feature-x"
}
```

### Step 4: Implement Feature
[... implementation steps ...]

### Step 5: Create PR
```bash
Tool: github.create_pr
Args: {
  repository: "org/repo",
  title: "feat: Implement feature X (ISS-123)",
  body: "Closes ISS-123\n\n[PR description]",
  base: "main",
  head: "feature/ISS-123-feature-x"
}

Output: pr_number = 456
```

### Step 6: Update Linear Issue
```bash
Tool: linear.update_issue
Args: {
  issueId: "ISS-123",
  state: "In Review",
  prUrl: "https://github.com/org/repo/pull/456"
}
```
```

## Error Handling with MCP

Skills should handle MCP server failures gracefully:

```markdown
## Error Handling

### MCP Server Unavailable

IF MCP server fails:
1. Log error with details
2. Attempt fallback method (e.g., Bash with CLI)
3. If no fallback, fail with actionable error message

Example:
```
Error: GitHub MCP server not responding
Attempted: github.create_pr
Fallback: Attempting `gh pr create` via Bash
Result: [Success/Failure]

If all methods fail:
Error: Cannot create PR. Please:
1. Check GitHub MCP server connection
2. Verify GITHUB_TOKEN environment variable
3. Or use `gh` CLI manually: gh pr create --title "..." --body "..."
```
```

### Tool Not Available

```markdown
IF required tool missing:
1. Check if alternative tool available
2. Suggest manual workaround
3. Fail with helpful error

Example:
```
Error: Tool 'github.create_issue_comment' not available
Required for: Adding automated PR comments
Workaround: Comments can be added manually in GitHub UI
Alternative: Use `gh pr comment` via Bash
```
```

## Testing MCP Integration

### Validation Script

```python
#!/usr/bin/env python3
"""Validate MCP integration for agent skills."""

from typing import List, Dict
import json

def validate_mcp_requirements(skill_metadata: Dict, available_servers: List[str]) -> bool:
    """Check if required MCP servers are available."""

    required = skill_metadata.get('antigravity', {}).get('required_mcp_servers', [])
    optional = skill_metadata.get('antigravity', {}).get('optional_mcp_servers', [])

    # Check required servers
    missing_required = [s for s in required if s not in available_servers]
    if missing_required:
        print(f"❌ Missing required MCP servers: {missing_required}")
        return False

    # Warn about optional servers
    missing_optional = [s for s in optional if s not in available_servers]
    if missing_optional:
        print(f"⚠️  Optional MCP servers unavailable: {missing_optional}")

    print(f"✅ All required MCP servers available: {required}")
    return True


def validate_tool_availability(skill_metadata: Dict, available_tools: List[str]) -> bool:
    """Check if required tools are available."""

    required = skill_metadata.get('antigravity', {}).get('required_tools', [])
    optional = skill_metadata.get('antigravity', {}).get('optional_tools', [])

    # Check required tools
    missing_required = [t for t in required if t not in available_tools]
    if missing_required:
        print(f"❌ Missing required tools: {missing_required}")
        return False

    # Warn about optional tools
    missing_optional = [t for t in optional if t not in available_tools]
    if missing_optional:
        print(f"⚠️  Optional tools unavailable: {missing_optional}")

    print(f"✅ All required tools available: {required}")
    return True


# Usage
if __name__ == '__main__':
    # Load skill metadata
    skill = {
        'antigravity': {
            'required_mcp_servers': ['github', 'linear'],
            'required_tools': ['github.create_pr', 'linear.create_issue']
        }
    }

    # Query available servers/tools (from agent environment)
    available_servers = ['github', 'linear', 'antigravity-agents']
    available_tools = ['github.create_pr', 'github.get_repo_info', 'linear.create_issue']

    # Validate
    servers_ok = validate_mcp_requirements(skill, available_servers)
    tools_ok = validate_tool_availability(skill, available_tools)

    if servers_ok and tools_ok:
        print("\n✅ Skill is ready to execute")
    else:
        print("\n❌ Skill cannot execute due to missing dependencies")
```

## Best Practices

### 1. Declare Dependencies Explicitly

Always declare required MCP servers in YAML frontmatter:

```yaml
antigravity:
  required_mcp_servers: [github, linear]
  optional_mcp_servers: [slack]
```

### 2. Provide Fallbacks

When possible, offer fallback methods:

```markdown
Primary: Use github MCP server (github.create_pr)
Fallback 1: Use gh CLI via Bash
Fallback 2: Manual instructions for user
```

### 3. Validate Before Executing

Check MCP availability before starting workflow:

```markdown
## Pre-Execution Checklist
- [ ] GitHub MCP server connected
- [ ] GitHub token valid
- [ ] Required tools available
- [ ] Repository accessible
```

### 4. Handle Errors Gracefully

Never fail silently. Provide actionable error messages:

```
❌ Error: github.create_pr failed
Reason: Rate limit exceeded (remaining: 0, resets in 45 minutes)
Action: Wait 45 minutes or use personal access token with higher limits
Workaround: Create PR manually: gh pr create --title "..." --body "..."
```

### 5. Document Tool Usage

Show exact tool calls with expected inputs/outputs:

```markdown
Tool: github.create_pr
Input: {
  repository: "org/repo",
  title: "feat: Add feature",
  base: "main",
  head: "feature/new-feature"
}
Expected Output: {
  number: 123,
  html_url: "https://github.com/org/repo/pull/123",
  state: "open"
}
```

## Antigravity-Specific Patterns

### Agent-to-MCP Communication

Antigravity agents can use MCP servers through skills:

```python
# .agent/agents/feature-developer/main.py
from antigravity.core import AntigravityAgent
from antigravity.skills import load_skill

class FeatureDeveloper(AntigravityAgent):
    async def execute(self, task: str):
        # Load skill with MCP requirements
        skill = load_skill("feature-implementation-workflow")

        # Verify MCP servers available
        if not await self.verify_mcp_servers(skill.required_mcp_servers):
            raise RuntimeError("Required MCP servers not available")

        # Execute skill with MCP tools
        result = await self.execute_skill(skill, task)

        return result
```

### MCP Server as Agent Tool

The Antigravity MCP server exposes agents as tools:

```bash
# Available via MCP
Tool: antigravity.invoke_agent
Args: {
  agent: "explorer",
  task: "Analyze authentication module"
}

# Skill can orchestrate multiple agents
Tool: antigravity.invoke_agent
Args: {
  agent: "architect",
  task: "Design API architecture"
}

Tool: antigravity.invoke_agent
Args: {
  agent: "api-designer",
  task: "Implement API endpoints based on architecture"
}
```

## Conclusion

**Agent Skills + MCP = Powerful Combination**

- Skills provide **workflow intelligence** (what to do)
- MCP provides **tool access** (how to do it)
- Together they enable **autonomous, reliable execution**

**Key Takeaways:**

1. Declare MCP dependencies explicitly in skill metadata
2. Provide fallback methods when possible
3. Validate MCP availability before execution
4. Handle errors gracefully with actionable messages
5. Document tool usage with examples
6. Test across different MCP configurations

This integration pattern allows skills to be **portable** (work with any MCP-compatible agent) while remaining **practical** (degrade gracefully when MCP unavailable).
