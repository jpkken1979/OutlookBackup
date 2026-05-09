---
name: activator
description: Activa y configura el ecosistema Antigravity en cualquier repositorio
version: 1.0.0
tier: 9
triggers:
  - "activar antigravity"
  - "activate"
  - "configurar agentes"
  - "setup agents"
  - "instalar agentes"
---

# Activator Agent

Agente que configura automaticamente el ecosistema Antigravity Agents en cualquier repositorio.

## Proposito

Cuando el usuario dice "activar", "activate", o "configurar agentes", este agente:
1. Detecta la ubicacion del ecosistema Antigravity
2. Crea/actualiza `.claude/settings.json` con la configuracion MCP
3. Verifica que todo funcione

## Triggers

- "activar antigravity"
- "activate agents"
- "configurar agentes"
- "setup antigravity"
- "instalar agentes"

## Uso

```
Usuario: "Activar antigravity en este proyecto"
Agente: Configura .claude/settings.json automaticamente
```

## Capacidades

1. **Deteccion automatica**: Busca el ecosistema en rutas comunes
2. **Configuracion MCP**: Crea settings.json con el servidor v2
3. **Verificacion**: Prueba que el MCP responda correctamente
4. **Multi-modo**: Soporta referencia externa, copia, o submodulo

## Output

```json
{
  "status": "activated",
  "mcp_server": "/path/to/agents-server-v2.py",
  "agents_available": 62,
  "tools_available": ["execute_agent", "find_best_agent", "get_costs"]
}
```
