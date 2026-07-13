# Regla: Ecosistema MCP-First

Aplica a todas las sesiones en este repositorio.

## Principio

- El ecosistema se usa **primero por MCP**, no por autodescubrimiento local masivo.
- Skills y agentes existen en `.agent/`, pero no deben inflar el contexto base de Claude Code.
- Si una capacidad ya existe en MCP, se consulta on-demand.

## Orden de uso

1. MCP tools del ecosistema:
   - `antigravity-skills`
   - `antigravity-agents`
   - `antigravity-intelligence`
   - `context7`
2. CLI directo solo si MCP no cubre el caso:
   - `python .agent/scripts/invoke-agent.py`
3. Lectura directa de archivos solo como fallback:
   - `.agent/agents/*`
   - `.agent/skills/*`

## Resolución compartida

- Si la app tiene skill/agente local por MCP, usar eso primero.
- Si no existe localmente o el catálogo local no alcanza, consultar `antigravity-remote`.
- `antigravity-remote` es la biblioteca compartida del ecosistema y debe servir como fallback entre apps y entornos cloud.
- No copiar skills/agentes al proyecto solo para hacer discovery; el discovery compartido va por MCP remoto.

## Evitar

- Cargar cientos de skills al contexto base.
- Duplicar agentes locales de Claude si ya existe servidor MCP equivalente.
- Duplicar skills/agentes dentro de cada app cuando basta con discovery por `antigravity-remote`.
- Repetir inventarios largos dentro de `CLAUDE.md` o reglas.

## Regla práctica

> Buscar por MCP primero. Leer archivos locales solo cuando el MCP no alcance.
