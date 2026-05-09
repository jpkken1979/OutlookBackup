---
name: nexus
description: Nexus desktop app integration — UI components, Tauri commands, agent orchestration, and desktop ecosystem management
version: "1.0.0"
author: antigravity
tags: [nexus, desktop, tauri, ui, agents, skills]
requirements:
type: feature
---
  - nexus-app running
type: feature
---

# Nexus Integration Skill

Provides integration capabilities for the Antigravity Nexus desktop application (Tauri 2 + React 19).

## Capabilities

- **UI Component Kit**: Premium React components with Glassmorphism, Glow effects, and Tailwind v4 styling (`ui_component_kit.md`)
- **UI/UX Architect**: Figma-to-React conversion with Stitches/Styled-components and design system enforcement (`ui_ux_architect.md`)
- **Agent Debate**: Multi-agent consensus orchestration for complex architecture and security decisions (`agent_debate.md`)
- **Skill Miner**: Automatic knowledge mining from Python codebases to generate skill catalog entries (`skill_miner.md`)
- **Self Healing**: Autonomous error recovery and resilience patterns (`self_healing.md`)
- **Shadow Workspace**: Isolated workspace management for safe experimentation (`shadow_workspace.md`)
- **Token Warden**: Token usage monitoring and budget enforcement (`token_warden.md`)

## Usage

This skill is used internally by the Nexus desktop application for ecosystem management operations. Individual sub-skills can be invoked directly:

```bash
# Agent debate for consensus decisions
python scripts/agent_debate.py "<task_description>"

# Skill mining from a codebase
python scripts/skill_miner.py <target_dir>
```

## Design Rules

- Follow `DESIGN_SYSTEM.md` for all visual components
- Use Dark palette (#0a0a0c) with cyan-400 (#22d3ee) primary accents
- Framer Motion variants must be defined outside React components
- Tauri IPC exclusively via `invoke()` — never expose Node APIs directly
