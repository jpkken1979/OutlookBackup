---
description: Usar NotebookLM desde Claude Code
argument-hint: [status|auth|list|ask|add|mcp] [...]
allowed-tools: Bash, Read
---

Usa la skill local `notebooklm` en `.agent/skills/notebooklm/`. No llames sus
scripts directamente: siempre usa `python scripts/run.py ...` desde el directorio
de la skill.

Interpreta `$ARGUMENTS` asi:

- Sin argumentos o `status`: verificar autenticacion con
  `python scripts/run.py auth_manager.py status`.
- `auth` o `setup`: abrir autenticacion visible con
  `python scripts/run.py auth_manager.py setup` y avisar que el usuario debe
  iniciar sesion en Google.
- `list`: listar notebooks con `python scripts/run.py notebook_manager.py list`.
- `ask <pregunta>`: preguntar con
  `python scripts/run.py ask_question.py --question "<pregunta>"`.
- `add <url>`: primero hacer smart discovery preguntando al notebook que contiene;
  despues agregarlo con nombre, descripcion y topics derivados. Si discovery falla,
  pedir esos metadatos al usuario.
- `mcp`: mostrar la guia `docs/guides/NOTEBOOKLM_IDE_INTEGRATION.md` y explicar la
  ruta recomendada para Claude Code, Codex, Cursor, Windsurf y GitHub Copilot.

Reglas:

1. Comprueba auth antes de `ask`, `add` o `list`.
2. Si falta auth, ejecuta `auth_manager.py setup` y espera a que el usuario termine.
3. Cuando la respuesta de NotebookLM termine preguntando si falta algo, analiza gaps
   y haz follow-ups antes de responder al usuario.
4. Responde en espanol, citando que la respuesta viene de NotebookLM si se uso.

Directorio de ejecucion:
!`cd .agent/skills/notebooklm && python scripts/run.py auth_manager.py status`
