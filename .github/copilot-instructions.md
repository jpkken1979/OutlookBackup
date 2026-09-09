# AI Copilot Instructions — Antigravity Ecosystem

## Version
- Antigravity: 5.0.0
- Gateway: http://localhost:4747

## Agents (145 agentes)

### Tier 0- `debugger`- `performance-optimizer`
### Tier 1- `project-planner`- `super-orchestrator`
### Tier 2- `code-reviewer`- `coder`
### Tier 3- `docs-specialist`- `local-executor`- `qa-automation-engineer`
### Specialized / No-tier (136 agents)- `__pycache__`- `_archive`- `_docs`- `a11y`- `activator`- `agent-composer`- `analyst`- `analytics-analyst`- `api-designer`- `api-gateway-specialist`- ... y 126 mas

## Skills
- Base: `.agent/skills/` (801 skills)
- Custom: `.agent/skills-custom/` (52 skills)
- Plugins: `.agent/plugins/` (78 skills)

<!-- ANTIGRAVITY-START -->
# GitHub Copilot Instructions — Antigravity Ecosystem

This workspace runs **Antigravity v6.1.4** with 142 agents
and a modular MCP runtime. Installed by Nexus on 2026-08-13.

## Gateway & MCP Servers

- Local gateway: `http://localhost:4747` (port 4747)
- Registered servers (from `.mcp.json`): `antigravity`, `playwright`
- Universal adapter: `.antigravity/nexus-client.json`
- Live contract: `GET /v1/nexus/manifest`
- `antigravity` is a **broker**, not one server per capability: everything is
  reached through six meta-tools (`antigravity_search`, `antigravity_describe`,
  `antigravity_run_skill`, `antigravity_run_agent`, `antigravity_call`,
  `antigravity_status`). Memory (mem0) and Brain are connectors of
  `antigravity_call`, not standalone servers.
- Agents and skills stay in Nexus and are loaded on demand. Do not bulk-copy
  the catalog unless the user explicitly requests an offline bundle.
- Resolve credentials only through the adapter reference; never write a token
  into this file or generated MCP configuration.

## Agent Tiers

### Tier 0
- `debugger`
- `performance-optimizer`

### Tier 1
- `project-planner`
- `super-orchestrator`

### Tier 2
- `code-reviewer`
- `coder`

### Tier 3
- `docs-specialist`
- `local-executor`
- `qa-automation-engineer`

### Specialized / No-tier (133 agents)
- `a11y`
- `activator`
- `agent-composer`
- `analyst`
- `analytics-analyst`
- `api-designer`
- `api-gateway-specialist`
- `api-tester`
- `app-auditor`
- `app-creator`
- _(and 123 more — see `.agent/agents/`)_

## Key Entry Points

- `.mcp.json` — MCP server config (auto-generated, all IDEs)
- `.antigravity/config.json` — ecosystem config (gateway, version, policy)
- `.antigravity/nexus-client.json` — versioned discovery adapter for all clients
- `.antigravity/rules.md` — project-specific rules
- `ESTADO_PROYECTO.md` — project memory (read before starting work)
- `.agent/agents/` — all agents (each has `IDENTITY.md` + `SYSTEM_PROMPT.md`)
- `.agent/skills/` — modular skills library

## Workflow

1. Find the capability first: `antigravity_search`, then `antigravity_describe`.
2. Execute with `antigravity_run_agent` (complex tasks) or `antigravity_run_skill`.
3. Read `ESTADO_PROYECTO.md` before starting any session.
4. Respect constraints in `.antigravity/rules.md` and `.claude/rules/`.
<!-- ANTIGRAVITY-END -->