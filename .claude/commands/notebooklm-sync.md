---
description: Sincronizar NotebookLM con agentes locales
argument-hint: [status|install|login|doctor|mcp-json|setup-claude-code|nlm ...]
allowed-tools: Bash, Read
---

Gestiona la integracion de NotebookLM con Claude Code, Codex, OpenCode y otros
clientes MCP usando el bridge local `.agent/scripts/notebooklm_bridge.py`.

Reglas:

1. Ejecuta `status` si el usuario no dio argumentos.
2. Para login, avisa que se abrira un navegador visible y que el usuario debe
   iniciar sesion en Google.
3. No copies cookies, tokens ni datos de `data/` al chat.
4. Para Codex/OpenCode, usa `mcp-json` y explica donde pegar el JSON segun el
   cliente que el usuario indique.
5. Si el comando falla porque `claude`, `uv`, `pipx` o `nlm` no estan en PATH,
   usa el bridge local; no requieras instalacion global.
6. Para crear o alimentar notebooks desde archivos generados por agentes, usa:
   - `nlm notebook create "Titulo"`
   - `nlm source add NOTEBOOK_ID --file "ruta\\archivo.pdf" --wait`
   - `nlm source add NOTEBOOK_ID --url "https://..." --wait`
   - `nlm source add NOTEBOOK_ID --text "contenido" --title "Titulo" --wait`
   - `nlm notebook query NOTEBOOK_ID "pregunta"`
7. Nunca subas archivos sensibles a NotebookLM sin que el usuario lo pida.

Estado o accion:
!`python .agent/scripts/notebooklm_bridge.py $ARGUMENTS`
