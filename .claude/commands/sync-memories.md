---
description: Sincronizar memorias al repositorio para compartir entre PCs
allowed-tools: Read, Write, Bash, Glob
---

Sincroniza las memorias de Claude Code al repositorio:

1. Copiar archivos de `~/.claude/projects/*/memory/` que correspondan a este proyecto a `.claude/memory/`
2. Verificar que `.claude/memory/MEMORY.md` está actualizado
3. Listar los archivos nuevos/modificados
4. Sugerir al usuario hacer commit de los cambios
