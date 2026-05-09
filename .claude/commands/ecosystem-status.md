---
description: Estado completo del ecosistema Antigravity
allowed-tools: Read, Bash, Grep, Glob
---

Muestra el estado completo del ecosistema:

1. **Gateway**: verificar si `:4747` responde
2. **Agentes**: contar activos vs deprecated
3. **Skills**: contar por categoría (base, custom, plugins)
4. **MCP Servers**: verificar cuáles están activos en `.mcp.json`
5. **Tests**: ejecutar `make test-quick` y reportar resultados
6. **Memoria**: verificar estado de antigravity-memory
7. **Nexus**: verificar si compila (`cd nexus-app && npm run ts:app`)

Formato: tabla resumen con indicadores verde/rojo.
