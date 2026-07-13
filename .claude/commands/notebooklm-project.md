---
description: Gestionar notebooks por proyecto
argument-hint: [list|active [project]|set <project> <notebook-id> --title "..."]
allowed-tools: Bash, Read
---

Gestiona el registry local ignorado `.agent/notebooklm/projects.json`.

Usos:

- `list`: muestra proyectos asociados.
- `active [project]`: muestra o cambia el proyecto activo.
- `set <project> <notebook-id> --title "..."`: asocia un proyecto a un notebook.

No edites el JSON a mano salvo emergencia.

Resultado:
!`python .agent/scripts/notebooklm_workflow.py project $ARGUMENTS`
