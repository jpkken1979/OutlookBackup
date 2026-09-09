---
description: Sincronizacion automatica de NotebookLM (inject + map + resync)
argument-hint: [status|app|workspace|workspace-associate|workspace-full]
allowed-tools: Bash, Read
---

Comando rapido para dejar NotebookLM sincronizado y actualizado.

Modos:

- `status`: valida estado base (`bridge status` + `workflow doctor`).
- `app`: sincroniza solo la app actual (inject local).
- `workspace`: sincroniza root + subrepos (inject masivo).
- `workspace-associate`: inject masivo + auto mapeo `project -> notebook_id` por similitud de titulo.
- `workspace-full`: inject masivo + auto mapeo + `resync` de fuentes registradas.

Reglas:

1. Si `nlm login --check` falla, hay que reautenticar primero.
2. Si Chrome esta abierto y bloquea login CDP, cerrar Chrome completo y relanzar login.
3. No subir secretos ni credenciales tecnicas.

Ejecucion por argumento:

- Sin argumentos o `status`:
!`python .agent/scripts/notebooklm_bridge.py status && python .agent/scripts/notebooklm_workflow.py doctor`

- `app`:
!`python .agent/scripts/notebooklm_sync_all.py`

- `workspace`:
!`python .agent/scripts/notebooklm_sync_all.py --workspace`

- `workspace-associate`:
!`python .agent/scripts/notebooklm_sync_all.py --workspace --associate`

- `workspace-full`:
!`python .agent/scripts/notebooklm_sync_all.py --workspace --associate --resync`
