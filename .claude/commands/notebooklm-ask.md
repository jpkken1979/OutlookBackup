---
description: Preguntar al NotebookLM del proyecto
argument-hint: [--project nombre|--notebook-id id] "pregunta"
allowed-tools: Bash, Read
---

Pregunta al notebook asociado al proyecto actual o al proyecto indicado.

Reglas:

1. Ejecuta la pregunta con el workflow local.
2. Analiza la respuesta contra la pregunta original.
3. Si faltan riesgos, pasos, fechas, archivos o conclusiones, haz un follow-up
   usando `python .agent/scripts/notebooklm_workflow.py ask ...` con contexto
   suficiente. No hagas mas de dos follow-ups salvo que el usuario lo pida.
4. Responde en espanol y deja claro que la evidencia viene de NotebookLM.

Respuesta inicial:
!`python .agent/scripts/notebooklm_workflow.py ask $ARGUMENTS`
