# Regla: Ecosistema MCP-First

Aplica a todas las sesiones en este repositorio.

## Principio

- El ecosistema se usa **primero por MCP**, no por autodescubrimiento local masivo.
- Skills y agentes existen en `.agent/`, pero no deben inflar el contexto base de Claude Code.
- Si una capacidad ya existe en MCP, se consulta on-demand.

## Orden de uso

1. MCP: el broker `antigravity` es la UNICA entrada (`.mcp.json`). Sus seis
   meta-tools, en este orden:
   - `antigravity_search` — empezar siempre aca, busca la capacidad por texto libre
   - `antigravity_describe` — ver firma/params de lo que encontro el search
   - `antigravity_run_skill` / `antigravity_run_agent` — ejecutar
   - `antigravity_call` — connectors puntuales (brain, mem0, watcher, context7…)
   - `antigravity_status` — salud del broker y del gateway
2. CLI directo solo si MCP no cubre el caso:
   - `python .agent/scripts/invoke-agent.py`
3. Lectura directa de archivos solo como fallback:
   - `.agent/agents/*`
   - `.agent/skills/*`

## Resolución compartida

- Si la app tiene skill/agente local, usarlo primero — `antigravity_search` ya
  resuelve con precedencia proyecto > usuario > bundle.
- El fallback remoto lo resuelve el propio broker contra el gateway; ya no hay un
  server `antigravity-remote` aparte que registrar.
- No copiar skills/agentes al proyecto solo para hacer discovery: las 43 apps del
  monorepo comparten el mismo broker en `:4747/mcp` (migradas 2026-07-28).

## Evitar

- Cargar cientos de skills al contexto base.
- Duplicar agentes locales de Claude si el broker ya los expone.
- Duplicar skills/agentes dentro de cada app: alcanza con el discovery del broker.
- Repetir inventarios largos dentro de `CLAUDE.md` o reglas.

## Regla práctica

> Buscar por MCP primero. Leer archivos locales solo cuando el MCP no alcance.
