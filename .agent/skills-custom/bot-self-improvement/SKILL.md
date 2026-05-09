---
name: bot-self-improvement
description: Analyzes OpenGravity bot logs and failures to suggest new tools, skills, and improvements. Run when the bot repeatedly fails at the same type of task.
triggers:
  - "mejorar bot"
  - "analizar fallos bot"
  - "bot se rompe con"
  - "añadir capacidad"
  - "bot no puede"
version: "1.0.0"
author: antigravity
---

# Bot Self-Improvement Skill

## Purpose
Analyze bot failure patterns and propose concrete improvements: new tools, better prompts, or new skills.

## Input
- Recent bot logs or failure description
- Type of request the bot failed to handle

## Output
- Root cause analysis
- Specific code changes to fix the issue
- New tool or skill to create if needed

## Process
1. Analyze the failure type (schema crash, missing tool, wrong LLM response)
2. Identify the fix (add tool, update prompt, add validator fallback)
3. Generate the implementation code
4. Optionally create a new skill if the gap is systematic

## Usage
```bash
python .agent/skills-custom/bot-self-improvement/scripts/main.py --failure "descripcion del fallo" --json
```
