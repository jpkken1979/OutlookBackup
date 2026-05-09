---
# Regla: Config Guard — OBLIGATORIO antes de tocar configuración crítica
---

Antes de modificar CUALQUIERA de estos archivos, SIEMPRE hacer recall del Brain primero:

| Archivo | Por qué es crítico |
|---|---|
| `~/.claude/settings.json` | Nexus lee SOLO este para verificar hooks de memoria |
| `.claude/settings.json` | Hooks del proyecto — afecta todas las sesiones |
| `.mcp.json` | Rompe todos los servidores MCP si hay error |
| `.env` | Tokens activos — nunca proponer moverlo ni ignorarlo |
| `~/.codex/accounts/` | Snapshots de cuentas Codex — NUNCA borrar sin backup |
| `nexus-app/src-tauri/src/commands/memory.rs` | Lógica que Nexus usa para verificar el estado |

## Protocolo obligatorio antes de tocar cualquiera de estos archivos:

1. Leer `.claude/memory/MEMORY.md` buscando entradas relacionadas
2. Hacer query al Brain: `brain.query("nombre del archivo o tema")`
3. Leer el archivo actual COMPLETO antes de editarlo
4. Verificar que el cambio no rompe dependencias conocidas

## Errores que YA pasaron y están documentados en memoria:

- `bugfix_hooks_global_vs_project.md` — hooks de memoria van en GLOBAL, no en proyecto
- `config_claude_mem_hooks_activated_2026_04_07.md` — cómo se activaron los hooks
- El checker de Nexus lee SOLO `~/.claude/settings.json`, nunca el settings del proyecto

## Regla de oro

> Antes de "mejorar" algo en configuración, preguntarse:
> ¿Consulté la memoria sobre este archivo? ¿Sé quién más depende de este archivo?
> Si la respuesta es NO → leer primero, actuar después.
