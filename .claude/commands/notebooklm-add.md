---
description: Subir una fuente a NotebookLM
argument-hint: [--new "Titulo"|--project nombre|--notebook-id id] [--force-sensitive] <archivo|url|texto>
allowed-tools: Bash, Read
---

Sube una fuente a NotebookLM usando el workflow del repo.

Reglas:

1. En este repo privado, reportes internos, Excel, DBs de trabajo y nomina son
   permitidos por la politica `private_repo_trusted`.
2. Si el script bloquea, asumilo como credencial tecnica real (`.env`, cookie,
   clave privada o token embebido); no lo fuerces automaticamente.
3. Si falta notebook asociado, explica que debe usar `--new "Titulo"` o
   `--notebook-id NOTEBOOK_ID`.
4. Si crea un notebook con `--new`, queda registrado como notebook del proyecto.
5. Reporta el notebook/proyecto usado y si `--wait` completo el procesamiento.

Resultado:
!`python .agent/scripts/notebooklm_workflow.py add $ARGUMENTS`
