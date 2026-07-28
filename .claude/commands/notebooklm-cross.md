---
description: Preguntar a VARIOS notebooks de NotebookLM a la vez (cross-notebook)
argument-hint: ["pregunta"] [--notebooks "OpenAntigravity Memory Book, KobetsuV3 Memory Book"]
allowed-tools: mcp__notebooklm-mcp__cross_notebook_query, mcp__notebooklm-mcp__notebook_list, Read
---

Consulta cruzada sobre varios notebooks — para preguntas que cruzan proyectos
(p. ej. "¿cómo comparte el ecosistema los hooks entre OpenAntigravity y
KobetsuV3?" o decisiones que afectan a más de una app).

Reglas:

1. Usá la tool MCP `cross_notebook_query` con la pregunta del usuario.
2. Si el usuario no especificó notebooks (`--notebooks`), usá por defecto los
   registrados en `.agent/notebooklm/projects.json` (leé el archivo y pasá los
   títulos como `notebook_names` separados por coma). NO uses `all=True` salvo
   pedido explícito — hay rate limits.
3. Presentá la respuesta agregada citando de qué notebook sale cada evidencia.
4. Si un notebook no responde por auth, recordá que el refresh corre solo cada
   8h (tarea "Antigravity NotebookLM AuthRefresh"); para forzarlo:
   `.venv-mcp/notebooklm/Scripts/nlm.exe login`.
5. Respondé en español y contrastá con archivos locales si hay conflicto.
