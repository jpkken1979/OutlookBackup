---
description: Diagnostico unificado de NotebookLM
argument-hint: []
allowed-tools: Bash, Read
---

Ejecuta el doctor unificado de NotebookLM y resume:

- login valido
- notebooks accesibles
- clientes MCP configurados
- JSON MCP valido
- proyecto activo del registry local

Resultado:
!`python .agent/scripts/notebooklm_workflow.py doctor`
