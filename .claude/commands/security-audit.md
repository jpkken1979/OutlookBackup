---
description: Auditoría de seguridad del ecosistema
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, Agent
---

Ejecuta una auditoría de seguridad completa del repositorio actual:

1. **Python**: Verificar que no hay `shell=True` en subprocess, no secrets hardcodeados, no `eval()` o `exec()` inseguros
2. **TypeScript**: Verificar path validation, no `any` en tipos, no XSS potencial
3. **MCP**: Verificar CORS, rate limiting, path traversal protection
4. **Dependencies**: Ejecutar `pip-audit` y `npm audit`
5. **Docker**: Verificar que no hay passwords hardcodeados

Reportar hallazgos con severidad (CRITICAL, HIGH, MEDIUM, LOW) y archivos afectados.
